"""Subtitle generation and burning utilities."""
from __future__ import annotations

import argparse
import logging
import re
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import cv2

LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL = "small"
TARGET_LANGUAGE = "en"

EMOJI_TRIGGERS: Sequence[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"\\b(?:thanks|thank you)\\b", re.IGNORECASE), "🙏"),
    (re.compile(r"\\b(?:yes|yeah|yep)\\b", re.IGNORECASE), "✅"),
    (re.compile(r"\\b(?:no|nah|nope)\\b", re.IGNORECASE), "❌"),
    (re.compile(r"\\b(?:money|million|invoice|paid)\\b", re.IGNORECASE), "💰"),
    (re.compile(r"\\b(?:idea|think|brainstorm)\\b", re.IGNORECASE), "💡"),
    (re.compile(r"\\b(?:wow|amazing|incredible)\\b", re.IGNORECASE), "🤯"),
    (re.compile(r"\\b(?:joke|funny|laugh)\\b", re.IGNORECASE), "😂"),
    (re.compile(r"\\b(?:win|success|victory)\\b", re.IGNORECASE), "🏆"),
    (re.compile(r"100", re.IGNORECASE), "💯"),
]

EMOJI_LOOKUP = [emoji for _, emoji in EMOJI_TRIGGERS]


@dataclass
class StyleConfig:
    font_name: str = "Arial"
    font_size: int = 26
    margin_v: int = 120
    outline: float = 2.0
    shadow: float = 0.0
    alignment: int = 2
    margin_l: int = 80
    margin_r: int = 80
    primary_colour: str = "&H00FFFFFF"
    secondary_colour: str = "&H00000000"
    outline_colour: str = "&H00000000"
    back_colour: str = "&H00000000"
    play_res_x: int = 1080
    play_res_y: int = 1920
    emoji_font: Optional[str] = "Apple Color Emoji"


@dataclass
class SubtitleBlock:
    index: int
    start: str
    end: str
    lines: List[str]


@dataclass
class ProcessResult:
    source_video: Path
    output_video: Path
    srt_path: Path
    ass_path: Path


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="[%(levelname)s] %(message)s")


def whisper_srt(video: Path, *, model: str = DEFAULT_MODEL, force: bool = False) -> Path:
    video = video.resolve()
    output_dir = video.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    expected = output_dir / f"{video.stem}.srt"
    if expected.exists() and not force:
        LOGGER.info("Reusing existing SRT for %s", video.name)
        return expected

    cmd = [
        sys.executable,
        "-m",
        "whisper",
        str(video),
        "--model",
        model,
        "--output_format",
        "srt",
        "--output_dir",
        str(output_dir),
        "--language",
        TARGET_LANGUAGE,
    ]

    LOGGER.info("Running Whisper on %s", video.name)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:  # pylint: disable=broad-except
        raise RuntimeError(f"Whisper failed for {video.name}") from exc

    if expected.exists():
        return expected

    matches = list(output_dir.glob(f"{video.stem}*.srt"))
    if not matches:
        raise FileNotFoundError(f"Whisper did not produce an SRT for {video.name}")
    return matches[0]


def parse_srt(path: Path) -> List[SubtitleBlock]:
    content = path.read_text(encoding="utf-8")
    lines = [line.rstrip("\r") for line in content.splitlines()]
    blocks: List[SubtitleBlock] = []
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        index_line = lines[i].strip()
        if not index_line.isdigit():
            i += 1
            continue
        index = int(index_line)
        i += 1
        if i >= len(lines):
            break
        timing = lines[i].strip()
        i += 1
        if "-->" not in timing:
            continue
        start, end = [part.strip() for part in timing.split("-->")]
        text_lines: List[str] = []
        while i < len(lines) and lines[i].strip():
            text_lines.append(lines[i])
            i += 1
        blocks.append(SubtitleBlock(index=index, start=start, end=end, lines=text_lines))
        while i < len(lines) and not lines[i].strip():
            i += 1
    return blocks


def write_srt(blocks: Iterable[SubtitleBlock], path: Path) -> None:
    parts: List[str] = []
    for block in blocks:
        parts.append(str(block.index))
        parts.append(f"{block.start} --> {block.end}")
        parts.extend(block.lines)
        parts.append("")
    content = "\r\n".join(parts)
    if not content.endswith("\r\n"):
        content += "\r\n"
    path.write_text(content, encoding="utf-8")


