"""Array service reconstruction over explicit SDK fixtures; native axes are real.

These tests are not SDK or model repair quality evidence.
"""
import asyncio,importlib,json,re
from copy import deepcopy
from pathlib import Path
import pytest
from nexus.contracts import CandidateProposal,file_hash,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.repair import oracle,primitive_trace,sequence_trace,sequences,array_trace,string_trace,values
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_array_uploads import prepare
from tests.test_array_contracts import raw_oracle,raw_property,raw_relation,sequence_raw
from tests.test_relation_service import record_public
from tests.sdk.test_arrays_sdk import rotation_source

MODULES={'oracle':'nexus.repair.exploration','property':'nexus.repair.property_service','relation':'nexus.repair.relation_service','sequence':'nexus.repair.sequence_service'}
CLASSES={'oracle':'ExplorationService','property':'PropertyService','relation':'RelationService','sequence':'SequenceService'}


def register(uploads,draft,args,models,kind):
    kwargs={('properties' if k=='property' else 'relations' if k=='relation' else 'sequences' if k=='sequence' else k)+'_json':json.dumps(v) for k,v in models.items()}
    uploads.confirm(draft['id'],**args,**kwargs);source=uploads.source(draft['id'],actor_id='alice');store=uploads.store;ws=WorkspaceStore(store.root,registered=[source]);baseline=ws.import_project(source,'.')
    req=RequirementService(store);d=req.prepare_requirement(draft['id'],uploads.profile(draft['id'])['goal'])
    spec=req.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='alice');task=req.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/uploaded.cj')
    def apply(suffix=''):
        c=ws.apply_candidate(store.get_task(task.id),CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=original+'\n// explicit fixture '+suffix+'\n')],requirement_refs=['REQ-UPLOAD']))
        record_public(store,ws,task,c);return c
    engine=getattr(importlib.import_module(MODULES[kind]),CLASSES[kind])(store)
    return store,ws,task,apply,engine


def setup(root,kind,*,previous=False,array_return=False):
    if kind=='sequence':
        raw,_=sequence_raw();uploads=UploadService(RunStore(root));draft=uploads.prepare('state.cj',rotation_source().encode(),'数组状态交换／重置',actor_id='alice',request_key='s')
        args=dict(expected_version=1,function='rotateState',examples_json=json.dumps([dict(args=[0,[1,2],'a'],expected=[2,1],suite='target'),dict(args=[1,[2,1],'a'],expected=[],suite='regression')]),consent=True,actor_id='alice');models=dict(sequence=raw)
    elif array_return:
        uploads=UploadService(RunStore(root));draft=uploads.prepare('items.cj',b'public func orderItems(items: Array<Int64>): Array<Int64> { if (items.size == 0) { return [0] }; return items }\n','返回原项目，包含空数组',actor_id='alice',request_key='i')
        args=dict(expected_version=1,function='orderItems',examples_json=json.dumps([dict(args=[[1]],expected=[1],suite='target'),dict(args=[[2,1]],expected=[2,1],suite='regression')]),consent=True,actor_id='alice')
        models=dict(oracle=dict(version=4,function='orderItems',domains=dict(items=dict(values=[[],[1],[2,1]])),expression='items',seed=7,max_cases=16,excluded_inputs=[]))
    else:
        uploads,draft,args=prepare(root);models={kind:{'oracle':raw_oracle,'property':raw_property,'relation':raw_relation}[kind]()}
        if previous:models['oracle']=raw_oracle()
    return register(uploads,draft,args,models,kind)


