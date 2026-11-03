"""Actual local SDK/native/stdio with explicit HTTP model and graph fixtures."""
import asyncio,json,zipfile
import httpx,pytest
from nexus.analysis.repair import RepairAnalysis
from nexus.analysis.service import AnalysisService
from nexus.demo.deepseek import DeepSeekProvider
from nexus.execution.delivery import DeliveryService
from nexus.repair.cegis_loop import RepairLoop
from nexus.repair.focus_service import FocusService
from nexus.repair import public_fields
from nexus.contracts import file_hash
from nexus.uploads.language import Parser
from tests.analysis.test_repair_bridge import Transport
from tests.sdk.test_object_loop_sdk import setup,SERVICES

pytestmark=pytest.mark.sdk


class ObjectGraphTransport(Transport):
    def __init__(self,types):self.types=types
    def analyze(self,tool,args):
        response=super().analyze(tool,args)
        if tool=='sympas_dep_graph':
            info=Parser(args['code'],types=self.types).program(headers_only=True);nodes=[];edges=[]
            for i,f in enumerate(info['functions']+info.get('methods',[])):
                nodes.extend([dict(id='param'+str(i),label='[L'+str(f['line'])+']: fixture parameter'),dict(id='result'+str(i),label='[L'+str(f['final_line'])+']: fixture result')]);edges.append({'from':'param'+str(i),'to':'result'+str(i)})
            response['response']['json_graphs'].append(dict(graph_type='Pdg',nodes=nodes,edges=edges))
        return response


