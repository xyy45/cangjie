"""Self-built object defects/reference fixes with real SDK/native service gates.

No live model or remote analysis quality is measured here.
"""
import asyncio,json
from copy import deepcopy
import pytest
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.contracts import CandidateProposal,file_hash,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.uploads.language import literal
from nexus.projects.index import inspect_project
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.repair import oracle,sequences
from nexus.repair.sequence_service import failure_trace
from tests.sdk.test_string_loop_sdk import SERVICES
from tests.sdk.test_objects_sdk import declaration
from tests.test_object_contracts import state

pytestmark=pytest.mark.sdk
NL=chr(10)


def scenario(kind,mode='normal'):
    if kind=='sequence':
        bug='if (this.amount == 1 && mode >= 70) { return this }\n' if mode!='public' else 'if (this.amount == 0 && mode == 100) { return this }\n'
        method=NL.join(['public func flip(mode: Int64, items: Array<Int64>): OrderState {','if (items.size == 0) { return this }',bug,'return OrderState(1 - this.amount, this.label, this.active, this.items)','}',''])
        code='package bench\n'+declaration('class').rsplit('}\n',1)[0]+method+'}\n'
        wrapper=b'package bench\npublic func advance(mode: Int64, current: OrderState, items: Array<Int64>): OrderState { return current.flip(mode, items) }\n'
        domains=dict(mode=dict(min=0,max=100,points=[]),current=dict(values=[state(0),state(1)]),items=dict(values=[[],[1,2]]))
        model=dict(version=4,kind='sequence',function='advance',state_param='current',domains=domains,initial_states=[state(0)],initial_precondition='array_len(ctx2) > 0',context_params=['items'],
            operations=[dict(id='OP-FLIP',text='使用固定数组上下文切换对象状态，mode不改变语义',args=[dict(domain='mode'),dict(context='items')],transition='object_with(state,"amount",1-object_get(state,"amount")) if array_len(arg2)>0 else state')],
            invariants=[dict(id='INV-REFERENCE',text='所有字段等于参考状态',precondition='True',assertion='result == expected_state')],seed=7,max_sequences=8,max_steps=4,excluded_inputs=[])
        return dict(function='advance',path='src/state.cj',files={'src/state.cj':code.encode(),'src/order.cj':wrapper},fixed=code.replace(bug,''),bug=bug,model=model,
            goal='数组上下文非空时每步切换amount字段0和1；空上下文保持状态。mode不改变业务，保留label/active/items字段，连续调用使用真实上次返回。',
            examples=[dict(args=[100,state(0),[1,2]],expected=state(1),suite='target'),dict(args=[0,state(0),[]],expected=state(0),suite='regression')])
    method='public func change(n: Int64): OrderState { return OrderState(this.amount - n, this.label, this.active, this.items) }\n'
    code='package bench\n'+declaration('class').rsplit('}\n',1)[0]+method+'}\n';fixed=code.replace('this.amount - n','this.amount + n')
    files={'src/state.cj':code.encode(),'src/order.cj':b'package bench\npublic func adjust(state: OrderState, n: Int64): OrderState { return state.change(n) }\n'}
    domains=dict(state=dict(values=[state(0),state(1),state(2),state(3)]),n=dict(min=0,max=1,points=[]))
    if kind=='oracle':model=dict(version=5,function='adjust',domains=domains,expression='object_with(state,"amount",object_get(state,"amount")+n)',seed=7,max_cases=16,excluded_inputs=[])
    elif kind=='property':model=dict(version=4,kind='single',function='adjust',domains=domains,properties=[dict(id='PROP-INCREASE',text='非负增量必须准确加到amount，其他字段保留',precondition='True',assertion='object_get(result,"amount")==object_get(arg0,"amount")+arg1 and object_get(result,"items")==object_get(arg0,"items") and object_get(result,"label")==object_get(arg0,"label") and object_get(result,"active")==object_get(arg0,"active")')],seed=7,max_cases=16,excluded_inputs=[])
    else:model=dict(version=4,kind='relation',function='adjust',domains=domains,relations=[dict(id='REL-MONOTONIC',text='相同起始状态的增量增大时结果不下降',precondition='left_arg0 == right_arg0 and left_arg1 <= right_arg1',assertion='object_get(left_result,"amount") <= object_get(right_result,"amount")')],seed=7,max_pairs=16,excluded_inputs=[])
    if mode=='unknown':
        assert kind=='oracle';code=fixed;files['src/state.cj']=code.encode();domains['state']['values']=[state(0),state(1),state((1<<63)-1)]
        model['expression']='object_with(state,"amount",object_get(state,"amount") if n > 9223372036854775807-object_get(state,"amount") else object_get(state,"amount")+n)'
    return dict(function='adjust',path='src/state.cj',files=files,fixed=fixed,model=model,goal='amount加上非负n并保留其他字段'+('，达到Int64上限时封顶' if mode=='unknown' else ''),examples=[dict(args=[state(1),0],expected=state(1),suite='target'),dict(args=[state(0),0],expected=state(0),suite='regression')])


