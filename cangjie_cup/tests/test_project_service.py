import io
import json
import zipfile

import pytest

from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_project_index import project
from tests.test_upload_routes import page

EXAMPLES=[dict(args=[2],expected=102,suite='target'),dict(args=[0],expected=100,suite='regression')]


def payload(files):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for path,data in files.items():z.writestr('billing/'+path,data)
    return stream.getvalue()


def prepare(service,key='one',files=None):
    assert hasattr(service,'prepare_project'),'project preparation is not wired to uploads'
    return service.prepare_project('billing.zip',payload(files or project()),'订单总额为输入加100，fee原样返回输入',actor_id='alice',request_key=key)


def confirm(service,draft,**extra):
    return service.confirm(draft['id'],expected_version=1,function='total',examples_json=json.dumps(EXAMPLES),consent=True,actor_id='alice',**extra)


def test_project_upload_keeps_all_original_files_and_test_ids_and_freezes_scope(tmp_path):
    service=UploadService(RunStore(tmp_path));draft=prepare(service)
    assert draft['kind']=='PROJECT' and draft['production_paths']==['src/fee.cj','src/order.cj']
    assert draft==prepare(service)
    with pytest.raises(LookupError):service.get(draft['id'],actor_id='bob')
    value=confirm(service,draft,allowed_paths=['src/fee.cj','src/order.cj'])
    source=service.source(draft['id'],actor_id='alice')
    for path,data in project().items():assert (source/path).read_bytes()==data
    profile=service.profile(draft['id'])
    assert profile['allowed_paths']==['src/fee.cj','src/order.cj']
    assert set(profile['suite_tests']['regression'])=={'UploadedTests.case1','BillingTests.amount','BillingTests.zero'}
    assert profile['context_visibility']['src/cases_test.cj']=='PUBLIC_TEST'
    assert (source/'src/nexus_uploaded_test.cj').is_file()
    assert len(service.case(draft['id'],actor_id='alice')['files'])==2
    assert confirm(service,draft,allowed_paths=['src/fee.cj','src/order.cj'])==value
    with pytest.raises(ValueError):confirm(service,draft,allowed_paths=['src/order.cj'])
    (source/'README.md').write_text('tampered')
    with pytest.raises(ValueError):service.profile(draft['id'])


def test_project_original_manifest_tamper_scope_and_request_reuse_are_rejected(tmp_path):
    service=UploadService(RunStore(tmp_path));draft=prepare(service)
    with pytest.raises(ValueError):prepare(service,files={**project(),'README.md':b'changed'})
    for paths in [[],['src/missing.cj'],['src/cases_test.cj'],['src/order.cj','src/order.cj']]:
        with pytest.raises(ValueError):confirm(service,draft,allowed_paths=paths)
    original=tmp_path/'uploads'/draft['id']/'original/src/fee.cj'
    original.write_text('changed')
    with pytest.raises(ValueError):service.get(draft['id'],actor_id='alice')


def test_project_candidates_validate_all_files_and_preserve_frozen_material(tmp_path):
    from nexus.contracts import CandidateProposal,file_hash
    from nexus.execution.workspace import WorkspaceStore
    from nexus.requirements.service import RequirementService
    service=UploadService(RunStore(tmp_path));draft=prepare(service);confirm(service,draft)
    source=service.source(draft['id'],actor_id='alice');ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.')
    req=RequirementService(service.store);d=req.prepare_requirement(draft['id'],draft['goal'])
    spec=req.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='alice')
    task=req.prepare_task(draft['id'],spec.id,baseline)
    with service.store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/fee.cj')
    def proposal(code):return CandidateProposal(edits=[dict(path='src/fee.cj',before_hash=file_hash(original),content=code)],requirement_refs=['REQ-UPLOAD'])
    with pytest.raises(ValueError):ws.apply_candidate(task,proposal(original.replace('fee(x: Int64)','fee(x: Bool)')))
    candidate=ws.apply_candidate(task,proposal(original.replace('x + 1','x')))
    assert candidate.attempt==1 and candidate.edits[0].path=='src/fee.cj'


