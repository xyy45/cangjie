"""Object upload confirmation and field-wise generated public tests, no SDK."""
import json
from copy import deepcopy
import pytest
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.contracts import source_manifest
from tests.test_object_language import source
from tests.test_object_projects import project


def tagged(amount,items=None,kind='OrderState'):
    return {'$type':kind,'fields':{'amount':amount,'items':[] if items is None else items}}


def examples(kind='OrderState'):
    return [dict(args=[tagged(10,[1,2],kind),3],expected=tagged(7,[1,2],kind),suite='target'),dict(args=[tagged(0,[],kind),0],expected=tagged(0,[],kind),suite='regression')]


@pytest.mark.parametrize('kind',['struct','class'])
def test_object_confirm_generates_single_call_field_assertions_and_frozen_raw_json(tmp_path,kind):
    uploads=UploadService(RunStore(tmp_path));draft=uploads.prepare('object.cj',source(kind).encode(),'返回扣减后的新对象',actor_id='alice',request_key='one')
    raw=json.dumps(examples(),ensure_ascii=False,indent=2);confirmed=uploads.confirm(draft['id'],expected_version=1,function='apply',examples_json=raw,consent=True,actor_id='alice')
    root=uploads.source(draft['id'],actor_id='alice');text=(root/'src/cases_test.cj').read_text()
    assert text.count(confirmed['public_test_target']+'(')==2 and '.amount' in text and '.items.size' in text
    assert '= apply\n' in text
    assert '.items[0]' in text and '.items[1]' in text and 'if (' in text
    assert '@Expect(apply(' not in text and confirmed['examples_json']==raw
    manifest=source_manifest(root);assert uploads.confirm(draft['id'],expected_version=1,function='apply',examples_json=raw,consent=True,actor_id='alice')==confirmed
    assert source_manifest(root)==manifest
    with pytest.raises(LookupError):uploads.get(draft['id'],actor_id='bob')
    changed=deepcopy(examples());changed[0]['expected']['fields']['amount']=8
    with pytest.raises(ValueError):uploads.confirm(draft['id'],expected_version=1,function='apply',examples_json=json.dumps(changed),consent=True,actor_id='alice')


def test_object_public_test_class_avoids_declared_name_and_suite_ids_follow_it(tmp_path):
    uploads=UploadService(RunStore(tmp_path));text=source('class').replace('OrderState','UploadedTests');draft=uploads.prepare('object.cj',text.encode(),'返回新对象',actor_id='alice',request_key='one');raw=json.dumps(examples('UploadedTests'))
    result=uploads.confirm(draft['id'],expected_version=1,function='apply',examples_json=raw,consent=True,actor_id='alice');assert result['public_test_class']!='UploadedTests'
    profile=uploads.profile(draft['id']);assert profile['suite_tests']=={'target':[result['public_test_class']+'.case0'],'regression':[result['public_test_class']+'.case1']}
    root=uploads.source(draft['id'],actor_id='alice');assert 'class '+result['public_test_class']+' {' in (root/'src/cases_test.cj').read_text()


def test_object_project_confirm_preserves_original_projected_cases_and_edit_scope(tmp_path):
    files=project();uploads=UploadService(RunStore(tmp_path));draft=uploads.prepare_project('objects',None,'修复状态方法',actor_id='alice',request_key='one',entries=files)
    uploads.confirm(draft['id'],expected_version=1,function='apply',examples_json=json.dumps(examples()),allowed_paths=['src/state.cj'],consent=True,actor_id='alice')
    root=uploads.source(draft['id'],actor_id='alice');assert (root/'src/cases_test.cj').read_bytes()==files['src/cases_test.cj']
    assert '.amount' in (root/'src/nexus_uploaded_test.cj').read_text()
    profile=uploads.profile(draft['id']);assert profile['allowed_paths']==['src/state.cj']
    assert set(profile['suite_tests']['regression'])=={'UploadedTests.case1','Cases.amount','Cases.items'}


def test_object_project_workspace_preserves_frozen_declarations_and_allowed_paths(tmp_path):
    from nexus.contracts import CandidateProposal,file_hash
    from nexus.execution.workspace import WorkspaceStore
    from nexus.requirements.service import RequirementService
    uploads=UploadService(RunStore(tmp_path));draft=uploads.prepare_project('objects',None,'修复状态方法',actor_id='alice',request_key='one',entries=project())
    uploads.confirm(draft['id'],expected_version=1,function='apply',examples_json=json.dumps(examples()),allowed_paths=['src/state.cj'],consent=True,actor_id='alice')
    source_root=uploads.source(draft['id'],actor_id='alice');ws=WorkspaceStore(tmp_path,registered=[source_root]);baseline=ws.import_project(source_root,'.')
    requirements=RequirementService(uploads.store);request=requirements.prepare_requirement(draft['id'],'修复状态方法')
    spec=requirements.confirm_requirement(request['id'],dict(schema_version=1,expected_version=1,requirements=request['requirements'],allowed_paths=request['allowed_paths']),actor_id='alice')
    task=requirements.prepare_task(draft['id'],spec.id,baseline)
    with uploads.store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/state.cj')
    def apply(content):return ws.apply_candidate(task,CandidateProposal(edits=[dict(path='src/state.cj',before_hash=file_hash(original),content=content)],requirement_refs=['REQ-UPLOAD']))
    candidate=apply(original.replace('this.amount - n','this.amount - n - 1'));assert ws.read_file(candidate.id,'src/cases_test.cj')==ws.read_file(baseline,'src/cases_test.cj')
    for content in (original.replace('public class','public struct'),original.replace('refund(n: Int64)','refund(quantity: Int64)').replace('amount - n','amount - quantity')):
        with pytest.raises(ValueError):apply(content)
