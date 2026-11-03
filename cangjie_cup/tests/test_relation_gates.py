"""Controller/route/delivery gates; transport and model outputs are fixtures."""
import asyncio
from copy import deepcopy

import pytest

from nexus.contracts import CandidateProposal,ToolResult,file_hash
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore
from tests.test_repair_loop import Client,Provider
from tests.test_delivery import checked


def observed_failure():
    return dict(kind='business_relation',relation_id='REL-MONOTONE',relation_text='增加数量不得降低金额',pair_id='PAIR-fixture',
        left_args=[9,100,False],right_args=[10,100,False],left_actual_return=900,right_actual_return=0,
        assertion_value=False,expected_relation=True,left_test_id='Fixture.case0',right_test_id='Fixture.case1',
        left_source=dict(log_ref='records/relation-fixture.log',coordinate='ANSI_STRIPPED_FULL_LOG',start_char=0,end_char=80),
        right_source=dict(log_ref='records/relation-fixture.log',coordinate='ANSI_STRIPPED_FULL_LOG',start_char=90,end_char=170))


def run(tmp_path,mode):
    store=RunStore(tmp_path);task=store.create_task('base','fix',['src/a.cj']);provider=Provider(store,task.id)
    class RelationClient(Client):
        async def call_tool(self,name,arguments):
            result=await super().call_tool(name,arguments)
            if name=='candidate.test':
                result.data['diagnostics']='Public PASS fixture'
                state='UNKNOWN' if mode=='unknown' else 'FAIL' if mode=='always-fail' or self.attempt==1 else 'PASS'
                report=dict(candidate_id='foreign' if mode=='wrong-binding' else arguments['candidate_id'],state=state,
                    binding=dict(tree_hash='d'*64,relations_hash='a'*64),failures=[observed_failure()] if state=='FAIL' else [],reason='fixture unknown' if state=='UNKNOWN' else '')
                result=ToolResult(operation_status='OK',data={**result.data,'relations':report})
            return result
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *_:provider,client_factory=RelationClient).run(task.id))
    return store,result,provider


def test_relation_failure_drives_next_round_with_two_returns_and_no_numeric_expected(tmp_path):
    store,result,provider=run(tmp_path,'second-pass')
    assert result.status=='REVIEW_PENDING' and len(provider.contexts)==2
    feedback=provider.contexts[1]['feedback'][0];failure=feedback['failure_cases'][0]
    assert failure['kind']=='business_relation' and failure['left_actual_return']==900 and failure['right_actual_return']==0
    assert failure['left_test_id']!=failure['right_test_id'] and failure['relations_hash']=='a'*64
    assert failure['assertion_value'] is False and failure['expected_relation'] is True
    assert 'expected' not in failure and 'actual' not in failure and feedback['failed_checks'][0]['kind']=='business_relation'
    assert feedback['diagnostic_snippets'][0]['visibility']=='PUBLIC' and 'relations_contract' not in str(provider.contexts)


@pytest.mark.parametrize('mode',['unknown','wrong-binding','always-fail'])
def test_relation_unknown_mismatch_or_failure_cannot_be_selected(tmp_path,mode):
    store,result,provider=run(tmp_path,mode)
    assert result.status in ('BLOCKED','UNREPAIRED')
    assert not any('selected_candidate_id' in event for event in store.records(result.id,'event'))
    assert len(provider.contexts)==(2 if mode=='always-fail' else 1)


def test_confirmed_relation_cannot_be_skipped_by_empty_ok_envelope(tmp_path):
    from tests.test_relation_service import setup
    store,ws,task,_=setup(tmp_path);original=ws.read_file(task.baseline_id,'src/uploaded.cj');contexts=[]
    class Model:
        async def propose(self,context):
            contexts.append(context)
            return CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original+'\n// candidate\n')],requirement_refs=['REQ-UPLOAD'])
    class MissingRelation(Client):
        async def call_tool(self,name,arguments):
            if name=='workspace.list_files':return ToolResult(operation_status='OK',data=dict(files=[dict(path='src/uploaded.cj')]))
            if name=='workspace.read_file':return ToolResult(operation_status='OK',data=dict(content=original,file_hash=file_hash(original)))
            if name=='candidate.apply':
                self.attempt+=1;c=ws.apply_candidate(store.get_task(task.id),CandidateProposal.model_validate(arguments['proposal']))
                return ToolResult(operation_status='OK',data=c.model_dump())
            return await super().call_tool(name,arguments)
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *_:Model(),client_factory=MissingRelation).run(task.id))
    assert result.status=='BLOCKED' and len(contexts)==1
    assert 'Required business relations missing' in str(store.records(task.id,'event'))


