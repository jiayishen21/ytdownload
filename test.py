"""Call POST /api/convert. Start the server first: python run.py"""

import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:5000"
DEFAULT_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
FORMATS = ("mp3", "mp4")


def convert(youtube_url: str, fmt: str) -> bool:
    body = json.dumps({"url": youtube_url, "format": fmt}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/convert",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read().decode())
            print(f"[{fmt}] {resp.status} {data}")
            return True
    except urllib.error.HTTPError as exc:
        data = json.loads(exc.read().decode())
        print(f"[{fmt}] {exc.code} {data}")
        return False
    except urllib.error.URLError as exc:
        print(f"Could not reach server at {BASE_URL}: {exc.reason}")
        print("Is the Flask app running? (python run.py)")
        return False


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_URL

    if len(sys.argv) > 2:
        formats = [sys.argv[2].lower()]
    else:
        formats = list(FORMATS)

    failed = []
    for fmt in formats:
        print(f"\n--- {fmt.upper()} ---")
        if not convert(url, fmt):
            failed.append(fmt)

    if failed:
        print(f"\nFailed: {', '.join(failed)}")
        sys.exit(1)

    print(f"\nAll passed ({', '.join(formats)})")


if __name__ == "__main__":
    main()