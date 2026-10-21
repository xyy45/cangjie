import json
import pytest
from nexus.store import RunStore
from nexus.contracts import CandidateProposal,file_hash
from nexus.execution.workspace import WorkspaceStore

SOURCE=b'package usercalc\r\npublic func fee(quantity: Int64, price: Int64): Int64 {\r\n    quantity + price\r\n}\r\n'
EXAMPLES=[dict(args=[3,100],expected=300,suite='target'),dict(args=[1,0],expected=0,suite='regression')]


def service(tmp_path):
    from nexus.uploads.service import UploadService
    return UploadService(RunStore(tmp_path))


def test_prepare_confirm_preserves_source_bytes_and_freezes_data_derived_tests(tmp_path):
    upload=service(tmp_path)
    draft=upload.prepare('pricing.cj',SOURCE,'费用应为数量乘单价',actor_id='alice',request_key='prepare')
    assert draft['status']=='DRAFT' and draft['functions'][0]['name']=='fee'
    confirmed=upload.confirm(draft['id'],expected_version=1,function='fee',examples_json=json.dumps(EXAMPLES),consent=True,actor_id='alice')
    profile=upload.profile(draft['id']);source=upload.source(draft['id'],actor_id='alice')
    assert confirmed['status']=='CONFIRMED' and profile['allowed_paths']==['src/uploaded.cj']
    assert (source/'src/uploaded.cj').read_bytes()==SOURCE
    tests=(source/'src/cases_test.cj').read_text()
    assert '@Expect(fee(3, 100), 300)' in tests and '@Expect(fee(1, 0), 0)' in tests
    assert profile['suite_tests']=={'target':['UploadedTests.case0'],'regression':['UploadedTests.case1']}
    assert upload.confirm(draft['id'],expected_version=1,function='fee',examples_json=json.dumps(EXAMPLES),consent=True,actor_id='alice')==confirmed
    with pytest.raises(ValueError):upload.confirm(draft['id'],expected_version=1,function='fee',examples_json=json.dumps(EXAMPLES[::-1]),consent=True,actor_id='alice')


def test_upload_ownership_preparation_idempotency_and_project_tamper(tmp_path):
    upload=service(tmp_path);draft=upload.prepare('pricing.cj',SOURCE,'计算费用',actor_id='alice',request_key='same')
    assert upload.prepare('pricing.cj',SOURCE,'计算费用',actor_id='alice',request_key='same')==draft
    with pytest.raises(ValueError):upload.prepare('pricing.cj',SOURCE,'改变需求',actor_id='alice',request_key='same')
    with pytest.raises(LookupError):upload.get(draft['id'],actor_id='bob')
    with pytest.raises(LookupError):upload.get(draft['id'],actor_id=None)
    with pytest.raises(ValueError):upload.source(draft['id'],actor_id='alice')
    with pytest.raises(ValueError):upload.confirm(draft['id'],expected_version=1,function='fee',examples_json=json.dumps(EXAMPLES),consent=False,actor_id='alice')
    upload.confirm(draft['id'],expected_version=1,function='fee',examples_json=json.dumps(EXAMPLES),consent=True,actor_id='alice')
    source=upload.source(draft['id'],actor_id='alice');(source/'src/cases_test.cj').write_text('forged')
    with pytest.raises(ValueError):upload.profile(draft['id'])


def test_uploaded_task_keeps_crlf_hash_and_blocks_unsafe_model_candidate(tmp_path):
    from nexus.requirements.service import RequirementService
    upload=service(tmp_path);draft=upload.prepare('pricing.cj',SOURCE,'计算费用',actor_id='alice',request_key='k')
    upload.confirm(draft['id'],expected_version=1,function='fee',examples_json=json.dumps(EXAMPLES),consent=True,actor_id='alice')
    source=upload.source(draft['id'],actor_id='alice');ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.')
    req=RequirementService(upload.store);prepared=req.prepare_requirement(draft['id'],'计算费用')
    spec=req.confirm_requirement(prepared['id'],dict(schema_version=1,expected_version=1,requirements=prepared['requirements'],allowed_paths=prepared['allowed_paths']),actor_id='alice')
    task=req.prepare_task(draft['id'],spec.id,baseline)
    with upload.store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/uploaded.cj');assert original.encode()==SOURCE
    for malicious in ('package usercalc\npublic func fee(quantity: Int64, price: Int64): Int64 { File.read(1) }',
                       'package usercalc\npublic func fee(quantity: Bool, price: Int64): Int64 { 1 }'):
        proposal=CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=malicious)],requirement_refs=['REQ-UPLOAD'])
        with pytest.raises(ValueError):ws.apply_candidate(task,proposal)
    good=CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original.replace('quantity + price','quantity * price'))],requirement_refs=['REQ-UPLOAD'])
    candidate=ws.apply_candidate(task,good)
    assert candidate.attempt==1 and len(upload.store.records(task.id,'candidate'))==1
