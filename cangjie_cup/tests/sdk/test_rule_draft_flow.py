"""Real pinned SDK/core2; HTTP generation and repair providers are labelled fixtures."""
import asyncio
import json
import zipfile
from copy import deepcopy

import httpx
import pytest

from nexus.contracts import CandidateProposal,source_manifest
from nexus.demo.rule_draft_provider import RuleDraftProvider
from nexus.execution.delivery import DeliveryService
from nexus.execution.workspace import WorkspaceStore
from nexus.repair.cegis_loop import RepairLoop
from nexus.repair.exploration import ExplorationService
from nexus.requirements.service import RequirementService
from nexus.store import RunStore
from nexus.uploads.rule_drafts import RuleDraftService
from nexus.uploads.service import UploadService
from tests.test_rule_drafts import SOURCE,suggestion
from tests.test_project_service import prepare as prepare_project

pytestmark=pytest.mark.sdk


@pytest.mark.parametrize('project',[False,True],ids=['single-file','two-file-project'])
def test_generated_rule_confirmed_then_repaired_verified_and_archived(tmp_path,monkeypatch,project):
    for key,value in dict(DEEPSEEK_API_KEY='fixture-draft-key',DEEPSEEK_BASE_URL='https://model.example',DEEPSEEK_MODEL='draft-model').items():monkeypatch.setenv(key,value)
    store=RunStore(tmp_path);uploads=UploadService(store)
    upload=prepare_project(uploads) if project else uploads.prepare('fee.cj',SOURCE,'quantity与price均在0..1000，返回二者乘积',actor_id='alice',request_key='upload')
    payload=suggestion();function='total' if project else 'fee';paths=['src/fee.cj','src/order.cj'] if project else None
    if project:
        payload['examples']=[dict(args=[2],expected=102,suite='target'),dict(args=[0],expected=100,suite='regression')]
        payload['oracle']=dict(version=1,function='total',domains={'x':dict(min=0,max=1000,points=[0,1,2])},expression='x + 100',seed=0,max_cases=32)
    wire=[]
    def response(request):
        body=json.loads(request.content);context=json.loads(body['messages'][1]['content']);wire.append(context)
        assert set(context['files'])==({'src/fee.cj','src/order.cj'} if project else {'src/uploaded.cj'})
        assert not any('_test.cj' in p or 'verification/' in p or p=='cjpm.toml' for p in context['files'])
        return httpx.Response(200,json=dict(model='draft-model',usage=dict(prompt_tokens=100,completion_tokens=50,total_tokens=150),choices=[dict(finish_reason='stop',message={'content':json.dumps(payload)})]))
    drafts=RuleDraftService(store,provider_factory=lambda:RuleDraftProvider(transport=httpx.MockTransport(response)))
    job=drafts.create(upload['id'],actor_id='alice',expected_version=1,function=function,allowed_paths=paths,request_key='generate',consent=True)
    drafts.run(job['id']);preview=drafts.apply_preview(job['id'],actor_id='alice',expected_version=1,function=function,allowed_paths=paths)
    uploaded=uploads.confirm(upload['id'],actor_id='alice',expected_version=1,function=function,examples_json=preview['examples_json'],oracle_json=preview['oracle_json'],rule_draft_ref=preview['rule_draft_ref'],allowed_paths=paths,consent=True)
    assert len(wire)==1 and uploaded['rule_draft_provenance']['origin']=='HTTP_FIXTURE_NOT_LIVE'
    root=uploads.source(upload['id'],actor_id='alice');ws=WorkspaceStore(store.root,registered=[root]);baseline=ws.import_project(root,'.');frozen=source_manifest(ws.subject_path(baseline))
    requirements=RequirementService(store);draft=requirements.prepare_requirement(upload['id'],upload['goal'])
    spec=requirements.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=1,requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='TEST_FIXTURE')
    task=requirements.prepare_task(upload['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    captured=[]
    class RepairFixture:
        def __init__(self,*args):pass
        async def propose(self,context):
            captured.append(context)
            assert not any(p.startswith('verification/') for p in context['files'])
            path='src/fee.cj' if project else 'src/uploaded.cj';old=context['files'][path]
            code=old['content'].replace('x + 1','x') if project else old['content'].replace('quantity + price','quantity * price')
            return CandidateProposal(edits=[dict(path=path,before_hash=old['file_hash'],content=code)],requirement_refs=['REQ-UPLOAD'])
    result=asyncio.run(RepairLoop(store,provider_factory=RepairFixture).run(task.id))
    assert result.status=='REVIEW_PENDING',store.records(task.id,'event')[-1]
    candidate=store.records(task.id,'candidate')[-1];search=ExplorationService(store).verify(candidate['id'])
    assert search['state']=='PASS' and search['native_boundary'] and len(captured)==1
    assert source_manifest(ws.subject_path(baseline))==frozen
    delivery=DeliveryService(store);accepted=delivery.accept(candidate['id'],delivery.check_set_hash(candidate['id']),actor_id='TEST_FIXTURE')
    archive=delivery.export(candidate['id'],accepted.id)
    with zipfile.ZipFile(store.root/archive['download_ref']) as z:
        proof=json.loads(z.read('project/verification/rule-draft/provenance.json'))
        assert proof['rule_draft_id']==job['id'] and proof['business_verified'] is False
        assert z.read('project/verification/rule-draft/response.json')==(drafts.directory(job['id'])/'response.json').read_bytes()
        assert 'fixture-draft-key' not in z.read('project/verification/rule-draft/response.json').decode()
        if project:assert z.read('project/src/order.cj')==(root/'src/order.cj').read_bytes()
