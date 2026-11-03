"""Native transition permit, followed by a short service-owned CAS commit."""
from nexus.contracts import TaskRecord
from nexus.policy.core import NativeCoreClient


def transition_payload(current,updated):
    return dict(task_id=current.id,from_status=current.status,to_status=updated.status,
        revision=current.revision,expected_revision=current.revision,new_revision=updated.revision,
        attempt_count=current.attempt_count,next_attempt_count=updated.attempt_count)


def prepare_update(current,**changes):
    updated=TaskRecord.model_validate({**current.model_dump(),**changes,'revision':current.revision+1})
    if updated.id!=current.id:raise ValueError('Task identity cannot change')
    payload=transition_payload(current,updated)
    proof=NativeCoreClient().call_sync('task.transition',payload)
    if proof['response']['data']!={'decision':'Allow','reason':'PERMITTED'}:
        raise ValueError('NATIVE_STATE_DENIED: '+proof['response']['data'].get('reason','invalid decision'))
    return updated,proof


def permit_matches(proof,current,updated):
    payload=transition_payload(current,updated)
    # No process is started here. Recheck all IPC bindings and actual component
    # bytes at commit, even if the valid decision was obtained before this txn.
    data=NativeCoreClient().verify_proof(proof,'task.transition',payload)
    return data=={'decision':'Allow','reason':'PERMITTED'}
