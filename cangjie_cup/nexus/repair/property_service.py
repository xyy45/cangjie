"""Candidate-bound single-call properties over pinned SDK observations."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import re
import time

from nexus.adapters.cangjie import report_parser
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.contracts import digest,source_manifest
from nexus.execution import runner
from nexus.execution.runner import run_command
from nexus.policy import core
from nexus.repair import oracle,properties,property_trace,primitive_trace,string_trace,array_trace,values,verification_evidence
from nexus.repair.exploration import ExplorationService,boundary_payload,native_identity,sha,object_dependencies
from nexus.requirements.service import RequirementService
from nexus.store import uid


def score(failure):
    args=failure['args']
    if any(type(x) in (str,list,dict) for x in args):return (sum(values.primitive_weight(x) for x in args),tuple(values.typed_key(x) for x in args),failure['property_id'])
    return (sum(abs(int(x)) for x in args),tuple(int(x) for x in args),failure['property_id'])


class PropertyService(ExplorationService):
    def __init__(self,store):
        super().__init__(store)
        with store.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS property_runs(candidate_id TEXT PRIMARY KEY,task_id TEXT NOT NULL,state TEXT NOT NULL,report_ref TEXT,report_sha256 TEXT)')

    def read_record(self,ref,identity):
        if (self.store.root/'records').is_symlink():raise ValueError('属性证据目录不得为符号链接')
        return super().read_record(ref,identity)

    def binding(self,candidate_id):
        c=self.ws.candidate(candidate_id);task=self.store.get_task(c.task_id)
        if task.schema_version!=2:return None
        spec,plan=RequirementService(self.store).task_context(task)
        if not spec.project_id.startswith('upload_'):return None
        from nexus.uploads.service import UploadService
        uploads=UploadService(self.store);uploaded=uploads._read(spec.project_id)
        if not uploaded.get('properties_contract'):return None
        uploads.profile(spec.project_id)
        baseline=self.ws.verify_baseline(task.baseline_id)
        contract=json.loads((baseline/'verification/properties.json').read_bytes())
        checked_signature=contract['signature']
        if 'scope' in checked_signature:
            from nexus.repair.scoped_batches import signature as source_signature
            checked_signature=source_signature(self.store,task,candidate_id,contract)
        if (plan.context_visibility.get('verification/properties.json')!='VERIFICATION_ONLY' or
                uploaded.get('properties_origin')!='USER_CONFIRMED' or contract!=uploaded['properties_contract'] or digest(contract)!=uploaded['properties_hash']):
            raise ValueError('业务属性确认或验证计划变化')
        checked=properties.validate_contract({k:contract[k] for k in properties.FIELDS},checked_signature,uploaded['examples'])
        if checked!=contract:raise ValueError('业务属性规范变化')
        path,tree,check_plan=CangjieVerifier(self.store.root,task.id).identity(candidate_id)
        tests=[v for v in self.store.records(task.id,'check') if v['subject_id']==candidate_id and v['kind']=='test' and v['tree_hash']==tree and v['plan_hash']==check_plan]
        public=tests[-1] if tests else None;native=native_identity()
        files=[*[Path(m.__file__) for m in object_dependencies(contract['signature'])],Path(__file__),Path(properties.__file__),Path(property_trace.__file__),Path(primitive_trace.__file__),Path(array_trace.__file__),Path(oracle.__file__),Path(runner.__file__),Path(report_parser.__file__),Path(core.__file__),Path(__file__).with_name('exploration.py')]
        identity=dict(candidate_id=candidate_id,task_id=task.id,tree_hash=tree,check_plan_hash=check_plan,
            verification_plan_hash=plan.plan_hash,properties_hash=digest(contract),origin='USER_CONFIRMED',
            oracle_hash=uploaded.get('oracle_hash'),public_check_hash=digest(public) if public else None,
            engine_hash=digest({p.name:sha(p.read_bytes()) for p in files}),native_core=native)
        if contract['version']>=2:
            proof=verification_evidence.public_evidence(self.store,public,task,plan)
            if public:public={**public,'state':proof['state']}
            required={}
            if uploaded.get('oracle_contract') is not None:
                try:
                    previous=ExplorationService(self.store).verify(candidate_id)
                    required['oracle']=dict(state=previous['state'],report_hash=digest(previous))
                except (ValueError,OSError,KeyError,TypeError):required['oracle']=dict(state='UNKNOWN',report_hash=None)
            identity.update(public_evidence=proof,required_checks=required,engine_hash=digest(dict(base=identity['engine_hash'],
                files={m.__name__:sha(Path(m.__file__).read_bytes()) for m in (values,string_trace,verification_evidence)})))
        return c,task,path,contract,public,identity

    def cumulative(self,c,identity):
        refs=[];inputs=[]
        with self.store.connect() as db:
            rows=db.execute('SELECT candidate_id,report_ref,report_sha256 FROM property_runs WHERE task_id=?',(c.task_id,)).fetchall()
        for cid,ref,hash_ in sorted(rows,key=lambda r:self.ws.candidate(r[0]).attempt):
            previous=self.ws.candidate(cid)
            if previous.attempt>=c.attempt:continue
            report=self.verify(cid)
            if report['binding']['properties_hash']!=identity['properties_hash']:raise ValueError('累计属性契约变化')
            if report['state']=='UNKNOWN':raise ValueError('先前属性执行结果未知')
            refs.append(dict(candidate_id=cid,report_ref=ref,report_sha256=hash_))
            inputs.extend(f['args'] for f in report['failures'])
        return refs,inputs

    @staticmethod
    def search_inputs(contract,axes,cumulative):
        seen=set();cases=[];regressions=set()
        for args in cumulative:
            if not properties.applicable(contract,args):raise ValueError('累计反例无适用属性')
            regressions.add(oracle.input_key(args))
        if len(regressions)>contract['max_cases']:raise ValueError('累计属性反例超过执行预算')
        for args in cumulative+oracle.generate_inputs(properties.sampler(contract),axes=axes):
            key=oracle.input_key(args)
            if key not in seen and properties.applicable(contract,args):
                seen.add(key);cases.append(deepcopy(args))
                if len(cases)==contract['max_cases']:break
        if not cases:raise ValueError('业务属性没有适用输入')
        return cases,len(regressions)

    @staticmethod
    def shrink_inputs(contract,axes,best):
        return [args for args in oracle.shrink_inputs(properties.sampler(contract),best['args'],axes=axes)
                if best['property_id'] in properties.applicable(contract,args)]

    def interpret_batch(self,batch,contract):
        log=self.read_record(batch['log_ref'],batch['log_sha256']).decode()
        result=property_trace.interpret(contract,batch['inputs'],batch['token'],log,batch['exit_code'],batch['problem'],required_ids=batch['required_ids'])
        for failure in result['failures']:failure['source']['log_ref']=batch['log_ref']
        if contract['version']>=2:
            for observation in result['observations']:observation['source']['log_ref']=batch['log_ref']
        return result

    async def batch(self,path,contract,cases,deadline_at,label,required_ids,report):

        if 'scope' in contract['signature']:
            from nexus.repair import scoped_batches
            token=digest(dict(binding=report['binding'],index=len(report['batches']),label=label,inputs=cases,required_ids=required_ids))[:16]
            return await scoped_batches.batch(self,path,contract,cases,deadline_at,label,report,mode='single',token=token,required_ids=required_ids)
        package,names=self.probe_material(path);manifest=source_manifest(path)
        index=len(report['batches'])
        token=digest(dict(binding=report['binding'],index=index,label=label,inputs=cases,required_ids=required_ids))[:16]
        harness=property_trace.harness(contract,cases,package,token)
        project=self.store.root/'properties'/uid();project.mkdir(parents=True)
        for name in names:
            raw=(path/name).read_bytes()
            if sha(raw)!=manifest[name]:raise ValueError('属性执行前候选变化')
            dest=project/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        (project/'src/property_observations_test.cj').write_bytes(harness)
        h_ref,h_hash=self.write_record(harness,'.properties.cj');l_ref,l_hash=self.write_record(b'','.properties.log')
        batch=dict(label=label,inputs=cases,required_ids=required_ids,token=token,exit_code=None,problem='BATCH_PENDING',execution_argv=[],
            project_path=project.relative_to(self.store.root).as_posix(),project_manifest=source_manifest(project),
            harness_ref=h_ref,harness_sha256=h_hash,log_ref=l_ref,log_sha256=l_hash)
        report['batches'].append(batch)
        # The event preserves the attempt/material binding even if the process dies.
        self.store.append_record(report['binding']['task_id'],'event',dict(type='PROPERTY_BATCH_STARTED',candidate_id=report['candidate_id'],index=index,token=token,harness_ref=h_ref,harness_sha256=h_hash,project_path=batch['project_path']))
        timeout=min(60,max(0,(deadline_at-int(time.time()*1000))/1000));log=''
        try:
            if not timeout:batch['problem']='SEARCH_DEADLINE_EXCEEDED'
            else:
                batch['exit_code'],log,batch['problem']=await run_command(project,['cjpm','test'],timeout=timeout,private_root=self.store.root,execution_argv=batch['execution_argv'],test_output='all')
            if len(log.encode())>2*1024*1024:batch.update(exit_code=None,problem='OUTPUT_LIMIT');log=''
        except asyncio.CancelledError:
            batch['problem']='CANCELLED';raise
        finally:
            batch['log_ref'],batch['log_sha256']=self.write_record(log.encode(),'.properties.log')
            batch['result']=self.interpret_batch(batch,contract)
        if source_manifest(project)!=batch['project_manifest'] or source_manifest(path)!=manifest:raise ValueError('属性执行期间源码变化')
        return batch['result']

    @staticmethod
    def conclusion(batches):
        facts=[f for b in batches for f in b['result']['failures']]
        selected=[];seen=set()
        for failure in sorted(facts,key=score):
            key=(failure['property_id'],oracle.input_key(failure['args']))
            if key not in seen:seen.add(key);selected.append(failure)
        return dict(failures=selected[:16],failure_count=len(facts),distinct_failure_count=len(selected),failures_truncated=len(selected)>16,
            state='UNKNOWN' if not batches or any(b['result']['state']=='UNKNOWN' for b in batches) else 'FAIL' if facts else 'PASS')

    def verify(self,candidate_id):
        binding=self.binding(candidate_id)
        if binding is None:return None
        c,task,path,contract,public,identity=binding
        with self.store.connect() as db:row=db.execute('SELECT state,report_ref,report_sha256 FROM property_runs WHERE candidate_id=?',(candidate_id,)).fetchone()
        if not row or row[0]=='STARTED':raise ValueError('业务属性尚无已确认结果')
        try:
            report=json.loads(self.read_record(row[1],row[2]));batches=report['batches']
            if digest(report['binding'])!=digest(identity) or report['candidate_id']!=candidate_id or report['state']!=row[0]:raise ValueError('业务属性候选绑定变化')
            expected_meta=dict(schema_version=1,seed=contract['seed'],algorithm=contract['algorithm'],public_test_state=public['state'] if public else 'NOT_RUN')
            if digest({key:report[key] for key in expected_meta})!=digest(expected_meta):raise ValueError('属性报告元数据变化')
            if len(batches)>3:raise ValueError('属性批次超过预算')
            proof=report['native_boundary'];axes=None;refs=[];cumulative=[]
            if proof is not None:
                data=core.NativeCoreClient().verify_proof(proof,'boundary.axes',boundary_payload(properties.sampler(contract)))
                if set(data)!={'axes'} or proof['component']!=identity['native_core']:raise ValueError('属性原生轴绑定变化')
                axes=oracle.checked_axes(properties.sampler(contract),data['axes'])
                refs,cumulative=self.cumulative(c,identity)
            elif batches or report['state'] in ('PASS','FAIL'):raise ValueError('业务属性缺少原生轴证据')
            if report['regression_refs']!=refs:raise ValueError('累计属性证据变化')
            expected_inputs,regressions=self.search_inputs(contract,axes,cumulative) if axes is not None else ([],0)
            all_ids=[p['id'] for p in contract['properties']];best=None
            package,names=(None,None) if 'scope' in contract['signature'] else self.probe_material(path)
            for index,batch in enumerate(batches):
                scope=all_ids if index==0 else [best['property_id']] if best else []
                expected=expected_inputs if index==0 else self.shrink_inputs(contract,axes,best) if best else []
                if batch['inputs']!=expected or not expected or batch['required_ids']!=scope or batch['label']!=('search' if index==0 else 'shrink'):raise ValueError('属性批次输入或覆盖范围变化')
                token=digest(dict(binding=identity,index=index,label=batch['label'],inputs=expected,required_ids=scope))[:16]
                if batch['token']!=token:raise ValueError('属性观测标记变化')
                if 'scope' in contract['signature']:
                    from nexus.repair import scoped_batches
                    scoped_batches.verify(self,path,contract,batch,c.id,mode='single',items=expected,token=token)
                else:
                    harness=property_trace.harness(contract,expected,package,token)
                    if self.read_record(batch['harness_ref'],batch['harness_sha256'])!=harness:raise ValueError('属性测试程序变化')
                    rel=Path(batch['project_path'])
                    if rel.is_absolute() or len(rel.parts)!=2 or rel.parts[0]!='properties' or not re.fullmatch(r'[0-9a-f]{32}',rel.name):raise ValueError('属性工程引用无效')
                    project=self.store.root/rel
                    manifest={n:sha((path/n).read_bytes()) for n in names};manifest['src/property_observations_test.cj']=sha(harness)
                    if project.is_symlink() or project.parent.is_symlink() or batch['project_manifest']!=manifest or source_manifest(project)!=manifest:raise ValueError('属性工程材料变化')
                result=self.interpret_batch(batch,contract)
                if digest(result)!=digest(batch['result']):raise ValueError('业务属性日志与结论不符')
                full_argv=[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]
                if 'scope' not in contract['signature'] and (batch['execution_argv'] not in [[],full_argv[:1],full_argv] or result['state'] in ('PASS','FAIL') and batch['execution_argv']!=full_argv):raise ValueError('属性执行参数变化')
                if index and batches[index-1]['result']['state']!='FAIL':raise ValueError('属性缩减缺少失败依据')
                failures=result['failures'] if index==0 else [f for f in result['failures'] if f['property_id']==best['property_id']]
                if failures:best=min(failures,key=score)
            conclusion=self.conclusion(batches)
            for key in ('failures','failure_count','distinct_failure_count','failures_truncated'):
                if digest(report[key])!=digest(conclusion[key]):raise ValueError('属性反例汇总变化')
            if report['state']!='UNKNOWN' and report['state']!=conclusion['state']:raise ValueError('属性状态证据不足')
            if report['state'] in ('PASS','FAIL') and (not public or public['state']!='PASS' or any(v['state']!='PASS' for v in identity.get('required_checks',{}).values())):raise ValueError('公开测试或必需前置检查未通过')
            if digest([report['search_cases'],report['shrink_cases'],report['regression_cases']])!=digest([len(expected_inputs) if batches else 0,sum(len(b['inputs']) for b in batches[1:]),regressions]):raise ValueError('属性执行计数变化')
            return report
        except (KeyError,TypeError,IndexError,json.JSONDecodeError) as exc:raise ValueError('业务属性报告格式无效') from exc

    async def run(self,candidate_id,deadline_at=None):
        binding=self.binding(candidate_id)
        if binding is None:return None
        c,task,path,contract,public,identity=binding
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT state FROM property_runs WHERE candidate_id=?',(candidate_id,)).fetchone()
            if not previous:
                db.execute('INSERT INTO property_runs VALUES (?,?,?,NULL,NULL)',(candidate_id,task.id,'STARTED'))
                self.store._append_event(db,task.id,dict(type='PROPERTY_STARTED',candidate_id=candidate_id,tree_hash=identity['tree_hash'],properties_hash=identity['properties_hash']))
        if previous:
            if previous[0]=='STARTED':return dict(state='UNKNOWN',candidate_id=candidate_id,reason='业务属性执行待核实，不自动重放')
            return self.verify(candidate_id)
        deadline_at=min(deadline_at or int(time.time()*1000)+90000,int(time.time()*1000)+90000)
        report=dict(schema_version=1,candidate_id=candidate_id,binding=identity,state='UNKNOWN',public_test_state=public['state'] if public else 'NOT_RUN',
            reason='',batches=[],failures=[],failure_count=0,distinct_failure_count=0,failures_truncated=False,
            search_cases=0,shrink_cases=0,regression_cases=0,regression_refs=[],native_boundary=None,
            seed=contract['seed'],algorithm=contract['algorithm'],limitations=['有限输入域采样；不证明任意输入正确','缩减有预算限制，不保证全局最小','仅单次调用属性；未覆盖调用关系、操作序列、并发或外部状态'])
        try:
            if identity['native_core'] is None:raise ValueError('属性验证原生组件不可用')
            if not public or public['state']!='PASS' or any(v['state']!='PASS' for v in identity.get('required_checks',{}).values()):raise ValueError('普通测试或必需前置检查尚未通过')
            proof=await core.NativeCoreClient().call('boundary.axes',boundary_payload(properties.sampler(contract)),deadline_at=deadline_at)
            if proof['component']!=identity['native_core']:raise ValueError('属性原生组件变化')
            axes=oracle.checked_axes(properties.sampler(contract),proof['response']['data']['axes'])
            refs,cumulative=self.cumulative(c,identity);report['regression_refs']=refs;report['native_boundary']=proof
            cases,regressions=self.search_inputs(contract,axes,cumulative);report['regression_cases']=regressions
            report['search_cases']=len(cases)
            result=await self.batch(path,contract,cases,deadline_at,'search',[p['id'] for p in contract['properties']],report)
            if result['state']=='FAIL':
                best=min(result['failures'],key=score)
                for _ in range(2):
                    smaller=self.shrink_inputs(contract,axes,best)
                    if not smaller or int(time.time()*1000)>=deadline_at:break
                    report['shrink_cases']+=len(smaller)
                    reduced=await self.batch(path,contract,smaller,deadline_at,'shrink',[best['property_id']],report)
                    if reduced['state']=='UNKNOWN':break
                    failures=[f for f in reduced['failures'] if f['property_id']==best['property_id']]
                    if not failures:break
                    best=min(failures,key=score)
            report.update(self.conclusion(report['batches']))
        except (ValueError,OSError,KeyError,StopIteration) as exc:
            report.update(self.conclusion(report['batches']));report.update(state='UNKNOWN',reason=str(exc))
        except asyncio.CancelledError:
            report.update(self.conclusion(report['batches']));report.update(state='UNKNOWN',reason='业务属性执行中断，不自动重放');self.finish(task.id,report);raise
        self.finish(task.id,report)
        return self.verify(candidate_id)

    def finish(self,task_id,report):
        ref,hash_=self.write_record(report,'.properties.json')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute('UPDATE property_runs SET state=?,report_ref=?,report_sha256=? WHERE candidate_id=? AND state=?',(report['state'],ref,hash_,report['candidate_id'],'STARTED')).rowcount
            if changed!=1:raise ValueError('业务属性完成状态冲突')
            self.store._append_event(db,task_id,dict(type='PROPERTY_FINISHED',candidate_id=report['candidate_id'],tree_hash=report['binding']['tree_hash'],state=report['state'],report_ref=ref,report_sha256=hash_,properties=report))
