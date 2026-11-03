"""Actual stdio schema rejection and native policy version/identity checks."""
import asyncio
import json
import subprocess
import time
from pathlib import Path
import pytest
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from nexus.policy.client import PolicyClient
from nexus.adapters.cangjie.sdk import sdk_environment

ROOT=Path(__file__).resolve().parents[2]


def policy_request(**changes):
    return {**dict(schema_version=1,policy_version='1.1',action='candidate.apply',task_id='task',
        request_id='native-version-test',paths=['src/quantity.cj'],input_tree_hash='a'*64,
        arguments_hash='b'*64,remaining_budget=3,accepted=False,approval_binding='',
        deadline_at=int(time.time()*1000)+30000),**changes}


def test_real_stdio_explicit_versions_and_unknown_versions_rejected(tmp_path):
    fixture=ROOT/'fixtures/order-demo'
    baseline=WorkspaceStore(tmp_path,registered=[fixture]).import_project(fixture,'.')
    async def run():
        async with ToolClient(tmp_path) as client:
            good=await client.call_tool('workspace.read_file',dict(baseline_id=baseline,path='src/quantity.cj'))
            assert good.operation_status=='OK' and good.schema_version==1
            for changed in ({'schema_version':999},{'tool_version':'obsolete'},{'unexpected_permission':True}):
                bad=await client.call_tool('workspace.read_file',dict(baseline_id=baseline,path='src/quantity.cj',**changed))
                assert bad.operation_status=='ERROR'
            raw=await client.session.call_tool('workspace.read_file',dict(baseline_id=baseline,path='src/quantity.cj'))
            assert raw.isError or json.loads(raw.content[0].text)['operation_status']=='ERROR'
    asyncio.run(run())


def test_native_rejects_unknown_versions_and_extra_fields_independent_of_python():
    for changes in ({'schema_version':999},{'policy_version':'obsolete'},{'unexpected_permission':True}):
        result=subprocess.run([str(ROOT/'.runtime/policy')],input=json.dumps(policy_request(**changes))+'\n',
            text=True,capture_output=True,env=sdk_environment(),timeout=3)
        assert result.returncode==0
        decision=json.loads(result.stdout)
        assert decision['decision']=='Deny',decision


def test_policy_decision_binds_version_tree_approval_and_actual_component():
    request=policy_request()
    result=asyncio.run(PolicyClient(ROOT).decide(request))
    assert result['decision']=='Allow',result
    assert result['schema_version']==1 and result['policy_version']=='1.1'
    assert result['input_tree_hash']==request['input_tree_hash']
    assert result['approval_binding']==request['approval_binding']
    assert len(result['policy_component_hash'])==len(result['policy_source_hash'])==64


def test_expired_mcp_request_and_policy_request_are_denied(tmp_path):
    fixture=ROOT/'fixtures/order-demo'
    baseline=WorkspaceStore(tmp_path,registered=[fixture]).import_project(fixture,'.')
    async def run():
        async with ToolClient(tmp_path) as client:
            result=await client.call_tool('workspace.read_file',dict(baseline_id=baseline,
                path='src/quantity.cj',deadline_at=1))
            assert result.operation_status=='ERROR'
        assert (await PolicyClient(ROOT).decide(policy_request(deadline_at=1)))['decision']=='Deny'
    asyncio.run(run())


def test_mcp_wrong_tree_and_noninteger_versions_are_rejected(tmp_path):
    fixture=ROOT/'fixtures/order-demo'
    baseline=WorkspaceStore(tmp_path,registered=[fixture]).import_project(fixture,'.')
    async def run():
        async with ToolClient(tmp_path) as client:
            for extra in ({'input_tree_hash':'0'*64},{'schema_version':True},{'schema_version':1.0}):
                result=await client.call_tool('workspace.read_file',dict(baseline_id=baseline,
                    path='src/quantity.cj',**extra))
                assert result.operation_status=='ERROR'
    asyncio.run(run())


def test_stale_source_binary_or_build_record_blocks_before_process_spawn(tmp_path,monkeypatch):
    import shutil
    runtime=tmp_path/'.runtime';runtime.mkdir()
    (runtime/'sdk').symlink_to(ROOT/'.runtime/sdk',target_is_directory=True)
    source=tmp_path/'cangjie/policy/src/main.cj';source.parent.mkdir(parents=True)
    source.write_bytes((ROOT/'cangjie/policy/src/main.cj').read_bytes())
    binary=runtime/'policy';shutil.copyfile(ROOT/'.runtime/policy',binary);binary.chmod(0o700)
    metadata=runtime/'policy-build.json';metadata.write_bytes((ROOT/'.runtime/policy-build.json').read_bytes())
    client=PolicyClient(tmp_path)
    assert client.component_identity()==PolicyClient(ROOT).component_identity()
    originals={p:p.read_bytes() for p in (source,binary,metadata)}
    async def no_spawn(*args,**kwargs):
        raise AssertionError('Stale Policy must be blocked before process launch')
    monkeypatch.setattr('nexus.policy.client.asyncio.create_subprocess_exec',no_spawn)
    async def run():
        for changed in (source,binary,metadata):
            changed.write_bytes(originals[changed]+b'\nchanged')
            denied=await client.decide(policy_request())
            assert denied['decision']=='Deny' and denied['reason']=='POLICY_UNAVAILABLE'
            changed.write_bytes(originals[changed])
    asyncio.run(run())
