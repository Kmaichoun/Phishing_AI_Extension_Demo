"""Start the demo using saved origins even if the terminal has stale exports."""
import os
import sys
from pathlib import Path

from dotenv import dotenv_values
import uvicorn
from local_ollama import ensure_local_ollama

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    saved = dotenv_values(ROOT / '.env')
    for key in ('LLM_PROVIDER', 'OLLAMA_BASE_URL', 'OLLAMA_MODEL'):
        if saved.get(key):
            os.environ[key] = saved[key]
    ensure_local_ollama(saved)
    origins = saved.get('AUTH_WEB_ORIGINS', '') or ''
    if not any(value.strip().startswith('https://') for value in origins.split(',')):
        raise SystemExit('Run scripts/configure_public_demo.py with your current HTTPS origin first.')
    os.environ['AUTH_WEB_ORIGINS'] = origins
    os.environ['AUTH_COOKIE_SECURE'] = 'true'
    sys.path.insert(0, str(ROOT / 'backend'))
    uvicorn.run('app:app', host='127.0.0.1', port=8765)
