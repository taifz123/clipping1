# AI Clip Creator

A Windows-first toolchain that crops horizontal videos into 9:16 portrait clips, generates subtitles with emoji triggers, and burns them into TikTok-ready exports. It includes a Flask dashboard, batch CLI, and a watchdog-powered automation pipeline.

## Features

- Dynamic face/upper-body tracking with OpenCV and Haar cascades to keep subjects centered in portrait crops.
- Automatic Whisper transcription (`tiny`, `small`, or `medium` models) with keyword → emoji triggers appended to the last subtitle line.
- Subtitle styling via ASS with configurable fonts, outline, margins, and alignment. White text, black outline, and no background box by default.
- Reliable FFmpeg burns using relative Unix-style subtitle paths to avoid Windows filter parsing issues.
- Flask web interface for uploads, configuration, and downloading processed clips.
- CLI batch runner and watchdog-based auto pipeline that responds to new `.mp4` files in `static/clips`.
- Optional archiving of originals into `static/archive_originals/` after processing.

## Project layout

```
ai-clip-creator/
  app_env/                # virtual environment (created by install script)
  fonts/                  # drop custom fonts here (e.g., NotoColorEmoji.ttf)
  models/                 # optional model cache (not populated automatically)
  static/
    clips/                # inputs and outputs
    archive_originals/    # originals moved here after archiving
    style.css             # web UI styling
  templates/
    index.html            # Flask template
  tools/
    dynamic_crop.py       # 9:16 cropper
    subtitle_pipeline.py  # Whisper + emoji + ASS + burn
    auto_pipeline.py      # watchdog loop
  app.py                  # Flask app
  batch_subtitle.py       # CLI batch processor
  run-all.bat             # crop -> subtitle -> archive -> web
  run-web.bat             # start web only
  run-auto.bat            # watcher + web dashboards
  install-windows.bat     # create/refresh the venv
  README.md
```

## Prerequisites

- Windows 11 with Python 3.12 (64-bit) installed.
- [FFmpeg](https://ffmpeg.org/) available on your `PATH`.
- Internet connection for the first Whisper model download.
- (Optional) [Noto Color Emoji](https://fonts.google.com/noto/specimen/Noto+Color+Emoji) font file in `fonts/` for colorful emoji on systems without Apple Color Emoji.

## Quick start (Windows)

1. Open **Command Prompt** in the project root.
2. Run `install-windows.bat` to create the `app_env` virtual environment and install dependencies (`openai-whisper`, `opencv-python`, `numpy`, `flask`, `watchdog`, `tqdm`).
3. Place input `.mp4` files into `static/clips/`.
4. Choose your workflow:
   - `run-all.bat` – crops, generates subtitles (archiving originals), then launches the Flask web app.
   - `run-web.bat` – starts only the Flask dashboard.
   - `run-auto.bat` – launches the auto watcher and the web dashboard in separate windows.

## Manual commands

Activate the environment manually:

```bat
call app_env\Scripts\activate.bat
```

Then use these scripts from the repository root:

### Dynamic cropper

```bat
python tools\dynamic_crop.py
```

- Crops each landscape `.mp4` in `static/clips/` to `*_crop916.mp4` using face/upper-body tracking.

### Subtitle pipeline

```bat
python batch_subtitle.py [--model small] [--no-emoji] [--font-name Arial] [--font-size 28]
```

- Prefers `*_crop916.mp4` files; falls back to the originals.
- Produces `*_subtitled.mp4` with ASS-burned captions.
- Add `--archive` to move originals to `static/archive_originals/` after successful runs.

### Auto pipeline watcher

```bat
python tools\auto_pipeline.py
```

- Watches `static/clips/` for new `.mp4` files.
- Runs crop → subtitle → burn automatically, then archives the original source video.
- Options:
  - `--no-emoji` – disable emoji injection.
  - `--font-name`, `--font-size`, `--margin-v`, `--outline`, `--shadow`, `--alignment` – adjust ASS styling.
  - `--model tiny|small|medium` – choose Whisper model.
  - `--no-archive` – keep original files in place.
  - `--no-initial` – skip processing files that already exist at startup.

### Flask web app

```bat
python app.py
```

- Visit [http://127.0.0.1:5000](http://127.0.0.1:5000) to upload videos, choose options, and download results.

## Emoji triggers

Keywords are checked against the last line of each subtitle block (case-insensitive). When triggered, one emoji is appended to the final line. The default mapping is:

| Keywords (regex)                        | Emoji |
|----------------------------------------|-------|
| `thanks`, `thank you`                  | 🙏    |
| `yes`, `yeah`, `yep`                   | ✅    |
| `no`, `nah`, `nope`                    | ❌    |
| `money`, `million`, `invoice`, `paid`  | 💰    |
| `idea`, `think`, `brainstorm`          | 💡    |
| `wow`, `amazing`, `incredible`         | 🤯    |
| `joke`, `funny`, `laugh`               | 😂    |
| `win`, `success`, `victory`            | 🏆    |
| `100`                                  | 💯    |

To customize the mapping, edit `EMOJI_TRIGGERS` in `tools/subtitle_pipeline.py`.

## Styling tips

- Default ASS style uses white text, black outline (Outline=2), zero drop shadow, bottom-center alignment (2), and `MarginV=120`.
- Pass different style values through the CLI, auto watcher, or the web UI form.
- For emoji rendering:
  - macOS systems can use `Apple Color Emoji` automatically.
  - On Windows, copy `NotoColorEmoji.ttf` into `fonts/`. The pipeline adds `fonts/` as `fontsdir` so FFmpeg can load the font without installation.

## Troubleshooting

- **FFmpeg errors about subtitle filters** – ensure the project is launched from the repository root so relative paths resolve correctly. Absolute `C:\` paths are intentionally avoided.
- **Whisper model download slow** – run the desired model once to cache it under the user directory. You can symlink or copy models into the optional `models/` directory if you prefer custom paths.
- **Emoji not colorful** – confirm that `fonts/NotoColorEmoji.ttf` exists or install a color emoji font available to libass. The console logs show which font was selected.
- **Permission errors when moving files** – close any applications using the videos before running `--archive` or the auto watcher. Windows may lock files that are open in other apps.

## License

This project is provided as-is. Review any bundled or third-party license requirements (OpenAI Whisper, OpenCV, FFmpeg) before distributing compiled outputs.