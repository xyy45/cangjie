"""Self-built String defects with actual pinned SDK/native verification.

Reference fixes are explicit test inputs, not live LLM quality measurements.
"""
import asyncio,json
from pathlib import Path
import pytest
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.contracts import CandidateProposal,file_hash,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.repair import oracle,sequences
from nexus.repair.exploration import ExplorationService
from nexus.repair.property_service import PropertyService
from nexus.repair.relation_service import RelationService
from nexus.repair.sequence_service import SequenceService,failure_trace

pytestmark=pytest.mark.sdk
SERVICES=dict(oracle=ExplorationService,property=PropertyService,relation=RelationService,sequence=SequenceService)


def scenario(kind):
    if kind in ('oracle','property'):
        bad='package bench\npublic func validLabel(code: String): Bool {\nreturn code.size <= 4\n}\n';fixed=bad.replace('code.size','code.toRuneArray().size')
        domains=dict(code=dict(values=['','abc','abcdef','中','中中','中中中中','中中中中中']))
        if kind=='oracle':model=dict(version=3,function='validLabel',domains=domains,expression='rune_len(code) <= 4',seed=7,max_cases=16,excluded_inputs=[])
        else:model=dict(version=2,kind='single',function='validLabel',domains=domains,properties=[dict(id='PROP-RUNES',text='按码点长度判定',precondition='True',assertion='result == (rune_len(arg0) <= 4)')],seed=7,max_cases=16,excluded_inputs=[])
        return dict(function='validLabel',path='src/label.cj',files={'src/label.cj':bad.encode()},fixed=fixed,model=model,examples=[dict(args=['abc'],expected=True,suite='target'),dict(args=['abcdef'],expected=False,suite='regression')])
    if kind=='relation':
        bad='package bench\npublic func encode(user: String, code: String): String {\nif (user == "u" || user == "v") { return user + ":" + code }\nreturn user + code\n}\n';fixed=bad.replace('return user + code','return user + ":" + code')
        wrapper=b'package bench\npublic func ticket(user: String, code: String): String { return encode(user, code) }\n'
        model=dict(version=2,kind='relation',function='ticket',domains=dict(user=dict(values=['','a','ab','u','v']),code=dict(values=['','a','b','bc','c','x','y'])),relations=[dict(id='REL-SPLIT',text='分段不同的票据不能冲突',precondition='left_arg0 + left_arg1 == right_arg0 + right_arg1 and (left_arg0 != right_arg0 or left_arg1 != right_arg1)',assertion='left_result != right_result')],seed=7,max_pairs=16,excluded_inputs=[])
        return dict(function='ticket',path='src/encoding.cj',files={'src/encoding.cj':bad.encode(),'src/ticket.cj':wrapper},fixed=fixed,model=model,examples=[dict(args=['u','x'],expected='u:x',suite='target'),dict(args=['v','y'],expected='v:y',suite='regression')])
    bug='if (state != "" && quantity > 5) { return state }\n'
    bad='package bench\npublic func advance(state: String, quantity: Int64): String {\n'+bug+'if (state.size < 3) { return state + "a" }\nreturn state\n}\n'
    model=dict(version=2,kind='sequence',function='advance',state_param='state',domains=dict(state=dict(values=['','a','aa','aaa']),quantity=dict(min=0,max=100,points=[])),initial_states=[''],initial_precondition='True',context_params=[],operations=[dict(id='OP-APPEND',text='追加并封顶',args=[dict(domain='quantity')],transition='state + "a" if rune_len(state) < 3 else state')],invariants=[dict(id='INV-BOUND',text='状态保持有界',precondition='True',assertion='byte_len(result) <= 3')],seed=7,max_sequences=8,max_steps=4,excluded_inputs=[])
    return dict(function='advance',path='src/state.cj',files={'src/state.cj':bad.encode()},fixed=bad.replace(bug,''),model=model,examples=[dict(args=['',1],expected='a',suite='target'),dict(args=['aaa',0],expected='aaa',suite='regression')])


