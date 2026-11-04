"""Native MCP slice calls and immutable legacy bindings, no network."""
import copy,json,zipfile
import pytest
from nexus.analysis.service import AnalysisService
from nexus.analysis.normalize import validate_source
from nexus.analysis import cache
from tests.analysis.test_service import FakeClient,SOURCE


def test_new_analysis_uses_native_slice_and_exports_exact_returned_lines(tmp_path):
    class Client(FakeClient):calls=[]
    service=AnalysisService(tmp_path,client_factory=Client)
    job=service.create(validate_source('add.cj',SOURCE),actor_id='a',request_key='native',origin='UPLOAD',slice_line=2)
    service.run(job['id']);result=service.get(job['id'],actor_id='a')
    assert [t for t,_ in Client.calls]==['sympas_slice','sympas_dep_graph','ast_symbol_extractor']
    assert result['analysis_profile']==8 and result['slice_scope']=='MCP_NATIVE'
    args=Client.calls[0][1]
    assert args==dict(code=SOURCE.decode(),filename='add.cj',lang='cangjie',line=2,direction='Bwd',method='SymPas',format='json')
    assert result['observations'][0]['data']['slices']=={'result@add':[2,3]}
    assert 'derived_slice' not in result
    with zipfile.ZipFile(service.export(job['id'],actor_id='a')) as z:
        assert 'observations/sympas_slice.json' in z.namelist()
        assert 'observations/sympas_slice_table.json' not in z.namelist()
        raw=json.loads(z.read('observations/sympas_slice.json'))
        assert raw['input']==args and raw['response']['data']['backward_slices']=={'result@add':{'add.cj':[2,3]}}


def test_failed_native_slice_is_not_recovered_from_local_logs(tmp_path):
    class Client(FakeClient):
        calls=[]
        def analyze(self,tool,args):
            reply=super().analyze(tool,args)
            if tool=='sympas_slice':reply['response']={'status':'success','data':{'backward_slices':{}},'raw_output':'Backward Static SliceTable:\n result@add {"add.cj: [2,3]"}'}
            return reply
    service=AnalysisService(tmp_path,client_factory=Client)
    job=service.create(validate_source('add.cj',SOURCE),actor_id='a',request_key='empty',origin='UPLOAD')
    service.run(job['id']);r=service.get(job['id'],actor_id='a')
    assert r['observations'][0]['status']=='EMPTY'
    assert 'derived_slice' not in r
    assert not any(t=='sympas_slice_table' for t,_ in Client.calls)


def test_old_table_request_is_idempotent_but_not_a_fresh_native_cache_hit(tmp_path,monkeypatch):
    from tests.analysis.test_cache import CacheClient
    CacheClient.calls=[]
    monkeypatch.setattr(cache,'PROFILE',7)
    service=AnalysisService(tmp_path,client_factory=CacheClient)
    source=validate_source('add.cj',SOURCE)
    first=service.create(source,actor_id='a',request_key='old',origin='UPLOAD');service.run(first['id'])
    old=service.get(first['id'],actor_id='a')
    assert old['observations'][0]['tool']=='sympas_slice_table'
    before=(service.directory(first['id'])/'result.json').read_bytes()
    monkeypatch.setattr(cache,'PROFILE',8)
    assert service.create(source,actor_id='a',request_key='old',origin='UPLOAD')['id']==first['id']
    job=service.create(source,actor_id='a',request_key='fresh',origin='UPLOAD',reuse_cache=True)
    assert job['id']!=first['id'] and not job.get('cache_hit')
    assert (service.directory(first['id'])/'result.json').read_bytes()==before


def test_old_local_slice_route_is_retired_and_does_not_traverse(tmp_path,monkeypatch):
    from nexus.demo.app import create_demo_app
    import nexus.analysis.routes as routes
    app=create_demo_app(tmp_path,provider='rule');service=app.extensions['analysis_service'];service.client_factory=FakeClient
    client=app.test_client();client.get('/')
    with client.session_transaction() as session:actor=session['actor_id']
    job=service.create(validate_source('add.cj',SOURCE),actor_id=actor,request_key='n',origin='UPLOAD');service.run(job['id'])
    detail=client.get('/api/analysis/'+job['id']).get_json()
    assert 'point_slice_url' not in detail
    if hasattr(routes,'point_slice'):monkeypatch.setattr(routes,'point_slice',lambda *a:pytest.fail('local traversal called'))
    response=client.get('/api/analysis/'+job['id']+'/point-slice?line=2')
    assert response.status_code==410


def test_model_context_uses_native_slice_evidence(tmp_path):
    import asyncio
    from tests.analysis.test_repair_bridge import setup
    store,task,context,bridge=setup(tmp_path)
    asyncio.run(bridge.enrich(task,context))
    for entry in context['analysis']['files']:
        slices=next(t for t in entry['tools'] if t['tool']=='sympas_slice')
        assert slices['included'] and slices['data']['slices']
        assert 'sympas_slice_table' not in slices['evidence_id']


def test_native_scope_cannot_be_changed_into_a_local_or_legacy_projection(tmp_path):
    service=AnalysisService(tmp_path,client_factory=FakeClient)
    job=service.create(validate_source('add.cj',SOURCE),actor_id='a',request_key='scope',origin='UPLOAD');service.run(job['id'])
    with service.store.connect() as db:
        status,payload=service._row(job['id']);payload['slice_scope']='VARIABLE_TABLE'
        db.execute('UPDATE analysis_jobs SET payload=? WHERE id=?',(json.dumps(payload),job['id']))
    with pytest.raises(ValueError):service.get(job['id'],actor_id='a')
