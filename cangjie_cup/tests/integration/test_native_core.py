"""Execute the real pinned Cangjie component, not a policy fixture."""
import asyncio
import importlib
import importlib.util
from pathlib import Path
import time

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOW = -(2**63)
HIGH = 2**63 - 1


def client(root=ROOT):
    assert importlib.util.find_spec('nexus.policy.core') is not None, 'native core IPC is missing'
    return importlib.import_module('nexus.policy.core').NativeCoreClient(root)


def domains(*items):
    return {'domains': list(items)}


def integer(name='x', lo=-2, hi=3, points=None):
    return {'name': name, 'type': 'Int64', 'domain': {'min': lo, 'max': hi, 'points': [1] if points is None else points}}


def test_native_axes_have_stable_boundary_order_and_boolean_types():
    core = client()
    payload = domains(integer(), {'name': 'enabled', 'type': 'Bool', 'domain': {}})
    proof = asyncio.run(core.call('boundary.axes', payload))
    assert proof['response']['data'] == {'axes': [[0, -2, 3, 1, 2, -1], [False, True]]}
    assert all(type(x) is bool for x in proof['response']['data']['axes'][1])
    assert core.verify_proof(proof, 'boundary.axes', payload) == proof['response']['data']


def test_native_empty_axes_preserve_supported_zero_parameter_functions():
    proof=asyncio.run(client().call('boundary.axes',domains()))
    assert proof['response']['data']=={'axes':[]}


@pytest.mark.parametrize('lo,hi,points,want', [
    (LOW, LOW + 2, [LOW], [LOW + 2, LOW, LOW + 1]),
    (HIGH - 2, HIGH, [HIGH], [HIGH - 2, HIGH, HIGH - 1]),
    (LOW, HIGH, [LOW, HIGH], [0, LOW, HIGH, LOW + 1, HIGH - 1, -1, 1]),
    (5, 5, [5, 5], [5]),
])
def test_native_extremes_do_not_wrap_or_duplicate(lo, hi, points, want):
    result = asyncio.run(client().call('boundary.axes', domains(integer(lo=lo, hi=hi, points=points))))
    assert result['response']['data']['axes'] == [want]


@pytest.mark.parametrize('payload', [
    domains(integer(lo=3, hi=2)), domains(integer(points=[4])),
    domains(integer(lo=True)), domains(integer(points=[False])),
    domains(integer(points=[0] * 9)), domains(integer(), integer()),
    domains({'name': 'b', 'type': 'Bool', 'domain': {'min': 0}}),
    domains({'name': 'x', 'type': 'String', 'domain': {}}),
    {'domains': [integer()], 'extra': True}, domains(*[integer(str(i)) for i in range(17)]),
])
def test_native_rejects_malformed_domains(payload):
    with pytest.raises(ValueError):
        asyncio.run(client().call('boundary.axes', payload))


def test_missing_component_and_expired_request_do_not_fallback(tmp_path):
    core = client(tmp_path)
    with pytest.raises(ValueError):
        asyncio.run(core.call('boundary.axes', domains(integer())))
    with pytest.raises(ValueError):
        asyncio.run(client().call('boundary.axes', domains(integer()), deadline_at=1))


def test_spawn_runtime_failure_is_a_bounded_denial_without_action(monkeypatch):
    from nexus.policy.core import NativePolicyClient
    from nexus.policy.context import policy_context
    from nexus.policy.gate import gate_and_execute
    from nexus.contracts import TaskRecord,ToolResult
    task=TaskRecord(id='task',baseline_id='baseline',goal='native startup fault',allowed_paths=['src/a.cj'])
    request=policy_context(task,action='candidate.apply',request_id='spawn-fault',arguments_hash='b'*64,
        input_tree_hash='a'*64,deadline_at=int(time.time()*1000)+30000,paths=['src/a.cj'])
    async def cannot_spawn(*args,**kwargs):raise RuntimeError('SYNTHETIC_STARTUP_SECRET')
    monkeypatch.setattr('nexus.policy.core.asyncio.create_subprocess_exec',cannot_spawn)
    async def action():raise AssertionError('unavailable native process executed action')
    result=asyncio.run(gate_and_execute(request,action,policy=NativePolicyClient(ROOT)))
    assert result.operation_status=='ERROR' and result.error=='CORE_POLICY_UNAVAILABLE'
    assert 'SYNTHETIC_STARTUP_SECRET' not in str(result)


