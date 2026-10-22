"""Native SVG evidence must remain private, source-bound and independently available."""
import hashlib
import json
import zipfile
import httpx
import pytest
from nexus.analysis.client import ResearchClient
from nexus.analysis.service import AnalysisService
from tests.analysis.test_service import FakeClient,create

SVG=b'<svg xmlns="http://www.w3.org/2000/svg"><text>call graph</text></svg>'


def transport(url='/artifacts/run/f_cg.svg?api_key=capability',status=200,content=SVG):
    def respond(request):
        if request.method=='POST':
            return httpx.Response(200,json={'status':'success','graphs':[
                {'graph_type':'Ddg','svg':{'url':'/artifacts/run/f_ddg.svg?api_key=wrong'}},
                {'graph_type':'Cg','svg':{'download_url':url}}]})
        assert request.url.path=='/artifacts/run/f_cg.svg'
        assert request.url.params['api_key']=='capability'
        return httpx.Response(status,content=content,headers={'Content-Type':'image/svg+xml'})
    return httpx.MockTransport(respond)


def test_native_svg_is_retrieved_before_capability_is_redacted():
    with ResearchClient(transport=transport(),token='') as client:
        reply=client.analyze('sympas_dep_graph',{})
    assert reply.pop('_callgraph_bytes')==SVG
    assert reply['callgraph']['status']=='SAVED'
    assert reply['callgraph']['upstream_path']=='/artifacts/run/f_cg.svg'
    assert 'capability' not in json.dumps(reply) and 'wrong' not in json.dumps(reply)


def test_upstream_download_flag_is_not_mistaken_for_embedded_credential():
    svg=b'<svg xmlns="http://www.w3.org/2000/svg" width="100"><text>1</text></svg>'
    with ResearchClient(transport=transport('/artifacts/run/f_cg.svg?api_key=capability&download=1',content=svg),token='') as client:
        reply=client.analyze('sympas_dep_graph',{})
    assert reply['callgraph']['status']=='SAVED' and reply['_callgraph_bytes']==svg


def test_relative_artifact_capability_is_redacted_before_persistence():
    with ResearchClient(transport=transport('artifacts/run/f_cg.svg?api_key=capability'),token='') as client:
        reply=client.analyze('sympas_dep_graph',{})
    assert reply.pop('_callgraph_bytes')==SVG
    assert 'capability' not in json.dumps(reply)


def test_malformed_optional_svg_url_does_not_discard_graph_response():
    with ResearchClient(transport=transport('http://[invalid/artifacts/run/f_cg.svg'),token='') as client:
        reply=client.analyze('sympas_dep_graph',{})
    assert reply['response']['status']=='success' and reply['callgraph']['status']=='UNAVAILABLE'


@pytest.mark.parametrize('url',[
    'http://evil.example/artifacts/run/f_cg.svg?api_key=capability',
    '//evil.example/artifacts/run/f_cg.svg',
    '/artifacts/../secret.svg','/other/f_cg.svg',
])
def test_unapproved_artifact_location_is_not_fetched(url):
    with ResearchClient(transport=transport(url),token='') as client:
        reply=client.analyze('sympas_dep_graph',{})
    assert reply['http_status']==200 and reply['callgraph']['status']=='UNAVAILABLE'
    assert '_callgraph_bytes' not in reply


@pytest.mark.parametrize('status,content',[(302,SVG),(500,b'error'),(200,b'<html>error</html>'),(200,b'x'*(2*1024*1024+1))],ids=['redirect','error','html','oversized'])
def test_svg_failure_preserves_successful_graph_response(status,content):
    with ResearchClient(transport=transport(status=status,content=content),token='') as client:
        reply=client.analyze('sympas_dep_graph',{})
    assert reply['response']['status']=='success'
    assert reply['callgraph']['status']=='UNAVAILABLE' and '_callgraph_bytes' not in reply


def test_unknown_svg_encoding_is_optional_failure():
    raw=b'<?xml version="1.0" encoding="invalid-codec"?><svg xmlns="http://www.w3.org/2000/svg"/>'
    with ResearchClient(transport=transport(content=raw),token='') as client:reply=client.analyze('sympas_dep_graph',{})
    assert reply['response']['status']=='success' and reply['callgraph']['status']=='UNAVAILABLE'


class SvgClient(FakeClient):
    def analyze(self,tool,args):
        reply=super().analyze(tool,args)
        if tool=='sympas_slice_table':reply['response']={'status':'error','message':'failed slice'}
        if tool=='sympas_dep_graph':
            assert 'Cg' in args['graph_types'] and 'svg' in args['formats']
            reply.update(_callgraph_bytes=SVG,callgraph={'status':'SAVED','upstream_path':'/artifacts/run/f_cg.svg'})
        return reply


