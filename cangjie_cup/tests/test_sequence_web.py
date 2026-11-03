"""Sequence GET uses current evidence and exact primitive text; never executes."""
import asyncio
from copy import deepcopy
import io
import json

import pytest

from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.contracts import CandidateProposal,file_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.repair.sequence_service import SequenceService
from tests.test_sequence_uploads import SOURCE,EXAMPLES,sequence
from tests.test_sequence_service import sdk
from tests.test_relation_service import record_public
from tests.test_upload_routes import page

raw=sequence

@pytest.mark.parametrize('tamper',['sequence-log','public-log','public-report'])
def test_sequence_candidate_and_task_reads_are_owner_bound_verified_and_never_execute(tmp_path,monkeypatch,tamper):
    app,alice,headers=page(tmp_path)
    upload=alice.post('/api/uploads/repair',data={'file':(io.BytesIO(SOURCE),'refund.cj'),'goal':'累计退款封顶实付','request_key':'sequence'},headers=headers).json
    frozen=alice.post('/api/uploads/repair/'+upload['id']+'/confirm',json=dict(expected_version=1,function='refund',examples_json=json.dumps(EXAMPLES),sequences_json=json.dumps(raw()),consent=True),headers=headers)
    assert frozen.status_code==200
    rd=alice.post('/api/requirements/drafts',json=dict(project=upload['id'],goal=upload['goal']),headers=headers).json
    spec=alice.post('/api/requirements/drafts/'+rd['id']+'/confirm',json=dict(schema_version=1,expected_version=1,requirements=rd['requirements'],allowed_paths=rd['allowed_paths']),headers=headers).json
    task=alice.post('/api/tasks',json=dict(project=upload['id'],spec_id=spec['id'],idempotency_key='sequence-task'),headers=headers).json
    store=app.extensions['upload_service'].store;ws=WorkspaceStore(store.root);current=store.get_task(task['id']);original=ws.read_file(current.baseline_id,'src/uploaded.cj')
    c=ws.apply_candidate(current,CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original+'\n// candidate\n')],requirement_refs=['REQ-UPLOAD']))
    url='/api/candidates/'+c.id;missing=alice.get(url)
    assert missing.status_code==200 and missing.json['sequences']['state']=='UNKNOWN'
    calls=sdk(monkeypatch,good=True);_,tree,plan=CangjieVerifier(store.root,task['id']).identity(c.id)
    record_public(store,ws,current,c)
    report=asyncio.run(SequenceService(store).run(c.id));assert report['state']=='PASS';before=len(calls)
    response=alice.get(url);assert response.json['sequences']['binding']==report['binding'] and response.json['sequences']['state']=='PASS' and len(calls)==before
    snapshot=alice.get('/api/tasks/'+task['id']).json;assert next(r for r in snapshot['candidates'] if r['id']==c.id)['sequences']['state']=='PASS'
    bob=app.test_client();bob.get('/');assert bob.get(url).status_code==404 and bob.get('/api/tasks/'+task['id']).status_code==404
    assert alice.post(url+'/sequences',json={},headers=headers).status_code in (404,405)
    public=store.records(task['id'],'check')[-1]
    ref=report['batches'][0]['log_ref'] if tamper=='sequence-log' else public['log_ref'] if tamper=='public-log' else public['report_ref']
    (store.root/ref).write_text('forged')
    invalid=alice.get(url);assert invalid.status_code==200 and invalid.json['sequences']['state']=='UNKNOWN'
    assert invalid.json['check_set_hash'] is None and len(calls)==before
    snapshot=alice.get('/api/tasks/'+task['id']).json
    assert next(r for r in snapshot['candidates'] if r['id']==c.id)['sequences']['state']=='UNKNOWN'
    assert next(e for e in snapshot['events'] if e['type']=='SEQUENCE_FINISHED')['sequences']['state']=='PASS'



def test_all_primitive_sequence_states_and_vectors_have_lossless_display_text():
    from nexus.web.property_view import primitive_text
    value=dict(initial_state=2**63-2,before_state=2**63-2,reference_before=2**63-2,expected_state=2**63-1,actual_return=2**63-1,context=[2**63-1,True],args=[2**63-2,False],
        steps=[dict(initial_state=False,before_state=False,reference_before=False,expected_state=True,actual_return=True,args=[False],context=[])])
    before=deepcopy(value);shown=primitive_text(value)
    for field in ('initial_state','before_state','reference_before'):assert shown[field+'_text']=='9223372036854775806'
    assert shown['expected_state_text']=='9223372036854775807' and shown['actual_return_text']=='9223372036854775807'
    assert shown['context_text']=='[9223372036854775807,true]' and shown['args_text']=='[9223372036854775806,false]'
    assert shown['steps'][0]['initial_state_text']=='false' and shown['steps'][0]['expected_state_text']=='true'
    assert value==before
