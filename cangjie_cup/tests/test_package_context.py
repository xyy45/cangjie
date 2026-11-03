"""No HTTP requests: observe the exact context at the model boundary."""
import asyncio,json
from copy import deepcopy
from types import SimpleNamespace
import pytest
from nexus.contracts import ToolResult
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.mcp.tools import workspace
from nexus.repair.cegis_loop import RepairLoop
from nexus.llm.provider import ProviderUnavailable
from tests.sdk.test_package_services_sdk import material,rule,state


def setup(root,*,crlf=False,with_oracle=True):
    files=material();files['src/model/state.cj']+=b'\n// NONSELECTED_BODY_SECRET_87632\n'
    if crlf:files['src/step.cj']=files['src/step.cj'].replace(b'\n',b'\r\n')
    store=RunStore(root);uploads=UploadService(store);d=uploads.prepare_project('scoped',None,'保持增量业务语义',actor_id='alice',request_key='one',entries=files)
    examples=[dict(args=[state(0),1],expected=state(1),suite='target'),dict(args=[state(1,[]),1],expected=state(2,[]),suite='regression')]
    frozen=uploads.confirm(d['id'],expected_version=1,function='bench.step',examples_json=json.dumps(examples),consent=True,
        actor_id='alice',allowed_paths=['src/step.cj'],**({'oracle_json':json.dumps(rule('oracle'))} if with_oracle else {}))
    source=uploads.source(d['id'],actor_id='alice');ws=WorkspaceStore(root,registered=[source]);baseline=ws.import_project(source,'.')
    req=RequirementService(store);draft=req.prepare_requirement(d['id'],frozen['goal']);spec=req.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=1,requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='alice')
    task=req.prepare_task(d['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    return store,ws,task,frozen


def test_scoped_workspace_reads_exclude_nonselected_bodies_and_original_tests(tmp_path):
    store,ws,task,value=setup(tmp_path)
    assert workspace.visible_paths(ws,task.baseline_id,task.id)=={'src/step.cj',value['public_test_path']}
    for path in ('src/model/state.cj','src/cases_test.cj','verification/oracle.json'):
        with pytest.raises(ValueError):workspace.read_file(ws,SimpleNamespace(baseline_id=task.baseline_id,task_id=task.id,path=path,start_line=1,end_line=None))


def test_model_context_contains_only_selected_sources_public_examples_and_readonly_interfaces(tmp_path):
    store,ws,task,value=setup(tmp_path);contexts=[]
    class Client:
        def __init__(self,root):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def call_tool(self,name,args):
            request=SimpleNamespace(baseline_id=task.baseline_id,task_id=task.id,prefix='',start_line=1,end_line=None,**({'path':args['path']} if 'path' in args else {}))
            if name=='project.diagnose':
                data=dict(build=dict(state='PASS'),test=dict(state='FAIL',diagnostics='EXPLICIT SDK FIXTURE ORIGINAL_TEST_BODY_NOT_FOR_MODEL NONSELECTED_BODY_SECRET_87632'))
            elif name=='workspace.list_files':data=workspace.list_files(ws,request)
            elif name=='workspace.read_file':data=workspace.read_file(ws,request)
            else:raise AssertionError('No actual repair/tool/model request allowed in context test')
            return ToolResult(operation_status='OK',data=data)
    class Stop:
        async def propose(self,context):contexts.append(deepcopy(context));raise ProviderUnavailable('EXPLICIT STOP BEFORE HTTP')
    result=asyncio.run(RepairLoop(store,client_factory=Client,provider_factory=lambda *_:Stop()).run(task.id))
    assert result.status=='BLOCKED' and len(contexts)==1
    context=contexts[0];encoded=json.dumps(context,ensure_ascii=False)
    assert 'NONSELECTED_BODY_SECRET_87632' not in encoded and 'ORIGINAL_TEST_BODY_NOT_FOR_MODEL' not in encoded
    assert set(context['files'])=={'src/step.cj',value['public_test_path']}
    assert context['scoped_project']['signature']['name']=='bench.step'
    assert context['scoped_project']['graph_hash']==value['project_index']['graph_hash']
    assert context['scoped_project']['readonly_dependencies']
    assert all(not path.endswith('_test.cj') for path in context['scoped_project']['production_graph']['imports'])


def test_presend_scope_guard_preserves_crlf_and_rejects_added_source(tmp_path):
    from nexus.repair.scoped_context import prepare,enforce
    from nexus.contracts import file_hash
    store,ws,task,value=setup(tmp_path,crlf=True);baseline=ws.verify_baseline(task.baseline_id)
    context=dict(files={p:dict(content=(baseline/p).read_bytes().decode(),file_hash=file_hash((baseline/p).read_bytes().decode()))
        for p in ('src/step.cj',value['public_test_path'])},upload_constraints=dict(allowed='闭合语言',forbidden='导入'),
        diagnostics=dict(build=dict(state='PASS'),test=dict(state='FAIL')))
    prepare(store,task,value,context);enforce(store,task,value,context)
    context['files']['src/model/state.cj']=dict(content='unexpected readonly body',file_hash='f'*64)
    with pytest.raises(ValueError):enforce(store,task,value,context)
