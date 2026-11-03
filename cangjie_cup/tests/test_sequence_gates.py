"""Sequence gates and focus projection; model/MCP results here are explicit fixtures."""
import asyncio
from copy import deepcopy
import json

import pytest

from nexus.contracts import CandidateProposal,ToolResult,file_hash
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore
from tests.test_repair_loop import Client,Provider
from tests.test_delivery import checked


def observed_failure():
    from nexus.repair.sequence_trace import interpret
    from tests.test_sequence_trace import contract,trajectory,log
    from tests.test_primitive_trace import TOKEN
    trace=trajectory();text=log([[(0,7),(7,14)]],[(2,'MODEL_MISMATCH')]);failure=interpret(contract(),[trace],TOKEN,text,0,None)['failures'][0]
    for step in failure['steps']:step['source']['log_ref']='records/sequence-fixture.log'
    failure['source']['log_ref']='records/sequence-fixture.log';failure['end_source']['log_ref']='records/sequence-fixture.log'
    return failure


def run(tmp_path,mode):
    store=RunStore(tmp_path);task=store.create_task('base','fix',['src/a.cj']);provider=Provider(store,task.id)
    class SequenceClient(Client):
        async def call_tool(self,name,arguments):
            result=await super().call_tool(name,arguments)
            if name=='candidate.test':
                result.data['diagnostics']='Public PASS fixture'
                state='UNKNOWN' if mode=='unknown' else 'FAIL' if mode=='always-fail' or self.attempt==1 else 'PASS'
                report=dict(candidate_id='foreign' if mode=='wrong-candidate' else arguments['candidate_id'],state=state,
                    binding=dict(tree_hash='changed' if mode=='wrong-tree' else 'd'*64,sequences_hash='a'*64),failures=[observed_failure()] if state=='FAIL' else [],reason='fixture unknown' if state=='UNKNOWN' else '')
                result=ToolResult(operation_status='OK',data={**result.data,'sequences':report})
            return result
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *_:provider,client_factory=SequenceClient).run(task.id))
    return store,result,provider


def test_sequence_failure_enters_next_round_with_full_real_prefix_and_typed_states(tmp_path):
    store,result,provider=run(tmp_path,'second-pass');assert result.status=='REVIEW_PENDING' and len(provider.contexts)==2
    feedback=provider.contexts[1]['feedback'][0];failure=feedback['failure_cases'][0]
    assert failure['kind']=='business_sequence' and failure['initial_state']==0 and failure['context']==[10]
    assert [s['args'] for s in failure['steps']]==[[0,7,10],[7,7,10]]
    assert failure['actual_return']==14 and failure['expected_state']==10 and failure['sequences_hash']=='a'*64
    assert failure['steps'][0]['test_id']==failure['steps'][1]['test_id']
    assert feedback['failed_checks'][0]['kind']=='business_sequence'
    assert feedback['diagnostic_snippets'][0]['visibility']=='PUBLIC' and 'sequences_contract' not in str(provider.contexts)


@pytest.mark.parametrize('mode',['unknown','wrong-candidate','wrong-tree','always-fail'])
def test_invalid_or_failed_sequence_cannot_be_selected(tmp_path,mode):
    store,result,provider=run(tmp_path,mode)
    assert result.status in ('BLOCKED','UNREPAIRED')
    assert not any('selected_candidate_id' in e for e in store.records(result.id,'event'))
    assert len(provider.contexts)==(2 if mode=='always-fail' else 1)


@pytest.mark.parametrize('mode',['missing','wrong-contract','unverified-pass'])
def test_confirmed_sequence_cannot_be_skipped_or_forged_by_success_envelope(tmp_path,mode):
    from tests.test_sequence_service import setup
    store,ws,task,_=setup(tmp_path);original=ws.read_file(task.baseline_id,'src/uploaded.cj');contexts=[]
    class Model:
        async def propose(self,context):
            contexts.append(context)
            return CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original+'\n// candidate\n')],requirement_refs=['REQ-UPLOAD'])
    class MissingSequence(Client):
        async def call_tool(self,name,arguments):
            if name=='workspace.list_files':return ToolResult(operation_status='OK',data=dict(files=[dict(path='src/uploaded.cj')]))
            if name=='workspace.read_file':return ToolResult(operation_status='OK',data=dict(content=original,file_hash=file_hash(original)))
            if name=='candidate.apply':
                self.attempt+=1;c=ws.apply_candidate(store.get_task(task.id),CandidateProposal.model_validate(arguments['proposal']));self.c=c
                return ToolResult(operation_status='OK',data=c.model_dump())
            result=await super().call_tool(name,arguments)
            if name=='candidate.test' and mode!='missing':
                from nexus.uploads.service import UploadService
                from nexus.requirements.service import RequirementService
                spec,_=RequirementService(store).task_context(task);upload=UploadService(store)._read(spec.project_id)
                result.data['sequences']=dict(state='PASS',candidate_id=self.c.id,binding=dict(tree_hash=self.c.tree_hash,sequences_hash='changed' if mode=='wrong-contract' else upload['sequences_hash']))
            return result
    result=asyncio.run(RepairLoop(store,provider_factory=lambda *_:Model(),client_factory=MissingSequence).run(task.id))
    assert result.status=='BLOCKED' and len(contexts)==1
    assert 'selected_candidate_id' not in str(store.records(task.id,'event'))


