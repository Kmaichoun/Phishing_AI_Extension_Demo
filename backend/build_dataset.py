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
from urllib.parse import quote_plus, urlsplit, urlunsplit

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = BASE_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
SEED_PATH = DATA_DIR / "seed_urls.csv"
LEGITIMATE_DEEP_LINKS_PATH = DATA_DIR / "legitimate_deep_links.csv"
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
    parser.add_argument(
        "--legitimate-deep-link-ratio",
        type=float,
        default=0.65,
        help="Target fraction of legitimate URLs that contain a non-root path.",
    )
    parser.add_argument(
        "--legitimate-query-ratio",
        type=float,
        default=0.18,
        help="Target fraction of legitimate URLs that contain a query string.",
    )
    parser.add_argument(
        "--legitimate-long-query-ratio",
        type=float,
        default=0.05,
        help=(
            "Target fraction of legitimate URLs with long/encoded query strings; "
            "these hard negatives reduce false positives on search and tracking URLs."
        ),
    )
    parser.add_argument(
        "--legitimate-subdomain-ratio",
        type=float,
        default=0.65,
        help="Target fraction of legitimate URLs with a non-www subdomain label.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--refresh", action="store_true", help="Re-download cached feeds.")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use cache only and fail if a required feed is missing.",
    )
    parser.add_argument(
        "--reuse-existing",
        action="store_true",
        help=(
            "Rebuild from the existing output CSV instead of source-feed caches; "
            "useful after caches have been intentionally cleaned."
        ),
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


def load_legitimate_deep_links() -> list[dict[str, object]]:
    """Load audited hard negatives representing ordinary, non-root web pages."""
    rows: list[dict[str, object]] = []
    if not LEGITIMATE_DEEP_LINKS_PATH.exists():
        return rows
    with LEGITIMATE_DEEP_LINKS_PATH.open(
        "r", encoding="utf-8-sig", newline=""
    ) as file:
        for raw in csv.DictReader(file):
            url = normalized_url(raw.get("url", ""))
            if url is None:
                continue
            rows.append(
                {
                    "url": url,
                    "label": 0,
                    "source": (raw.get("source") or "curated_deep_link").strip(),
                }
            )
    return rows


def load_existing_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.exists():
        raise FileNotFoundError(f"Existing dataset not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        for raw in csv.DictReader(file):
            url = normalized_url(raw.get("url", ""))
            label_text = (raw.get("label") or "").strip()
            if url is None or label_text not in {"0", "1"}:
                continue
            rows.append(
                {
                    "url": url,
                    "label": int(label_text),
                    "source": (raw.get("source") or "existing").strip(),
                }
            )
    return rows


BENIGN_PATH_TEMPLATES = (
    "/watch",
    "/search",
    "/docs/getting-started",
    "/products/overview",
    "/news/technology/article-2026",
    "/blog/security/research-update",
    "/support/help-center/topic-1042",
    "/wiki/Internet_security",
    "/projects/open-source/repository",
    "/en-us/learn/tutorials/introduction",
    "/community/discussions/4821",
    "/account/settings/profile",
)

BENIGN_QUERY_TEMPLATES = (
    "v=AwKnraP_Wno",
    "q=security+research",
    "page=2&sort=recent",
    "lang=en&utm_source=documentation",
    "id=12345",
    "ref=homepage",
)

BENIGN_LONG_QUERY_TERMS = (
    "เว็บไซต์สำหรับค้นหาข้อมูลภาษาไทย",
    "ข่าวความปลอดภัยไซเบอร์และงานวิจัย",
    "คู่มือการใช้งานระบบสำหรับผู้เริ่มต้น",
    "machine learning security research paper",
)

BENIGN_SUBDOMAIN_LABELS = (
    "docs",
    "support",
    "help",
    "developer",
    "news",
    "blog",
    "learn",
    "community",
    "status",
    "accounts",
)


def url_shape(url: str) -> tuple[bool, bool]:
    parsed = urlsplit(url)
    return bool(parsed.path and parsed.path != "/"), bool(parsed.query)


def benign_long_query(index: int) -> str:
    """Create deterministic legitimate search/tracking query hard negatives.

    Modern search pages legitimately contain percent-encoded international text,
    analytics identifiers and long opaque navigation state. The values are
    synthetic and are never requested over the network.
    """
    term = BENIGN_LONG_QUERY_TERMS[index % len(BENIGN_LONG_QUERY_TERMS)]
    repeated_term = " ".join([term] * (2 + index % 3))
    digest = hashlib.sha256(f"benign-query-{index}".encode("utf-8")).hexdigest()
    navigation_state = (digest + digest[::-1])[:96]
    return (
        f"q={quote_plus(repeated_term)}"
        f"&source=web&lang={'th' if index % 2 == 0 else 'en'}"
        f"&session={digest[:32]}&navigation={navigation_state}"
        f"&page={index % 9 + 1}&sort=recent"
    )


def augment_legitimate_shapes(
    rows: list[dict[str, object]],
    deep_link_ratio: float,
    query_ratio: float,
    long_query_ratio: float,
    subdomain_ratio: float,
    rng: random.Random,
) -> dict[str, int | float]:
    """Break the label shortcut where only phishing samples have paths/queries.

    Tranco supplies domains rather than page URLs. We deterministically turn a
    subset of those roots into benign-shaped deep links without visiting them.
    Hostname grouping keeps all variants of a site in the same CV partition.
    """
    target_deep_links = round(len(rows) * deep_link_ratio)
    target_queries = round(len(rows) * query_ratio)
    target_subdomains = round(len(rows) * subdomain_ratio)
    current_deep_links = sum(url_shape(str(row["url"]))[0] for row in rows)
    current_queries = sum(url_shape(str(row["url"]))[1] for row in rows)

    root_candidates = [
        row for row in rows if url_shape(str(row["url"])) == (False, False)
    ]
    rng.shuffle(root_candidates)
    required_deep_links = max(0, target_deep_links - current_deep_links)
    selected = root_candidates[:required_deep_links]

    required_queries = max(0, target_queries - current_queries)
    query_rows = set(id(row) for row in selected[:required_queries])
    for index, row in enumerate(selected):
        parsed = urlsplit(str(row["url"]))
        path = BENIGN_PATH_TEMPLATES[index % len(BENIGN_PATH_TEMPLATES)]
        query = (
            BENIGN_QUERY_TEMPLATES[index % len(BENIGN_QUERY_TEMPLATES)]
            if id(row) in query_rows
            else ""
        )
        row["url"] = urlunsplit((parsed.scheme, parsed.netloc, path, query, ""))
        row["source"] = f"{row['source']}_deep_link"

    def has_long_query(row: dict[str, object]) -> bool:
        query = urlsplit(str(row["url"])).query
        return len(query) >= 160 or query.count("%") >= 12

    target_long_queries = round(len(rows) * long_query_ratio)
    current_long_queries = sum(has_long_query(row) for row in rows)
    required_long_queries = max(0, target_long_queries - current_long_queries)
    long_query_candidates = [
        row
        for row in rows
        if url_shape(str(row["url"]))[1] and not has_long_query(row)
    ]
    rng.shuffle(long_query_candidates)
    for index, row in enumerate(long_query_candidates[:required_long_queries]):
        parsed = urlsplit(str(row["url"]))
        row["url"] = urlunsplit(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                benign_long_query(index),
                "",
            )
        )
        row["source"] = f"{row['source']}_long_query"

    def has_feature_subdomain(row: dict[str, object]) -> bool:
        hostname = (urlsplit(str(row["url"])).hostname or "").removeprefix("www.")
        return len([part for part in hostname.split(".") if part]) > 2

    current_subdomains = sum(has_feature_subdomain(row) for row in rows)
    required_subdomains = max(0, target_subdomains - current_subdomains)
    subdomain_candidates = [row for row in rows if not has_feature_subdomain(row)]
    rng.shuffle(subdomain_candidates)
    for index, row in enumerate(subdomain_candidates[:required_subdomains]):
        parsed = urlsplit(str(row["url"]))
        hostname = (parsed.hostname or "").removeprefix("www.")
        if not hostname or len(hostname.split(".")) < 2:
            continue
        hostname = f"{BENIGN_SUBDOMAIN_LABELS[index % len(BENIGN_SUBDOMAIN_LABELS)]}.{hostname}"
        port = f":{parsed.port}" if parsed.port else ""
        row["url"] = urlunsplit(
            (parsed.scheme, f"{hostname}{port}", parsed.path, parsed.query, "")
        )
        row["source"] = f"{row['source']}_subdomain"

    final_deep_links = sum(url_shape(str(row["url"]))[0] for row in rows)
    final_queries = sum(url_shape(str(row["url"]))[1] for row in rows)
    final_long_queries = sum(has_long_query(row) for row in rows)
    final_subdomains = sum(has_feature_subdomain(row) for row in rows)
    return {
        "target_deep_link_ratio": deep_link_ratio,
        "target_query_ratio": query_ratio,
        "target_long_query_ratio": long_query_ratio,
        "target_subdomain_ratio": subdomain_ratio,
        "deep_link_count": final_deep_links,
        "query_count": final_queries,
        "long_query_count": final_long_queries,
        "subdomain_count": final_subdomains,
        "deep_link_ratio": round(final_deep_links / len(rows), 6),
        "query_ratio": round(final_queries / len(rows), 6),
        "long_query_ratio": round(final_long_queries / len(rows), 6),
        "subdomain_ratio": round(final_subdomains / len(rows), 6),
    }


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
    if not (
        0
        <= args.legitimate_long_query_ratio
        <= args.legitimate_query_ratio
        <= args.legitimate_deep_link_ratio
        <= 1
        and 0 <= args.legitimate_subdomain_ratio <= 1
    ):
        raise ValueError(
            "Legitimate URL ratios must satisfy "
            "0 <= long-query <= query <= deep-link <= 1."
        )

    rng = random.Random(args.seed)
    legitimate_deep_links = load_legitimate_deep_links()

    if args.reuse_existing:
        existing_rows = load_existing_rows(args.output.resolve())
        phishing = choose_rows(
            [],
            [row for row in existing_rows if row["label"] == 1],
            args.phishing_limit,
            rng,
        )
        legitimate_feed = [row for row in existing_rows if row["label"] == 0]
    else:
        ensure_sources(args.refresh, args.offline)
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
        legitimate_feed = legitimate_seed + load_tranco_rows()

    phishing_hosts = {hostname_group(str(row["url"])) for row in phishing}
    legitimate_feed = [
        row
        for row in legitimate_feed
        if hostname_group(str(row["url"])) not in phishing_hosts
    ]
    legitimate = choose_rows(
        [
            row
            for row in legitimate_deep_links
            if hostname_group(str(row["url"])) not in phishing_hosts
        ],
        legitimate_feed,
        args.legitimate_limit,
        rng,
    )
    legitimate_shape_summary = augment_legitimate_shapes(
        legitimate,
        args.legitimate_deep_link_ratio,
        args.legitimate_query_ratio,
        args.legitimate_long_query_ratio,
        args.legitimate_subdomain_ratio,
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
        "legitimate_url_shapes": legitimate_shape_summary,
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
            "extension_analyzer_sha256": sha256(
                PROJECT_DIR / "extension" / "analyzer.js"
            ),
        },
        "build_mode": "reuse_existing" if args.reuse_existing else "source_feeds",
        "feed_files": (
            {}
            if args.reuse_existing
            else {
                name: {
                    "url": source["url"],
                    "path": project_relative(source["cache"]),
                    "sha256": sha256(source["cache"]),
                }
                for name, source in SOURCES.items()
            }
        ),
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
