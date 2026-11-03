"""Test-only fake transport exercises persistence and ownership, not live analysis."""
from pathlib import Path
import json
import zipfile
import pytest
from nexus.analysis.service import AnalysisService, AnalysisConflict
from nexus.analysis.normalize import validate_source

SOURCE=b'func add(a: Int64, b: Int64): Int64 {\n    let result = a + b\n    return result\n}\n'

class FakeClient:
    calls=[]
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def analyze(self,tool,args):
        self.calls.append((tool,args))
        response={'status':'success'}
        if tool in ('sympas_slice','sympas_slice_table'):response['data']={'backward_slices':{'result@add':{args['filename']:[2,3]}}}
        if tool=='sympas_slice_table':response.update(tool=tool,direction='Bwd',method='SymPas',row_count=1,backward_slice_count=1)
        if tool=='sympas_dep_graph':response['json_graphs']=[{'graph_type':'Ddg','nodes':[{'id':'one','label':'[L2]: result = a + b'},{'id':'two','label':'[L3]: return result'}],'edges':[{'from':'one','to':'two'}]}]
        if tool=='ast_symbol_extractor':response['symbols']=[{'symbol':'result@add','appears_in':['Ddg']}]
        return dict(http_status=200,response=response,elapsed_ms=1,transport='TEST_FAKE_NOT_LIVE')

@pytest.fixture
def service(tmp_path):
    FakeClient.calls=[]
    return AnalysisService(tmp_path,client_factory=FakeClient)


def create(service,key='request-1',source=SOURCE):
    return service.create(validate_source('add.cj',source),actor_id='operator',request_key=key,origin='UPLOAD')


def test_source_bound_result_and_evidence_archive(service):
    job=create(service);service.run(job['id'])
    result=service.get(job['id'],actor_id='operator')
    assert result['status']=='COMPLETE' and len(FakeClient.calls)==3
    assert result['source']['code'].encode()==SOURCE
    assert all(o['status']=='VALID' and o['source_sha256']==result['source']['source_sha256'] for o in result['observations'])
    assert service.run(job['id']) is False and len(FakeClient.calls)==3
    with zipfile.ZipFile(service.export(job['id'],actor_id='operator')) as z:
        assert z.read('source.cj')==SOURCE
        assert len([p for p in z.namelist() if p.startswith('observations/')])==3


def test_duplicate_request_is_idempotent_and_conflicting_body_is_rejected(service):
    job=create(service)
    assert create(service)['id']==job['id']
    with pytest.raises(AnalysisConflict):create(service,source=SOURCE.replace(b'a + b',b'a - b'))
    with pytest.raises(AnalysisConflict):create(service,key='other')


def test_other_actor_cannot_read_or_export_upload(service):
    job=create(service);service.run(job['id'])
    with pytest.raises(LookupError):service.get(job['id'],actor_id='other')
    with pytest.raises(LookupError):service.export(job['id'],actor_id='other')


def test_source_and_observation_tampering_cannot_be_exported(service):
    job=create(service);service.run(job['id'])
    root=service.directory(job['id'])
    (root/'source.cj').write_text('changed')
    with pytest.raises(ValueError):service.get(job['id'],actor_id='operator')
    with pytest.raises(ValueError):service.export(job['id'],actor_id='operator')


def test_restart_marks_uncertain_and_never_replays(service):
    job=create(service);service.reconcile()
    assert service.get(job['id'],actor_id='operator')['status']=='IN_DOUBT'
    assert service.run(job['id']) is False and not FakeClient.calls


def test_source_changed_before_run_releases_active_slot_without_network(service):
    job=create(service)
    (service.directory(job['id'])/'source.cj').write_text('changed')
    assert service.run(job['id']) is True
    assert service._row(job['id'])[0]=='FAILED'
    assert not FakeClient.calls
    assert create(service,key='next')['id']!=job['id']


def test_two_workers_cannot_claim_the_same_job(service):
    from concurrent.futures import ThreadPoolExecutor
    job=create(service)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(service.run,[job['id'],job['id']]))
    assert sorted(results)==[False,True] and len(FakeClient.calls)==3


def test_changed_raw_observation_is_rejected_by_export(service):
    job=create(service);service.run(job['id'])
    path=service.directory(job['id'])/'observations/sympas_dep_graph.json';path.write_text('{}')
    with pytest.raises(ValueError):service.export(job['id'],actor_id='operator')


def test_tool_failure_does_not_get_replaced_by_another_sources_snapshot(tmp_path):
    from nexus.analysis.client import AnalysisUnavailable
    class Offline(FakeClient):
        def analyze(self,*args):raise AnalysisUnavailable('offline')
    service=AnalysisService(tmp_path,client_factory=Offline);job=create(service);service.run(job['id'])
    result=service.get(job['id'],actor_id='operator')
    assert result['origin']=='UPLOAD' and result['status']=='FAILED'
    assert all(o['status']=='UNAVAILABLE' and o['data']=={} for o in result['observations'])


def test_download_contains_exactly_the_verified_result_bytes(service):
    import hashlib
    job=create(service);service.run(job['id']);report=service.get(job['id'],actor_id='operator')
    with zipfile.ZipFile(service.export(job['id'],actor_id='operator')) as z:
        assert hashlib.sha256(z.read('result.json')).hexdigest()==report['result_sha256']
        assert z.read('result.json')==(service.directory(job['id'])/'result.json').read_bytes()


def test_selected_line_is_sent_to_tool_and_bound_to_saved_result(service):
    job=service.create(validate_source('add.cj',SOURCE),actor_id='operator',request_key='line-2',origin='UPLOAD',slice_line=2)
    service.run(job['id']);result=service.get(job['id'],actor_id='operator')
    assert 'line' not in next(args for tool,args in FakeClient.calls if tool=='sympas_slice_table')
    assert result['slice_scope']=='VARIABLE_TABLE'
    assert result['slice_criterion']=={'line':2,'direction':'Bwd','method':'SymPas'}
    assert service.list('operator')[0]['slice_criterion']['line']==2
    with zipfile.ZipFile(service.export(job['id'],actor_id='operator')) as z:
        assert json.loads(z.read('result.json'))['slice_criterion']['line']==2
    with pytest.raises(AnalysisConflict):
        service.create(validate_source('add.cj',SOURCE),actor_id='operator',request_key='line-2',origin='UPLOAD',slice_line=3)


@pytest.mark.parametrize('line',[True,False,0,-1,5,2.0,'2'])
def test_invalid_target_line_never_creates_a_job_or_calls_tools(service,line):
    with pytest.raises(ValueError):
        service.create(validate_source('add.cj',SOURCE),actor_id='operator',request_key='bad-line',origin='UPLOAD',slice_line=line)
    assert service.list('operator')==[] and not FakeClient.calls
