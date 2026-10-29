"""Explicit, hash-bound permission for a research model used in a Web demo."""
import hashlib
import json
from pathlib import Path


def authorized_demo(model_path: Path, authorization_path: Path) -> bool:
    try:
        record = json.loads(authorization_path.read_text(encoding='utf-8'))
        return (record.get('mode') == 'user_requested_web_test'
                and record.get('model_sha256') == hashlib.sha256(model_path.read_bytes()).hexdigest())
    except (OSError, ValueError, TypeError):
        return False
