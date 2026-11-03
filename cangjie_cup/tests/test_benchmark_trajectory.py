"""Algorithm fixtures; actual pinned SDK trajectory is tested separately."""
import importlib
import importlib.util
import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from nexus.contracts import digest
from nexus.benchmark.corpus import sha


def api():
    assert importlib.util.find_spec('nexus.benchmark.trajectory') is not None,'trajectory analyzer missing'
    return importlib.import_module('nexus.benchmark.trajectory')


def fixture(tmp_path,monkeypatch,*,first_success=False):
    module=api();root=tmp_path/'run';records=root/'runtime/records';records.mkdir(parents=True)
    candidates=[dict(id='c_one',attempt=1,tree_hash='1'*64,model_call_id='m1-result')]
    if not first_success:candidates.append(dict(id='c_two',attempt=2,tree_hash='2'*64,model_call_id='m2-result'))
    failure=dict(args=[1000,900,200],actual='1100',expected='-1',kind='independent_rule')
    feedback=dict(previous_candidate_id='c_one',tree_hash='1'*64,failure_cases=[failure],
                  failed_checks=[dict(kind='independent_rule',state='FAIL',subject_id='c_one',tree_hash='1'*64)])
    events=[] if first_success else [dict(event_id='e1',repair_feedback=feedback)]
    checks=[];calls=[];search={};manifest={}
    for c in candidates:
        for kind in ('build','test'):
            checks.append(dict(id=c['id']+kind,subject_id=c['id'],tree_hash=c['tree_hash'],plan_hash='plan',kind=kind,state='PASS'))
        n=c['attempt'];ref=f'records/m{n}.request.json'
        body=dict(messages=[dict(role='user',content=json.dumps(dict(iteration=dict(round=n),feedback=[] if n==1 else [feedback])))])
        raw=json.dumps(body).encode();(root/'runtime'/ref).write_bytes(raw);manifest[ref]=sha(raw)
        response_ref=f'records/m{n}.response.json';response=json.dumps(dict(choices=[dict(message=dict(content='fixture'))])).encode()
        (root/'runtime'/response_ref).write_bytes(response);manifest[response_ref]=sha(response)
        for suffix,status in (('','STARTED'),('-result','SUCCEEDED')):
            calls.append(dict(id=f'm{n}'+suffix,request_ref=ref,response_ref=response_ref if suffix else None,status=status,origin='TEST',model_id='fixture'))
        state='FAIL' if n==1 and not first_success else 'PASS'
        search[c['id']]=dict(candidate_id=c['id'],binding=dict(tree_hash=c['tree_hash']),state=state,failures=[failure] if state=='FAIL' else [])
    result=dict(schema_version=2,origin='FIXTURE',result_hash='a'*64,record_manifest=manifest,native_task_id='t',task_id='business_hard_001',
                candidate_id=candidates[-1]['id'],tree_hash=candidates[-1]['tree_hash'],mode='cegis',task_status='REVIEW_PENDING',
                build_state='PASS',public_state='PASS',holdout_state='PASS',independent_search_state='PASS',verified_repair=True)
    rows=dict(candidate=candidates,check=checks,event=events,model_call=calls)
    store=SimpleNamespace(root=root/'runtime',records=lambda task,kind:deepcopy(rows[kind]))
    monkeypatch.setattr(module,'verify_run',lambda *a:deepcopy(result))
    monkeypatch.setattr(module,'RunStore',lambda *a:store)
    monkeypatch.setattr(module,'CangjieVerifier',lambda *a:SimpleNamespace(identity=lambda cid:(None,next(c['tree_hash'] for c in candidates if c['id']==cid),'plan')))
    monkeypatch.setattr(module,'ExplorationService',lambda *a:SimpleNamespace(verify=lambda cid:deepcopy(search[cid])))
    return module,root,result,rows,search


def test_trajectory_first_round_miss_then_bound_counterexample_feedback(tmp_path,monkeypatch):
    module,root,result,rows,search=fixture(tmp_path,monkeypatch)
    report=module.analyze_run(tmp_path/'corpus',root)
    assert report['origin']=='FIXTURE' and report['state']=='KNOWN'
    assert report['initial_candidate']==dict(candidate_id='c_one',tree_hash='1'*64,attempt=1)
    assert report['first_round_missed'] and report['observed_counterexample_feedback'] and report['later_repaired']
    assert report['rounds'][0]['feedback_event_id']=='e1'
    assert report['rounds'][1]['received_counterexample_from']=='c_one'
    assert report['result_hash']==result['result_hash'] and report['record_manifest_hash']==digest(result['record_manifest'])
    assert report==module.analyze_run(tmp_path/'corpus',root)


def test_trajectory_first_round_success_not_claimed_iteration_gain(tmp_path,monkeypatch):
    module,root,*_=fixture(tmp_path,monkeypatch,first_success=True)
    report=module.analyze_run(tmp_path/'corpus',root)
    assert report['first_round_repaired'] and not report['first_round_missed']
    assert not report['later_repaired'] and not report['observed_counterexample_feedback']


