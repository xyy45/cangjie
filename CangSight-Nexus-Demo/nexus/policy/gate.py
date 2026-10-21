from collections.abc import Awaitable, Callable
from pathlib import Path
from copy import deepcopy
import time

from nexus.contracts import ToolResult, digest
from nexus.policy.client import PolicyClient


async def gate_and_execute(request: dict[str, object], action: Callable[[], Awaitable[ToolResult]],
                           *, policy: PolicyClient | None = None, audit: Callable[[dict], str] | None = None) -> ToolResult:
    snapshot = deepcopy(request)
    fingerprint = digest(request)
    native = policy or PolicyClient(Path(__file__).resolve().parents[2])
    decision = await native.decide(request)
    reference = audit({'request': snapshot, 'decision': decision}) if audit else None
    executed=False
    if digest(request) != fingerprint:
        result = ToolResult(operation_status='ERROR', error='POLICY_ARGUMENTS_CHANGED')
    elif decision.get('decision') != 'Allow':
        result = ToolResult(operation_status='ERROR', error=str(decision.get('reason', 'POLICY_DENIED')),
                          data={'policy': decision})
    elif any(decision.get(key)!=snapshot.get(key) for key in ('schema_version','policy_version','request_id','input_tree_hash','arguments_hash','approval_binding')):
        result = ToolResult(operation_status='ERROR',error='POLICY_RESPONSE_BINDING_CHANGED')
    elif snapshot.get('deadline_at',0)<=int(time.time()*1000):
        result = ToolResult(operation_status='ERROR',error='REQUEST_DEADLINE_EXCEEDED')
    else:
        try:
            identity=native.component_identity()
            if any(decision.get(key)!=value for key,value in identity.items()):
                raise ValueError('Policy component changed before action')
        except (OSError,ValueError):
            result=ToolResult(operation_status='ERROR',error='POLICY_COMPONENT_CHANGED')
        else:
            executed=True
            try:
                result = await action()
            except (ValueError,OSError):
                if audit:audit({'policy_outcome':dict(request_id=snapshot.get('request_id'),
                    action=snapshot.get('action'),action_executed=True,operation_status='ERROR',error='ACTION_FAILED')})
                raise
    if reference:
        result.record_refs.append(reference)
    if audit:
        outcome=audit({'policy_outcome':dict(request_id=snapshot.get('request_id'),action=snapshot.get('action'),
            action_executed=executed,operation_status=result.operation_status,error=result.error)})
        result.record_refs.append(outcome)
    return result
