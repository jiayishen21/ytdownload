# ytdownload

Containerized web service that converts YouTube videos to **MP3** or **MP4** and streams the result to the client. The image bundles the app, **yt-dlp**, and **FFmpeg** — the host only needs Docker.

Converted files are sent as browser downloads. Nothing is persisted on the server after each request.

## Quick start

```bash
git clone <repo-url>
cd ytdownload
docker compose up --build -d
```

Open **http://localhost:5000/** — paste a YouTube URL, choose MP3 or MP4, click **Download**.

```bash
# Logs
docker compose logs -f

# Stop
docker compose down
```

Rebuild after code changes:

```bash
docker compose up --build -d
```

### Run without Compose

```bash
docker build -t ytdownload .
docker run --rm -p 5000:5000 ytdownload
```

## Web UI

Served at `/` on port **5000**. Submits `POST /api/convert` and triggers a file download when conversion completes. MP4 jobs can take several minutes; the UI stays in a loading state until the response returns.

## API

### `POST /api/convert`

| Field    | Required | Default | Description              |
| -------- | -------- | ------- | ------------------------ |
| `url`    | Yes      | —       | YouTube video URL        |
| `format` | No       | `mp3`   | `mp3` or `mp4`           |

**Example:**

```bash
curl -X POST http://localhost:5000/api/convert \
  -H "Content-Type: application/json" \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","format":"mp3"}' \
  -o output.mp3
```

Form fields (`url`, `format`) work as an alternative to JSON.

**Success (200):** binary attachment (`audio/mpeg` or `video/mp4`).

**Errors (JSON):**

| Status | When                                                |
| ------ | --------------------------------------------------- |
| `400`  | Missing `url`, invalid `format`, or non-YouTube URL |
| `500`  | Download or conversion failed                     |

### Supported YouTube URLs

- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/shorts/VIDEO_ID`
- `/embed/`, `/v/`, `/live/` paths

Playlist query params (`?list=...`) are stripped — only the single video is converted.

Invalid URLs (localhost, random strings, the site homepage, etc.) are rejected with **400** before yt-dlp runs.

### Attachment filename

```
{sanitized-title}-{timestamp}.{mp3|mp4}
```

`timestamp` is `YYYYMMDD_HHMMSS` when conversion started (container local time).

## Quality and codecs

No resolution or bitrate options on the API — behavior is defined in `app/youtube.py` via [yt-dlp](https://github.com/yt-dlp/yt-dlp).

| Format | Behavior |
| ------ | -------- |
| **MP3** | Best audio → 192 kbps MP3 |
| **MP4** | Best video + audio, merged to MP4 with **H.264 + AAC** for broad player support |

MP4 is slower and larger than MP3. Playlist links only download one video.

## Container image

| Layer | Contents |
| ----- | -------- |
| Base | `python:3.12-slim-bookworm` |
| System | `ffmpeg` (via `apt`) |
| App | Flask, yt-dlp, gunicorn (`requirements.txt`) |
| Process | `gunicorn` on `0.0.0.0:5000`, 600s worker timeout, 1 worker |

```dockerfile
# Dockerfile summary
apt install ffmpeg
pip install -r requirements.txt
CMD gunicorn --bind 0.0.0.0:5000 --timeout 600 run:app
```

Temp files live in the container filesystem during a request and are removed after the response is sent.

Optional dev-only env (not for production):

```yaml
environment:
  - YTDOWNLOAD_DEV_OUTPUT_DIR=/app/test_output
```

## Deployment

1. Install Docker on the server.
2. Clone the repo and run `docker compose up -d --build`.
3. Put **nginx**, **Caddy**, or similar in front for HTTPS if exposed publicly.
4. Plan for CPU, memory, disk, and outbound bandwidth — large MP4s are heavy.

The service has **no authentication or rate limiting**. Do not expose it to the open internet without protecting it yourself.

### YouTube and abuse detection

YouTube does not offer a supported “download API” for this use case. Heavy or automated traffic from a server IP can trigger blocks, captchas, or “sign in to confirm you’re not a bot” errors. Personal/low-volume use is more reliable than a public multi-user deployment.

Only download content you have the right to use. Respect YouTube’s terms and copyright.

## Smoke testing

With the stack running, from the repo root on any machine with Python 3:

```bash
python test.py
```

Writes responses to `test_output/` by default. Options:

```bash
python test.py "https://www.youtube.com/watch?v=VIDEO_ID" mp4
python test.py --no-save "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Project layout

```
ytdownload/
├── app/
│   ├── __init__.py
│   ├── routes.py
│   ├── validators.py   # YouTube URL checks
│   ├── youtube.py      # yt-dlp + FFmpeg
│   └── templates/
│       └── index.html
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── run.py              # used as gunicorn entry (run:app)
└── test.py             # optional host-side API test
```

## License and use

For personal or authorized use. Operators are responsible for compliance with YouTube’s terms and applicable law.
