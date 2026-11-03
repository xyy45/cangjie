"""Sequence service integrity tests with explicit SDK log fixtures, real native axes.

Real compilation is exercised separately under tests/sdk/test_sequences_sdk.py.
"""
import asyncio
from copy import deepcopy
import importlib
import importlib.util
import json

import pytest

from nexus.contracts import CandidateProposal,digest,file_hash,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from tests.test_sequence_uploads import prepared,sequence
from tests.test_relation_service import record_public


def setup(tmp_path,*,relation=False,maximum=8,single=False,numeric=False):
    uploads,draft,args=prepared(tmp_path);model=sequence();model['max_sequences']=maximum
    extra={}
    if relation:
        extra['relations_json']=json.dumps(dict(version=1,kind='relation',function='refund',domains=deepcopy(model['domains']),relations=[
            dict(id='REL-NONNEGATIVE',text='返回非负',precondition='True',assertion='left_result >= 0 and right_result >= 0')],seed=0,max_pairs=16,excluded_inputs=[]))
    if single:extra['properties_json']=json.dumps(dict(version=1,kind='single',function='refund',domains=deepcopy(model['domains']),properties=[dict(id='PROP-BOUND',text='非负',precondition='True',assertion='result >= 0')],seed=0,max_cases=16,excluded_inputs=[]))
    if numeric:extra['oracle_json']=json.dumps(dict(version=1,function='refund',domains=deepcopy(model['domains']),expression='min(paid, state + amount)',seed=0,max_cases=32))
    uploads.confirm(draft['id'],**args,sequences_json=json.dumps(model),**extra)
    root=uploads.source(draft['id'],actor_id='alice');store=uploads.store;ws=WorkspaceStore(tmp_path,registered=[root]);baseline=ws.import_project(root,'.')
    req=RequirementService(store);draft_req=req.prepare_requirement(draft['id'],draft['goal'])
    spec=req.confirm_requirement(draft_req['id'],dict(schema_version=1,expected_version=1,requirements=draft_req['requirements'],allowed_paths=draft_req['allowed_paths']),actor_id='alice')
    task=req.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/uploaded.cj')
    def candidate(*,good=False,public='PASS',suffix=''):
        body=original.replace('return state + amount','if (amount > paid - state) { return paid }\n return state + amount') if good else original
        proposal=CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=body+'\n// candidate '+suffix+'\n')],requirement_refs=['REQ-UPLOAD'])
        c=ws.apply_candidate(store.get_task(task.id),proposal)
        if public is not None:record_public(store,ws,task,c,public)
        return c
    return store,ws,task,candidate


def api(store):
    assert importlib.util.find_spec('nexus.repair.sequence_service') is not None,'state sequence execution service missing'
    return importlib.import_module('nexus.repair.sequence_service').SequenceService(store)


def sdk(monkeypatch,*,good=False,problem=None,cancel=False,delay=None):
    from nexus.repair import sequence_trace,sequences
    module=importlib.import_module('nexus.repair.sequence_service');calls=[];plans={};original=sequence_trace.harness
    def capture(contract,traces,package,token):
        plans[token]=(contract,traces);return original(contract,traces,package,token)
    monkeypatch.setattr(sequence_trace,'harness',capture)
    async def run(project,argv,**kwargs):
        calls.append(project)
        if delay is not None:await delay()
        if cancel:raise asyncio.CancelledError
        text=(project/'src/sequence_observations_test.cj').read_text()
        token=next(t for t in reversed(plans) if 'NexusSequences'+t in text);contract,traces=plans[token];rows=[]
        for i,trace in enumerate(traces):
            plan=sequences.reference_trace(contract,trace);before=trace['initial_state'];lines=[];mode='COMPLETE'
            for j,step in enumerate(plan['steps']):
                amount,paid=step['args'][1:];actual=min(paid,before+amount) if good else before+amount
                lines.append(f' NEXUS_SEQUENCE_V1|{token}|case{i}|step{j}|Int64|{before}|{actual}\n');before=actual
                if actual!=step['expected_state']:mode='MODEL_MISMATCH';break
            lines.append(f' NEXUS_SEQUENCE_END_V1|{token}|case{i}|{len(lines)}|{mode}\n')
            rows.append(f' [ PASSED ] CASE: case{i} (1 ns)\n STDOUT:\n'+''.join(lines))
        log='EXPLICIT SDK LOG FIXTURE\nTP: uploaded, RESULT:\n TCS: NexusSequences'+token+', RESULT:\n'+''.join(rows)+f'Summary: TOTAL: {len(rows)} PASSED: {len(rows)}, SKIPPED: 0, ERROR: 0 FAILED: 0\ncjpm test success\n'
        kwargs['execution_argv'].extend([['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']])
        return (None,log,problem) if problem else (0,log,None)
    monkeypatch.setattr(module,'run_command',run)
    return calls


