"""Small SQLite record index with immutable JSON record files."""
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time
import uuid

from nexus.contracts import (TaskRecord, CandidateRecord, CheckResult, ModelCall,
                             ToolCall, AcceptanceRecord, ReviewRecord, RunEvent)


def uid() -> str:
    return uuid.uuid4().hex


class RunStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'records').mkdir(exist_ok=True)
        self.database = self.root / 'runs.sqlite3'
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS records(
                    id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
                    kind TEXT NOT NULL, object_id TEXT, attempt INTEGER, ref TEXT NOT NULL,
                    UNIQUE(kind, object_id));
                CREATE UNIQUE INDEX IF NOT EXISTS candidate_attempt
                    ON records(task_id, attempt) WHERE kind='candidate';
            ''')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def create_task(self, baseline_id: str, goal: str, allowed_paths: list[str]) -> TaskRecord:
        task = TaskRecord(id=uid(), baseline_id=baseline_id, goal=goal, allowed_paths=allowed_paths)
        with self.connect() as db:
            db.execute('INSERT INTO tasks VALUES (?,?)', (task.id, task.model_dump_json()))
        return task

    @staticmethod
    def _decode_task(payload: str) -> TaskRecord:
        data = json.loads(payload)
        # Explicit legacy reader: absent version denotes the original V1 task
        # contract only. It never receives a V1.1 confirmation or new permissions.
        if 'schema_version' not in data:
            legacy_fields = {'id','baseline_id','goal','allowed_paths','test_plan','status','attempt_count'}
            if set(data) - legacy_fields:
                raise ValueError('Unversioned task does not match the legacy contract')
            data = {**data, 'schema_version': 1}
        return TaskRecord.model_validate(data)

    def get_task(self, task_id: str) -> TaskRecord:
        with self.connect() as db:
            row = db.execute('SELECT payload FROM tasks WHERE id=?', (task_id,)).fetchone()
        if not row:
            raise ValueError('unknown task')
        return self._decode_task(row[0])

    def update_task(self, task_id: str, *, expected_status: str | None = None,
                    expected_revision: int | None = None, **changes) -> TaskRecord | None:
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT payload FROM tasks WHERE id=?', (task_id,)).fetchone()
            if not row:
                raise ValueError('unknown task')
            current = self._decode_task(row[0])
            if expected_status is not None and current.status != expected_status:
                return None
            if expected_revision is not None and current.revision != expected_revision:
                return None
            if changes.get('attempt_count', current.attempt_count) < current.attempt_count:
                raise ValueError('attempts cannot decrease')
            task = TaskRecord.model_validate({**current.model_dump(), **changes, 'revision': current.revision+1})
            db.execute('UPDATE tasks SET payload=? WHERE id=?', (task.model_dump_json(), task_id))
            if task.status!=current.status:
                self._append_event(db,task_id,dict(type='TASK_STATE_CHANGED',previous_status=current.status,
                                                 status=task.status,task_revision=task.revision))
        return task

    def _append_event(self, db, task_id: str, payload: dict) -> str:
        sequence=db.execute("SELECT COUNT(*) FROM records WHERE task_id=? AND kind='event'",(task_id,)).fetchone()[0]+1
        row=db.execute('SELECT payload FROM tasks WHERE id=?',(task_id,)).fetchone()
        task=self._decode_task(row[0])
        event_type=payload.get('type') or next((name for key,name in (
            ('selected_candidate_id','CANDIDATE_SELECTED'),('repair_feedback','REPAIR_FEEDBACK'),
            ('policy','POLICY_DECISION'),('stop_reason','STOPPED')) if key in payload),'DETAIL')
        event=RunEvent(event_id=uid(),task_id=task_id,sequence=sequence,type=event_type,
            candidate_id=payload.get('candidate_id',payload.get('selected_candidate_id')),
            status=payload.get('status',task.status),occurred_at=time.time(),data=payload)
        ref=f'records/{event.event_id}.json'
        with (self.root/ref).open('x') as stream:stream.write(event.model_dump_json())
        db.execute('INSERT INTO records VALUES (?,?,?,?,?,?)',
                   (event.event_id,task_id,'event',event.event_id,None,ref))
        return ref

    def append_record(self, task_id: str, kind: str, payload: dict[str, object]) -> str:
        self.get_task(task_id)
        if kind not in ('candidate', 'check', 'model_call', 'tool_call', 'acceptance', 'event', 'review'):
            raise ValueError('unknown record kind')
        if payload.get('task_id', task_id) != task_id:
            raise ValueError('foreign task')

        def reject_secrets(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key.lower() in ('api_key', 'authorization', 'password', 'secret'):
                        raise ValueError('credentials may not be recorded')
                    reject_secrets(child)
            elif isinstance(value, list):
                for child in value:
                    reject_secrets(child)
        reject_secrets(payload)
        if kind=='event':
            with self.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                return self._append_event(db,task_id,payload)
        record_models = {'candidate': CandidateRecord, 'check': CheckResult,
                         'model_call': ModelCall, 'tool_call': ToolCall,
                         'acceptance': AcceptanceRecord, 'review': ReviewRecord}
        if kind in record_models:
            payload = record_models[kind].model_validate(payload).model_dump()
        record_id = uid()
        ref = f'records/{record_id}.json'
        with self.connect() as db:
            for key in ('candidate_id', 'subject_id'):
                subject = payload.get(key)
                if subject:
                    owner = db.execute("SELECT task_id FROM records WHERE object_id=? AND kind='candidate'", (subject,)).fetchone()
                    if owner and owner[0] != task_id:
                        raise ValueError('foreign candidate')
                    if not owner and subject != self.get_task(task_id).baseline_id:
                        raise ValueError('unknown subject')
            try:
                db.execute('INSERT INTO records VALUES (?,?,?,?,?,?)',
                           (record_id, task_id, kind, payload.get('id'), payload.get('attempt'), ref))
                with (self.root / ref).open('x') as stream:
                    json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
            except sqlite3.IntegrityError as exc:
                raise ValueError('duplicate record or attempt') from exc
        return ref

    def records(self, task_id: str, kind: str) -> list[dict]:
        self.get_task(task_id)
        with self.connect() as db:
            refs = db.execute('SELECT ref FROM records WHERE task_id=? AND kind=? ORDER BY rowid', (task_id, kind)).fetchall()
        values=[json.loads((self.root/ref).read_text()) for (ref,) in refs]
        if kind=='event':
            # Explicit read view for original V1 event payloads and new envelopes.
            return [{**RunEvent.model_validate(value).data,**RunEvent.model_validate(value).model_dump()}
                    if 'schema_version' in value else value for value in values]
        return values
