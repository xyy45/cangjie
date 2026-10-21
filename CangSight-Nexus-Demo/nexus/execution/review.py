"""Trusted user review and cancellation; neither action starts a repair."""
from nexus.contracts import ReviewRecord
from nexus.execution.workspace import WorkspaceStore
from nexus.store import RunStore, uid


class ReviewService:
    def __init__(self, store: RunStore):
        self.store=store

    @staticmethod
    def actor(actor_id):
        if not isinstance(actor_id,str) or not 1<=len(actor_id)<=128:
            raise ValueError('Trusted local user identity required')

    def record(self, db, review: ReviewRecord):
        ref=f'records/{review.id}.json'
        with (self.store.root/ref).open('x') as stream:stream.write(review.model_dump_json())
        db.execute('INSERT INTO records VALUES (?,?,?,?,?,?)',
                   (review.id,review.task_id,'review',review.id,None,ref))
        self.store._append_event(db,review.task_id,dict(type='USER_REVIEW',candidate_id=review.candidate_id,
            review_id=review.id,decision=review.decision,decision_source=review.decision_source,
            actor_id=review.actor_id,reason=review.reason))
        return ref

    def reject(self, candidate_id, task_revision, *, actor_id, reason=''):
        self.actor(actor_id)
        c=WorkspaceStore(self.store.root).candidate(candidate_id)
        from nexus.execution.delivery import DeliveryService
        try:check_hash=DeliveryService(self.store).check_set_hash(candidate_id)
        except ValueError:check_hash=None
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            task=self.store._decode_task(db.execute('SELECT payload FROM tasks WHERE id=?',(c.task_id,)).fetchone()[0])
            selected=[e['selected_candidate_id'] for e in self.store.records(task.id,'event') if 'selected_candidate_id' in e]
            if type(task_revision) is not int or task.revision!=task_revision:
                raise ValueError('Task revision changed; refresh before review')
            if task.status!='REVIEW_PENDING' or not selected or selected[-1]!=candidate_id:
                raise ValueError('Candidate is not current review selection')
            review=ReviewRecord(id=uid(),task_id=task.id,candidate_id=c.id,spec_hash=task.spec_hash,
                verification_plan_hash=task.verification_plan_hash,check_set_hash=check_hash,
                decision='REJECT',actor_id=actor_id,reason=reason)
            previous=task.status
            task.status='REJECTED';task.revision+=1
            db.execute('UPDATE tasks SET payload=? WHERE id=?',(task.model_dump_json(),task.id))
            self.record(db,review)
            self.store._append_event(db,task.id,dict(type='TASK_STATE_CHANGED',status=task.status,
                previous_status=previous,task_revision=task.revision))
        return review

    def cancel(self, task_id, task_revision, *, actor_id):
        self.actor(actor_id)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload FROM tasks WHERE id=?',(task_id,)).fetchone()
            if not row:raise ValueError('Unknown task')
            task=self.store._decode_task(row[0])
            if type(task_revision) is not int or task.revision!=task_revision:
                raise ValueError('Task revision changed; refresh before cancellation')
            if task.status not in ('READY','DIAGNOSING','GENERATING','APPLYING','BUILDING','TESTING','REVIEW_PENDING','EXPORTING'):
                raise ValueError('Task cannot be cancelled in its current state')
            calls={r['id']:r for r in self.store.records(task_id,'model_call')}
            unknown=any(r['status']=='STARTED' and calls.get(r['id']+'-result',{}).get('status') not in ('SUCCEEDED','FAILED') for r in calls.values())
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tool_requests'").fetchone():
                unknown=unknown or bool(db.execute("SELECT 1 FROM tool_requests WHERE task_id=? AND state='STARTED'",(task_id,)).fetchone())
            previous=task.status
            task.status='CANCELLED';task.revision+=1
            db.execute('UPDATE tasks SET payload=? WHERE id=?',(task.model_dump_json(),task.id))
            result=dict(type='USER_CANCELLED',status=task.status,previous_status=previous,
                task_revision=task.revision,actor_id=actor_id,in_flight_unknown=unknown,
                operation_status='IN_DOUBT' if unknown else 'OK',
                message='Future steps stopped; in-flight effects and incurred costs are not reversed')
            self.store._append_event(db,task.id,result)
        return result