def rewrite(engine,report):
    ref,hash_=engine.write_record(report,'.sequences.json')
    with engine.store.connect() as db:db.execute('UPDATE sequence_runs SET report_ref=?,report_sha256=? WHERE candidate_id=?',(ref,hash_,report['candidate_id']))


def test_changed_public_original_blocks_before_sdk(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch);c=apply()
    public=store.records(task.id,'check')[-1];(store.root/public['log_ref']).write_text('changed public original')
    report=asyncio.run(engine.run(c.id))
    assert report['state']=='UNKNOWN' and report['batches']==[] and calls==[]
    assert engine.verify(c.id)==report


def test_changed_relation_predecessor_invalidates_sequence(tmp_path,monkeypatch):
    from nexus.repair.relation_service import RelationService
    from tests.test_relation_service import sdk as relation_sdk
    store,ws,task,apply=setup(tmp_path,relation=True);engine=api(store);c=apply(good=True)
    # Refund-safe generic pair fixture: each observed primitive is nonnegative.
    module=importlib.import_module('nexus.repair.relation_service')
    original_trace=module.relation_trace.harness;plans={}
    def harness(contract,pairs,package,token):plans[token]=(contract,pairs);return original_trace(contract,pairs,package,token)
    monkeypatch.setattr(module.relation_trace,'harness',harness)
    async def run(project,argv,**kwargs):
        token=next(reversed(plans));contract,pairs=plans[token];cls='NexusRelations'+token;rows=[]
        for i,pair in enumerate(pairs):
            for side in ('left','right'):
                state,amount,paid=pair[side];actual=min(paid,state+amount);case='case'+str(i*2+(side=='right'))
                rows.append(f' [ PASSED ] CASE: {case} (1 ns)\n STDOUT:\n NEXUS_RELATION_V1|{token}|{case}|Int64|{actual}\n')
        kwargs['execution_argv'].extend([['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']])
        return 0,'EXPLICIT RELATION LOG FIXTURE\nTP: uploaded, RESULT:\n TCS: '+cls+', RESULT:\n'+''.join(rows)+f'Summary: TOTAL: {len(rows)} PASSED: {len(rows)}, SKIPPED: 0, ERROR: 0 FAILED: 0\ncjpm test success\n',None
    monkeypatch.setattr(module,'run_command',run)
    prior=asyncio.run(RelationService(store).run(c.id));assert prior['state']=='PASS'
    sdk(monkeypatch,good=True);report=asyncio.run(engine.run(c.id));assert report['state']=='PASS'
    assert report['binding']['required_checks']['relations']==dict(state='PASS',report_hash=digest(prior))
    (store.root/prior['batches'][0]['log_ref']).write_text('changed relation evidence')
    with pytest.raises(ValueError):engine.verify(c.id)


