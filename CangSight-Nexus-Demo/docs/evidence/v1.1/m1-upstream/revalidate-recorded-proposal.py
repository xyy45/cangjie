"""Local audit: reverify a recorded LIVE proposal; never construct/call a model.
Requires this developer's retained original run. Not another LIVE generation.
This manual MCP revalidation does not exercise the separately tested base dispatcher.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from nexus.contracts import CandidateProposal, CandidateRecord, tree_hash
from nexus.execution.delivery import DeliveryService
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from nexus.requirements.service import RequirementService
from nexus.store import RunStore, uid


async def main():
    started=time.monotonic()
    prior=json.loads((ROOT/'docs/evidence/v1.1/live/current-live-summary.json').read_text())
    old=RunStore(Path(prior['run_directory']))
    old_task=old.get_task(prior['task_id'])
    source_calls=[r for r in old.records(old_task.id,'model_call') if r['status']=='SUCCEEDED']
    assert len(source_calls)==1 and source_calls[0]['origin']=='LIVE'
    response=json.loads((old.root/source_calls[0]['response_ref']).read_text())
    proposal=CandidateProposal.model_validate_json(response['choices'][0]['message']['content'])
    source_candidate=WorkspaceStore(old.root).candidate(prior['candidate_id'])
    assert proposal.edits==source_candidate.edits
    old_approval=old.records(old_task.id,'acceptance')[0]
    current_old_plan=CangjieVerifier(old.root,old_task.id).identity(source_candidate.id)[2]
    old_plans={check['plan_hash'] for check in old.records(old_task.id,'check') if check['subject_id']==source_candidate.id}
    assert current_old_plan not in old_plans
    try:DeliveryService(old).acceptance(source_candidate.id,old_approval['id'])
    except ValueError as exc:invalidation_reason=str(exc)
    else:raise AssertionError('Old approval must not survive changed executor identity')
    original_archive=Path(prior['archive'])
    assert hashlib.sha256(original_archive.read_bytes()).hexdigest()==prior['archive_sha256']
    run=ROOT/'.runtime/revalidation'/uid()
    store=RunStore(run)
    ws=WorkspaceStore(run,registered=[ROOT/'fixtures/order-demo-bug'])
    baseline=ws.import_project(ROOT/'fixtures/order-demo-bug','.')
    assert tree_hash(ws.verify_baseline(baseline))==source_candidate.baseline_hash
    service=RequirementService(store)
    draft=service.prepare_requirement('order-demo-bug',old_task.goal)
    spec=service.confirm_requirement(draft['id'],dict(schema_version=1,expected_version=draft['version'],
        requirements=draft['requirements'],allowed_paths=draft['allowed_paths']),actor_id='EXECUTOR_REVALIDATION_OPERATOR')
    task=service.prepare_task('order-demo-bug',spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    ref='records/prior-live-archive.zip';shutil.copyfile(original_archive,run/ref)
    store.append_record(task.id,'event',dict(type='PRIOR_LIVE_PROPOSAL_PROVENANCE',
        source_task_id=old_task.id,source_candidate_id=source_candidate.id,
        source_model_call_id=source_calls[0]['id'],source_model_id=source_calls[0]['model_id'],
        source_archive_ref=ref,source_archive_sha256=prior['archive_sha256'],
        old_approval_invalidated=True,invalidation_reason=invalidation_reason,new_model_requests=0,
        message='Exact recorded model proposal reused with explicit provenance; not a new model generation'))
    async with ToolClient(run) as client:
        async def call(name,**args):
            result=await client.call_tool(name,dict(task_id=task.id,**args))
            if result.operation_status!='OK':raise RuntimeError(f'{name}: {result.operation_status}: {result.error}')
            return result.data
        store.update_task(task.id,status='DIAGNOSING')
        diagnosis=await call('project.diagnose',subject_id=baseline)
        assert diagnosis['build']['state']=='PASS' and diagnosis['test']['state']=='FAIL'
        store.update_task(task.id,status='APPLYING')
        candidate=CandidateRecord.model_validate(await call('candidate.apply',proposal=proposal.model_dump()))
        assert candidate.tree_hash==source_candidate.tree_hash
        args=dict(candidate_id=candidate.id,expected_tree_hash=candidate.tree_hash)
        store.update_task(task.id,status='BUILDING')
        build=await call('candidate.build',**args);assert build['state']=='PASS',build['diagnostics']
        store.update_task(task.id,status='TESTING')
        test=await call('candidate.test',**args);assert test['state']=='PASS',test['diagnostics']
        assert test['counts']['passed']==11 and test['counts']['failed']==0
        store.update_task(task.id,status='REVIEW_PENDING')
        store.append_record(task.id,'event',dict(selected_candidate_id=candidate.id,origin='PRIOR_LIVE_EXECUTOR_REVALIDATION'))
        delivery=DeliveryService(store)
        approval=delivery.accept(candidate.id,delivery.check_set_hash(candidate.id),actor_id='EXECUTOR_REVALIDATION_OPERATOR')
        exported=await call('candidate.export',candidate_id=candidate.id,acceptance_id=approval.id)
        assert exported['status']=='DELIVERED'
        artifact=delivery.verify_archive(exported['export_id'],approval)
    assert store.records(task.id,'model_call')==[]
    summary=dict(schema_version=1,origin='REVALIDATION_OF_RECORDED_LIVE_PROPOSAL',task_id=task.id,
        candidate_id=candidate.id,tree_hash=candidate.tree_hash,run_directory=str(run),
        source_task_id=old_task.id,source_candidate_id=source_candidate.id,source_model_call_id=source_calls[0]['id'],
        source_model_id=source_calls[0]['model_id'],source_archive_sha256=prior['archive_sha256'],
        proposal_edits_identical_to_recorded_response=True,new_model_requests=0,total_paid_requests_in_goal=1,
        old_approval_invalidated=True,invalidation_reason=invalidation_reason,
        old_plan_hashes=sorted(old_plans),current_old_task_plan_hash=current_old_plan,
        executor_source_sha256=hashlib.sha256((ROOT/'nexus/execution/runner.py').read_bytes()).hexdigest(),
        status=store.get_task(task.id).status,baseline_test=diagnosis['test']['counts'],candidate_test=test['counts'],
        current_checks=store.records(task.id,'check'),export_id=exported['export_id'],archive=str(artifact),
        archive_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),approval_actor=approval.actor_id,
        elapsed_seconds=round(time.monotonic()-started,3),external_reproduction='PENDING',m1_status='NOT_EXERCISED_BY_THIS_MANUAL_REVALIDATION')
    (run/'validation-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    (ROOT/'docs/evidence/v1.1/m1-upstream/current-executor-revalidation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps({key:summary[key] for key in ('origin','task_id','status','new_model_requests','elapsed_seconds','archive_sha256')},ensure_ascii=False))


if __name__=='__main__':asyncio.run(main())
