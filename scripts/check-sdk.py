#!/usr/bin/env python3
"""Compile and consume only the source packages this repository distributes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(os.environ.get('SDK_TOOLS_DIR', ROOT / '.sdk-tools')).resolve()
BUILD = ROOT / '.sdk-build'
UNITY = Path('Unity/Assets/CubeageSDK')
SOURCE_DIRS = ('Cocos', 'Solar2D')


def run(*args, **kwargs):
    print('+', *map(str, args), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def expected_files(folder):
    files = set()
    for path in folder.rglob('*'):
        if path.is_symlink():
            raise ValueError('Package symlinks are not supported: ' + str(path))
        if path.is_file():
            files.add(path.relative_to(folder).as_posix())
    return files


def unpack_checked(archive, destination, prefix, expected):
    """Reject missing, unexpected, linked and escaping package members before extract."""
    with tarfile.open(archive) as bundle:
        files = set()
        for member in bundle.getmembers():
            path = Path(member.name)
            if (path.is_absolute() or '..' in path.parts or not path.parts
                    or path.parts[0] != prefix or not (member.isfile() or member.isdir())):
                raise ValueError('Unsafe package member: ' + member.name)
            if member.isfile():
                relative = Path(*path.parts[1:]).as_posix()
                if relative in files:
                    raise ValueError('Duplicate package member: ' + member.name)
                files.add(relative)
        if files != expected:
            raise ValueError('Package contents differ: missing=' + str(expected - files)
                             + ', unexpected=' + str(files - expected))
        for member in bundle.getmembers():
            if member.isfile():
                target = destination / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as stream, target.open('wb') as output:
                    shutil.copyfileobj(stream, output)
    return destination / prefix


def check_unity_layout(package):
    metadata = json.loads((package / 'package.json').read_text())
    if metadata['name'] != 'com.cubeage.sdk' or metadata['unity'] != '2022.3':
        raise ValueError('Unexpected Unity package identity or supported engine line')
    assemblies = {}
    for path in package.rglob('*.asmdef'):
        definition = json.loads(path.read_text())
        if definition['name'] in assemblies:
            raise ValueError('Duplicate assembly name')
        assemblies[definition['name']] = definition
    if 'CubeageSDK.Runtime' not in assemblies:
        raise ValueError('Missing runtime assembly definition')
    for definition in assemblies.values():
        for reference in definition.get('references', []):
            if reference not in assemblies:
                raise ValueError('Unresolved SDK assembly reference: ' + reference)
    guids = set()
    for path in package.rglob('*'):
        if path.suffix == '.meta':
            guid = next(line.split(': ', 1)[1] for line in path.read_text().splitlines()
                        if line.startswith('guid: '))
            if guid in guids:
                raise ValueError('Duplicate Unity asset GUID')
            guids.add(guid)
        elif path.is_file() and not path.with_name(path.name + '.meta').is_file():
            raise ValueError('Missing Unity asset metadata: ' + str(path))


def compiler(editor=False):
    data = TOOLS / 'Editor/Data'
    env = dict(os.environ, DOTNET_ROOT=str(data / 'NetCoreRuntime'),
               DOTNET_MULTILEVEL_LOOKUP='0', DOTNET_SYSTEM_GLOBALIZATION_INVARIANT='1')
    command = [data / 'NetCoreRuntime/dotnet', data / 'DotNetSdkRoslyn/csc.dll', '-noconfig']
    references = [data / 'NetStandard/ref/2.1.0/netstandard.dll']
    references += sorted((data / 'NetStandard/compat/2.1.0/shims').rglob('*.dll'))
    references += sorted((data / 'NetStandard/Extensions/2.0.0').glob('*.dll'))
    references += sorted((data / 'Managed/UnityEngine').glob('UnityEngine*.dll'))
    if editor:
        references += sorted((data / 'Managed/UnityEngine').glob('UnityEditor*.dll'))
    return command, references, env


def csharp(sources, output, *, defines=None, extra_refs=(), executable=False):
    command, references, env = compiler(editor=defines == 'UNITY_EDITOR')
    options = ['-nologo', '-nostdlib+', '-langversion:9.0', '-nowarn:0649',
               '-target:' + ('exe' if executable else 'library'), '-out:' + str(output)]
    if defines:
        options.append('-define:' + defines)
    options += ['-r:' + str(path) for path in references + list(extra_refs)]
    options += list(map(str, sources))
    response = output.with_suffix('.rsp')
    response.write_text('\n'.join('"' + value + '"' for value in options))
    return run(*command, '@' + str(response), env=env)


def typescript(package, out):
    return run(ROOT / 'node_modules/.bin/tsc', '--strict', '--target', 'es2017',
               '--module', 'commonjs', '--skipLibCheck', '--rootDir', package,
               '--outDir', out, TOOLS / 'creator.d.ts',
               package / 'Cocos/CubeageSDK.ts', package / 'Cocos/CubeageSDKConfig.ts',
               package / 'tests/cocos/consumer.ts')


def luac(package):
    for path in sorted((package / 'Solar2D').glob('*.lua')):
        run(TOOLS / 'lua-5.1.5/src/luac', '-p', path)


def packages():
    original = ROOT / UNITY
    check_unity_layout(original)
    result = run('npm', 'pack', '--ignore-scripts', '--json', '--pack-destination', BUILD,
                 original, capture_output=True, text=True)
    packed = json.loads(result.stdout)[0]
    unity_archive = BUILD / packed['filename']
    unity = unpack_checked(unity_archive, BUILD / 'unity', 'package', expected_files(original))
    check_unity_layout(unity)
    for name in expected_files(original):
        if (original / name).read_bytes() != (unity / name).read_bytes():
            raise ValueError('Unity package changed source bytes: ' + name)
    archive = BUILD / 'cubeage-sdk-source.tar.gz'
    expected = set()
    with tarfile.open(archive, 'w:gz') as bundle:
        for directory in SOURCE_DIRS:
            for name in sorted(expected_files(ROOT / directory)):
                relative = directory + '/' + name
                expected.add(relative)
                bundle.add(ROOT / relative, arcname='cubeage-sdk-source/' + relative, recursive=False)
    source = unpack_checked(archive, BUILD / 'source', 'cubeage-sdk-source', expected)
    for name in expected:
        if (ROOT / name).read_bytes() != (source / name).read_bytes():
            raise ValueError('Source package changed source bytes: ' + name)
    # Consumer code lives outside shipped packages. Copy to retain relative imports.
    shutil.copytree(ROOT / 'tests', source / 'tests')
    return unity, source, [unity_archive, archive]


def expect_failure(label, callback):
    try:
        callback()
    except (subprocess.CalledProcessError, ValueError):
        print('Correctly rejected:', label, flush=True)
        return
    raise AssertionError('Negative control unexpectedly passed: ' + label)


def negatives(unity, source):
    with tempfile.TemporaryDirectory(dir=BUILD) as directory:
        tmp = Path(directory)
        broken_unity = tmp / 'unity'
        shutil.copytree(unity, broken_unity)
        with (broken_unity / 'CubeageSDK.cs').open('a') as stream:
            stream.write('\n#error SDK_GATE_NEGATIVE_CONTROL\n')
        expect_failure('Unity compilation error', lambda: csharp(
            sorted(broken_unity.rglob('*.cs')), tmp / 'broken.dll'))
        editor_leak = tmp / 'EditorLeak.cs'
        editor_leak.write_text('public class EditorLeak { public UnityEditor.MenuItem value; }')
        expect_failure('editor API in a player assembly', lambda: csharp(
            [editor_leak], tmp / 'editor-leak.dll'))
        broken_source = tmp / 'source'
        shutil.copytree(source, broken_source)
        with (broken_source / 'Cocos/CubeageSDK.ts').open('a') as stream:
            stream.write('\nconst gateNegativeControl: number = "not a number";\n')
        expect_failure('Cocos type error', lambda: typescript(broken_source, tmp / 'js'))
        with (broken_source / 'Solar2D/cubeage_sdk.lua').open('a') as stream:
            stream.write('\nfunction (\n')
        expect_failure('Lua syntax error', lambda: luac(broken_source))
        (broken_unity / 'CubeageSDK.Runtime.asmdef').unlink()
        expect_failure('missing Unity assembly definition', lambda: check_unity_layout(broken_unity))
        expect_failure('missing package entrypoint', lambda: unpack_checked(
            BUILD / 'cubeage-sdk-source.tar.gz', tmp / 'unpack', 'cubeage-sdk-source', {'missing.lua'}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    os.chdir(ROOT)
    run('python3', ROOT / 'scripts/bootstrap-tools.py')
    if BUILD.exists():
        shutil.rmtree(BUILD)
    BUILD.mkdir()
    unity, source, archives = packages()
    for lane, defines in [('player', None), ('android', 'UNITY_ANDROID'),
                          ('ios', 'UNITY_IOS'), ('editor', 'UNITY_EDITOR')]:
        assembly = BUILD / ('CubeageSDK.' + lane + '.dll')
        csharp(sorted(unity.rglob('*.cs')), assembly, defines=defines)
        csharp([ROOT / 'tests/unity/Consumer.cs'], BUILD / ('Consumer.' + lane + '.dll'),
               extra_refs=[assembly])
    # SdkConfig is engine-independent; execute a separately compiled real consumer.
    config_test = BUILD / 'ConfigTest.dll'
    csharp([unity / 'Models/SdkConfig.cs', ROOT / 'tests/unity/ConfigTest.cs'],
           config_test, executable=True)
    config_test.with_suffix('.runtimeconfig.json').write_text(json.dumps({
        'runtimeOptions': {'tfm': 'net6.0', 'framework': {'name': 'Microsoft.NETCore.App', 'version': '6.0.3'}}}))
    _, _, env = compiler()
    run(TOOLS / 'Editor/Data/NetCoreRuntime/dotnet', config_test, env=env)
    js = BUILD / 'js'
    typescript(source, js)
    run('node', '--test', ROOT / 'tests/cocos/consumer.test.cjs',
        env=dict(os.environ, SDK_JS=str(js / 'Cocos')))
    luac(source)
    run(TOOLS / 'lua-5.1.5/src/luac', '-p', ROOT / 'tests/solar2d/consumer.lua')
    data = BUILD / 'solar2d-data'
    data.mkdir()
    run(TOOLS / 'lua-5.1.5/src/lua', ROOT / 'tests/solar2d/consumer.lua',
        env=dict(os.environ, LUA_PATH=str(source / 'Solar2D/?.lua') + ';' + str(TOOLS / '?.lua'),
                 SDK_TEST_DATA=str(data)))
    if args.negative:
        negatives(unity, source)
    receipts = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in archives}
    (BUILD / 'package-sha256.json').write_text(json.dumps(receipts, indent=2) + '\n')
    print('SDK compilation, packaged consumer tests and package checks passed.', flush=True)
    print(json.dumps(receipts, indent=2), flush=True)


if __name__ == '__main__':
    main()
