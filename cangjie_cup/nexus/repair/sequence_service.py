"""Content-bound reachable state sequences over genuine pinned SDK observations."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import re
import time

from nexus.adapters.cangjie import report_parser
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.contracts import digest,source_manifest
import nexus.contracts as contracts
from nexus.execution import runner,workspace
from nexus.execution.runner import run_command
from nexus.policy import core
from nexus.repair import oracle,properties,primitive_trace,array_trace,sequences,sequence_trace,property_service,relation_service,verification_evidence
from nexus.repair.exploration import ExplorationService,boundary_payload,native_identity,sha,object_dependencies
from nexus.requirements.service import RequirementService
from nexus.store import uid


def failure_trace(contract,failure):
    """Reconstruct the full reachable prefix, never just its last intermediate state."""
    return dict(initial_state=deepcopy(failure['initial_state']),context=deepcopy(failure['context']),steps=[
        dict(operation_id=step['operation_id'],args=[deepcopy(step['args'][i]) for i in contract['nonstate_indices']]) for step in failure['steps']])


def score(contract,failure):return (*sequences.trace_score(failure_trace(contract,failure)),tuple(failure['failure_ids']))


class SequenceService(ExplorationService):
    def __init__(self,store):
        super().__init__(store)
        with store.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS sequence_runs(candidate_id TEXT PRIMARY KEY,task_id TEXT NOT NULL,state TEXT NOT NULL,report_ref TEXT,report_sha256 TEXT)')

    def read_record(self,ref,identity):
        if (self.store.root/'records').is_symlink():raise ValueError('序列证据目录不得为符号链接')
        relative=Path(ref)
        if relative.is_absolute() or len(relative.parts)!=2 or relative.parts[0]!='records' or '..' in relative.parts:raise ValueError('序列证据引用无效')
        path=self.store.root/relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size>2*1024*1024:raise ValueError('序列证据不可用或超限')
        with path.open('rb') as stream:raw=stream.read(2*1024*1024+1)
        if len(raw)>2*1024*1024 or sha(raw)!=identity:raise ValueError('序列证据摘要变化或超限')
        return raw

    def required_checks(self,candidate_id,uploaded):
        checks={}
        for name,service in [('oracle',ExplorationService),('properties',property_service.PropertyService),('relations',relation_service.RelationService)]:
            if uploaded.get(name+'_contract') is None:continue
            try:
                report=service(self.store).verify(candidate_id)
                checks[name]=dict(state=report['state'],report_hash=digest(report)) if report else dict(state='UNKNOWN',report_hash=None)
            except (ValueError,OSError,KeyError,TypeError,StopIteration):checks[name]=dict(state='UNKNOWN',report_hash=None)
        return checks

    def binding(self,candidate_id):
        c=self.ws.candidate(candidate_id);task=self.store.get_task(c.task_id)
        if task.schema_version!=2:return None
        spec,plan=RequirementService(self.store).task_context(task)
        if not spec.project_id.startswith('upload_'):return None
        from nexus.uploads.service import UploadService
        import nexus.uploads.service as upload_service
        import nexus.requirements.service as requirements
        uploads=UploadService(self.store);uploaded=uploads._read(spec.project_id)
        if not uploaded.get('sequences_contract'):return None
        uploads.profile(spec.project_id);baseline=self.ws.verify_baseline(task.baseline_id)
        contract=json.loads((baseline/'verification/sequences.json').read_bytes())
        checked_signature=contract['signature']
        if 'scope' in checked_signature:
            from nexus.repair.scoped_batches import signature as source_signature
            checked_signature=source_signature(self.store,task,candidate_id,contract)
        if (plan.context_visibility.get('verification/sequences.json')!='VERIFICATION_ONLY' or uploaded.get('sequences_origin')!='USER_CONFIRMED' or
                contract!=uploaded['sequences_contract'] or digest(contract)!=uploaded.get('sequences_hash')):raise ValueError('序列确认或验证计划变化')
        if sequences.validate_contract({k:contract[k] for k in sequences.FIELDS},checked_signature,uploaded['examples'])!=contract:raise ValueError('序列模型规范变化')
        reserved={oracle.input_key(a) for a in contract['excluded_inputs']}
        for name in ('oracle','properties','relations'):
            previous=uploaded.get(name+'_contract')
            if previous is not None and reserved!={oracle.input_key(a) for a in previous.get('excluded_inputs',[])}:raise ValueError('序列保留集合变化')
        path,tree,check_plan=CangjieVerifier(self.store.root,task.id).identity(candidate_id)
        tests=[v for v in self.store.records(task.id,'check') if v['subject_id']==candidate_id and v['kind']=='test' and v['tree_hash']==tree and v['plan_hash']==check_plan]
        record=tests[-1] if tests else None;proof=verification_evidence.public_evidence(self.store,record,task,plan)
        public={**record,'state':proof['state']} if record else None;native=native_identity()
        modules=[*object_dependencies(contract['signature']),sequences,sequence_trace,primitive_trace,array_trace,properties,property_service,property_service.property_trace,
            relation_service,relation_service.relations,relation_service.relation_trace,oracle,runner,report_parser,core,contracts,verification_evidence,workspace,upload_service,requirements]
        if contract['version']>=2:
            from nexus.repair import values,string_trace
            modules.extend([values,string_trace])
        files=[Path(__file__),Path(__file__).with_name('exploration.py'),*[Path(m.__file__) for m in modules]]
        identity=dict(candidate_id=candidate_id,task_id=task.id,tree_hash=tree,check_plan_hash=check_plan,
            verification_plan_hash=plan.plan_hash,sequences_hash=digest(contract),origin='USER_CONFIRMED',
            oracle_hash=uploaded.get('oracle_hash'),properties_hash=uploaded.get('properties_hash'),relations_hash=uploaded.get('relations_hash'),
            public_check_hash=digest(record) if record else None,public_evidence=proof,required_checks=self.required_checks(candidate_id,uploaded),
            engine_hash=digest({p.relative_to(Path(__file__).parents[2]).as_posix():sha(p.read_bytes()) for p in files}),native_core=native)
        return c,task,path,contract,public,identity

    def cumulative(self,c,identity,contract):
        refs=[];traces=[]
        with self.store.connect() as db:rows=db.execute('SELECT candidate_id,state,report_ref,report_sha256 FROM sequence_runs WHERE task_id=?',(c.task_id,)).fetchall()
        for cid,state,ref,hash_ in sorted(rows,key=lambda r:self.ws.candidate(r[0]).attempt):
            previous=self.ws.candidate(cid)
            if previous.attempt>=c.attempt:continue
            if state=='STARTED':raise ValueError('先前序列执行待核实')
            report=self.verify(cid)
            if report['binding']['sequences_hash']!=identity['sequences_hash']:raise ValueError('累计序列契约变化')
            if report['state']=='UNKNOWN':raise ValueError('先前序列执行结果未知')
            if report['state']!='FAIL':continue
            refs.append(dict(candidate_id=cid,report_ref=ref,report_sha256=hash_))
            traces.extend(failure_trace(contract,f) for f in report['failures'])
        return refs,traces

    def interpret_batch(self,batch,contract):
        log=self.read_record(batch['log_ref'],batch['log_sha256']).decode()
        result=sequence_trace.interpret(contract,batch['traces'],batch['token'],log,batch['exit_code'],batch['problem'],require_coverage=batch['label']=='search')
        for path in [*result['observations'],*result['failures']]:
            path['end_source']['log_ref']=batch['log_ref']
            for step in path['steps']:step['source']['log_ref']=batch['log_ref']
            if 'source' in path:path['source']['log_ref']=batch['log_ref']
        return result

    async def batch(self,path,contract,traces,deadline_at,label,report):

        if 'scope' in contract['signature']:
            from nexus.repair import scoped_batches
            token=digest(dict(binding=report['binding'],index=len(report['batches']),label=label,traces=traces))[:16]
            return await scoped_batches.batch(self,path,contract,traces,deadline_at,label,report,mode='sequence',token=token)
        package,names=self.probe_material(path);manifest=source_manifest(path);index=len(report['batches'])
        token=digest(dict(binding=report['binding'],index=index,label=label,traces=traces))[:16]
        harness=sequence_trace.harness(contract,traces,package,token)
        project=self.store.root/'sequences'/uid();project.mkdir(parents=True)
        for name in names:
            raw=(path/name).read_bytes()
            if sha(raw)!=manifest[name]:raise ValueError('序列执行前候选变化')
            dest=project/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        (project/'src/sequence_observations_test.cj').write_bytes(harness)
        h_ref,h_hash=self.write_record(harness,'.sequences.cj');l_ref,l_hash=self.write_record(b'','.sequences.log')
        batch=dict(label=label,traces=traces,token=token,exit_code=None,problem='BATCH_PENDING',execution_argv=[],
            project_path=project.relative_to(self.store.root).as_posix(),project_manifest=source_manifest(project),
            harness_ref=h_ref,harness_sha256=h_hash,log_ref=l_ref,log_sha256=l_hash)
        report['batches'].append(batch)
        self.store.append_record(report['binding']['task_id'],'event',dict(type='SEQUENCE_BATCH_STARTED',candidate_id=report['candidate_id'],index=index,token=token,harness_ref=h_ref,harness_sha256=h_hash,project_path=batch['project_path']))
        timeout=min(60,max(0,(deadline_at-int(time.time()*1000))/1000));log=''
        try:
            if not timeout:batch['problem']='SEARCH_DEADLINE_EXCEEDED'
            else:batch['exit_code'],log,batch['problem']=await run_command(project,['cjpm','test'],timeout=timeout,private_root=self.store.root,execution_argv=batch['execution_argv'],test_output='all')
            if len(log.encode())>2*1024*1024:batch.update(exit_code=None,problem='OUTPUT_LIMIT');log=''
        except asyncio.CancelledError:
            batch['problem']='CANCELLED';raise
        finally:
            batch['log_ref'],batch['log_sha256']=self.write_record(log.encode(),'.sequences.log');batch['result']=self.interpret_batch(batch,contract)
        if source_manifest(project)!=batch['project_manifest'] or source_manifest(path)!=manifest:raise ValueError('序列执行期间源码变化')
        return batch['result']

    @staticmethod
    def conclusion(batches,contract):
        facts=[f for b in batches for f in b['result']['failures']];selected=[];seen=set();operations={};invariants={}
        for failure in sorted(facts,key=lambda f:score(contract,f)):
            key=sequences.trace_key(failure_trace(contract,failure))
            if key not in seen:seen.add(key);selected.append(failure)
        for batch in batches:
            for field,coverage in [('per_operation',operations),('per_invariant',invariants)]:
                for fact in batch['result'][field]:
                    row=coverage.setdefault(fact['id'],{k:(v if k=='id' else 0) for k,v in fact.items()})
                    for key in fact:
                        if key!='id':row[key]+=fact[key]
        return dict(failures=selected[:8],failure_count=len(facts),distinct_failure_count=len(selected),failures_truncated=len(selected)>8,
            state='UNKNOWN' if not batches or any(b['result']['state']=='UNKNOWN' for b in batches) else 'FAIL' if facts else 'PASS',
            search_traces=len(batches[0]['traces']) if batches else 0,shrink_traces=sum(len(b['traces']) for b in batches[1:]),
            search_planned_calls=batches[0]['result']['planned_calls'] if batches else 0,shrink_planned_calls=sum(b['result']['planned_calls'] for b in batches[1:]),
            observed_calls=sum(b['result']['observed_calls'] for b in batches),per_operation=list(operations.values()),per_invariant=list(invariants.values()))

    def verify(self,candidate_id):
        binding=self.binding(candidate_id)
        if binding is None:return None
        c,task,path,contract,public,identity=binding
        with self.store.connect() as db:row=db.execute('SELECT state,report_ref,report_sha256 FROM sequence_runs WHERE candidate_id=?',(candidate_id,)).fetchone()
        if not row or row[0]=='STARTED':raise ValueError('序列尚无已确认结果')
        try:
            report=json.loads(self.read_record(row[1],row[2]));batches=report['batches']
            if digest(report['binding'])!=digest(identity) or report['candidate_id']!=candidate_id or report['state']!=row[0]:raise ValueError('序列候选绑定变化')
            expected_meta=dict(schema_version=1,seed=contract['seed'],algorithm=contract['algorithm'],public_test_state=public['state'] if public else 'NOT_RUN')
            if digest({key:report[key] for key in expected_meta})!=digest(expected_meta):raise ValueError('序列报告元数据变化')
            if len(batches)>3:raise ValueError('序列批次超过预算')
            proof=report['native_boundary'];axes=None;refs=[];generated=None
            if proof is not None:
                data=core.NativeCoreClient().verify_proof(proof,'boundary.axes',boundary_payload(sequences.sampler(contract)))
                if set(data)!={'axes'} or proof['component']!=identity['native_core']:raise ValueError('序列原生轴绑定变化')
                axes=oracle.checked_axes(sequences.sampler(contract),data['axes']);refs,cumulative=self.cumulative(c,identity,contract)
                generated=sequences.generate_traces(contract,axes,cumulative)
            elif batches or report['state'] in ('PASS','FAIL'):raise ValueError('序列缺少原生轴证据')
            if report['regression_refs']!=refs:raise ValueError('累计序列证据变化')
            if digest([report['candidate_checks'],report['regression_traces']])!=digest([generated['candidate_checks'] if generated else 0,generated['regression_traces'] if generated else 0]):raise ValueError('序列生成或回归计数变化')
            best=None;target=None;package,names=(None,None) if 'scope' in contract['signature'] else self.probe_material(path)
            for index,batch in enumerate(batches):
                expected=generated['traces'] if index==0 else sequences.shrink_traces(contract,failure_trace(contract,best),target,axes) if best else []
                if batch['traces']!=expected or not expected or batch['label']!=('search' if index==0 else 'shrink'):raise ValueError('序列批次路径变化')
                token=digest(dict(binding=identity,index=index,label=batch['label'],traces=expected))[:16]
                if batch['token']!=token:raise ValueError('序列观测标记变化')
                if 'scope' in contract['signature']:
                    from nexus.repair import scoped_batches
                    scoped_batches.verify(self,path,contract,batch,c.id,mode='sequence',items=expected,token=token)
                else:
                    harness=sequence_trace.harness(contract,expected,package,token)
                    if self.read_record(batch['harness_ref'],batch['harness_sha256'])!=harness:raise ValueError('序列测试程序变化')
                    rel=Path(batch['project_path'])
                    if rel.is_absolute() or len(rel.parts)!=2 or rel.parts[0]!='sequences' or not re.fullmatch(r'[0-9a-f]{32}',rel.name):raise ValueError('序列工程引用无效')
                    project=self.store.root/rel;manifest={n:sha((path/n).read_bytes()) for n in names};manifest['src/sequence_observations_test.cj']=sha(harness)
                    if project.is_symlink() or project.parent.is_symlink() or batch['project_manifest']!=manifest or source_manifest(project)!=manifest:raise ValueError('序列工程材料变化')
                result=self.interpret_batch(batch,contract)
                if digest(result)!=digest(batch['result']):raise ValueError('序列日志与结论不符')
                full_argv=[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]
                if 'scope' not in contract['signature'] and (batch['execution_argv'] not in [[],full_argv[:1],full_argv] or result['state'] in ('PASS','FAIL') and batch['execution_argv']!=full_argv):raise ValueError('序列执行参数变化')
                if index and batches[index-1]['result']['state']!='FAIL':raise ValueError('序列缩减缺少失败依据')
                failures=result['failures'] if index==0 else [f for f in result['failures'] if target in f['failure_ids']]
                if failures:
                    best=min(failures,key=lambda f:score(contract,f))
                    if index==0:target=best['failure_ids'][0]
                elif index and index!=len(batches)-1:raise ValueError('序列缩减不得越过未复现批次')
            conclusion=self.conclusion(batches,contract)
            for key,value in conclusion.items():
                if key!='state' and digest(report[key])!=digest(value):raise ValueError('序列反例、覆盖或执行计数变化')
            if report['state']!='UNKNOWN' and report['state']!=conclusion['state']:raise ValueError('序列状态证据不足')
            if report['state'] in ('PASS','FAIL') and (not public or public['state']!='PASS' or any(v['state']!='PASS' for v in identity['required_checks'].values())):raise ValueError('序列前置检查未通过')
            return report
        except (KeyError,TypeError,IndexError,json.JSONDecodeError) as exc:raise ValueError('序列报告格式无效') from exc

    async def run(self,candidate_id,deadline_at=None):
        binding=self.binding(candidate_id)
        if binding is None:return None
        c,task,path,contract,public,identity=binding
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');previous=db.execute('SELECT state FROM sequence_runs WHERE candidate_id=?',(candidate_id,)).fetchone()
            if not previous:
                db.execute('INSERT INTO sequence_runs VALUES (?,?,?,NULL,NULL)',(candidate_id,task.id,'STARTED'))
                self.store._append_event(db,task.id,dict(type='SEQUENCE_STARTED',candidate_id=candidate_id,tree_hash=identity['tree_hash'],sequences_hash=identity['sequences_hash']))
        if previous:
            if previous[0]=='STARTED':return dict(state='UNKNOWN',candidate_id=candidate_id,reason='序列执行待核实，不自动重放')
            return self.verify(candidate_id)
        deadline_at=min(deadline_at if deadline_at is not None else int(time.time()*1000)+90000,int(time.time()*1000)+90000)
        report=dict(schema_version=1,candidate_id=candidate_id,binding=identity,state='UNKNOWN',public_test_state=public['state'] if public else 'NOT_RUN',
            reason='',batches=[],**{k:v for k,v in self.conclusion([],contract).items() if k!='state'},
            candidate_checks=0,regression_traces=0,regression_refs=[],native_boundary=None,seed=contract['seed'],algorithm=contract['algorithm'],
            limitations=['有限原始状态及操作序列采样，不证明任意路径正确','最多128次搜索计划调用及两批各64次缩减计划调用，不保证全局最小',
                '每报告保留最多8条失败前缀，完整批次原件仍归档；累计并集超预算则UNKNOWN','不覆盖多字段对象、数据库、外部副作用或并发'])
        if contract['version']==4:
            report['limitations'][0]='有限具名对象状态及固定上下文采样，不证明任意路径正确'
            report['limitations'][-1]='仅只读扁平对象值，不覆盖可变身份图、数据库、外部副作用或并发'
        try:
            if identity['native_core'] is None:raise ValueError('序列验证原生组件不可用')
            if not public or public['state']!='PASS' or any(v['state']!='PASS' for v in identity['required_checks'].values()):raise ValueError('公开测试或必需前置检查尚未通过')
            if int(time.time()*1000)>=deadline_at:raise ValueError('序列执行预算已到期')
            proof=await core.NativeCoreClient().call('boundary.axes',boundary_payload(sequences.sampler(contract)),deadline_at=deadline_at)
            if proof['component']!=identity['native_core']:raise ValueError('序列原生组件变化')
            axes=oracle.checked_axes(sequences.sampler(contract),proof['response']['data']['axes'])
            refs,cumulative=self.cumulative(c,identity,contract);generated=sequences.generate_traces(contract,axes,cumulative)
            report.update(regression_refs=refs,native_boundary=proof,candidate_checks=generated['candidate_checks'],regression_traces=generated['regression_traces'])
            result=await self.batch(path,contract,generated['traces'],deadline_at,'search',report)
            if result['state']=='FAIL':
                best=min(result['failures'],key=lambda f:score(contract,f));target=best['failure_ids'][0]
                for _ in range(2):
                    smaller=sequences.shrink_traces(contract,failure_trace(contract,best),target,axes)
                    if not smaller or int(time.time()*1000)>=deadline_at:break
                    reduced=await self.batch(path,contract,smaller,deadline_at,'shrink',report)
                    if reduced['state']=='UNKNOWN':break
                    failures=[f for f in reduced['failures'] if target in f['failure_ids']]
                    if not failures:break
                    best=min(failures,key=lambda f:score(contract,f))
            report.update(self.conclusion(report['batches'],contract))
        except (ValueError,OSError,KeyError,StopIteration) as exc:
            report.update(self.conclusion(report['batches'],contract));report.update(state='UNKNOWN',reason=str(exc))
        except asyncio.CancelledError:
            report.update(self.conclusion(report['batches'],contract));report.update(state='UNKNOWN',reason='序列执行中断，不自动重放');self.finish(task.id,report);raise
        self.finish(task.id,report)
        return self.verify(candidate_id)

    def finish(self,task_id,report):
        ref,hash_=self.write_record(report,'.sequences.json')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute('UPDATE sequence_runs SET state=?,report_ref=?,report_sha256=? WHERE candidate_id=? AND state=?',(report['state'],ref,hash_,report['candidate_id'],'STARTED')).rowcount
            if changed!=1:raise ValueError('序列完成状态冲突')
            self.store._append_event(db,task_id,dict(type='SEQUENCE_FINISHED',candidate_id=report['candidate_id'],tree_hash=report['binding']['tree_hash'],state=report['state'],report_ref=ref,report_sha256=hash_,sequences=report))
