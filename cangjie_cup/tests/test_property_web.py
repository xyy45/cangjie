"""Owner-scoped read-only property report through the existing candidate route."""
import asyncio
import io
import json
import pytest

from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.contracts import CandidateProposal,CheckResult,file_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.store import uid
from nexus.repair.property_service import PropertyService
from tests.test_property_uploads import SOURCE
from tests.test_property_contract import raw,EXAMPLES
from tests.test_property_service import sdk
from tests.test_upload_routes import page


def test_property_report_is_read_only_actor_bound_and_tamper_is_unknown(tmp_path,monkeypatch):
    app,alice,headers=page(tmp_path)
    upload=alice.post('/api/uploads/repair',data={'file':(io.BytesIO(SOURCE),'refund.cj'),'goal':'退款不得超过实付','request_key':'property'},headers=headers).json
    frozen=alice.post('/api/uploads/repair/'+upload['id']+'/confirm',json=dict(expected_version=1,function='refundState',examples_json=json.dumps(EXAMPLES),properties_json=json.dumps(raw()),consent=True),headers=headers)
    assert frozen.status_code==200
    rd=alice.post('/api/requirements/drafts',json={'project':upload['id'],'goal':upload['goal']},headers=headers).json
    spec=alice.post('/api/requirements/drafts/'+rd['id']+'/confirm',json=dict(schema_version=1,expected_version=1,requirements=rd['requirements'],allowed_paths=rd['allowed_paths']),headers=headers).json
    task=alice.post('/api/tasks',json={'project':upload['id'],'spec_id':spec['id'],'idempotency_key':'property-task'},headers=headers).json
    store=app.extensions['upload_service'].store;ws=WorkspaceStore(store.root);current=store.get_task(task['id'])
    original=ws.read_file(current.baseline_id,'src/uploaded.cj')
    c=ws.apply_candidate(current,CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original+'\n// candidate\n')],requirement_refs=['REQ-UPLOAD']))
    url='/api/candidates/'+c.id
    missing=alice.get(url);assert missing.status_code==200 and missing.json['properties']['state']=='UNKNOWN'
    calls=sdk(monkeypatch,good=True)
    _,tree,plan=CangjieVerifier(store.root,task['id']).identity(c.id)
    store.append_record(task['id'],'check',CheckResult(id=uid(),subject_id=c.id,kind='test',state='PASS',tree_hash=tree,plan_hash=plan,diagnostics='EXPLICIT PUBLIC FIXTURE').model_dump())
    report=asyncio.run(PropertyService(store).run(c.id));assert report['state']=='PASS'
    before=len(calls);response=alice.get(url)
    assert response.json['properties']['binding']==report['binding'] and response.json['properties']['state']=='PASS' and len(calls)==before
    snapshot=alice.get('/api/tasks/'+task['id']).json
    assert next(r for r in snapshot['candidates'] if r['id']==c.id)['properties']['state']=='PASS'
    bob=app.test_client();bob.get('/')
    assert bob.get(url).status_code==404
    assert alice.post(url+'/properties',json={},headers=headers).status_code in (404,405)
    (store.root/report['batches'][0]['log_ref']).write_text('forged')
    invalid=alice.get(url);assert invalid.status_code==200 and invalid.json['properties']['state']=='UNKNOWN'
    assert invalid.json['check_set_hash'] is None and len(calls)==before
    changed=alice.get('/api/tasks/'+task['id']).json
    assert next(r for r in changed['candidates'] if r['id']==c.id)['properties']['state']=='UNKNOWN'
    assert next(e for e in changed['events'] if e['type']=='PROPERTY_FINISHED')['properties']['state']=='PASS'


def test_property_presentation_preserves_int64_values_without_mutating_evidence():
    import importlib.util
    assert importlib.util.find_spec('nexus.web.property_view') is not None,'canonical property presentation missing'
    from nexus.web.property_view import primitive_text
    original=dict(failure=dict(kind='business_property',args=[2**63-2,False],actual_return=2**63-1),flag=dict(actual_return=False,args=[]))
    shown=primitive_text(original)
    assert shown['failure']['args_text']=='[9223372036854775806,false]'
    assert shown['failure']['actual_return_text']=='9223372036854775807'
    assert shown['flag']['actual_return_text']=='false' and shown['flag']['args_text']=='[]'
    assert shown['failure']['actual_return']==original['failure']['actual_return']
    assert 'actual_return_text' not in original['failure']


@pytest.mark.parametrize('field',['precondition','assertion'])
def test_unhashable_property_expression_is_http400_without_freezing(tmp_path,field):
    app,client,headers=page(tmp_path)
    uploaded=client.post('/api/uploads/repair',data={'file':(io.BytesIO(SOURCE),'refund.cj'),'goal':'合法退款','request_key':'bad-expression'},headers=headers).json
    value=raw();value['properties'][0][field]=[]
    response=client.post('/api/uploads/repair/'+uploaded['id']+'/confirm',json=dict(expected_version=1,function='refundState',examples_json=json.dumps(EXAMPLES),properties_json=json.dumps(value),consent=True),headers=headers)
    assert response.status_code==400 and response.json['code']=='UPLOAD_INPUT_INVALID'
    assert client.get('/api/uploads/repair/'+uploaded['id']).json['status']=='DRAFT'
