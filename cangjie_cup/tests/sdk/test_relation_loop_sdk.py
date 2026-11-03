"""Two HTTP model fixture rounds with real SDK, native policy and local MCP."""
import asyncio
import json
import zipfile

import httpx
import pytest

from nexus.contracts import file_hash
from nexus.analysis.repair import RepairAnalysis
from nexus.analysis.service import AnalysisService
from nexus.demo.deepseek import DeepSeekProvider
from nexus.execution.delivery import DeliveryService
from nexus.repair.cegis_loop import RepairLoop
from nexus.repair.focus_service import FocusService
from nexus.repair.property_service import PropertyService
from nexus.repair.relation_service import RelationService
from tests.test_relation_service import setup
from tests.analysis.test_repair_localization import GraphTransport

pytestmark=pytest.mark.sdk


def test_real_relation_counterexample_drives_second_fixture_round_localization_and_bound_delivery(tmp_path,monkeypatch):
    store,ws,task,_=setup(tmp_path,single='result >= 0',reserved=[[9,100,False]]);captured=[];bodies=[]
    for key,value in dict(DEEPSEEK_API_KEY='fixture-only',DEEPSEEK_BASE_URL='https://fixture.invalid',DEEPSEEK_MODEL='test-model').items():monkeypatch.setenv(key,value)
    client=httpx.AsyncClient
    def response(request):
        body=json.loads(request.content);bodies.append(body);context=json.loads(body['messages'][1]['content']);captured.append(context)
        original=context['files']['src/uploaded.cj']['content']
        changed=original.replace('return quantity * price','if (quantity >= 10) { return 0 }\n return quantity * price') if len(captured)==1 else original+'\n// HTTP FIXTURE reference\n'
        references=[tool['evidence_id'] for entry in context.get('analysis',{}).get('files',[]) for tool in entry['tools'] if tool.get('included') and tool['status']=='VALID'][:1]
        payload=dict(schema_version=1,summary='HTTP FIXTURE candidate',suggestions=[dict(path='src/uploaded.cj',reason='HTTP FIXTURE')],analysis_refs=references,
            proposal=dict(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=changed)],requirement_refs=['REQ-UPLOAD']))
        return httpx.Response(200,json=dict(model='test-model',usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),choices=[dict(finish_reason='stop',message=dict(content=json.dumps(payload)))]))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:client(transport=httpx.MockTransport(response),**kw))
    bridge=RepairAnalysis(store,AnalysisService(tmp_path,client_factory=GraphTransport))
    result=asyncio.run(RepairLoop(store,provider_factory=DeepSeekProvider,context_enricher=bridge.enrich,focus_enricher=FocusService(store).enrich).run(task.id))
    assert result.status=='REVIEW_PENDING',store.records(task.id,'event')[-1]
    assert len(captured)==2
    assert captured[0]['diagnostics']['test']['state']=='PASS' and 'diagnostics' in captured[0]['diagnostics']['test']
    assert all('verification/relations.json' not in c['files'] and 'relations_contract' not in c and 'excluded_inputs' not in json.dumps(c) for c in captured)
    feedback=captured[1]['feedback'][0];failure=feedback['failure_cases'][0]
    assert failure['kind']=='business_relation' and failure['left_actual_return']>failure['right_actual_return']
    assert 'expected' not in failure and failure['assertion_value'] is False
    assert 'business_relation' in bodies[0]['messages'][0]['content'] and 'suggestions.path' in bodies[0]['messages'][0]['content']
    targets=captured[1]['repair_focus']['targets'];assert len(targets)>=2
    assert captured[1]['repair_focus']['binding']['subject_id']==feedback['previous_candidate_id']
    assert targets[0]['relation_role']=='left' and targets[1]['relation_role']=='right'
    assert targets[0]['expected'] is None and targets[1]['expected'] is None
    assert targets[0]['actual_return']==failure['left_actual_return'] and targets[1]['actual_return']==failure['right_actual_return']
    assert all(t['mapping']=='CONFIRMED_CASE' and t['function']=='amount' for t in targets)
    assert all(context['analysis']['status']=='COMPLETE' for context in captured)
    assert all(anchor['slice']['status']=='VALID' for target in targets for location in target['locations'] for anchor in location['anchors'])
    events=store.records(task.id,'event');selected=next(e['selected_candidate_id'] for e in events if 'selected_candidate_id' in e)
    failed=RelationService(store).verify(feedback['previous_candidate_id']);passed=RelationService(store).verify(selected)
    assert failed['state']=='FAIL' and passed['state']=='PASS' and passed['regression_pairs']>0
    assert PropertyService(store).verify(feedback['previous_candidate_id'])['state']=='PASS'
    for side in ('left','right'):
        log=(store.root/failure[side+'_source']['log_ref']).read_text()
        assert '|Int64|'+str(failure[side+'_actual_return']) in log and 'FIXTURE' not in log
    delivery=DeliveryService(store)
    with pytest.raises(ValueError):delivery.check_set_hash(feedback['previous_candidate_id'])
    accepted=delivery.accept(selected,delivery.check_set_hash(selected),actor_id='alice');exported=delivery.export(selected,accepted.id)
    with zipfile.ZipFile(store.root/exported['download_ref']) as archive:
        assert archive.read('evidence/analysis.json') and archive.read('evidence/localization.json')
        assert json.loads(archive.read('evidence/relation-report.json'))==passed
        assert json.loads(archive.read('evidence/relations.json'))['kind']=='relation'
        assert archive.read('project/verification/relations.json')
        for batch in passed['batches']:
            assert archive.read('evidence/native/'+batch['log_ref'])==(store.root/batch['log_ref']).read_bytes()
            assert archive.read('evidence/native/'+batch['harness_ref'])==(store.root/batch['harness_ref']).read_bytes()
    (store.root/passed['batches'][0]['log_ref']).write_text('tampered after acceptance')
    with pytest.raises(ValueError):delivery.export(selected,accepted.id)
