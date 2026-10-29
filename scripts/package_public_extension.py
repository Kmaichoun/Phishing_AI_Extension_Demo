"""Package the public extension, retaining sources in public/ across Vite builds."""
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'extension'
PUBLIC = ROOT / 'web-app/public/downloads'
DIST = ROOT / 'web-app/dist/downloads'
NAME = 'phish-radar-extension.zip'
ALLOWED = {'.json', '.js', '.css', '.html', '.png', '.svg', '.md'}


def main():
    manifest = json.loads((SOURCE / 'manifest.json').read_text(encoding='utf-8'))
    assert manifest['manifest_version'] == 3
    trust = (SOURCE / 'app-trust.js').read_text(encoding='utf-8')
    origin = re.search(r"PUBLIC_WEB_APP_ORIGIN = '(https://[^']+)'", trust).group(1)
    paths = [manifest['background']['service_worker'], manifest['action']['default_popup']]
    paths += list(manifest.get('icons', {}).values())
    for content in manifest.get('content_scripts', []):
        paths += content.get('js', []) + content.get('css', [])
    for resource in manifest.get('web_accessible_resources', []):
        paths += resource['resources']
    for path in paths:
        assert (SOURCE / path).is_file(), f'Missing manifest asset: {path}'
    files = sorted(p for p in SOURCE.rglob('*') if p.is_file())
    assert all(p.suffix in ALLOWED for p in files), 'Unexpected file in extension; review before publishing'
    for p in files:
        if p.suffix == '.html':
            for asset in re.findall(r'(?:src|href)=["\']([^"\']+)', p.read_text(encoding='utf-8')):
                if not asset.startswith(('#', 'http:', 'https:', 'data:', 'chrome:')):
                    assert (p.parent / asset.split('?')[0]).is_file(), f'Missing HTML asset: {asset}'
    PUBLIC.mkdir(parents=True, exist_ok=True)
    archive = PUBLIC / NAME
    with ZipFile(archive, 'w', compression=ZIP_DEFLATED) as z:
        for p in files:
            info = ZipInfo('phish-radar-extension/' + p.relative_to(SOURCE).as_posix())
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            z.writestr(info, p.read_bytes())
    with ZipFile(archive) as z:
        assert z.testzip() is None
        assert len(z.namelist()) == len(files)
        for p in files:
            assert z.read('phish-radar-extension/' + p.relative_to(SOURCE).as_posix()) == p.read_bytes()
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (PUBLIC / (NAME + '.sha256')).write_text(digest + '  ' + NAME + '\n', encoding='utf-8')
    (PUBLIC / 'INSTALL_TH.md').write_bytes((SOURCE / 'INSTALL_TH.md').read_bytes())
    if (ROOT / 'web-app/dist/index.html').is_file():
        DIST.mkdir(parents=True, exist_ok=True)
        for path in (archive, PUBLIC / (NAME + '.sha256'), PUBLIC / 'INSTALL_TH.md'):
            (DIST / path.name).write_bytes(path.read_bytes())
    print(json.dumps({'version': manifest['version'], 'files': len(files), 'bytes': archive.stat().st_size,
                      'sha256': digest, 'download_url': origin + '/downloads/' + NAME}, ensure_ascii=False))


if __name__ == '__main__':
    main()