@pytest.mark.parametrize('mode',['normal','public','unknown'])
def test_object_cegis_fixture_model_real_sdk_feedback_gates_and_delivery(tmp_path,monkeypatch,mode):
    root=tmp_path.resolve();kind='oracle' if mode=='unknown' else 'sequence';store,ws,task,_,data=setup(root,kind,mode);contexts=[];requests=[]
    for key,value in dict(DEEPSEEK_API_KEY='fixture-only',DEEPSEEK_BASE_URL='https://fixture.invalid',DEEPSEEK_MODEL='test-model').items():monkeypatch.setenv(key,value)
    def response(request):
        assert request.url.host=='fixture.invalid';body=json.loads(request.content);requests.append(body);context=json.loads(body['messages'][1]['content']);contexts.append(context)
        original=context['files'][data['path']]['content'];changed=(original if len(contexts)==1 else data['fixed'])+'\n// explicit HTTP FIXTURE\n'
        refs=[t['evidence_id'] for f in context.get('analysis',{}).get('files',[]) for t in f['tools'] if t.get('included') and t['status']=='VALID'][:1]
        payload=dict(schema_version=1,summary='HTTP FIXTURE object proposal',suggestions=[dict(path=data['path'],reason='HTTP FIXTURE')],analysis_refs=refs,proposal=dict(edits=[dict(path=data['path'],before_hash=file_hash(original),content=changed)],requirement_refs=['REQ-UPLOAD']))
        return httpx.Response(200,json=dict(model='test-model',usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),choices=[dict(finish_reason='stop',message=dict(content=json.dumps(payload)))]))
    def provider(store,identity):return DeepSeekProvider(store,identity,transport=httpx.MockTransport(response))
    bridge=RepairAnalysis(store,AnalysisService(root,client_factory=lambda:ObjectGraphTransport(data['types'])));focus=FocusService(store)
    result=asyncio.run(RepairLoop(store,provider_factory=provider,context_enricher=bridge.enrich,focus_enricher=focus.enrich).run(task.id))
    (root/'http-model-fixture-contexts.json').write_text(json.dumps(contexts,ensure_ascii=True,indent=2));assert all(r['origin']=='TEST' for r in store.records(task.id,'model_call'))
    if mode=='unknown':
        assert result.status=='BLOCKED' and len(contexts)==1,store.records(task.id,'event')[-1]
        assert not any('selected_candidate_id' in e for e in store.records(task.id,'event'))
        return
    assert result.status=='REVIEW_PENDING' and len(contexts)==2,store.records(task.id,'event')[-1]
    assert all(c['upload_constraints']['readonly_object_fields'] and c['upload_constraints']['object_registry']==data['types'] and 'verification/sequences.json' not in c['files'] for c in contexts)
    assert 'sequences_contract' not in str(contexts) and 'excluded_inputs' not in json.dumps(contexts)
    failure=contexts[1]['feedback'][0]['failure_cases'][0]
    if mode=='public':
        assert failure['kind']=='public_field' and failure['field_path']==['amount'] and failure['actual_value']==0 and failure['expected_value']==1 and 'actual_return' not in failure
        assert contexts[1]['repair_focus']['targets'][0]['field_path']==['amount']
    else:
        assert failure['kind']=='business_sequence' and failure['initial_state']['$type']=='OrderState' and type(failure['context'][0]) is list and len(failure['steps'])==2
        assert failure['steps'][1]['before_state']==failure['steps'][0]['actual_return']
        assert contexts[1]['repair_focus']['targets'][0]['mapping']=='CONFIRMED_CASE'
    selected=next(e['selected_candidate_id'] for e in store.records(task.id,'event') if 'selected_candidate_id' in e);engine=SERVICES[kind](store);passed=engine.verify(selected);assert passed['state']=='PASS'
    if mode=='normal':
        failed=engine.verify(contexts[1]['feedback'][0]['previous_candidate_id']);assert failed['state']=='FAIL' and passed['regression_traces']>0
    delivery=DeliveryService(store)
    with pytest.raises(ValueError):delivery.check_set_hash(contexts[1]['feedback'][0]['previous_candidate_id'])
    from nexus.web.app import create_app
    app=create_app(store,RepairLoop(store),delivery,require_operator=False);app.testing=True;app.config['RUN_TASKS']=False;web=app.test_client();web.get('/')
    with web.session_transaction() as session:session['actor_id']='OBJECT_SDK_FIXTURE';csrf=session['csrf']
    headers={'Origin':'http://localhost','X-CSRF-Token':csrf}
    approval=web.post('/api/candidates/'+selected+'/accept',json=dict(check_set_hash=delivery.check_set_hash(selected),task_revision=store.get_task(task.id).revision),headers=headers);assert approval.status_code==200,approval.json
    exported=web.post('/api/candidates/'+selected+'/export',json=dict(acceptance_id=approval.json['id']),headers=headers);assert exported.status_code==200,exported.json
    url=exported.json['download_url'];assert web.get(url).status_code==200
    with zipfile.ZipFile(root/exported.json['download_ref']) as archive:
        assert json.loads(archive.read('evidence/sequence-report.json'))==passed and archive.read('evidence/analysis.json') and archive.read('evidence/localization.json')
    public=[r for r in store.records(task.id,'check') if r['subject_id']==selected and r['kind']=='test'][-1]
    controls=[('object-wire',root/passed['batches'][0]['log_ref']),('public',root/public['log_ref']),('model',ws.verify_baseline(task.baseline_id)/'verification/sequences.json'),('registry',ws.verify_baseline(task.baseline_id)/'src/state.cj')];outcomes=[]
    for name,path in controls:
        original=path.read_bytes();changed=original.replace(b'o:OrderState:',b'o:OtherState:',1) if name=='object-wire' else b'{}' if name=='model' else b'changed public log' if name=='public' else original.replace(b'public let amount: Int64',b'public let amount: Bool',1);assert changed!=original
        path.write_bytes(changed)
        try:status=web.get(url).status_code;outcomes.append(dict(control=name,http_status=status));assert status==400
        finally:path.write_bytes(original)
    assert engine.verify(selected)==passed and web.get(url).status_code==200
    (root/'download-tamper-controls.json').write_text(json.dumps(outcomes))
