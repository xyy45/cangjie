"""No API calls: execution identity must cover failures as well as candidates."""
import asyncio
import json

import pytest

from nexus.benchmark.corpus import build_corpus,load_corpus,encoded
from nexus.benchmark.runner import plan_runs,run_case,verify_run
from nexus.benchmark.report import summarize
from tests.test_benchmark_report import row


def test_plan_binds_actual_execution_identity_without_reading_private_config(tmp_path):
    from nexus.benchmark.identity import implementation_identity,implementation_hash
    identity=implementation_identity()
    assert identity['core']['core_component_hash']
    assert identity['source_hashes']['nexus/demo/deepseek.py']
    assert identity['source_hashes']['cang_sight_server/server.py']
    assert identity['dependencies']['httpx'] and identity['requirements_lock']
    assert not any('.env' in p for p in identity['source_hashes'])
    build_corpus(tmp_path/'data',count=30);corpus=load_corpus(tmp_path/'data')
    plan=plan_runs(corpus,['business_001'],['direct'],max_model_requests=3)
    assert plan['schema_version']==3 and plan['implementation_hash']==implementation_hash()
    assert plan['implementation_identity']==identity


def test_mixed_or_missing_execution_hashes_cannot_claim_live_comparison():
    rows=[{**row('a',m,True),'implementation_hash':'a'*64} for m in ('direct','mcp','cegis')]
    assert summarize(rows)['comparison_state']=='LIVE_COMPARABLE'
    rows[1]['implementation_hash']='b'*64
    assert summarize(rows)['comparison_state']=='INCOMPLETE_OR_MISMATCHED'
    rows[1]['implementation_hash']='a'*64;rows[0].pop('implementation_hash')
    assert summarize(rows)['comparison_state']=='INCOMPLETE_OR_MISMATCHED'


def test_failure_without_candidate_preserves_execution_binding_and_rejects_changed_code(tmp_path,monkeypatch):
    from nexus.benchmark import runner
    from nexus.benchmark.identity import implementation_hash
    from nexus.contracts import digest
    build_corpus(tmp_path/'data',count=30);corpus=load_corpus(tmp_path/'data');case=corpus['tasks'][0]
    class NoModel:
        def __init__(self,store,**kwargs):self.store=store
        async def run(self,task_id):self.store.update_task(task_id,status='BLOCKED')
    monkeypatch.setattr(runner,'RepairLoop',NoModel)
    output=tmp_path/'run';r=asyncio.run(run_case(corpus,case,'direct',output,origin='FIXTURE'))
    assert r['candidate_id'] is None and r['model_requests']==0 and not r['verified_repair']
    assert r['implementation_hash']==implementation_hash()
    started=json.loads((output/'STARTED.json').read_bytes())
    assert started['implementation_hash']==r['implementation_hash']
    assert verify_run(tmp_path/'data',output)['result_hash']==r['result_hash']
    changed={**r,'implementation_hash':'b'*64};changed['result_hash']=digest({k:v for k,v in changed.items() if k!='result_hash'})
    (output/'result.json').write_bytes(encoded(changed))
    with pytest.raises(ValueError,match='绑定|版本'):verify_run(tmp_path/'data',output)
    (output/'result.json').write_bytes(encoded(r))
    monkeypatch.setattr(runner,'implementation_hash',lambda:'b'*64)
    with pytest.raises(ValueError,match='版本'):verify_run(tmp_path/'data',output)


def test_run_rejects_execution_drift_before_creating_output_or_request(tmp_path):
    build_corpus(tmp_path/'data',count=30);corpus=load_corpus(tmp_path/'data')
    with pytest.raises(ValueError,match='版本'):
        asyncio.run(run_case(corpus,corpus['tasks'][0],'direct',tmp_path/'never',origin='FIXTURE',expected_implementation_hash='b'*64))
    assert not (tmp_path/'never').exists()


def test_nested_linked_package_is_rejected_instead_of_silently_omitting_execution(tmp_path,monkeypatch):
    from nexus.benchmark import identity
    root=tmp_path/'project'
    for package in ('nexus','cang_sight_server','scripts'):(root/package).mkdir(parents=True)
    for name in ('requirements.lock','scripts/doctor.py','scripts/build_core.py'):(root/name).write_text('')
    outside=tmp_path/'outside';outside.mkdir();(outside/'execute.py').write_text('value=1')
    (root/'nexus/linked_package').symlink_to(outside,target_is_directory=True)
    monkeypatch.setattr(identity,'PROJECT_ROOT',root)
    monkeypatch.setattr(identity,'toolchain_identity',lambda:{'fixture':'not SDK evidence'})
    monkeypatch.setattr(identity.NativeCoreClient,'component_identity',lambda self:{'fixture':'not native evidence'})
    with pytest.raises(ValueError,match='链接'):identity.implementation_identity()
