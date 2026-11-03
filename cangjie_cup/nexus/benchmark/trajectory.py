"""Read-only, record-bound observations; feedback correlation is not causality."""
import json
from pathlib import Path, PurePosixPath

from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.benchmark.corpus import sha
from nexus.benchmark.runner import verify_run
from nexus.contracts import digest
from nexus.repair.exploration import ExplorationService
from nexus.store import RunStore


def analyze_run(corpus_root,run_root):
    result=verify_run(corpus_root,run_root)
    store=RunStore(Path(run_root)/'runtime');task=result['native_task_id']
    candidates=store.records(task,'candidate');checks=store.records(task,'check')
    events=store.records(task,'event');calls=store.records(task,'model_call')
    by_call={c['id']:c for c in calls};manifest=result['record_manifest'];issues=[];rounds=[];feedbacks={}
    verifier=CangjieVerifier(store.root,task);searcher=ExplorationService(store)

    def bound_bytes(ref):
        p=PurePosixPath(ref or '')
        if p.is_absolute() or len(p.parts)!=2 or p.parts[0]!='records' or '..' in p.parts or str(p)!=ref or '\\' in ref:
            raise ValueError('轨迹请求引用无效')
        path=store.root/ref
        if ref not in manifest or path.is_symlink() or sha(path.read_bytes())!=manifest[ref]:raise ValueError('轨迹请求摘要变化')
        return path.read_bytes()

    def request_context(call):
        raw=bound_bytes(call.get('request_ref'))
        try:
            body=json.loads(raw);users=[m for m in body['messages'] if m['role']=='user']
            if len(users)!=1:return None
            context=json.loads(users[0]['content'])
            return context if isinstance(context,dict) else None
        except (ValueError,TypeError,KeyError):return None

    # A response may be rejected before any candidate is registered. Its request
    # still belongs in the feedback-delivery observations, independently of trees.
    requests=[];request_index={}
    for number,call in enumerate((c for c in calls if c['status']=='STARTED'),1):
        reply=by_call.get(call['id']+'-result',{});context=request_context(call)
        iteration=context.get('iteration') if context is not None else None
        valid_round=isinstance(iteration,dict) and type(iteration.get('round')) is int and iteration['round']==number
        acknowledged=(reply.get('status') in ('SUCCEEDED','FAILED') and reply.get('request_ref')==call['request_ref'] and bool(reply.get('response_ref')))
        if acknowledged:bound_bytes(reply['response_ref'])
        if not valid_round:issues.append('REQUEST_ROUND_UNKNOWN')
        if not acknowledged:issues.append('MODEL_OUTCOME_OR_DELIVERY_UNKNOWN')
        entry=dict(model_call_id=reply.get('id'),round=number,request_ref=call['request_ref'],request_sha256=manifest[call['request_ref']],
                   response_ref=reply.get('response_ref'),response_sha256=manifest.get(reply.get('response_ref')),
                   outcome=reply.get('status','UNKNOWN'),state='KNOWN' if valid_round and acknowledged else 'UNKNOWN',context=context)
        requests.append(entry);request_index[reply.get('id')]=entry

    for expected_attempt,candidate in enumerate(candidates,1):
        cid=candidate['id'];tree=candidate['tree_hash'];attempt=candidate['attempt']
        row=dict(candidate_id=cid,tree_hash=tree,attempt=attempt,build_state='UNKNOWN',public_state='UNKNOWN',
                 search_state='UNKNOWN' if result['mode']=='cegis' else 'NOT_ENABLED',model_call_id=candidate.get('model_call_id'),
                 request_ref=None,request_sha256=None,feedback_event_id=None,feedback_hash=None,
                 received_counterexample_from=None)
        start_issues=len(issues)
        if type(attempt) is not int or attempt!=expected_attempt:issues.append('ATTEMPT_SEQUENCE_MISMATCH')
        try:
            _,actual,plan=verifier.identity(cid)
            if actual!=tree:raise ValueError('candidate tree mismatch')
            for kind,key in (('build','build_state'),('test','public_state')):
                bound=[c for c in checks if c['subject_id']==cid and c['tree_hash']==tree and c['plan_hash']==plan and c['kind']==kind]
                if bound:row[key]=bound[-1]['state']
                if row[key] not in ('PASS','FAIL') and not (kind=='test' and row['build_state']=='FAIL'):issues.append('CHECK_UNKNOWN')
        except (ValueError,OSError,KeyError):issues.append('CANDIDATE_IDENTITY_UNKNOWN')
        search=None
        if result['mode']=='cegis' and row['build_state']==row['public_state']=='PASS':
            try:
                search=searcher.verify(cid)
                if (not search or search.get('candidate_id')!=cid or search.get('binding',{}).get('tree_hash')!=tree or
                        search.get('state') not in ('PASS','FAIL')):raise ValueError('search binding unknown')
                row['search_state']=search['state']
            except (ValueError,OSError,KeyError):issues.append('SEARCH_UNKNOWN')
        elif result['mode']=='cegis':row['search_state']='NOT_RUN'

        call=by_call.get(candidate.get('model_call_id'),{});request=request_index.get(call.get('id'))
        if (call.get('status')!='SUCCEEDED' or request is None or request['state']!='KNOWN' or
                request['round']!=attempt):issues.append('CANDIDATE_MODEL_BINDING_UNKNOWN')
        else:
            row['request_ref']=request['request_ref'];row['request_sha256']=request['request_sha256']

        if row['search_state']=='FAIL' and search:
            matches=[]
            for event in events:
                feedback=event.get('repair_feedback',{})
                if feedback.get('previous_candidate_id')!=cid:continue
                if (feedback.get('tree_hash')!=tree or feedback.get('failure_cases')!=search.get('failures') or
                        not feedback.get('failure_cases') or not any(c.get('kind')=='independent_rule' and c.get('state')=='FAIL'
                            and c.get('subject_id')==cid and c.get('tree_hash')==tree for c in feedback.get('failed_checks',[]))):
                    issues.append('FEEDBACK_BINDING_UNKNOWN');continue
                matches.append((event,feedback))
            if len(matches)==1:
                event,feedback=matches[0];row['feedback_event_id']=event.get('event_id');row['feedback_hash']=digest(feedback)
                feedbacks[cid]=feedback
            else:issues.append('FEEDBACK_MISSING_OR_AMBIGUOUS')
        row['state']='KNOWN' if len(issues)==start_issues else 'UNKNOWN';rounds.append(row)

    feedback_requests=[]
    for request in requests:
        context=request['context'];supplied=context.get('feedback',[]) if context is not None else []
        if not isinstance(supplied,list):issues.append('REQUEST_FEEDBACK_UNKNOWN');continue
        for source in rounds:
            feedback=feedbacks.get(source['candidate_id'])
            if (feedback and source['state']=='KNOWN' and request['round']>source['attempt'] and
                    any(digest(f)==digest(feedback) for f in supplied)):
                item={k:v for k,v in request.items() if k!='context'}
                item.update(source_candidate_id=source['candidate_id'],source_tree_hash=source['tree_hash'],
                            feedback_event_id=source['feedback_event_id'],feedback_hash=source['feedback_hash'])
                feedback_requests.append(item)
                if request['state']=='KNOWN':
                    for row in rounds:
                        if row['model_call_id']==request['model_call_id']:row['received_counterexample_from']=source['candidate_id']

    raw={k:result[k] for k in ('task_status','build_state','public_state','holdout_state','independent_search_state')}
    if any(v in ('UNKNOWN','UNAVAILABLE','IN_DOUBT') for v in raw.values()):issues.append('FINAL_VERIFICATION_UNKNOWN')
    failure=[]
    if result['build_state']=='FAIL':failure.append('BUILD_FAILED')
    if result['public_state']=='FAIL':failure.append('PUBLIC_BEHAVIOR_FAILED')
    if result['holdout_state']=='FAIL':failure.append('HOLDOUT_FAILED')
    if result['independent_search_state']=='FAIL' and result['task_status']=='UNREPAIRED':failure.append('SEARCH_COUNTEREXAMPLE_EXHAUSTED')
    reasons=[e.get('stop_reason','') for e in events]
    if any('Model response schema rejected' in s or 'Model analysis references' in s for s in reasons):failure.append('GENERATION_OUTPUT_INVALID')
    if any('Candidate exceeds the confirmed editable scope' in s for s in reasons) or any(e.get('policy',{}).get('decision')=='DENY' for e in events if isinstance(e.get('policy',{}),dict)):
        failure.append('POLICY_REJECTED')
    if result['task_status'] in ('BLOCKED','IN_DOUBT') or not rounds and not failure:issues.append('RUN_INCOMPLETE_OR_UNKNOWN')
    if issues:failure.insert(0,'INFRASTRUCTURE_UNKNOWN')
    state='UNKNOWN' if issues else 'KNOWN';observed=any(r['state']=='KNOWN' for r in feedback_requests)
    # Holdout can establish an initial miss only when it grades that exact tree.
    initial_holdout_failed=bool(rounds and result['candidate_id']==rounds[0]['candidate_id'] and result['tree_hash']==rounds[0]['tree_hash'] and result['holdout_state']=='FAIL')
    first_missed=bool(rounds and rounds[0]['state']=='KNOWN' and rounds[0]['build_state']==rounds[0]['public_state']=='PASS' and
                      (rounds[0]['search_state']=='FAIL' or initial_holdout_failed))
    first_feedback=bool(rounds and any(r['state']=='KNOWN' and r['source_candidate_id']==rounds[0]['candidate_id'] and r['round']<=rounds[-1]['attempt'] for r in feedback_requests))
    later=(state=='KNOWN' and first_feedback and first_missed and bool(result['verified_repair']) and rounds[-1]['candidate_id']==result['candidate_id'] and len(rounds)>1)
    report=dict(schema_version=1,kind='VERIFIED_TRAJECTORY_OBSERVATION',origin=result['origin'],state=state,
                result_hash=result['result_hash'],record_manifest_hash=digest(manifest),task_id=result['task_id'],mode=result['mode'],
                initial_candidate={k:rounds[0][k] for k in ('candidate_id','tree_hash','attempt')} if rounds else None,rounds=rounds,
                first_round_repaired=bool(state=='KNOWN' and len(rounds)==1 and result['verified_repair']),first_round_missed=first_missed,
                search_discovered_counterexample=any(r['state']=='KNOWN' and r['search_state']=='FAIL' for r in rounds),
                feedback_requests=feedback_requests,observed_counterexample_feedback=bool(observed),later_repaired=bool(later),raw_states=raw,
                failure_class=failure[0] if failure else 'NONE_OBSERVED',failure_classes=failure,unknown_reasons=sorted(set(issues)),
                limitations=['Observed feedback followed by repair is correlation, not causal attribution.',
                             'FIXTURE origin is not real model improvement; holdout is never model feedback.'])
    report['trajectory_hash']=digest(report);return report