def setup(root,kind,mode='normal'):
    data=scenario(kind,mode);store=RunStore(root);uploads=UploadService(store);files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,**data['files']};info=inspect_project(files);types=info['types']
    original='package bench\nimport std.unittest.*\nimport std.unittest.testmacro.*\n@Test\nclass OriginalFields {\n'
    for index,example in enumerate(data['examples']):original+=' @TestCase\n func case'+str(index)+'() { @Expect('+data['function']+'('+', '.join(literal(a,types) for a in example['args'])+').amount, '+str(example['expected']['fields']['amount'])+') }\n'
    files['src/original_test.cj']=(original+'}\n').encode();draft=uploads.prepare_project('objects-'+kind,None,data['goal'],actor_id='OBJECT_SDK_FIXTURE',request_key='one',entries=files)
    key=dict(oracle='oracle_json',property='properties_json',relation='relations_json',sequence='sequences_json')[kind]
    uploads.confirm(draft['id'],expected_version=1,function=data['function'],examples_json=json.dumps(data['examples']),allowed_paths=[data['path']],consent=True,actor_id='OBJECT_SDK_FIXTURE',**{key:json.dumps(data['model'])})
    source=uploads.source(draft['id'],actor_id='OBJECT_SDK_FIXTURE');ws=WorkspaceStore(root,registered=[source]);baseline=ws.import_project(source,'.');req=RequirementService(store);d=req.prepare_requirement(draft['id'],draft['goal']);spec=req.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='OBJECT_SDK_FIXTURE');task=req.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,data['path']);data['types']=types
    def candidate(fixed=False):return ws.apply_candidate(store.get_task(task.id),CandidateProposal(edits=[dict(path=data['path'],before_hash=file_hash(original),content=(data['fixed'] if fixed else original)+'\n// explicit reference candidate\n')],requirement_refs=['REQ-UPLOAD']))
    return store,ws,task,candidate,data


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_object_public_pass_independent_failure_reference_fix_and_full_history(tmp_path,kind):
    store,ws,task,apply,data=setup(tmp_path.resolve(),kind);verifier=CangjieVerifier(store.root,task.id);engine=SERVICES[kind](store);reports=[]
    for fixed in (False,True):
        candidate=apply(fixed);assert asyncio.run(verifier.build(candidate.id)).state=='PASS'
        public=asyncio.run(verifier.test(candidate.id));assert public.state=='PASS',public.diagnostics
        before=source_manifest(ws.subject_path(candidate.id));report=asyncio.run(engine.run(candidate.id));reports.append(report)
        (tmp_path/(('fixed' if fixed else 'defect')+'-report.json')).write_text(json.dumps(report,ensure_ascii=True,indent=2))
        assert report['state']==('PASS' if fixed else 'FAIL'),(report.get('reason'),report)
        assert report['public_test_state']=='PASS' and engine.verify(candidate.id)==report and source_manifest(ws.subject_path(candidate.id))==before
        for batch in report['batches']:
            log=(store.root/batch['log_ref']).read_text();assert 'NEXUS_EXECUTION_PHASE' in log and '_V4|' in log and 'FIXTURE' not in log
    failed,passed=reports
    if kind=='sequence':
        contract=engine.binding(passed['candidate_id'])[3];retained={sequences.trace_key(failure_trace(contract,f)) for f in failed['failures']}
        assert contract['state_index']==1 and contract['context_indices']==[2] and passed['regression_traces']>0 and retained<={sequences.trace_key(t) for t in passed['batches'][0]['traces']}
        first=failed['batches'][0]['result']['failures'];later=[f for b in failed['batches'][1:] for f in b['result']['failures']]
        assert later and min(sequences.trace_score(failure_trace(contract,f)) for f in later)<min(sequences.trace_score(failure_trace(contract,f)) for f in first)
        assert all('不覆盖多字段对象' not in text for text in passed['limitations'])
    elif kind=='relation':assert passed['regression_pairs']>0
    else:assert passed['regression_cases']>0 and {oracle.input_key(f['args']) for f in failed['failures']}<={oracle.input_key(a) for a in passed['batches'][0]['inputs']}
