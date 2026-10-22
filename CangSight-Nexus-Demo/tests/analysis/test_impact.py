"""Deterministic transport tests for source binding; not live analysis accuracy."""
import json
import zipfile
import pytest
from nexus.analysis.impact import ImpactService,describe_change
from nexus.analysis.service import AnalysisService
from nexus.analysis.normalize import validate_source
from nexus.contracts import CandidateProposal,file_hash,tree_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.scenarios import ROOT
from nexus.store import RunStore

class Transport:
    calls=[]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def analyze(self,tool,args):
        self.calls.append((tool,args))
        response={'status':'success','untrusted_ref':'records/foreign.json'}
        if tool in ('sympas_slice','sympas_slice_table'):response['data']={'backward_slices':{'quantity':{args['filename']:[3,4]}}}
        if tool=='sympas_slice_table':response.update(tool=tool,direction='Bwd',method='SymPas',row_count=1,backward_slice_count=1)
        if tool=='sympas_dep_graph':response['json_graphs']=[dict(graph_type='Ddg',nodes=[
            dict(id='changed',label='[L4]: '+args['code'].splitlines()[3]),dict(id='input',label='(formal-in)%quantity'),
            dict(id='return',label='[L5]: return'),dict(id='unrelated',label='[L1]: other')],
            edges=[{'from':'input','to':'changed'},{'from':'changed','to':'return'}])]
        if tool=='ast_symbol_extractor':response['symbols']=[dict(symbol='quantity')]
        return dict(http_status=200,response=response,elapsed_ms=1,transport='TEST_ONLY')


def setup(tmp_path,transport=Transport,source=None):
    Transport.calls=[];source=source or ROOT/'fixtures/order-demo-bug'
    ws=WorkspaceStore(tmp_path,registered=[source]);baseline=ws.import_project(source,'.');store=RunStore(tmp_path)
    task=store.create_task(baseline,'修复数量',['src/quantity.cj'])
    before=ws.read_file(baseline,'src/quantity.cj')
    candidate=ws.apply_candidate(task,CandidateProposal(edits=[dict(path='src/quantity.cj',before_hash=file_hash(before),
        content=before.replace('quantity >= 0','quantity >= 1'))],requirement_refs=['goal']))
    store.update_task(task.id,status='UNREPAIRED')  # This test has no build/test attestation.
    analysis=AnalysisService(tmp_path,client_factory=transport)
    return store,ws,candidate,ImpactService(store,analysis)


def test_diff_maps_insertions_and_function_text_without_comment_brace_confusion():
    before='func f(): Int64 {\n // } fake func hidden() {\n return 1\n}\n'
    after='// inserted\n'+before.replace('return 1','return 2')
    change=describe_change(before,after)
    assert change['before_lines']==[3] and change['after_lines']==[1,4]
    assert {f['name'] for f in change['functions']}=={'f'}
    assert change['functions'][0]['origin']=='SOURCE_TEXT'


def test_candidate_preview_is_local_and_two_sides_are_bound_and_not_replayed(tmp_path):
    store,ws,c,service=setup(tmp_path);baseline=tree_hash(ws.subject_path(store.get_task(c.task_id).baseline_id))
    preview=service.get(c.id);assert preview['status']=='NOT_STARTED' and not Transport.calls
    assert preview['files'][0]['changes']['before_lines']==[4]
    job,created=service.start(c.id);assert created and job['candidate_id']==c.id
    assert service.run(c.id) is True
    report=service.get(c.id);assert report['status']=='COMPLETE' and len(Transport.calls)==6
    file=report['files'][0]
    assert file['before']['source_sha256']!=file['after']['source_sha256']
    assert file['before']['slice_criterion']['line']==file['after']['slice_criterion']['line']==4
    assert {n['id'] for n in file['after']['graph']['nodes']}=={'changed','input','return'}
    assert file['after']['graph']['anchor_ids']==['changed']
    assert service.start(c.id)[1] is False and service.run(c.id) is False and len(Transport.calls)==6
    assert baseline==tree_hash(ws.subject_path(store.get_task(c.task_id).baseline_id))
    assert not store.records(c.task_id,'acceptance') and not store.records(c.task_id,'model_call')
    with zipfile.ZipFile(service.export(c.id)) as z:
        assert json.loads(z.read('report.json'))['candidate_id']==c.id
        assert not any('foreign' in name for name in z.namelist())
        assert any(name.endswith('sympas_dep_graph.json') for name in z.namelist())


