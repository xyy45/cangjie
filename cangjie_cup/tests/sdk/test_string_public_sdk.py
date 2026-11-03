"""Real fixed SDK public tests; no model, network analysis or native policy calls."""
import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from nexus.adapters.cangjie.report_parser import parse_test_report
from nexus.contracts import source_manifest
from nexus.execution.runner import run_command
from nexus.projects.index import inspect_project
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_string_projects import string_project

pytestmark=pytest.mark.sdk


def execute(root,files,name,expected,case_ids):
    project=root/name;project.mkdir()
    for path,raw in files.items():
        p=project/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    original=source_manifest(project);commands=[]
    code,log,problem=asyncio.run(run_command(project,['cjpm','test'],private_root=root,timeout=60,test_output='all',execution_argv=commands))
    (root/(name+'.log')).write_text(log)
    parsed=parse_test_report(log)
    result=dict(exit_code=code,problem=problem,state=parsed.state,case_results=parsed.case_results,execution_argv=commands,source_manifest=original)
    (root/(name+'.json')).write_text(json.dumps(result,ensure_ascii=True,indent=2))
    assert problem is None and parsed.state==expected,(result,log[-4000:])
    assert (code==0)==(expected=='PASS')
    assert set(parsed.case_results)==set(case_ids)
    assert source_manifest(project)==original
    assert commands==[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]
    return result


@pytest.mark.parametrize('scenario',['length','echo'])
def test_uploaded_string_public_failure_then_fixed_sdk_pass(tmp_path,scenario):
    nl=chr(10)
    if scenario=='length':
        source='public func label(code: String): Bool { code.size <= 4 }'+nl
        fixed=source.replace('code.size','code.toRuneArray().size');function='label'
        examples=[dict(args=['中中'],expected=True,suite='target'),dict(args=['abc'],expected=True,suite='regression')]
    else:
        source=nl.join(['public func echo(x: String): String {',' if (x == "") { return "!" }',' return x','}',''])
        fixed=nl.join(['public func echo(x: String): String {',' return x','}','']);function='echo'
        control=chr(0)+chr(10)+chr(13)+chr(9)+'"'+chr(92)+'中😀${not_code}'
        examples=[dict(args=[''],expected='',suite='target'),dict(args=[control],expected=control,suite='regression'),dict(args=['x'*256],expected='x'*256,suite='regression'),dict(args=['中'*85+'x'],expected='中'*85+'x',suite='regression')]
    store=RunStore(tmp_path/'upload');service=UploadService(store)
    draft=service.prepare(scenario+'.cj',source.encode(),'自建String公开测试',actor_id='alice',request_key=scenario)
    service.confirm(draft['id'],expected_version=1,function=function,examples_json=json.dumps(examples),consent=True,actor_id='alice')
    project=service.source(draft['id'],actor_id='alice');manifest=source_manifest(project);files={name:(project/name).read_bytes() for name in manifest}
    (tmp_path/'original-upload.cj').write_bytes(source.encode());(tmp_path/'examples.json').write_text(json.dumps(examples,ensure_ascii=True))
    ids=['UploadedTests.case'+str(i) for i in range(len(examples))]
    execute(tmp_path,files,'bad','FAIL',ids)
    package='package uploadedrepair'+nl
    assert files['src/uploaded.cj']==package.encode()+source.encode()
    execute(tmp_path,{**files,'src/uploaded.cj':(package+fixed).encode()},'fixed','PASS',ids)
    assert source_manifest(project)==manifest and service.profile(draft['id'])


def test_cross_file_string_original_cases_and_escaped_literals_run_in_sdk(tmp_path):
    files=string_project();files['src/fee.cj']=files['src/fee.cj'].replace(b'{ x }',b'{ x + x }');index=inspect_project(files)
    ids=[c['id'] for c in index['test_cases']]
    execute(tmp_path,files,'bad','FAIL',ids)
    fixed={**files,'src/fee.cj':files['src/fee.cj'].replace(b'{ x + x }',b'{ x }')}
    execute(tmp_path,fixed,'fixed','PASS',ids)
    for path in index['frozen_manifest']:assert files[path]==fixed[path]
