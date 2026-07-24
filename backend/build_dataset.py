from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import statistics
import subprocess
import sys
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
SEED_PATH = DATA_DIR / "seed_urls.csv"
OUTPUT_PATH = DATA_DIR / "training_urls.csv"
MANIFEST_PATH = DATA_DIR / "training_urls.manifest.json"
RULE_SCORER_PATH = PROJECT_DIR / "scripts" / "score_dataset.js"

SOURCES = {
    "phishtank": {
        "url": "https://data.phishtank.com/data/online-valid.csv",
        "cache": CACHE_DIR / "phishtank-online-valid.csv",
    },
    "openphish": {
        "url": "https://openphish.com/feed.txt",
        "cache": CACHE_DIR / "openphish-feed.txt",
    },
    "tranco": {
        "url": "https://tranco-list.eu/top-1m.csv.zip",
        "cache": CACHE_DIR / "tranco-top-1m.csv.zip",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a balanced, reproducible phishing/legitimate URL dataset."
    )
    parser.add_argument("--phishing-limit", type=int, default=5_000)
    parser.add_argument("--legitimate-limit", type=int, default=5_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--refresh", action="store_true", help="Re-download cached feeds.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use cache only and fail if a required feed is missing.",
    )
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    return parser.parse_args()


def download(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "phis-radar-ai-research/1.0 (academic dataset builder)",
            "Accept": "*/*",
        },
    )
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    with urllib.request.urlopen(request, timeout=90) as response:
        temporary.write_bytes(response.read())
    temporary.replace(destination)


def ensure_sources(refresh: bool, offline: bool) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for name, source in SOURCES.items():
        cache_path = source["cache"]
        if cache_path.exists() and not refresh:
            continue
        if offline:
            raise FileNotFoundError(f"Missing cached {name} feed: {cache_path}")
        print(f"Downloading {name}: {source['url']}")
        download(str(source["url"]), cache_path)


def normalized_url(raw_url: str) -> str | None:
    value = (raw_url or "").strip()
    if not value or len(value) > 4_096:
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return None
    try:
        port = f":{parsed.port}" if parsed.port else ""
    except ValueError:
        return None
    hostname = parsed.hostname.rstrip(".").lower()
    if not hostname or hostname == "localhost":
        return None
    userinfo = ""
    if parsed.username:
        userinfo = parsed.username
        if parsed.password:
            userinfo += f":{parsed.password}"
        userinfo += "@"
    netloc = f"{userinfo}{hostname}{port}"
    return urlunsplit(
        (parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, "")
    )


def hostname_group(url: str) -> str:
    return (urlsplit(url).hostname or "").rstrip(".").lower()


def load_seed_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with SEED_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        for raw in csv.DictReader(file):
            url = normalized_url(raw.get("url", ""))
            if url is None:
                continue
            label = int(raw.get("label", ""))
            if label not in {0, 1}:
                continue
            rows.append({"url": url, "label": label, "source": "seed"})
    return rows


def load_phishtank_rows() -> list[dict[str, object]]:
    path = SOURCES["phishtank"]["cache"]
    rows: list[dict[str, object]] = []
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as file:
        for raw in csv.DictReader(file):
            url = normalized_url(raw.get("url", ""))
            if url:
                rows.append({"url": url, "label": 1, "source": "phishtank"})
    return rows


def load_openphish_rows() -> list[dict[str, object]]:
    path = SOURCES["openphish"]["cache"]
    rows: list[dict[str, object]] = []
    for raw_url in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        url = normalized_url(raw_url)
        if url:
            rows.append({"url": url, "label": 1, "source": "openphish"})
    return rows


def load_tranco_rows() -> list[dict[str, object]]:
    path = SOURCES["tranco"]["cache"]
    rows: list[dict[str, object]] = []
    with zipfile.ZipFile(path) as archive:
        csv_name = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
        with archive.open(csv_name) as binary:
            text = io.TextIOWrapper(binary, encoding="utf-8-sig", errors="replace")
            for values in csv.reader(text):
                if len(values) < 2:
                    continue
                url = normalized_url(f"https://{values[1].strip()}/")
                if url:
                    rows.append({"url": url, "label": 0, "source": "tranco"})
    return rows