def test_project_zip_and_directory_routes_are_private_bounded_and_csrf_guarded(tmp_path):
    app,client,headers=page(tmp_path)
    body=lambda:dict(file=(io.BytesIO(payload(project())),'billing.zip'),goal='计算订单',request_key='zip')
    assert client.post('/api/uploads/repair/project',data=body()).status_code==403
    result=client.post('/api/uploads/repair/project',data=body(),headers=headers)
    assert result.status_code==201,result.json
    assert result.json['kind']=='PROJECT'
    data={'goal':'目录上传','request_key':'directory','paths_json':json.dumps(list(project())),'files':[(io.BytesIO(v),p.rsplit('/',1)[-1]) for p,v in project().items()]}
    directory=client.post('/api/uploads/repair/project',data=data,headers=headers)
    assert directory.status_code==201,directory.json
    assert directory.json['source_sha256']==result.json['source_sha256']
    invalid=client.post('/api/uploads/repair/project',data={'file':(io.BytesIO(b'bad'),'bad.zip'),'goal':'测试','request_key':'bad'},headers=headers)
    assert invalid.status_code==400 and invalid.json['code']=='UPLOAD_INPUT_INVALID'
    bob=app.test_client();bob.get('/')
    assert bob.get('/api/uploads/repair/'+result.json['id']).status_code==404
    assert bob.get('/api/uploads/repair').json['uploads']==[]


def test_original_zip_is_retained_and_bound_not_just_reconstructed_files(tmp_path):
    service=UploadService(RunStore(tmp_path));original=payload(project())
    draft=service.prepare_project('billing.zip',original,'计算订单',actor_id='alice',request_key='zip')
    raw=tmp_path/'uploads'/draft['id']/'original.zip'
    assert raw.is_file() and raw.read_bytes()==original
    raw.write_bytes(b'tampered')
    with pytest.raises(ValueError):service.get(draft['id'],actor_id='alice')


def test_reserved_generated_test_path_is_checked_case_insensitively(tmp_path):
    files=project();files['src/Nexus_uploaded_test.cj']=files.pop('src/cases_test.cj')
    with pytest.raises(ValueError):prepare(UploadService(RunStore(tmp_path)),files=files)


def test_project_route_accepts_legal_archive_larger_than_old_single_file_body_limit(tmp_path):
    _,client,headers=page(tmp_path);files=project();files['notes.md']=b'a'*(127*1024)
    archive=payload(files);assert len(archive)>131072
    result=client.post('/api/uploads/repair/project',data={'file':(io.BytesIO(archive),'billing.zip'),'goal':'计算订单','request_key':'large'},headers=headers)
    assert result.status_code==201,result.json


@pytest.mark.parametrize('limit',['count','bytes','missing-lock-rule'])
def test_confirmation_rejects_final_project_budget_overflow_before_freezing(tmp_path,limit):
    from nexus.projects.archive import MAX_FILE,MAX_TOTAL
    files=project()
    if limit=='count':files.update({f'note{i}.md':b'note' for i in range(94)})
    elif limit=='missing-lock-rule':
        del files['cjpm.lock'];files.update({f'note{i}.md':b'note' for i in range(94)})
    else:
        remaining=MAX_TOTAL-32-sum(len(x) for x in files.values());i=0
        while remaining:
            size=min(MAX_FILE,remaining);files[f'note{i}.md']=b'x'*size;remaining-=size;i+=1
    service=UploadService(RunStore(tmp_path))
    draft=service.prepare_project('目录工程',None,'计算订单',actor_id='alice',request_key='budget',entries=files) if limit=='bytes' else prepare(service,files=files)
    extra={}
    if limit=='missing-lock-rule':extra['oracle_json']=json.dumps(dict(version=1,function='total',domains={'x':dict(min=0,max=8)},expression='x+100',seed=7,max_cases=32))
    with pytest.raises(ValueError,match='预算'):confirm(service,draft,**extra)
    assert service.get(draft['id'],actor_id='alice')['status']=='DRAFT'
    assert not (tmp_path/'uploads'/draft['id']/'project').exists()
    assert not (tmp_path/'uploads'/draft['id']/'.project-staging').exists()


def test_final_budget_boundary_with_generated_lock_test_and_rule_is_importable(tmp_path):
    from nexus.contracts import source_manifest
    from nexus.execution.workspace import WorkspaceStore
    files=project();del files['cjpm.lock'];files.update({f'note{i}.md':b'note' for i in range(92)})
    service=UploadService(RunStore(tmp_path));draft=prepare(service,files=files)
    rule=json.dumps(dict(version=1,function='total',domains={'x':dict(min=0,max=8)},expression='x+100',seed=7,max_cases=32))
    confirm(service,draft,oracle_json=rule)
    root=service.source(draft['id'],actor_id='alice');assert len(source_manifest(root))==100
    ws=WorkspaceStore(tmp_path,registered=[root]);assert ws.import_project(root,'.').startswith('b_')
