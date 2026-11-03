import httpx
import pytest
from nexus.analysis.client import ResearchClient, AnalysisUnavailable


def test_only_fixed_analysis_tools_and_endpoint_can_be_called():
    calls=[]
    def reply(request):
        calls.append(request)
        return httpx.Response(200,json={'status':'success','data':{'backward_slices':{}}})
    with ResearchClient(transport=httpx.MockTransport(reply),token='dummy-secret') as client:
        result=client.analyze('sympas_slice',{'filename':'a.cj','code':'return 1','lang':'cangjie','line':1})
        assert result['http_status']==200
        with pytest.raises(ValueError):client.analyze('agentic_repair',{})
    assert len(calls)==1 and calls[0].url.path=='/tools/sympas_slice'
    assert 'api_key' not in calls[0].content.decode()


def test_timeout_does_not_retry_or_echo_credential():
    calls=[]
    def fail(request):calls.append(request);raise httpx.ReadTimeout('dummy-secret')
    with ResearchClient(transport=httpx.MockTransport(fail),token='dummy-secret') as client:
        with pytest.raises(AnalysisUnavailable) as error:client.analyze('sympas_slice',{})
    assert len(calls)==1 and 'dummy-secret' not in str(error.value)


def test_escaped_token_is_removed_before_persistence():
    import json
    payload={'status':'success','data':{'note':'dummy-secret'},'preview':json.dumps({'echo':'dummy-secret'}).replace('dummy-secret',r'\u0064ummy-secret')}
    with ResearchClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json=payload)),token='dummy-secret') as client:
        result=client.analyze('sympas_slice',{})
    assert 'dummy-secret' not in json.dumps(result)
    assert json.loads(result['response']['preview'])['echo']=='[REDACTED]'

@pytest.mark.parametrize('url',['http://127.0.0.1:6240','http://47.94.83.64:1','http://47.94.83.64:6240@evil.example','https://evil.example','http://47.94.83.64:6240?token=secret'])
def test_arbitrary_endpoints_are_not_accepted(url):
    with pytest.raises(AnalysisUnavailable):ResearchClient(url=url)


def test_redirect_is_not_followed():
    calls=[]
    def reply(request):calls.append(request);return httpx.Response(302,headers={'Location':'https://evil.example'})
    with ResearchClient(transport=httpx.MockTransport(reply)) as client:result=client.analyze('sympas_slice',{})
    assert result['http_status']==302 and len(calls)==1


def test_total_deadline_cancels_a_stream_even_if_read_timeout_would_not(monkeypatch):
    import asyncio
    import nexus.analysis.client as module
    monkeypatch.setattr(module,'REQUEST_SECONDS',.01)
    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{'
            await asyncio.sleep(.05)
            yield b'}'
    with ResearchClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,stream=Slow()))) as client:
        with pytest.raises(AnalysisUnavailable):client.analyze('sympas_slice',{})