def setup(root,kind):
    data=scenario(kind);store=RunStore(root);uploads=UploadService(store);files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,**data['files']}
    draft=uploads.prepare_project('string-'+kind,None,'String边界业务自建验证',actor_id='TEST_FIXTURE',request_key='one',entries=files)
    key=dict(oracle='oracle_json',property='properties_json',relation='relations_json',sequence='sequences_json')[kind]
    uploads.confirm(draft['id'],expected_version=1,function=data['function'],examples_json=json.dumps(data['examples']),allowed_paths=[data['path']],consent=True,actor_id='TEST_FIXTURE',**{key:json.dumps(data['model'])})
    source=uploads.source(draft['id'],actor_id='TEST_FIXTURE');ws=WorkspaceStore(root,registered=[source]);baseline=ws.import_project(source,'.')
    req=RequirementService(store);rd=req.prepare_requirement(draft['id'],draft['goal']);spec=req.confirm_requirement(rd['id'],dict(schema_version=1,expected_version=1,requirements=rd['requirements'],allowed_paths=rd['allowed_paths']),actor_id='TEST_FIXTURE')
    task=req.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,data['path'])
    def candidate(fixed=False):
        return ws.apply_candidate(store.get_task(task.id),CandidateProposal(edits=[dict(path=data['path'],before_hash=file_hash(original),content=(data['fixed'] if fixed else original)+'\n// candidate\n')],requirement_refs=['REQ-UPLOAD']))
    return store,ws,task,candidate,data


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_string_public_pass_independent_failure_reference_fix_and_history(tmp_path,kind):
    store,ws,task,apply,data=setup(tmp_path.resolve(),kind);verifier=CangjieVerifier(store.root,task.id);engine=SERVICES[kind](store)
    reports=[]
    for fixed in (False,True):
        candidate=apply(fixed);assert asyncio.run(verifier.build(candidate.id)).state=='PASS'
        public=asyncio.run(verifier.test(candidate.id));assert public.state=='PASS',public.diagnostics
        before=source_manifest(ws.subject_path(candidate.id));report=asyncio.run(engine.run(candidate.id));reports.append(report)
        (tmp_path/(('fixed' if fixed else 'defect')+'-report.json')).write_text(json.dumps(report,ensure_ascii=True,indent=2))
        assert report['state']==('PASS' if fixed else 'FAIL'),(report.get('reason'),report)
        assert report['public_test_state']=='PASS' and engine.verify(candidate.id)==report
        assert source_manifest(ws.subject_path(candidate.id))==before
        for batch in report['batches']:
            log=(store.root/batch['log_ref']).read_text()
            assert 'NEXUS_EXECUTION_PHASE' in log and '_V2|' in log and 'FIXTURE' not in log
    failed,passed=reports
    if kind=='sequence':
        contract=engine.binding(passed['candidate_id'])[3]
        retained={sequences.trace_key(failure_trace(contract,f)) for f in failed['failures']}
        assert passed['regression_traces']>0 and retained<={sequences.trace_key(t) for t in passed['batches'][0]['traces']}
        first=failed['batches'][0]['result']['failures'];later=[f for b in failed['batches'][1:] for f in b['result']['failures']]
        assert later and min(sequences.trace_score(failure_trace(contract,f)) for f in later)<min(sequences.trace_score(failure_trace(contract,f)) for f in first),'requires actual smaller observed failure'
    elif kind=='relation':
        assert passed['regression_pairs']>0
        assert failed['failures'][0]['left_actual_return']==failed['failures'][0]['right_actual_return']
    else:
        assert passed['regression_cases']>0
        retained={oracle.input_key(f['args']) for f in failed['failures']};assert retained<={oracle.input_key(a) for a in passed['batches'][0]['inputs']}


