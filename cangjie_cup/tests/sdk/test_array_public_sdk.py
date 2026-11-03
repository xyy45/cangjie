"""Actual fixed SDK Array public defects and reference fixes, no model/MCP."""
import json
import pytest
from nexus.contracts import source_manifest
from nexus.projects.index import inspect_project,validate_project_candidate
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_array_projects import array_project
from tests.sdk.test_string_public_sdk import execute

pytestmark=pytest.mark.sdk
LOW=-(1<<63);HIGH=(1<<63)-1

@pytest.mark.parametrize('scenario',['sum','return'])
def test_uploaded_array_public_defect_then_reference_fix(tmp_path,scenario):
    if scenario=='sum':
        source='''public func orderTotal(values: Array<Int64>): Int64 {
 var total: Int64 = 0
 var index: Int64 = 0
 while (index < values.size - 1) {
  total = total + values[index]
  index = index + 1
 }
 return total
}
'''
        fixed=source.replace('index < values.size - 1','index < values.size');function='orderTotal'
        examples=[dict(args=[[]],expected=0,suite='regression'),dict(args=[[3,-2,5]],expected=6,suite='target'),dict(args=[[LOW,HIGH]],expected=-1,suite='target'),dict(args=[[LOW]],expected=LOW,suite='target'),dict(args=[[3]*16],expected=48,suite='target'),dict(args=[[0]],expected=0,suite='regression')]
    else:
        source='''public func orderItems(values: Array<Int64>): Array<Int64> {
 if (values.size == 0) { return [0] }
 return values
}
'''
        fixed=source.replace('return [0]','return []');function='orderItems'
        examples=[dict(args=[[]],expected=[],suite='target'),dict(args=[[LOW,HIGH]],expected=[LOW,HIGH],suite='regression'),dict(args=[[LOW]*16],expected=[LOW]*16,suite='regression'),dict(args=[[1,1,-1]],expected=[1,1,-1],suite='regression')]
    service=UploadService(RunStore(tmp_path/'upload'));draft=service.prepare(scenario+'.cj',source.encode(),'自建数组公开测试',actor_id='alice',request_key=scenario)
    service.confirm(draft['id'],expected_version=1,function=function,examples_json=json.dumps(examples),consent=True,actor_id='alice')
    project=service.source(draft['id'],actor_id='alice');before=source_manifest(project);files={n:(project/n).read_bytes() for n in before}
    (tmp_path/'original-upload.cj').write_text(source);(tmp_path/'examples.json').write_text(json.dumps(examples))
    ids=['UploadedTests.case'+str(i) for i in range(len(examples))]
    execute(tmp_path,files,'bad','FAIL',ids)
    assert files['src/uploaded.cj']==('package uploadedrepair\n'+source).encode()
    execute(tmp_path,{**files,'src/uploaded.cj':('package uploadedrepair\n'+fixed).encode()},'fixed','PASS',ids)
    assert source_manifest(project)==before and service.profile(draft['id'])


def test_array_two_file_original_literal_tests_run_unchanged(tmp_path):
    files=array_project();good=files['src/helper.cj'];files['src/helper.cj']=good.replace(b'{ values }',b'{ if (values.size == 0) { return [0] }; return values }')
    baseline=inspect_project(files);ids=[c['id'] for c in baseline['test_cases']]
    execute(tmp_path,files,'bad','FAIL',ids)
    fixed={**files,'src/helper.cj':good};validate_project_candidate(fixed,baseline)
    execute(tmp_path,fixed,'fixed','PASS',ids)
    for path in baseline['frozen_manifest']:assert files[path]==fixed[path]