def fake_sdk(monkeypatch,kind,*,good=False,unknown=False):
    module=importlib.import_module(MODULES[kind]);captured={};calls=[];primitive=primitive_trace.harness;sequence=sequence_trace.harness
    def observe(signature,cases,package,token,protocol,version=1):
        captured[token]=dict(signature=deepcopy(signature),cases=deepcopy(cases),protocol=protocol,version=version)
        return primitive(signature,cases,package,token,protocol,version=version)
    def paths(contract,traces,package,token):
        captured[token]=dict(contract=deepcopy(contract),traces=deepcopy(traces));return sequence(contract,traces,package,token)
    monkeypatch.setattr(primitive_trace,'harness',observe);monkeypatch.setattr(sequence_trace,'harness',paths)
    async def run(project,argv,**kwargs):
        filename={'oracle':'boundary_test.cj','property':'property_observations_test.cj','relation':'relation_observations_test.cj','sequence':'sequence_observations_test.cj'}[kind]
        program=(project/'src'/filename).read_text();prefix,nonce=re.search(r'(NEXUS_(?:ORACLE|PROPERTY|RELATION|SEQUENCE)_V3)\|([0-9a-f]{16})',program).groups();cls=re.search(r'class (\w+)',program)[1];data=captured[nonce]
        lines=['EXPLICIT SDK LOG FIXTURE','TP: uploadedrepair, RESULT:',' TCS: '+cls+', RESULT:']
        if kind=='sequence':
            contract,traces=data['contract'],data['traces'];calls.append(deepcopy(traces));primitive_kind=contract['signature']['return_type']
            for i,trace in enumerate(traces):
                plan=sequences.reference_trace(contract,trace);before=deepcopy(trace['initial_state']);mode='COMPLETE';lines+=[' [ PASSED ] CASE: case'+str(i)+' (1 ns)',' STDOUT:']
                for j,step in enumerate(plan['steps']):
                    actual=deepcopy(step['expected_state']) if good else [9]
                    lines.append(' NEXUS_SEQUENCE_V3|'+nonce+'|case'+str(i)+'|step'+str(j)+'|'+primitive_kind+'|'+array_trace.encode(before,primitive_kind)+'|'+array_trace.encode(actual,primitive_kind));before=actual
                    if actual!=step['expected_state']:mode='MODEL_MISMATCH';break
                lines.append(' NEXUS_SEQUENCE_END_V3|'+nonce+'|case'+str(i)+'|'+str(j+1)+'|'+mode)
            count=len(traces)
        else:
            cases=data['cases'];s=data['signature'];calls.append(deepcopy(cases));primitive_kind=s['return_type']
            for i,args in enumerate(cases):
                actual=(deepcopy(args[0]) if good or args[0] else [0]) if primitive_kind=='Array<Int64>' else sum(args[0])+args[1] if good else (args[0][0] if args[0] else 0)+args[1] if kind=='relation' else sum(args[0][:-1])+args[1]
                lines+=[' [ PASSED ] CASE: case'+str(i)+' (1 ns)',' STDOUT:',' '+prefix+'|'+nonce+'|case'+str(i)+'|'+primitive_kind+'|'+array_trace.encode(actual,primitive_kind)]
            count=len(cases)
        lines+=['Summary: TOTAL: '+str(count)+' PASSED: '+str(count)+', SKIPPED: 0, ERROR: 0 FAILED: 0','cjpm test success','']
        kwargs['execution_argv'].extend([['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]);assert kwargs['test_output']=='all'
        return (None,chr(10).join(lines),'TimeoutError') if unknown else (0,chr(10).join(lines),None)
    monkeypatch.setattr(module,'run_command',run);return calls


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_array_services_use_actual_typed_v3_observations_and_do_not_reexecute(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);calls=fake_sdk(monkeypatch,kind);c=apply();manifest=source_manifest(ws.subject_path(c.id));report=asyncio.run(engine.run(c.id))
    assert report['state']=='FAIL' and report['public_test_state']=='PASS' and report['failures']
    assert engine.verify(c.id)==report and asyncio.run(engine.run(c.id))==report and source_manifest(ws.subject_path(c.id))==manifest
    assert 1<=len(calls)<=3 and report['batches']
    if kind=='oracle':assert report['failures'][0]['test_id'].startswith('NexusOracleV3') and report['failures'][0]['source']['log_ref']
    if kind=='sequence':assert type(report['failures'][0]['actual_return']) is list and report['failures'][0]['source']['log_ref']


def test_oracle4_empty_return_has_canonical_json_and_typed_actual(tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,'oracle',array_return=True);fake_sdk(monkeypatch,'oracle');c=apply();report=asyncio.run(engine.run(c.id));assert report['state']=='FAIL'
    failure=report['failures'][0];assert failure['expected']=='[]' and failure['actual']=='[0]' and failure['expected_value']==[] and failure['actual_return']==[0]
    assert failure['args']==[[]] and failure['source']['log_ref']


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
@pytest.mark.parametrize('dependency',[array_trace,string_trace,values])
def test_array_codec_dependencies_are_bound_even_for_scalar_return(kind,dependency,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);fake_sdk(monkeypatch,kind,good=True);c=apply();report=asyncio.run(engine.run(c.id));assert report['state']=='PASS'
    monkeypatch.setattr(dependency,'__file__',str(Path(dependency.__file__).with_name('oracle.py')))
    with pytest.raises(ValueError):engine.verify(c.id)


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_array_current_public_original_is_checked_before_independent_execution(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);calls=fake_sdk(monkeypatch,kind,good=True);c=apply();public=next(r for r in store.records(task.id,'check') if r['subject_id']==c.id and r['kind']=='test')
    (store.root/public['log_ref']).write_text('changed original public log')
    report=asyncio.run(engine.run(c.id));assert report['state']=='UNKNOWN' and not calls and not report['batches']


@pytest.mark.parametrize('kind',['property','relation'])
def test_array_required_oracle_must_pass_first(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind,previous=True);calls=fake_sdk(monkeypatch,kind,good=True);c=apply();report=asyncio.run(engine.run(c.id))
    assert report['state']=='UNKNOWN' and not calls and not report['batches']


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_array_prior_started_attempt_blocks_later_candidate(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);calls=fake_sdk(monkeypatch,kind,good=True);first=apply('first');table={'oracle':'exploration_runs','property':'property_runs','relation':'relation_runs','sequence':'sequence_runs'}[kind]
    with store.connect() as db:db.execute('INSERT INTO '+table+' VALUES (?,?,?,NULL,NULL)',(first.id,task.id,'STARTED'))
    second=apply('second');report=asyncio.run(engine.run(second.id));assert report['state']=='UNKNOWN' and not calls and not report['batches']
    assert engine.verify(second.id)==report


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_array_timeout_is_not_retried_and_blocks_next_candidate(kind,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);calls=fake_sdk(monkeypatch,kind,unknown=True);first=apply('first');report=asyncio.run(engine.run(first.id));assert report['state']=='UNKNOWN' and len(calls)==1
    assert engine.verify(first.id)==report and asyncio.run(engine.run(first.id))==report and len(calls)==1
    second=apply('second');assert asyncio.run(engine.run(second.id))['state']=='UNKNOWN' and len(calls)==1


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
def test_array_report_reconstruction_has_no_execution_or_network(kind,tmp_path,monkeypatch):
    import socket
    from nexus.policy import core
    store,ws,task,apply,engine=setup(tmp_path,kind);fake_sdk(monkeypatch,kind,good=True);c=apply();report=asyncio.run(engine.run(c.id));assert report['state']=='PASS'
    def deny(*args,**kwargs):raise AssertionError('replay triggered external effect')
    monkeypatch.setattr(importlib.import_module(MODULES[kind]),'run_command',deny);monkeypatch.setattr(core.NativeCoreClient,'call',deny);monkeypatch.setattr(socket,'create_connection',deny)
    assert engine.verify(c.id)==report


def test_array_failure_prefix_snapshot_cannot_mutate_original_report():
    from nexus.repair.sequence_service import failure_trace
    raw,s=sequence_raw();c=sequences.validate_contract(raw,s,[])
    original=dict(initial_state=[],context=['a'],steps=[dict(operation_id='OP-SWAP',args=[0,[],'a'])])
    copied=failure_trace(c,original);copied['initial_state'].append(99)
    assert original['initial_state']==[]


@pytest.mark.parametrize('kind',['oracle','property'])
def test_array_search_preserves_caller_history_as_independent_values(kind):
    from nexus.repair.exploration import ExplorationService
    from nexus.repair.property_service import PropertyService
    from nexus.repair import properties
    contract=oracle.validate_contract(raw_oracle(),raw_signature(),[]) if kind=='oracle' else properties.validate_contract(raw_property(),raw_signature(),[])
    original=[[[1,2],1]];axes=oracle.checked_axes(contract)
    rows,_=(ExplorationService.string_search if kind=='oracle' else PropertyService.search_inputs)(contract,axes,original)
    rows[0][0].append(99);assert original==[[[1,2],1]]


def raw_signature():
    from tests.test_array_contracts import signature
    return signature()
