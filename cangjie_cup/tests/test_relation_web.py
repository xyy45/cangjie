"""Read-only paired reports use verified state and lossless display text."""
import asyncio
import io
import json
import pytest

from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.contracts import CandidateProposal,CheckResult,file_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.repair.relation_service import RelationService
from nexus.store import uid
from tests.test_relation_uploads import SOURCE
from tests.test_relations import raw,EXAMPLES
from tests.test_relation_service import sdk,record_public
from tests.test_upload_routes import page


@pytest.mark.parametrize('tamper',['relation-log','public-log','public-report'])
def test_relation_candidate_and_task_reads_are_owner_bound_verified_and_never_execute(tmp_path,monkeypatch,tamper):
    app,alice,headers=page(tmp_path)
    upload=alice.post('/api/uploads/repair',data={'file':(io.BytesIO(SOURCE),'amount.cj'),'goal':'增加数量总额不得下降','request_key':'relation'},headers=headers).json
    frozen=alice.post('/api/uploads/repair/'+upload['id']+'/confirm',json=dict(expected_version=1,function='amount',examples_json=json.dumps(EXAMPLES),relations_json=json.dumps(raw()),consent=True),headers=headers)
    assert frozen.status_code==200
    rd=alice.post('/api/requirements/drafts',json=dict(project=upload['id'],goal=upload['goal']),headers=headers).json
    spec=alice.post('/api/requirements/drafts/'+rd['id']+'/confirm',json=dict(schema_version=1,expected_version=1,requirements=rd['requirements'],allowed_paths=rd['allowed_paths']),headers=headers).json
    task=alice.post('/api/tasks',json=dict(project=upload['id'],spec_id=spec['id'],idempotency_key='relation-task'),headers=headers).json
    store=app.extensions['upload_service'].store;ws=WorkspaceStore(store.root);current=store.get_task(task['id']);original=ws.read_file(current.baseline_id,'src/uploaded.cj')
    c=ws.apply_candidate(current,CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original+'\n// candidate\n')],requirement_refs=['REQ-UPLOAD']))
    url='/api/candidates/'+c.id;missing=alice.get(url)
    assert missing.status_code==200 and missing.json['relations']['state']=='UNKNOWN'
    calls=sdk(monkeypatch,good=True);_,tree,plan=CangjieVerifier(store.root,task['id']).identity(c.id)
    record_public(store,ws,current,c)
    report=asyncio.run(RelationService(store).run(c.id));assert report['state']=='PASS';before=len(calls)
    response=alice.get(url);assert response.json['relations']['binding']==report['binding'] and response.json['relations']['state']=='PASS' and len(calls)==before
    snapshot=alice.get('/api/tasks/'+task['id']).json;assert next(r for r in snapshot['candidates'] if r['id']==c.id)['relations']['state']=='PASS'
    bob=app.test_client();bob.get('/');assert bob.get(url).status_code==404 and bob.get('/api/tasks/'+task['id']).status_code==404
    assert alice.post(url+'/relations',json={},headers=headers).status_code in (404,405)
    public=store.records(task['id'],'check')[-1]
    ref=report['batches'][0]['log_ref'] if tamper=='relation-log' else public['log_ref'] if tamper=='public-log' else public['report_ref']
    (store.root/ref).write_text('forged')
    invalid=alice.get(url);assert invalid.status_code==200 and invalid.json['relations']['state']=='UNKNOWN'
    assert invalid.json['check_set_hash'] is None and len(calls)==before
    snapshot=alice.get('/api/tasks/'+task['id']).json
    assert next(r for r in snapshot['candidates'] if r['id']==c.id)['relations']['state']=='UNKNOWN'
    assert next(e for e in snapshot['events'] if e['type']=='RELATION_FINISHED')['relations']['state']=='PASS'


def test_relation_display_text_preserves_each_int64_and_bool_without_mutating_records():
    from nexus.web.property_view import primitive_text
    source=dict(failure=dict(left_args=[2**63-2,False],right_args=[2**63-1,True],left_actual_return=2**63-2,right_actual_return=2**63-1),
        nested=dict(left=dict(args=[],actual_return=False),right=dict(args=[],actual_return=True)))
    shown=primitive_text(source)['failure']
    assert shown['left_args_text']=='[9223372036854775806,false]' and shown['right_args_text']=='[9223372036854775807,true]'
    assert shown['left_actual_return_text']=='9223372036854775806' and shown['right_actual_return_text']=='9223372036854775807'
    assert source['failure']['left_actual_return']==2**63-2 and 'left_actual_return_text' not in source['failure']
    assert primitive_text(source)['nested']['left']['actual_return_text']=='false'
