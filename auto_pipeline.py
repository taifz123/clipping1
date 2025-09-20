"""Automatic watcher for the clipping pipeline."""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import tools.batch_subtitle as batch_subtitle
import tools.dynamic_crop as dynamic_crop

CLIPS_DIR = PROJECT_ROOT / "static" / "clips"
_OUTPUT_SUFFIXES = ("_crop916.mp4", "_subtitled.mp4", "_crop916_subtitled.mp4")


def _iter_pending_videos() -> Iterable[Path]:
    for candidate in CLIPS_DIR.glob("*.mp4"):
        name = candidate.name
        if any(name.endswith(suffix) for suffix in _OUTPUT_SUFFIXES):
            continue
        yield candidate


def pending_exists() -> bool:
    """Return ``True`` when there are unprocessed ``.mp4`` inputs."""
    return any(_iter_pending_videos())


def run_once() -> None:
    """Execute the crop and subtitle steps sequentially."""
    dynamic_crop.main()
    batch_subtitle.main()


def main(poll_interval: float = 5.0) -> None:
    if not CLIPS_DIR.exists():
        raise FileNotFoundError(f"Clips folder not found: {CLIPS_DIR}")

    print(f"[auto] Watching for new videos in {CLIPS_DIR}", flush=True)
    while True:
        try:
            if pending_exists():
                print("[auto] New video detected → running crop + subtitles...", flush=True)
                run_once()
                print("[auto] Processing complete. Waiting for next upload…", flush=True)
        except Exception as exc:  # pragma: no cover - defensive: keep watcher alive
            print(f"[auto][error] {exc}", flush=True)
        time.sleep(poll_interval)


if __name__ == "__main__":
    main()