def test_matching_source_and_criterion_reuses_existing_analysis(tmp_path):
    store,ws,c,service=setup(tmp_path);task=store.get_task(c.task_id)
    source=validate_source('quantity.cj',ws.safe_file(task.baseline_id,'src/quantity.cj').read_bytes())
    old=service.analysis.create(source,actor_id='repair-'+task.id,request_key='previous',origin='REGISTERED',slice_line=4)
    service.analysis.run(old['id'])
    service.start(c.id);service.run(c.id)
    report=service.get(c.id)
    assert report['files'][0]['before']['analysis_id']==old['id'] and report['files'][0]['before']['reused']
    assert len(Transport.calls)==6


def test_changed_criterion_does_not_reuse_old_baseline_slice(tmp_path):
    store,ws,c,service=setup(tmp_path);task=store.get_task(c.task_id)
    source=validate_source('quantity.cj',ws.safe_file(task.baseline_id,'src/quantity.cj').read_bytes())
    old=service.analysis.create(source,actor_id='repair-'+task.id,request_key='previous',origin='REGISTERED',slice_line=3)
    service.analysis.run(old['id']);service.start(c.id);service.run(c.id)
    assert service.get(c.id)['files'][0]['before']['analysis_id']!=old['id'] and len(Transport.calls)==9


def test_changed_candidate_or_evidence_is_rejected(tmp_path):
    store,ws,c,service=setup(tmp_path);service.start(c.id);service.run(c.id)
    report=service.get(c.id);ref=report['evidence_files'][0]['record_ref']
    (store.root/ref).write_text('tampered')
    with pytest.raises(ValueError):service.get(c.id)
    with pytest.raises(ValueError):service.export(c.id)
    assert len(Transport.calls)==6


def test_restart_does_not_replay_an_impact_request(tmp_path):
    _,_,c,service=setup(tmp_path);service.start(c.id);service.reconcile()
    assert service.get(c.id)['status']=='IN_DOUBT'
    assert service.start(c.id)[1] is False and service.run(c.id) is False and not Transport.calls


def test_failed_graph_is_not_fabricated_and_remaining_evidence_is_visible(tmp_path):
    class Partial(Transport):
        def analyze(self,tool,args):
            result=super().analyze(tool,args)
            if tool=='sympas_dep_graph':result['response']={'status':'error','message':'engine failed'}
            return result
    _,_,c,service=setup(tmp_path,Partial);service.start(c.id);service.run(c.id)
    report=service.get(c.id)
    assert report['status']=='PARTIAL'
    assert report['files'][0]['after']['graph']['status']=='FAILED'
    assert report['files'][0]['after']['graph']['nodes']==[]


def test_impact_routes_require_csrf_and_bind_analysis_to_candidate(tmp_path):
    from nexus.demo.app import create_demo_app
    store,_,c,service=setup(tmp_path)
    app=create_demo_app(tmp_path,provider='rule');app.config.update(TESTING=True,RUN_IMPACTS=False)
    client=app.test_client();client.get('/')
    with client.session_transaction() as session:csrf=session['csrf']
    headers={'Origin':'http://localhost','X-CSRF-Token':csrf};url=f'/api/demo/candidates/{c.id}/impact'
    assert client.get(url).json['status']=='NOT_STARTED'
    assert client.post(url,json={}).status_code==403
    assert client.post(url,json={'candidate_id':'foreign'},headers=headers).status_code==400
    assert client.post(url,json={},headers=headers).status_code==202
    app.extensions['impact_service'].analysis.client_factory=Transport
    app.extensions['impact_service'].run(c.id)
    report=client.get(url).json;identity=report['files'][0]['after']['analysis_id']
    assert client.get(url+'/analysis/'+identity).json['bound_label'].startswith('修复后')
    assert client.get(url+'/analysis/'+'f'*32).status_code==400
    assert client.get(url+'/evidence').status_code==200
    assert client.post(url,json={},headers=headers).status_code==200
    assert len(Transport.calls)==6


