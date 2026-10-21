"""Snapshot actual task evidence separately from the accepted project tree."""
import hashlib
import json
from pathlib import Path

from nexus.contracts import CheckResult, source_manifest
from nexus.requirements.review import assess_requirements
from nexus.requirements.service import RequirementService


class EvidenceArchive:
    def __init__(self, store):
        self.store=store

    @staticmethod
    def json_bytes(value):
        return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2).encode()

    def files(self, candidate, source, acceptance, export_id):
        task=self.store.get_task(candidate.task_id)
        spec,plan=RequirementService(self.store).task_context(task)
        manifest=source_manifest(source)
        files={'project/'+name:(source/name).read_bytes() for name in manifest}
        if spec.project_id.startswith('upload_'):
            from nexus.uploads.service import UploadService
            uploaded=UploadService(self.store)._read(spec.project_id)
            files['evidence/upload.json']=self.json_bytes(dict(schema_version=1,filename=uploaded['filename'],
                source_sha256=uploaded['source_sha256'],confirmation_hash=uploaded['confirmation_hash'],
                source_prefix=uploaded.get('source_prefix',''),function=uploaded['function'],examples=uploaded['examples'],notice='Only user-confirmed examples are verified.'))
            files['evidence/upload-original.cj']=(self.store.root/'uploads'/spec.project_id/'source.cj').read_bytes()
        analysis=[e for e in self.store.records(task.id,'event') if e['type']=='ANALYSIS_CONTEXT']
        if analysis:
            from nexus.analysis.repair import verify_evidence
            files['evidence/analysis.json']=self.json_bytes(dict(schema_version=1,
                contexts=[verify_evidence(self.store,event) for event in analysis],
                model_citations=[dict(model_call_id=e['model_call_id'],analysis_refs=e.get('analysis_refs',[]),
                    analysis_context_hash=e.get('analysis_context_hash')) for e in self.store.records(task.id,'event')
                    if e['type']=='MODEL_SUGGESTION']))
        impacts=[e for e in self.store.records(task.id,'event') if e['type']=='IMPACT_ANALYSIS']
        if impacts:
            from nexus.analysis.impact import verify_impact_event
            reports=[verify_impact_event(self.store,event) for event in impacts]
            files['evidence/impact.json']=self.json_bytes(dict(schema_version=1,accepted_candidate_id=candidate.id,
                reports=reports,notice='Reports identify their own candidate versions; static observations are not correctness proof.'))
        if any(hashlib.sha256(files['project/'+name]).hexdigest()!=identity for name,identity in manifest.items()):
            raise ValueError('Project changed during evidence snapshot')
        refs=set()
        with self.store.connect() as db:
            refs.update(row[0] for row in db.execute('SELECT ref FROM records WHERE task_id=?',(task.id,)))
            operations=[dict(zip(('request_id','tool','state','request_ref','result_ref'),row)) for row in db.execute(
                'SELECT request_id,tool,state,request_ref,result_ref FROM tool_requests WHERE task_id=? ORDER BY rowid',(task.id,))] if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='tool_requests'").fetchone() else []
        for operation in operations:
            refs.add(operation['request_ref'])
            if operation['result_ref']:refs.add(operation['result_ref'])
        native=[]
        def collect(value):
            if isinstance(value,dict):
                for key,child in value.items():
                    if key.endswith('_ref') and isinstance(child,str) and child.startswith('records/'):
                        refs.add(child)
                    elif key=='record_refs' and isinstance(child,list):
                        refs.update(ref for ref in child if isinstance(ref,str) and ref.startswith('records/'))
                    else:collect(child)
            elif isinstance(value,list):
                for child in value:collect(child)
        copied=set()
        while refs-copied:
            ref=sorted(refs-copied)[0]
            path=Path(ref)
            if path.is_absolute() or '..' in path.parts or path.parts[0]!='records':
                raise ValueError('Invalid native evidence reference')
            actual=self.store.root/path
            if actual.is_symlink():raise ValueError('Symlink evidence is forbidden')
            content=actual.read_bytes()  # Missing originals stop export; no replacement summaries.
            archive_path='evidence/native/'+ref
            files[archive_path]=content
            native.append(dict(runtime_ref=ref,archive_path=archive_path,sha256=hashlib.sha256(content).hexdigest()))
            copied.add(ref)
            # Analysis originals contain untrusted remote JSON. Only their
            # trusted task index supplies references; remote fields cannot add
            # unrelated local records to the archive.
            if path.suffix=='.json' and '.analysis.' not in path.name:collect(json.loads(content))
        checks=[r for r in self.store.records(task.id,'check') if r['subject_id']==candidate.id]
        test=next(r for r in reversed(checks) if r['kind']=='test')
        results=assess_requirements(spec,plan,CheckResult.model_validate(test),build_state='PASS')
        files['evidence/changes.diff']=(self.store.root/candidate.diff_ref).read_bytes()
        files['evidence/verification.json']=self.json_bytes(dict(schema_version=1,checks=checks,
            check_set_hash=acceptance.check_set_hash,limitations=plan.limitations))
        files['evidence/requirements.json']=self.json_bytes(dict(schema_version=1,spec=spec.model_dump(),
            verification_plan=plan.model_dump(),requirement_results=results))
        calls=self.store.records(task.id,'model_call')
        files['evidence/sessions.json']=self.json_bytes(dict(schema_version=1,
            capture_phase='EXPORT_RESERVED_BEFORE_COMPLETION',collection='Original local persisted records copied byte-for-byte',
            model_calls=calls,model_evidence='RECORDED' if calls else 'NO_MODEL_CALL_RECORDED',
            native_records=native,mcp_operations=operations,
            limitations=['Current export completion and final archive hash are recorded externally after publication',
                          'No model call is inferred from hand-written candidates or SDK tests']))
        files['evidence/acceptance.json']=self.json_bytes(dict(schema_version=1,acceptance=acceptance.model_dump(),
            reviews=self.store.records(task.id,'review'),export_id=export_id,consumption_state='RESERVED'))
        files['README.md']=('''# CangSight-Nexus verified project

Run `cjpm build -V` and `cjpm test` from `project/` with the pinned Cangjie 1.0.5 toolchain.
`evidence/` contains original records and their indexes. No SDK, credentials, Git metadata,
or generated target directory is included. Project and archive identities are separate.
The manifest uses SHA256 of file bytes and excludes its own hash. The final ZIP hash is
stored in the external export receipt. This snapshot predates the export completion record.
Passing frozen tests supports only the registered order-case requirements; it does not prove
arbitrary program correctness. See evidence/requirements.json for untested behavior.
''').encode()
        outer=dict(schema_version=1,project_tree_hash=candidate.tree_hash,project_files=manifest,
            task_id=task.id,candidate_id=candidate.id,spec_hash=spec.spec_hash,verification_plan_hash=plan.plan_hash,
            export_id=export_id,algorithm='SHA256 file bytes; sorted canonical project map',
            source_mode_profile='files 0644, source directories 0755; checked separately from content digest',
            excluded=['target/','.git/','.env','SDK/runtime binaries'],
            files={name:hashlib.sha256(content).hexdigest() for name,content in sorted(files.items())})
        files['manifest.json']=self.json_bytes(outer)
        return files
