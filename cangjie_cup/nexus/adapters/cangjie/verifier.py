import uuid
import hashlib
import time
from pathlib import Path

from nexus.adapters.cangjie.report_parser import parse_test_report, project_suites
from nexus.adapters.cangjie.sdk import sdk_environment, SDK, MACOS_SDK
from nexus.contracts import CheckResult, digest, tree_hash
from nexus.execution.runner import run_command
from nexus.execution.workspace import WorkspaceStore
from nexus.store import RunStore


class CangjieVerifier:
    def __init__(self, root: Path, task_id: str, *, deadline_at: int | None = None):
        self.root = Path(root)
        self.task_id = task_id
        self.deadline_at = deadline_at
        self.store = RunStore(root)
        self.ws = WorkspaceStore(root)

    def _scoped_context(self,task,subject_id):
        from nexus.repair.package_evidence import subject_context
        return subject_context(self.store,task,subject_id)

    def identity(self, subject_id):
        task = self.store.get_task(self.task_id)
        if subject_id == task.baseline_id:
            path = self.ws.verify_baseline(subject_id)
        else:
            c = self.ws.candidate(subject_id)
            if c.task_id != task.id:
                raise ValueError('foreign candidate')
            path = self.ws.subject_path(subject_id)
        binaries = {'cjc':hashlib.sha256((SDK/'bin/cjc').read_bytes()).hexdigest(),
                    'cjpm':hashlib.sha256((SDK/'tools/bin/cjpm').read_bytes()).hexdigest()}
        from nexus.policy.core import NativeCoreClient
        try:policy_identity=NativeCoreClient().component_identity()
        except (ValueError,OSError):policy_identity=None
        requirement_binding = {}
        if task.schema_version == 2:
            from nexus.requirements.service import RequirementService
            spec, frozen = RequirementService(self.store).task_context(task)
            upload_binding={}
            if spec.project_id.startswith('upload_'):
                from nexus.uploads.service import UploadService
                from nexus.uploads import language
                UploadService(self.store).validate_subject(task,path)
                upload_binding={'upload_language':hashlib.sha256(Path(language.__file__).read_bytes()).hexdigest()}
            if frozen.toolchain_id != digest(binaries):
                raise ValueError('Frozen toolchain identity changed')
            requirement_binding = {'spec_hash':spec.spec_hash,'verification_plan_hash':frozen.plan_hash,
                                   **upload_binding}
        scope=self._scoped_context(task,subject_id)
        scoped_binding={}
        if scope is not None:
            from nexus.repair.package_evidence import component_identity
            from nexus.execution.package_validation import tool_identity
            scoped_binding=dict(scoped_components=component_identity(scope['index']),scoped_tools=tool_identity())
        plan = digest({'requirement_binding': requirement_binding, 'native_core':policy_identity,**scoped_binding,
            'test_plan': task.test_plan, 'sdkroot': str(MACOS_SDK),
            'compiler': binaries['cjc'], 'cjpm': binaries['cjpm'],
            'verifier': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'parser': hashlib.sha256((Path(__file__).parent/'report_parser.py').read_bytes()).hexdigest(),
            'runner': hashlib.sha256((Path(__file__).parents[2]/'execution/runner.py').read_bytes()).hexdigest()})
        return path, tree_hash(path), plan

    async def _run(self, subject_id: str, kind: str) -> CheckResult:
        if self.store.get_task(self.task_id).status in ('CANCELLED','REJECTED','BLOCKED','IN_DOUBT','UNREPAIRED','DELIVERED'):
            return CheckResult(subject_id=subject_id,kind=kind,state='UNKNOWN',diagnostics='TASK_STOPPED')
        try:
            path, identity, plan = self.identity(subject_id)
            from nexus.policy.core import NativeCoreClient
            NativeCoreClient().component_identity()
            sdk_environment()
            scoped=self._scoped_context(self.store.get_task(self.task_id),subject_id)
        except (ValueError, OSError) as exc:
            return CheckResult(subject_id=subject_id, kind=kind, state='UNKNOWN', diagnostics=str(exc))
        records = self.store.records(self.task_id, 'check')
        matching = [r for r in records if r['subject_id'] == subject_id and r['tree_hash'] == identity and r['plan_hash'] == plan]
        previous = [r for r in matching if r['kind'] == kind]
        if previous:
            if scoped is not None:
                from nexus.repair.package_evidence import checked_record
                rebuilt=checked_record(self.store,previous[-1],context=scoped,plan=scoped.get('plan'))
                if rebuilt['state']!=previous[-1]['state'] or rebuilt['state']=='UNKNOWN':
                    return CheckResult(subject_id=subject_id,kind=kind,state='UNKNOWN',tree_hash=identity,
                        plan_hash=plan,diagnostics='SCOPED_CACHE_INVALID: '+rebuilt['diagnostics'])
            return CheckResult.model_validate(previous[-1])
        if kind == 'test' and not any(r['kind'] == 'build' and r['state'] == 'PASS' for r in matching):
            return CheckResult(subject_id=subject_id, kind=kind, state='NOT_RUN', tree_hash=identity, plan_hash=plan)
        if kind=='test' and scoped is not None:
            from nexus.repair.package_evidence import checked_record
            builds=[r for r in matching if r['kind']=='build' and r['state']=='PASS']
            if checked_record(self.store,builds[-1],context=scoped,plan=scoped.get('plan'))['state']!='PASS':
                return CheckResult(subject_id=subject_id,kind=kind,state='UNKNOWN',tree_hash=identity,
                    plan_hash=plan,diagnostics='SCOPED_BUILD_EVIDENCE_INVALID')
        argv = ['cjpm', 'build', '-V'] if kind == 'build' else ['cjpm', 'test']
        started = time.monotonic()
        remaining=90.0 if self.deadline_at is None else min(90.0,(self.deadline_at-int(time.time()*1000))/1000)
        if remaining<=0:
            return CheckResult(subject_id=subject_id,kind=kind,state='UNKNOWN',diagnostics='REQUEST_DEADLINE_EXCEEDED')
        execution_argv=[]
        package_proof=None;log_raw=None;scoped_result=None
        if scoped is not None:
            code,log_raw,problem,execution_argv,scoped_result,package_proof=await self._execute_scoped(
                scoped,kind,deadline=time.monotonic()+remaining)
            log=log_raw.decode('utf-8',errors='replace')
        else:
            code, log, problem = await run_command(path, argv,timeout=remaining,private_root=self.root,
                execution_argv=execution_argv)
        duration_ms = round((time.monotonic()-started)*1000)
        result = scoped_result or CheckResult(kind=kind, state='UNKNOWN')
        if problem is None:
            if kind == 'test' and scoped is None:
                result = parse_test_report(log)
                if result.state == 'PASS' and code != 0:
                    result.state = 'UNKNOWN'
            elif kind=='build':
                if code == 0 and 'cjpm build success' in log:
                    result.state = 'PASS'
                elif code is not None and code > 0 and 'error generated' in log and '.cj:' in log:
                    result.state = 'FAIL'
        try:
            _, after, after_plan = self.identity(subject_id)
            if after != identity or scoped is not None and after_plan!=plan:
                result.state = 'UNKNOWN'
                problem = 'SOURCE_CHANGED'
        except (ValueError, OSError):
            result.state = 'UNKNOWN'
            problem = 'SOURCE_CHANGED'
        if any(term in log for term in ('Operation not permitted', 'Permission denied', 'incompatible with arm64', 'command not found', 'No such file or directory', 'sandbox-exec:', 'sandbox blocked', 'Library not loaded:')):
            result.state = 'UNKNOWN'
        task = self.store.get_task(self.task_id)
        limitations = []
        if task.schema_version == 2:
            from nexus.requirements.service import RequirementService
            _, frozen = RequirementService(self.store).task_context(task)
            limitations = frozen.limitations
            if kind == 'test':
                result.suite_results = project_suites(result,frozen.suite_tests)
                if any(r['state']=='UNKNOWN' for r in result.suite_results.values()):
                    result.state = 'UNKNOWN'
        check_id = uuid.uuid4().hex
        ref = f'records/{check_id}.log'
        (self.root / ref).write_bytes(log_raw if log_raw is not None else log.encode())
        result = CheckResult(schema_version=task.schema_version, argv=argv, execution_argv=execution_argv, working_root='.',
            toolchain_hash=digest({'cjc':hashlib.sha256((SDK/'bin/cjc').read_bytes()).hexdigest(),
                                   'cjpm':hashlib.sha256((SDK/'tools/bin/cjpm').read_bytes()).hexdigest()}),
            duration_ms=duration_ms, report_ref=f'records/{check_id}.report.json',
            case_results=result.case_results, suite_results=result.suite_results, limitations=limitations,
            spec_hash=task.spec_hash, verification_plan_hash=task.verification_plan_hash,
            id=check_id, subject_id=subject_id, plan_hash=plan, tree_hash=identity,
            kind=kind, state=result.state, exit_code=code, counts=result.counts,
            log_ref=ref, diagnostics=problem or log[-16000:],package_evidence=package_proof)
        (self.root / result.report_ref).write_text(result.model_dump_json())
        self.store.append_record(self.task_id, 'check', result.model_dump())
        return result

    async def _execute_scoped(self,context,kind,*,deadline):
        from nexus.execution import package_validation as execution
        from nexus.execution.runner import run_scoped_build_command
        from nexus.repair.package_evidence import capture
        project=context['project'];index=context['index']
        scanned=await execution.scan(project,index,deadline=deadline,private_root=self.root)
        code=None;raw=b'';problem=scanned['diagnostics'] or None;argv=[];test=None
        result=CheckResult(kind=kind,state='UNKNOWN')
        if scanned['state']=='PASS':
            remaining=2*1024*1024-sum(len(s['stdout'])+len(s['stderr']) for s in scanned['scans'])
            if remaining<=0:problem='OUTPUT_LIMIT'
            elif kind=='test':
                test=await execution.run_scoped_tests(project,expected=context['expected'],deadline=deadline,
                    private_root=self.root,output_limit=remaining)
                code=test['exit_code'];raw=test['stdout'];problem=test['problem'];argv=test['execution_argv']
                parsed=test['parsed'];result=CheckResult(kind=kind,state=parsed['state'],counts=parsed['counts'],case_results=parsed['case_results'])
            else:
                code,raw,problem=await run_scoped_build_command(project,deadline=deadline,
                    private_root=self.root,output_limit=remaining)
                argv=[['cjpm','build','-V']]
                scanned['source_after']=execution._snapshot(project);scanned['tool_after']=execution.tool_identity()
                if scanned['source_before']!=scanned['source_after'] or scanned['tool_before']!=scanned['tool_after']:
                    scanned['state']='UNKNOWN';scanned['diagnostics']='BUILD_INPUT_CHANGED';problem='BUILD_INPUT_CHANGED'
        try:raw.decode('utf-8',errors='strict')
        except UnicodeError:problem='INVALID_SDK_UTF8';result.state='UNKNOWN'
        proof=capture(self.root,project=project,index=index,scanned=scanned,execution=test)
        return code,raw,problem,argv,result,proof

    async def build(self, subject_id: str) -> CheckResult:
        return await self._run(subject_id, 'build')

    async def test(self, subject_id: str) -> CheckResult:
        return await self._run(subject_id, 'test')