def inject_emojis(srt: Path, *, enable: bool = True, triggers: Sequence[Tuple[re.Pattern[str], str]] = EMOJI_TRIGGERS) -> Path:
    if not enable:
        return srt
    blocks = parse_srt(srt)
    changed = False
    for block in blocks:
        if not block.lines:
            continue
        last_line = block.lines[-1]
        for pattern, emoji in triggers:
            if pattern.search(last_line):
                if emoji not in last_line:
                    block.lines[-1] = last_line + " " + emoji
                    changed = True
                break
    if not changed:
        LOGGER.info("No emoji triggers fired for %s", srt.name)
        return srt

    output = srt.with_name(f"{srt.stem}_emoji{srt.suffix}")
    write_srt(blocks, output)
    LOGGER.info("Injected emojis into %s", output.name)
    return output


def _parse_timestamp_to_cs(value: str) -> int:
    hours, minutes, rest = value.split(":")
    seconds, millis = rest.split(",")
    total_millis = (
        int(hours) * 3600000
        + int(minutes) * 60000
        + int(seconds) * 1000
        + int(millis)
    )
    return int(round(total_millis / 10))


def _format_ass_time(cs: int) -> str:
    hours, remainder = divmod(cs, 360000)
    minutes, remainder = divmod(remainder, 6000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"


def escape_ass(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _split_line_emoji(text: str) -> Tuple[str, Optional[str]]:
    trimmed = text.rstrip()
    for emoji in EMOJI_LOOKUP:
        token = emoji
        with_space = f" {emoji}"
        if trimmed.endswith(with_space):
            return trimmed[: -len(with_space)], emoji
        if trimmed.endswith(token):
            return trimmed[: -len(token)], emoji
    return text, None


def _format_event_text(lines: List[str], style: StyleConfig) -> str:
    formatted_lines: List[str] = []
    for i, line in enumerate(lines):
        base, emoji = _split_line_emoji(line if i == len(lines) - 1 else line)
        base_escaped = escape_ass(base)
        if emoji and style.emoji_font:
            emoji_chunk = f"{{\\fn{escape_ass(style.emoji_font)}}}{escape_ass(emoji)}{{\\r}}"
            if base_escaped and not base_escaped.endswith(" "):
                base_escaped = base_escaped + r"\h"
            formatted_lines.append(base_escaped + emoji_chunk)
        elif emoji:
            if base_escaped and not base_escaped.endswith(" "):
                base_escaped = base_escaped + r"\h"
            formatted_lines.append(base_escaped + escape_ass(emoji))
        else:
            formatted_lines.append(base_escaped)
    return r"\N".join(formatted_lines)


def srt_to_ass(
    srt: Path,
    ass: Path,
    style: StyleConfig,
    *,
    video_size: Optional[Tuple[int, int]] = None,
) -> None:
    blocks = parse_srt(srt)
    if not blocks:
        raise RuntimeError(f"No subtitle entries found in {srt}")

    if video_size:
        style = replace(style, play_res_x=video_size[0], play_res_y=video_size[1])

    ass_lines: List[str] = ["[Script Info]", "ScriptType: v4.00+", "WrapStyle: 0", "ScaledBorderAndShadow: yes"]
    ass_lines.append("YCbCr Matrix: TV.709")
    ass_lines.append(f"PlayResX: {style.play_res_x}")
    ass_lines.append(f"PlayResY: {style.play_res_y}")
    ass_lines.append("")
    ass_lines.append("[V4+ Styles]")
    ass_lines.append(
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding"
    )
    style_line = (
        f"Style: Default,{style.font_name},{style.font_size},{style.primary_colour},{style.secondary_colour},"
        f"{style.outline_colour},{style.back_colour},0,0,0,0,100,100,0,0,1,{style.outline},{style.shadow},"
        f"{style.alignment},{style.margin_l},{style.margin_r},{style.margin_v},1"
    )
    ass_lines.append(style_line)
    ass_lines.append("")
    ass_lines.append("[Events]")
    ass_lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

    for block in blocks:
        start_cs = _parse_timestamp_to_cs(block.start)
        end_cs = _parse_timestamp_to_cs(block.end)
        dialogue = _format_event_text(block.lines, style)
        ass_lines.append(
            f"Dialogue: 0,{_format_ass_time(start_cs)},{_format_ass_time(end_cs)},Default,,0,0,0,,{dialogue}"
        )

    ass.write_text("\n".join(ass_lines) + "\n", encoding="utf-8")
    LOGGER.info("Wrote ASS subtitles to %s", ass.name)


def _video_size(video: Path) -> Optional[Tuple[int, int]]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        return None
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if width > 0 and height > 0:
        return width, height
    return None


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_emoji_font(preferred: Optional[str]) -> Tuple[Optional[str], Optional[Path]]:
    if preferred:
        apple_paths = [
            Path("/System/Library/Fonts/Apple Color Emoji.ttc"),
            Path("C:/Windows/Fonts/AppleColorEmoji.ttf"),
        ]
        for candidate in apple_paths:
            if candidate.exists():
                LOGGER.debug("Using Apple emoji font at %s", candidate)
                return preferred, None
    noto_path = _project_root() / "fonts" / "NotoColorEmoji.ttf"
    if noto_path.exists():
        LOGGER.info("Using bundled Noto Color Emoji font")
        return "Noto Color Emoji", noto_path
    if not preferred:
        LOGGER.warning("No dedicated emoji font found; falling back to Segoe UI Emoji")
        return "Segoe UI Emoji", None
    LOGGER.warning("Preferred emoji font '%s' not found; using it anyway", preferred)
    return preferred, None


def burn_ass(video: Path, ass: Path, *, overwrite: bool = True) -> Path:
    project_root = _project_root()
    target_dir = video.parent
    base_stem = video.stem
    if base_stem.endswith("_crop916"):
        base_stem = base_stem[: -len("_crop916")]
    output = target_dir / f"{base_stem}_subtitled{video.suffix}"
    if output.exists() and not overwrite:
        LOGGER.info("Skipping burn for %s (output exists)", output.name)
        return output

    try:
        ass_rel = ass.relative_to(project_root).as_posix()
    except ValueError as exc:  # pylint: disable=broad-except
        raise RuntimeError("ASS file must be inside the project directory") from exc

    def _escape_filter_value(value: str) -> str:
        escaped = []
        for ch in value:
            if ch in " ':,[]\\":
                escaped.append(f"\\{ch}")
            else:
                escaped.append(ch)
        return "".join(escaped)

    fonts_dir = project_root / "fonts"
    filter_expr = f"subtitles={_escape_filter_value(ass_rel)}"
    if fonts_dir.exists():
        fonts_rel = fonts_dir.relative_to(project_root).as_posix()
        filter_expr = f"{filter_expr}:fontsdir={_escape_filter_value(fonts_rel)}"

    cmd = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-i",
        str(video),
        "-vf",
        filter_expr,
        "-c:a",
        "copy",
        str(output),
    ]

    LOGGER.info("Burning subtitles into %s", output.name)
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as exc:  # pylint: disable=broad-except
        cmd_str = " ".join(cmd)
        LOGGER.error("FFmpeg command failed: %s", cmd_str)
        raise RuntimeError("FFmpeg subtitle burn failed") from exc

    return output


def process_video(
    video: Path,
    *,
    model: str = DEFAULT_MODEL,
    style: Optional[StyleConfig] = None,
    enable_emoji: bool = True,
    overwrite: bool = True,
) -> Optional[ProcessResult]:
    video = video.resolve()
    if style is None:
        style = StyleConfig()

    srt_path = whisper_srt(video, model=model, force=overwrite)
    emoji_srt = inject_emojis(srt_path, enable=enable_emoji)
    ass_path = emoji_srt.with_suffix(".ass")
    video_size = _video_size(video)
    emoji_font, _font_file = _resolve_emoji_font(style.emoji_font)
    style = replace(style, emoji_font=emoji_font)
    srt_to_ass(emoji_srt, ass_path, style, video_size=video_size)
    output_video = burn_ass(video, ass_path, overwrite=overwrite)
    return ProcessResult(video, output_video, emoji_srt, ass_path)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate subtitles and burn them into videos")
    parser.add_argument("video", type=Path, help="Target video file")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Whisper model to use")
    parser.add_argument("--font-name", default="Arial")
    parser.add_argument("--font-size", type=int, default=26)
    parser.add_argument("--margin-v", type=int, default=120)
    parser.add_argument("--outline", type=float, default=2.0)
    parser.add_argument("--shadow", type=float, default=0.0)
    parser.add_argument("--alignment", type=int, default=2)
    parser.add_argument("--no-emoji", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    _setup_logging(args.verbose)
    style = StyleConfig(
        font_name=args.font_name,
        font_size=args.font_size,
        margin_v=args.margin_v,
        outline=args.outline,
        shadow=args.shadow,
        alignment=args.alignment,
    )
    try:
        process_video(
            args.video,
            model=args.model,
            style=style,
            enable_emoji=not args.no_emoji,
            overwrite=args.overwrite,
        )
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.error("Error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())