def test_failure_retains_real_prefix_and_replays_without_execution(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch);c=apply();before=source_manifest(ws.subject_path(c.id))
    report=asyncio.run(engine.run(c.id));assert report['state']=='FAIL' and report['public_test_state']=='PASS'
    assert 1<=len(calls)<=3 and report['search_traces']<=16 and report['shrink_traces']<=16
    assert report['search_planned_calls']<=128 and report['shrink_planned_calls']<=128 and report['candidate_checks']<=8192
    assert report['observed_calls']==sum(b['result']['observed_calls'] for b in report['batches'])
    failure=report['failures'][0];assert failure['kind']=='business_sequence' and len(failure['steps'])>=2
    assert failure['actual_return']>failure['expected_state'] and 'MODEL-OP-REFUND' in failure['failure_ids']
    assert len({s['test_id'] for s in failure['steps']})==1
    assert all(s['source']['log_ref']==failure['source']['log_ref'] for s in failure['steps'])
    assert [s['before_state'] for s in failure['steps'][1:]]==[s['actual_return'] for s in failure['steps'][:-1]]
    count=len(calls);assert engine.verify(c.id)==report and asyncio.run(engine.run(c.id))==report and len(calls)==count
    assert source_manifest(ws.subject_path(c.id))==before


def test_later_candidate_reexecutes_all_earlier_retained_prefixes(tmp_path,monkeypatch):
    from nexus.repair.sequence_service import failure_trace
    from nexus.repair.sequences import trace_key
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch);first=apply();failed=asyncio.run(engine.run(first.id))
    sdk(monkeypatch,good=True);second=apply(good=True);passed=asyncio.run(engine.run(second.id))
    assert passed['state']=='PASS' and passed['regression_traces']>0
    contract=engine.binding(second.id)[3]
    assert {trace_key(failure_trace(contract,f)) for f in failed['failures']}<={trace_key(t) for t in passed['batches'][0]['traces']}
    assert engine.verify(first.id)==failed and engine.verify(second.id)==passed


@pytest.mark.parametrize('public',[None,'FAIL','UNKNOWN'])
def test_missing_public_pass_blocks_all_execution(tmp_path,monkeypatch,public):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch);c=apply(public=public)
    report=asyncio.run(engine.run(c.id));assert report['state']=='UNKNOWN' and not report['batches'] and not calls
    assert engine.verify(c.id)==report


def test_missing_configured_relation_blocks_execution(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path,relation=True);engine=api(store);calls=sdk(monkeypatch,good=True);c=apply(good=True)
    report=asyncio.run(engine.run(c.id));assert report['state']=='UNKNOWN' and not calls and not report['batches']


@pytest.mark.parametrize('change',['log','harness','source','candidate-tree','traces','initial','context','end','expected-state','argv','batch-result','binding','failures','native','engine'])
def test_modified_evidence_cannot_replay(tmp_path,monkeypatch,change):
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch,good=True);c=apply(good=True);report=asyncio.run(engine.run(c.id));batch=report['batches'][0]
    if change in ('log','harness'):(store.root/batch[change+'_ref']).write_text('forged')
    elif change=='source':(store.root/batch['project_path']/'src/uploaded.cj').write_text('forged')
    elif change=='candidate-tree':(ws.subject_path(c.id)/'src/uploaded.cj').write_text('forged')
    elif change=='engine':
        original=engine.binding
        def binding(identity):
            value=list(original(identity));value[-1]=dict(value[-1],engine_hash='changed');return tuple(value)
        monkeypatch.setattr(engine,'binding',binding)
    else:
        if change=='traces':batch['traces'].reverse()
        elif change=='initial':batch['traces'][0]['initial_state']=1
        elif change=='context':batch['traces'][0]['context']=[9]
        elif change=='end':batch['result']['observations'][0]['stop_reason']='MODEL_MISMATCH'
        elif change=='expected-state':batch['result']['observations'][0]['steps'][0]['expected_state']=999
        elif change=='argv':batch['execution_argv']=[]
        elif change=='batch-result':batch['result']['state']='FAIL'
        elif change=='binding':report['binding']['tree_hash']='changed'
        elif change=='failures':report['failures']=[dict(kind='forged')]
        else:report['native_boundary']['response']['data']['axes'][0].append(999)
        rewrite(engine,report)
    with pytest.raises(ValueError):engine.verify(c.id)


@pytest.mark.parametrize('problem',['TimeoutError','OUTPUT_LIMIT'])
def test_unknown_execution_does_not_retry(tmp_path,monkeypatch,problem):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch,problem=problem);c=apply()
    report=asyncio.run(engine.run(c.id));assert report['state']=='UNKNOWN' and len(calls)==1
    assert report['observed_calls']==0 and report['failures']==[]
    assert asyncio.run(engine.run(c.id))==report and len(calls)==1


