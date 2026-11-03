"""Public binding/CAS/replay checks with explicitly simulated SDK observations.

The local native core remains real. This file never claims SDK or model evidence;
tests/sdk/test_properties_sdk.py exercises the real compiler/runtime separately.
"""
import asyncio
import importlib
import importlib.util
import json
import re

import pytest

from nexus.contracts import CandidateProposal,CheckResult,file_hash,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.store import RunStore,uid
from tests.test_property_uploads import prepared
from tests.test_property_contract import raw


def setup(tmp_path,*,reserved=None):
    uploads,draft,args=prepared(tmp_path);value=raw()
    if reserved is not None:value['excluded_inputs']=reserved
    uploads.confirm(draft['id'],**args,properties_json=json.dumps(value))
    root=uploads.source(draft['id'],actor_id='alice');store=uploads.store
    ws=WorkspaceStore(tmp_path,registered=[root]);baseline=ws.import_project(root,'.')
    requirements=RequirementService(store);d=requirements.prepare_requirement(draft['id'],'合法退款不得超过实付，非法申请保持旧累计')
    spec=requirements.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='alice')
    task=requirements.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/uploaded.cj')
    def candidate(code='refunded + requested + 0',public='PASS'):
        from nexus.adapters.cangjie.verifier import CangjieVerifier
        content=original.replace('return refunded + requested',code) if code.startswith('if ') else original.replace('refunded + requested',code)
        proposal=CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=content)],requirement_refs=['REQ-UPLOAD'])
        c=ws.apply_candidate(store.get_task(task.id),proposal)
        _,tree,plan=CangjieVerifier(tmp_path,task.id).identity(c.id)
        if public is not None:store.append_record(task.id,'check',CheckResult(id=uid(),subject_id=c.id,kind='test',state=public,tree_hash=tree,plan_hash=plan,diagnostics='EXPLICIT PUBLIC RESULT FIXTURE').model_dump())
        return c
    return store,ws,task,candidate


def api(store):
    assert importlib.util.find_spec('nexus.repair.property_service') is not None,'property search service missing'
    return importlib.import_module('nexus.repair.property_service').PropertyService(store)


def sdk(monkeypatch,*,good=False,unknown=False,cancel=False):
    module=importlib.import_module('nexus.repair.property_service');calls=[]
    async def run(project,argv,**kwargs):
        calls.append((project,kwargs))
        if cancel:raise asyncio.CancelledError
        text=(project/'src/property_observations_test.cj').read_text()
        token=re.search(r'class NexusProperties([0-9a-f]{16})',text)[1]
        inputs=[list(map(int,row.split(', '))) for row in re.findall(r'__nexusTarget'+token+r'\(([-0-9, ]+)\)',text)]
        log='EXPLICIT SDK LOG FIXTURE\nTP: uploaded, RESULT:\n TCS: NexusProperties'+token+', RESULT:\n'
        for i,(paid,refunded,requested) in enumerate(inputs):
            actual=refunded if good and requested>paid-refunded else refunded+requested
            log+=f' [ PASSED ] CASE: case{i} (1 ns)\n STDOUT:\n NEXUS_PROPERTY_V1|{token}|case{i}|Int64|{actual}\n'
        n=len(inputs);log+=f'Summary: TOTAL: {n} PASSED: {n}, SKIPPED: 0, ERROR: 0 FAILED: 0\ncjpm test success\n'
        kwargs['execution_argv'].extend([['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']])
        assert kwargs['test_output']=='all'
        return (None,log,'TimeoutError') if unknown else (0,log,None)
    monkeypatch.setattr(module,'run_command',run)
    return calls


def test_property_failure_has_real_return_and_replays_without_new_execution(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch);c=apply()
    before=source_manifest(ws.subject_path(c.id));report=asyncio.run(engine.run(c.id))
    assert report['state']=='FAIL' and report['public_test_state']=='PASS'
    assert 1<=len(calls)<=3 and report['search_cases']<=32 and report['shrink_cases']<=64
    assert report['failures'][0]['kind']=='business_property' and report['failures'][0]['expected_property'] is True
    assert type(report['failures'][0]['actual_return']) is int
    assert report['failures'][0]['assertion_value'] is False
    assert 'expected' not in report['failures'][0]
    assert engine.verify(c.id)==report and asyncio.run(engine.run(c.id))==report
    assert source_manifest(ws.subject_path(c.id))==before
    assert all(b['required_ids'] for b in report['batches'])
    assert all(b['result']['execution_state']=='PASS' for b in report['batches'])


def test_next_candidate_regresses_only_earlier_verified_counterexamples(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch);first=apply()
    failed=asyncio.run(engine.run(first.id));sdk(monkeypatch,good=True)
    second=apply('if (requested > paid - refunded) { return refunded }\n return refunded + requested')
    passed=asyncio.run(engine.run(second.id))
    assert passed['state']=='PASS' and passed['regression_cases']>0
    assert {tuple(f['args']) for f in failed['failures']}<={tuple(o['args']) for o in passed['batches'][0]['result']['observations']}
    # Replaying attempt1 must not incorporate future attempt2 facts.
    assert engine.verify(first.id)==failed


