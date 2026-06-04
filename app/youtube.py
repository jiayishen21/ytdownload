import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import yt_dlp

from app.validators import validate_youtube_url

Format = Literal["mp3", "mp4"]
VALID_FORMATS: frozenset[str] = frozenset({"mp3", "mp4"})
FORMAT_MIMETYPES: dict[str, str] = {
    "mp3": "audio/mpeg",
    "mp4": "video/mp4",
}


class ConversionError(Exception):
    pass


def _dev_output_dir() -> Path | None:
    """Optional dev-only directory (e.g. test_output). Set YTDOWNLOAD_DEV_OUTPUT_DIR."""
    raw = os.environ.get("YTDOWNLOAD_DEV_OUTPUT_DIR", "").strip()
    if not raw:
        return None
    return Path(raw).resolve()


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def _sanitize_filename(title: str) -> str:
    sanitized = re.sub(r'[<>:"/\\|?*]', "", title)
    sanitized = re.sub(r"\s+", " ", sanitized).strip()
    return sanitized[:200] or "untitled"


def _normalize_url(url: str) -> str:
    """Use a single video URL; drop playlist/radio query params."""
    url = url.strip()
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return url

    query = parse_qs(parsed.query, keep_blank_values=True)
    query.pop("list", None)
    query.pop("index", None)
    query.pop("start_radio", None)

    flat_query = urlencode({key: values[0] for key, values in query.items()})
    return urlunparse(parsed._replace(query=flat_query))


def _ffmpeg_binary_name() -> str:
    return "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"


def _find_ffmpeg_dir() -> str | None:
    """Locate the directory containing ffmpeg (PATH, FFMPEG_LOCATION, or Windows fallbacks)."""
    env_location = os.environ.get("FFMPEG_LOCATION")
    if env_location:
        path = Path(env_location)
        if path.is_dir() and (path / _ffmpeg_binary_name()).exists():
            return str(path)
        if path.is_file():
            return str(path.parent)

    on_path = shutil.which("ffmpeg")
    if on_path:
        return str(Path(on_path).parent)

    if sys.platform == "win32":
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
        "noplaylist": True,
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
        # Prefer H.264 + AAC in an MP4 container (plays in Windows Media Player, etc.).
        # Plain bestvideo+bestaudio often muxes Opus audio, which many players reject.
        opts["format"] = (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo+bestaudio/best"
        )
        opts["merge_output_format"] = "mp4"
        opts["format_sort"] = ["vcodec:h264", "res", "fps", "acodec:aac"]
        opts["postprocessors"] = [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ]
        opts["postprocessor_args"] = {
            "VideoConvertor": ["-c:v", "copy", "-c:a", "aac", "-movflags", "+faststart"],
        }

    return opts


def _find_output_file(tmpdir: str, video_id: str, ext: str) -> str | None:
    direct = os.path.join(tmpdir, f"{video_id}.{ext}")
    if os.path.isfile(direct):
        return direct

    for name in os.listdir(tmpdir):
        if name.startswith(video_id) and name.endswith(f".{ext}"):
            return os.path.join(tmpdir, name)

    return None


def _video_info(info: dict[str, Any] | None) -> dict[str, Any]:
    if not info:
        raise ConversionError("Could not fetch video info")
    if info.get("_type") == "playlist" and info.get("entries"):
        first = info["entries"][0]
        if isinstance(first, dict):
            return first
    return info


def convert_url(url: str, fmt: str = "mp3") -> dict[str, Any]:
    """Download from a YouTube URL; return temp file metadata for browser download."""
    format_type = fmt.lower()
    if format_type not in VALID_FORMATS:
        raise ConversionError(f"format must be one of: {', '.join(sorted(VALID_FORMATS))}")

    ffmpeg_dir = _find_ffmpeg_dir()
    if not ffmpeg_dir:
        raise ConversionError(
            "ffmpeg not found. Install ffmpeg and ensure it is on PATH, "
            "or set FFMPEG_LOCATION to the directory containing the ffmpeg binary."
        )

    clean_url = _normalize_url(validate_youtube_url(url))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tmpdir = tempfile.mkdtemp()

    try:
        opts = _ydl_opts(ffmpeg_dir, tmpdir, format_type)  # type: ignore[arg-type]

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                raw_info = ydl.extract_info(clean_url, download=True)
        except Exception as exc:
            raise ConversionError(_strip_ansi(str(exc))) from exc

        info = _video_info(raw_info)
        video_id = info.get("id", "unknown")
        title = info.get("title", "")

        temp_file = _find_output_file(tmpdir, video_id, format_type)
        if not temp_file:
            raise ConversionError(
                f"{format_type.upper()} file was not created. ffmpeg dir: {ffmpeg_dir}"
            )

        filename = f"{_sanitize_filename(title)}-{timestamp}.{format_type}"
        final_path = os.path.join(tmpdir, filename)
        if os.path.exists(final_path):
            filename = (
                f"{_sanitize_filename(title)}-{timestamp}-{video_id}.{format_type}"
            )
            final_path = os.path.join(tmpdir, filename)

        shutil.move(temp_file, final_path)

        dev_dir = _dev_output_dir()
        if dev_dir:
            dev_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(final_path, dev_dir / filename)

        return {
            "video_id": video_id,
            "title": title,
            "format": format_type,
            "filename": filename,
            "path": final_path,
            "mimetype": FORMAT_MIMETYPES[format_type],
            "tmpdir": tmpdir,
        }
    except Exception:
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise


def convert_url_to_mp3(url: str) -> dict[str, Any]:
    return convert_url(url, "mp3")