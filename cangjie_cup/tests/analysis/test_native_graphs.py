"""Explicit HTTP fixtures; no remote generation or model requests."""
import asyncio
import hashlib
import json
import zipfile

import httpx
import pytest

from nexus.analysis import native_graphs as graphs
from nexus.analysis.client import ResearchClient
from nexus.analysis.service import AnalysisService
from tests.analysis.test_service import FakeClient,create


def svg(kind):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400">'
            '<text>'+kind+'</text></svg>').encode()


def payload(types=None):
    return dict(status='success',graphs=[dict(graph_type=k,svg=dict(
        download_url='/artifacts/run/'+k+'.svg?api_key=capability')) for k in (types or graphs.GRAPH_TYPES)])


def test_seven_original_svgs_are_downloaded_once_and_capabilities_not_persisted():
    calls=[]
    def response(request):
        calls.append(request)
        if request.method=='POST':return httpx.Response(200,json=payload())
        return httpx.Response(200,content=svg(request.url.path.split('/')[-1].split('.')[0]))
    with ResearchClient(transport=httpx.MockTransport(response),token='') as c:
        result=c.analyze('sympas_dep_graph',dict(graph_types=','.join(graphs.GRAPH_TYPES)))
    assert len(calls)==8
    assert set(result['_native_graph_bytes'])==set(graphs.GRAPH_TYPES)
    assert all(result['_native_graph_bytes'][k]==svg(k) for k in graphs.GRAPH_TYPES)
    assert result['_callgraph_bytes']==svg('Cg')
    raw={k:v for k,v in result.items() if not k.startswith('_')}
    assert 'capability' not in json.dumps(raw)
    assert all(g['status']=='SAVED' and g['aspect_ratio']==2 for g in raw['native_graphs']['graphs'].values())


@pytest.mark.parametrize('bad',['foreign','redirect','html','entity','credential','encoded_credential','conflict'])
def test_one_bad_graph_does_not_hide_other_graph_types(bad):
    p=payload();calls=[]
    if bad=='foreign':p['graphs'][0]['svg']['download_url']='https://evil.invalid/artifacts/r/Cfg.svg'
    if bad=='conflict':p['graphs'].append(dict(graph_type='Cfg',svg=dict(url='/artifacts/run/other.svg')))
    def response(request):
        if request.method=='POST':return httpx.Response(200,json=p)
        calls.append(request)
        kind=request.url.path.split('/')[-1].split('.')[0]
        if kind=='Cfg':
            if bad=='redirect':return httpx.Response(302,headers={'Location':'https://evil.invalid/'})
            content={'html':b'<html>error</html>','entity':b'<!DOCTYPE svg [<!ENTITY a "x">]><svg xmlns="http://www.w3.org/2000/svg">&a;</svg>',
                'credential':svg('capability'),'encoded_credential':svg('capabil&#105;ty')}.get(bad,svg(kind))
            return httpx.Response(200,content=content)
        return httpx.Response(200,content=svg(kind))
    with ResearchClient(transport=httpx.MockTransport(response),token='') as c:
        r=c.analyze('sympas_dep_graph',dict(graph_types=','.join(graphs.GRAPH_TYPES)))
    assert r['native_graphs']['graphs']['Cfg']['status']=='UNAVAILABLE'
    assert all(r['native_graphs']['graphs'][k]['status']=='SAVED' for k in graphs.GRAPH_TYPES if k!='Cfg')
    assert all(x.url.host=='47.94.83.64' for x in calls)


def test_missing_graph_does_not_trigger_a_generation_retry():
    calls=[]
    def response(request):
        calls.append(request)
        return httpx.Response(200,json=payload(['Pdg'])) if request.method=='POST' else httpx.Response(200,content=svg('Pdg'))
    with ResearchClient(transport=httpx.MockTransport(response),token='') as c:
        r=c.analyze('sympas_dep_graph',dict(graph_types=','.join(graphs.GRAPH_TYPES)))
    assert len(calls)==2 and r['native_graphs']['graphs']['Sdg']['status']=='UNAVAILABLE'
    assert r['native_graphs']['graphs']['Pdg']['status']=='SAVED'


@pytest.mark.parametrize('failure',['tool_error','not_generated'])
def test_failure_declarations_do_not_promote_leftover_svg_links(failure):
    p=payload(['Sdg']);calls=[]
    if failure=='tool_error':p['status']='error'
    else:p['graphs'][0]['generated']=False
    def response(request):calls.append(request);return httpx.Response(200,content=svg('Sdg'))
    async def collect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as c:
            return await graphs.fetch_graphs(c,p,base_url='http://47.94.83.64:6240',token='')
    result=asyncio.run(collect())
    assert not calls and result['native_graphs']['graphs']['Sdg']['status']=='UNAVAILABLE'


def test_total_byte_budget_is_enforced_while_streaming(monkeypatch):
    monkeypatch.setattr(graphs,'MAX_TOTAL_BYTES',len(svg('Cfg'))+5)
    calls=[]
    def response(request):
        calls.append(request)
        return httpx.Response(200,content=svg('Cfg'))
    async def collect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as c:
            return await graphs.fetch_graphs(c,payload(),base_url='http://47.94.83.64:6240',token='')
    r=asyncio.run(collect())
    assert len(calls)==2 and r['native_graphs']['graphs']['Cfg']['status']=='SAVED'
    assert len(r['_native_graph_bytes'])==1


