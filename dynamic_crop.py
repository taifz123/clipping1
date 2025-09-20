"""Utilities for dynamically cropping landscape clips to 9:16."""
from __future__ import annotations

import argparse
import logging
import sys
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import cv2
import numpy as np
from tqdm import tqdm

LOGGER = logging.getLogger(__name__)

TARGET_ASPECT = 9 / 16
SMOOTH_WINDOW = 10
DEFAULT_MIN_CONFIDENCE = 1.1


@dataclass
class CropResult:
    """Information about a processed clip."""

    source: Path
    output: Path
    frame_count: int


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(message)s",
    )


def _ensure_even(value: int) -> int:
    return value if value % 2 == 0 else value + 1


def _load_cascade(name: str) -> cv2.CascadeClassifier:
    cascade_path = Path(cv2.data.haarcascades) / name
    classifier = cv2.CascadeClassifier(str(cascade_path))
    if classifier.empty():
        raise RuntimeError(f"Failed to load cascade '{name}' from {cascade_path}")
    return classifier


def _detect_regions(
    frame_gray: np.ndarray,
    face_cascade: cv2.CascadeClassifier,
    upper_body_cascade: cv2.CascadeClassifier,
) -> List[Tuple[int, int, int, int]]:
    faces = face_cascade.detectMultiScale(frame_gray, DEFAULT_MIN_CONFIDENCE, 5)
    if len(faces) > 0:
        return list(faces)
    uppers = upper_body_cascade.detectMultiScale(frame_gray, DEFAULT_MIN_CONFIDENCE, 5)
    return list(uppers)


def _pick_largest(regions: Iterable[Tuple[int, int, int, int]]) -> Optional[Tuple[int, int, int, int]]:
    best_region: Optional[Tuple[int, int, int, int]] = None
    best_area = 0
    for region in regions:
        x, y, w, h = region
        area = w * h
        if area > best_area:
            best_area = area
            best_region = region
    return best_region


def should_skip(width: int, height: int, *, tolerance: float = 0.05) -> bool:
    if width <= 0 or height <= 0:
        return True
    aspect = width / height
    return aspect <= TARGET_ASPECT * (1 + tolerance)


def process_video(
    video_path: Path,
    *,
    overwrite: bool = False,
    smooth_window: int = SMOOTH_WINDOW,
    target_aspect: float = TARGET_ASPECT,
) -> Optional[CropResult]:
    video_path = video_path.resolve()
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    output_path = video_path.with_name(f"{video_path.stem}_crop916{video_path.suffix}")
    if output_path.exists() and not overwrite:
        LOGGER.info("Skipping %s (crop already exists)", video_path.name)
        return CropResult(video_path, output_path, 0)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open {video_path}")

    writer: Optional[cv2.VideoWriter] = None

    try:
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        if should_skip(width, height):
            LOGGER.info("Video %s is already portrait-friendly; skipping crop", video_path.name)
            return None

        target_width = _ensure_even(int(round(height * target_aspect)))
        target_width = max(2, min(target_width, width))

        face_cascade = _load_cascade("haarcascade_frontalface_default.xml")
        upper_body_cascade = _load_cascade("haarcascade_upperbody.xml")

        fourcc_codes = ("avc1", "H264", "mp4v")
        for code in fourcc_codes:
            fourcc = cv2.VideoWriter_fourcc(*code)
            candidate = cv2.VideoWriter(str(output_path), fourcc, fps, (target_width, height))
            if candidate.isOpened():
                writer = candidate
                LOGGER.debug("Using %s codec for %s", code, output_path.name)
                break
            candidate.release()
        if writer is None or not writer.isOpened():
            raise RuntimeError("Could not open video writer for output")

        centers = deque(maxlen=max(1, smooth_window))
        default_center = width // 2
        centers.append(default_center)

        processed = 0
        progress = tqdm(total=frame_count or None, unit="frame", desc=video_path.name)
        last_valid_region: Optional[Tuple[int, int, int, int]] = None

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)

            regions = _detect_regions(gray, face_cascade, upper_body_cascade)
            region = _pick_largest(regions) or last_valid_region
            if region is not None:
                last_valid_region = region
                x, y, w, h = region
                centers.append(x + w // 2)
            else:
                centers.append(centers[-1] if centers else default_center)

            smoothed_center = int(round(sum(centers) / len(centers)))
            half_width = target_width // 2
            left = max(0, min(smoothed_center - half_width, width - target_width))
            right = left + target_width
            cropped = frame[:, left:right]

            if cropped.shape[1] < target_width:
                pad_total = target_width - cropped.shape[1]
                pad_left = pad_total // 2
                pad_right = pad_total - pad_left
                cropped = cv2.copyMakeBorder(
                    cropped,
                    0,
                    0,
                    pad_left,
                    pad_right,
                    cv2.BORDER_CONSTANT,
                    value=(0, 0, 0),
                )

            writer.write(cropped)
            processed += 1
            progress.update(1)

        progress.close()
        LOGGER.info("Created %s", output_path.relative_to(video_path.parent))
        return CropResult(video_path, output_path, processed)
    finally:
        cap.release()
        if writer is not None:
            writer.release()


def crop_directory(input_dir: Path, *, overwrite: bool = False) -> List[CropResult]:
    input_dir = input_dir.resolve()
    if not input_dir.exists():
        raise FileNotFoundError(input_dir)

    results: List[CropResult] = []
    videos = sorted(p for p in input_dir.glob("*.mp4") if not p.stem.endswith("_crop916"))
    if not videos:
        LOGGER.info("No .mp4 files found in %s", input_dir)
        return results

    for video in videos:
        try:
            result = process_video(video, overwrite=overwrite)
            if result is not None:
                results.append(result)
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.error("Failed to crop %s: %s", video.name, exc)
    return results


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dynamically crop videos to 9:16")
    parser.add_argument(
        "--clips-dir",
        type=Path,
        default=Path("static/clips"),
        help="Directory containing source videos",
    )
    parser.add_argument("--overwrite", action="store_true", help="Recreate existing crops")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    _setup_logging(args.verbose)
    try:
        crop_directory(args.clips_dir, overwrite=args.overwrite)
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.error("Error: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())