@pytest.mark.parametrize('change',['log','harness','source','scope','argv','batch-result','binding','failures','native'])
def test_changed_evidence_cannot_replay_as_bound_result(tmp_path,monkeypatch,change):
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch,good=True);c=apply()
    report=asyncio.run(engine.run(c.id));batch=report['batches'][0]
    if change in ('log','harness'):(store.root/batch[change+'_ref']).write_text('forged')
    elif change=='source':(store.root/batch['project_path']/'src/uploaded.cj').write_text('forged')
    else:
        if change=='scope':batch['required_ids']=[]
        elif change=='argv':batch['execution_argv']=[['cjpm','test']]
        elif change=='batch-result':batch['result']['state']='FAIL'
        elif change=='binding':report['binding']['tree_hash']='0'*64
        elif change=='failures':report['failures']=[dict(args=[999,899,199],actual_return=999)]
        else:report['native_boundary']['response']['data']['axes'][0]=[]
        ref,identity=engine.write_record(report,'.properties.json')
        with store.connect() as db:db.execute('UPDATE property_runs SET report_ref=?,report_sha256=? WHERE candidate_id=?',(ref,identity,c.id))
    with pytest.raises(ValueError):engine.verify(c.id)


def test_unknown_or_cancelled_search_cannot_pass_and_never_reexecutes(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch,unknown=True);c=apply()
    report=asyncio.run(engine.run(c.id));assert report['state']=='UNKNOWN' and len(calls)==1
    assert asyncio.run(engine.run(c.id))==report and len(calls)==1
    store,ws,task,apply=setup(tmp_path/'cancel');engine=api(store)
    second=apply();calls=sdk(monkeypatch,cancel=True)
    with pytest.raises(asyncio.CancelledError):asyncio.run(engine.run(second.id))
    assert engine.verify(second.id)['state']=='UNKNOWN' and len(calls)==1
    assert asyncio.run(engine.run(second.id))['state']=='UNKNOWN' and len(calls)==1


def test_started_cas_and_public_failure_do_not_execute(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch);c=apply(public='FAIL')
    assert asyncio.run(engine.run(c.id))['state']=='UNKNOWN' and calls==[]
    second=apply('refunded + requested + 00')
    with store.connect() as db:db.execute('INSERT INTO property_runs VALUES (?,?,?,NULL,NULL)',(second.id,task.id,'STARTED'))
    with pytest.raises(ValueError):engine.verify(second.id)
    assert asyncio.run(engine.run(second.id))['state']=='UNKNOWN' and calls==[]


def test_reserved_inputs_absent_in_search_shrink_and_replay(tmp_path,monkeypatch):
    reserved=[[900,900,200],[999,899,199]]
    store,ws,task,apply=setup(tmp_path,reserved=reserved);engine=api(store);sdk(monkeypatch);c=apply()
    report=asyncio.run(engine.run(c.id));assert report['state']=='FAIL'
    assert not {tuple(x) for x in reserved}&{tuple(a) for b in report['batches'] for a in b['inputs']}
    assert engine.verify(c.id)==report


def test_prior_unknown_blocks_new_execution_but_remains_a_readable_unknown(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch,unknown=True)
    first=apply();assert asyncio.run(engine.run(first.id))['state']=='UNKNOWN'
    calls=sdk(monkeypatch,good=True);second=apply('refunded + requested + 00')
    report=asyncio.run(engine.run(second.id))
    assert report['state']=='UNKNOWN' and calls==[] and engine.verify(second.id)==report


def test_concurrent_requests_claim_one_search(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch,good=True);c=apply()
    module=importlib.import_module('nexus.repair.property_service');original=module.run_command
    async def exercise():
        started=asyncio.Event();release=asyncio.Event()
        async def paused(*args,**kwargs):
            started.set();await release.wait();return await original(*args,**kwargs)
        monkeypatch.setattr(module,'run_command',paused)
        first=asyncio.create_task(engine.run(c.id));await started.wait()
        second=await engine.run(c.id);assert second['state']=='UNKNOWN'
        release.set();return await first
    assert asyncio.run(exercise())['state']=='PASS' and len(calls)==1


def test_changed_shared_observer_source_invalidates_saved_property_report(tmp_path,monkeypatch):
    from pathlib import Path
    from nexus.repair import primitive_trace
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch,good=True);c=apply()
    assert asyncio.run(engine.run(c.id))['state']=='PASS'
    changed=tmp_path/'changed-observer'/Path(primitive_trace.__file__).name
    changed.parent.mkdir();changed.write_bytes(Path(primitive_trace.__file__).read_bytes()+b'\n# EXPLICIT SOURCE IDENTITY FIXTURE\n')
    monkeypatch.setattr(primitive_trace,'__file__',str(changed))
    with pytest.raises(ValueError):engine.verify(c.id)
