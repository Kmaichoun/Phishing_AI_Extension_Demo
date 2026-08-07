from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_PATH = DATA_DIR / "legitimate_deep_links.csv"
MANIFEST_PATH = DATA_DIR / "legitimate_deep_links.manifest.json"
COLLINFO_URL = "https://index.commoncrawl.org/collinfo.json"
USER_AGENT = "phish-radar-ai-academic-dataset/1.1 (Kasetsart University project)"

IGNORED_EXTENSIONS = {
    ".7z", ".apk", ".avi", ".bin", ".css", ".csv", ".dmg", ".doc",
    ".docx", ".exe", ".gif", ".gz", ".ico", ".iso", ".jar", ".jpeg",
    ".jpg", ".js", ".json", ".m4a", ".mkv", ".mov", ".mp3", ".mp4",
    ".msi", ".pdf", ".png", ".ppt", ".pptx", ".rar", ".rss", ".svg",
    ".tar", ".tgz", ".tif", ".tiff", ".tsv", ".txt", ".wav", ".webm",
    ".webp", ".woff", ".woff2", ".xls", ".xlsx", ".xml", ".zip",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect real legitimate deep-link URL metadata from Common Crawl "
            "for the already curated trusted hosts. No destination page is visited."
        )
    )
    parser.add_argument("--per-domain", type=int, default=40)
    parser.add_argument("--max-total", type=int, default=1_500)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def request_json(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def latest_index() -> str:
    collections = request_json(COLLINFO_URL)
    if not isinstance(collections, list) or not collections:
        raise RuntimeError("Common Crawl did not return an index collection list.")
    index_id = str(collections[0].get("id") or "")
    if not index_id:
        raise RuntimeError("Latest Common Crawl collection has no id.")
    return index_id


def normalized_deep_link(raw_url: str, trusted_hostname: str) -> str | None:
    try:
        parsed = urlsplit(raw_url.strip())
    except ValueError:
        return None
    hostname = (parsed.hostname or "").rstrip(".").lower()
    if parsed.scheme.lower() not in {"http", "https"} or hostname != trusted_hostname:
        return None
    path = parsed.path or "/"
    if path == "/" or len(raw_url) > 1_000:
        return None
    lower_path = path.casefold()
    if any(lower_path.endswith(extension) for extension in IGNORED_EXTENSIONS):
        return None
    try:
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError:
        return None
    return urlunsplit(("https", f"{hostname}{port}", path, parsed.query, ""))


def load_existing(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Curated trusted-host file not found: {path}")
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for raw in csv.DictReader(file):
            url = (raw.get("url") or "").strip()
            if not url or url.casefold() in seen:
                continue
            seen.add(url.casefold())
            output.append(
                {
                    "url": url,
                    "source": (raw.get("source") or "curated_deep_link").strip(),
                }
            )
    return output


def query_domain(index_id: str, hostname: str, limit: int) -> list[str]:
    parameters = urllib.parse.urlencode(
        [
            ("url", f"{hostname}/*"),
            ("output", "json"),
            ("filter", "status:200"),
            ("filter", "mime:text/html"),
            ("collapse", "urlkey"),
            ("limit", str(limit)),
        ]
    )
    url = f"https://index.commoncrawl.org/{index_id}-index?{parameters}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        lines = response.read().decode("utf-8", errors="replace").splitlines()
    output: list[str] = []
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        candidate = normalized_deep_link(str(record.get("url") or ""), hostname)
        if candidate:
            output.append(candidate)
    return output


def collect(args: argparse.Namespace) -> None:
    if args.per_domain < 1 or args.max_total < 1 or args.delay < 0.5:
        raise ValueError("Use positive limits and a polite delay of at least 0.5 seconds.")

    output_path = args.output.resolve()
    existing = load_existing(output_path)
    curated = [row for row in existing if row["source"] == "curated_deep_link"]
    hostnames = sorted(
        {
            (urlsplit(row["url"]).hostname or "").rstrip(".").lower()
            for row in curated
            if urlsplit(row["url"]).hostname
        }
    )
    index_id = latest_index()
    collected: list[dict[str, str]] = []
    seen = {row["url"].casefold() for row in curated}
    failures: list[dict[str, str]] = []

    for position, hostname in enumerate(hostnames, start=1):
        if len(collected) >= args.max_total:
            break
        try:
            urls = query_domain(index_id, hostname, args.per_domain)
        except (OSError, urllib.error.HTTPError) as error:
            failures.append({"hostname": hostname, "error": str(error)})
            urls = []
        for url in urls:
            key = url.casefold()
            if key in seen:
                continue
            seen.add(key)
            collected.append(
                {"url": url, "source": "common_crawl_trusted_domain"}
            )
            if len(collected) >= args.max_total:
                break
        print(
            f"[{position}/{len(hostnames)}] {hostname}: "
            f"accepted={len(urls)} total={len(collected)}"
        )
        if position < len(hostnames):
            time.sleep(args.delay)

    rows = curated + collected
    temporary = output_path.with_suffix(output_path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["url", "source"])
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output_path)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "common_crawl_index": index_id,
        "query_mode": "one sequential CDX query per curated trusted hostname",
        "destination_pages_visited": False,
        "curated_count": len(curated),
        "common_crawl_count": len(collected),
        "row_count": len(rows),
        "host_count": len(hostnames),
        "per_domain_limit": args.per_domain,
        "delay_seconds": args.delay,
        "failures": failures,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    collect(parse_args())
