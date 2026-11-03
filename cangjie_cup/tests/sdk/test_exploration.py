"""Real SDK and isolated test execution; model calls in later loop tests are fixtures."""
import asyncio,importlib.util,json,time
import pytest
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.contracts import CandidateProposal,file_hash,source_manifest
from nexus.adapters.cangjie.verifier import CangjieVerifier

pytestmark=pytest.mark.sdk


def setup(tmp_path):
    store=RunStore(tmp_path);u=UploadService(store)
    src=b'public func f(x: Int64): Int64 { x + 1 }\n'
    draft=u.prepare('f.cj',src,'返回输入值',actor_id='TEST_FIXTURE',request_key='one')
    oracle=dict(version=1,function='f',domains={'x':dict(min=0,max=8,points=[3])},expression='x',seed=7,max_cases=32)
    u.confirm(draft['id'],expected_version=1,function='f',examples_json=json.dumps([dict(args=[1],expected=1,suite='target'),dict(args=[2],expected=2,suite='regression')]),consent=True,actor_id='TEST_FIXTURE',oracle_json=json.dumps(oracle))
    project=u.source(draft['id'],actor_id='TEST_FIXTURE');ws=WorkspaceStore(tmp_path,registered=[project]);baseline=ws.import_project(project,'.')
    r=RequirementService(store);d=r.prepare_requirement(draft['id'],'返回输入值');s=r.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='TEST_FIXTURE')
    task=r.prepare_task(draft['id'],s.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/uploaded.cj')
    def candidate(code):
        return ws.apply_candidate(store.get_task(task.id),CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original.replace('x + 1',code))],requirement_refs=['REQ-UPLOAD']))
    return store,ws,task,candidate


def exploration(store):
    assert importlib.util.find_spec('nexus.repair.exploration') is not None,'independent exploration runner missing'
    from nexus.repair.exploration import ExplorationService
    return ExplorationService(store)


def test_public_pass_is_not_enough_real_counterexample_shrinks_and_next_candidate_passes(tmp_path):
    store,ws,task,apply=setup(tmp_path);engine=exploration(store)
    first=apply('if (x <= 2) { x } else { 0 }')
    verifier=CangjieVerifier(tmp_path,task.id)
    assert asyncio.run(verifier.build(first.id)).state=='PASS'
    assert asyncio.run(verifier.test(first.id)).state=='PASS'
    before=source_manifest(ws.subject_path(first.id))
    report=asyncio.run(engine.run(first.id,deadline_at=int(time.time()*1000)+180000))
    assert report['state']=='FAIL' and report['public_test_state']=='PASS'
    assert report['failures'][0]['args']==[3] and report['failures'][0]['actual']=='0' and report['failures'][0]['expected']=='3'
    assert report['search_cases']>2 and report['shrink_cases']>0
    assert report['native_boundary']['response']['data']['axes']==[[0,8,3,2,4,1,7]]
    assert report['native_boundary']['component']==report['binding']['native_core']
    assert engine.verify(first.id)==report
    assert source_manifest(ws.subject_path(first.id))==before
    second=apply('x')
    assert asyncio.run(verifier.build(second.id)).state=='PASS'
    assert asyncio.run(verifier.test(second.id)).state=='PASS'
    fixed=asyncio.run(engine.run(second.id,deadline_at=int(time.time()*1000)+180000))
    assert fixed['state']=='PASS' and fixed['regression_cases']>=1
    assert engine.verify(second.id)==fixed
    # The cached run is evidence-bound and does not execute again.
    assert asyncio.run(engine.run(second.id))==fixed
    batch=fixed['batches'][0]
    original_log=(store.root/batch['log_ref']).read_bytes()
    (store.root/batch['log_ref']).write_text('forged')
    with pytest.raises(ValueError):engine.verify(second.id)
    (store.root/batch['log_ref']).write_bytes(original_log)
    assert 'project_path' in batch, 'probe project must be retained for integrity verification'
    (store.root/batch['project_path']/'src/uploaded.cj').write_text('forged')
    with pytest.raises(ValueError):engine.verify(second.id)


