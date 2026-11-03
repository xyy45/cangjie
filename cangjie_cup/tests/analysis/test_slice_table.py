"""Native table results retain whole-table scope and immutable provenance."""
import json
import zipfile
import pytest
from nexus.analysis.normalize import normalize, validate_source
from nexus.analysis.service import AnalysisService
from tests.analysis.test_service import SOURCE, FakeClient


def table():
    return dict(status='success',tool='sympas_slice_table',direction='Bwd',method='SymPas',
        row_count=1,backward_slice_count=1,data={'backward_slices':{'result@add':{'add.cj':[2,3]}}})


def test_native_table_is_valid_with_explicit_whole_table_scope():
    observed=normalize('sympas_slice_table',table(),'add.cj',4)
    assert observed['status']=='VALID'
    assert observed['data']==dict(slices={'result@add':[2,3]},scope='VARIABLE_TABLE',direction='Bwd',method='SymPas')


@pytest.mark.parametrize('change', ['file','range','boolean','empty','count','direction','method','symbol'])
def test_unusable_native_tables_never_become_valid(change):
    payload=table()
    if change=='file':payload['data']['backward_slices']['result@add']={'foreign.cj':[2]}
    if change=='range':payload['data']['backward_slices']['result@add']['add.cj']=[5]
    if change=='boolean':payload['data']['backward_slices']['result@add']['add.cj']=[True]
    if change=='empty':payload['data']['backward_slices']={}
    if change=='count':payload['row_count']=999
    if change=='direction':payload['direction']='Fwd'
    if change=='method':payload['method']='Dynamic'
    if change=='symbol':payload['data']['backward_slices']={'  ':{'add.cj':[2]}}
    assert normalize('sympas_slice_table',payload,'add.cj',4)['status']!='VALID'


class NativeClient(FakeClient):
    def analyze(self,tool,args):
        if tool=='sympas_slice_table':
            self.calls.append((tool,args))
            return dict(http_status=200,response=table(),elapsed_ms=1,transport='TEST_NOT_LIVE')
        return super().analyze(tool,args)


def test_new_jobs_use_native_table_without_claiming_a_line_criterion(tmp_path):
    NativeClient.calls=[]
    service=AnalysisService(tmp_path,client_factory=NativeClient)
    job=service.create(validate_source('add.cj',SOURCE),actor_id='a',request_key='new',origin='UPLOAD',slice_line=2)
    service.run(job['id']);result=service.get(job['id'],actor_id='a')
    assert result['status']=='COMPLETE'
    assert result['slice_scope']=='VARIABLE_TABLE'
    assert result['slice_criterion']['line']==2  # UI navigation anchor, not an engine criterion.
    args=next(args for tool,args in NativeClient.calls if tool=='sympas_slice_table')
    assert args['table_formats']==['json'] and 'line' not in args
    assert not any(tool=='sympas_slice' for tool,args in NativeClient.calls)
    observed=result['observations'][0]
    assert observed['tool']=='sympas_slice_table' and observed['data']['scope']=='VARIABLE_TABLE'
    assert 'derived_slice' not in result
    with zipfile.ZipFile(service.export(job['id'],actor_id='a')) as z:
        raw=json.loads(z.read('observations/sympas_slice_table.json'))
        assert raw['tool']=='sympas_slice_table' and raw['input']==args
        assert json.loads(z.read('result.json'))['slice_scope']=='VARIABLE_TABLE'


def test_native_table_is_sent_through_the_fixed_client_endpoint():
    import httpx
    from nexus.analysis.client import ResearchClient
    requests=[]
    def reply(request):
        requests.append(request)
        return httpx.Response(200,json=table())
    with ResearchClient(transport=httpx.MockTransport(reply)) as client:
        result=client.analyze('sympas_slice_table',dict(code=SOURCE.decode(),filename='add.cj',lang='cangjie',table_formats=['json']))
    assert result['http_status']==200 and requests[0].url.path=='/tools/sympas_slice_table'


def test_native_model_context_contains_whole_table_scope(tmp_path):
    import asyncio
    from tests.analysis.test_repair_bridge import setup
    store,task,context,bridge=setup(tmp_path)
    asyncio.run(bridge.enrich(task,context))
    for entry in context['analysis']['files']:
        slices=next(t for t in entry['tools'] if t['tool']=='sympas_slice_table')
        assert slices['included'] and slices['data']['scope']=='VARIABLE_TABLE'
        assert 'sympas_slice_table' in slices['evidence_id']


def test_new_default_samples_and_downloads_use_native_tables():
    from nexus.analysis import samples
    for identity,want in (('sum3',5),('loop',4),('calls',10)):
        result=samples.snapshot(identity)
        observed=next(o for o in result['observations'] if o['tool']=='sympas_slice_table')
        assert observed['status']=='VALID' and len(observed['data']['slices'])==want
        assert 'derived_slice' not in result
        with zipfile.ZipFile(samples.snapshot_archive(identity)) as z:
            assert 'observations/sympas_slice_table.json' in z.namelist()
            assert 'derived-slices.json' not in z.namelist()


def test_sample_native_svg_is_exposed_as_source_bound_evidence(tmp_path):
    from nexus.demo.app import create_demo_app
    app=create_demo_app(tmp_path,provider='rule');client=app.test_client()
    result=client.get('/analysis/samples/calls').json['snapshot']
    assert result['callgraph']['view_url']=='/analysis/samples/calls/callgraph.svg'
    response=client.get(result['callgraph']['view_url'])
    assert response.status_code==200 and response.mimetype=='image/svg+xml'
    assert b'<svg' in response.data
