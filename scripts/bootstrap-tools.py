#!/usr/bin/env python3
"""Fetch hash-pinned, unmodified compiler/host references. No editor or login."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(os.environ.get('SDK_TOOLS_DIR', ROOT / '.sdk-tools')).resolve()
MANIFEST = ROOT / 'scripts/tools.json'


def run(*args, **kwargs):
    print('+', *map(str, args), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def download(spec, destination):
    run('curl', '--fail', '--location', '--silent', '--show-error',
        '--connect-timeout', '30', '--max-time', '600', spec['url'], '-o', destination)
    with destination.open('rb') as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
        digest = digest.hexdigest()
    if digest != spec['sha256']:
        raise RuntimeError('SHA256 mismatch: ' + spec['url'])


def main():
    fingerprint = hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    marker = TOOLS / '.complete'
    if marker.exists() and marker.read_text() == fingerprint:
        return
    specs = json.loads(MANIFEST.read_text())
    TOOLS.mkdir(parents=True, exist_ok=True)
    # Partial downloads/extractions never mark the cache complete. A failed step
    # fails CI; it is not retried or hidden by an existing partial cache.
    with tempfile.TemporaryDirectory(prefix='cubeage-sdk-tools-') as directory:
        tmp = Path(directory)
        unity = tmp / 'unity.tar.xz'
        download(specs['unity'], unity)
        run('tar', '-xJf', unity, '-C', TOOLS,
            'Editor/Data/DotNetSdkRoslyn', 'Editor/Data/NetCoreRuntime',
            'Editor/Data/Managed/UnityEngine', 'Editor/Data/NetStandard')
        lua = tmp / 'lua.tar.gz'
        download(specs['lua'], lua)
        run('tar', '-xzf', lua, '-C', TOOLS)
        run('make', '-C', TOOLS / 'lua-5.1.5', 'generic')
        for key, name in [('cocos-types', 'creator.d.ts'),
                          ('solar2d-json', 'json.lua'), ('solar2d-dkjson', 'dkjson.lua')]:
            download(specs[key], tmp / name)
            shutil.copyfile(tmp / name, TOOLS / name)
    marker.write_text(fingerprint)


if __name__ == '__main__':
    main()
