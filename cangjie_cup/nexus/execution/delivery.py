"""User acceptance and transactional, content-bound export reservation."""
import hashlib
import json
from pathlib import Path
import time
import zipfile

from nexus.adapters.cangjie.report_parser import parse_test_report, project_suites
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.contracts import AcceptanceRecord, CheckResult, ReviewRecord, digest, source_manifest, tree_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.store import RunStore, uid


class DeliveryService:
    def __init__(self, store: RunStore):
        self.store = store
        self.ws = WorkspaceStore(store.root)
        (store.root/'exports').mkdir(exist_ok=True)
        with store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS acceptances(
                id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL, payload TEXT NOT NULL,
                export_id TEXT UNIQUE, status TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS export_artifacts(
                export_id TEXT PRIMARY KEY, archive_hash TEXT NOT NULL, manifest_hash TEXT NOT NULL)''')

    def check_set_hash(self, candidate_id: str) -> str:
        c = self.ws.candidate(candidate_id)
        verifier = CangjieVerifier(self.store.root, c.task_id)
        _, identity, plan = verifier.identity(candidate_id)
        task = self.store.get_task(c.task_id)
        scoped=verifier._scoped_context(task,candidate_id)
        binding = None
        if task.schema_version==2:
            from nexus.requirements.service import RequirementService
            binding = RequirementService(self.store).task_context(task)
        checks = self.store.records(c.task_id, 'check')
        selected = []
        for kind in ('build','test'):
            matching = [r for r in checks if r['subject_id']==candidate_id and r['tree_hash']==identity
                        and r['plan_hash']==plan and r['kind']==kind]
            if not matching:
                raise ValueError('required check missing')
            check = matching[-1]
            if check['state'] != 'PASS' or check['exit_code'] != 0:
                raise ValueError('required check not PASS')
            if binding and (check.get('schema_version')!=2 or check.get('spec_hash')!=task.spec_hash or
                    check.get('verification_plan_hash')!=task.verification_plan_hash):
                raise ValueError('Check requirement binding changed')
            if scoped is not None:
                from nexus.repair.package_evidence import checked_record
                rebuilt=checked_record(self.store,check,context=scoped,plan=binding[1] if binding else None)
                if rebuilt['state']!='PASS':raise ValueError('Scoped原件或完整XML验证变化，禁止交付')
            elif check.get('package_evidence') is not None:
                raise ValueError('Scoped证据缺少所属冻结工程')
            ref = Path(check['log_ref'])
            if ref.is_absolute() or '..' in ref.parts or ref.parts[0] != 'records':
                raise ValueError('invalid log reference')
            text = (self.store.root/ref).read_bytes().decode('utf-8') if scoped is not None else (self.store.root/ref).read_text()
            report_ref = check.get('report_ref')
            if binding and not report_ref:
                raise ValueError('Required check report missing')
            if report_ref:
                report_path = Path(report_ref)
                if report_path.is_absolute() or '..' in report_path.parts or report_path.parts[0]!='records':
                    raise ValueError('Invalid report reference')
                if json.loads((self.store.root/report_path).read_text())!=check:
                    raise ValueError('Check report content changed')
            if kind=='test':
                parsed = CheckResult.model_validate(check) if scoped is not None else parse_test_report(text)
                if parsed.state!='PASS' or parsed.counts!=check['counts']:
                    raise ValueError('test evidence inconsistent')
                if binding:
                    spec, frozen = binding
                    suites = project_suites(parsed,frozen.suite_tests)
                    if parsed.case_results!=check.get('case_results') or suites!=check.get('suite_results'):
                        raise ValueError('Frozen test suite evidence inconsistent')
                    from nexus.requirements.review import assess_requirements
                    reviewed = CheckResult.model_validate({**check,'suite_results':suites})
                    if any(r['status']!='SATISFIED_BY_TESTS' for r in assess_requirements(spec,frozen,reviewed,build_state='PASS')):
                        raise ValueError('Required behavior is unknown or not satisfied')
            elif 'cjpm build success' not in text:
                raise ValueError('build evidence inconsistent')
            selected.append({'check':check,'log_hash':hashlib.sha256(text.encode()).hexdigest()})
        from nexus.repair.exploration import ExplorationService
        exploration=ExplorationService(self.store).verify(candidate_id)
        if exploration is not None:
            if exploration['state']!='PASS':raise ValueError('独立规则验证尚未通过')
            selected.append({'independent_exploration':exploration})
        from nexus.repair.property_service import PropertyService
        properties=PropertyService(self.store).verify(candidate_id)
        if properties is not None:
            if properties['state']!='PASS':raise ValueError('业务属性验证尚未通过')
            selected.append({'business_properties':properties})
        from nexus.repair.relation_service import RelationService
        relations=RelationService(self.store).verify(candidate_id)
        if relations is not None:
            if relations['state']!='PASS':raise ValueError('业务关系验证尚未通过')
            selected.append({'business_relations':relations})
        from nexus.repair.sequence_service import SequenceService
        sequences=SequenceService(self.store).verify(candidate_id)
        if sequences is not None:
            if sequences['state']!='PASS':raise ValueError('状态序列验证尚未通过')
            selected.append({'business_sequences':sequences})
        from nexus.repair.focus_service import FocusService
        focus=FocusService(self.store)
        for event in self.store.records(task.id,'event'):
            if event['type']=='LOCALIZATION_CONTEXT':selected.append({'localization':focus.verify(task.id,event)})
        return digest(selected)

    def accept(self, candidate_id: str, check_set_hash: str, *, actor_id=None, task_revision=None) -> AcceptanceRecord:
        from nexus.execution.review import ReviewService
        review_service=ReviewService(self.store)
        c=self.ws.candidate(candidate_id)
        task=self.store.get_task(c.task_id)
        if task.schema_version==2 and actor_id is None:
            raise ValueError('V1.1 approval requires a trusted user identity')
        actor_id=actor_id or 'local-service'
        review_service.actor(actor_id)
        if self.check_set_hash(candidate_id)!=check_set_hash:
            raise ValueError('check set changed')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            task=self.store._decode_task(db.execute('SELECT payload FROM tasks WHERE id=?',(c.task_id,)).fetchone()[0])
            selected=[e['selected_candidate_id'] for e in self.store.records(task.id,'event') if 'selected_candidate_id' in e]
            if task.status!='REVIEW_PENDING' or not selected or selected[-1]!=candidate_id:
                raise ValueError('candidate is not current review selection')
            if task_revision is not None and (type(task_revision) is not int or task_revision!=task.revision):
                raise ValueError('Task revision changed; refresh before review')
            rows=db.execute('SELECT payload FROM acceptances WHERE candidate_id=? ORDER BY rowid DESC',(candidate_id,)).fetchall()
            if rows:
                previous=AcceptanceRecord.model_validate_json(rows[0][0])
                if (previous.tree_hash==c.tree_hash and previous.check_set_hash==check_set_hash and
                        previous.expires_at>time.time() and previous.actor_id==actor_id):
                    return previous
            results=[]
            if task.schema_version==2:
                from nexus.requirements.service import RequirementService
                from nexus.requirements.review import assess_requirements
                spec,plan=RequirementService(self.store).task_context(task)
                tests=[r for r in self.store.records(task.id,'check') if r['subject_id']==candidate_id and r['kind']=='test']
                results=assess_requirements(spec,plan,CheckResult.model_validate(tests[-1]),build_state='PASS')
            review=ReviewRecord(id=uid(),task_id=task.id,candidate_id=c.id,spec_hash=task.spec_hash,
                verification_plan_hash=task.verification_plan_hash,check_set_hash=check_set_hash,
                decision='ACCEPT',actor_id=actor_id,requirement_results=results)
            acceptance=AcceptanceRecord(schema_version=2 if task.schema_version==2 else 1,id=uid(),
                task_id=task.id,candidate_id=c.id,tree_hash=c.tree_hash,check_set_hash=check_set_hash,
                spec_hash=task.spec_hash,verification_plan_hash=task.verification_plan_hash,
                actor_id=actor_id,review_id=review.id,expires_at=time.time()+1800)
            review_service.record(db,review)
            db.execute('INSERT INTO acceptances VALUES (?,?,?,NULL,?)',
                (acceptance.id,candidate_id,acceptance.model_dump_json(),'ACCEPTED'))
            ref=f'records/{acceptance.id}.json'
            with (self.store.root/ref).open('x') as stream:stream.write(acceptance.model_dump_json())
            db.execute('INSERT INTO records VALUES (?,?,?,?,?,?)',
                (acceptance.id,task.id,'acceptance',acceptance.id,None,ref))
        return acceptance

    def acceptance(self, candidate_id, acceptance_id, *, actor_id=None):
        with self.store.connect() as db:
            row = db.execute('SELECT payload, export_id, status FROM acceptances WHERE id=? AND candidate_id=?', (acceptance_id,candidate_id)).fetchone()
        if not row:
            raise ValueError('acceptance missing')
        a = AcceptanceRecord.model_validate_json(row[0])
        c = self.ws.candidate(candidate_id)
        task = self.store.get_task(c.task_id)
        if actor_id is not None and a.actor_id!=actor_id:
            raise ValueError('Approval belongs to another local session')
        if task.schema_version==2:
            if (a.schema_version!=2 or a.task_id!=task.id or a.spec_hash!=task.spec_hash or
                    a.verification_plan_hash!=task.verification_plan_hash or a.allowed_action!='candidate.export'):
                raise ValueError('Approval requirement or action binding changed')
            saved=[r for r in self.store.records(task.id,'acceptance') if r['id']==a.id]
            reviews=[r for r in self.store.records(task.id,'review') if r['id']==a.review_id]
            if saved!=[a.model_dump()] or len(reviews)!=1:
                raise ValueError('Approval native record missing or changed')
            review=ReviewRecord.model_validate(reviews[0])
            if (review.decision!='ACCEPT' or review.candidate_id!=c.id or review.actor_id!=a.actor_id or
                    review.check_set_hash!=a.check_set_hash or review.spec_hash!=a.spec_hash or
                    review.verification_plan_hash!=a.verification_plan_hash):
                raise ValueError('User review binding changed')
        selected = [e['selected_candidate_id'] for e in self.store.records(task.id,'event') if 'selected_candidate_id' in e]
        if task.status not in ('REVIEW_PENDING','EXPORTING','DELIVERED') or not selected or selected[-1]!=candidate_id:
            raise ValueError('acceptance no longer matches current selection')
        if a.expires_at < time.time() or c.tree_hash != a.tree_hash or self.check_set_hash(candidate_id)!=a.check_set_hash:
            raise ValueError('acceptance expired or evidence changed')
        return a, row[1], row[2]

    def _package(self, candidate_id, export_id):
        c = self.ws.candidate(candidate_id)
        source = self.ws.subject_path(candidate_id)
        manifest = source_manifest(source)
        target = self.store.root/'exports'/f'{export_id}.zip'
        temporary = target.with_suffix('.tmp')
        try:
            if self.store.get_task(c.task_id).schema_version==2:
                from nexus.execution.archive import EvidenceArchive
                with self.store.connect() as db:
                    row=db.execute('SELECT payload FROM acceptances WHERE export_id=?',(export_id,)).fetchone()
                if not row:raise ValueError('Export reservation missing')
                acceptance=AcceptanceRecord.model_validate_json(row[0])
                files=EvidenceArchive(self.store).files(c,source,acceptance,export_id)
                with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
                    for name,content in files.items():
                        info=zipfile.ZipInfo(name)
                        info.create_system=3
                        info.external_attr=0o100644<<16
                        archive.writestr(info,content,compress_type=zipfile.ZIP_DEFLATED)
                if tree_hash(source)!=c.tree_hash:raise ValueError('Project changed during export')
                temporary.replace(target)
                return target.relative_to(self.store.root).as_posix()
            with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
                for name, identity in manifest.items():
                    content = (source/name).read_bytes()
                    if hashlib.sha256(content).hexdigest()!=identity:
                        raise ValueError('candidate changed during export')
                    archive.writestr(name,content)
                archive.writestr('CANGSIGHT-MANIFEST.json',json.dumps({'tree_hash':c.tree_hash,'files':manifest},sort_keys=True))
            with zipfile.ZipFile(temporary) as archive:
                actual = {name:hashlib.sha256(archive.read(name)).hexdigest() for name in manifest}
                if actual != manifest or tree_hash(source)!=c.tree_hash:
                    raise ValueError('export manifest mismatch')
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return target.relative_to(self.store.root).as_posix()

    def verify_archive(self, export_id: str, acceptance: AcceptanceRecord, *, require_receipt=True) -> Path:
        target = self.store.root/'exports'/f'{export_id}.zip'
        with zipfile.ZipFile(target) as archive:
            if acceptance.schema_version==2:
                manifest=json.loads(archive.read('manifest.json'))
                files=manifest['files']
                if (manifest['schema_version']!=1 or manifest['export_id']!=export_id or
                        manifest['candidate_id']!=acceptance.candidate_id or
                        manifest['spec_hash']!=acceptance.spec_hash or
                        manifest['verification_plan_hash']!=acceptance.verification_plan_hash or
                        manifest['project_tree_hash']!=acceptance.tree_hash or digest(manifest['project_files'])!=acceptance.tree_hash):
                    raise ValueError('Archive approval binding changed')
                if set(archive.namelist())!=set(files)|{'manifest.json'} or len(archive.namelist())!=len(files)+1:
                    raise ValueError('Unexpected archive entries')
                project={name.removeprefix('project/'):identity for name,identity in files.items() if name.startswith('project/')}
                if any((archive.getinfo(name).external_attr>>16)&0o777!=0o644 for name in files if name.startswith('project/')):
                    raise ValueError('Archive project permissions changed')
                if project!=manifest['project_files'] or any(hashlib.sha256(archive.read(name)).hexdigest()!=identity for name,identity in files.items()):
                    raise ValueError('Archive contents changed')
                if require_receipt:
                    with self.store.connect() as db:
                        receipt=db.execute('SELECT archive_hash,manifest_hash FROM export_artifacts WHERE export_id=?',(export_id,)).fetchone()
                    actual=(hashlib.sha256(target.read_bytes()).hexdigest(),hashlib.sha256(archive.read('manifest.json')).hexdigest())
                    if not receipt or tuple(receipt)!=actual:
                        raise ValueError('Archive external receipt missing or changed')
                return target
            manifest = json.loads(archive.read('CANGSIGHT-MANIFEST.json'))
            files = manifest['files']
            if manifest['tree_hash'] != acceptance.tree_hash or digest(files) != acceptance.tree_hash:
                raise ValueError('archive identity mismatch')
            if set(archive.namelist()) != set(files)|{'CANGSIGHT-MANIFEST.json'} or len(archive.namelist()) != len(files)+1:
                raise ValueError('unexpected archive entries')
            if any(hashlib.sha256(archive.read(name)).hexdigest()!=identity for name,identity in files.items()):
                raise ValueError('archive contents changed')
        return target

    def export(self, candidate_id: str, acceptance_id: str) -> dict[str, object]:
        acceptance, _, _ = self.acceptance(candidate_id,acceptance_id)
        from nexus.policy.state import prepare_update
        candidate=self.ws.candidate(candidate_id)
        snapshot=self.store.get_task(candidate.task_id)
        reservation=prepare_update(snapshot,status='EXPORTING') if snapshot.status=='REVIEW_PENDING' else None
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT export_id,status FROM acceptances WHERE id=?', (acceptance_id,)).fetchone()
            if row[1]=='IN_DOUBT':
                raise ValueError('Export outcome unknown; manual reconciliation required')
            export_id = row[0] or uid()
            if row[1] in ('EXPORTING','DELIVERED'):
                result = dict(export_id=export_id,status=row[1],tree_hash=acceptance.tree_hash)
                if row[1]=='DELIVERED':
                    self.verify_archive(export_id,acceptance)
                    result['download_ref']=f'exports/{export_id}.zip'
                return result
            candidate=self.ws.candidate(candidate_id)
            task=self.store._decode_task(db.execute('SELECT payload FROM tasks WHERE id=?',(candidate.task_id,)).fetchone()[0])
            if task.status!='REVIEW_PENDING':
                raise ValueError('Task stopped before export reservation')
            db.execute('UPDATE acceptances SET export_id=?,status=? WHERE id=?', (export_id,'EXPORTING',acceptance_id))
            if reservation is None or not self.store._commit_task(db,snapshot,*reservation,export_id=export_id):
                raise ValueError('Task changed before export reservation')
        try:
            # Reconcile a previous reserved/failed export by revalidating and repackaging the same ID.
            self.acceptance(candidate_id,acceptance_id)
            ref = self._package(candidate_id,export_id)
            self.acceptance(candidate_id,acceptance_id)
            target=self.verify_archive(export_id,acceptance,require_receipt=False)
            archive_hash=hashlib.sha256(target.read_bytes()).hexdigest()
            with zipfile.ZipFile(target) as archive:
                manifest_hash=hashlib.sha256(archive.read('manifest.json' if acceptance.schema_version==2 else 'CANGSIGHT-MANIFEST.json')).hexdigest()
            publication_snapshot=self.store.get_task(candidate.task_id)
            if publication_snapshot.model_dump()!=reservation[0].model_dump():raise ValueError('Task changed during packaging')
            publication=prepare_update(publication_snapshot,status='DELIVERED')
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                task=self.store._decode_task(db.execute('SELECT payload FROM tasks WHERE id=?',(candidate.task_id,)).fetchone()[0])
                if task.status!='EXPORTING':
                    raise ValueError('Task stopped before export publication')
                # All checks here are local reads. The native process completed
                # before the transaction; approval/evidence may have changed
                # during that wait and must be current at publication.
                fresh,reserved_id,reserved_state=self.acceptance(candidate_id,acceptance_id)
                if (reserved_id!=export_id or reserved_state!='EXPORTING' or
                        fresh.model_dump()!=acceptance.model_dump() or fresh.expires_at<=time.time()):
                    raise ValueError('Approval changed before export publication')
                db.execute('UPDATE acceptances SET status=? WHERE id=? AND export_id=?', ('DELIVERED',acceptance_id,export_id))
                db.execute('INSERT INTO export_artifacts VALUES (?,?,?)',(export_id,archive_hash,manifest_hash))
                if not self.store._commit_task(db,publication_snapshot,*publication,export_id=export_id):
                    raise ValueError('Task changed before export publication')
                if fresh.expires_at<=time.time():raise ValueError('Approval expired before export commit')
            return dict(export_id=export_id,status='DELIVERED',tree_hash=acceptance.tree_hash,download_ref=ref)
        except Exception:
            (self.store.root/'exports'/f'{export_id}.zip').unlink(missing_ok=True)
            with self.store.connect() as db:
                failed=db.execute('SELECT status FROM acceptances WHERE id=? AND export_id=?',(acceptance_id,export_id)).fetchone()
            current=self.store.get_task(candidate.task_id)
            if current.status=='EXPORTING':
                self.store.update_task(candidate.task_id,expected_status='EXPORTING',expected_revision=current.revision,
                    status='IN_DOUBT' if failed and failed[0]=='IN_DOUBT' else 'REVIEW_PENDING')
            with self.store.connect() as db:
                db.execute('UPDATE acceptances SET status=? WHERE id=? AND export_id=? AND status=?', ('FAILED',acceptance_id,export_id,'EXPORTING'))
            raise
