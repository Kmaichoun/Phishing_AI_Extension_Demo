"""Local-only gated model promotion and checksum-verified rollback. No --force flag."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from model_registry import atomic_json, experiment_path, sha256, verified_analysis

PRODUCTION = ROOT/'backend'/'model.pkl'
REGISTRY = ROOT/'backend'/'data'/'model_registry'


@contextmanager
def locked(registry):
    registry.mkdir(parents=True, exist_ok=True)
    lock = registry/'operation.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        lock.unlink(missing_ok=True)


def replace_verified(source, destination, expected_hash):
    fd, name = tempfile.mkstemp(dir=destination.parent, suffix='.tmp')
    os.close(fd)
    temporary = Path(name)
    try:
        shutil.copyfile(source, temporary)
        if sha256(temporary) != expected_hash:
            raise ValueError('Source checksum changed; refusing replacement')
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def install(source, expected_hash, action, production=PRODUCTION, registry=REGISTRY):
    """Caller holds operation lock. Persist recovery info before touching production."""
    previous = sha256(production)
    snapshot = registry / (previous + '.pkl')
    if snapshot.exists() and sha256(snapshot) != previous:
        raise ValueError('Existing backup checksum mismatch')
    if not snapshot.exists():
        replace_verified(production, snapshot, previous)
    event_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    event = {'action': action, 'from_sha256': previous, 'to_sha256': expected_hash,
             'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'prepared'}
    event_path = registry/(event_id+'.json')
    atomic_json(event_path, event)
    if sha256(production) != previous:
        raise ValueError('Production changed while backing up; refusing replacement')
    replace_verified(source, production, expected_hash)
    event['status'] = 'installed'
    atomic_json(event_path, event)
    return event


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('check', 'promote'):
        sub.add_parser(command).add_argument('experiment')
    sub.add_parser('list')
    sub.add_parser('rollback').add_argument('sha256')
    args = parser.parse_args()
    if args.command == 'list':
        print(json.dumps({'production_sha256': sha256(PRODUCTION),
                          'backups': sorted(p.stem for p in REGISTRY.glob('*.pkl'))}, indent=2))
        return
    if args.command in ('check', 'promote'):
        path = experiment_path(args.experiment)
        report = verified_analysis(path)
        print(json.dumps({'promotion_ready': report['promotion_ready'], 'checks': report['checks']}, ensure_ascii=True, indent=2))
        if not report['promotion_ready']:
            raise SystemExit('NOT READY: production unchanged. Review error_analysis.json.')
        if args.command == 'check':
            return
        with locked(REGISTRY):
            report = verified_analysis(path)
            if not report['promotion_ready']:
                raise SystemExit('Gate changed; refusing promotion')
            event = install(path/'candidate.pkl', report['artifacts']['candidate.pkl'], 'promote:'+path.name)
    else:
        if not re.fullmatch('[0-9a-f]{64}', args.sha256):
            raise ValueError('Use a full backup SHA-256 from list')
        with locked(REGISTRY):
            source = REGISTRY/(args.sha256+'.pkl')
            if not source.is_file() or source.is_symlink() or sha256(source) != args.sha256:
                raise ValueError('Verified backup not found')
            event = install(source, args.sha256, 'rollback')
    print(json.dumps(event, indent=2))
    print('Restart backend and verify /health before use. Previous bytes were backed up.')


if __name__ == '__main__':
    main()