def test_native_proof_rejects_response_and_request_binding_changes():
    import copy
    core = client(); payload = domains(integer())
    proof = asyncio.run(core.call('boundary.axes', payload))
    for side, field, bad in [('response', 'payload_hash', 'f' * 64),
                             ('response', 'request_id', 'other'),
                             ('response', 'core_version', '1.0'),
                             ('request', 'payload', domains(integer(lo=-3))),
                             ('component', 'core_component_hash', '0' * 64)]:
        changed = copy.deepcopy(proof); changed[side][field] = bad
        with pytest.raises(ValueError):
            core.verify_proof(changed, 'boundary.axes', payload)


@pytest.mark.parametrize('body', [
    'echo invalid',
    'cat >/dev/null; exit 2',
    'cat >/dev/null; /bin/sleep 5',
    "cat >/dev/null; /usr/bin/yes x | /usr/bin/head -c 70000",
])
def test_bad_or_hanging_process_cannot_supply_native_evidence(tmp_path, monkeypatch, body):
    core = client(tmp_path)
    runtime = tmp_path / '.runtime'; runtime.mkdir()
    binary = runtime / 'core'; binary.write_text('#!/bin/sh\n' + body + '\n'); binary.chmod(0o700)
    monkeypatch.setattr(core, 'component_identity', lambda: {'core_component_hash': 'a' * 64, 'core_source_hash': 'b' * 64, 'core_compiler_hash': 'c' * 64})
    started = time.monotonic()
    with pytest.raises(ValueError):
        asyncio.run(core.call('boundary.axes', domains(integer())))
    assert time.monotonic() - started < 3.5


@pytest.mark.parametrize('mutation', [
    "r['request_id']='other'", "r['payload_hash']='f'*64", "r['schema_version']=True",
    "r['operation']='other'", "r['core_version']='old'", "r['extra']=0",
    "print(json.dumps(r))",  # A second response is never accepted.
])
def test_ipc_fixture_wrong_binding_or_second_response_is_rejected(tmp_path,monkeypatch,mutation):
    import sys
    core=client(tmp_path);runtime=tmp_path/'.runtime';runtime.mkdir()
    binary=runtime/'core'
    binary.write_text('#!'+sys.executable+'\nimport sys,json\np=json.loads(sys.stdin.readline())\n'
        "r={k:p[k] for k in ('schema_version','core_version','operation','request_id','payload_hash')}\n"
        "r.update(status='OK',reason='COMPLETED',data={'axes':[[0]]})\n"+mutation+'\nprint(json.dumps(r))\n')
    binary.chmod(0o700)
    monkeypatch.setattr(core,'component_identity',lambda:{'core_component_hash':'a'*64,'core_source_hash':'b'*64,'core_compiler_hash':'c'*64})
    with pytest.raises(ValueError):asyncio.run(core.call('boundary.axes',domains(integer())))


def test_source_set_or_build_record_changes_make_component_unavailable(tmp_path):
    import shutil
    for relative in ('cangjie/core/src/main.cj','.runtime/core','.runtime/core-build.json','.runtime/sdk/cangjie/bin/cjc'):
        dest=tmp_path/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        # Avoid copying the 110MiB compiler: its regular hard link is read-only here.
        if relative.endswith('/cjc'):dest.hardlink_to(ROOT/relative)
        else:shutil.copyfile(ROOT/relative,dest)
    core=client(tmp_path)
    assert core.component_identity()==client().component_identity()
    extra=tmp_path/'cangjie/core/src/extra.cj';extra.write_text('package cangsightcore')
    with pytest.raises(ValueError):core.component_identity()
    extra.unlink()
    source=tmp_path/'cangjie/core/src/main.cj';source.write_text(source.read_text()+'\n// changed\n')
    with pytest.raises(ValueError):core.component_identity()
