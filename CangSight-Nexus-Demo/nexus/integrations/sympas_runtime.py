"""Minimal derived Sympas gateway; no original domain executors or state database.

Derived from nuptpisa/CangSight, commit
5db0c7eeeb6a62812fc04e9e88497339fed5e11f,
Sympas-Nexus/nexus/gateway/app.py, Apache-2.0.
Changes: extract public-value filtering, run-query route and generic dispatcher;
inject the existing CangSight controller and use its sole state store. This is a modified subset,
not the unmodified upstream create_app application. See docs/third-party/sympas.
"""
from typing import Any, Mapping
import hashlib
import logging
from pathlib import Path
import threading
import time

from flask import Blueprint, jsonify, request

BASE_COMMIT = '5db0c7eeeb6a62812fc04e9e88497339fed5e11f'
ADAPTER_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
logger = logging.getLogger(__name__)
_SENSITIVE_FIELDS = {
    "authorization", "cookie", "set_cookie", "credential", "credentials",
    "api_key", "apikey",
}


def _is_sensitive_field(name: Any) -> bool:
    normalized = str(name).strip().lower().replace("-", "_")
    return (
        normalized in _SENSITIVE_FIELDS
        or normalized.endswith("_token")
        or normalized.endswith("_secret")
        or normalized.endswith("_password")
        or normalized.endswith("_api_key")
    )


def _public_value(value: Any) -> Any:
    """递归脱敏 Gateway 对外数据，避免令牌进入 Dashboard、SSE 和日志。"""
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _is_sensitive_field(key) else _public_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_public_value(item) for item in value]
    return value


class RuntimeBridge:
    """Upstream dispatch metadata is an event projection, never business state."""
    def __init__(self, store):
        self.store = store

    def append_event(self, run_id, event_type, payload):
        return self.store.append_record(run_id, 'event', dict(
            type='SYMPAS_'+event_type.upper(), base_commit=BASE_COMMIT,adapter_sha256=ADAPTER_SHA256,
            dispatch_payload=_public_value(payload)))

    def update_run(self, run_id, **changes):
        self.append_event(run_id, 'dispatch_state', changes)
        if changes.get('status') == 'failed':
            task = self.store.get_task(run_id)
            if task.status in {'READY','DIAGNOSING','GENERATING','APPLYING','BUILDING','TESTING'}:
                self.store.update_task(run_id, expected_status=task.status,
                    expected_revision=task.revision, status='IN_DOUBT')


def _append_run_event(run_id, event_type, payload, *, store):
    return store.append_event(run_id, event_type, payload)


def _update_run(run_id, *, store, **changes):
    store.update_run(run_id, **changes)


def _execute_run(run_id, team_profile, payload, store, handler):
    """Derived from upstream app.py:_execute_run; handler/store are injected.

    Removed global domain registry/default database; redact exception messages.
    The upstream queued/running/completed states describe dispatch only.
    """
    run_store = store
    handler = handler if team_profile == 'cangjie-repair' else None
    if handler is None:
        _update_run(run_id, store=run_store, status='failed', error='Unknown capability')
        _append_run_event(run_id, 'run_failed', {'error':'Unknown capability'}, store=run_store)
        return

    _update_run(
        run_id, store=run_store, status="running",
        started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    )
    _append_run_event(run_id, "run_started", {"team_profile":team_profile}, store=run_store)

    def emit_run_event(event_type: str, payload_data: dict) -> None:
        _append_run_event(run_id, event_type, payload_data, store=run_store)

    handler_payload = dict(payload)
    handler_payload["_run_id"] = run_id
    handler_payload["_emit_event"] = emit_run_event

    try:
        result = handler(handler_payload)
        _update_run(
            run_id, store=run_store, status="completed",
            finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), result=result,
        )
        _append_run_event(run_id, "run_finished", {"result":result}, store=run_store)
    except Exception as exc:
        # Do not copy upstream logger.exception/str(exc): errors may contain credentials.
        logger.warning('Gateway dispatch failed: %s', type(exc).__name__)
        _update_run(
            run_id, store=run_store, status="failed",
            finished_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            error=type(exc).__name__,
        )
        _append_run_event(run_id, "run_failed", {"error":type(exc).__name__}, store=run_store)


def gateway(store, start_task, task_view, run_task):
    """Mount only Cangjie run creation/query; caller must enforce operator guards."""
    routes = Blueprint('sympas_cangjie', __name__)
    bridge = RuntimeBridge(store)

    def handler(payload):
        run_task(payload['_run_id'])
        task = store.get_task(payload['_run_id'])
        return dict(task_id=task.id, status=task.status)

    @routes.post('/agents/runs')
    def create_run():
        body = request.get_json()
        if (not isinstance(body, dict)
                or set(body) != {'schema_version', 'team_profile', 'payload'}
                or type(body['schema_version']) is not int or body['schema_version'] != 1
                or body['team_profile'] != 'cangjie-repair'):
            raise ValueError('Unsupported gateway contract or capability')
        # Same transaction, idempotency, confirmed requirements and single loop.
        def dispatch(run_id):
            # Retains the upstream create_run queue/event/thread dispatch sequence.
            _append_run_event(run_id, 'run_queued', {'team_profile':'cangjie-repair'}, store=bridge)
            worker = threading.Thread(target=_execute_run,
                args=(run_id,'cangjie-repair',body['payload'],bridge,handler),daemon=True)
            try:
                worker.start()
            except RuntimeError as exc:
                bridge.update_run(run_id,status='failed',error=type(exc).__name__)
        response = start_task(body['payload'], base_commit=BASE_COMMIT,
            adapter_sha256=ADAPTER_SHA256,dispatch=dispatch)
        data = response.get_json()
        return jsonify(_public_value(dict(data, run_id=data['id'])))

    @routes.get('/agents/runs/<run_id>')
    def get_run(run_id):
        try:
            store.get_task(run_id)
        except ValueError:
            return jsonify({"status": "error", "message": "run not found"}), 404
        response = task_view(run_id)
        return jsonify(_public_value(dict(response.get_json(), run_id=run_id,
                                         tool_calls=store.records(run_id, 'tool_call'))))

    @routes.get('/agents/runs/<run_id>/events')
    def get_run_events(run_id):
        try:
            store.get_task(run_id)
        except ValueError:
            return jsonify({"status": "error", "message": "run not found"}), 404
        raw = request.args.get('after_event_id', request.headers.get('Last-Event-ID', '0'))
        if not raw.isascii() or not raw.isdigit():
            raise ValueError('Nonnegative event cursor required')
        events = [event for event in store.records(run_id, 'event')
                  if event.get('sequence', 0) > int(raw)][:100]
        return jsonify(events=_public_value(events), limit=100,
                       last_event_id=events[-1]['sequence'] if events else int(raw))

    return routes
