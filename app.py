"""Flask web interface for the AI Clip Creator."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from flask import Flask, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from tools import dynamic_crop, subtitle_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent
CLIPS_DIR = PROJECT_ROOT / "static" / "clips"
CLIPS_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(CLIPS_DIR)
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # 1GB
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

LOGGER = logging.getLogger(__name__)


@dataclass
class ClipDisplay:
    base_name: str
    original: Optional[str]
    cropped: Optional[str]
    subtitled: Optional[str]

    @property
    def original_url(self) -> Optional[str]:
        if not self.original:
            return None
        return url_for("static", filename=f"clips/{self.original}")

    @property
    def cropped_url(self) -> Optional[str]:
        if not self.cropped:
            return None
        return url_for("static", filename=f"clips/{self.cropped}")

    @property
    def subtitled_url(self) -> Optional[str]:
        if not self.subtitled:
            return None
        return url_for("static", filename=f"clips/{self.subtitled}")


def _unique_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def _collect_results() -> List[ClipDisplay]:
    results: List[ClipDisplay] = []
    for subtitled in sorted(CLIPS_DIR.glob("*_subtitled.mp4")):
        base = subtitled.stem[: -len("_subtitled")]
        original = CLIPS_DIR / f"{base}.mp4"
        cropped = CLIPS_DIR / f"{base}_crop916.mp4"
        results.append(
            ClipDisplay(
                base_name=base,
                original=original.name if original.exists() else None,
                cropped=cropped.name if cropped.exists() else None,
                subtitled=subtitled.name,
            )
        )
    return results


def _parse_float(value: str, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@app.route("/", methods=["GET", "POST"])
def index():
    processed: List[ClipDisplay] = []
    if request.method == "POST":
        uploads = request.files.getlist("videos")
        if not uploads or all(not file.filename for file in uploads):
            flash("Please upload at least one MP4 video.", "error")
            return redirect(request.url)

        model = request.form.get("model", subtitle_pipeline.DEFAULT_MODEL)
        font_name = request.form.get("font_name", "Arial")
        font_size = _parse_int(request.form.get("font_size", "26"), 26)
        margin_v = _parse_int(request.form.get("margin_v", "120"), 120)
        outline = _parse_float(request.form.get("outline", "2"), 2.0)
        shadow = _parse_float(request.form.get("shadow", "0"), 0.0)
        alignment = _parse_int(request.form.get("alignment", "2"), 2)
        emoji_enabled = request.form.get("emoji", "on") == "on"

        for upload in uploads:
            if not upload or not upload.filename:
                continue
            filename = secure_filename(upload.filename)
            if not filename.lower().endswith(".mp4"):
                flash(f"Skipped unsupported file: {upload.filename}", "warning")
                continue
            destination = _unique_path(CLIPS_DIR, filename)
            upload.save(destination)
            LOGGER.info("Saved upload to %s", destination)

            crop_result = None
            try:
                crop_result = dynamic_crop.process_video(destination, overwrite=True)
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.error("Cropping failed for %s: %s", destination.name, exc)
                flash(f"Cropping failed for {destination.name}: {exc}", "error")

            target_video = crop_result.output if crop_result else destination
            style = subtitle_pipeline.StyleConfig(
                font_name=font_name,
                font_size=font_size,
                margin_v=margin_v,
                outline=outline,
                shadow=shadow,
                alignment=alignment,
            )

            try:
                result = subtitle_pipeline.process_video(
                    target_video,
                    model=model,
                    style=style,
                    enable_emoji=emoji_enabled,
                    overwrite=True,
                )
                processed.append(
                    ClipDisplay(
                        base_name=target_video.stem.replace("_crop916", ""),
                        original=destination.name,
                        cropped=crop_result.output.name if crop_result else None,
                        subtitled=result.output_video.name,
                    )
                )
            except Exception as exc:  # pylint: disable=broad-except
                LOGGER.error("Subtitle pipeline failed for %s: %s", target_video.name, exc)
                flash(f"Subtitle pipeline failed for {target_video.name}: {exc}", "error")

        if processed:
            flash("Processing complete!", "success")

    existing = _collect_results()
    return render_template(
        "index.html",
        processed=processed,
        existing=existing,
        default_model=subtitle_pipeline.DEFAULT_MODEL,
    )


def create_app() -> Flask:
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    app.run(debug=False)