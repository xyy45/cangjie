"""Single bounded Generate → Verify → Feedback controller over real MCP."""
import asyncio
import re
from copy import deepcopy

from nexus.contracts import CandidateRecord, digest
from nexus.llm.provider import ModelProvider, ProviderUnavailable
from nexus.mcp.client import ToolClient
from nexus.store import RunStore, uid
from nexus.repair.feedback import build_feedback

def feedback_identity(build, test):
    def normalize(text):
        text = re.sub(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|[78])', '', text or '')
        text = re.sub(r'[bc]_[0-9a-f]{32}', '<subject>', text)
        text = re.sub(r'\b\d+\s*(?:ns|μs|ms)\b|\b\d{2}:\d{2}:\d{2}\b', '<time>', text)
        return text
    return digest({'build': normalize(build.get('diagnostics')), 'test': normalize(test.get('diagnostics'))})


TERMINAL = {'CANCELLED', 'BLOCKED', 'REJECTED', 'IN_DOUBT', 'UNREPAIRED', 'DELIVERED', 'REVIEW_PENDING'}


class ToolFailure(RuntimeError):
    def __init__(self, state, message):
        self.state = state
        super().__init__(message)


class RepairLoop:
    def __init__(self, store: RunStore, *, provider_factory=ModelProvider, client_factory=ToolClient, context_enricher=None):
        self.store, self.provider_factory, self.client_factory = store, provider_factory, client_factory
        self.context_enricher=context_enricher

    def phase(self, task_id, status):
        task = self.store.get_task(task_id)
        if task.status in TERMINAL:
            return False
        return self.store.update_task(task_id, expected_status=task.status, status=status) is not None

    def pending_operations(self, task_id):
        calls={record['id']:record for record in self.store.records(task_id,'model_call')}
        if any(record['status']=='STARTED' and calls.get(record['id']+'-result',{}).get('status') not in ('SUCCEEDED','FAILED')
               for record in calls.values()):
            return True
        with self.store.connect() as db:
            exists=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='tool_requests'").fetchone()
            return bool(exists and db.execute("SELECT 1 FROM tool_requests WHERE task_id=? AND state IN ('STARTED','IN_DOUBT')",(task_id,)).fetchone())

    async def run(self, task_id: str):
        # Claim once in a SQLite transaction; page refresh cannot restart a run.
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            task = self.store.get_task(task_id)
            if task.status != 'READY':
                return task
            task.status = 'DIAGNOSING'
            task.revision += 1
            db.execute('UPDATE tasks SET payload=? WHERE id=?', (task.model_dump_json(), task.id))
            self.store._append_event(db,task.id,dict(type='TASK_STATE_CHANGED',previous_status='READY',
                status=task.status,task_revision=task.revision))
        try:
            async with asyncio.timeout(480):
                async with self.client_factory(self.store.root) as client:
                    async def call(name, **arguments):
                        if self.store.get_task(task.id).status in TERMINAL:
                            raise ToolFailure('BLOCKED','Task stopped before the next MCP operation')
                        arguments.update(task_id=task.id, request_id=uid())
                        result = await client.call_tool(name, arguments)
                        if result.operation_status != 'OK':
                            raise ToolFailure('IN_DOUBT' if result.operation_status == 'IN_DOUBT' else 'BLOCKED', result.error)
                        return result.data
                    diagnosis = await call('project.diagnose', subject_id=task.baseline_id)
                    if diagnosis['build']['state'] == 'UNKNOWN' or diagnosis['test']['state'] == 'UNKNOWN':
                        raise ToolFailure('BLOCKED', 'Baseline environment unknown')
                    files = await call('workspace.list_files', baseline_id=task.baseline_id)
                    source = {}
                    for item in files['files']:
                        if item['path'].endswith('.cj'):
                            source[item['path']] = await call('workspace.read_file', baseline_id=task.baseline_id, path=item['path'])
                    context = dict(goal=task.goal, allowed_paths=task.allowed_paths, files=source,
                                   diagnostics=diagnosis, sdk='Cangjie 1.0.5', feedback=[])
                    diagnostics_public = True  # Legacy registered fixtures have public frozen tests.
                    feedback_mapping = {}
                    if task.schema_version == 2:
                        from nexus.requirements.service import RequirementService
                        spec, plan = RequirementService(self.store).task_context(task)
                        feedback_mapping = dict(suite_tests=plan.suite_tests, requirement_test_map=plan.requirement_test_map)
                        context['requirements'] = spec.model_dump(exclude={'confirmed_by'})
                        if spec.project_id.startswith('upload_'):
                            context['upload_constraints']=dict(types=['Int64','Bool'],preserve_all_function_signatures=True,
                                allowed='局部变量、算术/比较/逻辑、if/else、while及文件内已声明函数调用',
                                forbidden='导入、类、宏、字符串、数组、成员访问、外部调用、顶层初始化、main入口',
                                source_notice='src/uploaded.cj是冻结工程副本；无包声明的原文件已补固定package，不能删除或改名',
                                coverage='只验证用户确认的公开示例，不推断任意输入语义')
                        context['verification_plan_hash'] = plan.plan_hash
                        diagnostics_public = 'VERIFICATION_ONLY' not in plan.context_visibility.values()
                        if not diagnostics_public:
                            context['diagnostics'] = {kind:{key:value for key,value in diagnosis[kind].items()
                                if key in ('state','kind','exit_code','counts')} for kind in ('build','test')}
                            context['diagnostics']['limitations'] = ['Verification-only diagnostics withheld']
                    if self.context_enricher is not None:
                        await self.context_enricher(task,context)
                    provider = self.provider_factory(self.store, task.id)
                    seen, feedback_hashes = set(), []
                    for attempt in range(task.attempt_count+1, 4):
                        if not self.phase(task_id, 'GENERATING'): break
                        context['iteration']=dict(round=attempt,max_rounds=3,remaining_model_requests=4-attempt,
                            apply_base='IMMUTABLE_BASELINE',analysis_subject='BASELINE',
                            instruction='Return all accumulated edits against original baseline hashes')
                        proposal = await provider.propose(deepcopy(context))
                        if not self.phase(task_id, 'APPLYING'): break
                        if any(edit.path not in task.allowed_paths for edit in proposal.edits):
                            raise ToolFailure('REJECTED','Candidate exceeds the confirmed editable scope')
                        fingerprint = digest(proposal.model_dump())
                        if fingerprint in seen:
                            self.phase(task_id,'UNREPAIRED')
                            self.store.append_record(task_id,'event',{'stop_reason':'Repeated candidate proposal'})
                            break
                        seen.add(fingerprint)
                        candidate = await call('candidate.apply', proposal=proposal.model_dump())
                        # Server owns attempt numbering. Re-read; never let model choose it.
                        current = self.store.get_task(task_id)
                        if current.attempt_count < attempt:
                            self.store.update_task(task_id, attempt_count=attempt)
                        if not self.phase(task_id, 'BUILDING'): break
                        args = dict(candidate_id=candidate['id'], expected_tree_hash=candidate['tree_hash'])
                        build = await call('candidate.build', **args)
                        test = {'state': 'NOT_RUN'}
                        if build['state'] == 'PASS':
                            if not self.phase(task_id, 'TESTING'): break
                            test = await call('candidate.test', **args)
                        if build['state'] not in ('PASS', 'FAIL') or (build['state'] == 'PASS' and test['state'] not in ('PASS', 'FAIL')):
                            raise ToolFailure('BLOCKED', 'Required verification unavailable or not run')
                        if build['state'] == test['state'] == 'PASS':
                            if self.phase(task_id, 'REVIEW_PENDING'):
                                self.store.append_record(task_id, 'event', {'selected_candidate_id': candidate['id']})
                            break
                        diff = await call('candidate.diff', candidate_id=candidate['id'])
                        feedback = build_feedback(CandidateRecord.model_validate(candidate), diff, build, test,
                            remaining_budget=3-attempt, requirement_refs=proposal.requirement_refs,
                            diagnostics_public=diagnostics_public, **feedback_mapping).model_dump()
                        self.store.append_record(task_id, 'event', {'repair_feedback': feedback})
                        feedback_hashes.append(feedback_identity(build,test))
                        context['feedback'].append(feedback)
                        if len(feedback_hashes) >= 2 and feedback_hashes[-1] == feedback_hashes[-2]:
                            self.phase(task_id,'UNREPAIRED')
                            self.store.append_record(task_id,'event',{'stop_reason':'Repeated verification failure; no progress'})
                            break
                    else:
                        self.phase(task_id,'UNREPAIRED')
                        self.store.append_record(task_id,'event',{'stop_reason':'Candidate budget exhausted'})
        except (ProviderUnavailable, ToolFailure, asyncio.TimeoutError) as exc:
            state=exc.state if isinstance(exc,(ProviderUnavailable,ToolFailure)) else ('IN_DOUBT' if self.pending_operations(task_id) else 'BLOCKED')
            if self.phase(task_id,state):
                self.store.append_record(task_id, 'event', {'stop_reason': str(exc)})
        except asyncio.CancelledError:
            if self.phase(task_id,'IN_DOUBT'):
                self.store.append_record(task_id,'event',{'stop_reason':'Controller interrupted; do not replay in-flight operations'})
            raise
        except Exception as exc:
            if self.phase(task_id,'IN_DOUBT'):
                self.store.append_record(task_id,'event',{'stop_reason':f'Unexpected controller failure: {type(exc).__name__}'})
        return self.store.get_task(task_id)
