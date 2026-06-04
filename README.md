# ytdownload

A small Flask API that downloads YouTube videos as **MP3** or **MP4** files. Downloads are saved locally under `downloads/` with predictable filenames.

## Requirements

- **Python 3.10+** (recommended)
- **FFmpeg** — required for audio extraction (MP3) and merging video + audio (MP4)
  - Install on Windows: `winget install Gyan.FFmpeg`
  - After installing, restart your terminal so `ffmpeg` is on your PATH (the app also tries to find WinGet installs automatically)

## Setup

```powershell
cd ytdownload
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run the server

```powershell
python run.py
```

The API listens at **http://127.0.0.1:5000** with debug mode enabled.

Alternatively:

```powershell
flask run
```

(Uses `.flaskenv` — `FLASK_APP=run:app`, `FLASK_DEBUG=1`.)

## API

### `POST /api/convert`

Download and convert a YouTube video.

**JSON body:**

| Field    | Required | Default | Description            |
| -------- | -------- | ------- | ---------------------- |
| `url`    | Yes      | —       | Full YouTube watch URL |
| `format` | No       | `mp3`   | `mp3` or `mp4`         |

**Example request:**

```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "format": "mp4"
}
```

Form fields (`url`, `format`) are also accepted if you are not sending JSON.

**Success response (200):**

```json
{
  "ok": true,
  "video_id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up ...",
  "format": "mp4",
  "filename": "Rick Astley - Never Gonna Give You Up ...-20260604_020457.mp4",
  "path": "C:\\Users\\...\\ytdownload\\downloads\\..."
}
```

**Error responses:**

| Status | When                                             |
| ------ | ------------------------------------------------ |
| `400`  | Missing `url`, or invalid `format`               |
| `500`  | Download/conversion failed (see `error` message) |

## Output files

Saved under **`downloads/`** (created automatically). This folder is gitignored.

**Filename pattern:**

```
{sanitized-title}-{timestamp}.{mp3|mp4}
```

- **Title** — video title with characters unsafe on Windows removed (`<>:"/\|?*`)
- **Timestamp** — when the download **started**, formatted as `YYYYMMDD_HHMMSS` (local time)

If a file with the same name already exists, the video ID is appended:

```
{title}-{timestamp}-{video_id}.mp3
```

## Quality, resolution, and frame rate

**Everything is automatic.** The API does not accept resolution, FPS, or codec options today.

Choices are made by [yt-dlp](https://github.com/yt-dlp/yt-dlp) using the format strings in `app/youtube.py`:

### MP3 (`format: "mp3"`)

| Setting          | Value                      | Effect                                                      |
| ---------------- | -------------------------- | ----------------------------------------------------------- |
| Stream selection | `bestaudio/best`           | Highest-quality audio YouTube offers for that video         |
| Post-process     | `FFmpegExtractAudio` → MP3 | Converts to MP3                                             |
| Audio bitrate    | `preferredquality: "192"`  | **192 kbps** MP3 (the only quality value we pin explicitly) |

No video is downloaded for MP3.

### MP4 (`format: "mp4"`)

| Setting          | Value                        | Effect                                             |
| ---------------- | ---------------------------- | -------------------------------------------------- |
| Stream selection | `bestvideo+bestaudio/best`   | Best separate video and audio streams, then merged |
| Container        | `merge_output_format: "mp4"` | Output file is MP4                                 |

**Resolution and frame rate** come from whatever YouTube exposes as the “best” video stream — often 1080p or 4K when available. We do **not** cap resolution (e.g. 720p), force 30 FPS, or pick a specific codec (H.264, VP9, AV1, etc.). File size and download time can be large for high-resolution uploads.

To change this behavior in the future, the `format` string in yt-dlp would need to be updated (for example `bestvideo[height<=720]+bestaudio/best` for a 720p cap).

## Testing

With the server running, in another terminal:

```powershell
python test.py
```

By default this converts the same URL as **both** MP3 and MP4.

```powershell
# Custom URL
python test.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Single format only
python test.py "https://www.youtube.com/watch?v=VIDEO_ID" mp4
```

Each format is tried in sequence; the script exits with code `1` if any request fails. Requests use a 10-minute timeout because downloads can take a while, especially MP4.

## Project layout

```
ytdownload/
├── app/
│   ├── __init__.py    # Flask app factory
│   ├── routes.py      # /api/convert
│   └── youtube.py     # yt-dlp download logic
├── downloads/         # Saved files (gitignored)
├── run.py             # Dev server entry point
├── test.py            # Manual API test script
├── requirements.txt
└── .flaskenv
```

## Things to know

- **FFmpeg is mandatory** for both formats. Without it you will get errors about post-processing or missing output files.
- **MP4 is slower and larger** than MP3 because it downloads and merges full video.
- **First request after server start** may feel slow while yt-dlp/FFmpeg warm up.
- **Only YouTube URLs** are intended; other sites depend on yt-dlp support and are untested here.
- **Legal / ToS** — only download content you have the right to. This tool is for personal use; respect YouTube’s terms and copyright.
- **No auth or rate limiting** — the API is a local dev server, not hardened for public exposure.

## Dependencies

- **Flask** — HTTP API
- **yt-dlp** — YouTube metadata and downloads
- **FFmpeg** (system) — audio extraction and video/audio merge
