#!/usr/bin/env python3
"""Prepare a small, URL-free, domain-disjoint RF/MLP teaching dataset.

Uses only the Python standard library. It reads the private development CSV,
verifies the recorded feature-source snapshot, and exports numeric features.
No model is imported, unpickled, trained, promoted, or changed. No URL is fetched.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib
import io
import json
import math
import random
import sys
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


SEED = 20261023
SCHEMA = "url-v8-domain-enriched"
EXPECTED_DATA_SHA256 = "c02bb2adf07c71ddc391403f3d190fb9ab289d058f62ba3177318612428b0df0"
SOURCE_FILES = (
    "backend/feature_extractor.py",
    "backend/domain_parts.py",
    "backend/public_suffix_list.dat",
    "backend/reference_origin_features.py",
)
SPLITS = ("train", "validation", "test")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def counter_records(counts: Counter, names: tuple[str, ...]) -> list[dict]:
    return [dict(zip(names, key), rows=value) for key, value in sorted(counts.items())]


def allocation(counts: dict[tuple, int], total: int) -> dict[tuple, int]:
    """Proportional allocation with largest remainders, without oversampling."""
    population = sum(counts.values())
    if population < total:
        raise ValueError(f"Requested {total} samples from only {population} rows")
    exact = {key: value * total / population for key, value in counts.items()}
    out = {key: math.floor(value) for key, value in exact.items()}
    order = sorted(counts, key=lambda key: (-(exact[key] - out[key]), key))
    for key in order[: total - sum(out.values())]:
        out[key] += 1
    return out


def canonical_identity(raw_url: str) -> tuple[bytes, str]:
    """Conservative URL deduplication; keep path/query/scheme distinctions.

    Lowercase IDNA hostname, remove one www alias and trailing host dot,
    remove default port and fragment, canonicalize empty path to '/'. Keep
    username/password (only in the in-memory digest input), path and query.
    """
    value = raw_url.strip()
    if not value:
        raise ValueError("Empty URL")
    if "://" not in value:
        value = "https://" + value
    parsed = urlsplit(value)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Not an HTTP URL with a hostname")
    host = parsed.hostname.casefold().rstrip(".").removeprefix("www.")
    host = host.encode("idna").decode("ascii")
    if not host or any(char.isspace() or ord(char) < 33 for char in host):
        raise ValueError("Invalid hostname")
    port = parsed.port
    scheme = parsed.scheme.casefold()
    bracketed = "[" + host + "]" if ":" in host else host
    authority = bracketed
    if port is not None and (scheme, port) not in {("http", 80), ("https", 443)}:
        authority += ":" + str(port)
    if "@" in parsed.netloc:
        authority = parsed.netloc.rsplit("@", 1)[0] + "@" + authority
    canonical = urlunsplit((scheme, authority, parsed.path or "/", parsed.query, ""))
    return hashlib.sha256(canonical.encode("utf-8")).digest(), host


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=30000)
    parser.add_argument("--output", default="output/colab-rf-dl-20261023/data")
    parser.add_argument("--replace", action="store_true", help="Replace only this script's three named outputs")
    args = parser.parse_args()
    if args.rows < 100:
        raise ValueError("Use at least 100 rows for a two-class demonstration")
    started = time.perf_counter()
    root = Path(__file__).resolve().parents[1]
    source_root = root / ".ai-context/current-source"
    source_csv = root / "backend/data/simple_quality_rf_20261008/dataset.csv"
    output = (root / args.output).resolve()
    if not output.is_relative_to(root):
        raise ValueError("Output directory must be inside this project")
    output.mkdir(parents=True, exist_ok=True)
    output_names = ("features.csv.gz", "manifest.json", "demo_dataset.zip")
    if not args.replace and any((output / name).exists() for name in output_names):
        raise FileExistsError("An output exists; inspect it first, or explicitly pass --replace")

    manifest_path = root / "docs/ai/CURRENT_SOURCE_MANIFEST.json"
    snapshot = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_files = {item["path"]: item for item in snapshot["files"]}
    zip_path = root / snapshot["snapshot_zip"]["path"]
    if sha256_file(zip_path) != snapshot["snapshot_zip"]["sha256"]:
        raise ValueError("Source archive hash does not match the recorded snapshot")
    verified_files = {}
    for relative in SOURCE_FILES:
        digest = sha256_file(source_root / relative)
        if digest != expected_files[relative]["sha256"]:
            raise ValueError(f"Feature source hash mismatch: {relative}")
        verified_files[relative] = digest
    data_digest = sha256_file(source_csv)
    if data_digest != EXPECTED_DATA_SHA256:
        raise ValueError("Input data hash differs from the recorded dataset; review provenance first")

    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source_root / "backend"))
    extractor = importlib.import_module("feature_extractor")
    domain_module = importlib.import_module("domain_parts")
    feature_names = list(extractor.feature_names(SCHEMA))
    assert len(feature_names) == 172 and len(set(feature_names)) == 172
    assert not any(name.startswith("publisher_reference_") for name in feature_names)
    registered_domain = lru_cache(maxsize=200000)(domain_module.domain_parts)

    @lru_cache(maxsize=200000)
    def group_identity(host: str) -> bytes:
        registered = registered_domain(host)[0]
        if not registered:
            raise ValueError("Empty registered domain")
        return hashlib.sha256(f"phish-radar-demo-group:{SEED}:".encode() + registered.encode("ascii")).digest()

    counts = Counter()
    source_counts = Counter()
    excluded_sources = Counter()
    duplicate_sources = Counter()
    reference_label_masks = {}
    # Dedup across the entire eligible universe before sampling. Values are
    # [raw URL, binary-label mask, first source, group digest, occurrence count].
    unique = {}
    print("Scanning and deduplicating the development universe; URL values remain private.", flush=True)
    with source_csv.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            counts["input_rows"] += 1
            source = sys.intern(row["source"])
            source_counts[source] += 1
            if source.startswith("official_reference"):
                excluded_sources[source] += 1
                counts["excluded_targeted_reference_rows"] += 1
                # References are not eligible for export, but their labels
                # still participate in the global contradiction check.
                try:
                    reference_id, _ = canonical_identity(row["url"])
                    reference_label = int(row["label"])
                    if reference_label in {0, 1}:
                        reference_label_masks[reference_id] = reference_label_masks.get(reference_id, 0) | (1 << reference_label)
                except (ValueError, UnicodeError):
                    pass
                continue
            try:
                label = int(row["label"])
                if label not in {0, 1}:
                    raise ValueError("Nonbinary label")
            except (TypeError, ValueError):
                counts["excluded_invalid_label_rows"] += 1
                continue
            try:
                url_id, host = canonical_identity(row["url"])
                group_id = group_identity(host)
            except (ValueError, UnicodeError):
                counts["excluded_invalid_url_rows"] += 1
                continue
            if url_id in unique:
                entry = unique[url_id]
                entry[1] |= 1 << label
                entry[4] += 1
                duplicate_sources[source] += 1
            else:
                unique[url_id] = [row["url"], 1 << label, source, group_id, 1]
    strata = defaultdict(list)
    universe_counts = Counter()
    universe_groups = defaultdict(set)
    for url_id, entry in unique.items():
        raw_url, label_mask, source, group_id, occurrences = entry
        label_mask |= reference_label_masks.get(url_id, 0)
        if label_mask == 3:
            counts["conflicting_canonical_url_groups"] += 1
            counts["excluded_conflicting_label_rows"] += occurrences
            continue
        counts["removed_duplicate_rows"] += occurrences - 1
        label = 1 if label_mask == 2 else 0
        bucket = int.from_bytes(group_id[:8], "big") / 2**64
        split = "train" if bucket < 0.70 else ("validation" if bucket < 0.85 else "test")
        strata[(split, source, label)].append((url_id, raw_url, group_id))
        universe_counts[(split, source, label)] += 1
        universe_groups[split].add(group_id)
    counts["eligible_unique_rows"] = sum(universe_counts.values())
    assert sum(counts[key] for key in (
        "excluded_targeted_reference_rows", "excluded_invalid_label_rows",
        "excluded_invalid_url_rows", "excluded_conflicting_label_rows",
        "removed_duplicate_rows", "eligible_unique_rows")) == counts["input_rows"]
    del unique

    train_n = round(args.rows * 0.70)
    validation_n = round(args.rows * 0.15)
    targets = dict(zip(SPLITS, (train_n, validation_n, args.rows - train_n - validation_n)))
    selected = []
    selected_counts = Counter()
    selected_groups = defaultdict(set)
    for split in SPLITS:
        stratum_counts = {key: len(value) for key, value in strata.items() if key[0] == split}
        quotas = allocation(stratum_counts, targets[split])
        for key, quota in quotas.items():
            _, source, label = key
            random_seed = int.from_bytes(hashlib.sha256(f"{SEED}:{key}".encode()).digest(), "big")
            for url_id, raw_url, group_id in random.Random(random_seed).sample(strata[key], quota):
                selected.append((split, source, label, group_id, url_id, raw_url))
                selected_counts[key] += 1
                selected_groups[split].add(group_id)
    del strata
    assert len(selected) == args.rows
    assert len({row[4] for row in selected}) == args.rows
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        assert not universe_groups[left] & universe_groups[right]
        assert not selected_groups[left] & selected_groups[right]
    for split in SPLITS:
        assert {row[2] for row in selected if row[0] == split} == {0, 1}
    selected.sort(key=lambda row: (SPLITS.index(row[0]), hashlib.sha256(row[4]).digest()))
    print(json.dumps({"input_rows": counts["input_rows"], "eligible_unique_rows": counts["eligible_unique_rows"], "sample_rows": len(selected), "features": len(feature_names)}), flush=True)
    print("Extracting numeric features for sampled rows only.", flush=True)

    feature_path = output / "features.csv.gz"
    with feature_path.open("wb") as binary:
        with gzip.GzipFile(filename="", mode="wb", fileobj=binary, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["label", "source", "split", "group_id"] + feature_names)
                for index, (split, source, label, group_id, url_id, raw_url) in enumerate(selected, 1):
                    try:
                        features = extractor.extract_features(raw_url, SCHEMA)
                        values = [float(features[name]) for name in feature_names]
                        if not all(math.isfinite(value) for value in values):
                            raise ValueError("Nonfinite numeric feature")
                    except Exception as exc:
                        # Never put the raw URL in an error or traceback.
                        raise RuntimeError(f"Feature extraction failed for opaque sample {url_id.hex()}: {type(exc).__name__}") from None
                    writer.writerow([label, source, split, group_id.hex()] + values)
                    if index % 10000 == 0:
                        print(f"Extracted {index}/{args.rows} rows", flush=True)

    # Read the shipped file back; check output schema, finite values and groups.
    checked_counts = Counter()
    checked_groups = defaultdict(set)
    with gzip.open(feature_path, "rt", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == ["label", "source", "split", "group_id"] + feature_names
        for row in reader:
            assert row["label"] in {"0", "1"} and row["split"] in SPLITS
            assert all(math.isfinite(float(row[name])) for name in feature_names)
            assert len(row["group_id"]) == 64 and all(char in "0123456789abcdef" for char in row["group_id"])
            checked_counts[(row["split"], row["source"], int(row["label"]))] += 1
            checked_groups[row["split"]].add(row["group_id"])
    assert checked_counts == selected_counts
    assert sum(checked_counts.values()) == args.rows
    assert all(not checked_groups[a] & checked_groups[b] for a, b in (("train", "validation"), ("train", "test"), ("validation", "test")))
    csv_hash = hashlib.sha256()
    csv_bytes = 0
    with gzip.open(feature_path, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            csv_hash.update(block)
            csv_bytes += len(block)

    manifest = {
        "format_version": 1,
        "name": "Phish Radar RF versus MLP preliminary Colab demonstration",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "rows": args.rows,
        "features_csv_sha256": csv_hash.hexdigest(),
        "features_csv_bytes": csv_bytes,
        "labels": {"0": "benign", "1": "phishing"},
        "feature_schema": SCHEMA,
        "feature_count": len(feature_names),
        "feature_names": feature_names,
        "metadata_columns": ["label", "source", "split", "group_id"],
        "source_dataset": {
            "path": source_csv.relative_to(root).as_posix(),
            "sha256": data_digest,
            "recorded_sha256": EXPECTED_DATA_SHA256,
            "recorded_hash_matches": data_digest == EXPECTED_DATA_SHA256,
            "bytes": source_csv.stat().st_size,
            "counts_by_source": dict(sorted(source_counts.items())),
            "source_provenance": "docs/paper/evidence/dataset-provenance.json",
        },
        "source_snapshot": {
            "path": ".ai-context/current-source",
            "source_date": snapshot["source_date"],
            "archive_sha256": snapshot["snapshot_zip"]["sha256"],
            "verified_files": verified_files,
            "runtime_model_used": False,
        },
        "filtering": {
            **dict(sorted(counts.items())),
            "excluded_sources": dict(sorted(excluded_sources.items())),
            "duplicate_occurrences_by_source_before_conflict_removal": dict(sorted(duplicate_sources.items())),
            "url_deduplication": "Across the full valid-URL universe before sampling; excluded reference rows contribute only to contradiction detection, never export. IDNA/lowercase hostname, remove one www and trailing host dot, default port, and fragment; empty path becomes /. Preserve scheme/path/query/userinfo distinctions. First eligible source wins for repeated equal-label URL; remove all eligible rows of conflicting-label canonical URL.",
            "url_values_exported": False,
            "raw_hostname_values_exported": False,
            "original_group_or_split_columns_used": False,
        },
        "split_protocol": {
            "grouping": "Recomputed registered domain from snapshot offline ICANN PSL; IP address grouped by literal address. PRIVATE suffix rules are not in this project PSL, so tenants under a private hosting suffix may conservatively share the same parent group.",
            "assignment": "SHA256('phish-radar-demo-group:' + seed + ':' + registered_domain), first 64 bits / 2**64; <0.70 train, <0.85 validation, otherwise test. Assigned before sampling across retained universe.",
            "group_id": "The full deterministic SHA256 digest above. Pseudonymous opaque group identifier, not a claim of irreversible anonymization.",
            "sampling": "Within each split, proportional largest-remainder source x label allocation; deterministic random sample without replacement within each stratum.",
            "target_rows": targets,
            "universe_counts": counter_records(universe_counts, ("split", "source", "label")),
            "sample_counts": counter_records(selected_counts, ("split", "source", "label")),
            "universe_unique_groups": {key: len(universe_groups[key]) for key in SPLITS},
            "sample_unique_groups": {key: len(selected_groups[key]) for key in SPLITS},
            "group_overlap_count": 0,
            "selected_canonical_url_duplicates": 0,
            "finite_features_verified": True,
            "both_classes_each_split_verified": True,
        },
        "files": {
            "features.csv.gz": {"sha256": sha256_file(feature_path), "bytes": feature_path.stat().st_size},
        },
        "caveats": [
            "This is a new split of a reused project development source, not a new independent or forward-temporal test.",
            "The existing production/demo RF artifact is not used. Both comparison models must be trained fresh on this shared sample.",
            "172 v8 features intentionally omit two v9/v10 publisher-reference fields; this is a separate comparison experiment from the documented 174-feature project model.",
            "Validation is for early stopping/threshold choice. Use test only for the final shared evaluation; it has no timestamp-based independence claim.",
            "Publisher/source artefacts remain possible, including PhreshPhish benign query stripping and collection/class differences. Excluding query-length/count features does not remove every shortcut.",
            "Sampling preserves each split's source-by-label proportions approximately; class balance and source mix need not be identical across splits.",
            "One seed and one small sample are for a classroom demonstration, not statistical proof of superiority, current-Internet accuracy, or production readiness.",
            "Project dataset/source licenses still apply to derived features. DeepURLBench is CC BY-NC 4.0; consult the source provenance before redistribution.",
            "No raw URL, hostname, observed timestamp, user history, credentials, registry contents, or original free-text evidence is exported.",
        ],
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(output / "demo_dataset.zip", "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(feature_path, "features.csv.gz")
        archive.write(output / "manifest.json", "manifest.json")
    with zipfile.ZipFile(output / "demo_dataset.zip") as archive:
        assert set(archive.namelist()) == {"features.csv.gz", "manifest.json"}
        assert archive.testzip() is None
    elapsed = time.perf_counter() - started
    print(json.dumps({
        "output": output.relative_to(root).as_posix(),
        "rows": args.rows,
        "feature_count": len(feature_names),
        "sample_counts": counter_records(selected_counts, ("split", "source", "label")),
        "filtering": dict(sorted(counts.items())),
        "zip_bytes": (output / "demo_dataset.zip").stat().st_size,
        "zip_sha256": sha256_file(output / "demo_dataset.zip"),
        "elapsed_seconds": round(elapsed, 2),
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()
