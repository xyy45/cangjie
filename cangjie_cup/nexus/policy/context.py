"""Build policy facts from service-owned records, never from model claims."""
import time

from nexus.contracts import digest


def policy_context(task, *, action, request_id, arguments_hash, input_tree_hash,
                   deadline_at, paths=None, subject_id=None, subject_task_id=None,
                   acceptance=None, check_set_hash='', export_verified=False):
    approval = {}
    if acceptance is not None:
        approval = dict(task_id=acceptance.task_id or task.id, candidate_id=acceptance.candidate_id,
            tree_hash=acceptance.tree_hash, spec_hash=acceptance.spec_hash or '',
            verification_plan_hash=acceptance.verification_plan_hash or '',
            check_set_hash=acceptance.check_set_hash, expires_at_ms=int(acceptance.expires_at * 1000))
    facts = dict(task_id=task.id, subject_task_id=subject_task_id or task.id,
        subject_id=subject_id or task.baseline_id, status=task.status, revision=task.revision,
        task_hash=digest(task.model_dump()), allowed_paths=list(task.allowed_paths),
        spec_hash=task.spec_hash or '', verification_plan_hash=task.verification_plan_hash or '',
        tree_hash=input_tree_hash, check_set_hash=check_set_hash,
        now_ms=int(time.time() * 1000), approval=approval, export_verified=export_verified)
    return dict(schema_version=1, policy_version='2.0', action=action, task_id=task.id,
        request_id=request_id, arguments_hash=arguments_hash, input_tree_hash=input_tree_hash,
        deadline_at=deadline_at, paths=list(paths or []), remaining_budget=3-task.attempt_count,
        accepted=acceptance is not None, approval_binding=digest(acceptance.model_dump()) if acceptance else '',
        facts=facts)


def check_task_snapshot(store, context):
    current=store.get_task(context['task_id'])
    facts=context['facts']
    if (current.revision!=facts['revision'] or digest(current.model_dump())!=facts['task_hash']):
        raise ValueError('Task version changed after native decision')
    if facts['approval'] and facts['approval']['expires_at_ms']<=int(time.time()*1000):
        raise ValueError('Approval expired after native decision')
