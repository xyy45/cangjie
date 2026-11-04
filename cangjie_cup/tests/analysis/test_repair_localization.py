"""Evidence binding tests use explicit check/tool fixtures, not native accuracy claims."""
import asyncio
import importlib
import importlib.util
import json

import pytest

from nexus.adapters.cangjie.report_parser import parse_test_report,project_suites
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.analysis.repair import RepairAnalysis
from nexus.analysis.service import AnalysisService
from nexus.contracts import CheckResult,digest,file_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.store import RunStore,uid
from nexus.uploads.service import UploadService
from tests.analysis.test_repair_bridge import Transport


def api():
    assert importlib.util.find_spec('nexus.repair.focus_service') is not None,'verified focus service missing'
    return importlib.import_module('nexus.repair.focus_service').FocusService


class GraphTransport(Transport):
    def analyze(self,tool,args):
        response=super().analyze(tool,args)
        if tool=='sympas_dep_graph':
            from nexus.uploads.language import Parser
            functions=Parser(args['code']).program(headers_only=True)['functions'];nodes=[];edges=[]
            for i,f in enumerate(functions):
                nodes.extend([dict(id=f'param{i}',label=f"[L{f['line']}]: parameter"),dict(id=f'result{i}',label=f"[L{f['final_line']}]: result")])
                edges.append({'from':f'param{i}','to':f'result{i}'})
            response['response']['json_graphs'].append(dict(graph_type='Pdg',nodes=nodes,edges=edges))
        return response


def setup(tmp_path,transport=GraphTransport):
    store=RunStore(tmp_path);uploads=UploadService(store)
    source=b'package calc\npublic func total(x: Int64): Int64 {\n return x + 1\n}\n'
    draft=uploads.prepare('calc.cj',source,'函数返回原输入',actor_id='TEST_FIXTURE',request_key='focus')
    examples=[dict(args=[2],expected=2,suite='target'),dict(args=[0],expected=0,suite='regression')]
    uploads.confirm(draft['id'],expected_version=1,function='total',examples_json=json.dumps(examples),consent=True,actor_id='TEST_FIXTURE')
    root=uploads.source(draft['id'],actor_id='TEST_FIXTURE');ws=WorkspaceStore(tmp_path,registered=[root]);baseline=ws.import_project(root,'.')
    req=RequirementService(store);d=req.prepare_requirement(draft['id'],draft['goal'])
    spec=req.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='TEST_FIXTURE')
    task=req.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    context=dict(requirements={'project_id':draft['id']},files={'src/uploaded.cj':dict(content=source.decode(),file_hash=file_hash(source.decode()))})
    bridge=RepairAnalysis(store,AnalysisService(tmp_path,client_factory=transport));asyncio.run(bridge.enrich(task,context))
    # A pinned-format log fixture tests reconstruction. SDK execution is separate.
    log='''TCS: UploadedTests,
 [ FAILED ] CASE: case0 (1 ns)
 Expect Failed: `(total(2) == 2)`
 left: 3
 right: 2
 [ FAILED ] CASE: case1 (1 ns)
 Expect Failed: `(total(0) == 0)`
 left: 1
 right: 0
Summary: TOTAL: 2 PASSED: 0, SKIPPED: 0, ERROR: 0 FAILED: 2
Error: cjpm test failed'''
    parsed=parse_test_report(log);assert parsed.state=='FAIL' and len(parsed.case_results)==2
    _,tree,plan_hash=CangjieVerifier(tmp_path,task.id).identity(baseline);_,plan=req.task_context(task)
    identity=uid();ref='records/'+identity+'.log';report_ref='records/'+identity+'.report.json'
    check=CheckResult(**{**parsed.model_dump(),'schema_version':2,'id':identity,'subject_id':baseline,'tree_hash':tree,
        'plan_hash':plan_hash,'spec_hash':task.spec_hash,'verification_plan_hash':task.verification_plan_hash,
        'kind':'test','exit_code':1,'log_ref':ref,'report_ref':report_ref,'diagnostics':log,
        'suite_results':project_suites(parsed,plan.suite_tests)})
    (tmp_path/ref).write_text(log);(tmp_path/report_ref).write_text(check.model_dump_json());store.append_record(task.id,'check',check.model_dump())
    return store,task,check,context


