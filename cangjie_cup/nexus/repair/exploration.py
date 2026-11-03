"""Independent, content-bound searches executed inside candidate.test's gate."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import time

from nexus.contracts import digest,source_manifest
from nexus.execution.workspace import WorkspaceStore
from nexus.execution.runner import run_command
from nexus.adapters.cangjie.report_parser import parse_test_report
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.repair.counterexamples import failure_cases
from nexus.repair import oracle
from nexus.policy import core
from nexus.store import uid
from nexus.uploads.language import inspect_source,literal


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()


def boundary_payload(contract):
    from nexus.repair import object_values
    payload={'domains':[dict(name=p['name'],type=p['type'],domain=deepcopy(contract['domains'][p['name']]))
                       for p in contract['signature']['params']]}
    if object_values.has_objects(contract['signature']):
        payload['types']={name:{key:deepcopy(item[key]) for key in ('kind','fields')} for name,item in object_values.registry(contract['signature']['types']).items()}
    return payload


def object_dependencies(signature):
    from nexus.repair import object_values,object_expressions,object_trace
    from nexus.uploads import object_types,language
    from nexus.projects import index
    base=(object_values,object_expressions,object_trace,object_types,language,index) if object_values.has_objects(signature) else ()
    if 'scope' not in signature:return base
    from nexus.repair import scoped_batches,scoped_probe,scoped_material,scoped_signature,scoped_harness,scoped_trace,scoped_sequence,scoped_values,scoped_imports,package_evidence
    from nexus.projects import scopes,names
    from nexus.execution import package_validation
    from nexus.adapters.cangjie import scoped_reports
    from nexus.uploads import scoped_project,scoped_public_tests
    return (*base,scoped_batches,scoped_probe,scoped_material,scoped_signature,scoped_harness,scoped_trace,scoped_sequence,scoped_values,scoped_imports,package_evidence,scopes,names,package_validation,scoped_reports,scoped_project,scoped_public_tests)


def native_identity():
    try:return core.NativeCoreClient().component_identity()
    except (OSError,ValueError):return None


class ExplorationService:
    def __init__(self,store):
        self.store=store;self.ws=WorkspaceStore(store.root)
        with store.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS exploration_runs(candidate_id TEXT PRIMARY KEY,task_id TEXT NOT NULL,state TEXT NOT NULL,report_ref TEXT,report_sha256 TEXT)')

    def binding(self,candidate_id):
        candidate=self.ws.candidate(candidate_id);task=self.store.get_task(candidate.task_id)
        if task.schema_version!=2:return None
        from nexus.requirements.service import RequirementService
        spec,plan=RequirementService(self.store).task_context(task)
        if not spec.project_id.startswith('upload_'):return None
        baseline=self.ws.verify_baseline(task.baseline_id);rule=baseline/'verification/oracle.json'
        if not rule.exists():return None
        if plan.context_visibility.get('verification/oracle.json')!='VERIFICATION_ONLY':raise ValueError('独立规则未绑定验证计划')
        from nexus.uploads.service import UploadService
        uploaded=UploadService(self.store)._read(spec.project_id)
        raw=rule.read_bytes();contract=json.loads(raw)
        if contract!=uploaded.get('oracle_contract') or digest(contract)!=uploaded.get('oracle_hash'):raise ValueError('独立规则确认摘要变化')
        functions=(uploaded['project_index']['functions'] if uploaded.get('kind')=='PROJECT' else inspect_source((baseline/'src/uploaded.cj').read_text())['functions'])
        signature=next(f for f in functions if f['name']==contract['function'])
        if 'scope' in signature:
            from nexus.repair.scoped_batches import signature as source_signature
            signature=source_signature(self.store,task,candidate_id,contract)
        fields=('version','function','domains','expression','seed','max_cases')+(('excluded_inputs',) if contract['version'] in (2,3,4,5,6) else ())
        checked=oracle.validate_contract({k:contract[k] for k in fields},signature,uploaded['examples'])
        if checked!=contract:raise ValueError('独立规则规范变化')
        path,tree,check_plan=CangjieVerifier(self.store.root,task.id).identity(candidate_id)
        checks=[c for c in self.store.records(task.id,'check') if c['subject_id']==candidate_id and c['kind']=='test' and c['tree_hash']==tree and c['plan_hash']==check_plan]
        test=checks[-1] if checks else None
        public_record=test
        from nexus.repair import verification_evidence,string_trace,array_trace,values,primitive_trace
        from nexus.execution import runner
        from nexus.adapters.cangjie import report_parser
        evidence=verification_evidence.public_evidence(self.store,test,task,plan) if contract['version'] in (3,4,5,6) else None
        if evidence is not None and test:test={**test,'state':evidence['state']}
        native=native_identity()
        engine=digest(dict(files={p.name:sha(p.read_bytes()) for p in (Path(__file__),Path(oracle.__file__),Path(core.__file__))},native_core=native))
        identity=dict(candidate_id=candidate_id,task_id=task.id,tree_hash=tree,check_plan_hash=check_plan,
            verification_plan_hash=plan.plan_hash,oracle_hash=digest(contract),engine_hash=engine,
            public_check_hash=digest(test) if test else None,native_core=native)
        if contract['version'] in (3,4,5,6):
            dependencies=[string_trace,array_trace,values,primitive_trace,verification_evidence,runner,report_parser,*object_dependencies(contract['signature'])]
            identity.update(public_check_hash=digest(public_record) if public_record else None,public_evidence=evidence,
                engine_hash=digest(dict(base=engine,files={m.__name__:sha(Path(m.__file__).read_bytes()) for m in dependencies})))
        return candidate,task,path,contract,test,identity

    def read_record(self,ref,identity):
        p=Path(ref)
        if p.is_absolute() or len(p.parts)!=2 or p.parts[0]!='records' or '..' in p.parts:raise ValueError('独立验证证据引用无效')
        path=self.store.root/p
        if path.is_symlink():raise ValueError('独立验证证据不得为符号链接')
        raw=path.read_bytes()
        if sha(raw)!=identity:raise ValueError('独立验证证据摘要变化')
        return raw

    def write_record(self,value,suffix):
        raw=value if isinstance(value,bytes) else encoded(value)
        ref='records/'+uid()+suffix
        with (self.store.root/ref).open('xb') as f:f.write(raw)
        return ref,sha(raw)

    @staticmethod
    def harness(contract,cases,package):
        text='package '+package+'\nimport std.unittest.*\nimport std.unittest.testmacro.*\n@Test\nclass BoundaryTests {\n'
        for i,args in enumerate(cases):
            text+='    @TestCase\n    func case'+str(i)+'() {\n        @Expect('+contract['function']+'('+', '.join(literal(x) for x in args)+'), '+literal(oracle.expected(contract,args))+')\n    }\n'
        return (text+'}\n').encode()

    def interpret(self,batch,contract):
        cases=batch['inputs'];log=self.read_record(batch['log_ref'],batch['log_sha256']).decode()
        parsed=parse_test_report(log)
        expected_ids={'BoundaryTests.case'+str(i) for i in range(len(cases))}
        if (batch['problem'] is not None or parsed.state not in ('PASS','FAIL') or set(parsed.case_results)!=expected_ids or
                parsed.state=='PASS' and batch['exit_code']!=0 or parsed.state=='FAIL' and not batch['exit_code']):
            return dict(state='UNKNOWN',failures=[],counts=parsed.counts)
        parsed.log_ref=batch['log_ref'];parsed.diagnostics=log
        detected=failure_cases(parsed,suite_tests={'independent':sorted(expected_ids)},requirement_test_map={'REQ-UPLOAD':['independent']})
        failures=[]
        for item in detected:
            index=int(item['test_id'].split('case')[-1]);args=cases[index];answer=literal(oracle.expected(contract,args))
            # A missing/unrecognized actual value cannot become an attributed business failure.
            if item['expected']!=answer or item['actual'] is None:return dict(state='UNKNOWN',failures=[],counts=parsed.counts)
            failures.append({**item,'args':args,'oracle_hash':digest(contract),'kind':'independent_rule'})
        if parsed.state=='FAIL' and not failures:return dict(state='UNKNOWN',failures=[],counts=parsed.counts)
        return dict(state=parsed.state,failures=failures,counts=parsed.counts)

    @staticmethod
    def probe_material(path):
        from nexus.uploads.language import Parser
        manifest=source_manifest(path)
        names=sorted(name for name in manifest if name in ('cjpm.toml','cjpm.lock') or name.endswith('.cj') and not name.endswith('_test.cj'))
        from nexus.uploads.object_types import collect
        from nexus.repair.object_values import registry
        sources={name:(path/name).read_text() for name in names if name.endswith('.cj')};types={}
        for source in sources.values():
            declared=collect(source,validate=False)['types']
            if set(types)&set(declared):raise ValueError('探测工程对象声明重复')
            types.update(declared)
        types=registry(types)
        packages={Parser(source,types=types if types else None).program(headers_only=True)['package'] for source in sources.values()}
        if len(packages)!=1 or None in packages:raise ValueError('探测工程必须属于一个显式包')
        return next(iter(packages)),names

    async def batch(self,path,contract,cases,deadline_at,label):
        if any(not oracle.permitted_input(contract,args) for args in cases):raise ValueError('探测请求包含保留验收输入')
        project=self.store.root/'explorations'/uid();project.mkdir(parents=True)
        manifest=source_manifest(path)
        package,names=self.probe_material(path)
        for name in names:
            raw=(path/name).read_bytes()
            if sha(raw)!=manifest[name]:raise ValueError('探测前候选变化')
            dest=project/name;dest.parent.mkdir(exist_ok=True,parents=True);dest.write_bytes(raw);dest.chmod(0o644)
        harness=self.harness(contract,cases,package)
        target=project/'src/boundary_test.cj';target.write_bytes(harness);target.chmod(0o644)
        expected_manifest=source_manifest(project)
        timeout=min(60.0,max(0,(deadline_at-int(time.time()*1000))/1000))
        commands=[]
        if timeout<=0:code,log,problem=None,'','SEARCH_DEADLINE_EXCEEDED'
        else:code,log,problem=await run_command(project,['cjpm','test'],timeout=timeout,private_root=self.store.root,execution_argv=commands)
        if source_manifest(project)!=expected_manifest or source_manifest(path)!=manifest:raise ValueError('探测执行期间源码变化')
        log_ref,log_hash=self.write_record(log.encode(),'.exploration.log')
        harness_ref,harness_hash=self.write_record(harness,'.exploration.cj')
        batch=dict(label=label,inputs=cases,exit_code=code,problem=problem,execution_argv=commands,
            project_path=project.relative_to(self.store.root).as_posix(),project_manifest=expected_manifest,
            log_ref=log_ref,log_sha256=log_hash,harness_ref=harness_ref,harness_sha256=harness_hash)
        return batch,self.interpret(batch,contract)

    def verify(self,candidate_id):
        binding=self.binding(candidate_id)
        if binding is None:return None
        candidate,task,path,contract,public,identity=binding
        if contract['version'] in (3,4,5,6):return self.verify_string(candidate,task,path,contract,public,identity)
        with self.store.connect() as db:row=db.execute('SELECT state,report_ref,report_sha256 FROM exploration_runs WHERE candidate_id=?',(candidate_id,)).fetchone()
        if not row or row[0]=='STARTED':raise ValueError('独立验证尚无已确认结果，禁止交付')
        report=json.loads(self.read_record(row[1],row[2]))
        if digest(report['binding'])!=digest(identity) or report['state']!=row[0]:raise ValueError('独立验证候选或规则绑定变化')
        proof=report.get('native_boundary')
        if proof is not None:
            data=core.NativeCoreClient().verify_proof(proof,'boundary.axes',boundary_payload(contract))
            if set(data)!={'axes'} or proof['component']!=identity['native_core']:raise ValueError('原生边界证据或组件绑定变化')
            oracle.checked_axes(contract,data['axes'])
        elif report['batches'] or report['state'] in ('PASS','FAIL'):
            raise ValueError('独立搜索缺少原生边界证据')
        for batch in report['batches']:
            if any(not oracle.permitted_input(contract,args) for args in batch['inputs']):raise ValueError('独立搜索混入保留验收输入')
            package,names=self.probe_material(path)
            if self.read_record(batch['harness_ref'],batch['harness_sha256'])!=self.harness(contract,batch['inputs'],package):raise ValueError('独立测试程序变化')
            relative=Path(batch['project_path'])
            if (relative.is_absolute() or len(relative.parts)!=2 or relative.parts[0]!='explorations' or
                    len(relative.name)!=32 or any(c not in '0123456789abcdef' for c in relative.name)):
                raise ValueError('探测工程引用无效')
            project=self.store.root/relative
            if project.is_symlink() or project.parent.is_symlink() or not project.is_dir():raise ValueError('探测工程变化')
            expected_manifest={name:sha((path/name).read_bytes()) for name in names}
            expected_manifest['src/boundary_test.cj']=batch['harness_sha256']
            if batch['project_manifest']!=expected_manifest or source_manifest(project)!=expected_manifest:
                raise ValueError('探测工程源码或配置变化')
            result=self.interpret(batch,contract)
            if digest(result)!=digest(batch['result']):raise ValueError('独立验证日志与报告不符')
        batches=report['batches']
        if report['state']=='PASS' and (not public or public['state']!='PASS' or not batches or any(b['result']['state']!='PASS' for b in batches)):
            raise ValueError('独立验证PASS证据不足')
        if report['state']=='FAIL' and not any(b['result']['state']=='FAIL' for b in batches):raise ValueError('独立验证FAIL证据不足')
        return report

    async def run(self,candidate_id,deadline_at=None):
        binding=self.binding(candidate_id)
        if binding is None:return None
        candidate,task,path,contract,public,identity=binding
        if contract['version'] in (3,4,5,6):return await self.run_string(candidate,task,path,contract,public,identity,deadline_at)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT state FROM exploration_runs WHERE candidate_id=?',(candidate_id,)).fetchone()
            if not previous:
                db.execute('INSERT INTO exploration_runs VALUES (?,?,?,NULL,NULL)',(candidate_id,task.id,'STARTED'))
                self.store._append_event(db,task.id,dict(type='EXPLORATION_STARTED',candidate_id=candidate_id,oracle_hash=identity['oracle_hash']))
        if previous:
            if previous[0]=='STARTED':return dict(state='UNKNOWN',candidate_id=candidate_id,reason='独立验证执行结果待核实，不自动重放')
            return self.verify(candidate_id)
        deadline_at=min(deadline_at or int(time.time()*1000)+90000,int(time.time()*1000)+90000)
        report=dict(schema_version=1,binding=identity,candidate_id=candidate_id,state='UNKNOWN',public_test_state=public['state'] if public else 'NOT_RUN',
            reason='',batches=[],failures=[],search_cases=0,shrink_cases=0,regression_cases=0,seed=contract['seed'],algorithm=contract['algorithm'],
            native_boundary=None,
            limitations=['有限参数域采样；不证明任意输入正确','缩减有预算限制，不保证全局最小',
                        '边界轴由仓颉生成；组合、随机、缩减附加邻近值和封存输入过滤由Python执行'])
        try:
            if identity['native_core'] is None:raise ValueError('Native core unavailable; independent search blocked')
            if not public or public['state']!='PASS':raise ValueError('普通测试尚未通过')
            proof=await core.NativeCoreClient().call('boundary.axes',boundary_payload(contract),deadline_at=deadline_at)
            if proof['component']!=identity['native_core']:raise ValueError('原生边界组件在启动后变化')
            axes=oracle.checked_axes(contract,proof['response']['data']['axes'])
            report['native_boundary']=proof
            cumulative=[]
            for event in self.store.records(task.id,'event'):
                if event.get('type')=='EXPLORATION_FINISHED' and event.get('candidate_id')!=candidate_id:
                    old=self.verify(event['candidate_id'])
                    if old['binding']['oracle_hash']!=identity['oracle_hash']:raise ValueError('累计反例规则变化')
                    cumulative.extend(f['args'] for f in old['failures'])
            if any(not oracle.permitted_input(contract,args) for args in cumulative):raise ValueError('累计反例混入保留验收输入')
            cases=[];seen=set()
            for args in cumulative+oracle.generate_inputs(contract,axes=axes):
                key=tuple(args)
                if key not in seen:seen.add(key);cases.append(args)
            report['regression_cases']=len({tuple(x) for x in cumulative});report['search_cases']=len(cases)
            batch,result=await self.batch(path,contract,cases,deadline_at,'search')
            batch['result']=result;report['batches'].append(batch);report.update(state=result['state'],failures=result['failures'])
            if result['state']=='FAIL':
                best=min(result['failures'],key=lambda x:sum(abs(int(v)) for v in x['args']))
                for _ in range(2):
                    smaller=oracle.shrink_inputs(contract,best['args'],axes=axes)
                    if not smaller or int(time.time()*1000)>=deadline_at:break
                    batch,reduced=await self.batch(path,contract,smaller,deadline_at,'shrink')
                    batch['result']=reduced;report['batches'].append(batch);report['shrink_cases']+=len(smaller)
                    if reduced['state']=='UNKNOWN':report.update(state='UNKNOWN',reason='反例缩减执行未完成');break
                    if not reduced['failures']:break
                    best=min(reduced['failures'],key=lambda x:sum(abs(int(v)) for v in x['args']))
                report['failures']=[best]+[f for f in result['failures'] if f['args']!=best['args']][:15]
        except (ValueError,OSError,KeyError,StopIteration) as exc:
            report.update(state='UNKNOWN',reason=str(exc))
        except asyncio.CancelledError:
            report.update(state='UNKNOWN',reason='独立验证中断，禁止自动重放')
            self.finish(task.id,report)
            raise
        self.finish(task.id,report)
        return self.verify(candidate_id)

    @staticmethod
    def string_score(failure):
        from nexus.repair import values
        return (sum(values.primitive_weight(x) for x in failure['args']),tuple(values.typed_key(x) for x in failure['args']))

    def string_cumulative(self,c,identity):
        refs=[];inputs=[]
        with self.store.connect() as db:
            rows=db.execute('SELECT candidate_id,report_ref,report_sha256 FROM exploration_runs WHERE task_id=?',(c.task_id,)).fetchall()
        for cid,ref,hash_ in sorted(rows,key=lambda row:self.ws.candidate(row[0]).attempt):
            if self.ws.candidate(cid).attempt>=c.attempt:continue
            old=self.verify(cid)
            if old['state']=='UNKNOWN':raise ValueError('先前独立验证结果未知')
            if old['binding']['oracle_hash']!=identity['oracle_hash']:raise ValueError('累计反例规则变化')
            refs.append(dict(candidate_id=cid,report_ref=ref,report_sha256=hash_))
            inputs.extend(f['args'] for f in old['failures'])
        return refs,inputs

    @staticmethod
    def string_search(contract,axes,cumulative):
        if any(not oracle.permitted_input(contract,args) for args in cumulative):raise ValueError('累计反例混入保留验收输入')
        regressions={oracle.input_key(args) for args in cumulative}
        if len(regressions)>contract['max_cases']:raise ValueError('累计反例超过执行预算')
        seen=set();cases=[]
        for args in cumulative+oracle.generate_inputs(contract,axes=axes):
            key=oracle.input_key(args)
            if key not in seen:
                oracle.expected(contract,args)
                seen.add(key);cases.append(deepcopy(args))
                if len(cases)==contract['max_cases']:break
        if not cases:raise ValueError('独立规则没有可用输入')
        return cases,len(regressions)

    def string_interpret(self,batch,contract):
        from nexus.repair import primitive_trace
        raw=primitive_trace.read(contract['signature'],batch['inputs'],batch['token'],'oracle',
            self.read_record(batch['log_ref'],batch['log_sha256']).decode(),batch['exit_code'],batch['problem'],version=contract['version']-1)
        failures=[]
        for observation in raw['observations']:
            observation['source']['log_ref']=batch['log_ref']
            args=observation['args'];expected=oracle.expected(contract,args);actual=observation['actual_return']
            if type(actual) is not type(expected) or actual!=expected:
                failures.append(dict(kind='independent_rule',test_id=observation['test_id'],args=deepcopy(args),
                    expected=json.dumps(expected,ensure_ascii=False,separators=(',',':')),
                    actual=json.dumps(actual,ensure_ascii=False,separators=(',',':')),
                    expected_value=deepcopy(expected),actual_return=deepcopy(actual),source=dict(observation['source']),oracle_hash=digest(contract),
                    requirement_refs=['REQ-UPLOAD'],mapping_basis='USER_CONFIRMED_ORACLE'))
        return {**raw,'state':'UNKNOWN' if raw['state']=='UNKNOWN' else 'FAIL' if failures else 'PASS','failures':failures}

    @staticmethod
    def string_conclusion(batches):
        facts=[f for b in batches for f in b['result']['failures']];selected=[];seen=set()
        for failure in sorted(facts,key=ExplorationService.string_score):
            key=oracle.input_key(failure['args'])
            if key not in seen:seen.add(key);selected.append(failure)
        return dict(state='UNKNOWN' if not batches or any(b['result']['state']=='UNKNOWN' for b in batches) else 'FAIL' if facts else 'PASS',
            failures=selected[:16],failure_count=len(facts),distinct_failure_count=len(selected),failures_truncated=len(selected)>16,
            search_cases=len(batches[0]['inputs']) if batches else 0,shrink_cases=sum(len(batch['inputs']) for batch in batches[1:]))

    async def string_batch(self,path,contract,cases,deadline_at,label,report):
        if 'scope' in contract['signature']:
            from nexus.repair import scoped_batches
            token=digest(dict(binding=report['binding'],index=len(report['batches']),label=label,inputs=cases))[:16]
            return await scoped_batches.batch(self,path,contract,cases,deadline_at,label,report,mode='oracle',token=token)
        from nexus.repair import primitive_trace
        # Validate the complete rule batch before creating material or executing SDK.
        for args in cases:oracle.expected(contract,args)
        package,names=self.probe_material(path);manifest=source_manifest(path);index=len(report['batches'])
        token=digest(dict(binding=report['binding'],index=index,label=label,inputs=cases))[:16]
        harness=primitive_trace.harness(contract['signature'],cases,package,token,'oracle',version=contract['version']-1)
        project=self.store.root/'explorations'/uid();project.mkdir(parents=True)
        for name in names:
            raw=(path/name).read_bytes()
            if sha(raw)!=manifest[name]:raise ValueError('探测前候选变化')
            dest=project/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        (project/'src/boundary_test.cj').write_bytes(harness)
        h_ref,h_hash=self.write_record(harness,'.exploration.cj');l_ref,l_hash=self.write_record(b'','.exploration.log')
        batch=dict(label=label,inputs=cases,token=token,exit_code=None,problem='BATCH_PENDING',execution_argv=[],
            project_path=project.relative_to(self.store.root).as_posix(),project_manifest=source_manifest(project),
            harness_ref=h_ref,harness_sha256=h_hash,log_ref=l_ref,log_sha256=l_hash)
        report['batches'].append(batch)
        self.store.append_record(report['binding']['task_id'],'event',dict(type='EXPLORATION_BATCH_STARTED',candidate_id=report['candidate_id'],index=index,
            token=token,harness_ref=h_ref,harness_sha256=h_hash,project_path=batch['project_path']))
        timeout=min(60,max(0,(deadline_at-int(time.time()*1000))/1000));log=''
        try:
            if not timeout:batch['problem']='SEARCH_DEADLINE_EXCEEDED'
            else:batch['exit_code'],log,batch['problem']=await run_command(project,['cjpm','test'],timeout=timeout,
                private_root=self.store.root,execution_argv=batch['execution_argv'],test_output='all')
            if len(log.encode())>2*1024*1024:batch.update(exit_code=None,problem='OUTPUT_LIMIT');log=''
        except asyncio.CancelledError:
            batch['problem']='CANCELLED';raise
        finally:
            batch['log_ref'],batch['log_sha256']=self.write_record(log.encode(),'.exploration.log')
            batch['result']=self.string_interpret(batch,contract)
        if source_manifest(project)!=batch['project_manifest'] or source_manifest(path)!=manifest:raise ValueError('探测执行期间源码变化')
        return batch['result']

    def verify_string(self,c,task,path,contract,public,identity):
        from nexus.repair import primitive_trace
        with self.store.connect() as db:row=db.execute('SELECT state,report_ref,report_sha256 FROM exploration_runs WHERE candidate_id=?',(c.id,)).fetchone()
        if not row or row[0]=='STARTED':raise ValueError('独立验证尚无已确认结果，禁止交付')
        try:
            report=json.loads(self.read_record(row[1],row[2]));batches=report['batches']
            if digest(report['binding'])!=digest(identity) or report['candidate_id']!=c.id or report['state']!=row[0]:raise ValueError('独立验证候选绑定变化')
            expected_meta=dict(schema_version=contract['version']-1,seed=contract['seed'],algorithm=contract['algorithm'])
            if digest({key:report[key] for key in expected_meta})!=digest(expected_meta) or len(batches)>3:raise ValueError('独立验证版本、采样或预算变化')
            axes=None;refs=[];cumulative=[];proof=report['native_boundary']
            if proof is not None:
                data=core.NativeCoreClient().verify_proof(proof,'boundary.axes',boundary_payload(contract))
                if set(data)!={'axes'} or proof['component']!=identity['native_core']:raise ValueError('原生边界证据变化')
                axes=oracle.checked_axes(contract,data['axes']);refs,cumulative=self.string_cumulative(c,identity)
            elif batches or report['state'] in ('PASS','FAIL'):raise ValueError('缺少原生边界证据')
            if report['regression_refs']!=refs:raise ValueError('累计反例引用变化')
            cases,regressions=self.string_search(contract,axes,cumulative) if axes is not None else ([],0)
            best=None;package,names=(None,None) if 'scope' in contract['signature'] else self.probe_material(path)
            for index,batch in enumerate(batches):
                expected=cases if index==0 else oracle.shrink_inputs(contract,best['args'],axes=axes) if best else []
                label='search' if index==0 else 'shrink'
                if batch['inputs']!=expected or not expected or batch['label']!=label:raise ValueError('独立验证批次输入变化')
                token=digest(dict(binding=identity,index=index,label=label,inputs=expected))[:16]
                if batch['token']!=token:raise ValueError('独立观测标记变化')
                if 'scope' in contract['signature']:
                    from nexus.repair import scoped_batches
                    scoped_batches.verify(self,path,contract,batch,c.id,mode='oracle',items=expected,token=token)
                else:
                    harness=primitive_trace.harness(contract['signature'],expected,package,token,'oracle',version=contract['version']-1)
                    if self.read_record(batch['harness_ref'],batch['harness_sha256'])!=harness:raise ValueError('独立测试程序变化')
                    relative=Path(batch['project_path'])
                    if relative.is_absolute() or len(relative.parts)!=2 or relative.parts[0]!='explorations' or len(relative.name)!=32 or any(ch not in '0123456789abcdef' for ch in relative.name):raise ValueError('探测工程引用无效')
                    project=self.store.root/relative;manifest={name:sha((path/name).read_bytes()) for name in names};manifest['src/boundary_test.cj']=sha(harness)
                    if project.is_symlink() or project.parent.is_symlink() or batch['project_manifest']!=manifest or source_manifest(project)!=manifest:raise ValueError('探测工程材料变化')
                result=self.string_interpret(batch,contract)
                if digest(result)!=digest(batch['result']):raise ValueError('独立验证日志与报告不符')
                argv=[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]
                if 'scope' not in contract['signature'] and (batch['execution_argv'] not in [[],argv[:1],argv] or result['state'] in ('PASS','FAIL') and batch['execution_argv']!=argv):raise ValueError('独立验证执行参数变化')
                if index and batches[index-1]['result']['state']!='FAIL':raise ValueError('缩减缺少失败依据')
                if result['failures']:best=min(result['failures'],key=self.string_score)
            conclusion=self.string_conclusion(batches)
            for key in ('failures','failure_count','distinct_failure_count','failures_truncated'):
                if digest(report[key])!=digest(conclusion[key]):raise ValueError('独立反例汇总变化')
            if report['state']!='UNKNOWN' and report['state']!=conclusion['state']:raise ValueError('独立验证状态证据不足')
            if report['state'] in ('PASS','FAIL') and (not public or public['state']!='PASS'):raise ValueError('公开测试未通过')
            if report['public_test_state']!=(public['state'] if public else 'NOT_RUN'):raise ValueError('公开测试状态变化')
            if digest([report['search_cases'],report['shrink_cases'],report['regression_cases']])!=digest([len(cases) if batches else 0,sum(len(b['inputs']) for b in batches[1:]),regressions]):raise ValueError('独立执行计数变化')
            return report
        except (KeyError,TypeError,IndexError,json.JSONDecodeError) as exc:raise ValueError('独立验证报告格式无效') from exc

    async def run_string(self,c,task,path,contract,public,identity,deadline_at):
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');previous=db.execute('SELECT state FROM exploration_runs WHERE candidate_id=?',(c.id,)).fetchone()
            if not previous:
                db.execute('INSERT INTO exploration_runs VALUES (?,?,?,NULL,NULL)',(c.id,task.id,'STARTED'))
                self.store._append_event(db,task.id,dict(type='EXPLORATION_STARTED',candidate_id=c.id,oracle_hash=identity['oracle_hash']))
        if previous:
            if previous[0]=='STARTED':return dict(state='UNKNOWN',candidate_id=c.id,reason='独立验证执行结果待核实，不自动重放')
            return self.verify(c.id)
        deadline_at=min(deadline_at or int(time.time()*1000)+90000,int(time.time()*1000)+90000)
        report=dict(schema_version=contract['version']-1,candidate_id=c.id,binding=identity,state='UNKNOWN',public_test_state=public['state'] if public else 'NOT_RUN',reason='',
            batches=[],failures=[],failure_count=0,distinct_failure_count=0,failures_truncated=False,search_cases=0,shrink_cases=0,regression_cases=0,regression_refs=[],
            seed=contract['seed'],algorithm=contract['algorithm'],native_boundary=None,
            limitations=['有限String枚举与参数采样；不证明任意输入正确','缩减有预算限制，不保证全局最小','观测值最多256个UTF-8字节，不提供候选中间值堆上限'])
        if contract['version']==5:report['limitations']=['有限具名对象域与参数采样；不证明任意输入正确','缩减有预算限制，不保证全局最小','对象只含只读原始字段，String最多256字节、Array最多16项；无候选中间分配硬堆限额']
        if contract['version']==4:report['limitations']=['有限Array枚举与参数采样；不证明任意输入正确','缩减有预算限制，不保证全局最小','观测Array最多16项、String最多256个UTF-8字节，不提供候选中间分配硬堆限额']
        try:
            if identity['native_core'] is None:raise ValueError('独立验证原生组件不可用')
            if not public or public['state']!='PASS':raise ValueError('公开测试尚未通过')
            refs,cumulative=self.string_cumulative(c,identity)
            proof=await core.NativeCoreClient().call('boundary.axes',boundary_payload(contract),deadline_at=deadline_at)
            if proof['component']!=identity['native_core']:raise ValueError('独立验证原生组件变化')
            axes=oracle.checked_axes(contract,proof['response']['data']['axes'])
            report['regression_refs']=refs;report['native_boundary']=proof
            cases,regressions=self.string_search(contract,axes,cumulative);report['regression_cases']=regressions;report['search_cases']=len(cases)
            result=await self.string_batch(path,contract,cases,deadline_at,'search',report)
            if result['state']=='FAIL':
                best=min(result['failures'],key=self.string_score)
                for _ in range(2):
                    smaller=oracle.shrink_inputs(contract,best['args'],axes=axes)
                    if not smaller or int(time.time()*1000)>=deadline_at:break
                    reduced=await self.string_batch(path,contract,smaller,deadline_at,'shrink',report)
                    if reduced['state']=='UNKNOWN' or not reduced['failures']:break
                    best=min(reduced['failures'],key=self.string_score)
            report.update(self.string_conclusion(report['batches']))
        except (ValueError,OSError,KeyError,StopIteration) as exc:
            report.update(self.string_conclusion(report['batches']));report.update(state='UNKNOWN',reason=str(exc))
        except asyncio.CancelledError:
            report.update(self.string_conclusion(report['batches']));report.update(state='UNKNOWN',reason='独立验证中断，不自动重放');self.finish(task.id,report);raise
        self.finish(task.id,report)
        return self.verify(c.id)

    def finish(self,task_id,report):
        ref,identity=self.write_record(report,'.exploration.json')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('UPDATE exploration_runs SET state=?,report_ref=?,report_sha256=? WHERE candidate_id=? AND state=?',
                (report['state'],ref,identity,report['candidate_id'],'STARTED'))
            self.store._append_event(db,task_id,dict(type='EXPLORATION_FINISHED',candidate_id=report['candidate_id'],
                state=report['state'],report_ref=ref,report_sha256=identity,exploration=report))
