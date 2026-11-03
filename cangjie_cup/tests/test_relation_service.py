"""Relation CAS/binding/replay over explicit SDK log fixtures; native core is real.

Real compilation/execution is checked separately by tests/sdk/test_relations_sdk.py.
"""
import asyncio
import importlib
import importlib.util
import json
from pathlib import Path
import re

import pytest

from nexus.contracts import CandidateProposal,CheckResult,digest,file_hash,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.store import uid
from tests.test_relation_uploads import prepared
from tests.test_relations import raw


def record_public(store,ws,task,c,state='PASS'):
    """Pinned-format public evidence fixture, not an SDK execution claim."""
    from nexus.adapters.cangjie import report_parser
    from nexus.adapters.cangjie.verifier import CangjieVerifier
    _,tree,check_plan=CangjieVerifier(store.root,task.id).identity(c.id)
    _,plan=RequirementService(store).task_context(task)
    if state=='UNKNOWN':log='EXPLICIT INCOMPLETE PUBLIC LOG FIXTURE\n'
    else:
        first='FAILED' if state=='FAIL' else 'PASSED';passed=1 if state=='FAIL' else 2;failed=1 if state=='FAIL' else 0
        log=f'EXPLICIT PUBLIC LOG FIXTURE\nTP: uploaded, RESULT:\n TCS: UploadedTests, RESULT:\n [ {first} ] CASE: case0 (1 ns)\n [ PASSED ] CASE: case1 (1 ns)\nSummary: TOTAL: 2 PASSED: {passed}, SKIPPED: 0, ERROR: 0 FAILED: {failed}\n'+('Error: cjpm test failed' if failed else 'cjpm test success')+'\n'
    parsed=report_parser.parse_test_report(log);identity=uid();ref='records/'+identity+'.public.log';report_ref='records/'+identity+'.public.report.json'
    result=CheckResult(schema_version=2,id=identity,subject_id=c.id,kind='test',state=state,tree_hash=tree,plan_hash=check_plan,
        spec_hash=task.spec_hash,verification_plan_hash=task.verification_plan_hash,exit_code=0 if state=='PASS' else 1 if state=='FAIL' else None,
        counts=parsed.counts,case_results=parsed.case_results,suite_results=report_parser.project_suites(parsed,plan.suite_tests),
        log_ref=ref,report_ref=report_ref,diagnostics=log[-16000:],argv=['cjpm','test'],working_root='.',toolchain_hash=plan.toolchain_id)
    (store.root/ref).write_text(log);(store.root/report_ref).write_text(result.model_dump_json());store.append_record(task.id,'check',result.model_dump())
    return result


def setup(tmp_path,*,single=None,with_oracle=False,reserved=None):
    uploads,draft,args=prepared(tmp_path);relation=raw()
    if reserved is not None:relation['excluded_inputs']=reserved
    extra={}
    if single is not None:
        extra['properties_json']=json.dumps(dict(version=1,kind='single',function='amount',domains=relation['domains'],properties=[
            dict(id='PROP-POSITIVE',text='金额约束',precondition='True',assertion=single)],seed=0,max_cases=16,excluded_inputs=relation['excluded_inputs']))
    if with_oracle:
        extra['oracle_json']=json.dumps(dict(version=1,function='amount',domains=dict(quantity=dict(min=1,max=2),price=dict(min=100,max=100),promotion={}),
            expression='quantity * price',seed=0,max_cases=16))
    uploads.confirm(draft['id'],**args,relations_json=json.dumps(relation),**extra)
    root=uploads.source(draft['id'],actor_id='alice');store=uploads.store;ws=WorkspaceStore(tmp_path,registered=[root]);baseline=ws.import_project(root,'.')
    requirements=RequirementService(store);d=requirements.prepare_requirement(draft['id'],draft['goal'])
    spec=requirements.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='alice')
    task=requirements.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    original=ws.read_file(baseline,'src/uploaded.cj')
    def candidate(*,good=False,public='PASS',suffix=''):
        from nexus.adapters.cangjie.verifier import CangjieVerifier
        body=original if good else original.replace('return quantity * price','if (quantity >= 10) { return 0 }\n return quantity * price')
        proposal=CandidateProposal(edits=[dict(path='src/uploaded.cj',before_hash=file_hash(original),content=body+'\n// candidate'+suffix+'\n')],requirement_refs=['REQ-UPLOAD'])
        c=ws.apply_candidate(store.get_task(task.id),proposal);_,tree,plan=CangjieVerifier(tmp_path,task.id).identity(c.id)
        if public is not None:record_public(store,ws,task,c,public)
        return c
    return store,ws,task,candidate


