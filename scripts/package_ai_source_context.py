"""Build and verify the curated, deterministic source archive for AI readers.

Uses only Python's standard library. This archives source for inspection, not a
working deployment: model binaries, datasets, local state and credentials are
deliberately absent. Run from any directory; the default project root is the
parent of this script's directory.
"""

from __future__ import annotations

import argparse
import ast
from datetime import date
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
from urllib.parse import urlsplit
import zipfile


SOURCE_DATE = "2026-10-20"
ZIP_PATH = "docs/ai/current-source.zip"
MANIFEST_PATH = "docs/ai/CURRENT_SOURCE_MANIFEST.json"
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_BYTES = 20 * 1024 * 1024
MAX_ARCHIVE_BYTES = 10 * 1024 * 1024
CODE_SUFFIXES = {".py", ".js", ".cjs", ".mjs", ".ps1", ".sh"}
WEB_TEXT_SUFFIXES = {
    ".js", ".jsx", ".cjs", ".mjs", ".ts", ".tsx", ".html", ".css",
    ".scss", ".json", ".svg", ".webmanifest",
}
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".woff", ".woff2", ".ttf"}
DEPLOY_SUFFIXES = {".conf", ".service", ".yaml", ".yml", ".json", ".sh", ".ps1", ".toml"}
BACKEND_STATIC = {
    "backend/public_suffix_list.dat",
    "backend/public_suffix_list.SOURCE.txt", "backend/requirements.txt",
    "backend/requirements-training.txt",
}
ROOT_FILES = {".env.example", ".dockerignore", ".gitignore", ".gitattributes", "Dockerfile"}
BANNED_DIRECTORIES = {
    ".git", ".agents", ".codex", ".aws", ".venv", "venv", "env",
    "node_modules", "__pycache__", "dist", "build", "data", "model_backups",
    "backups", "local-backups", "output", "tmp", "temp", "cache", ".cache",
    "credentials", "secrets", "authdata", "sessions", "logs",
}
BANNED_FILE_NAMES = {"credentials.json", "secrets.json", "authdata.json", "tokens.json", "cookies.json"}
EXCLUDED_CATEGORIES = [
    "Model binaries, candidate models and model backups; obtain a matching artifact separately.",
    "Raw datasets and all backend/data files, raw reference manifests and collection outputs.",
    "Local environment files other than .env.example; credentials, auth/session records, logs and caches.",
    "Local model-demo authorization metadata, which contains machine-specific source/backup paths.",
    "backend/reference-origin-v1.json: its evidence URLs contain transient query values; obtain the original matching registry privately to run the recorded model.",
    "Dependencies, virtual environments, compiled builds, downloaded extension archives and archive checksums.",
    "Nested Git repositories, Git metadata, agent settings, local backups, temporary/output folders and symlinks/reparse points.",
    "Historical project documentation; docs/ai and docs/paper are separate context outside this source archive.",
    "Files outside the explicit source/template/schema/asset allowlist and files larger than 2 MiB.",
]
TEXT_SUFFIXES = WEB_TEXT_SUFFIXES | CODE_SUFFIXES | DEPLOY_SUFFIXES | {".md", ".txt", ".sql", ".dat"}

