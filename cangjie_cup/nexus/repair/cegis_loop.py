"""Single bounded Generate → Verify → Feedback controller over real MCP."""
import asyncio
import re
from copy import deepcopy

from nexus.contracts import CandidateRecord, RepairFeedback, digest
from nexus.llm.provider import ModelProvider, ProviderUnavailable
from nexus.mcp.client import ToolClient
from nexus.store import RunStore, uid
from nexus.repair.feedback import build_feedback
from nexus.contracts import CheckResult

def object_constraints(base,types):
    from nexus.repair.object_values import registry
    types=registry(types)
    if not types:return base
    result=deepcopy(base)
    result.update(types=list(base['types'])+list(types),object_registry=types,readonly_object_fields=True,
        preserve_all_type_declarations=True,preserve_constructor_and_method_signatures=True,
        allowed=base['allowed']+'；仓颉具名struct/class的闭合构造、只读字段读取、已声明纯实例方法、this字段／方法及局部对象重绑定；对象字段仅Int64/Bool/String/Array<Int64>',
        forbidden='导入、宏、继承、接口、静态或扩展成员、属性getter/setter、var字段、mut方法、对象字段赋值、嵌套对象或对象数组、对象==或依赖class引用身份、修改声明字段／构造器／方法接口、数组元素赋值、Array构造器或一般成员方法、字符串插值、外部调用、顶层初始化、main入口')
    return result


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
    def __init__(self, store: RunStore, *, provider_factory=ModelProvider, client_factory=ToolClient, context_enricher=None,focus_enricher=None):
        self.store, self.provider_factory, self.client_factory = store, provider_factory, client_factory
        self.context_enricher=context_enricher
        self.focus_enricher=focus_enricher

    def phase(self, task_id, status):
        task = self.store.get_task(task_id)
        if task.status in TERMINAL:
            return False
        return self.store.update_task(task_id, expected_status=task.status,expected_revision=task.revision,status=status) is not None

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
        task=self.store.get_task(task_id)
        if task.status!='READY':return task
        claimed=self.store.update_task(task_id,expected_status='READY',expected_revision=task.revision,status='DIAGNOSING')
        if claimed is None:return self.store.get_task(task_id)
        task=claimed
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
                    properties_required=False
                    relations_required=False;relations_hash=None;oracle_required=False
                    sequences_required=False;sequences_hash=None
                    feedback_mapping = {}
                    scoped_upload=None
                    if task.schema_version == 2:
                        from nexus.requirements.service import RequirementService
                        spec, plan = RequirementService(self.store).task_context(task)
                        feedback_mapping = dict(suite_tests=plan.suite_tests, requirement_test_map=plan.requirement_test_map)
                        context['requirements'] = spec.model_dump(exclude={'confirmed_by'})
                        if spec.project_id.startswith('upload_'):
                            from nexus.uploads.service import UploadService
                            upload=UploadService(self.store)._read(spec.project_id)
                            properties_required=upload.get('properties_contract') is not None
                            relations_required=upload.get('relations_contract') is not None
                            relations_hash=upload.get('relations_hash');oracle_required=upload.get('oracle_contract') is not None
                            sequences_required=upload.get('sequences_contract') is not None;sequences_hash=upload.get('sequences_hash')
                            project_mode=upload.get('kind')=='PROJECT'
                            context['upload_constraints']=dict(types=['Int64','Bool','String','Array<Int64>'],string_max_utf8_bytes=256,array_max_length=16,readonly_arrays=True,preserve_all_function_signatures=True,
                                allowed='局部变量、算术/比较/逻辑、if/else、while、同包已声明函数调用；Array<Int64>字面量、下标读取、.size、for遍历，数组最多16项且只读；String字面量、+、==、!=、.size(UTF-8字节数)、.toRuneArray().size(码点数)，不做Unicode归一化',
                                forbidden='导入、类、宏、嵌套或非Int64数组、数组元素赋值、Array构造器或成员方法、除明确长度表达式外的成员访问、字符串插值或原始多行字符串、外部调用、顶层初始化、main入口',
                                source_notice='同包工程原文件；配置、测试和函数接口冻结，只能修改allowed_paths内生产文件' if project_mode else 'src/uploaded.cj是冻结工程副本；无包声明的原文件已补固定package，不能删除或改名',
                                analysis_scope='PER_FILE',
                                coverage='验证原工程公开测试和确认示例；启用独立规则时追加有限搜索，不推断任意输入语义' if project_mode else '只验证用户确认的公开示例，不推断任意输入语义')
                            from nexus.uploads.language import inspect_source
                            from nexus.execution.workspace import WorkspaceStore
                            frozen=WorkspaceStore(self.store.root).verify_baseline(task.baseline_id)
                            types=(upload['project_index'].get('types',{}) if project_mode else inspect_source((frozen/'src/uploaded.cj').read_text()).get('types',{}))
                            context['upload_constraints']=object_constraints(context['upload_constraints'],types)
                            if project_mode and upload['project_index']['version']==2:
                                from nexus.repair import scoped_context
                                scoped_context.prepare(self.store,task,upload,context)
                                scoped_upload=upload
                        context['verification_plan_hash'] = plan.plan_hash
                        # The oracle is inert private rule data, never part of the
                        # baseline/public test logs. Actual hidden test sources still
                        # require withholding diagnostics as before.
                        diagnostics_public = not any(visibility=='VERIFICATION_ONLY' and
                            not (spec.project_id.startswith('upload_') and path in ('verification/oracle.json','verification/properties.json','verification/relations.json','verification/sequences.json'))
                            for path,visibility in plan.context_visibility.items())
                        if not diagnostics_public:
                            context['diagnostics'] = {kind:{key:value for key,value in diagnosis[kind].items()
                                if key in ('state','kind','exit_code','counts')} for kind in ('build','test')}
                            context['diagnostics']['limitations'] = ['Verification-only diagnostics withheld']
                        if scoped_upload is not None:diagnostics_public=False
                    if self.context_enricher is not None:
                        await self.context_enricher(task,context)
                    provider = self.provider_factory(self.store, task.id)
                    seen, feedback_hashes = set(), []
                    for attempt in range(task.attempt_count+1, 4):
                        if not self.phase(task_id, 'GENERATING'): break
                        context['iteration']=dict(round=attempt,max_rounds=3,remaining_model_requests=4-attempt,
                            apply_base='IMMUTABLE_BASELINE',analysis_subject='BASELINE',
                            instruction='Return all accumulated edits against original baseline hashes')
                        if self.focus_enricher is not None:await self.focus_enricher(task,context)
                        if scoped_upload is not None:
                            from nexus.repair.scoped_context import enforce
                            enforce(self.store,task,scoped_upload,context)
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
                        exploration=None
                        properties=None
                        relations=None
                        sequences=None
                        if build['state'] == 'PASS':
                            if not self.phase(task_id, 'TESTING'): break
                            test = await call('candidate.test', **args)
                            exploration=test.pop('exploration',None)
                            properties=test.pop('properties',None)
                            relations=test.pop('relations',None)
                            sequences=test.pop('sequences',None)
                        if build['state'] not in ('PASS', 'FAIL') or (build['state'] == 'PASS' and test['state'] not in ('PASS', 'FAIL')):
                            raise ToolFailure('BLOCKED', 'Required verification unavailable or not run')
                        if exploration is not None and exploration['state'] not in ('PASS','FAIL'):
                            raise ToolFailure('BLOCKED','Independent exploration unavailable: '+exploration.get('reason','unknown result'))
                        if properties is not None:
                            if properties.get('candidate_id')!=candidate['id'] or properties.get('binding',{}).get('tree_hash')!=candidate['tree_hash']:
                                raise ToolFailure('BLOCKED','Business property candidate binding changed')
                            if properties.get('state') not in ('PASS','FAIL'):
                                raise ToolFailure('BLOCKED','Business properties unavailable: '+properties.get('reason','unknown result'))
                        if properties_required and test['state']=='PASS' and (exploration is None or exploration['state']=='PASS') and properties is None:
                            raise ToolFailure('BLOCKED','Required business properties missing')
                        if relations_required and test['state']=='PASS' and oracle_required and exploration is None:
                            raise ToolFailure('BLOCKED','Required relation prerequisite oracle missing')
                        if relations is not None:
                            if (relations.get('candidate_id')!=candidate['id'] or relations.get('binding',{}).get('tree_hash')!=candidate['tree_hash'] or
                                    relations_hash is not None and relations.get('binding',{}).get('relations_hash')!=relations_hash):
                                raise ToolFailure('BLOCKED','Business relation candidate binding changed')
                            if relations.get('state') not in ('PASS','FAIL'):
                                raise ToolFailure('BLOCKED','Business relations unavailable: '+relations.get('reason','unknown result'))
                            if test['state']!='PASS' or exploration is not None and exploration['state']!='PASS' or properties is not None and properties['state']!='PASS':
                                raise ToolFailure('BLOCKED','Business relation prerequisites have not passed')
                        if relations_required and test['state']=='PASS' and (exploration is None or exploration['state']=='PASS') and (properties is None or properties['state']=='PASS') and relations is None:
                            raise ToolFailure('BLOCKED','Required business relations missing')
                        if sequences_required and test['state']=='PASS' and oracle_required and exploration is None:
                            raise ToolFailure('BLOCKED','Required sequence prerequisite oracle missing')
                        if sequences is not None:
                            if (sequences.get('candidate_id')!=candidate['id'] or sequences.get('binding',{}).get('tree_hash')!=candidate['tree_hash'] or
                                    sequences_hash is not None and sequences.get('binding',{}).get('sequences_hash')!=sequences_hash):
                                raise ToolFailure('BLOCKED','Business sequence candidate or contract binding changed')
                            if sequences.get('state') not in ('PASS','FAIL'):
                                raise ToolFailure('BLOCKED','Business sequences unavailable: '+sequences.get('reason','unknown result'))
                            if test['state']!='PASS' or any(r is not None and r['state']!='PASS' for r in (exploration,properties,relations)):
                                raise ToolFailure('BLOCKED','Business sequence prerequisites have not passed')
                            if sequences_required:
                                from nexus.repair.sequence_service import SequenceService
                                try:
                                    verified=SequenceService(self.store).verify(candidate['id'])
                                    if verified is None or digest(verified)!=digest(sequences):raise ValueError('Sequence original report mismatch')
                                except (ValueError,OSError,KeyError,TypeError) as exc:raise ToolFailure('BLOCKED','Business sequence originals unavailable: '+str(exc)) from exc
                        if sequences_required and test['state']=='PASS' and all(r is None or r['state']=='PASS' for r in (exploration,properties,relations)) and sequences is None:
                            raise ToolFailure('BLOCKED','Required business sequences missing')
                        if build['state'] == test['state'] == 'PASS' and (exploration is None or exploration['state']=='PASS') and (properties is None or properties['state']=='PASS') and (relations is None or relations['state']=='PASS') and (sequences is None or sequences['state']=='PASS'):
                            if self.phase(task_id, 'REVIEW_PENDING'):
                                self.store.append_record(task_id, 'event', {'selected_candidate_id': candidate['id']})
                            break
                        diff = await call('candidate.diff', candidate_id=candidate['id'])
                        if sequences is not None and sequences['state']=='FAIL':
                            cases=[{**f,'candidate_id':candidate['id'],'tree_hash':candidate['tree_hash'],
                                'sequences_hash':sequences['binding']['sequences_hash'],'requirement_refs':proposal.requirement_refs,
                                'mapping_basis':'USER_CONFIRMED_SEQUENCE'} for f in sequences['failures']]
                            if not cases:raise ToolFailure('BLOCKED','Sequence failure lacks observed reachable prefix')
                            feedback=RepairFeedback(previous_candidate_id=candidate['id'],baseline_hash=candidate['baseline_hash'],
                                tree_hash=candidate['tree_hash'],diff=diff['diff'],edited_files=candidate['edits'],
                                failed_checks=[dict(kind='business_sequence',state='FAIL',subject_id=candidate['id'],tree_hash=candidate['tree_hash'],
                                    sequences_hash=sequences['binding']['sequences_hash'],public_test_state=test['state'])],
                                diagnostic_snippets=[dict(kind='business_sequence',visibility='PUBLIC',source='verified_sequence_observations',
                                    log_ref=cases[0]['source']['log_ref'],record_refs=sorted({step['source']['log_ref'] for f in cases for step in f['steps']}),
                                    text='Observed reachable sequence violations: '+str([{k:f[k] for k in ('initial_state','context','steps','step_index','failure_ids')} for f in cases]))],
                                requirement_refs=proposal.requirement_refs,failure_cases=cases,remaining_budget=3-attempt).model_dump()
                        elif relations is not None and relations['state']=='FAIL':
                            cases=[{**f,'candidate_id':candidate['id'],'tree_hash':candidate['tree_hash'],
                                'relations_hash':relations['binding']['relations_hash'],'requirement_refs':proposal.requirement_refs,
                                'mapping_basis':'USER_CONFIRMED_RELATION'} for f in relations['failures']]
                            if not cases:raise ToolFailure('BLOCKED','Relation failure lacks both observed counterexamples')
                            fields=('relation_id','relation_text','left_args','right_args','left_actual_return','right_actual_return','assertion_value','expected_relation')
                            feedback=RepairFeedback(previous_candidate_id=candidate['id'],baseline_hash=candidate['baseline_hash'],
                                tree_hash=candidate['tree_hash'],diff=diff['diff'],edited_files=candidate['edits'],
                                failed_checks=[dict(kind='business_relation',state='FAIL',subject_id=candidate['id'],tree_hash=candidate['tree_hash'],
                                    relations_hash=relations['binding']['relations_hash'],public_test_state=test['state'])],
                                diagnostic_snippets=[dict(kind='business_relation',visibility='PUBLIC',source='verified_relation_observations',
                                    log_ref=cases[0]['left_source']['log_ref'],record_refs=sorted({f[side+'_source']['log_ref'] for f in cases for side in ('left','right')}),
                                    text='Observed paired relation violations: '+str([{k:f[k] for k in fields} for f in cases]))],
                                requirement_refs=proposal.requirement_refs,failure_cases=cases,remaining_budget=3-attempt).model_dump()
                        elif properties is not None and properties['state']=='FAIL':
                            cases=[{**f,'candidate_id':candidate['id'],'tree_hash':candidate['tree_hash'],
                                'properties_hash':properties['binding']['properties_hash'],'requirement_refs':proposal.requirement_refs,
                                'mapping_basis':'USER_CONFIRMED_PROPERTY'} for f in properties['failures']]
                            if not cases:raise ToolFailure('BLOCKED','Property failure lacks observed counterexample')
                            feedback=RepairFeedback(previous_candidate_id=candidate['id'],baseline_hash=candidate['baseline_hash'],
                                tree_hash=candidate['tree_hash'],diff=diff['diff'],edited_files=candidate['edits'],
                                failed_checks=[dict(kind='business_property',state='FAIL',subject_id=candidate['id'],tree_hash=candidate['tree_hash'],
                                    properties_hash=properties['binding']['properties_hash'],public_test_state=test['state'])],
                                diagnostic_snippets=[dict(kind='business_property',visibility='PUBLIC',source='verified_property_observations',
                                    log_ref=cases[0]['source']['log_ref'],text='Observed property violations: '+str([
                                        {k:f[k] for k in ('property_id','property_text','args','actual_return','assertion_value','expected_property')} for f in cases]))],
                                requirement_refs=proposal.requirement_refs,failure_cases=cases,remaining_budget=3-attempt).model_dump()
                        elif exploration is not None and exploration['state']=='FAIL':
                            if exploration['binding']['tree_hash']!=candidate['tree_hash'] or exploration['candidate_id']!=candidate['id']:
                                raise ToolFailure('BLOCKED','Independent exploration candidate binding changed')
                            cases=exploration['failures']
                            feedback=RepairFeedback(previous_candidate_id=candidate['id'],baseline_hash=candidate['baseline_hash'],
                                tree_hash=candidate['tree_hash'],diff=diff['diff'],edited_files=candidate['edits'],
                                failed_checks=[dict(kind='independent_rule',state='FAIL',subject_id=candidate['id'],
                                    tree_hash=candidate['tree_hash'],oracle_hash=exploration['binding']['oracle_hash'],public_test_state=test['state'])],
                                diagnostic_snippets=[dict(kind='independent_rule',visibility='PUBLIC',source='verified_exploration',
                                    log_ref=cases[0]['source']['log_ref'],text='Independent rule counterexamples: '+str([
                                        dict(args=f['args'],actual=f['actual'],expected=f['expected']) for f in cases]))],
                                requirement_refs=proposal.requirement_refs,failure_cases=cases,remaining_budget=3-attempt).model_dump()
                        else:
                            public_fields=None
                            if task.schema_version==2 and (diagnostics_public or scoped_upload is not None) and test['state']=='FAIL':
                                from nexus.repair.public_fields import for_task
                                fields=for_task(self.store,task,CheckResult.model_validate(test),spec=spec)
                                if fields is not None:
                                    public_fields=([f for f in fields['failures'] if f.get('visibility')=='PUBLIC'] if scoped_upload is not None else fields['failures']) or None
                            feedback = build_feedback(CandidateRecord.model_validate(candidate), diff, build, test,
                                remaining_budget=3-attempt, requirement_refs=proposal.requirement_refs,
                                diagnostics_public=diagnostics_public, public_failure_cases=public_fields, **feedback_mapping).model_dump()
                        self.store.append_record(task_id, 'event', {'repair_feedback': feedback})
                        feedback_hashes.append(digest(dict(public=feedback_identity(build,test),independent=[
                            dict(args=f['args'],actual=f['actual'],expected=f['expected']) for f in exploration['failures']] if exploration else [],
                            properties=[{k:f[k] for k in ('property_id','args','actual_return','assertion_value','expected_property')} for f in properties['failures']] if properties else [],
                            relations=[{k:f[k] for k in ('relation_id','left_args','right_args','left_actual_return','right_actual_return','assertion_value','expected_relation')} for f in relations['failures']] if relations else [],
                            sequences=[dict(initial_state=f['initial_state'],context=f['context'],failure_ids=f['failure_ids'],steps=[{k:step[k] for k in ('operation_id','args','before_state','actual_return','expected_state')} for step in f['steps']]) for f in sequences['failures']] if sequences else [])))
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