def api(store):
    assert importlib.util.find_spec('nexus.repair.relation_service') is not None,'paired relation search service missing'
    return importlib.import_module('nexus.repair.relation_service').RelationService(store)


def sdk(monkeypatch,*,good=False,unknown=False,cancel=False):
    module=importlib.import_module('nexus.repair.relation_service');calls=[]
    async def run(project,argv,**kwargs):
        calls.append(project)
        if cancel:raise asyncio.CancelledError
        if (project/'src/boundary_test.cj').exists():
            # Earlier numeric oracle has quantity1..2 and price100: both
            # candidate branches agree with its hand-confirmed q*price rule.
            text=(project/'src/boundary_test.cj').read_text();count=text.count('@TestCase');cls='BoundaryTests'
            rows=[f' [ PASSED ] CASE: case{i} (1 ns)\n' for i in range(count)]
        else:
            name='relation' if (project/'src/relation_observations_test.cj').exists() else 'property'
            text=(project/('src/'+name+'_observations_test.cj')).read_text()
            prefix,classname=('NEXUS_RELATION_V1','NexusRelations') if name=='relation' else ('NEXUS_PROPERTY_V1','NexusProperties')
            token=re.search('class '+classname+r'([0-9a-f]{16})',text)[1];cls=classname+token
            values=re.findall(r'__nexusTarget'+token+r'\(([-0-9, falsetru]+)\)',text)
            rows=[]
            for i,args in enumerate(values):
                q,p,flag=args.split(', ');q=int(q);p=int(p)
                actual=q*p if good or q<10 else 0
                rows.append(f' [ PASSED ] CASE: case{i} (1 ns)\n STDOUT:\n {prefix}|{token}|case{i}|Int64|{actual}\n')
            count=len(rows)
        log='EXPLICIT SDK LOG FIXTURE\nTP: uploaded, RESULT:\n TCS: '+cls+', RESULT:\n'+''.join(rows)
        log+=f'Summary: TOTAL: {count} PASSED: {count}, SKIPPED: 0, ERROR: 0 FAILED: 0\ncjpm test success\n'
        kwargs['execution_argv'].extend([['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']] if kwargs.get('test_output')=='all' else [['cjpm','test']])
        return (None,log,'TimeoutError') if unknown else (0,log,None)
    monkeypatch.setattr(module,'run_command',run)
    from nexus.repair import property_service,exploration
    monkeypatch.setattr(property_service,'run_command',run);monkeypatch.setattr(exploration,'run_command',run)
    return calls


def test_relation_failure_binds_both_real_case_coordinates_and_replays_without_execution(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch);c=apply();before=source_manifest(ws.subject_path(c.id))
    report=asyncio.run(engine.run(c.id))
    assert report['state']=='FAIL' and report['public_test_state']=='PASS'
    assert 1<=len(calls)<=3 and report['search_pairs']<=32 and report['shrink_pairs']<=32
    assert report['search_calls']==report['search_pairs']*2 and report['shrink_calls']==report['shrink_pairs']*2
    assert report['candidate_checks']<=8192
    failure=report['failures'][0]
    assert failure['kind']=='business_relation' and failure['left_actual_return']>failure['right_actual_return']
    assert failure['left_test_id']!=failure['right_test_id'] and 'expected' not in failure
    assert failure['left_source']['log_ref']==failure['right_source']['log_ref']
    count=len(calls);assert engine.verify(c.id)==report and asyncio.run(engine.run(c.id))==report and len(calls)==count
    assert source_manifest(ws.subject_path(c.id))==before


