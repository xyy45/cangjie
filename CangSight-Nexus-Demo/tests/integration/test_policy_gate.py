import asyncio
import json
import time
import hashlib
import pytest
from pathlib import Path
from nexus.contracts import ToolResult, digest
from nexus.policy.client import PolicyClient
from nexus.policy.gate import gate_and_execute

ROOT = Path(__file__).resolve().parents[2]


def request(**changes):
    return dict(schema_version=1,policy_version='1.1',deadline_at=int(time.time()*1000)+30000,approval_binding='',action='candidate.apply', task_id='task', request_id='req', paths=['src/quantity.cj'],
                input_tree_hash='a'*64, arguments_hash='b'*64, remaining_budget=3,
                accepted=False, **changes)


def test_deny_never_calls_action():
    async def run():
        count = 0
        async def action():
            nonlocal count
            count += 1
            return ToolResult(operation_status='OK')
        r = request()
        r['paths'] = ['src/order_test.cj']
        result = await gate_and_execute(r, action, policy=PolicyClient(ROOT))
        assert result.operation_status == 'ERROR'
        assert count == 0
    asyncio.run(run())


def test_dead_policy_blocks_materialization(tmp_path):
    async def run():
        async def action():
            (tmp_path / 'bad').touch()
            return ToolResult(operation_status='OK')
        result = await gate_and_execute(request(), action, policy=PolicyClient(tmp_path))
        assert result.operation_status == 'ERROR'
        assert not (tmp_path / 'bad').exists()
    asyncio.run(run())


def test_native_allow_and_need_approval():
    async def run():
        policy = PolicyClient(ROOT)
        assert (await policy.decide(request()))['decision'] == 'Allow'
        r = request()
        r['action'] = 'candidate.export'
        assert (await policy.decide(r))['decision'] == 'NeedApproval'
    asyncio.run(run())


def test_changed_arguments_rejected():
    async def run():
        r = request()
        class ChangingPolicy:
            async def decide(self, data):
                data['remaining_budget'] = 0
                return {'decision': 'Allow'}
        async def action():
            raise AssertionError('changed request executed')
        result = await gate_and_execute(r, action, policy=ChangingPolicy())
        assert result.error == 'POLICY_ARGUMENTS_CHANGED'
    asyncio.run(run())


def test_invalid_json_and_timeout_deny(tmp_path,monkeypatch):
    attest_ipc_fixture(monkeypatch)
    async def run():
        runtime = tmp_path / '.runtime'
        runtime.mkdir()
        binary = runtime / 'policy'
        for body in ('echo invalid', '/bin/sleep 5'):
            binary.write_text('#!/bin/sh\n' + body + '\n')
            binary.chmod(0o700)
            assert (await PolicyClient(tmp_path).decide(request()))['decision'] == 'Deny'
    asyncio.run(run())


@pytest.mark.parametrize('field', ['request_id', 'arguments_hash','input_tree_hash','approval_binding','schema_version','policy_version'])
def test_response_binding_fields_rejected_independently(tmp_path, field,monkeypatch):
    attest_ipc_fixture(monkeypatch)
    runtime = tmp_path / '.runtime'
    runtime.mkdir()
    binary = runtime / 'policy'
    valid = {'schema_version':1,'policy_version':'1.1','input_tree_hash':'a'*64,'approval_binding':'',
             'decision': 'Allow', 'reason': 'TEST_IPC_RESPONSE',
             'request_id': 'req', 'arguments_hash': 'b'*64}
    async def run():
        def respond(data):
            binary.write_text("#!/bin/sh\necho '" + json.dumps(data) + "'\n")
            binary.chmod(0o700)
        # Correct counterpart fields are held fixed; the control must be accepted.
        respond(valid)
        assert (await PolicyClient(tmp_path).decide(request()))['decision'] == 'Allow'
        respond({**valid, field: 'wrong'})
        result = await PolicyClient(tmp_path).decide(request())
        assert result['decision']=='Deny' and result['reason']=='POLICY_UNAVAILABLE'
    asyncio.run(run())


def test_policy_message_limit_and_native_candidate_budget(tmp_path):
    async def run():
        oversized = {**request(), 'extra': 'x'*65536}
        result=await PolicyClient(tmp_path).decide(oversized)
        assert result['decision']=='Deny' and result['reason']=='MESSAGE_LIMIT'
        for budget in (0, 4):
            result = await PolicyClient(ROOT).decide({**request(), 'remaining_budget': budget})
            assert result['decision'] == 'Deny' and result['reason'] == 'BUDGET_EXHAUSTED'
    asyncio.run(run())


def attest_ipc_fixture(monkeypatch):
    def fixture_identity(client):
        return {'policy_component_hash':hashlib.sha256((client.root/'.runtime/policy').read_bytes()).hexdigest(),
                'policy_source_hash':'f'*64}
    monkeypatch.setattr(PolicyClient,'component_identity',fixture_identity)
