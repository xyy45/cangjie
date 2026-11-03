"""Executable installation checks: no model calls or ambient path dependency."""
import copy
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from nexus.deployment import checks


@pytest.fixture
def prepared(monkeypatch, tmp_path):
    root = tmp_path / 'project'
    (root / '.runtime/stdx/darwin_aarch64_cjnative/static/stdx').mkdir(parents=True)
    (root / 'requirements.lock').write_text('Flask==3.1.3\n')
    mac = tmp_path / 'MacOSX15.4.sdk'
    mac.mkdir()
    environment = dict(python=dict(version='3.12.4', path='/private/python'),
        platform=dict(system='Darwin', machine='arm64'),
        sdk=dict(state='available', tools={
            'cjc':dict(state='available', path='/private/cjc', version='Cangjie Compiler: 1.0.5 (cjnative)\nTarget: aarch64-apple-darwin'),
            'cjpm':dict(state='available', path='/private/cjpm', version='Cangjie Package Manager: 1.0.5')}),
        core=dict(state='available', version='2.0', component=dict(core_source_hash='a'*64,
            core_component_hash='b'*64, core_compiler_hash='c'*64)),
        model_connectivity='NOT_PROBED', model_config=dict(api_key_present=True,
            base_url_present=True, model_present=True))
    monkeypatch.setattr(checks, 'ROOT', root)
    monkeypatch.setattr(checks, 'LOCK_COUNT', 1)
    monkeypatch.setattr(checks, 'MACOS_SDK', mac)
    monkeypatch.setattr(checks, 'inspect_environment', lambda: copy.deepcopy(environment))
    monkeypatch.setattr(checks.metadata, 'version', lambda name: '3.1.3')
    return root, environment


@pytest.fixture
def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    return port


def item(report, code):
    return next(row for row in report['checks'] if row['code'] == code)


def test_ready_check_preserves_old_environment_interface_and_no_private_paths(prepared, free_port):
    report = checks.inspect(provider='deepseek', port=free_port)
    assert report['schema_version'] == 1 and report['ready'] is True
    assert all(row['state'] == 'PASS' for row in report['checks'])
    assert report['model_connectivity'] == 'NOT_PROBED'
    assert set(prepared[1]) == {'python','platform','sdk','core','model_connectivity','model_config'}
    assert '/private/' not in json.dumps(report)


@pytest.mark.parametrize('version', ['2.12.5', None])
def test_exact_dependency_mismatch_or_missing_is_not_ready(prepared, free_port, monkeypatch, version):
    def installed(name):
        if version is None:
            raise checks.metadata.PackageNotFoundError(name)
        return version
    monkeypatch.setattr(checks.metadata, 'version', installed)
    report = checks.inspect(provider='rule', port=free_port)
    assert not report['ready'] and item(report, 'DEPENDENCIES')['state'] == 'FAIL'
    assert item(report, 'DEPENDENCIES')['details']['mismatches'][0]['expected'] == '3.1.3'


@pytest.mark.parametrize('lock', ['Flask>=3.1\n', 'Flask==3.1.3\nflask==3.1.3\n', ''])
def test_bad_lock_is_bounded_failure(prepared, free_port, lock):
    (prepared[0] / 'requirements.lock').write_text(lock)
    report = checks.inspect(provider='rule', port=free_port)
    assert not report['ready'] and item(report, 'DEPENDENCIES')['state'] == 'FAIL'


def test_sdk_missing_and_tool_probe_failure_are_not_pass(prepared, free_port):
    tools = prepared[1]['sdk']['tools']
    tools['cjc'].update(state='unavailable', path=None, version=None)
    report = checks.inspect(provider='rule', port=free_port)
    assert item(report, 'SDK_TOOLCHAIN')['state'] == 'FAIL'
    tools['cjc'].update(path='/private/cjc')
    report = checks.inspect(provider='rule', port=free_port)
    assert item(report, 'SDK_TOOLCHAIN')['state'] == 'UNKNOWN' and not report['ready']


