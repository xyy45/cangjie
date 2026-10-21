"""Real pinned SDK / native MCP; deterministic model HTTP fixture, not LIVE AI."""
import asyncio,json,zipfile
import httpx,pytest
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.repair.cegis_loop import RepairLoop
from nexus.demo.deepseek import DeepSeekProvider
from nexus.contracts import file_hash,source_manifest

pytestmark=pytest.mark.sdk


@pytest.mark.parametrize('package',['package usercalc\r\n',''])
def test_uploaded_source_real_failure_feedback_then_repair_and_archive(tmp_path,monkeypatch,package):
    source=(package+'public func fee(quantity: Int64, price: Int64): Int64 {\r\n    quantity + price\r\n}\r\n').encode()
    store=RunStore(tmp_path);upload=UploadService(store)
    draft=upload.prepare('fee.cj',source,'费用为数量乘单价',actor_id='TEST_FIXTURE',request_key='k')
    examples=[dict(args=[3,100],expected=300,suite='target'),dict(args=[1,0],expected=0,suite='regression')]
    upload.confirm(draft['id'],expected_version=1,function='fee',examples_json=json.dumps(examples),consent=True,actor_id='TEST_FIXTURE')
    project=upload.source(draft['id'],actor_id='TEST_FIXTURE');ws=WorkspaceStore(tmp_path,registered=[project]);baseline=ws.import_project(project,'.')
    requirements=RequirementService(store);prepared=requirements.prepare_requirement(draft['id'],'费用为数量乘单价')
    spec=requirements.confirm_requirement(prepared['id'],dict(schema_version=1,expected_version=1,requirements=prepared['requirements'],allowed_paths=prepared['allowed_paths']),actor_id='TEST_FIXTURE')
    task=requirements.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    manifest=source_manifest(ws.subject_path(baseline));captured=[]
    for key,value in dict(DEEPSEEK_API_KEY='test-only',DEEPSEEK_BASE_URL='https://model.example',DEEPSEEK_MODEL='test-model').items():monkeypatch.setenv(key,value)
    real_client=httpx.AsyncClient
    def reply(request):
        context=json.loads(json.loads(request.content)['messages'][1]['content']);captured.append(context)
        original=context['files']['src/uploaded.cj']['content']
        content=original.replace('quantity + price','quantity - price' if len(captured)==1 else 'quantity * price')
        message=dict(schema_version=1,summary='测试夹具',suggestions=[dict(path='src/uploaded.cj',reason='测试夹具')],analysis_refs=[],
            proposal=dict(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=content)],requirement_refs=['REQ-UPLOAD']))
        return httpx.Response(200,json=dict(model='test-model',usage=dict(prompt_tokens=100,completion_tokens=50,total_tokens=150),choices=[dict(finish_reason='stop',message=dict(content=json.dumps(message)))]))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real_client(transport=httpx.MockTransport(reply),**kw))
    result=asyncio.run(RepairLoop(store,provider_factory=DeepSeekProvider).run(task.id))
    assert result.status=='REVIEW_PENDING',store.records(task.id,'event')[-1]
    assert len(captured)==2 and captured[0]['files']['src/uploaded.cj']['content'].encode()==(b'' if package else b'package uploadedrepair\n')+source
    case=captured[1]['feedback'][0]['failure_cases'][0]
    assert case['input']=='fee(3, 100)' and case['actual']=='-97' and case['expected']=='300'
    assert case['requirement_refs']==['REQ-UPLOAD']
    assert source_manifest(ws.subject_path(baseline))==manifest
    from nexus.execution.delivery import DeliveryService
    candidate=next(e['selected_candidate_id'] for e in store.records(task.id,'event') if 'selected_candidate_id' in e)
    delivery=DeliveryService(store);acceptance=delivery.accept(candidate,delivery.check_set_hash(candidate),actor_id='TEST_FIXTURE')
    exported=delivery.export(candidate,acceptance.id)
    with zipfile.ZipFile(tmp_path/exported['download_ref']) as z:
        assert z.read('evidence/upload-original.cj')==source
        assert json.loads(z.read('evidence/upload.json'))['examples']==examples
        assert b'quantity * price' in z.read('project/src/uploaded.cj')
