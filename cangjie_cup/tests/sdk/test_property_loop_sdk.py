"""Real SDK/native policy/MCP transport, deterministic model HTTP fixture only."""
import asyncio
import json
import zipfile

import httpx
import pytest

from nexus.contracts import file_hash
from nexus.demo.deepseek import DeepSeekProvider
from nexus.execution.delivery import DeliveryService
from nexus.repair.cegis_loop import RepairLoop
from nexus.repair.focus_service import FocusService
from nexus.repair.property_service import PropertyService
from tests.test_property_service import setup

pytestmark=pytest.mark.sdk


def test_actual_property_counterexample_drives_second_http_fixture_round_and_bound_export(tmp_path,monkeypatch):
    store,ws,task,_=setup(tmp_path,reserved=[[999,899,199]]);captured=[];bodies=[]
    for key,value in dict(DEEPSEEK_API_KEY='fixture-only',DEEPSEEK_BASE_URL='https://fixture.invalid',DEEPSEEK_MODEL='test-model').items():monkeypatch.setenv(key,value)
    client=httpx.AsyncClient
    def response(request):
        body=json.loads(request.content);bodies.append(body)
        context=json.loads(body['messages'][1]['content']);captured.append(context)
        original=context['files']['src/uploaded.cj']['content']
        changed=original.replace('refunded + requested','refunded + requested + 0') if len(captured)==1 else original.replace('return refunded + requested','if (requested > paid - refunded) { return refunded }\n return refunded + requested')
        payload=dict(schema_version=1,summary='HTTP FIXTURE candidate',suggestions=[dict(path='src/uploaded.cj',reason='HTTP FIXTURE')],analysis_refs=[],
            proposal=dict(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=changed)],requirement_refs=['REQ-UPLOAD']))
        return httpx.Response(200,json=dict(model='test-model',usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),choices=[dict(finish_reason='stop',message=dict(content=json.dumps(payload)))]))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:client(transport=httpx.MockTransport(response),**kw))
    result=asyncio.run(RepairLoop(store,provider_factory=DeepSeekProvider,focus_enricher=FocusService(store).enrich).run(task.id))
    assert result.status=='REVIEW_PENDING',store.records(task.id,'event')[-1]
    assert len(captured)==2
    assert captured[0]['diagnostics']['test']['state']=='PASS' and 'diagnostics' in captured[0]['diagnostics']['test']
    assert all('verification/properties.json' not in c['files'] and 'properties_contract' not in c and 'excluded_inputs' not in json.dumps(c) for c in captured)
    feedback=captured[1]['feedback'][0];failure=feedback['failure_cases'][0]
    assert failure['kind']=='business_property' and failure['actual_return']>failure['args'][0]
    assert 'expected' not in failure and failure['assertion_value'] is False
    assert 'suggestions.path' in bodies[0]['messages'][0]['content']
    focus=captured[1]['repair_focus'];target=focus['targets'][0]
    assert focus['binding']['subject_id']==feedback['previous_candidate_id']
    assert target['mapping']=='CONFIRMED_CASE' and target['function']=='refundState'
    assert target['expected'] is None and target['actual_return']==failure['actual_return']
    events=store.records(task.id,'event');selected=next(e['selected_candidate_id'] for e in events if 'selected_candidate_id' in e)
    failed=PropertyService(store).verify(feedback['previous_candidate_id']);passed=PropertyService(store).verify(selected)
    assert failed['state']=='FAIL' and passed['state']=='PASS' and passed['regression_cases']>0
    log=(store.root/failure['source']['log_ref']).read_text()
    assert '|Int64|'+str(failure['actual_return']) in log and 'FIXTURE' not in log
    delivery=DeliveryService(store)
    with pytest.raises(ValueError):delivery.check_set_hash(feedback['previous_candidate_id'])
    accepted=delivery.accept(selected,delivery.check_set_hash(selected),actor_id='alice')
    exported=delivery.export(selected,accepted.id)
    with zipfile.ZipFile(store.root/exported['download_ref']) as archive:
        assert json.loads(archive.read('evidence/property-report.json'))==passed
        assert json.loads(archive.read('evidence/properties.json'))['kind']=='single'
        assert archive.read('project/verification/properties.json')
        for batch in passed['batches']:
            assert archive.read('evidence/native/'+batch['log_ref'])==(store.root/batch['log_ref']).read_bytes()
            assert archive.read('evidence/native/'+batch['harness_ref'])==(store.root/batch['harness_ref']).read_bytes()
    (store.root/passed['batches'][0]['log_ref']).write_text('tampered after acceptance')
    with pytest.raises(ValueError):delivery.export(selected,accepted.id)


