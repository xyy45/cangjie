"""Two HTTP model fixtures, genuine SDK/native policy/stdio MCP, no external requests."""
import asyncio
from copy import deepcopy
import json
import zipfile

import httpx
import pytest

from nexus.analysis.repair import RepairAnalysis
from nexus.analysis.service import AnalysisService
from nexus.contracts import file_hash
from nexus.demo.deepseek import DeepSeekProvider
from nexus.execution.delivery import DeliveryService
from nexus.repair.cegis_loop import RepairLoop
from nexus.repair.focus_service import FocusService
from nexus.repair.exploration import ExplorationService
from nexus.repair.property_service import PropertyService
from nexus.repair.relation_service import RelationService
from nexus.repair.sequence_service import SequenceService
from nexus.uploads.service import UploadService
from tests.sdk.test_sequences_sdk import stock_system
from tests.analysis.test_repair_localization import GraphTransport

pytestmark=pytest.mark.sdk


def system(root,monkeypatch):
    # Add genuine confirmed predecessor contracts during fixture preparation;
    # all confirmation, execution and replay use the unchanged product methods.
    original=UploadService.confirm
    def confirm(self,*args,**kwargs):
        model=json.loads(kwargs['sequences_json']);domains=deepcopy(model['domains'])
        properties=dict(version=1,kind='single',function='adjust',domains=domains,properties=[dict(id='PROP-NONNEGATIVE',text='库存非负',precondition='True',assertion='result >= 0')],seed=0,max_cases=16,excluded_inputs=[])
        relations=dict(version=1,kind='relation',function='adjust',domains=domains,relations=[dict(id='REL-NONNEGATIVE',text='两个库存均非负',precondition='True',assertion='left_result >= 0 and right_result >= 0')],seed=0,max_pairs=16,excluded_inputs=[])
        oracle_domains=deepcopy(domains);oracle_domains['state']=dict(min=10,max=10)
        numeric=dict(version=1,function='adjust',domains=oracle_domains,expression='state - quantity if operation == 0 and quantity <= state else state if operation == 0 else min(capacity, state + quantity)',seed=0,max_cases=32)
        return original(self,*args,**kwargs,properties_json=json.dumps(properties),relations_json=json.dumps(relations),oracle_json=json.dumps(numeric))
    with monkeypatch.context() as preparation:
        preparation.setattr(UploadService,'confirm',confirm)
        return stock_system(root)


