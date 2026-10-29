"""Start an already installed loopback Ollama for the local academic demo."""
import json
import os
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


def tags(base):
    try:
        with urllib.request.urlopen(base + '/api/tags', timeout=1) as response:
            return json.load(response)
    except Exception:
        return None


def ensure_local_ollama(saved):
    if saved.get('LLM_PROVIDER', 'ollama') not in {'ollama', 'local', 'qwen'}:
        return
    base = saved.get('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
    parsed = urlsplit(base)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'}:
        return
    if tags(base) is not None:
        return
    installed = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Ollama/ollama.exe'
    executable = shutil.which('ollama') or (str(installed) if installed.is_file() else None)
    if not executable:
        print('Local Ollama not installed; explanation fallback remains available.', flush=True)
        return
    environment = dict(os.environ, OLLAMA_HOST=f"127.0.0.1:{parsed.port or 11434}")
    subprocess.Popen([executable, 'serve'], env=environment,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    for _ in range(10):
        if tags(base) is not None:
            print('Local Ollama ready; using installed models only.', flush=True)
            return
        time.sleep(.5)
    print('Local Ollama still starting; check /health for readiness.', flush=True)
