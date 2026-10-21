"""Frozen registered projects; paths never come from model-selected host roots."""
import difflib
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import uuid

from nexus.contracts import CandidateProposal, CandidateRecord, TaskRecord, file_hash, source_manifest, tree_hash
from nexus.store import RunStore


class WorkspaceStore:
    @staticmethod
    def source_modes(path: Path, *, normalize=False):
        # Registered material contains data/source files, never executable scripts.
        files=source_manifest(path)
        directories={path}
        for name in files:
            current=path/name
            directories.update(parent for parent in current.parents if parent==path or path in parent.parents)
            if normalize:current.chmod(0o644)
            elif stat.S_IMODE(current.stat().st_mode)!=0o644:
                raise ValueError('Source file permissions changed')
        for directory in directories:
            if normalize:directory.chmod(0o755)
            elif stat.S_IMODE(directory.stat().st_mode)!=0o755:
                raise ValueError('Source directory permissions changed')

    def __init__(self, root: Path, registered: list[Path] | None = None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.registered = [p.resolve() for p in (registered or [])]
        (self.root / 'baselines').mkdir(exist_ok=True)
        (self.root / 'candidates').mkdir(exist_ok=True)

    def import_project(self, source: Path, build_root: str) -> str:
        source = source.resolve()
        if source not in self.registered:
            raise ValueError('project is not registered')
        source_manifest(source)  # rejects symlinks before traversal/copy
        roots = sorted(p.parent for p in source.rglob('cjpm.toml') if 'target' not in p.relative_to(source).parts)
        if not build_root:
            if len(roots) != 1:
                raise ValueError('explicit build root required')
            selected = roots[0]
        else:
            relative = PurePosixPath(build_root)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('invalid build root')
            selected = source / build_root
            if selected not in roots:
                raise ValueError('unknown build root')
        manifest = source_manifest(selected)
        if not manifest or len(manifest) > 100 or sum((selected / p).stat().st_size for p in manifest) > 2*1024*1024:
            raise ValueError('project exceeds supported size')
        if any(Path(p).name.startswith('.') or Path(p).suffix not in ('.cj', '.toml', '.md', '.lock') for p in manifest):
            raise ValueError('unregistered project material')
        if any(Path(p).name == 'build.cj' for p in manifest):
            raise ValueError('build scripts are not allowed')
        baseline_id = 'b_' + uuid.uuid4().hex
        destination = self.root / 'baselines' / baseline_id
        destination.mkdir()
        try:
            for name in manifest:
                target = destination / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(selected / name, target)
            self.source_modes(destination,normalize=True)
            if source_manifest(destination) != manifest:
                raise ValueError('source changed during import')
            (self.root / 'baselines' / f'{baseline_id}.json').write_text(json.dumps({'tree_hash': tree_hash(destination), 'build_root': '.'}))
        except Exception:
            shutil.rmtree(destination)
            raise
        return baseline_id

    def subject_path(self, subject_id: str) -> Path:
        if not subject_id.startswith(('b_', 'c_')) or len(subject_id) != 34 or not all(c in '0123456789abcdef' for c in subject_id[2:]):
            raise ValueError('unknown subject')
        path = self.root / ('baselines' if subject_id.startswith('b_') else 'candidates') / subject_id
        if not path.is_dir() or path.is_symlink():
            raise ValueError('unknown subject')
        return path

    def verify_baseline(self, baseline_id: str) -> Path:
        path = self.subject_path(baseline_id)
        meta = json.loads((path.parent / f'{baseline_id}.json').read_text())
        self.source_modes(path)
        if tree_hash(path) != meta['tree_hash']:
            raise ValueError('baseline changed')
        return path

    def safe_file(self, baseline_id: str, name: str) -> Path:
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or rel.as_posix() != name or '\\' in name:
            raise ValueError('invalid source path')
        root = self.verify_baseline(baseline_id)
        path = root / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 131072:
            raise ValueError('file unavailable or too large')
        return path

    def read_file(self, baseline_id: str, path: str) -> str:
        return self.safe_file(baseline_id, path).read_bytes().decode('utf-8')


    def candidate(self, candidate_id: str) -> CandidateRecord:
        path = self.subject_path(candidate_id)
        if not candidate_id.startswith('c_'):
            raise ValueError('candidate required')
        record = CandidateRecord.model_validate_json((path.parent / f'{candidate_id}.json').read_text())
        self.source_modes(path)
        if tree_hash(path) != record.tree_hash:
            raise ValueError('candidate changed')
        if record.schema_version == 2:
            from nexus.requirements.service import RequirementService
            task = RunStore(self.root).get_task(record.task_id)
            RequirementService(RunStore(self.root)).task_context(task)
            if record.spec_hash!=task.spec_hash or record.verification_plan_hash!=task.verification_plan_hash:
                raise ValueError('Candidate requirement binding changed')
        return record

    def apply_candidate(self, task: TaskRecord, proposal: CandidateProposal) -> CandidateRecord:
        store = RunStore(self.root)
        current = store.get_task(task.id)
        if current.status not in ('READY','APPLYING'):
            raise ValueError('task does not allow candidate materialization')
        if current.baseline_id != task.baseline_id or current.attempt_count >= 3:
            raise ValueError('candidate budget exceeded or mismatched task')
        proposal = CandidateProposal.model_validate(proposal.model_dump())
        if current.schema_version == 2:
            from nexus.requirements.service import RequirementService
            spec, _ = RequirementService(store).task_context(current)
            refs = proposal.requirement_refs
            if len(refs)!=len(set(refs)) or not set(refs)<={r.id for r in spec.requirements}:
                raise ValueError('Unknown or duplicate requirement references')
        baseline = self.verify_baseline(current.baseline_id)
        manifest = source_manifest(baseline)
        for edit in proposal.edits:
            if edit.path not in current.allowed_paths or edit.path not in manifest:
                raise ValueError('protected or missing path')
            if file_hash(self.read_file(current.baseline_id, edit.path)) != edit.before_hash:
                raise ValueError('before_hash mismatch')
        if current.schema_version == 2 and spec.project_id.startswith('upload_'):
            from nexus.uploads.language import inspect_source,validate_candidate
            original=inspect_source(self.read_file(current.baseline_id,'src/uploaded.cj'))
            for edit in proposal.edits:validate_candidate(edit.content,original)
        candidate_id = 'c_' + uuid.uuid4().hex
        staging = self.root / 'candidates' / ('.staging-' + candidate_id)
        destination = staging.parent / candidate_id
        metadata = staging.parent / f'{candidate_id}.json'
        try:
            shutil.copytree(baseline, staging)
            for edit in proposal.edits:
                (staging / edit.path).write_text(edit.content)
            identity = tree_hash(staging)
            if identity == tree_hash(baseline) or any(c['tree_hash'] == identity for c in store.records(task.id, 'candidate')):
                raise ValueError('duplicate or unchanged candidate')
            diff = self._diff(baseline, staging)
            diff_ref = f'records/{candidate_id}.diff'
            record = CandidateRecord(schema_version=current.schema_version, spec_hash=current.spec_hash,
                                     verification_plan_hash=current.verification_plan_hash,
                                     model_call_id=next((r['id'] for r in reversed(store.records(task.id,'model_call')) if r['status']=='SUCCEEDED'),None),
                                     id=candidate_id, task_id=task.id, baseline_hash=tree_hash(baseline),
                                     edits=proposal.edits, tree_hash=identity, diff_ref=diff_ref,
                                     attempt=current.attempt_count+1)
            (self.root / diff_ref).write_text(diff)
            staging.rename(destination)
            metadata.write_text(record.model_dump_json())
            store.append_record(task.id, 'candidate', record.model_dump())
            store.update_task(task.id, attempt_count=record.attempt)
            return record
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            shutil.rmtree(destination, ignore_errors=True)
            metadata.unlink(missing_ok=True)
            (self.root / f'records/{candidate_id}.diff').unlink(missing_ok=True)
            raise

    @staticmethod
    def _diff(baseline: Path, candidate: Path) -> str:
        pieces = []
        for name in source_manifest(baseline):
            before = (baseline / name).read_text().splitlines(keepends=True)
            after = (candidate / name).read_text().splitlines(keepends=True)
            pieces.extend(difflib.unified_diff(before, after, fromfile='a/'+name, tofile='b/'+name))
        return ''.join(pieces)

    def diff(self, candidate_id: str) -> str:
        record = self.candidate(candidate_id)
        task = RunStore(self.root).get_task(record.task_id)
        return self._diff(self.verify_baseline(task.baseline_id), self.subject_path(candidate_id))