@pytest.mark.parametrize('mode',['direct','mcp','cegis'])
def test_first_candidate_holdout_failure_counts_miss_without_search_discovery(tmp_path,monkeypatch,mode):
    module,root,result,rows,search=fixture(tmp_path,monkeypatch,first_success=True)
    result.update(mode=mode,holdout_state='FAIL',verified_repair=False,
                  independent_search_state='PASS' if mode=='cegis' else 'NOT_ENABLED')
    report=module.analyze_run(tmp_path/'corpus',root)
    assert report['state']=='KNOWN' and report['first_round_missed']
    assert not report['search_discovered_counterexample']
    assert not report['observed_counterexample_feedback'] and not report['later_repaired']


def test_later_tree_holdout_failure_is_not_attributed_to_first_tree(tmp_path,monkeypatch):
    module,root,result,rows,search=fixture(tmp_path,monkeypatch)
    search['c_one'].update(state='PASS',failures=[])
    result.update(holdout_state='FAIL',verified_repair=False)
    report=module.analyze_run(tmp_path/'corpus',root)
    assert not report['first_round_missed']


@pytest.mark.parametrize('outcome',['FAILED','IN_DOUBT'])
def test_feedback_request_is_observed_even_without_next_candidate(tmp_path,monkeypatch,outcome):
    module,root,result,rows,search=fixture(tmp_path,monkeypatch)
    rows['candidate'].pop();rows['check']=[c for c in rows['check'] if c['subject_id']=='c_one']
    rows['model_call'][-1]['status']=outcome
    if outcome=='IN_DOUBT':rows['model_call'][-1]['response_ref']=None
    rows['event'].append(dict(stop_reason='Model response schema rejected'))
    result.update(candidate_id='c_one',tree_hash='1'*64,task_status='REJECTED',holdout_state='FAIL',independent_search_state='FAIL',verified_repair=False)
    report=module.analyze_run(tmp_path/'corpus',root)
    assert report['first_round_missed'] and not report['later_repaired']
    assert report['observed_counterexample_feedback']==(outcome=='FAILED')
    assert 'GENERATION_OUTPUT_INVALID' in report['failure_classes']
    assert len(report['feedback_requests'])==1
    assert report['feedback_requests'][0]['source_candidate_id']=='c_one'
    assert report['feedback_requests'][0]['request_ref']=='records/m2.request.json'
    if outcome=='IN_DOUBT':assert report['state']=='UNKNOWN'


@pytest.mark.parametrize('mutation',['missing-search','wrong-tree','unsent','unknown-model','wrong-attempt','wrong-feedback'])
def test_unknown_missing_or_wrong_tree_never_counts_success(tmp_path,monkeypatch,mutation):
    module,root,result,rows,search=fixture(tmp_path,monkeypatch)
    if mutation=='missing-search':search['c_one']=None
    elif mutation=='wrong-tree':search['c_one']['binding']['tree_hash']='f'*64
    elif mutation=='unknown-model':rows['model_call'][-1]['status']='IN_DOUBT'
    elif mutation=='wrong-attempt':rows['candidate'][1]['attempt']=3
    elif mutation=='wrong-feedback':rows['event'][0]['repair_feedback']['tree_hash']='f'*64
    else:
        ref='records/m2.request.json';path=root/'runtime'/ref;body=json.loads(path.read_bytes())
        context=json.loads(body['messages'][0]['content']);context['feedback']=[];body['messages'][0]['content']=json.dumps(context)
        raw=json.dumps(body).encode();path.write_bytes(raw);result['record_manifest'][ref]=sha(raw)
    report=module.analyze_run(tmp_path/'corpus',root)
    assert not report['later_repaired']
    # A bad later candidate cannot erase an independently acknowledged request.
    assert report['observed_counterexample_feedback']==(mutation=='wrong-attempt')
    if mutation!='unsent':assert report['state']=='UNKNOWN'


def test_source_tampering_is_rejected_before_trajectory_claim(tmp_path,monkeypatch):
    module,root,result,rows,search=fixture(tmp_path,monkeypatch)
    (root/'runtime/records/m2.request.json').write_text('{}')
    with pytest.raises(ValueError,match='摘要'):module.analyze_run(tmp_path/'corpus',root)


@pytest.mark.parametrize('change,expected',[
    ('build','BUILD_FAILED'),('public','PUBLIC_BEHAVIOR_FAILED'),('holdout','HOLDOUT_FAILED'),
    ('search','SEARCH_COUNTEREXAMPLE_EXHAUSTED'),('invalid','GENERATION_OUTPUT_INVALID'),
    ('policy','POLICY_REJECTED'),('unknown','INFRASTRUCTURE_UNKNOWN')])
def test_failure_classes_keep_raw_states(tmp_path,monkeypatch,change,expected):
    module,root,result,rows,search=fixture(tmp_path,monkeypatch,first_success=True)
    result['verified_repair']=False
    if change in ('build','public','holdout'):result[change+'_state']='FAIL'
    elif change=='search':result['independent_search_state']='FAIL';result['task_status']='UNREPAIRED'
    elif change=='unknown':result['holdout_state']='UNKNOWN'
    elif change=='invalid':
        result['task_status']='REJECTED';rows['event'].append(dict(stop_reason='Model response schema rejected'));rows['model_call'][-1]['status']='FAILED'
    else:result['task_status']='REJECTED';rows['event'].append(dict(stop_reason='Candidate exceeds the confirmed editable scope'))
    report=module.analyze_run(tmp_path/'corpus',root)
    assert expected in report['failure_classes']
    assert report['raw_states']['task_status']==result['task_status']