def test_partial_analysis_has_verified_svg_and_archive_and_no_replay(tmp_path):
    service=AnalysisService(tmp_path,client_factory=SvgClient);job=create(service);service.run(job['id'])
    report=service.get(job['id'],actor_id='operator');cg=report['callgraph']
    assert report['status']=='PARTIAL' and cg['status']=='SAVED'
    assert cg['source_sha256']==report['source']['source_sha256'] and cg['analysis_id']==job['id']
    assert cg['sha256']==hashlib.sha256(SVG).hexdigest()
    assert service.callgraph_bytes(job['id'],actor_id='operator')==SVG
    with zipfile.ZipFile(service.export(job['id'],actor_id='operator')) as z:
        assert z.read(cg['ref'])==SVG
        assert json.loads(z.read('manifest.json'))['files'][cg['ref']]==cg['sha256']
    assert not service.run(job['id'])
    with pytest.raises(LookupError):service.callgraph_bytes(job['id'],actor_id='other')
    (service.directory(job['id'])/cg['ref']).write_bytes(b'changed')
    with pytest.raises(ValueError):service.get(job['id'],actor_id='operator')
    with pytest.raises(ValueError):service.export(job['id'],actor_id='operator')


def test_svg_route_is_session_scoped_and_sandboxed(tmp_path):
    from nexus.demo.app import create_demo_app
    app=create_demo_app(tmp_path);app.config.update(TESTING=True,RUN_ANALYSES=False)
    web=app.test_client();web.get('/')
    with web.session_transaction() as session:actor=session['actor_id']
    service=app.extensions['analysis_service'];service.client_factory=SvgClient
    from nexus.analysis.samples import sample
    job=service.create(sample('sum3')['source'],actor_id=actor,request_key='svg',origin='SAMPLE');service.run(job['id'])
    report=web.get('/api/analysis/'+job['id']).json
    response=web.get(report['callgraph']['view_url'])
    assert response.status_code==200 and response.data==SVG
    assert 'sandbox' in response.headers['Content-Security-Policy']
    assert 'attachment' in web.get(report['callgraph']['download_url']).headers['Content-Disposition']
    other=app.test_client();other.get('/')
    assert other.get(report['callgraph']['view_url']).status_code==404
    (service.directory(job['id'])/report['callgraph']['ref']).unlink()
    assert web.get('/api/analysis/'+job['id']).status_code==409
    assert web.get(report['callgraph']['view_url']).status_code==409


def test_repair_evidence_keeps_native_svg_and_bound_route(tmp_path):
    import asyncio
    from tests.analysis.test_repair_bridge import setup,Transport
    from nexus.demo.app import create_demo_app
    class Native(Transport):
        def analyze(self,tool,args):
            reply=super().analyze(tool,args)
            if tool=='sympas_dep_graph':reply.update(_callgraph_bytes=SVG,callgraph={'status':'SAVED','upstream_path':'/artifacts/run/f_cg.svg'})
            return reply
    store,task,context,bridge=setup(tmp_path,Native)
    asyncio.run(bridge.enrich(task,context))
    event=store.records(task.id,'event')[-1]
    refs=[e for e in event['evidence_files'] if e['record_ref'].endswith('callgraph.svg')]
    assert len(refs)==2 and all((tmp_path/e['record_ref']).read_bytes()==SVG for e in refs)
    app=create_demo_app(tmp_path,provider='rule');app.config['TESTING']=True
    web=app.test_client();web.get('/')
    identity=context['analysis']['files'][0]['analysis_id']
    url=f'/api/demo/tasks/{task.id}/analysis/{identity}'
    result=web.get(url).json
    assert result['callgraph']['view_url']==url+'/callgraph.svg'
    assert web.get(result['callgraph']['view_url']).data==SVG
    assert web.get(f'/api/demo/tasks/{task.id}/analysis/'+('f'*32)+'/callgraph.svg').status_code!=200


def test_impact_svg_is_in_evidence_and_uses_candidate_bound_route(tmp_path):
    from tests.analysis.test_impact import setup,Transport
    from nexus.demo.app import create_demo_app
    class Native(Transport):
        def analyze(self,tool,args):
            reply=super().analyze(tool,args)
            if tool=='sympas_dep_graph':reply.update(_callgraph_bytes=SVG,callgraph={'status':'SAVED','upstream_path':'/artifacts/run/f_cg.svg'})
            return reply
    _,_,candidate,impact=setup(tmp_path,Native);impact.start(candidate.id);impact.run(candidate.id)
    report=impact.get(candidate.id)
    assert len([e for e in report['evidence_files'] if e['record_ref'].endswith('callgraph.svg')])==2
    app=create_demo_app(tmp_path,provider='rule');app.config['TESTING']=True
    web=app.test_client();web.get('/')
    identity=report['files'][0]['after']['analysis_id']
    url=f'/api/demo/candidates/{candidate.id}/impact/analysis/{identity}'
    result=web.get(url).json
    assert result['callgraph']['view_url']==url+'/callgraph.svg'
    assert web.get(result['callgraph']['view_url']).data==SVG


def test_svg_timeout_preserves_graph_without_retry(monkeypatch):
    import asyncio
    import nexus.analysis.client as module
    monkeypatch.setattr(module,'SVG_SECONDS',.01)
    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            await asyncio.sleep(.05)
            yield SVG
    def respond(request):
        if request.method=='POST':return httpx.Response(200,json={'status':'success','graphs':[{'graph_type':'Cg','svg':{'url':'/artifacts/run/f_cg.svg'}}]})
        return httpx.Response(200,stream=Slow())
    with ResearchClient(transport=httpx.MockTransport(respond),token='') as client:reply=client.analyze('sympas_dep_graph',{})
    assert reply['http_status']==200 and reply['response']['status']=='success'
    assert reply['callgraph']['status']=='UNAVAILABLE'
