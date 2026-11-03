"""Real SDK/native four-service loop; candidates are explicit local fixtures."""
import asyncio,importlib,json
import pytest
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.contracts import CandidateProposal,file_hash,source_manifest
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.adapters.cangjie.verifier import CangjieVerifier
from tests.sdk.test_package_reports_sdk import save

pytestmark=pytest.mark.sdk
MODULES={'oracle':('exploration','ExplorationService'),'property':('property_service','PropertyService'),
         'relation':('relation_service','RelationService'),'sequence':('sequence_service','SequenceService')}


def state(n,items=None):return {'$type':'bench.model.State','fields':{'amount':n,'items':[1,2] if items is None else items}}


def material():
    return {'cjpm.toml':CONFIG,'cjpm.lock':LOCK,
        'src/step.cj':b'''package bench
import bench.model.State
func step(state: State, n: Int64): State {
 if (state.amount >= 2) { return State(state.amount+n+1, state.items) }
 State(state.amount+n, state.items)
}
''',
        'src/model/state.cj':b'''package bench.model
public class State {
 public let amount: Int64
 public let items: Array<Int64>
 public init(amount: Int64, items: Array<Int64>) { this.amount=amount; this.items=items }
}
''',
        'src/cases_test.cj':b'''package bench
import bench.model.State
import std.unittest.*
import std.unittest.testmacro.*
// ORIGINAL_TEST_BODY_NOT_FOR_MODEL
@Test class Cases { @TestCase func case0() { @Expect(step(State(0, [1,2]),1).amount,1) } }
'''}


def rule(kind):
    domains=dict(state=dict(values=[state(i,items) for i in range(4) for items in ([],[1,2])]),n=dict(min=1,max=1,points=[]))
    common=dict(version=6 if kind=='oracle' else 5,function='bench.step',domains=domains,seed=7,excluded_inputs=[])
    if kind=='oracle':return dict(**common,expression='object_with(state,"amount",object_get(state,"amount")+n)',max_cases=16)
    if kind=='property':return dict(**common,kind='single',properties=[dict(id='PROP-STEP',text='金额增加且保留数组',precondition='True',
        assertion='object_get(result,"amount") == object_get(arg0,"amount")+arg1 and object_get(result,"items") == object_get(arg0,"items")')],max_cases=16)
    if kind=='relation':return dict(**common,kind='relation',relations=[dict(id='REL-INC',text='连续初始金额相差一',
        precondition='object_get(right_arg0,"amount") == object_get(left_arg0,"amount")+1 and object_get(left_arg0,"items") == object_get(right_arg0,"items") and left_arg1 == right_arg1',
        assertion='object_get(right_result,"amount") == object_get(left_result,"amount")+1')],max_pairs=16)
    return dict(**common,kind='sequence',state_param='state',initial_states=[state(0)],initial_precondition='True',context_params=[],
        operations=[dict(id='OP-INC',text='增加金额',args=[1],transition='object_with(state,"amount",object_get(state,"amount")+1)')],
        invariants=[dict(id='INV-POSITIVE',text='金额非负',precondition='True',assertion='object_get(result,"amount") >= 0')],max_sequences=8,max_steps=3)


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_scoped_public_pass_independent_fail_shrink_fixed_pass_and_rebuild(tmp_path,kind):
    files=material();store=RunStore(tmp_path);uploads=UploadService(store)
    draft=uploads.prepare_project('scoped',None,'增加金额且完整保留数组，连续调用保持正确状态',actor_id='alice',request_key='one',entries=files)
    values=[dict(args=[state(0),1],expected=state(1),suite='target'),dict(args=[state(1,[]),1],expected=state(2,[]),suite='regression')]
    field={'oracle':'oracle','property':'properties','relation':'relations','sequence':'sequences'}[kind]
    frozen=uploads.confirm(draft['id'],expected_version=1,function='bench.step',examples_json=json.dumps(values),
        consent=True,actor_id='alice',allowed_paths=['src/step.cj'],**{field+'_json':json.dumps(rule(kind))})
    root=uploads.source(draft['id'],actor_id='alice');ws=WorkspaceStore(tmp_path,registered=[root]);baseline=ws.import_project(root,'.')
    requirements=RequirementService(store);d=requirements.prepare_requirement(draft['id'],frozen['goal'])
    spec=requirements.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='alice')
    task=requirements.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    module,cls=MODULES[kind];engine=getattr(importlib.import_module('nexus.repair.'+module),cls)(store)
    async def run():
        histories=[];last=None
        for fixed in (False,True):
            code=files['src/step.cj'].decode().replace('state.amount+n+1','state.amount+n') if fixed else files['src/step.cj'].decode()+'\n// explicit local defect fixture'
            c=ws.apply_candidate(store.get_task(task.id),CandidateProposal(edits=[dict(path='src/step.cj',before_hash=file_hash(files['src/step.cj'].decode()),content=code)],requirement_refs=['REQ-UPLOAD']))
            verifier=CangjieVerifier(tmp_path,task.id);built=await verifier.build(c.id);assert built.state=='PASS',built
            checked=await verifier.test(c.id);assert checked.state=='PASS',checked
            before=source_manifest(ws.subject_path(c.id));report=await engine.run(c.id)
            assert report['state']==('PASS' if fixed else 'FAIL'),report
            assert engine.verify(c.id)==report and await engine.run(c.id)==report
            assert source_manifest(ws.subject_path(c.id))==before
            assert not any('bridge' in p or 'nexus_verify_' in p for p in before)
            if not fixed:assert report['failures'] and len(report['batches'])>=2,report
            histories.append(report);last=c
        save(tmp_path,'immutable-service-originals',{p.name:p.read_bytes() for p in (tmp_path/'records').iterdir() if p.is_file()})
        save(tmp_path,'service-history',histories)
        probe=tmp_path/histories[-1]['batches'][0]['project_path'];bridge=next(probe.glob('src/nexus_verify_bridge_*.cj'))
        bridge.write_bytes(bridge.read_bytes()+b'\n// disposable tamper control')
        with pytest.raises(ValueError):engine.verify(last.id)
    asyncio.run(run())
