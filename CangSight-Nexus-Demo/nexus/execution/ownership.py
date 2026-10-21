"""OS-backed controller ownership and conservative restart accounting, no replay."""
import fcntl
import json
import os
import stat
from pathlib import Path
import time

from nexus.store import uid

_active_owners={}


def owner_token(root: Path):
    return _active_owners.get(Path(root).resolve())


def verify_write_owner(root: Path, token):
    root=Path(root)
    metadata=root/'.controller-owner.json'
    if not metadata.exists():return  # Explicit isolated CLI/test runtime, not a managed workbench.
    value=json.loads(metadata.read_text())
    if value.get('schema_version')!=1 or not token or value.get('owner_id')!=token:
        raise ValueError('OWNER_UNCONFIRMED: managed runtime write ownership required')
    with (root/'.controller.lock').open('a+b') as handle:
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        fcntl.flock(handle,fcntl.LOCK_UN)
    raise ValueError('OWNER_UNCONFIRMED: controller lock is no longer held')


class RuntimeOwner:
    def __init__(self, root: Path):
        self.root=Path(root)
        self.handle=None
        self.token=None

    def acquire(self):
        self.root.mkdir(parents=True,exist_ok=True)
        handle=(self.root/'.controller.lock').open('a+b')
        try:fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return False
        self.handle=handle
        self.token=uid()
        _active_owners[self.root.resolve()]=self.token
        pending=self.root/'.controller-owner.next'
        pending.write_text(json.dumps(dict(schema_version=1,owner_id=self.token,pid=os.getpid(),
            acquired_at=time.time(),authority='held OS flock; PID is informational only')))
        pending.replace(self.root/'.controller-owner.json')
        return True

    def close(self):
        if self.handle:
            _active_owners.pop(self.root.resolve(),None)
            fcntl.flock(self.handle,fcntl.LOCK_UN)
            self.handle.close();self.handle=None;self.token=None

    def session_key(self):
        path=self.root/'.session-key'
        if path.is_symlink():raise ValueError('Session key must be a local regular file')
        if not path.exists():
            if not self.handle:raise ValueError('Runtime owner must initialize the session key')
            with path.open('xb') as stream:
                os.chmod(path,0o600)
                stream.write(os.urandom(32))
        key=path.read_bytes()
        if len(key)!=32:raise ValueError('Invalid local session key')
        return key

    def operator_key(self):
        path=self.root/'.operator-key'
        if not path.exists() and not path.is_symlink():
            if not self.handle:raise ValueError('Runtime owner must initialize operator credential')
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(descriptor,'w') as stream:stream.write(os.urandom(32).hex()+'\n')
        descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor) as stream:
            metadata=os.fstat(stream.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=os.geteuid() or stat.S_IMODE(metadata.st_mode)!=0o600:
                raise ValueError('Operator credential must be an owned private regular file')
            key=stream.read(66).strip()
        if len(key)!=64 or any(c not in '0123456789abcdef' for c in key):
            raise ValueError('Invalid operator credential')
        return key

    def reconcile(self, store):
        if not self.handle or store.root.resolve()!=self.root.resolve():
            raise ValueError('Runtime ownership must be confirmed before restart reconciliation')
        affected=[]
        active={'READY','DIAGNOSING','GENERATING','APPLYING','BUILDING','TESTING','EXPORTING'}
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            has_operations=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tool_requests'").fetchone()
            has_approvals=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='acceptances'").fetchone()
            for task_id,payload in db.execute('SELECT id,payload FROM tasks').fetchall():
                task=store._decode_task(payload)
                if task.status not in active:continue
                previous=task.status
                requests=db.execute("SELECT request_id,request_ref FROM tool_requests WHERE task_id=? AND state='STARTED'",(task_id,)).fetchall() if has_operations else []
                calls={r['id']:r for r in store.records(task_id,'model_call')}
                pending=[r['id'] for r in calls.values() if r['status']=='STARTED' and calls.get(r['id']+'-result',{}).get('status') not in ('SUCCEEDED','FAILED')]
                task.status='BLOCKED' if previous=='READY' and not requests and not pending else 'IN_DOUBT'
                task.revision+=1
                db.execute('UPDATE tasks SET payload=? WHERE id=?',(task.model_dump_json(),task_id))
                if has_operations:
                    db.execute("UPDATE tool_requests SET state='IN_DOUBT' WHERE task_id=? AND state='STARTED'",(task_id,))
                if has_approvals:
                    db.execute("UPDATE acceptances SET status='IN_DOUBT' WHERE status='EXPORTING' AND candidate_id IN (SELECT object_id FROM records WHERE task_id=? AND kind='candidate')",(task_id,))
                store._append_event(db,task_id,dict(type='CONTROLLER_RESTARTED',status=task.status,
                    previous_status=previous,task_revision=task.revision,owner_id=self.token,
                    request_ids=[row[0] for row in requests],request_refs=[row[1] for row in requests],
                    model_call_ids=pending,stop_reason='CONTROLLER_RESTARTED: manual reconciliation required; no automatic replay'))
                affected.append(dict(task_id=task_id,status=task.status))
        return affected