def test_later_candidate_regresses_only_verified_earlier_retained_pairs(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch);first=apply()
    failed=asyncio.run(engine.run(first.id));sdk(monkeypatch,good=True);second=apply(good=True)
    passed=asyncio.run(engine.run(second.id))
    assert passed['state']=='PASS' and passed['regression_pairs']>0
    actual={(tuple(p['left']),tuple(p['right'])) for p in passed['batches'][0]['pairs']}
    assert {(tuple(f['left_args']),tuple(f['right_args'])) for f in failed['failures']}<=actual
    assert engine.verify(first.id)==failed and engine.verify(second.id)==passed


@pytest.mark.parametrize('public',[None,'FAIL','UNKNOWN'])
def test_no_public_pass_means_no_relation_execution(tmp_path,monkeypatch,public):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch);c=apply(public=public)
    report=asyncio.run(engine.run(c.id))
    assert report['state']=='UNKNOWN' and calls==[] and report['batches']==[]
    assert engine.verify(c.id)==report


@pytest.mark.parametrize('earlier',['oracle-missing','single-missing','single-fail','single-unknown'])
def test_required_earlier_check_must_have_verified_pass_before_relation(tmp_path,monkeypatch,earlier):
    store,ws,task,apply=setup(tmp_path,single='result > 0' if earlier=='single-fail' else 'result >= 0' if earlier.startswith('single') else None,with_oracle=earlier.startswith('oracle'))
    engine=api(store);calls=sdk(monkeypatch,unknown=earlier=='single-unknown');c=apply()
    if earlier in ('single-fail','single-unknown'):
        from nexus.repair.property_service import PropertyService
        assert asyncio.run(PropertyService(store).run(c.id))['state']==('FAIL' if earlier=='single-fail' else 'UNKNOWN')
    calls.clear();report=asyncio.run(engine.run(c.id))
    assert report['state']=='UNKNOWN' and report['batches']==[] and calls==[]
    assert engine.verify(c.id)==report


def test_verified_prior_hashes_are_bound_and_later_tamper_invalidates_relation(tmp_path,monkeypatch):
    from nexus.repair.property_service import PropertyService
    from nexus.repair.exploration import ExplorationService
    store,ws,task,apply=setup(tmp_path,single='result >= 0',with_oracle=True);engine=api(store);sdk(monkeypatch,good=True);c=apply(good=True)
    numeric=asyncio.run(ExplorationService(store).run(c.id));single=asyncio.run(PropertyService(store).run(c.id))
    report=asyncio.run(engine.run(c.id))
    assert report['state']=='PASS'
    assert report['binding']['required_checks']['oracle']==dict(state='PASS',report_hash=digest(numeric))
    assert report['binding']['required_checks']['properties']==dict(state='PASS',report_hash=digest(single))
    batch=single['batches'][0];(store.root/batch['log_ref']).write_text('changed earlier evidence')
    with pytest.raises(ValueError):engine.verify(c.id)


