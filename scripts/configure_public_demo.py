"""Set one HTTPS demo origin for backend/login/ML and package the extension."""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from urllib.parse import urlsplit
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]


def normalize_origin(value: str) -> str:
    parsed = urlsplit(value.strip())
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
            or parsed.password or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or parsed.port not in (None, 443)):
        raise ValueError('Use the HTTPS origin only, without /#/login, credentials or a path.')
    if not re.fullmatch(r'[a-zA-Z0-9.-]+', parsed.hostname):
        raise ValueError('Use a valid DNS hostname.')
    return 'https://' + parsed.hostname.lower()


def set_env(source: str, key: str, value: str) -> str:
    pattern = rf'^{re.escape(key)}=.*$'
    if re.search(pattern, source, flags=re.MULTILINE):
        return re.sub(pattern, lambda _: f'{key}={value}', source, flags=re.MULTILINE)
    return source.rstrip() + f'\n{key}={value}\n'


def configure(value: str) -> Path:
    origin = normalize_origin(value)
    env_path = ROOT / '.env'
    if not env_path.is_file():
        raise RuntimeError('Configure database credentials in .env first.')
    trust_path = ROOT / 'extension/app-trust.js'
    trust, count = re.subn(
        r"const PUBLIC_WEB_APP_ORIGIN = '[^']*';",
        lambda _: f"const PUBLIC_WEB_APP_ORIGIN = '{origin}';",
        trust_path.read_text(encoding='utf-8'),
    )
    if count != 1:
        raise RuntimeError('Expected one PUBLIC_WEB_APP_ORIGIN configuration.')
    env = env_path.read_text(encoding='utf-8-sig')
    local = ['http://app.phishradar.localhost:5505', 'http://127.0.0.1:5505',
             'http://localhost:5505']
    env = set_env(env, 'AUTH_WEB_ORIGINS', ','.join([origin, *local]))
    env = set_env(env, 'AUTH_COOKIE_SECURE', 'true')
    # Replace previous temporary origins; never trust all of trycloudflare.com.
    env_path.write_text(env, encoding='utf-8')
    trust_path.write_text(trust, encoding='utf-8')
    output = ROOT / 'output/public-demo'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'Phish-Radar-Extension-public.zip'
    with ZipFile(archive, 'w', ZIP_DEFLATED) as package:
        for path in sorted((ROOT / 'extension').rglob('*')):
            if path.is_file():
                package.write(path, 'extension/' + path.relative_to(ROOT / 'extension').as_posix())
        package.writestr('PUBLIC-DEMO.txt',
                        f'Web: {origin}/#/login\n'
                        'Extract ZIP. Open chrome://extensions or brave://extensions.\n'
                        'Enable Developer mode, remove/disable the old copy, then Load unpacked\n'
                        'and select the extracted extension folder. No local backend is required\n'
                        'on the receiving computer. The host must keep the tunnel and backend running.\n'
                        'When the Quick Tunnel URL changes, regenerate and reinstall this package.\n')
    print(f'Public web: {origin}/#/login')
    print(f'Extension ZIP: {archive}')
    print('Restart backend with: bash start-public-backend.sh')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('origin')
    configure(parser.parse_args().origin)