@pytest.mark.parametrize('state',['FAIL','UNKNOWN','MISSING'])
def test_delivery_requires_current_sequence_pass(tmp_path,monkeypatch,state):
    from nexus.repair.sequence_service import SequenceService
    ws,store,c,delivery=checked(tmp_path)
    def verify(self,candidate_id):
        if state=='MISSING':raise ValueError('sequence report missing')
        return dict(state=state)
    monkeypatch.setattr(SequenceService,'verify',verify)
    with pytest.raises(ValueError):delivery.check_set_hash(c.id)


@pytest.mark.parametrize('earlier',['oracle','properties','relations',None])
@pytest.mark.parametrize('state',['FAIL','UNKNOWN'])
def test_route_runs_sequence_only_after_all_predecessors_pass(tmp_path,monkeypatch,earlier,state):
    import time
    import cang_sight_server.server as server
    from nexus.contracts import CheckResult
    from nexus.repair.exploration import ExplorationService
    from nexus.repair.property_service import PropertyService
    from nexus.repair.relation_service import RelationService
    from nexus.repair.sequence_service import SequenceService
    from tests.test_sequence_service import setup
    store,ws,task,apply=setup(tmp_path);c=apply();store.update_task(task.id,status='TESTING');calls=[]
    class Transport:
        def __init__(self,*args):pass
        def list_tools(self):return lambda fn:fn
        def call_tool(self):
            def capture(fn):self.handle=fn;return fn
            return capture
    async def public(self,cid):return CheckResult(subject_id=cid,kind='test',state='PASS')
    def check(name):
        async def run(self,cid,deadline_at=None):
            calls.append(name)
            if earlier and list(('oracle','properties','relations','sequences')).index(name)>list(('oracle','properties','relations','sequences')).index(earlier):raise AssertionError('later gate executed after failure')
            return dict(state=state if name==earlier else 'PASS')
        return run
    monkeypatch.setattr(server,'Server',Transport);monkeypatch.setattr(server.CangjieVerifier,'test',public)
    for cls,name in [(ExplorationService,'oracle'),(PropertyService,'properties'),(RelationService,'relations'),(SequenceService,'sequences')]:monkeypatch.setattr(cls,'run',check(name))
    route=server.create_server(tmp_path);result=asyncio.run(route.handle('candidate.test',dict(schema_version=1,tool_version='1.1',task_id=task.id,request_id='sequence-order-fixture',candidate_id=c.id,expected_tree_hash=c.tree_hash,deadline_at=int(time.time()*1000)+60000)))
    data=json.loads(result[0].text);assert data['operation_status']=='OK',data
    if earlier:assert 'sequences' not in data['data'] and 'sequences' not in calls
    else:assert data['data']['sequences']['state']=='PASS' and calls==['oracle','properties','relations','sequences']


def focus(failures):
    from nexus.repair import localization
    assert hasattr(localization,'sequence_calls'),'state steps need independent call identities'
    cases,calls=localization.sequence_calls(failures,'refund')
    source='package uploaded\npublic func refund(state: Int64, amount: Int64, paid: Int64): Int64 { return state + amount }\n'
    return localization.build_focus({'src/uploaded.cj':dict(content=source,file_hash=file_hash(source))},cases,calls,{},dict(baseline_id='b_fixture'))


def test_steps_sharing_sdk_case_do_not_collide_in_focus():
    failure=observed_failure();before=deepcopy(failure);report=focus([failure]);assert failure==before
    targets=report['targets'];assert len(targets)==2 and all(t['mapping']=='CONFIRMED_CASE' for t in targets)
    assert len({t['call_id'] for t in targets})==2 and len({t['test_id'] for t in targets})==1
    assert targets[0]['step_index']==1 and targets[0]['sequence_role']=='failure' and targets[1]['step_index']==0
    assert targets[0]['args']==[7,7,10] and targets[1]['args']==[0,7,10]
    assert targets[0]['failure_ids']==failure['failure_ids'] and targets[0]['expected_state']==10
    assert all(t['locations'][0]['coordinate_subject_id']=='b_fixture' for t in targets)


def test_multiple_labels_on_same_step_group_without_duplicate_calls():
    first=observed_failure();second=deepcopy(first);second['failure_ids']=['INV-EXTRA'];report=focus([first,second])
    assert len(report['targets'])==2 and set(report['targets'][0]['failure_ids'])=={'MODEL-OP-REFUND','INV-BOUND','INV-EXTRA'}


def test_focus_prioritizes_each_failed_step_and_flags_truncation():
    failures=[]
    for i in range(8):
        failure=observed_failure();failure['sequence_id']='SEQUENCE-fixture'+str(i)
        failures.append(failure)
    report=focus(failures);assert len(report['targets'])==8 and report['truncated'] is True
    assert all(t['sequence_role']=='failure' and t['step_index']==1 for t in report['targets'])
    assert len({t['sequence_id'] for t in report['targets']})==8
    assert all(len(f['steps'])==2 for f in failures)