@pytest.mark.parametrize('state',['FAIL','UNKNOWN','MISSING'])
def test_delivery_requires_current_relation_result(tmp_path,monkeypatch,state):
    from nexus.repair.relation_service import RelationService
    ws,store,c,delivery=checked(tmp_path)
    def verify(self,candidate_id):
        if state=='MISSING':raise ValueError('relation report missing')
        return dict(state=state)
    monkeypatch.setattr(RelationService,'verify',verify)
    with pytest.raises(ValueError):delivery.check_set_hash(c.id)


@pytest.mark.parametrize('earlier',['oracle','properties'])
@pytest.mark.parametrize('state',['FAIL','UNKNOWN'])
def test_earlier_failure_stops_relation_execution_in_real_policy_route(tmp_path,monkeypatch,earlier,state):
    import json,time
    import cang_sight_server.server as server
    from nexus.contracts import CheckResult
    from nexus.repair.exploration import ExplorationService
    from nexus.repair.property_service import PropertyService
    from nexus.repair.relation_service import RelationService
    from tests.test_relation_service import setup
    store,ws,task,apply=setup(tmp_path);c=apply();store.update_task(task.id,status='TESTING')
    class Transport:
        def __init__(self,*args):pass
        def list_tools(self):return lambda fn:fn
        def call_tool(self):
            def capture(fn):self.handle=fn;return fn
            return capture
    async def public(self,cid):return CheckResult(subject_id=cid,kind='test',state='PASS')
    async def numeric(self,cid,deadline_at=None):return dict(state=state) if earlier=='oracle' else None
    async def single(self,cid,deadline_at=None):
        if earlier=='oracle':raise AssertionError('oracle failure must stop single properties')
        return dict(state=state)
    async def forbidden(*args,**kwargs):raise AssertionError('earlier failure must stop relation')
    monkeypatch.setattr(server,'Server',Transport);monkeypatch.setattr(server.CangjieVerifier,'test',public)
    monkeypatch.setattr(ExplorationService,'run',numeric);monkeypatch.setattr(PropertyService,'run',single);monkeypatch.setattr(RelationService,'run',forbidden)
    route=server.create_server(tmp_path)
    result=asyncio.run(route.handle('candidate.test',dict(schema_version=1,tool_version='1.1',task_id=task.id,request_id='relation-order-fixture',candidate_id=c.id,expected_tree_hash=c.tree_hash,deadline_at=int(time.time()*1000)+60000)))
    data=json.loads(result[0].text)
    assert data['operation_status']=='OK',data
    assert data['data'][earlier if earlier=='properties' else 'exploration']['state']==state and 'relations' not in data['data']


def test_same_pair_failing_two_relations_maps_each_real_side_without_case_collision():
    from nexus.repair import localization
    assert hasattr(localization,'relation_calls'),'paired failures need two independent localization targets'
    first=observed_failure();second={**deepcopy(first),'relation_id':'REL-SECOND','relation_text':'第二关系'}
    cases,failures=localization.relation_calls([first,second],'amount')
    content='package uploaded\npublic func amount(quantity: Int64, price: Int64, promotion: Bool): Int64 { return quantity * price }\n'
    sources={'src/uploaded.cj':dict(content=content,file_hash=file_hash(content))}
    report=localization.build_focus(sources,cases,failures,{},dict(baseline_id='b_fixture'))
    assert len(report['targets'])==4
    assert [t['relation_role'] for t in report['targets']]==['left','right','left','right']
    assert [t['actual_return'] for t in report['targets']]==[900,0,900,0]
    assert all(t['mapping']=='CONFIRMED_CASE' and t['function']=='amount' and t['expected'] is None for t in report['targets'])
    assert {t['pair_id'] for t in report['targets']}=={'PAIR-fixture'}
    assert {t['relation_id'] for t in report['targets']}=={'REL-MONOTONE','REL-SECOND'}
