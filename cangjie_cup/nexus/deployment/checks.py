"""Read-only installation checks. Never probe a model or read workbench data."""
from importlib import metadata
import os
from pathlib import Path
import re
import socket
import stat

from scripts.doctor import inspect_environment
from nexus.adapters.cangjie.sdk import MACOS_SDK

ROOT = Path(__file__).resolve().parents[2]
LOCK_COUNT = 40
SAFE_VERSION = re.compile(r'[0-9][A-Za-z0-9.!+_-]{0,63}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')


def version(value):
    return value if type(value) is str and SAFE_VERSION.fullmatch(value) else None


def dependency_check():
    """Read only the fixed dependency list; never run pip or resolve online."""
    descriptor = None
    try:
        descriptor = os.open(ROOT / 'requirements.lock', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 0 < info.st_size <= 65536:
            raise ValueError('Invalid lock file')
        with os.fdopen(descriptor, 'rb') as stream:
            descriptor = None
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('Lock exceeds budget')
        entries = []
        names = set()
        for line in raw.decode('utf-8').splitlines():
            match = re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9_.-]{0,127})==([0-9][A-Za-z0-9.!+_-]{0,63})', line)
            if not match:
                raise ValueError('Expected exact lock entry')
            name, expected = match.groups()
            normalized = re.sub(r'[-_.]+', '-', name).lower()
            if normalized in names:
                raise ValueError('Duplicate distribution')
            names.add(normalized)
            entries.append((name, expected))
        if len(entries) != LOCK_COUNT:
            raise ValueError('Unexpected dependency count')
        mismatches = []
        for name, expected in entries:
            try:
                actual = version(metadata.version(name))
            except metadata.PackageNotFoundError:
                actual = None
            if actual != expected:
                mismatches.append(dict(distribution=name, expected=expected, actual=actual))
        return dict(code='DEPENDENCIES', state='FAIL' if mismatches else 'PASS',
                    details=dict(expected_distributions=len(entries), mismatches=mismatches),
                    repair_command='python -m pip install -r requirements.lock')
    except (OSError, ValueError, UnicodeError):
        return dict(code='DEPENDENCIES', state='FAIL', details=dict(reason='LOCK_UNAVAILABLE_OR_INVALID'),
                    repair_command='Restore the original requirements.lock from the verified application package')
    finally:
        if descriptor is not None:
            os.close(descriptor)


def inspect(*, provider='deepseek', port=8877):
    if provider not in ('deepseek', 'rule') or type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid provider or port')
    checks = []
    report = dict(schema_version=1, provider=provider, port=port,
                  target=dict(system='Darwin', machine='arm64', minimum_python='3.12',
                              tested_python='3.12.4', cangjie='1.0.5', stdx='1.0.5.1',
                              macos_developer_sdk='15.4'), checks=checks,
                  ready=False, model_connectivity='NOT_PROBED')

    def add(code, state, **details):
        checks.append(dict(code=code, state=state, details=details))

    try:
        environment = inspect_environment()
        add('ENVIRONMENT_PROBE', 'PASS')
    except (OSError, ValueError, ImportError, KeyError, TypeError):
        environment = {}
        add('ENVIRONMENT_PROBE', 'UNKNOWN', reason='LOCAL_PROBE_UNAVAILABLE')
    actual_python = version(environment.get('python', {}).get('version'))
    match = re.match(r'^(\d+)\.(\d+)\.', actual_python or '')
    supported_python = bool(match and tuple(map(int, match.groups())) >= (3, 12))
    add('PYTHON', 'PASS' if supported_python else 'FAIL', version=actual_python,
        tested_combination=actual_python == '3.12.4')
    platform = environment.get('platform', {})
    add('PLATFORM', 'PASS' if platform.get('system') == 'Darwin' and platform.get('machine') == 'arm64'
        else 'FAIL', target='macOS ARM64')
    checks.append(dependency_check())

    tools = environment.get('sdk', {}).get('tools', {})
    expected = {'cjc': r'Cangjie Compiler: 1\.0\.5 \(cjnative\)(?:\nTarget: aarch64-apple-darwin)?',
                'cjpm': r'Cangjie Package Manager: 1\.0\.5'}
    tool_state = 'PASS'
    for name, pattern in expected.items():
        value = tools.get(name, {})
        if not value.get('path'):
            tool_state = 'FAIL'
            break
        if value.get('state') != 'available' and not value.get('version'):
            tool_state = 'UNKNOWN'
        elif (value.get('state') != 'available' or type(value.get('version')) is not str or
              not re.fullmatch(pattern, value['version'].strip())):
            tool_state = 'FAIL'
            break
    add('SDK_TOOLCHAIN', tool_state, expected_version='1.0.5',
        repair_command='python scripts/install_runtime.py')
    add('MACOS_DEVELOPER_SDK', 'PASS' if MACOS_SDK.is_dir() else 'FAIL', expected_version='15.4')
    stdx = ROOT / '.runtime/stdx/darwin_aarch64_cjnative/static'
    add('STDX_LAYOUT', 'PASS' if stdx.is_dir() and (stdx / 'stdx').is_dir() else 'FAIL',
        expected_version='1.0.5.1', version_integrity='NOT_PROVEN_BY_LAYOUT',
        repair_command='python scripts/install_runtime.py')
    core = environment.get('core', {})
    component = core.get('component')
    valid_core = (core.get('state') == 'available' and core.get('version') == '2.0' and
                  type(component) is dict and
                  set(component) == {'core_source_hash','core_component_hash','core_compiler_hash'} and
                  all(type(v) is str and HASH.fullmatch(v) for v in component.values()))
    add('CORE', 'PASS' if valid_core else 'FAIL', component=component if valid_core else None,
        repair_command='python scripts/build_core.py')
    configured = environment.get('model_config', {})
    present = {key:configured.get(key) is True for key in
               ('api_key_present','base_url_present','model_present')}
    add('MODEL_CONFIGURATION', 'PASS' if provider == 'rule' or all(present.values()) else 'FAIL',
        required=provider == 'deepseek', present=present, connectivity='NOT_PROBED')
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(('127.0.0.1', port))
        add('PORT', 'PASS', host='127.0.0.1', reserved=False)
    except OSError:
        add('PORT', 'FAIL', host='127.0.0.1', reason='PORT_UNAVAILABLE', reserved=False)
    report['ready'] = all(check['state'] == 'PASS' for check in checks)
    return report
