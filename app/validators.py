import re
from urllib.parse import parse_qs, urlparse

# Standard YouTube video IDs are 11 characters.
_VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")

_PATH_PREFIXES = ("/shorts/", "/embed/", "/v/", "/live/")


class InvalidYouTubeURLError(ValueError):
    """Raised when a URL is not a supported YouTube video link."""


def _host_is_youtube(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower().split(":")[0]
    if host == "youtu.be":
        return True
    return host == "youtube.com" or host.endswith(".youtube.com")


def _video_id_from_parsed(parsed) -> str | None:
    host = (parsed.hostname or "").lower()

    if host == "youtu.be" or host.endswith(".youtu.be"):
        slug = parsed.path.strip("/").split("/")[0]
        return slug or None

    if parsed.path in ("", "/"):
        return None

    if parsed.path.startswith("/watch"):
        query = parse_qs(parsed.query)
        values = query.get("v")
        return values[0] if values else None

    for prefix in _PATH_PREFIXES:
        if parsed.path.startswith(prefix):
            return parsed.path[len(prefix) :].split("/")[0] or None

    return None


def validate_youtube_url(url: str) -> str:
    """
    Validate and return a stripped YouTube video URL.
    Raises InvalidYouTubeURLError if the URL is not a YouTube video link.
    """
    cleaned = url.strip()
    if not cleaned:
        raise InvalidYouTubeURLError("URL is empty")

    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise InvalidYouTubeURLError("URL must start with http:// or https://")

    if not _host_is_youtube(parsed.hostname):
        raise InvalidYouTubeURLError(
            "URL must be a YouTube link (youtube.com or youtu.be)"
        )

    video_id = _video_id_from_parsed(parsed)
    if not video_id or not _VIDEO_ID_RE.match(video_id):
        raise InvalidYouTubeURLError(
            "URL must point to a single YouTube video (e.g. youtube.com/watch?v=... or youtu.be/...)"
        )

    return cleaned