def test_expired_exploration_is_unknown_and_cannot_be_accepted(tmp_path):
    store,ws,task,apply=setup(tmp_path);engine=exploration(store);c=apply('x')
    verifier=CangjieVerifier(tmp_path,task.id)
    assert asyncio.run(verifier.build(c.id)).state=='PASS'
    assert asyncio.run(verifier.test(c.id)).state=='PASS'
    report=asyncio.run(engine.run(c.id,deadline_at=1))
    assert report['state']=='UNKNOWN'
    from nexus.execution.delivery import DeliveryService
    with pytest.raises(ValueError):DeliveryService(store).check_set_hash(c.id)


@pytest.mark.parametrize('public_failure_first',[False,True])
def test_new_rule_counterexample_drives_second_model_round_and_bound_archive(tmp_path,monkeypatch,public_failure_first):
    import httpx,zipfile
    from nexus.demo.deepseek import DeepSeekProvider
    from nexus.repair.cegis_loop import RepairLoop
    from nexus.execution.delivery import DeliveryService
    store,ws,task,_=setup(tmp_path);captured=[]
    for k,v in dict(DEEPSEEK_API_KEY='fixture-only',DEEPSEEK_BASE_URL='https://fixture.invalid',DEEPSEEK_MODEL='test-model').items():monkeypatch.setenv(k,v)
    real=httpx.AsyncClient
    def reply(request):
        context=json.loads(json.loads(request.content)['messages'][1]['content']);captured.append(context)
        original=context['files']['src/uploaded.cj']['content']
        step=len(captured)-(1 if public_failure_first else 0)
        content=original.replace('x + 1','x + 2' if step==0 else 'if (x <= 2) { x } else { 0 }' if step==1 else 'x')
        payload=dict(schema_version=1,summary='fixture',suggestions=[dict(path='src/uploaded.cj',reason='fixture')],analysis_refs=[],proposal=dict(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=content)],requirement_refs=['REQ-UPLOAD']))
        return httpx.Response(200,json=dict(model='test-model',usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),choices=[dict(finish_reason='stop',message=dict(content=json.dumps(payload)))]))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(reply),**kw))
    result=asyncio.run(RepairLoop(store,provider_factory=DeepSeekProvider).run(task.id))
    assert result.status=='REVIEW_PENDING',store.records(task.id,'event')[-1]
    assert len(captured)==(3 if public_failure_first else 2), 'public PASS must not bypass independent exploration'
    assert captured[0]['diagnostics']['test'].get('diagnostics'), 'public baseline failure diagnostics must remain visible'
    if public_failure_first:
        assert captured[1]['feedback'][0]['failure_cases'][0]['kind']=='test'
        assert captured[1]['feedback'][0]['diagnostic_snippets'][0]['visibility']=='PUBLIC'
    feedback=captured[-1]['feedback'][-1]
    assert feedback['failure_cases'][0]['args']==[3] and feedback['failure_cases'][0]['kind']=='independent_rule'
    assert 'oracle_contract' not in captured[0] and 'verification/oracle.json' not in captured[0]['files']
    chosen=next(e['selected_candidate_id'] for e in store.records(task.id,'event') if 'selected_candidate_id' in e)
    delivery=DeliveryService(store);acceptance=delivery.accept(chosen,delivery.check_set_hash(chosen),actor_id='TEST_FIXTURE')
    exported=delivery.export(chosen,acceptance.id)
    with zipfile.ZipFile(tmp_path/exported['download_ref']) as z:
        evidence=json.loads(z.read('evidence/exploration.json'))
        assert evidence['state']=='PASS' and evidence['regression_cases']>=1
        assert evidence['native_boundary']['response']['status']=='OK'
        assert 'project/verification/oracle.json' in z.namelist()


def test_search_failures_exhaust_candidate_budget_without_review_or_delivery(tmp_path):
    from nexus.repair.cegis_loop import RepairLoop
    from nexus.execution.delivery import DeliveryService
    store,ws,task,_=setup(tmp_path);contexts=[]
    class Provider:
        async def propose(self,context):
            contexts.append(context)
            original=context['files']['src/uploaded.cj']['content']
            content=original.replace('x + 1','if (x <= 2) { x } else { x - '+str(len(contexts))+' }')
            return CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=content)],requirement_refs=['REQ-UPLOAD'])
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *args:Provider()).run(task.id))
    assert result.status=='UNREPAIRED' and result.attempt_count==3 and len(contexts)==3
    assert all(len(c['feedback'])==i for i,c in enumerate(contexts))
    events=store.records(task.id,'event')
    assert not any('selected_candidate_id' in e for e in events)
    assert events[-1]['stop_reason']=='Candidate budget exhausted'
    c=store.records(task.id,'candidate')[-1]
    with pytest.raises(ValueError):DeliveryService(store).check_set_hash(c['id'])
    assert not store.records(task.id,'acceptance')