def test_sequence_feedback_drives_second_http_fixture_round_and_bound_download(tmp_path,monkeypatch):
    root=tmp_path.resolve();store,ws,task,_=system(root,monkeypatch);captured=[];bodies=[]
    for key,value in dict(DEEPSEEK_API_KEY='fixture-only',DEEPSEEK_BASE_URL='https://fixture.invalid',DEEPSEEK_MODEL='test-model').items():monkeypatch.setenv(key,value)
    client=httpx.AsyncClient
    def response(request):
        assert request.url.host=='fixture.invalid','unexpected network target'
        body=json.loads(request.content);bodies.append(body);context=json.loads(body['messages'][1]['content']);captured.append(context)
        original=context['files']['src/stock.cj']['content'];bug=' if (state < capacity && quantity == capacity - state) { return capacity - 1 }\n'
        changed=(original if len(captured)==1 else original.replace(bug,''))+'\n// explicit HTTP FIXTURE candidate\n'
        references=[tool['evidence_id'] for entry in context.get('analysis',{}).get('files',[]) for tool in entry['tools'] if tool.get('included') and tool['status']=='VALID'][:1]
        payload=dict(schema_version=1,summary='HTTP FIXTURE candidate',suggestions=[dict(path='src/stock.cj',reason='HTTP FIXTURE')],analysis_refs=references,
            proposal=dict(edits=[dict(path='src/stock.cj',before_hash=file_hash(original),content=changed)],requirement_refs=['REQ-UPLOAD']))
        return httpx.Response(200,json=dict(model='test-model',usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),choices=[dict(finish_reason='stop',message=dict(content=json.dumps(payload)))]))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:client(transport=httpx.MockTransport(response),**kw))
    bridge=RepairAnalysis(store,AnalysisService(root,client_factory=GraphTransport))
    result=asyncio.run(RepairLoop(store,provider_factory=DeepSeekProvider,context_enricher=bridge.enrich,focus_enricher=FocusService(store).enrich).run(task.id))
    assert result.status=='REVIEW_PENDING',store.records(task.id,'event')[-1]
    assert len(captured)==2 and all(context['analysis']['status']=='COMPLETE' for context in captured)
    assert 'diagnostics' in captured[0]['diagnostics']['test']
    assert all('verification/sequences.json' not in context['files'] and 'sequences_contract' not in context and 'excluded_inputs' not in json.dumps(context) for context in captured)
    feedback=captured[1]['feedback'][0];failure=feedback['failure_cases'][0]
    assert failure['kind']=='business_sequence' and failure['initial_state']==10 and len(failure['steps'])==2
    assert [s['operation_id'] for s in failure['steps']]==['OP-DEBIT','OP-CANCEL']
    assert failure['before_state']==failure['steps'][0]['actual_return'] and failure['actual_return']==9 and failure['expected_state']==10
    assert 'business_sequence' in bodies[0]['messages'][0]['content'] and 'call_id' in bodies[0]['messages'][0]['content']
    targets=captured[1]['repair_focus']['targets'];assert len(targets)>=2
    assert captured[1]['repair_focus']['binding']['subject_id']==feedback['previous_candidate_id']
    assert targets[0]['sequence_role']=='failure' and targets[0]['step_index']==1
    assert all(t['mapping']=='CONFIRMED_CASE' and t['function']=='adjust' for t in targets)
    assert len({t['call_id'] for t in targets})==len(targets)
    assert any(target['sequence_role']=='predecessor' and target['test_id']==targets[0]['test_id'] for target in targets)
    assert len(feedback['failure_cases'][0]['steps'])==2
    events=store.records(task.id,'event');selected=next(e['selected_candidate_id'] for e in events if 'selected_candidate_id' in e)
    engine=SequenceService(store);failed=engine.verify(feedback['previous_candidate_id']);passed=engine.verify(selected)
    assert failed['state']=='FAIL' and passed['state']=='PASS' and passed['regression_traces']>0
    for service in (ExplorationService,PropertyService,RelationService):
        assert service(store).verify(feedback['previous_candidate_id'])['state']=='PASS'
        assert service(store).verify(selected)['state']=='PASS'
    for step in failure['steps']:
        text=(root/step['source']['log_ref']).read_text()
        assert 'NEXUS_SEQUENCE_V1|' in text and 'FIXTURE' not in text
    delivery=DeliveryService(store)
    with pytest.raises(ValueError):delivery.check_set_hash(feedback['previous_candidate_id'])
    accepted=delivery.accept(selected,delivery.check_set_hash(selected),actor_id='alice');exported=delivery.export(selected,accepted.id)
    with zipfile.ZipFile(root/exported['download_ref']) as archive:
        assert json.loads(archive.read('evidence/sequence-report.json'))==passed
        assert json.loads(archive.read('evidence/sequences.json'))['kind']=='sequence'
        assert archive.read('evidence/analysis.json') and archive.read('evidence/localization.json') and archive.read('project/verification/sequences.json')
        for batch in passed['batches']:
            for kind in ('log','harness'):assert archive.read('evidence/native/'+batch[kind+'_ref'])==(root/batch[kind+'_ref']).read_bytes()
    from nexus.web.app import create_app
    app=create_app(store,RepairLoop(store),delivery,require_operator=False);web=app.test_client();web.get('/')
    with web.session_transaction() as session:session['actor_id']='alice'
    url='/downloads/'+exported['export_id'];assert web.get(url).status_code==200
    checks=[r for r in store.records(task.id,'check') if r['subject_id']==selected and r['kind']=='test']
    controls=[('end',root/passed['batches'][0]['log_ref']),('public',root/checks[-1]['log_ref']),('model',ws.verify_baseline(task.baseline_id)/'verification/sequences.json')]
    outcomes=[]
    for name,path in controls:
        original=path.read_bytes()
        path.write_bytes(original.replace(b'COMPLETE',b'WRONG_END',1) if name=='end' else b'{}' if name=='model' else b'changed public log')
        try:
            status=web.get(url).status_code;outcomes.append(dict(control=name,http_status=status));assert status==400
            with pytest.raises(ValueError):delivery.export(selected,accepted.id)
        finally:path.write_bytes(original)
    (root/'download-tamper-controls.json').write_text(json.dumps(outcomes))
    assert engine.verify(selected)==passed
