"""Real SDK/native gate + deterministic model HTTP responses; no paid AI calls."""
import asyncio
import json
import zipfile

import httpx
import pytest

from nexus.contracts import file_hash
from nexus.demo.deepseek import DeepSeekProvider
from nexus.execution.delivery import DeliveryService
from nexus.execution.workspace import WorkspaceStore
from nexus.projects.index import inspect_project
from nexus.repair.cegis_loop import RepairLoop
from nexus.requirements.service import RequirementService
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_project_service import EXAMPLES,payload
from tests.test_project_index import project

pytestmark=pytest.mark.sdk


@pytest.mark.parametrize('with_focus',[False,True])
def test_two_file_project_repair_public_failure_then_independent_counterexample_then_delivery(tmp_path,monkeypatch,with_focus):
    files=project();files['src/order.cj']=files['src/order.cj'].replace(b'+ 100',b'+ 101')
    store=RunStore(tmp_path);uploads=UploadService(store)
    d=uploads.prepare_project('billing.zip',payload(files),'fee返回输入，total返回输入加100',actor_id='TEST_FIXTURE',request_key='new-project')
    contract=dict(version=1,function='total',domains={'x':dict(min=0,max=8,points=[3])},expression='x + 100',seed=7,max_cases=32)
    uploads.confirm(d['id'],expected_version=1,function='total',examples_json=json.dumps(EXAMPLES),oracle_json=json.dumps(contract),consent=True,actor_id='TEST_FIXTURE')
    root=uploads.source(d['id'],actor_id='TEST_FIXTURE');ws=WorkspaceStore(tmp_path,registered=[root]);baseline=ws.import_project(root,'.')
    req=RequirementService(store);draft=req.prepare_requirement(d['id'],d['goal'])
    spec=req.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=1,requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='TEST_FIXTURE')
    task=req.prepare_task(d['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    captured=[];real=httpx.AsyncClient
    for key,value in dict(DEEPSEEK_API_KEY='fixture-only',DEEPSEEK_BASE_URL='https://fixture.invalid',DEEPSEEK_MODEL='test-model').items():monkeypatch.setenv(key,value)
    def reply(request):
        context=json.loads(json.loads(request.content)['messages'][1]['content']);captured.append(context)
        fee=context['files']['src/fee.cj']['content'];order=context['files']['src/order.cj']['content']
        edits=[dict(path='src/fee.cj',before_hash=file_hash(fee),content=fee.replace('x + 1','x'))]
        if len(captured)>1:
            expression='if (x <= 2) { fee(x) + 100 } else { fee(x) + 101 }' if len(captured)==2 else 'fee(x) + 100'
            edits.append(dict(path='src/order.cj',before_hash=file_hash(order),content=order.replace('fee(x) + 101',expression)))
        refs=[t['evidence_id'] for f in context.get('analysis',{}).get('files',[]) for t in f['tools'] if t.get('included') and t['status']=='VALID'][:1]
        value=dict(schema_version=1,summary='fixture',suggestions=[dict(path=e['path'],reason='fixture') for e in edits],analysis_refs=refs,proposal=dict(edits=edits,requirement_refs=['REQ-UPLOAD']))
        return httpx.Response(200,json=dict(model='test-model',usage=dict(prompt_tokens=10,completion_tokens=10,total_tokens=20),choices=[dict(finish_reason='stop',message=dict(content=json.dumps(value)))]))
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:real(transport=httpx.MockTransport(reply),**kw))
    kwargs={}
    if with_focus:
        from nexus.repair.focus_service import FocusService
        from nexus.analysis.repair import RepairAnalysis
        from nexus.analysis.service import AnalysisService
        from tests.analysis.test_repair_localization import GraphTransport
        assert hasattr(FocusService,'enrich'),'per-round focus hook missing'
        kwargs=dict(focus_enricher=FocusService(store).enrich,context_enricher=RepairAnalysis(store,AnalysisService(tmp_path,client_factory=GraphTransport)).enrich)
    result=asyncio.run(RepairLoop(store,provider_factory=DeepSeekProvider,**kwargs).run(task.id))
    assert result.status=='REVIEW_PENDING',store.records(task.id,'event')[-1]
    assert len(captured)==3
    assert captured[0]['upload_constraints']['analysis_scope']=='PER_FILE'
    assert captured[1]['feedback'][0]['failure_cases'][0]['kind']=='test'
    assert captured[2]['feedback'][-1]['failure_cases'][0]['kind']=='independent_rule'
    assert captured[2]['feedback'][-1]['failure_cases'][0]['args']==[3]
    assert 'verification/oracle.json' not in captured[0]['files']
    if with_focus:
        assert [c['repair_focus']['binding']['for_round'] for c in captured]==[1,2,3]
        for context in captured:
            focus=context['repair_focus'];assert focus['binding']['baseline_id']==baseline
            assert len(json.dumps(focus,ensure_ascii=False).encode())<=16384
            assert focus['targets'] and all(f['coordinate_subject_id']==baseline for t in focus['targets'] for f in t['locations'])
            assert focus['targets'][0]['locations'][0]['anchors'][0]['slice']['status']=='VALID'
        assert captured[1]['repair_focus']['binding']['subject_id']==captured[1]['feedback'][-1]['previous_candidate_id']
        assert captured[2]['repair_focus']['targets'][0]['args']==[3]
    selected=next(e['selected_candidate_id'] for e in store.records(task.id,'event') if 'selected_candidate_id' in e)
    from nexus.repair.exploration import ExplorationService
    search=ExplorationService(store).verify(selected)
    assert search['state']=='PASS' and search['regression_cases']>=1
    for batch in search['batches']:
        assert {'src/fee.cj','src/order.cj'}<=set(batch['project_manifest'])
    delivery=DeliveryService(store);acceptance=delivery.accept(selected,delivery.check_set_hash(selected),actor_id='TEST_FIXTURE')
    exported=delivery.export(selected,acceptance.id)
    with zipfile.ZipFile(tmp_path/exported['download_ref']) as z:
        for path in inspect_project(files)['frozen_manifest']:assert z.read('project/'+path)==files[path]
        for path,data in files.items():assert z.read('evidence/upload-original/'+path)==data
        assert b'x + 1' not in z.read('project/src/fee.cj')
        assert b'+ 100' in z.read('project/src/order.cj')
        assert json.loads(z.read('evidence/upload.json'))['kind']=='PROJECT'
        if with_focus:assert len(json.loads(z.read('evidence/localization.json'))['reports'])==3
    if with_focus:
        event=next(e for e in store.records(task.id,'event') if e['type']=='LOCALIZATION_CONTEXT')
        event_path=store.root/'records'/ (event['event_id']+'.json');original=event_path.read_bytes();raw=json.loads(original)
        raw['data']['localization']['targets'][0]['actual']='forged';event_path.write_text(json.dumps(raw))
        with pytest.raises(ValueError):delivery.check_set_hash(selected)
        event_path.write_bytes(original)
    probe=store.root/search['batches'][0]['project_path']/'src/fee.cj';probe.write_text('tampered')
    with pytest.raises(ValueError):ExplorationService(store).verify(selected)
