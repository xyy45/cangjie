"""Real pinned SDK observations; no live model or remote analysis requests."""
import asyncio
from pathlib import Path

import pytest

from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.contracts import source_manifest
from nexus.execution.runner import run_command
from nexus.repair import properties,property_trace,oracle
from tests.test_property_contract import raw,SIG,EXAMPLES

pytestmark=pytest.mark.sdk
TOKEN='0123456789abcdef'


def execute(root,contract,cases,source):
    project=root/'project';(project/'src').mkdir(parents=True)
    (project/'cjpm.toml').write_bytes(CONFIG);(project/'cjpm.lock').write_bytes(LOCK)
    (project/'src/logic.cj').write_text('package bench\n'+source)
    (project/'src/property_observations_test.cj').write_bytes(property_trace.harness(contract,cases,'bench',TOKEN))
    before=source_manifest(project);commands=[]
    code,log,problem=asyncio.run(run_command(project,['cjpm','test'],private_root=root,timeout=60,test_output='all',execution_argv=commands))
    (root/'sdk.log').write_text(log)
    assert source_manifest(project)==before
    result=property_trace.interpret(contract,cases,TOKEN,log,code,problem)
    assert result['execution_state']=='PASS',(code,problem,log[-3000:])
    assert commands[-1]==['cjpm','test','--skip-build','--show-all-output']
    assert len(result['observations'])==len(cases)
    return result


def test_sdk_observation_completes_but_business_property_fails_then_reference_passes(tmp_path):
    contract=properties.validate_contract(raw(),SIG,EXAMPLES)
    cases=oracle.generate_inputs(properties.sampler(contract))
    bad='public func refundState(paid: Int64, refunded: Int64, requested: Int64): Int64 { return refunded + requested }\n'
    good='public func refundState(paid: Int64, refunded: Int64, requested: Int64): Int64 {\n if (requested > paid - refunded) { return refunded }\n return refunded + requested\n}\n'
    failed=execute(tmp_path/'baseline',contract,cases,bad)
    assert failed['state']=='FAIL' and failed['failures']
    assert any(f['actual_return']>f['args'][0] for f in failed['failures'])
    passed=execute(tmp_path/'reference',contract,cases,good)
    assert passed['state']=='PASS'
    assert all(p['observed']>0 and p['failed']==0 for p in passed['per_property'])


@pytest.mark.parametrize('kind',['Bool','Int64-min','128-cases'])
def test_sdk_primitive_observation_types_extremes_and_case_budget(tmp_path,kind):
    if kind=='Bool':
        signature=dict(name='identity',params=[dict(name='x',type='Bool')],return_type='Bool');domains={'x':{}}
    else:
        signature=dict(name='identity',params=[dict(name='x',type='Int64')],return_type='Int64')
        domains={'x':dict(min=oracle.LOW,max=oracle.LOW+1)} if kind=='Int64-min' else {'x':dict(min=0,max=1000000)}
    value=dict(version=1,kind='single',function='identity',domains=domains,properties=[
        dict(id='PROP-IDENTITY',text='保持原值',precondition='True',assertion='result == arg0')],seed=0,max_cases=128,excluded_inputs=[])
    contract=properties.validate_contract(value,signature,[]);cases=oracle.generate_inputs(properties.sampler(contract))
    primitive=signature['return_type'];source='public func identity(x: '+primitive+'): '+primitive+' { return x }\n'
    result=execute(tmp_path,contract,cases,source)
    assert result['state']=='PASS'
    assert [o['actual_return'] for o in result['observations']]==[a[0] for a in cases]
    if kind=='128-cases':assert len(cases)==128


def test_sdk_user_function_named_println_does_not_shadow_observer_output(tmp_path):
    signature=dict(name='println',params=[dict(name='x',type='Int64')],return_type='Int64')
    value=dict(version=1,kind='single',function='println',domains={'x':dict(min=0,max=2)},properties=[
        dict(id='PROP-SAME',text='保持输入',precondition='True',assertion='result == arg0')],seed=0,max_cases=16,excluded_inputs=[])
    contract=properties.validate_contract(value,signature,[]);cases=oracle.generate_inputs(properties.sampler(contract))
    result=execute(tmp_path,contract,cases,'public func println(x: Int64): Int64 { return x }\n')
    assert result['state']=='PASS'


def test_sdk_zero_argument_property_observes_once(tmp_path):
    signature=dict(name='constant',params=[],return_type='Int64')
    value=dict(version=1,kind='single',function='constant',domains={},properties=[
        dict(id='PROP-CONSTANT',text='固定返回3',precondition='True',assertion='result == 3')],seed=0,max_cases=16,excluded_inputs=[])
    contract=properties.validate_contract(value,signature,[])
    assert execute(tmp_path,contract,[[]],'public func constant(): Int64 { return 3 }\n')['state']=='PASS'


