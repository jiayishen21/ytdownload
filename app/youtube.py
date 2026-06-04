import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yt_dlp

DOWNLOADS_DIR = Path(__file__).resolve().parent.parent / "downloads"
Format = Literal["mp3", "mp4"]
VALID_FORMATS: frozenset[str] = frozenset({"mp3", "mp4"})


class ConversionError(Exception):
    pass


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _sanitize_filename(title: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*]', "", title)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized[:200] or "untitled"


def _find_ffmpeg_dir() -> str | None:
    on_path = shutil.which("ffmpeg")
    if on_path:
        return str(Path(on_path).parent)

    search_roots = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
        Path(os.environ.get("ProgramFiles", "")),
        Path(os.environ.get("ProgramFiles(x86)", "")),
        Path("C:/ffmpeg"),
    ]

    for root in search_roots:
        if not root or not root.exists():
            continue
        try:
            for ffmpeg in root.rglob("ffmpeg.exe"):
                return str(ffmpeg.parent)
        except OSError:
            continue

    return None


def _ydl_opts(ffmpeg_dir: str, tmpdir: str, fmt: Format) -> dict[str, Any]:
    outtmpl = os.path.join(tmpdir, "%(id)s.%(ext)s")
    opts: dict[str, Any] = {
        "outtmpl": outtmpl,
        "ffmpeg_location": ffmpeg_dir,
        "quiet": True,
        "no_warnings": True,
    }

    if fmt == "mp3":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        opts["format"] = "bestvideo+bestaudio/best"
        opts["merge_output_format"] = "mp4"

    return opts


def _find_output_file(tmpdir: str, video_id: str, ext: str) -> str | None:
    direct = os.path.join(tmpdir, f"{video_id}.{ext}")
    if os.path.isfile(direct):
        return direct

    for name in os.listdir(tmpdir):
        if name.startswith(video_id) and name.endswith(f".{ext}"):
            return os.path.join(tmpdir, name)

    return None


def convert_url(url: str, fmt: str = "mp3") -> dict[str, Any]:
    """Download from a YouTube URL and save as MP3 or MP4 under downloads/."""
    format_type = fmt.lower()
    if format_type not in VALID_FORMATS:
        raise ConversionError(f"format must be one of: {', '.join(sorted(VALID_FORMATS))}")

    ffmpeg_dir = _find_ffmpeg_dir()
    if not ffmpeg_dir:
        raise ConversionError(
            "ffmpeg not found. Install it (winget install Gyan.FFmpeg), "
            "then restart your terminal so PATH updates."
        )

    downloaded_at = datetime.now()
    timestamp = downloaded_at.strftime("%Y%m%d_%H%M%S")

    with tempfile.TemporaryDirectory() as tmpdir:
        opts = _ydl_opts(ffmpeg_dir, tmpdir, format_type)  # type: ignore[arg-type]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
        except Exception as exc:
            raise ConversionError(_strip_ansi(str(exc))) from exc

        if not info:
            raise ConversionError("Could not fetch video info")

        video_id = info.get("id", "unknown")
        title = info.get("title", "")

        temp_file = _find_output_file(tmpdir, video_id, format_type)
        if not temp_file:
            raise ConversionError(
                f"{format_type.upper()} file was not created. ffmpeg dir: {ffmpeg_dir}"
            )

        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{_sanitize_filename(title)}-{timestamp}.{format_type}"
        dest_path = DOWNLOADS_DIR / filename

        if dest_path.exists():
            filename = (
                f"{_sanitize_filename(title)}-{timestamp}-{video_id}.{format_type}"
            )
            dest_path = DOWNLOADS_DIR / filename

        shutil.move(temp_file, dest_path)

        return {
            "video_id": video_id,
            "title": title,
            "format": format_type,
            "filename": filename,
            "path": str(dest_path),
            "downloaded_at": downloaded_at.isoformat(),
        }


def convert_url_to_mp3(url: str) -> dict[str, Any]:
    return convert_url(url, "mp3")