#!/usr/bin/env python3
"""Inspect repository context without importing the application or model.

Uses only the Python standard library. Reads a fixed allowlist of source and
metadata files, never .env, raw datasets, or network endpoints. Model/archive
bytes are read only with an explicit hash flag; pickle is never deserialized.
Printed snapshot metadata remains recorded evidence, not a runtime assertion.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = (
    "backend/app.py", "backend/feature_extractor.py",
    "backend/requirements.txt", "backend/requirements-training.txt",
    "web-app/package.json", "extension/manifest.json",
    "backend/reference-origin-v1.json",
)
EVIDENCE = "docs/paper/evidence/"
ARCHIVE_MANIFEST = "docs/ai/CURRENT_SOURCE_MANIFEST.json"
ARCHIVE_PATH = "docs/ai/current-source.zip"
MAX_TEXT_BYTES = 2 * 1024 * 1024


def safe_path(base: Path, relative: str) -> Path:
    """Do not follow a source/manifest path outside its inspected location."""
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError("path escapes inspected location")
    if any(part.lower().startswith(".env") for part in path.parts):
        raise ValueError("environment files are excluded")
    return path


def read_text(base: Path, relative: str) -> str | None:
    try:
        path = safe_path(base, relative)
        if not path.is_file():
            return None
        if path.stat().st_size > MAX_TEXT_BYTES:
            raise ValueError("text file exceeds inspection size limit")
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"Cannot inspect {relative}: {type(exc).__name__}") from exc


def read_json(base: Path, relative: str) -> dict:
    text = read_text(base, relative)
    if text is None:
        return {}
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {relative}")
    return data


def file_info(base: Path, relative: str, hash_bytes: bool = True) -> dict:
    result = {"path": relative, "exists": False}
    try:
        path = safe_path(base, relative)
        if not path.is_file():
            return result
        result.update(exists=True, bytes=path.stat().st_size)
        if hash_bytes:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            result["sha256"] = digest.hexdigest()
    except (OSError, ValueError) as exc:
        result["error"] = type(exc).__name__
    return result


def schema_markers(text: str) -> dict[str, str]:
    """Extract literal schema constants with AST; never execute source code."""
    result = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if (isinstance(target, ast.Name)
                        and target.id.endswith("SCHEMA_VERSION")
                        and isinstance(node.value.value, str)):
                    result[target.id] = node.value.value
    return result


def compare_hash(actual: str | None, expected: str | None) -> str:
    if not actual or not expected:
        return "not_compared"
    return "match" if actual.lower() == expected.lower() else "MISMATCH"


def git_context(location: Path) -> dict:
    binary = shutil.which("git")
    result = {"git_available": bool(binary),
              "local_git_marker": (location / ".git").exists()}
    if not binary:
        return result
    # rev-parse does not alter the worktree, invoke hooks, or access remotes.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env["GIT_OPTIONAL_LOCKS"] = "0"
    prefix = [binary, "--no-optional-locks", "-C", str(location)]
    try:
        top = subprocess.run(prefix + ["rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5,
                             check=False, env=env, shell=False)
        if top.returncode:
            # Refusal or corruption is not proof that a checkout does not exist.
            if "dubious ownership" in top.stderr.lower():
                result["status"] = "git_refused_ownership_check"
            elif "not a git repository" in top.stderr.lower() and not result["local_git_marker"]:
                result["status"] = "not_a_git_worktree"
            else:
                result["status"] = "git_query_failed"
            return result
        same = Path(top.stdout.strip()).resolve() == location.resolve()
        result["repository_root_matches_location"] = same
        result["status"] = "git_worktree" if same else "inside_ancestor_worktree"
        head = subprocess.run(prefix + ["rev-parse", "--verify", "HEAD"],
                              capture_output=True, text=True, timeout=5,
                              check=False, env=env, shell=False)
        value = head.stdout.strip()
        if head.returncode == 0 and re.fullmatch(r"[0-9a-fA-F]{40,64}", value):
            result["head"] = value
            result["head_scope"] = "this_location" if same else "ancestor_repository"
    except (OSError, subprocess.TimeoutExpired):
        result["status"] = "git_unavailable_or_timed_out"
    return result


def requirement_lines(text: str) -> list[str]:
    # Do not print index URLs, credentials, direct URLs, or arbitrary directives.
    pattern = r"[A-Za-z0-9_.-]+(?:\[[A-Za-z0-9_,.-]+\])?(?:[<>=!~].*)?"
    return [line.strip() for line in text.splitlines()
            if re.fullmatch(pattern, line.strip())
            and "://" not in line and "@" not in line]


def inspect_location(base: Path, label: str, hash_model: bool) -> dict:
    result = {"location": label, "exists": base.is_dir(), "errors": []}
    if not base.is_dir():
        return result
    result["git"] = git_context(base)
    result["source_files"] = [file_info(base, name) for name in SOURCE_FILES]
    result["model_file"] = file_info(base, "backend/model.pkl", hash_model)
    result["model_metadata"] = "not_deserialized; see recorded_snapshot_metadata"
    result["source"] = {}
    result["declared_dependencies"] = {}
    for name in ("backend/requirements.txt", "backend/requirements-training.txt"):
        try:
            text = read_text(base, name)
            if text is not None:
                result["declared_dependencies"][name] = requirement_lines(text)
        except ValueError as exc:
            result["errors"].append(str(exc))
    for name in ("backend/feature_extractor.py", "backend/app.py"):
        try:
            text = read_text(base, name)
            if text is not None and name.endswith("feature_extractor.py"):
                result["source"]["schema_constants"] = schema_markers(text)
                result["source"]["default_schema_constant"] = result["source"]["schema_constants"].get("FEATURE_SCHEMA_VERSION")
            elif text is not None:
                tree = ast.parse(text)
                strings = {n.value for n in ast.walk(tree)
                           if isinstance(n, ast.Constant) and isinstance(n.value, str)}
                result["source"]["risk_modes_present_in_code"] = sorted(
                    strings & {"ml_only", "weighted_40_60", "legacy_fixed_blend"})
                result["source"]["has_predict_function"] = any(
                    isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "predict"
                    for n in tree.body)
        except (ValueError, SyntaxError) as exc:
            result["errors"].append(f"{name}: {type(exc).__name__}")
    for name in ("web-app/package.json", "extension/manifest.json"):
        try:
            doc = read_json(base, name)
            if doc:
                keys = ("name", "version", "dependencies", "devDependencies") if name.endswith("package.json") else ("name", "version", "manifest_version")
                result["declared_dependencies"][name] = {k: doc[k] for k in keys if k in doc}
        except (ValueError, json.JSONDecodeError) as exc:
            result["errors"].append(f"{name}: {type(exc).__name__}")
    return result


def snapshot_metadata(root: Path) -> dict:
    result = {"origin": "recorded_documentation_only", "errors": []}
    for name, key in (("active-model.json", "active_model"),
                      ("dataset-provenance.json", "dataset_provenance"),
                      ("source-manifest.json", "source_manifest")):
        try:
            result[key] = read_json(root, EVIDENCE + name)
        except (ValueError, json.JSONDecodeError) as exc:
            result["errors"].append(f"{name}: {type(exc).__name__}")
    return result


def archive_context(root: Path, verify: bool) -> dict:
    result = {"manifest": file_info(root, ARCHIVE_MANIFEST),
              "archive": file_info(root, ARCHIVE_PATH, verify),
              "automatic_extraction": False}
    try:
        doc = read_json(root, ARCHIVE_MANIFEST)
        archive = doc.get("snapshot_zip", {})
        expected = archive.get("sha256") if isinstance(archive, dict) else None
        expected = expected or doc.get("snapshot_zip_sha256")
        files = doc.get("files", doc.get("source_files", doc.get("entries", [])))
        result.update(source_date=doc.get("source_date"),
                      declared_file_count=len(files) if isinstance(files, list) else None,
                      expected_zip_sha256=expected,
                      zip_hash_comparison=compare_hash(result["archive"].get("sha256"), expected),
                      note="Reference source snapshot, not the installed runtime. Extract manually to .ai-context/current-source to inspect it.")
    except (ValueError, json.JSONDecodeError) as exc:
        result["error"] = type(exc).__name__
    return result


def build_report(root: Path, hash_model: bool, verify_snapshot: bool) -> dict:
    snapshots = snapshot_metadata(root)
    recorded = snapshots.get("active_model", {})
    provenance = snapshots.get("dataset_provenance", {})
    inspection = recorded.get("inspection", {})
    expected_model = inspection.get("artifact_sha256")
    if not expected_model:
        expected_model = provenance.get("active_lineage", {}).get("model", {}).get("sha256")
    locations = [inspect_location(root, ".", hash_model)]
    nested = root / "Phishing_AI_Extension_Demo"
    if nested.is_dir():
        locations.append(inspect_location(nested, "Phishing_AI_Extension_Demo", hash_model))
    extracted = root / ".ai-context/current-source"
    if extracted.is_dir():
        locations.append(inspect_location(extracted, ".ai-context/current-source (reference only)", hash_model))
    diagnostics = []
    expected_sources = {v.get("path"): v.get("sha256") for v in snapshots.get("source_manifest", {}).get("source_files", []) if isinstance(v, dict)}
    schema = recorded.get("feature_schema_version")
    for item in locations:
        label = item["location"]
        model = item.get("model_file", {})
        item["model_hash_vs_recorded_snapshot"] = compare_hash(model.get("sha256"), expected_model)
        if item["model_hash_vs_recorded_snapshot"] == "MISMATCH":
            diagnostics.append(f"{label}: model bytes MISMATCH recorded paper artifact; snapshot metadata must not describe this local model.")
        elif model.get("exists") and not hash_model:
            diagnostics.append(f"{label}: model bytes not checked; use --hash-model to compare with recorded snapshot. Model metadata remains unverified.")
        markers = item.get("source", {}).get("schema_constants", {})
        item["source_support_for_recorded_schema"] = (
            "marker_present_only" if schema and schema in markers.values()
            else "MISMATCH_marker_missing" if schema and markers else "unknown")
        if item["source_support_for_recorded_schema"] == "MISMATCH_marker_missing":
            diagnostics.append(f"{label}: source lacks recorded schema marker {schema}; source and paper model snapshot are inconsistent.")
        item["source_hashes_vs_paper_manifest"] = [
            {"path": f["path"], "comparison": compare_hash(f.get("sha256"), expected_sources[f["path"]])}
            for f in item.get("source_files", []) if f["path"] in expected_sources]
        for check in item["source_hashes_vs_paper_manifest"]:
            if check["comparison"] == "MISMATCH":
                diagnostics.append(f"{label}: {check['path']} differs from recorded source manifest.")
    ambiguity = len(locations) > 1
    if ambiguity:
        diagnostics.append("Multiple source locations exist. The script directory defines the inspected project root; nested Git HEAD does not identify the parent sources.")
    if not recorded:
        diagnostics.append("Recorded active-model snapshot is missing; current model schema, formula and policy cannot be inferred by this script.")
    lineage = provenance.get("active_lineage", {})
    combined = provenance.get("combined_dataset", {})
    return {
        "project_root": str(root), "runtime_verified": False,
        "inspection_scope": "Read-only static files and recorded evidence. No application import, pickle deserialization, .env read, network, training, or runtime probe.",
        "model_hash_requested": hash_model, "multiple_source_locations": ambiguity,
        "locations": locations,
        "recorded_snapshot_metadata": {
            "origin": "Documentation snapshot; not freshly deserialized model metadata",
            "inspection_date": inspection.get("date"),
            "model_version": recorded.get("model_version"),
            "feature_schema_version": schema, "fusion_method": recorded.get("fusion_method"),
            "policy": recorded.get("policy"), "production_ready": recorded.get("production_ready"),
            "model_sha256": expected_model,
            "dataset_provenance_date": provenance.get("inspection_date"),
            "combined_dataset_path": combined.get("path"),
            "combined_dataset_rows_recorded": combined.get("rows"),
            "combined_dataset_sha256_recorded": lineage.get("combined_development_dataset", {}).get("sha256"),
            "sources_recorded": [v.get("source_column") for v in provenance.get("development_sources", []) if isinstance(v, dict)],
        },
        "current_source_archive": archive_context(root, verify_snapshot),
        "diagnostics": diagnostics,
        "metadata_errors": snapshots["errors"],
    }


def self_test() -> dict:
    tests = {
        "literal_schema_only": schema_markers('FEATURE_SCHEMA_VERSION="v4"\nREFERENCE_ROOT_SCHEMA_VERSION="v10"\nx = dangerous()\n') == {"FEATURE_SCHEMA_VERSION": "v4", "REFERENCE_ROOT_SCHEMA_VERSION": "v10"},
        "matching_hash": compare_hash("ABC", "abc") == "match",
        "mismatching_hash": compare_hash("abc", "def") == "MISMATCH",
        "absent_hash_is_unknown": compare_hash(None, "abc") == "not_compared",
        "requirements_hide_urls": requirement_lines("fastapi==0.111.0\n--index-url https://secret.example\npkg @ https://secret.example\n") == ["fastapi==0.111.0"],
    }
    for name, relative in (("path_escape_rejected", "../outside.py"),
                           ("environment_file_rejected", ".env")):
        try:
            safe_path(ROOT, relative)
            tests[name] = False
        except ValueError:
            tests[name] = True
    return {"self_test": tests, "passed": all(tests.values()),
            "test_scope": "In-memory parser, comparison and path-safety checks; no files created or application code executed."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.add_argument("--hash-model", action="store_true", help="Read model bytes for SHA256 comparison only; never deserialize them.")
    parser.add_argument("--verify-snapshot", action="store_true", help="Hash docs/ai/current-source.zip and compare with its manifest; never extract it.")
    parser.add_argument("--self-test", action="store_true", help="Run in-memory safety/parser checks without inspecting the project.")
    args = parser.parse_args()
    report = self_test() if args.self_test else build_report(ROOT, args.hash_model, args.verify_snapshot)
    if args.json or args.self_test:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        print("Project root:", report["project_root"])
        print("Runtime: NOT VERIFIED. Model metadata below comes from recorded documentation only.")
        for item in report["locations"]:
            print(f"\nLocation: {item['location']}")
            print(json.dumps(item, ensure_ascii=True, indent=2))
        print("\nRecorded documentation:")
        print(json.dumps(report["recorded_snapshot_metadata"], ensure_ascii=True, indent=2))
        print("\nReference source archive:")
        print(json.dumps(report["current_source_archive"], ensure_ascii=True, indent=2))
        print("\nDiagnostics:")
        for message in report["diagnostics"] + report["metadata_errors"]:
            print("-", message)
    return 1 if args.self_test and not report["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