def test_same_package_property_executes_cross_file_calls_and_preserves_frozen_material(tmp_path):
    from nexus.contracts import CandidateProposal,source_manifest
    from nexus.adapters.cangjie.verifier import CangjieVerifier
    from nexus.execution.workspace import WorkspaceStore
    from nexus.requirements.service import RequirementService
    from nexus.store import RunStore
    from nexus.uploads.service import UploadService
    from tests.test_project_index import project
    from tests.test_project_service import prepare,confirm
    files=project();files['src/fee.cj']=b'package billing\npublic func fee(x: Int64): Int64 {\n if (x >= 37) { return -1 }\n return x\n}\n'
    store=RunStore(tmp_path);uploads=UploadService(store);draft=prepare(uploads,files=files)
    props=dict(version=1,kind='single',function='total',domains={'x':dict(min=0,max=1000)},properties=[
        dict(id='PROP-TOTAL',text='非负输入的总金额至少100',precondition='arg0 >= 0',assertion='result >= 100')],seed=0,max_cases=16,excluded_inputs=[])
    value=confirm(uploads,draft,allowed_paths=['src/fee.cj'],properties_json=json.dumps(props))
    root=uploads.source(draft['id'],actor_id='alice');ws=WorkspaceStore(tmp_path,registered=[root]);base=ws.import_project(root,'.')
    req=RequirementService(store);rd=req.prepare_requirement(draft['id'],draft['goal'])
    spec=req.confirm_requirement(rd['id'],dict(schema_version=1,expected_version=1,requirements=rd['requirements'],allowed_paths=rd['allowed_paths']),actor_id='alice')
    task=req.prepare_task(draft['id'],spec.id,base)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(base,'src/fee.cj')
    def apply(content):return ws.apply_candidate(store.get_task(task.id),CandidateProposal(edits=[dict(path='src/fee.cj',before_hash=file_hash(original),content=content)],requirement_refs=['REQ-UPLOAD']))
    verifier=CangjieVerifier(tmp_path,task.id);engine=PropertyService(store)
    first=apply(original+'\n// preserve defect\n')
    assert asyncio.run(verifier.build(first.id)).state=='PASS' and asyncio.run(verifier.test(first.id)).state=='PASS'
    failed=asyncio.run(engine.run(first.id));assert failed['state']=='FAIL'
    second=apply('package billing\npublic func fee(x: Int64): Int64 { return x }\n')
    assert asyncio.run(verifier.build(second.id)).state=='PASS' and asyncio.run(verifier.test(second.id)).state=='PASS'
    passed=asyncio.run(engine.run(second.id));assert passed['state']=='PASS' and passed['regression_cases']>0
    for report in (failed,passed):
        for batch in report['batches']:
            assert {'src/fee.cj','src/order.cj'}<=set(batch['project_manifest'])
            assert 'src/cases_test.cj' not in batch['project_manifest']
    fixed=ws.subject_path(second.id)
    for path,content in files.items():
        if path!='src/fee.cj':assert (fixed/path).read_bytes()==content
    assert json.loads((fixed/'verification/properties.json').read_bytes())==value['properties_contract']