def unique_by_url(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        key = str(row["url"]).casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(row)
    return output


def choose_rows(
    seed_rows: list[dict[str, object]],
    feed_rows: list[dict[str, object]],
    limit: int,
    rng: random.Random,
) -> list[dict[str, object]]:
    selected = unique_by_url(seed_rows)
    selected_urls = {str(row["url"]).casefold() for row in selected}
    candidates = [
        row for row in unique_by_url(feed_rows) if str(row["url"]).casefold() not in selected_urls
    ]
    rng.shuffle(candidates)
    selected.extend(candidates[: max(0, limit - len(selected))])
    if len(selected) < limit:
        raise ValueError(f"Requested {limit:,} rows, but only {len(selected):,} are available.")
    return selected[:limit]


def calculate_rule_scores(urls: list[str], profile: str = "web") -> list[int]:
    if profile not in {"web", "extension"}:
        raise ValueError(f"Unknown RuleScore profile: {profile}")
    command = ["node", str(RULE_SCORER_PATH)]
    if profile == "extension":
        command.append("--extension")
    process = subprocess.run(
        command,
        input=json.dumps(urls, ensure_ascii=False),
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(f"RuleScore bridge failed: {process.stderr.strip()}")
    scores = json.loads(process.stdout)
    if len(scores) != len(urls):
        raise RuntimeError("RuleScore bridge returned a different number of rows.")
    return [int(score) for score in scores]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_DIR))
    except ValueError:
        return str(path.resolve())


def build_dataset(args: argparse.Namespace) -> None:
    if args.phishing_limit < 2 or args.legitimate_limit < 2:
        raise ValueError("Each class needs at least two URLs.")

    ensure_sources(args.refresh, args.offline)
    rng = random.Random(args.seed)
    seed_rows = load_seed_rows()
    phishing_seed = [row for row in seed_rows if row["label"] == 1]
    legitimate_seed = [row for row in seed_rows if row["label"] == 0]

    openphish = load_openphish_rows()
    phishtank = load_phishtank_rows()
    rng.shuffle(openphish)
    rng.shuffle(phishtank)
    phishing = choose_rows(
        phishing_seed,
        openphish + phishtank,
        args.phishing_limit,
        rng,
    )

    phishing_hosts = {hostname_group(str(row["url"])) for row in phishing}
    tranco = [
        row for row in load_tranco_rows() if hostname_group(str(row["url"])) not in phishing_hosts
    ]
    legitimate = choose_rows(
        [row for row in legitimate_seed if hostname_group(str(row["url"])) not in phishing_hosts],
        tranco,
        args.legitimate_limit,
        rng,
    )

    rows = phishing + legitimate
    rng.shuffle(rows)
    urls = [str(row["url"]) for row in rows]
    print(f"Calculating RuleScore for {len(urls):,} URLs with web-app/analyzer.js")
    scores = calculate_rule_scores(urls)
    for row, score in zip(rows, scores, strict=True):
        row["rule_score"] = score
        row["group"] = hostname_group(str(row["url"]))

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["url", "label", "source", "rule_score", "group"],
        )
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(output)

    label_counts = Counter(str(row["label"]) for row in rows)
    source_counts = Counter(str(row["source"]) for row in rows)
    score_by_label = {
        str(label): [int(row["rule_score"]) for row in rows if row["label"] == label]
        for label in (0, 1)
    }
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "output": project_relative(output),
        "random_seed": args.seed,
        "row_count": len(rows),
        "unique_url_count": len({url.casefold() for url in urls}),
        "unique_hostname_count": len({str(row["group"]) for row in rows}),
        "labels": dict(sorted(label_counts.items())),
        "sources": dict(sorted(source_counts.items())),
        "rule_score": {
            label: {
                "mean": round(statistics.fmean(values), 4),
                "median": statistics.median(values),
                "min": min(values),
                "max": max(values),
            }
            for label, values in score_by_label.items()
        },
        "rule_score_engine": {
            "training_profile": "web-app/analyzer.js (URL-only analysis)",
            "web_analyzer_sha256": sha256(PROJECT_DIR / "web-app" / "analyzer.js"),
            "extension_analyzer_sha256": sha256(PROJECT_DIR / "analyzer.js"),
        },
        "feed_files": {
            name: {
                "url": source["url"],
                "path": project_relative(source["cache"]),
                "sha256": sha256(source["cache"]),
            }
            for name, source in SOURCES.items()
        },
        "label_definition": {"0": "legitimate", "1": "phishing"},
        "safety_note": "URLs were parsed as strings only; the builder never visits submitted URLs.",
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        build_dataset(parse_args())
    except Exception as error:
        print(f"Dataset build failed: {error}", file=sys.stderr)
        raise