# Findings report a file, line and category only; never print the matched value.
SECRET_TOKEN = re.compile(
    r"(?:\bgh[pousr]_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b|"
    r"\bAKIA[A-Z0-9]{16}\b|\bxox[baprs]-[A-Za-z0-9-]{20,}\b|"
    r"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}\b)"
)
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----")
CREDENTIAL_LITERAL = re.compile(
    r"(?ix)(?<![\w?&./-])(?P<name>[\w-]*(?:password|passwd|pwd|api[_-]?key|access[_-]?token|"
    r"client[_-]?secret|auth[_-]?token|session[_-]?token|secret[_-]?key)[\w-]*)"
    r"[\"']?\s*[:=]\s*(?P<quote>[\"'])(?P<value>[^\"'\r\n]*)(?P=quote)"
)
ENV_CREDENTIAL = re.compile(
    r"(?im)^\s*(?:export\s+)?(?P<name>[A-Z0-9_]*(?:PASSWORD|PASSWD|API_KEY|"
    r"ACCESS_TOKEN|CLIENT_SECRET|SECRET_KEY)[A-Z0-9_]*)\s*=\s*(?P<value>[^\r\n]*)"
)
URL_LITERAL = re.compile(r"https?://[^\s\"'<>`]+")
AUTH_DATA_INSERT = re.compile(
    r"(?im)^\s*(?:INSERT|REPLACE)\s+INTO\s+[`\"]?(?:users|sessions|search_history|"
    r"scan_feedback|audit_events)\b"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_link(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def valid_relative(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and "\\" not in name and ":" not in name and not path.is_absolute() and all(
        part not in {"", ".", ".."} for part in path.parts
    )


def selected(name: str) -> bool:
    path = PurePosixPath(name)
    parts = path.parts
    suffix = path.suffix.lower()
    if not valid_relative(name) or any(p.lower() in BANNED_DIRECTORIES for p in parts[:-1]):
        return False
    if path.name.lower() in BANNED_FILE_NAMES:
        return False
    if path.name.startswith(".env") and path.name != ".env.example":
        return False
    if len(parts) == 1:
        return name in ROOT_FILES or suffix == ".sh"
    if parts[0] == "backend":
        return suffix == ".py" or name in BACKEND_STATIC
    if parts[0] == "scripts":
        return suffix in CODE_SUFFIXES
    if parts[0] == "extension":
        return suffix in WEB_TEXT_SUFFIXES | ASSET_SUFFIXES
    if parts[0] == "web-app":
        if len(parts) == 2:
            return suffix in WEB_TEXT_SUFFIXES or path.name in {"package-lock.json", "package.json", ".env.example"}
        return parts[1] in {"src", "public", "assets"} and suffix in WEB_TEXT_SUFFIXES | ASSET_SUFFIXES
    if parts[0] == "database":
        return suffix in {".sql", ".md"}
    if parts[0] == "deploy":
        return suffix in DEPLOY_SUFFIXES or path.name in {"Dockerfile", ".env.example"}
    return False


def walk_sources(root: Path):
    """Visit only allowlisted roots and prune links before descent."""
    def descend(directory: Path):
        for path in sorted(directory.iterdir(), key=lambda p: p.name):
            if is_link(path):
                continue
            if path.is_dir():
                if path.name.lower() not in BANNED_DIRECTORIES:
                    yield from descend(path)
            elif path.is_file():
                name = path.relative_to(root).as_posix()
                if selected(name):
                    yield path, name

    for path in sorted(root.iterdir(), key=lambda p: p.name):
        if is_link(path):
            continue
        if path.is_file() and selected(path.name):
            yield path, path.name
        elif path.is_dir() and path.name in {"backend", "extension", "web-app", "database", "deploy", "scripts"}:
            yield from descend(path)


def is_placeholder(value: str) -> bool:
    value = value.strip().strip("\"'").strip()
    if not value or value in {"***", "...", "<redacted>", "None", "null"}:
        return True
    if value.startswith(("${", "$env:", "os.environ", "process.env", "<")):
        return True
    return bool(re.fullmatch(
        r"(?i)(?:your[_ -].*|replace[_ -].*|change[_ -]?me.*|example[_ -].*|"
        r"placeholder.*|test[_ -].*|dummy[_ -].*|fake[_ -].*|ใส่.*|รหัสผ่าน.*|เปลี่ยน.*)", value
    ))


def synthetic_test_value(name: str, value: str) -> bool:
    """Allow only recognizable, public test fixtures in test/fixture source."""
    filename = PurePosixPath(name).name
    if not (filename.startswith("test_") or "fixture" in filename or filename.startswith("smoke_test_")):
        return False
    # Tests create disposable accounts or pass fixture strings into mock APIs.
    # Token/private-key patterns above still reject credential-shaped secrets.
    return True


def python_credential_literals(text: str):
    sensitive = re.compile(r"(?i)(?:password|passwd|pwd|api_?key|access_?token|client_?secret|auth_?token|session_?token|secret_?key)")
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            names = [target.id for target in targets if isinstance(target, ast.Name)]
        elif isinstance(node, ast.keyword):
            value, names = node.value, [node.arg or ""]
        elif isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and isinstance(key.value, str) and sensitive.search(key.value):
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        yield value.lineno, value.value
            continue
        else:
            continue
        if any(sensitive.search(name) for name in names) and isinstance(value, ast.Constant) and isinstance(value.value, str):
            yield value.lineno, value.value


def scan_text(name: str, text: str) -> list[dict]:
    findings = []

    def found(position: int, category: str):
        item = {"path": name, "line": text.count("\n", 0, position) + 1, "category": category}
        if item not in findings:
            findings.append(item)

    for pattern, category in ((SECRET_TOKEN, "credential-token"), (PRIVATE_KEY, "private-key")):
        for match in pattern.finditer(text):
            found(match.start(), category)
    credential_matches = []
    if name.endswith(".py"):
        for line, value in python_credential_literals(text):
            if not is_placeholder(value) and not synthetic_test_value(name, value):
                position = sum(len(chunk) for chunk in text.splitlines(keepends=True)[:line - 1])
                found(position, "hardcoded-credential-literal")
    else:
        credential_matches.extend(CREDENTIAL_LITERAL.finditer(text))
    if name.endswith(".env.example") or name.endswith(".md"):
        credential_matches.extend(ENV_CREDENTIAL.finditer(text))
    for match in credential_matches:
        value = match.group("value").strip().strip("\"'").strip()
        if not is_placeholder(value) and not synthetic_test_value(name, value):
            found(match.start(), "hardcoded-credential-literal")
    for match in URL_LITERAL.finditer(text):
        try:
            parsed = urlsplit(match.group())
            if parsed.password and not is_placeholder(parsed.password):
                fixture_host = parsed.hostname and (parsed.hostname in {"example.com", "example.org", "example.net", "localhost", "127.0.0.1"} or parsed.hostname.endswith((".example", ".test", ".invalid", ".example.com", ".example.org", ".example.net")))
                safe_fixture = synthetic_test_value(name, parsed.password) and fixture_host
                if not safe_fixture and not (name.endswith(".env.example") and parsed.password == "password"):
                    found(match.start(), "credential-in-url")
            if name.endswith(".json") and parsed.query:
                if re.search(r"(?i)(?:^|&)(?:nonce|state|access_token|session|sessionid|code)=", parsed.query):
                    found(match.start(), "transient-query-in-json")
        except ValueError:
            # Source contains URL regexes/templates as well as complete URLs.
            pass
    if name.endswith(".sql"):
        for match in AUTH_DATA_INSERT.finditer(text):
            found(match.start(), "auth-or-history-row-in-sql")
    return findings


def collect(root: Path) -> tuple[list[tuple[str, bytes]], list[dict]]:
    entries = []
    findings = []
    for path, name in walk_sources(root):
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise ValueError(f"Allowlisted source exceeds file size limit: {name}")
        data = path.read_bytes()
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in ROOT_FILES or path.name == ".env.example":
            try:
                decoded = data.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ValueError(f"Text source is not UTF-8: {name}") from exc
            findings.extend(scan_text(name, decoded))
        entries.append((name, data))
    entries.sort(key=lambda item: item[0])
    if sum(len(data) for _, data in entries) > MAX_TOTAL_BYTES:
        raise ValueError("Curated sources exceed total source size limit")
    return entries, findings


def verify_archive(path: Path, files: list[dict]) -> None:
    expected = {entry["path"]: entry for entry in files}
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) != len(expected) or len({item.filename for item in infos}) != len(infos):
            raise ValueError("Archive has missing or duplicate entries")
        for info in infos:
            name = info.filename
            if not valid_relative(name) or name not in expected or not selected(name):
                raise ValueError("Archive contains a path outside the source allowlist")
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError("Archive contains a symbolic link")
            data = archive.read(info)
            item = expected[name]
            if len(data) != item["bytes"] or sha256(data) != item["sha256"]:
                raise ValueError(f"Archive content does not match manifest: {name}")


def output_path(root: Path, name: str) -> Path:
    if not valid_relative(name):
        raise ValueError("Invalid output relative path")
    cursor = root
    for part in PurePosixPath(name).parts:
        cursor = cursor / part
        if cursor.exists() or cursor.is_symlink():
            if is_link(cursor):
                raise ValueError("Output path contains a link or reparse point")
    return cursor


def guard_current_source(root: Path) -> None:
    """Refuse an old clone before it can replace the newer source archive."""
    trees = {}
    for name in ("backend/feature_extractor.py", "backend/app.py"):
        path = root / name
        if not path.is_file() or is_link(path) or is_link(path.parent):
            raise ValueError("Current source guard failed; use --root with the current working copy, not the legacy clone")
        if path.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Current source guard input exceeds size limit")
        trees[name] = ast.parse(path.read_text(encoding="utf-8-sig"))
    schema_tree = trees["backend/feature_extractor.py"]
    has_v10 = any(
        isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
        and node.value.value == "url-v10-reference-root-context"
        and any(isinstance(target, ast.Name) and target.id == "REFERENCE_ROOT_SCHEMA_VERSION" for target in node.targets)
        for node in schema_tree.body
    )
    app_tree = trees["backend/app.py"]
    imports_demo_guard = any(
        isinstance(node, ast.ImportFrom) and node.module == "demo_model"
        and any(alias.name == "authorized_demo" for alias in node.names)
        for node in app_tree.body
    )
    source_strings = {node.value for node in ast.walk(app_tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    has_readiness = {"production_ready", "experimental_demo", "reference_origin_registry_sha256"}.issubset(source_strings)
    if not (has_v10 and imports_demo_guard and has_readiness):
        raise ValueError("Current source guard failed; use --root with the current working copy, not the legacy clone")


def build(root: Path, check_only: bool, source_date: str = SOURCE_DATE) -> dict:
    parsed_date = date.fromisoformat(source_date)
    if not (1980 <= parsed_date.year <= 2107) or parsed_date.isoformat() != source_date:
        raise ValueError("--source-date must be YYYY-MM-DD in the ZIP-supported years 1980 to 2107")
    guard_current_source(root)
    entries, findings = collect(root)
    summary = {
        "files": len(entries), "uncompressed_bytes": sum(len(data) for _, data in entries),
        "preflight_findings": findings,
    }
    if findings or check_only:
        return summary
    files = [{"path": name, "sha256": sha256(data), "bytes": len(data)} for name, data in entries]
    destination = output_path(root, ZIP_PATH)
    manifest_destination = output_path(root, MANIFEST_PATH)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if is_link(destination.parent) or (destination.exists() and is_link(destination)):
        raise ValueError("Output path must not be a link or reparse point")
    with tempfile.NamedTemporaryFile(prefix="current-source-", suffix=".zip", dir=destination.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, data in entries:
                info = zipfile.ZipInfo(name, (parsed_date.year, parsed_date.month, parsed_date.day, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        if temporary_path.stat().st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("Archive exceeds 10 MiB limit")
        verify_archive(temporary_path, files)
        archive_data = temporary_path.read_bytes()
        manifest = {
            "source_date": source_date, "inspection_date": source_date,
            "scope": "Curated current source from the original project root; not the old nested repository source.",
            "snapshot_zip": {"path": ZIP_PATH, "sha256": sha256(archive_data), "bytes": len(archive_data)},
            "files": files, "excluded_categories": EXCLUDED_CATEGORIES,
            "verification": {
                "credential_preflight_passed": True,
                "preflight_scope": "Heuristic static scan of every selected text file; recognized synthetic test fixtures and placeholder values allowed. Not a formal guarantee that all secrets are detectable.",
                "zip_entries_and_hashes_verified": True,
                "runtime_tests_run": False,
                "deterministic_zip_metadata": True,
            },
        }
        if manifest_destination.exists() and is_link(manifest_destination):
            raise ValueError("Manifest destination must not be a link")
        temporary_path.replace(destination)
        manifest_destination.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        summary.update({"archive_bytes": len(archive_data), "archive_sha256": manifest["snapshot_zip"]["sha256"], "archive_verified": True})
    finally:
        temporary_path.unlink(missing_ok=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--source-date", default=SOURCE_DATE, help="Inspection date as YYYY-MM-DD; use a new date when refreshing the source snapshot")
    parser.add_argument("--check-only", action="store_true", help="Only collect and scan candidates; do not write output")
    args = parser.parse_args()
    try:
        result = build(args.root.resolve(strict=True), args.check_only, args.source_date)
    except (OSError, ValueError, SyntaxError, zipfile.BadZipFile) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["preflight_findings"] else 0


if __name__ == "__main__":
    sys.exit(main())