def test_per_graph_byte_budget_does_not_discard_smaller_following_graphs(monkeypatch):
    monkeypatch.setattr(graphs,'MAX_SVG_BYTES',200)
    def response(request):
        return httpx.Response(200,content=b'x'*201 if 'Cfg.svg' in request.url.path else svg('Cg'))
    async def collect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as c:
            return await graphs.fetch_graphs(c,payload(),base_url='http://47.94.83.64:6240',token='')
    r=asyncio.run(collect())
    assert r['native_graphs']['graphs']['Cfg']['status']=='UNAVAILABLE'
    assert r['native_graphs']['graphs']['Cg']['status']=='SAVED'


def test_previous_profile_cache_alias_is_readable_but_not_reused_for_new_keys(tmp_path,monkeypatch):
    from nexus.analysis import cache
    from nexus.analysis.normalize import validate_source
    from tests.analysis.test_cache import CacheClient,SOURCE
    original=cache.arguments
    service=AnalysisService(tmp_path,client_factory=CacheClient)
    source=validate_source('add.cj',SOURCE)
    with monkeypatch.context() as old:
        old.setattr(cache,'PROFILE',6)
        old.setattr(cache,'arguments',lambda tool,source,criterion,**kw:original(tool,source,criterion,profile=6))
        first=service.create(source,actor_id='owner',request_key='first',origin='UPLOAD')
        service.run(first['id'])
        alias=service.create(source,actor_id='owner',request_key='alias',origin='UPLOAD',reuse_cache=True)
        assert alias['cache_hit']
    assert cache.PROFILE==8
    assert service.create(source,actor_id='owner',request_key='alias',origin='UPLOAD',reuse_cache=True)==alias
    fresh=service.create(source,actor_id='owner',request_key='fresh',origin='UPLOAD',reuse_cache=True)
    assert fresh['id']!=first['id'] and not fresh.get('cache_hit')


def test_whole_collection_has_deadline_and_preserves_completed_graph(monkeypatch):
    monkeypatch.setattr(graphs,'TOTAL_SECONDS',.02)
    calls=[]
    async def response(request):
        calls.append(request)
        if len(calls)>1:await asyncio.sleep(.05)
        return httpx.Response(200,content=svg('Cfg'))
    async def collect():
        async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as c:
            return await graphs.fetch_graphs(c,payload(),base_url='http://47.94.83.64:6240',token='')
    r=asyncio.run(collect())
    assert len(calls)==2 and len(r['_native_graph_bytes'])==1
    assert r['native_graphs']['graphs']['Dfg']['status']=='UNAVAILABLE'


class GraphClient(FakeClient):
    def analyze(self,tool,args):
        reply=super().analyze(tool,args)
        if tool=='sympas_dep_graph':
            assert set(args['graph_types'].split(','))==set(graphs.GRAPH_TYPES)
            reply.update(native_graphs=dict(schema_version=1,graphs={k:dict(status='SAVED',
                upstream_path='/artifacts/run/'+k+'.svg',aspect_ratio=2) for k in graphs.GRAPH_TYPES}),
                _native_graph_bytes={k:svg(k) for k in graphs.GRAPH_TYPES},
                _callgraph_bytes=svg('Cg'),callgraph=dict(status='SAVED',upstream_path='/artifacts/run/Cg.svg'))
        return reply


def test_seven_assets_are_bound_exported_and_owned(tmp_path):
    service=AnalysisService(tmp_path,client_factory=GraphClient);job=create(service);service.run(job['id'])
    r=service.get(job['id'],actor_id='operator')
    assert r['analysis_profile']==8 and r['native_graphs']['schema_version']==1
    for k,g in r['native_graphs']['graphs'].items():
        assert g['analysis_id']==job['id'] and g['graph_type']==k
        assert g['source_sha256']==r['source']['source_sha256']
        assert service.native_graph_bytes(job['id'],k,actor_id='operator')==svg(k)
    with zipfile.ZipFile(service.export(job['id'],actor_id='operator')) as z:
        for k,g in r['native_graphs']['graphs'].items():assert z.read(g['ref'])==svg(k)
    with pytest.raises(LookupError):service.native_graph_bytes(job['id'],'Sdg',actor_id='other')
    with pytest.raises(LookupError):service.native_graph_bytes(job['id'],'../core',actor_id='operator')
    g=r['native_graphs']['graphs']['Sdg'];(service.directory(job['id'])/g['ref']).write_bytes(svg('wrong'))
    with pytest.raises(ValueError):service.native_graph_bytes(job['id'],'Sdg',actor_id='operator')
    with pytest.raises(ValueError):service.export(job['id'],actor_id='operator')


def test_graph_routes_are_source_bound_and_svg_is_not_an_active_document(tmp_path):
    from nexus.demo.app import create_demo_app
    app=create_demo_app(tmp_path,provider='rule');app.testing=True
    service=app.extensions['analysis_service'];service.client_factory=GraphClient
    web=app.test_client();web.get('/')
    with web.session_transaction() as session:actor=session['actor_id']
    job=service.create(__import__('nexus.analysis.normalize',fromlist=['validate_source']).validate_source(
        'add.cj',b'func f(): Int64 { return 1 }\n'),actor_id=actor,request_key='native',origin='UPLOAD')
    service.run(job['id']);url='/api/analysis/'+job['id']
    report=web.get(url).json
    for kind,g in report['native_graphs']['graphs'].items():
        response=web.get(g['view_url']);assert response.status_code==200
        assert response.data==svg(kind) and 'sandbox' in response.headers['Content-Security-Policy']
        assert web.get(g['download_url']).headers['Content-Disposition'].startswith('attachment;')
    assert app.test_client().get(url+'/graphs/Sdg.svg').status_code==404
