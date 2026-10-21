"""Real SDK, native policy and MCP; model HTTP is deterministic test data, not LIVE AI evidence."""
import asyncio
import json
import httpx
import pytest
from nexus.contracts import file_hash, source_manifest
from nexus.demo.deepseek import DeepSeekProvider
from nexus.execution.workspace import WorkspaceStore
from nexus.repair.cegis_loop import RepairLoop
from nexus.requirements.service import RequirementService
from nexus.scenarios import ROOT, get_profile
from nexus.store import RunStore

pytestmark=pytest.mark.sdk


def test_failed_mcp_candidate_drives_next_deepseek_request_and_accumulated_edits(tmp_path,monkeypatch):
    source=ROOT/get_profile('cross-validation')['source']
    ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.')
    store=RunStore(tmp_path);service=RequirementService(store)
    draft=service.prepare_requirement('cross-validation','修复数量校验与计费')
    spec=service.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=1,
        requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='TEST_FIXTURE')
    task=service.prepare_task('cross-validation',spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    frozen=source_manifest(ws.subject_path(baseline));requests=[]
    for k,v in dict(DEEPSEEK_API_KEY='test-only',DEEPSEEK_BASE_URL='https://model.example',DEEPSEEK_MODEL='test-model').items():
        monkeypatch.setenv(k,v)
    real_client=httpx.AsyncClient
    def reply(request):
        context=json.loads(json.loads(request.content)['messages'][1]['content']);requests.append(context)
        edits=[]
        replacements={'src/quantity.cj':('quantity >= 0','quantity >= 1')}
        if len(requests)>1:replacements['src/fee.cj']=('quantity + unitPrice','quantity * unitPrice')
        for path,(old,new) in replacements.items():
            original=context['files'][path]['content']
            edits.append(dict(path=path,before_hash=file_hash(original),content=original.replace(old,new)))
        payload=dict(schema_version=1,summary='测试夹具提案',suggestions=[dict(path=e['path'],reason='测试夹具') for e in edits],
            proposal=dict(edits=edits,requirement_refs=[r.id for r in spec.requirements]))
        return httpx.Response(200,json=dict(model='test-model',usage=dict(prompt_tokens=100,completion_tokens=50,total_tokens=150),
            choices=[dict(finish_reason='stop',message=dict(content=json.dumps(payload)))]))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kwargs:real_client(transport=httpx.MockTransport(reply),**kwargs))
    result=asyncio.run(RepairLoop(store,provider_factory=DeepSeekProvider).run(task.id))
    assert result.status=='REVIEW_PENDING',store.records(task.id,'event')[-1]
    assert len(requests)==2 and result.attempt_count==2
    previous=requests[1]['feedback'][0]
    candidates=store.records(task.id,'candidate')
    checks=store.records(task.id,'check')
    assert previous['previous_candidate_id']==candidates[0]['id']
    assert previous['tree_hash']==candidates[0]['tree_hash']
    assert previous['failed_checks'][0]['state']=='FAIL'
    assert 'FAIL' in previous['diagnostic_snippets'][0]['text']
    cases={item['test_id']:item for item in previous['failure_cases']}
    assert cases['ValidationTests.multiply']['input']=='calculateFee(3, 100)'
    assert cases['ValidationTests.multiply']['actual']=='103' and cases['ValidationTests.multiply']['expected']=='300'
    assert cases['ValidationTests.multiply']['mapping_basis']=='TEST_SUITE'
    event=next(e['repair_feedback'] for e in store.records(task.id,'event') if 'repair_feedback' in e)
    assert previous['failure_cases']==event['failure_cases']
    assert previous['edited_files'][0]['content']==candidates[0]['edits'][0]['content']
    assert requests[0]['files']==requests[1]['files']
    assert requests[1]['iteration']['round']==2
    assert {e['path'] for e in candidates[1]['edits']}=={'src/quantity.cj','src/fee.cj'}
    assert next(c for c in checks if c['subject_id']==candidates[0]['id'] and c['kind']=='test')['state']=='FAIL'
    assert all(c['state']=='PASS' for c in checks if c['subject_id']==candidates[1]['id'])
    assert source_manifest(ws.subject_path(baseline))==frozen
    assert not store.records(task.id,'acceptance')
    # Both requests remain durably spent, even across provider reconstruction.
    with store.connect() as db:assert db.execute('SELECT COUNT(*) FROM demo_model_rounds WHERE task_id=?',(task.id,)).fetchone()[0]==2