@pytest.mark.parametrize('change',['log','harness','source','candidate-tree','pairs','scope','argv','batch-result','binding','failures','native','engine'])
def test_changed_evidence_or_shared_observer_cannot_replay_as_valid(tmp_path,monkeypatch,change):
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch,good=True);c=apply(good=True)
    report=asyncio.run(engine.run(c.id));batch=report['batches'][0]
    if change in ('log','harness'):(store.root/batch[change+'_ref']).write_text('forged')
    elif change=='source':(store.root/batch['project_path']/'src/uploaded.cj').write_text('forged')
    elif change=='candidate-tree':(ws.subject_path(c.id)/'src/uploaded.cj').write_text('forged')
    elif change=='engine':
        from nexus.repair import primitive_trace
        changed=tmp_path/'changed-source'/Path(primitive_trace.__file__).name;changed.parent.mkdir();changed.write_bytes(Path(primitive_trace.__file__).read_bytes()+b'\n# source identity fixture\n')
        monkeypatch.setattr(primitive_trace,'__file__',str(changed))
    else:
        if change=='pairs':batch['pairs'][0]['left'][0]+=1
        elif change=='scope':batch['required_ids']=[]
        elif change=='argv':batch['execution_argv']=[['cjpm','test']]
        elif change=='batch-result':batch['result']['state']='FAIL'
        elif change=='binding':report['binding']['tree_hash']='0'*64
        elif change=='failures':report['failures']=[dict(left_args=[1,100,False],right_args=[2,100,False])]
        else:report['native_boundary']['response']['data']['axes'][0]=[]
        ref,hash_=engine.write_record(report,'.relations.json')
        with store.connect() as db:db.execute('UPDATE relation_runs SET report_ref=?,report_sha256=? WHERE candidate_id=?',(ref,hash_,c.id))
    with pytest.raises(ValueError):engine.verify(c.id)


def test_unknown_cancellation_and_started_claim_never_reexecute(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch,unknown=True);first=apply()
    report=asyncio.run(engine.run(first.id));assert report['state']=='UNKNOWN' and len(calls)==1
    assert asyncio.run(engine.run(first.id))==report and len(calls)==1
    second=apply(suffix='second');calls=sdk(monkeypatch,good=True)
    assert asyncio.run(engine.run(second.id))['state']=='UNKNOWN' and calls==[]
    store,ws,task,apply=setup(tmp_path/'cancel');engine=api(store);calls=sdk(monkeypatch,cancel=True);c=apply()
    with pytest.raises(asyncio.CancelledError):asyncio.run(engine.run(c.id))
    assert engine.verify(c.id)['state']=='UNKNOWN' and asyncio.run(engine.run(c.id))['state']=='UNKNOWN' and len(calls)==1
    store,ws,task,apply=setup(tmp_path/'started');engine=api(store);calls=sdk(monkeypatch);c=apply()
    with store.connect() as db:db.execute('INSERT INTO relation_runs VALUES (?,?,?,NULL,NULL)',(c.id,task.id,'STARTED'))
    with pytest.raises(ValueError):engine.verify(c.id)
    assert asyncio.run(engine.run(c.id))['state']=='UNKNOWN' and calls==[]


def test_reserved_input_is_absent_on_both_sides_and_shrink_batches(tmp_path,monkeypatch):
    reserved=[[9,100,False],[8,1,False]];store,ws,task,apply=setup(tmp_path,reserved=reserved);engine=api(store);sdk(monkeypatch);c=apply()
    report=asyncio.run(engine.run(c.id));assert report['state']=='FAIL'
    for batch in report['batches']:
        for pair in batch['pairs']:assert pair['left'] not in reserved and pair['right'] not in reserved
    assert engine.verify(c.id)==report


def test_concurrent_requests_claim_only_one_search(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch,good=True);c=apply(good=True)
    module=importlib.import_module('nexus.repair.relation_service');original=module.run_command
    async def exercise():
        started=asyncio.Event();release=asyncio.Event()
        async def paused(*args,**kwargs):started.set();await release.wait();return await original(*args,**kwargs)
        monkeypatch.setattr(module,'run_command',paused)
        first=asyncio.create_task(engine.run(c.id));await started.wait()
        second=await engine.run(c.id);assert second['state']=='UNKNOWN'
        release.set();return await first
    assert asyncio.run(exercise())['state']=='PASS' and len(calls)==1