@pytest.mark.parametrize('field', ['sdk_version','core','macos_sdk','stdx','python','platform'])
def test_each_required_runtime_condition_fails_closed(prepared, free_port, field):
    root, environment = prepared
    if field == 'sdk_version': environment['sdk']['tools']['cjpm']['version'] = 'Cangjie Package Manager: 0.1.0'
    elif field == 'core': environment['core']['state'] = 'unavailable'
    elif field == 'macos_sdk': checks.MACOS_SDK.rmdir()
    elif field == 'stdx': (root / '.runtime/stdx/darwin_aarch64_cjnative/static/stdx').rmdir()
    elif field == 'python': environment['python']['version'] = '3.11.9'
    else: environment['platform']['machine'] = 'x86_64'
    report = checks.inspect(provider='rule', port=free_port)
    assert not report['ready']


def test_config_is_presence_only_and_rule_mode_needs_no_model(prepared, free_port):
    prepared[1]['model_config'] = dict(api_key_present=False, base_url_present=False, model_present=False)
    assert not checks.inspect(provider='deepseek', port=free_port)['ready']
    assert checks.inspect(provider='rule', port=free_port)['ready']
    prepared[1]['sdk']['tools']['cjc']['version'] = 'SECRET_VERSION_DO_NOT_ECHO'
    prepared[1]['model_config']['api_key_present'] = 'SECRET_CONFIG_DO_NOT_ECHO'
    assert 'SECRET_' not in json.dumps(checks.inspect(provider='deepseek', port=free_port))


def test_occupied_real_port_and_release(prepared):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        sock.listen()
        port = sock.getsockname()[1]
        report = checks.inspect(provider='rule', port=port)
        assert item(report, 'PORT')['state'] == 'FAIL' and not report['ready']
    assert checks.inspect(provider='rule', port=port)['ready']


@pytest.mark.parametrize('provider,port', [('other',8877),('rule',0),('rule',65536),('rule',True)])
def test_invalid_arguments_rejected(prepared, provider, port):
    with pytest.raises(ValueError): checks.inspect(provider=provider, port=port)


def test_probe_exception_does_not_echo_details(prepared, free_port, monkeypatch):
    def broken(): raise OSError('SECRET_PRIVATE_PATH_OR_CONFIGURATION')
    monkeypatch.setattr(checks, 'inspect_environment', broken)
    report = checks.inspect(provider='rule', port=free_port)
    assert not report['ready'] and item(report, 'ENVIRONMENT_PROBE')['state'] == 'UNKNOWN'
    assert 'SECRET_' not in json.dumps(report)


def cli(*args):
    root = Path(__file__).resolve().parents[1]
    environment = {key:value for key,value in os.environ.items()
                   if key != 'PYTHONPATH' and not key.startswith(('DEEPSEEK_','OPENAI_','ANTHROPIC_'))}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    return subprocess.run([sys.executable, '-B', *args], cwd=root, env=environment,
                          capture_output=True, text=True, timeout=30)


def test_real_direct_and_module_cli_have_matching_exit_semantics_without_pythonpath(free_port):
    direct = cli('scripts/doctor.py', '--provider','rule','--port',str(free_port))
    module = cli('-m','scripts.doctor','--provider','rule','--port',str(free_port))
    assert direct.returncode == module.returncode == 0, (direct.stdout,direct.stderr,module.stdout,module.stderr)
    assert json.loads(direct.stdout) == json.loads(module.stdout)
    # A developer checkout may contain an authorized .env. Isolate that input
    # in this child only; never rename or modify the real configuration.
    missing = cli('-c',
        'import dotenv,runpy,sys; dotenv.dotenv_values=lambda *a,**k:{}; '
        'sys.argv=["scripts.doctor","--provider","deepseek","--port",sys.argv[1]]; '
        'runpy.run_module("scripts.doctor",run_name="__main__")', str(free_port))
    assert missing.returncode == 1 and not json.loads(missing.stdout)['ready']
    invalid = cli('-m','scripts.doctor','--port','0')
    assert invalid.returncode == 2


def test_real_cli_occupied_port_exits_nonzero():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        sock.listen()
        result = cli('-m','scripts.doctor','--provider','rule','--port',str(sock.getsockname()[1]))
    assert result.returncode == 1
    assert item(json.loads(result.stdout), 'PORT')['state'] == 'FAIL'