def test_unavailable_native_boundary_is_unknown_without_probe_or_delivery(tmp_path,monkeypatch):
    from nexus.policy.core import NativeCoreClient
    store,ws,task,apply=setup(tmp_path);engine=exploration(store);c=apply('x')
    verifier=CangjieVerifier(tmp_path,task.id)
    assert asyncio.run(verifier.build(c.id)).state=='PASS'
    assert asyncio.run(verifier.test(c.id)).state=='PASS'
    def unavailable(self):raise ValueError('TEST_NATIVE_COMPONENT_UNAVAILABLE')
    monkeypatch.setattr(NativeCoreClient,'component_identity',unavailable)
    report=asyncio.run(engine.run(c.id))
    assert report['state']=='UNKNOWN' and report['batches']==[]
    assert 'UNAVAILABLE' in report['reason'] or 'unavailable' in report['reason']
    from nexus.execution.delivery import DeliveryService
    with pytest.raises(ValueError):DeliveryService(store).check_set_hash(c.id)


def test_native_boundary_tamper_cannot_be_replayed_or_accepted(tmp_path):
    from nexus.contracts import digest
    store,ws,task,apply=setup(tmp_path);engine=exploration(store);c=apply('x')
    verifier=CangjieVerifier(tmp_path,task.id)
    assert asyncio.run(verifier.build(c.id)).state=='PASS'
    assert asyncio.run(verifier.test(c.id)).state=='PASS'
    report=asyncio.run(engine.run(c.id))
    assert report['state']=='PASS'
    # Rehash the outer record as well: semantic proof must still reject it.
    report['native_boundary']['response']['data']['axes'][0]=[0,1,2]
    ref,sha=engine.write_record(report,'.tampered-exploration.json')
    with store.connect() as db:db.execute('UPDATE exploration_runs SET report_ref=?,report_sha256=? WHERE candidate_id=?',(ref,sha,c.id))
    with pytest.raises(ValueError):engine.verify(c.id)
    from nexus.execution.delivery import DeliveryService
    with pytest.raises(ValueError):DeliveryService(store).check_set_hash(c.id)


def test_zero_parameter_rule_still_runs_one_native_backed_sdk_case(tmp_path):
    store=RunStore(tmp_path);uploads=UploadService(store)
    draft=uploads.prepare('constant.cj',b'public func f(): Int64 { 0 }\n','固定返回1',actor_id='TEST_FIXTURE',request_key='zero')
    rule=dict(version=1,function='f',domains={},expression='1',seed=7,max_cases=16)
    uploads.confirm(draft['id'],expected_version=1,function='f',examples_json=json.dumps([
        dict(args=[],expected=1,suite='target'),dict(args=[],expected=1,suite='regression')]),
        consent=True,actor_id='TEST_FIXTURE',oracle_json=json.dumps(rule))
    project=uploads.source(draft['id'],actor_id='TEST_FIXTURE');ws=WorkspaceStore(tmp_path,registered=[project]);baseline=ws.import_project(project,'.')
    requirements=RequirementService(store);d=requirements.prepare_requirement(draft['id'],'固定返回1')
    spec=requirements.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='TEST_FIXTURE')
    task=requirements.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    content=ws.read_file(baseline,'src/uploaded.cj')
    candidate=ws.apply_candidate(task,CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(content),content=content.replace('{ 0 }','{ 1 }'))],requirement_refs=['REQ-UPLOAD']))
    verifier=CangjieVerifier(tmp_path,task.id)
    assert asyncio.run(verifier.build(candidate.id)).state=='PASS'
    assert asyncio.run(verifier.test(candidate.id)).state=='PASS'
    report=asyncio.run(exploration(store).run(candidate.id))
    assert report['state']=='PASS',report.get('reason')
    assert report['search_cases']==1 and report['batches'][0]['inputs']==[[]]
    assert report['native_boundary']['response']['data']['axes']==[]