def test_retained_failure_combinations_have_explicit_counts_and_truncation(tmp_path):
    from nexus.repair import relation_trace
    from tests.test_primitive_trace import log,TOKEN
    engine=api(setup(tmp_path)[0]);contract=importlib.import_module('nexus.repair.relations').validate_contract(raw(),importlib.import_module('tests.test_relations').SIG,[])
    pairs=[dict(left=[1,p,False],right=[10,p,False]) for p in range(1,21)]
    result=relation_trace.interpret(contract,pairs,TOKEN,log('relation',tuple(v for p in range(1,21) for v in (str(p),'0'))),0,None)
    reduced=relation_trace.interpret(contract,pairs[:16],TOKEN,log('relation',tuple(v for p in range(1,17) for v in (str(p),'0'))),0,None)
    summary=engine.conclusion([dict(pairs=pairs,result=result),dict(pairs=pairs[:16],result=reduced)])
    assert summary['failure_count']==36 and summary['distinct_failure_count']==20
    assert len(summary['failures'])==16 and summary['failures_truncated'] is True


def test_expired_deadline_and_oversized_output_are_unknown_without_retries(tmp_path,monkeypatch):
    store,ws,task,apply=setup(tmp_path/'expired');engine=api(store);calls=sdk(monkeypatch);c=apply()
    report=asyncio.run(engine.run(c.id,deadline_at=0))
    assert report['state']=='UNKNOWN' and report['batches']==[] and calls==[]
    assert engine.verify(c.id)==report and asyncio.run(engine.run(c.id))==report
    store,ws,task,apply=setup(tmp_path/'oversized');engine=api(store);calls=[];c=apply()
    async def oversized(*args,**kwargs):
        calls.append(args[0]);kwargs['execution_argv'].extend([['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']])
        return 0,'x'*(2*1024*1024+1),None
    monkeypatch.setattr(importlib.import_module('nexus.repair.relation_service'),'run_command',oversized)
    report=asyncio.run(engine.run(c.id))
    assert report['state']=='UNKNOWN' and report['observed_calls']==0 and len(calls)==1
    assert report['batches'][0]['problem']=='OUTPUT_LIMIT'
    assert engine.verify(c.id)==report and asyncio.run(engine.run(c.id))==report and len(calls)==1


@pytest.mark.parametrize('change',['log-changed','log-missing','report-changed','report-missing'])
@pytest.mark.parametrize('when',['before','after'])
def test_public_original_integrity_is_a_relation_prerequisite_and_replay_binding(tmp_path,monkeypatch,change,when):
    store,ws,task,apply=setup(tmp_path);engine=api(store);calls=sdk(monkeypatch,good=True);c=apply(good=True)
    if when=='after':assert asyncio.run(engine.run(c.id))['state']=='PASS'
    public=store.records(task.id,'check')[-1];ref=public['log_ref'] if change.startswith('log') else public['report_ref'];path=store.root/ref
    if change.endswith('missing'):path.unlink()
    else:path.write_text('changed original fixture')
    calls.clear()
    if when=='before':
        result=asyncio.run(engine.run(c.id));assert result['state']=='UNKNOWN' and result['public_test_state']=='UNKNOWN'
        assert result['batches']==[] and calls==[] and engine.verify(c.id)==result
    else:
        with pytest.raises(ValueError):engine.verify(c.id)
        assert calls==[]


def test_shared_public_helper_source_changes_invalidate_relation_pass(tmp_path,monkeypatch):
    from nexus.repair import verification_evidence
    store,ws,task,apply=setup(tmp_path);engine=api(store);sdk(monkeypatch,good=True);c=apply(good=True)
    assert asyncio.run(engine.run(c.id))['state']=='PASS'
    changed=tmp_path/'changed-source'/Path(verification_evidence.__file__).name;changed.parent.mkdir();changed.write_bytes(Path(verification_evidence.__file__).read_bytes()+b'\n# identity fixture\n')
    monkeypatch.setattr(verification_evidence,'__file__',str(changed))
    with pytest.raises(ValueError):engine.verify(c.id)
