"""Actual fixed SDK object public defects/reference fixes, not LLM evidence."""
import json
from copy import deepcopy
import pytest
from nexus.contracts import source_manifest
from nexus.projects.index import validate_project_candidate
from nexus.store import RunStore
from nexus.uploads.language import validate_candidate,inspect_source
from nexus.uploads.service import UploadService
from tests.sdk.test_string_public_sdk import execute
from tests.test_object_language import source
from tests.test_object_projects import project
from tests.test_object_uploads import examples

pytestmark=pytest.mark.sdk


def rich_source(kind):
    return source(kind).replace(' public init(', ' public let label: String\n public let active: Bool\n public init(',1).replace(
        'init(amount: Int64, items: Array<Int64>)','init(amount: Int64, items: Array<Int64>, label: String, active: Bool)').replace(
        '  this.items = items','  this.items = items\n  this.label = label\n  this.active = active').replace(
        'OrderState(this.amount - n, this.items)','OrderState(this.amount - n, this.items, this.label, this.active)')


@pytest.mark.parametrize('kind',['struct','class','collision','type-case0'])
def test_uploaded_object_public_defect_then_reference_fix(tmp_path,kind):
    good=rich_source('struct' if kind=='struct' else 'class');function='apply';type_name='OrderState'
    if kind=='collision':good=good.replace('OrderState','UploadedTests').replace('func apply(','func case0(');function='case0';type_name='UploadedTests'
    if kind=='type-case0':good=good.replace('OrderState','case0');type_name='case0'
    bad=good.replace('this.amount - n','this.amount + n');cases=examples(type_name)
    for case in cases:
        for value in (case['args'][0],case['expected']):value['fields'].update(label='中'+chr(0)+'"' if case['suite']=='target' else '',active=case['suite']=='target')
    for value in (cases[0]['args'][0],cases[0]['expected']):value['fields']['items']=[-(1<<63),(1<<63)-1]
    uploads=UploadService(RunStore(tmp_path/'confirmation'));draft=uploads.prepare('state.cj',bad.encode(),'返回扣减后的新对象，保留其他字段',actor_id='SDK_REFERENCE_FIXTURE',request_key='one')
    uploads.confirm(draft['id'],expected_version=1,function=function,examples_json=json.dumps(cases),consent=True,actor_id='SDK_REFERENCE_FIXTURE')
    root=uploads.source(draft['id'],actor_id='SDK_REFERENCE_FIXTURE');manifest=source_manifest(root);files={n:(root/n).read_bytes() for n in manifest}
    profile=uploads.profile(draft['id']);ids=[i for rows in profile['suite_tests'].values() for i in rows]
    if kind=='collision':assert all(not i.startswith('UploadedTests.') for i in ids)
    execute(tmp_path,files,'bad','FAIL',ids)
    validate_candidate(good,inspect_source(bad));fixed={**files,'src/uploaded.cj':good.encode()}
    execute(tmp_path,fixed,'fixed','PASS',ids)
    assert source_manifest(root)==manifest


def test_object_two_file_original_projection_tests_run_unchanged(tmp_path):
    files=project();good=files['src/state.cj'];files['src/state.cj']=good.replace(b'this.amount - n',b'this.amount + n')
    uploads=UploadService(RunStore(tmp_path/'confirmation'));draft=uploads.prepare_project('objects',None,'修复状态方法',actor_id='SDK_REFERENCE_FIXTURE',request_key='one',entries=files)
    uploads.confirm(draft['id'],expected_version=1,function='apply',examples_json=json.dumps(examples()),allowed_paths=['src/state.cj'],consent=True,actor_id='SDK_REFERENCE_FIXTURE')
    root=uploads.source(draft['id'],actor_id='SDK_REFERENCE_FIXTURE');manifest=source_manifest(root);material={n:(root/n).read_bytes() for n in manifest}
    profile=uploads.profile(draft['id']);ids=[i for rows in profile['suite_tests'].values() for i in rows]
    execute(tmp_path,material,'bad','FAIL',ids)
    fixed={**material,'src/state.cj':good};index=uploads.get(draft['id'],actor_id='SDK_REFERENCE_FIXTURE')['project_index']
    validate_project_candidate({n:fixed[n] for n in index['manifest']},index)
    execute(tmp_path,fixed,'fixed','PASS',ids)
    assert material['src/cases_test.cj']==fixed['src/cases_test.cj']==files['src/cases_test.cj'] and source_manifest(root)==manifest
