"""Fake transport checks binding and failure handling, never live service accuracy."""
import asyncio
import hashlib
import json
import pytest
from nexus.analysis.service import AnalysisService
from nexus.analysis.repair import RepairAnalysis
from nexus.contracts import file_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.scenarios import ROOT, get_profile
from nexus.store import RunStore


class Transport:
    calls=[]
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def analyze(self,tool,args):
        self.calls.append((tool,args))
        data={'status':'success'}
        if tool in ('sympas_slice','sympas_slice_table'):data['data']={'backward_slices':{'value':{args['filename']:[1]}}}
        if tool=='sympas_slice_table':data.update(tool=tool,direction='Bwd',method='SymPas',row_count=1,backward_slice_count=1)
        if tool=='sympas_dep_graph':data['json_graphs']=[{'graph_type':'Ddg','nodes':[{'id':'one','label':'[L1]: source'}],'edges':[]}]
        if tool=='ast_symbol_extractor':data['symbols']=[{'symbol':'value','appears_in':['Ddg']}]
        return dict(http_status=200,response=data,elapsed_ms=1,transport='TEST_NOT_LIVE')


def setup(tmp_path,transport=Transport,project='cross-validation'):
    Transport.calls=[]
    store=RunStore(tmp_path);profile=get_profile(project);source=ROOT/profile['source']
    ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.')
    task=store.create_task(baseline,'repair',profile['allowed_paths'])
    context=dict(requirements={'project_id':project},files={p:dict(content=ws.read_file(baseline,p),
        file_hash=file_hash(ws.read_file(baseline,p))) for p in profile['allowed_paths']})
    service=AnalysisService(tmp_path,client_factory=transport)
    return store,task,context,RepairAnalysis(store,service)


def test_exact_baseline_analysis_enters_context_with_original_evidence(tmp_path):
    store,task,context,bridge=setup(tmp_path)
    asyncio.run(bridge.enrich(task,context))
    report=context['analysis'];assert report['status']=='COMPLETE'
    assert len(Transport.calls)==6 and len(report['files'])==2
    for entry in report['files']:
        assert entry['source_sha256']==context['files'][entry['path']]['file_hash']
        for tool in entry['tools']:
            assert tool['included'] and tool['data'] and tool['evidence_id']
    event=store.records(task.id,'event')[-1]
    assert event['type']=='ANALYSIS_CONTEXT' and event['analysis_context']==report
    for ref in event['evidence_files']:
        assert hashlib.sha256((tmp_path/ref['record_ref']).read_bytes()).hexdigest()==ref['sha256']
    # Re-entering enrich reads the existing bound record; no remote replay.
    again={'files':context['files'],'requirements':context['requirements']}
    asyncio.run(bridge.enrich(task,again));assert again['analysis']==report and len(Transport.calls)==6


def test_failed_tool_data_never_becomes_model_evidence(tmp_path):
    class Partial(Transport):
        def analyze(self,tool,args):
            result=super().analyze(tool,args)
            if tool in ('sympas_slice','sympas_slice_table'):result['response']={'status':'success','engine_log':'SIL syntax error','data':{'backward_slices':{'fake':{args['filename']:[1]}}}}
            return result
    _,task,context,bridge=setup(tmp_path,Partial);asyncio.run(bridge.enrich(task,context))
    assert context['analysis']['status']=='PARTIAL'
    for entry in context['analysis']['files']:
        failed=entry['tools'][0]
        assert failed['status']=='FAILED' and not failed['included'] and 'data' not in failed


def test_context_or_persisted_evidence_tamper_blocks_reuse(tmp_path):
    store,task,context,bridge=setup(tmp_path)
    context['files']['src/fee.cj']['content']='changed'
    with pytest.raises(ValueError):asyncio.run(bridge.enrich(task,context))
    assert not Transport.calls


def test_recorded_artifact_tamper_cannot_be_reused(tmp_path):
    store,task,context,bridge=setup(tmp_path);asyncio.run(bridge.enrich(task,context))
    event=store.records(task.id,'event')[-1]
    (tmp_path/event['evidence_files'][0]['record_ref']).write_text('changed')
    with pytest.raises(ValueError):asyncio.run(bridge.enrich(task,context))


@pytest.mark.parametrize('project',['order-demo-bug','order-price','order-discount','cross-validation','cross-discount','cross-stock'])
def test_every_repair_profile_uses_its_own_allowed_production_sources(tmp_path,project):
    _,task,context,bridge=setup(tmp_path,project=project)
    asyncio.run(bridge.enrich(task,context))
    report=context['analysis'];paths={f['path'] for f in report['files']}
    assert paths==set(task.allowed_paths)
    assert len(Transport.calls)==len(paths)*3
    assert all(not p.endswith('_test.cj') for p in paths)
    assert {c[1]['code'] for c in Transport.calls}=={v['content'] for v in context['files'].values()}


def test_unknown_profile_cannot_trigger_external_analysis(tmp_path):
    _,task,context,bridge=setup(tmp_path);context['requirements']['project_id']='not-registered'
    with pytest.raises(ValueError):asyncio.run(bridge.enrich(task,context))
    assert not Transport.calls


def test_task_bound_routes_allow_direct_access_and_reject_foreign_analysis(tmp_path):
    from nexus.demo.app import create_demo_app
    store,task,context,bridge=setup(tmp_path);asyncio.run(bridge.enrich(task,context))
    app=create_demo_app(tmp_path,provider='rule');app.config['TESTING']=True
    client=app.test_client();client.get('/')
    base=f'/api/demo/tasks/{task.id}/analysis'
    assert client.get(base).status_code==200
    report=client.get(base).json['analysis'];identity=report['files'][0]['analysis_id']
    response=client.get(base+'/'+identity)
    assert response.status_code==200 and response.json['display_origin']=='REGISTERED_BOUND'
    assert response.json['source']['source_sha256']==report['files'][0]['source_sha256']
    assert client.get(base+'/'+identity+'/evidence').status_code==200
    assert client.get(base+'/'+'f'*32).status_code==400
    evidence=next(e for e in store.records(task.id,'event') if e['type']=='ANALYSIS_CONTEXT')['evidence_files'][0]
    (tmp_path/evidence['record_ref']).write_text('tamper')
    assert client.get(base).status_code==400