def test_sdk_service_public_pass_property_fail_then_new_candidate_regression_pass(tmp_path):
    from tests.test_property_service import setup
    from nexus.adapters.cangjie.verifier import CangjieVerifier
    from nexus.repair.property_service import PropertyService
    store,ws,task,apply=setup(tmp_path);engine=PropertyService(store)
    verifier=CangjieVerifier(tmp_path,task.id);first=apply(public=None)
    assert asyncio.run(verifier.build(first.id)).state=='PASS'
    assert asyncio.run(verifier.test(first.id)).state=='PASS'
    before=source_manifest(ws.subject_path(first.id))
    failed=asyncio.run(engine.run(first.id))
    assert failed['state']=='FAIL' and failed['public_test_state']=='PASS'
    assert all(b['result']['execution_state']=='PASS' for b in failed['batches'])
    assert failed['failures'][0]['actual_return']>failed['failures'][0]['args'][0]
    assert source_manifest(ws.subject_path(first.id))==before
    second=apply('if (requested > paid - refunded) { return refunded }\n return refunded + requested',public=None)
    assert asyncio.run(verifier.build(second.id)).state=='PASS'
    assert asyncio.run(verifier.test(second.id)).state=='PASS'
    passed=asyncio.run(engine.run(second.id))
    assert passed['state']=='PASS' and passed['regression_cases']>0
    assert engine.verify(first.id)==failed and engine.verify(second.id)==passed
    for report in (failed,passed):
        assert report['native_boundary']['component']==report['binding']['native_core']
        for batch in report['batches']:
            actual=(store.root/batch['log_ref']).read_text()
            assert 'NEXUS_EXECUTION_PHASE' in actual and 'NEXUS_PROPERTY_V1|' in actual
            assert 'FIXTURE' not in actual


def test_sdk_threshold_counterexample_is_really_shrunk_and_remains_applicable(tmp_path):
    import json
    from nexus.uploads.service import UploadService
    from nexus.store import RunStore
    from nexus.execution.workspace import WorkspaceStore
    from nexus.requirements.service import RequirementService
    from nexus.contracts import CandidateProposal,file_hash
    from nexus.adapters.cangjie.verifier import CangjieVerifier
    from nexus.repair.property_service import PropertyService
    store=RunStore(tmp_path);uploads=UploadService(store)
    draft=uploads.prepare('fee.cj',b'public func fee(x: Int64): Int64 {\n if (x >= 37) { return -1 }\n return x\n}\n','非负输入的费用不得为负',actor_id='alice',request_key='threshold')
    value=dict(version=1,kind='single',function='fee',domains={'x':dict(min=0,max=1000)},properties=[
        dict(id='PROP-NONNEGATIVE',text='非负费用',precondition='arg0 >= 0',assertion='result >= 0')],seed=0,max_cases=16,excluded_inputs=[])
    examples=[dict(args=[0],expected=0,suite='target'),dict(args=[1],expected=1,suite='regression')]
    uploads.confirm(draft['id'],actor_id='alice',expected_version=1,function='fee',examples_json=json.dumps(examples),properties_json=json.dumps(value),consent=True)
    root=uploads.source(draft['id'],actor_id='alice');ws=WorkspaceStore(tmp_path,registered=[root]);base=ws.import_project(root,'.')
    req=RequirementService(store);rd=req.prepare_requirement(draft['id'],draft['goal'])
    spec=req.confirm_requirement(rd['id'],dict(schema_version=1,expected_version=1,requirements=rd['requirements'],allowed_paths=rd['allowed_paths']),actor_id='alice')
    task=req.prepare_task(draft['id'],spec.id,base)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(base,'src/uploaded.cj')
    candidate=ws.apply_candidate(task,CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original+'\n// candidate\n')],requirement_refs=['REQ-UPLOAD']))
    verifier=CangjieVerifier(tmp_path,task.id)
    assert asyncio.run(verifier.build(candidate.id)).state=='PASS'
    assert asyncio.run(verifier.test(candidate.id)).state=='PASS'
    engine=PropertyService(store);report=asyncio.run(engine.run(candidate.id))
    assert report['state']=='FAIL' and report['shrink_cases']>0 and len(report['batches'])==3
    initial=min(f['args'][0] for f in report['batches'][0]['result']['failures'])
    assert initial==41 and 37<=report['failures'][0]['args'][0]<initial
    assert report['failures'][0]['actual_return']==-1 and engine.verify(candidate.id)==report
