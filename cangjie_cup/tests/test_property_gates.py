"""Property gates and feedback; all transport/model records here are fixtures."""
import asyncio
from copy import deepcopy

import pytest

from nexus.contracts import ToolResult,file_hash
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore
from tests.test_repair_loop import Client,Provider
from tests.test_delivery import checked


def run(tmp_path,mode):
    store=RunStore(tmp_path);task=store.create_task('base','fix',['src/a.cj']);provider=Provider(store,task.id)
    class PropertyClient(Client):
        async def call_tool(self,name,arguments):
            result=await super().call_tool(name,arguments)
            if name=='candidate.test':
                result.data['diagnostics']='Public PASS fixture'
                failure=dict(kind='business_property',property_id='PROP-RANGE',property_text='退款不得超过实付',test_id='Fixture.case0',
                    args=[1000,900,200],actual_return=1100,assertion_value=False,expected_property=True,
                    source=dict(log_ref='records/fixture.log',coordinate='ANSI_STRIPPED_FULL_LOG',start_char=0,end_char=100))
                state='UNKNOWN' if mode=='unknown' else 'FAIL' if mode=='always-fail' or self.attempt==1 else 'PASS'
                report=dict(candidate_id='foreign' if mode=='wrong-binding' else arguments['candidate_id'],state=state,
                    binding=dict(tree_hash='d'*64,properties_hash='a'*64),failures=[failure] if state=='FAIL' else [],reason='fixture unknown' if state=='UNKNOWN' else '')
                result=ToolResult(operation_status='OK',data={**result.data,'properties':report})
            return result
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *_:provider,client_factory=PropertyClient).run(task.id))
    return store,result,provider


def test_property_failure_enters_second_round_without_numeric_expected(tmp_path):
    store,result,provider=run(tmp_path,'second-pass')
    assert result.status=='REVIEW_PENDING' and len(provider.contexts)==2
    feedback=provider.contexts[1]['feedback'][0];failure=feedback['failure_cases'][0]
    assert failure['kind']=='business_property' and failure['actual_return']==1100
    assert failure['assertion_value'] is False and failure['expected_property'] is True
    assert 'expected' not in failure and 'actual' not in failure
    assert feedback['failed_checks'][0]['kind']=='business_property'
    assert feedback['diagnostic_snippets'][0]['visibility']=='PUBLIC'
    assert 'properties_contract' not in str(provider.contexts)


@pytest.mark.parametrize('mode',['unknown','wrong-binding','always-fail'])
def test_property_unavailable_or_failed_cannot_be_selected(tmp_path,mode):
    store,result,provider=run(tmp_path,mode)
    assert result.status in ('BLOCKED','UNREPAIRED')
    assert not any('selected_candidate_id' in e for e in store.records(result.id,'event'))
    assert len(provider.contexts)==(2 if mode=='always-fail' else 1)


@pytest.mark.parametrize('state',['FAIL','UNKNOWN','MISSING'])
def test_delivery_requires_current_property_verification(tmp_path,monkeypatch,state):
    from nexus.repair.property_service import PropertyService
    ws,store,c,delivery=checked(tmp_path)
    def verify(self,candidate_id):
        if state=='MISSING':raise ValueError('property report missing')
        return dict(state=state)
    monkeypatch.setattr(PropertyService,'verify',verify)
    with pytest.raises(ValueError):delivery.check_set_hash(c.id)


def test_property_focus_preserves_absent_numeric_expected(tmp_path):
    from nexus.repair.localization import build_focus
    content='package uploaded\npublic func refundState(paid: Int64, refunded: Int64, requested: Int64): Int64 { return refunded + requested }\n'
    sources={'src/uploaded.cj':dict(content=content,file_hash=file_hash(content))}
    failure=dict(kind='business_property',property_id='PROP-RANGE',property_text='退款不超实付',test_id='Observed.case0',
        args=[1000,900,200],actual_return=1100,assertion_value=False,expected_property=True,source=dict(log_ref='records/property.log'))
    case=dict(test_id=failure['test_id'],log_ref=failure['source']['log_ref'],function='refundState',args=failure['args'],requirement_refs=['REQ-UPLOAD'])
    report=build_focus(sources,[case],[failure],{},dict(baseline_id='b_fixture'))
    target=report['targets'][0]
    assert target['mapping']=='CONFIRMED_CASE' and target['args']==failure['args']
    assert target['expected'] is None and target['actual_return']==1100
    assert target['property_id']=='PROP-RANGE' and target['assertion_value'] is False


@pytest.mark.parametrize('state',['FAIL','UNKNOWN'])
def test_legacy_exploration_blocks_property_execution_in_policy_route(tmp_path,monkeypatch,state):
    import json
    import time
    import cang_sight_server.server as server
    from nexus.contracts import CheckResult
    from nexus.repair.exploration import ExplorationService
    from nexus.repair.property_service import PropertyService
    from tests.test_property_service import setup
    store,ws,task,apply=setup(tmp_path);c=apply();store.update_task(task.id,status='TESTING')
    # Capture the real route; transport and SDK results are explicit fixtures.
    class Transport:
        def __init__(self,*args):pass
        def list_tools(self):return lambda fn:fn
        def call_tool(self):
            def capture(fn):self.handle=fn;return fn
            return capture
    monkeypatch.setattr(server,'Server',Transport)
    async def public(self,cid):return CheckResult(subject_id=cid,kind='test',state='PASS')
    async def old(self,cid,deadline_at=None):return dict(state=state,reason='EXPLICIT LEGACY RESULT FIXTURE')
    async def forbidden(*args,**kwargs):raise AssertionError('legacy failure must not execute properties')
    monkeypatch.setattr(server.CangjieVerifier,'test',public)
    monkeypatch.setattr(ExplorationService,'run',old);monkeypatch.setattr(PropertyService,'run',forbidden)
    route=server.create_server(tmp_path)
    result=asyncio.run(route.handle('candidate.test',dict(schema_version=1,tool_version='1.1',task_id=task.id,request_id='order-fixture',candidate_id=c.id,expected_tree_hash=c.tree_hash,deadline_at=int(time.time()*1000)+60000)))
    data=json.loads(result[0].text)
    assert data['operation_status']=='OK',data
    assert data['data']['exploration']['state']==state and 'properties' not in data['data']


def test_confirmed_property_cannot_be_skipped_by_an_empty_success_envelope(tmp_path):
    from nexus.contracts import CandidateProposal
    from tests.test_property_service import setup
    store,ws,task,_=setup(tmp_path);original=ws.read_file(task.baseline_id,'src/uploaded.cj');contexts=[]
    class Model:
        async def propose(self,context):
            contexts.append(context)
            return CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original+'\n// candidate\n')],requirement_refs=['REQ-UPLOAD'])
    class MissingPropertyClient(Client):
        async def call_tool(self,name,arguments):
            if name=='workspace.list_files':return ToolResult(operation_status='OK',data={'files':[{'path':'src/uploaded.cj'}]})
            if name=='workspace.read_file':return ToolResult(operation_status='OK',data={'content':original,'file_hash':file_hash(original)})
            if name=='candidate.apply':
                self.attempt+=1
                c=ws.apply_candidate(store.get_task(task.id),CandidateProposal.model_validate(arguments['proposal']))
                return ToolResult(operation_status='OK',data=c.model_dump())
            return await super().call_tool(name,arguments)
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *_:Model(),client_factory=MissingPropertyClient).run(task.id))
    assert result.status=='BLOCKED' and len(contexts)==1
    assert 'Required business properties missing' in str(store.records(task.id,'event'))
