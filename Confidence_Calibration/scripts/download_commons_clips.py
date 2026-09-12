from __future__ import annotations

import argparse
import csv
import hashlib
import json
import urllib.parse
import urllib.request
from pathlib import Path


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "Textile Defect Detection benchmark downloader/1.0"


def commons_original_url(title: str) -> str:
    params = {
        "action": "query",
        "titles": title,
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    url = f"{COMMONS_API}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    pages = payload["query"]["pages"]
    page = next(iter(pages.values()))
    if "imageinfo" not in page:
        raise RuntimeError(f"No downloadable file URL found for {title}")
    return page["imageinfo"][0]["url"]


def commons_direct_url(title: str) -> str:
    filename = title.removeprefix("File:").replace(" ", "_")
    digest = hashlib.md5(filename.encode("utf-8")).hexdigest()
    quoted = urllib.parse.quote(filename, safe="()_-.")
    return f"https://upload.wikimedia.org/wikipedia/commons/{digest[0]}/{digest[:2]}/{quoted}"


def download(url: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=120) as response, output.open("wb") as f:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download public Wikimedia Commons benchmark clips.")
    parser.add_argument("--manifest", default="Confidence_Calibration/benchmark/clip_manifest.csv")
    parser.add_argument("--output-dir", default="Confidence_Calibration/benchmark/media")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--use-api", action="store_true", help="Resolve original file URLs through the Commons API.")
    args = parser.parse_args()

    with Path(args.manifest).open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if args.limit is not None:
        rows = rows[: args.limit]

    output_dir = Path(args.output_dir)
    for row in rows:
        title = row["commons_title"]
        output = output_dir / row["clip"]
        if output.exists():
            print(f"exists: {output}")
            continue
        url = commons_original_url(title) if args.use_api else commons_direct_url(title)
        print(f"downloading: {title} -> {output}")
        download(url, output)


if __name__ == "__main__":
    main()
