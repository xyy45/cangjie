"""Synthetic transport/control failures, never evidence of LIVE model success."""
import asyncio
import httpx
from nexus.contracts import CandidateProposal
from nexus.llm.provider import ModelProvider
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore
from test_repair_loop import Client, Provider


def test_paid_request_disconnect_is_in_doubt_without_retry(tmp_path,monkeypatch):
    store=RunStore(tmp_path);task=store.create_task('base','fix',['src/a.cj'])
    monkeypatch.setenv('DEEPSEEK_API_KEY','unit-fixture')
    monkeypatch.setenv('DEEPSEEK_BASE_URL','https://fixture.invalid')
    monkeypatch.setenv('DEEPSEEK_MODEL','TEST_TRANSPORT')
    calls=[]
    class Disconnected:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):
            calls.append(True)
            raise httpx.ReadTimeout('Synthetic connection lost after submission')
    monkeypatch.setattr('nexus.llm.provider.httpx.AsyncClient',Disconnected)
    result=asyncio.run(RepairLoop(store,provider_factory=ModelProvider,client_factory=Client).run(task.id))
    assert result.status=='IN_DOUBT' and result.attempt_count==0
    assert calls==[True]
    assert store.records(task.id,'model_call')[-1]['status']=='IN_DOUBT'
    assert store.records(task.id,'candidate')==[]


def test_proposal_outside_confirmed_scope_is_rejected_before_apply(tmp_path):
    store=RunStore(tmp_path);task=store.create_task('base','fix',['src/a.cj'])
    class Outside(Provider):
        async def propose(self,context):
            return CandidateProposal(edits=[dict(path='src/b.cj',before_hash='a'*64,content='outside')],requirement_refs=['goal'])
    class NoApply(Client):
        async def call_tool(self,name,args):
            assert name!='candidate.apply','Outside scope must not be materialized'
            return await super().call_tool(name,args)
    result=asyncio.run(RepairLoop(store,provider_factory=Outside,client_factory=NoApply).run(task.id))
    assert result.status=='REJECTED' and result.attempt_count==0


def test_outer_timeout_with_started_model_request_is_in_doubt(tmp_path):
    store=RunStore(tmp_path);task=store.create_task('base','fix',['src/a.cj'])
    class TimedOut(Provider):
        async def propose(self,context):
            store.append_record(task.id,'model_call',dict(id='pending',task_id=task.id,origin='TEST',
                model_id='NO_API',request_ref='records/synthetic.json',status='STARTED'))
            raise asyncio.TimeoutError('Synthetic outer deadline after request was recorded')
    result=asyncio.run(RepairLoop(store,provider_factory=TimedOut,client_factory=Client).run(task.id))
    assert result.status=='IN_DOUBT' and result.attempt_count==0


def test_malformed_candidate_stops_but_protected_path_is_rejected(tmp_path,monkeypatch):
    import json
    from nexus.llm.provider import ProviderUnavailable
    for key,value in [('DEEPSEEK_API_KEY','unit-fixture'),('DEEPSEEK_BASE_URL','https://fixture.invalid'),('DEEPSEEK_MODEL','TEST_TRANSPORT')]:
        monkeypatch.setenv(key,value)
    content={'value':'not JSON','usage':1}
    calls=[]
    class Response:
        status_code=200
        text='Synthetic test response, not an actual API result'
        def json(self):return dict(model='TEST_TRANSPORT',usage={'completion_tokens':content['usage']},
            choices=[dict(finish_reason='stop',message={'content':content['value']})])
    class Transport:
        def __init__(self,**kwargs):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def post(self,*args,**kwargs):calls.append(True);return Response()
    monkeypatch.setattr('nexus.llm.provider.httpx.AsyncClient',Transport)
    store=RunStore(tmp_path);task=store.create_task('base','fix',['src/a.cj'])
    async def rejected(expected):
        import pytest
        with pytest.raises(ProviderUnavailable) as failure:await ModelProvider(store,task.id).propose({'goal':'unit'})
        assert failure.value.state==expected
    asyncio.run(rejected('BLOCKED'))
    content['value']=json.dumps({'edits':[{'path':'src/order_test.cj','before_hash':'a'*64,'content':'forbidden'}],'requirement_refs':['goal']})
    asyncio.run(rejected('REJECTED'))
    content['value']=json.dumps({'edits':[{'path':'src/a.cj','before_hash':'a'*64,'content':'valid'}],'requirement_refs':['goal']})
    content['usage']=True
    asyncio.run(rejected('BLOCKED'))
    assert len(calls)==3  # Three explicit test calls, no retry by the provider.
    assert all(call['status']=='FAILED' for call in store.records(task.id,'model_call') if call['id'].endswith('-result'))