def test_cancellation_records_unknown_and_never_replays(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch,cancel=True);c=apply()
    with pytest.raises(asyncio.CancelledError):asyncio.run(engine.run(c.id))
    report=engine.verify(c.id);assert report['state']=='UNKNOWN' and len(calls)==1
    assert asyncio.run(engine.run(c.id))==report and len(calls)==1


def test_cas_owns_execution_once_and_started_has_no_retry(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);c=apply(good=True)
    async def check():
        entered=asyncio.Event();release=asyncio.Event()
        async def delay():entered.set();await release.wait()
        calls=sdk(monkeypatch,good=True,delay=delay);first=asyncio.create_task(engine.run(c.id));await entered.wait()
        second=await engine.run(c.id);assert second['state']=='UNKNOWN' and len(calls)==1
        release.set();assert (await first)['state']=='PASS' and len(calls)==1
    asyncio.run(check())


def test_expired_execution_budget_does_not_call_sdk(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch);c=apply()
    report=asyncio.run(engine.run(c.id,deadline_at=0));assert report['state']=='UNKNOWN' and not calls


@pytest.mark.parametrize('field',['seed','algorithm','public_test_state','schema_version'])
def test_report_metadata_must_be_reconstructed_not_just_hashed(tmp_path,monkeypatch,field):
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch,good=True);c=apply(good=True)
    report=asyncio.run(engine.run(c.id));report[field]='forged';rewrite(engine,report)
    with pytest.raises(ValueError):engine.verify(c.id)


@pytest.mark.parametrize('which',['numeric','single'])
def test_each_configured_primitive_prerequisite_must_exist(tmp_path,monkeypatch,which):
    store,ws,task,apply=setup(tmp_path,**{which:True});engine=api(store);calls=sdk(monkeypatch);c=apply()
    report=asyncio.run(engine.run(c.id));assert report['state']=='UNKNOWN' and not calls and not report['batches']
    assert engine.verify(c.id)==report


def test_verify_never_calls_sdk_native_ipc_or_network(tmp_path,monkeypatch):
    from nexus.policy import core
    import socket
    module=importlib.import_module('nexus.repair.sequence_service')
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch,good=True);c=apply(good=True);report=asyncio.run(engine.run(c.id))
    def forbidden(*args,**kwargs):raise AssertionError('read-only verification executed an external effect')
    monkeypatch.setattr(module,'run_command',forbidden);monkeypatch.setattr(core.NativeCoreClient,'call',forbidden);monkeypatch.setattr(socket,'create_connection',forbidden)
    assert engine.verify(c.id)==report


def test_shared_helper_source_identity_invalidates_sequence(tmp_path,monkeypatch):
    from nexus.repair import verification_evidence
    from pathlib import Path
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch,good=True);c=apply(good=True);asyncio.run(engine.run(c.id))
    # Keep the path within the package so this tests hash identity, not path rejection.
    monkeypatch.setattr(verification_evidence,'__file__',str(Path(verification_evidence.__file__).with_name('sequence_trace.py')))
    with pytest.raises(ValueError):engine.verify(c.id)