def test_comparison_chooses_a_graph_with_changed_lines_without_merging_ids():
    from nexus.analysis.impact import graph_neighborhood
    result={'observations':[{'tool':'sympas_dep_graph','status':'VALID','reason':'ok','data':{'graphs':[
        {'nodes':[{'id':'same','line':1,'label':'unrelated'}],'edges':[]},
        {'nodes':[{'id':'same','line':4,'label':'changed'}],'edges':[]}]}}]}
    graph=graph_neighborhood(result,[4])
    assert graph['graph_index']==1 and graph['graph_count']==2
    assert [n['label'] for n in graph['nodes']]==['changed']


def test_task_archive_verifier_rejects_changed_impact_artifacts(tmp_path):
    from nexus.analysis.impact import verify_impact_event
    store,_,c,service=setup(tmp_path);service.start(c.id);service.run(c.id)
    event=next(e for e in store.records(c.task_id,'event') if e['type']=='IMPACT_ANALYSIS')
    assert verify_impact_event(store,event)['candidate_id']==c.id
    (store.root/event['report_ref']).write_text('{}')
    with pytest.raises(ValueError):verify_impact_event(store,event)


def test_impact_reservation_blocks_unrelated_upload_until_its_own_analyses_finish(tmp_path):
    from nexus.analysis.service import AnalysisConflict
    _,_,c,service=setup(tmp_path);service.start(c.id)
    source=validate_source('other.cj',b'func other(): Int64 { return 1 }\n')
    with pytest.raises(AnalysisConflict):
        service.analysis.create(source,actor_id='other',request_key='other',origin='UPLOAD')
    assert service.run(c.id) is True and service.get(c.id)['status']=='COMPLETE'
    assert service.analysis.create(source,actor_id='other',request_key='other',origin='UPLOAD')['id']


def test_crlf_baseline_bytes_are_preserved_in_tool_requests_and_exports(tmp_path):
    import shutil,hashlib
    fixture=tmp_path/'registered';shutil.copytree(ROOT/'fixtures/order-demo-bug',fixture)
    file=fixture/'src/quantity.cj';raw=file.read_bytes().replace(b'\n',b'\r\n');file.write_bytes(raw)
    _,_,c,service=setup(tmp_path/'runtime',source=fixture);service.start(c.id);service.run(c.id)
    report=service.get(c.id)
    assert report['files'][0]['before']['source_sha256']==hashlib.sha256(raw).hexdigest()
    assert Transport.calls[0][1]['code'].encode()==raw
    with zipfile.ZipFile(service.export(c.id)) as z:
        source_ref=next(n for n in z.namelist() if n.endswith('.source.cj'))
        assert z.read(source_ref)==raw


def test_final_report_and_archive_event_cannot_be_committed_separately(tmp_path,monkeypatch):
    store,_,c,service=setup(tmp_path);service.start(c.id)
    original=store._append_event
    def fail(db,task_id,payload):
        if payload.get('type')=='IMPACT_ANALYSIS':raise OSError('simulated disk failure')
        return original(db,task_id,payload)
    monkeypatch.setattr(store,'_append_event',fail)
    service.run(c.id)
    assert service.get(c.id)['status']=='IN_DOUBT'
    assert not any(e['type']=='IMPACT_ANALYSIS' for e in store.records(c.task_id,'event'))
    assert service.start(c.id)[1] is False and service.run(c.id) is False and len(Transport.calls)==6