@pytest.mark.parametrize('mode',['normal','unknown'])
def test_string_cegis_http_fixture_feedback_and_real_delivery(tmp_path,monkeypatch,mode):
    import httpx,zipfile
    from nexus.analysis.repair import RepairAnalysis
    from nexus.analysis.service import AnalysisService
    from nexus.demo.deepseek import DeepSeekProvider
    from nexus.execution.delivery import DeliveryService
    from nexus.repair.cegis_loop import RepairLoop
    from nexus.repair.focus_service import FocusService
    from tests.analysis.test_repair_localization import GraphTransport
    root=tmp_path.resolve();store,ws,task,_,data=setup(root,'sequence');contexts=[];requests=[]
    for key,value in dict(DEEPSEEK_API_KEY='fixture-only',DEEPSEEK_BASE_URL='https://fixture.invalid',DEEPSEEK_MODEL='test-model').items():monkeypatch.setenv(key,value)
    client=httpx.AsyncClient
    def response(request):
        assert request.url.host=='fixture.invalid';body=json.loads(request.content);requests.append(body)
        context=json.loads(body['messages'][1]['content']);contexts.append(context);original=context['files'][data['path']]['content']
        changed=(original if len(contexts)==1 else data['fixed'])+'\n// explicit HTTP FIXTURE\n'
        if mode=='unknown':changed=changed.replace('if (state != \"\" && quantity > 5) { return state }','if (state != \"\" && quantity > 5) { while (true) { } }')
        refs=[t['evidence_id'] for f in context.get('analysis',{}).get('files',[]) for t in f['tools'] if t.get('included') and t['status']=='VALID'][:1]
        payload=dict(schema_version=1,summary='HTTP FIXTURE String proposal',suggestions=[dict(path=data['path'],reason='HTTP FIXTURE')],analysis_refs=refs,
            proposal=dict(edits=[dict(path=data['path'],before_hash=file_hash(original),content=changed)],requirement_refs=['REQ-UPLOAD']))
        return httpx.Response(200,json=dict(model='test-model',usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),choices=[dict(finish_reason='stop',message=dict(content=json.dumps(payload)))]))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:client(transport=httpx.MockTransport(response),**kw))
    bridge=RepairAnalysis(store,AnalysisService(root,client_factory=GraphTransport))
    result=asyncio.run(RepairLoop(store,provider_factory=DeepSeekProvider,context_enricher=bridge.enrich,focus_enricher=FocusService(store).enrich).run(task.id))
    (root/'http-model-fixture-contexts.json').write_text(json.dumps(contexts,ensure_ascii=True,indent=2))
    if mode=='unknown':
        assert result.status=='BLOCKED' and len(contexts)==1,store.records(task.id,'event')[-1]
        assert not any('selected_candidate_id' in e for e in store.records(task.id,'event'))
        return
    assert result.status=='REVIEW_PENDING' and len(contexts)==2,store.records(task.id,'event')[-1]
    assert all(c['analysis']['status']=='COMPLETE' and 'String' in c['upload_constraints']['types'] and 'verification/sequences.json' not in c['files'] for c in contexts)
    failure=contexts[1]['feedback'][0]['failure_cases'][0]
    assert failure['kind']=='business_sequence' and failure['initial_state']=='' and type(failure['actual_return']) is str and len(failure['steps'])==2
    assert failure['steps'][1]['before_state']==failure['steps'][0]['actual_return']
    targets=contexts[1]['repair_focus']['targets'];assert targets and targets[0]['mapping']=='CONFIRMED_CASE' and type(targets[0]['actual_return']) is str
    assert 'sequences_contract' not in str(contexts) and 'excluded_inputs' not in json.dumps(contexts)
    events=store.records(task.id,'event');selected=next(e['selected_candidate_id'] for e in events if 'selected_candidate_id' in e);engine=SequenceService(store)
    failed=engine.verify(contexts[1]['feedback'][0]['previous_candidate_id']);passed=engine.verify(selected)
    assert failed['state']=='FAIL' and passed['state']=='PASS' and passed['regression_traces']>0
    delivery=DeliveryService(store)
    with pytest.raises(ValueError):delivery.check_set_hash(failed['candidate_id'])
    from nexus.web.app import create_app
    app=create_app(store,RepairLoop(store),delivery,require_operator=False);app.testing=True;app.config['RUN_TASKS']=False;web=app.test_client();web.get('/')
    with web.session_transaction() as session:session['actor_id']='TEST_FIXTURE';csrf=session['csrf']
    headers={'Origin':'http://localhost','X-CSRF-Token':csrf}
    approval=web.post('/api/candidates/'+selected+'/accept',json=dict(check_set_hash=delivery.check_set_hash(selected),task_revision=store.get_task(task.id).revision),headers=headers)
    assert approval.status_code==200,approval.json
    exported=web.post('/api/candidates/'+selected+'/export',json=dict(acceptance_id=approval.json['id']),headers=headers)
    assert exported.status_code==200,exported.json
    url=exported.json['download_url'];assert web.get(url).status_code==200
    with zipfile.ZipFile(root/exported.json['download_ref']) as archive:
        assert json.loads(archive.read('evidence/sequence-report.json'))==passed
        assert archive.read('evidence/analysis.json') and archive.read('evidence/localization.json')
    public=[r for r in store.records(task.id,'check') if r['subject_id']==selected and r['kind']=='test'][-1]
    controls=[('hex',root/passed['batches'][0]['log_ref']),('public',root/public['log_ref']),('model',ws.verify_baseline(task.baseline_id)/'verification/sequences.json')];outcomes=[]
    for name,path in controls:
        original=path.read_bytes()
        changed=original.replace(b'|String|s:',b'|String|s:g',1) if name=='hex' else b'{}' if name=='model' else b'changed public log'
        assert changed!=original;path.write_bytes(changed)
        try:
            status=web.get(url).status_code;outcomes.append(dict(control=name,http_status=status));assert status==400
        finally:path.write_bytes(original)
    assert engine.verify(selected)==passed and web.get(url).status_code==200
    (root/'download-tamper-controls.json').write_text(json.dumps(outcomes))