def test_full_history_union_over_eight_is_not_recapped_and_over_budget_is_unknown(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from nexus.repair import sequences
    store,ws,task,apply=setup(tmp_path,maximum=16);engine=api(store);c=apply();contract=engine.binding(c.id)[3]
    prior={};failures=[]
    for index,amount in enumerate(range(1,10)):
        trace=dict(initial_state=0,context=[10],steps=[dict(operation_id='OP-REFUND',args=[amount,10])]*2)
        plan=sequences.reference_trace(contract,trace)
        failures.append(dict(initial_state=0,context=[10],steps=plan['steps']))
    # Deliberate report verification fixture isolates history-union plumbing;
    # real prefix provenance and SDK reexecution are tested separately.
    for n in (1,2):
        cid='historical'+str(n);prior[cid]=dict(state='FAIL',binding={'sequences_hash':digest(contract)},failures=failures[:5] if n==1 else failures[5:])
        with store.connect() as db:db.execute('INSERT INTO sequence_runs VALUES (?,?,?,?,?)',(cid,task.id,'FAIL','records/prior'+str(n),'hash'+str(n)))
    original=engine.ws.candidate
    monkeypatch.setattr(engine.ws,'candidate',lambda cid:SimpleNamespace(attempt=int(cid[-1])) if cid in prior else original(cid))
    monkeypatch.setattr(engine,'verify',lambda cid:prior[cid]);current=SimpleNamespace(task_id=task.id,attempt=3)
    refs,traces=engine.cumulative(current,{'sequences_hash':digest(contract)},contract)
    assert len(refs)==2 and len(traces)==9
    generated=sequences.generate_traces(contract,cumulative=traces);assert generated['regression_traces']==9
    assert {sequences.trace_key(t) for t in traces}<={sequences.trace_key(t) for t in generated['traces']}
    reduced=deepcopy(contract);reduced['max_sequences']=8
    with pytest.raises(ValueError,match='预算'):sequences.generate_traces(reduced,cumulative=traces)


def test_prior_started_or_unknown_prevents_a_new_execution(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);first=apply();second=apply(suffix='next');calls=sdk(monkeypatch,good=True)
    with store.connect() as db:db.execute('INSERT INTO sequence_runs VALUES (?,?,?,NULL,NULL)',(first.id,task.id,'STARTED'))
    report=asyncio.run(engine.run(second.id));assert report['state']=='UNKNOWN' and calls==[]
    assert engine.verify(second.id)==report


def test_output_limit_is_enforced_and_timeout_clamped(tmp_path,monkeypatch):
    module=importlib.import_module('nexus.repair.sequence_service');store,ws,task,apply=setup(tmp_path);engine=api(store);c=apply();calls=[]
    async def oversized(project,argv,**kwargs):
        calls.append(kwargs['timeout']);return 0,'x'*(2*1024*1024+1),None
    monkeypatch.setattr(module,'run_command',oversized)
    report=asyncio.run(engine.run(c.id,deadline_at=10**20));assert report['state']=='UNKNOWN' and len(calls)==1 and 0<calls[0]<=60
    batch=report['batches'][0];assert batch['problem']=='OUTPUT_LIMIT' and engine.read_record(batch['log_ref'],batch['log_sha256'])==b''


def test_conclusion_groups_multiple_ids_and_explicitly_retains_only_eight(tmp_path):
    from nexus.repair.sequence_service import SequenceService
    from nexus.repair import sequences
    from tests.test_sequence_trace import log
    from nexus.repair.sequence_trace import interpret
    from tests.test_primitive_trace import TOKEN
    from tests.test_sequences import refund_raw
    raw,signature=refund_raw();contract=sequences.validate_contract(raw,signature,[]);traces=[];cases=[]
    for a in range(1,11):
        depth=10//a+1
        if depth>4:continue
        for b in (0,1):
            args=[a,10];trace=dict(initial_state=0,context=[10],steps=[dict(operation_id='OP-REFUND',args=list(args)) for _ in range(depth)])
            if b:trace['steps'][0]['args']=[a-1,10]
            plan=sequences.reference_trace(contract,trace);before=0;observed=[]
            for step in plan['steps']:
                actual=before+step['args'][1];observed.append((before,actual));before=actual
                if actual!=step['expected_state']:break
            if actual!=step['expected_state']:traces.append(trace);cases.append(observed)
            if len(traces)==16:break
        if len(traces)==16:break
    result=interpret(contract,traces,TOKEN,log(cases,[(len(c),'MODEL_MISMATCH') for c in cases]),0,None)
    report=SequenceService.conclusion([dict(traces=traces,result=result)],contract)
    assert report['state']=='FAIL' and len(report['failures'])==8 and report['distinct_failure_count']>8 and report['failures_truncated'] is True
    assert all(set(f['failure_ids'])=={'MODEL-OP-REFUND','INV-BOUND'} for f in report['failures'])