def test_focus_preserves_confirmed_failure_and_native_variable_evidence_without_local_slicing(tmp_path):
    store,task,check,context=setup(tmp_path);before=len(GraphTransport.calls)
    service=api()(store);event=service.create(task.id,task.baseline_id);report=event['localization']
    assert report['status']=='PARTIAL' and report['binding']['subject_id']==task.baseline_id
    assert report['binding']['spec_hash']==task.spec_hash
    target=report['targets'][0];point=target['locations'][0]['anchors'][0]['slice']
    assert target['args']==[2] and target['actual']=='3' and target['expected']=='2'
    assert point['status']=='UNAVAILABLE' and point['origin']=='MCP_SYMPAS_SLICE'
    native=next(o for f in context['analysis']['files'] for o in f['tools'] if o['tool']=='sympas_slice')
    assert native['status']=='VALID' and native['included'] and native['data']['slices']
    assert service.verify(task.id,event)==report and len(GraphTransport.calls)==before
    assert service.create(task.id,task.baseline_id)==event
    assert len([e for e in store.records(task.id,'event') if e['type']=='LOCALIZATION_CONTEXT'])==1


@pytest.mark.parametrize('change',['log','report','pdg-copy','focus','cross-task'])
def test_focus_tampering_and_foreign_binding_are_rejected(tmp_path,change):
    store,task,check,_=setup(tmp_path);service=api()(store);event=service.create(task.id,task.baseline_id)
    if change=='log':(tmp_path/check.log_ref).write_text('changed')
    elif change=='report':(tmp_path/check.report_ref).write_text('{}')
    elif change=='pdg-copy':
        analysis_event=next(e for e in store.records(task.id,'event') if e['type']=='ANALYSIS_CONTEXT')
        ref=next(e['record_ref'] for e in analysis_event['evidence_files'] if e['record_ref'].endswith('analysis.observations.sympas_dep_graph.json'))
        (tmp_path/ref).write_text('{}')
    elif change=='focus':event['localization']['targets'][0]['actual']='forged'
    else:event['task_id']='foreign'
    with pytest.raises(ValueError):service.verify(task.id,event)


def test_missing_point_graph_remains_partial_and_does_not_invent_nodes(tmp_path):
    store,task,_,_=setup(tmp_path,Transport);event=api()(store).create(task.id,task.baseline_id)
    assert event['localization']['status']=='PARTIAL'
    assert all(a['slice']['status']=='UNAVAILABLE' for t in event['localization']['targets'] for f in t['locations'] for a in f['anchors'])


def test_localization_route_checks_round_evidence_and_browser_ownership(tmp_path):
    from nexus.demo.app import create_demo_app
    store,task,_,_=setup(tmp_path);event=api()(store).create(task.id,task.baseline_id)
    app=create_demo_app(tmp_path,provider='rule');app.config['TESTING']=True
    alice=app.test_client();alice.get('/')
    with alice.session_transaction() as s:s['actor_id']='TEST_FIXTURE'
    path='/api/demo/tasks/'+task.id+'/localization'
    response=alice.get(path+'?round=1');assert response.status_code==200,response.json
    assert response.json['report']==event['localization']
    for query in ['','?round=0','?round=4','?round=x','?round=1&extra=1']:
        assert alice.get(path+query).status_code==400
    assert alice.get(path+'?round=2').json['report'] is None
    bob=app.test_client();bob.get('/');assert bob.get(path+'?round=1').status_code==404
    (tmp_path/event['localization']['targets'][0]['failure_source']['log_ref']).write_text('tampered')
    assert alice.get(path+'?round=1').status_code==400
