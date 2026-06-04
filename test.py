"""Manual API test — the only default on-disk output is test_output/ here.

The web UI streams files to your browser (OS Downloads folder), not project downloads/.
The server does not write to downloads/ unless YTDOWNLOAD_DEV_OUTPUT_DIR is set.

Usage:
  python test.py
  python test.py "https://youtube.com/watch?v=..." mp3
  python test.py --no-save "https://..."   # call API only, do not write files
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "http://127.0.0.1:5000"
DEFAULT_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
FORMATS = ("mp3", "mp4")
OUT_DIR = Path(__file__).resolve().parent / "test_output"


def _filename_from_disposition(header: str | None) -> str:
    if not header:
        return "download.bin"
    if m := re.search(r"filename\*=UTF-8''([^;\s]+)", header, re.I):
        return m.group(1)
    if m := re.search(r'filename="([^"]+)"', header):
        return m.group(1)
    return "download.bin"


def convert(youtube_url: str, fmt: str, *, save: bool, out_dir: Path) -> bool:
    body = json.dumps({"url": youtube_url, "format": fmt}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/api/convert",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            if "application/json" in content_type:
                print(f"[{fmt}] {resp.status} {json.loads(data.decode())}")
                return False

            if not save:
                filename = _filename_from_disposition(
                    resp.headers.get("Content-Disposition")
                )
                print(f"[{fmt}] {resp.status} ok ({len(data)} bytes, {filename})")
                return True

            out_dir.mkdir(parents=True, exist_ok=True)
            filename = _filename_from_disposition(
                resp.headers.get("Content-Disposition")
            )
            out_path = out_dir / filename
            out_path.write_bytes(data)
            print(f"[{fmt}] {resp.status} saved {out_path}")
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
    parser = argparse.ArgumentParser(description="Test POST /api/convert")
    parser.add_argument("url", nargs="?", default=DEFAULT_URL, help="YouTube URL")
    parser.add_argument(
        "format",
        nargs="?",
        choices=FORMATS,
        help="mp3 or mp4 (omit to run both)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Call API only; do not write files to test_output/",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=OUT_DIR,
        help=f"Where to save files when testing (default: {OUT_DIR.name}/)",
    )
    args = parser.parse_args()

    formats = [args.format] if args.format else list(FORMATS)
    failed = []

    for fmt in formats:
        print(f"\n--- {fmt.upper()} ---")
        if not convert(args.url, fmt, save=not args.no_save, out_dir=args.output_dir):
            failed.append(fmt)

    if failed:
        print(f"\nFailed: {', '.join(failed)}")
        sys.exit(1)

    print(f"\nAll passed ({', '.join(formats)})")


if __name__ == "__main__":
    main()