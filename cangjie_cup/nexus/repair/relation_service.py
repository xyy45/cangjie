"""Candidate-bound paired relations over pinned SDK observations."""
import asyncio
import json
from pathlib import Path
import re
import time

from nexus.adapters.cangjie import report_parser
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.contracts import CheckResult,digest,source_manifest
import nexus.contracts as contracts
from nexus.execution import runner
from nexus.execution.runner import run_command
from nexus.policy import core
from nexus.repair import oracle,properties,primitive_trace,array_trace,relations,relation_trace,property_service,verification_evidence,string_trace,values
from nexus.repair.exploration import ExplorationService,boundary_payload,native_identity,sha,object_dependencies
from nexus.requirements.service import RequirementService
from nexus.store import uid


def failure_pair(failure):return dict(left=failure['left_args'],right=failure['right_args'])
def score(failure):return (*relations.pair_score(failure_pair(failure)),failure['relation_id'])


class RelationService(ExplorationService):
    def __init__(self,store):
        super().__init__(store)
        with store.connect() as db:db.execute('CREATE TABLE IF NOT EXISTS relation_runs(candidate_id TEXT PRIMARY KEY,task_id TEXT NOT NULL,state TEXT NOT NULL,report_ref TEXT,report_sha256 TEXT)')

    def read_record(self,ref,identity):
        if (self.store.root/'records').is_symlink():raise ValueError('关系证据目录不得为符号链接')
        return super().read_record(ref,identity)

    def required_checks(self,candidate_id,uploaded):
        checks={}
        for name,configured,service in (('oracle',uploaded.get('oracle_contract'),ExplorationService),
                                        ('properties',uploaded.get('properties_contract'),property_service.PropertyService)):
            if configured is None:continue
            try:
                report=service(self.store).verify(candidate_id)
                checks[name]=dict(state=report['state'],report_hash=digest(report)) if report else dict(state='UNKNOWN',report_hash=None)
            except (ValueError,OSError,KeyError,TypeError,StopIteration):checks[name]=dict(state='UNKNOWN',report_hash=None)
        return checks

    def public_evidence(self,check,task,plan):
        return verification_evidence.public_evidence(self.store,check,task,plan)

    def binding(self,candidate_id):
        c=self.ws.candidate(candidate_id);task=self.store.get_task(c.task_id)
        if task.schema_version!=2:return None
        spec,plan=RequirementService(self.store).task_context(task)
        if not spec.project_id.startswith('upload_'):return None
        from nexus.uploads.service import UploadService
        uploads=UploadService(self.store);uploaded=uploads._read(spec.project_id)
        if not uploaded.get('relations_contract'):return None
        uploads.profile(spec.project_id);baseline=self.ws.verify_baseline(task.baseline_id)
        contract=json.loads((baseline/'verification/relations.json').read_bytes())
        checked_signature=contract['signature']
        if 'scope' in checked_signature:
            from nexus.repair.scoped_batches import signature as source_signature
            checked_signature=source_signature(self.store,task,candidate_id,contract)
        if (plan.context_visibility.get('verification/relations.json')!='VERIFICATION_ONLY' or uploaded.get('relations_origin')!='USER_CONFIRMED' or
                contract!=uploaded['relations_contract'] or digest(contract)!=uploaded.get('relations_hash')):raise ValueError('业务关系确认或验证计划变化')
        if relations.validate_contract({k:contract[k] for k in relations.FIELDS},checked_signature,uploaded['examples'])!=contract:raise ValueError('业务关系规范变化')
        reserved={oracle.input_key(a) for a in contract['excluded_inputs']}
        for previous in (uploaded.get('oracle_contract'),uploaded.get('properties_contract')):
            if previous is not None and reserved!={oracle.input_key(a) for a in previous.get('excluded_inputs',[])}:raise ValueError('业务关系保留集合变化')
        path,tree,check_plan=CangjieVerifier(self.store.root,task.id).identity(candidate_id)
        tests=[v for v in self.store.records(task.id,'check') if v['subject_id']==candidate_id and v['kind']=='test' and v['tree_hash']==tree and v['plan_hash']==check_plan]
        public_record=tests[-1] if tests else None;public_proof=self.public_evidence(public_record,task,plan)
        public={**public_record,'state':public_proof['state']} if public_record else None;native=native_identity()
        files=[*[Path(m.__file__) for m in object_dependencies(contract['signature'])],Path(verification_evidence.__file__),Path(__file__),Path(relations.__file__),Path(relation_trace.__file__),Path(primitive_trace.__file__),Path(array_trace.__file__),Path(properties.__file__),
            Path(property_service.__file__),Path(property_service.property_trace.__file__),Path(oracle.__file__),Path(runner.__file__),
            Path(report_parser.__file__),Path(core.__file__),Path(contracts.__file__),Path(__file__).with_name('exploration.py')]
        if contract['version']>=2:files.extend([Path(values.__file__),Path(string_trace.__file__)])
        identity=dict(candidate_id=candidate_id,task_id=task.id,tree_hash=tree,check_plan_hash=check_plan,
            verification_plan_hash=plan.plan_hash,relations_hash=digest(contract),origin='USER_CONFIRMED',
            oracle_hash=uploaded.get('oracle_hash'),properties_hash=uploaded.get('properties_hash'),
            public_check_hash=digest(public_record) if public_record else None,public_evidence=public_proof,required_checks=self.required_checks(candidate_id,uploaded),
            engine_hash=digest({p.name:sha(p.read_bytes()) for p in files}),native_core=native)
        return c,task,path,contract,public,identity

    def cumulative(self,c,identity):
        refs=[];pairs=[]
        with self.store.connect() as db:rows=db.execute('SELECT candidate_id,report_ref,report_sha256 FROM relation_runs WHERE task_id=?',(c.task_id,)).fetchall()
        for cid,ref,hash_ in sorted(rows,key=lambda r:self.ws.candidate(r[0]).attempt):
            previous=self.ws.candidate(cid)
            if previous.attempt>=c.attempt:continue
            report=self.verify(cid)
            if report['binding']['relations_hash']!=identity['relations_hash']:raise ValueError('累计关系契约变化')
            if report['state']=='UNKNOWN':raise ValueError('先前关系执行结果未知')
            refs.append(dict(candidate_id=cid,report_ref=ref,report_sha256=hash_));pairs.extend(failure_pair(f) for f in report['failures'])
        return refs,pairs

    def interpret_batch(self,batch,contract):
        log=self.read_record(batch['log_ref'],batch['log_sha256']).decode()
        result=relation_trace.interpret(contract,batch['pairs'],batch['token'],log,batch['exit_code'],batch['problem'],required_ids=batch['required_ids'])
        for observation in result['observations']:
            for side in ('left','right'):observation[side]['source']['log_ref']=batch['log_ref']
        for failure in result['failures']:
            for side in ('left','right'):failure[side+'_source']['log_ref']=batch['log_ref']
        return result

    async def batch(self,path,contract,pairs,deadline_at,label,required_ids,report):

        if 'scope' in contract['signature']:
            from nexus.repair import scoped_batches
            token=digest(dict(binding=report['binding'],index=len(report['batches']),label=label,pairs=pairs,required_ids=required_ids))[:16]
            return await scoped_batches.batch(self,path,contract,pairs,deadline_at,label,report,mode='relation',token=token,required_ids=required_ids)
        package,names=self.probe_material(path);manifest=source_manifest(path);index=len(report['batches'])
        token=digest(dict(binding=report['binding'],index=index,label=label,pairs=pairs,required_ids=required_ids))[:16]
        harness=relation_trace.harness(contract,pairs,package,token)
        project=self.store.root/'relations'/uid();project.mkdir(parents=True)
        for name in names:
            raw=(path/name).read_bytes()
            if sha(raw)!=manifest[name]:raise ValueError('关系执行前候选变化')
            dest=project/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
        (project/'src/relation_observations_test.cj').write_bytes(harness)
        h_ref,h_hash=self.write_record(harness,'.relations.cj');l_ref,l_hash=self.write_record(b'','.relations.log')
        batch=dict(label=label,pairs=pairs,required_ids=required_ids,token=token,exit_code=None,problem='BATCH_PENDING',execution_argv=[],
            project_path=project.relative_to(self.store.root).as_posix(),project_manifest=source_manifest(project),
            harness_ref=h_ref,harness_sha256=h_hash,log_ref=l_ref,log_sha256=l_hash)
        report['batches'].append(batch)
        self.store.append_record(report['binding']['task_id'],'event',dict(type='RELATION_BATCH_STARTED',candidate_id=report['candidate_id'],index=index,token=token,harness_ref=h_ref,harness_sha256=h_hash,project_path=batch['project_path']))
        timeout=min(60,max(0,(deadline_at-int(time.time()*1000))/1000));log=''
        try:
            if not timeout:batch['problem']='SEARCH_DEADLINE_EXCEEDED'
            else:batch['exit_code'],log,batch['problem']=await run_command(project,['cjpm','test'],timeout=timeout,private_root=self.store.root,execution_argv=batch['execution_argv'],test_output='all')
            if len(log.encode())>2*1024*1024:batch.update(exit_code=None,problem='OUTPUT_LIMIT');log=''
        except asyncio.CancelledError:
            batch['problem']='CANCELLED';raise
        finally:
            batch['log_ref'],batch['log_sha256']=self.write_record(log.encode(),'.relations.log');batch['result']=self.interpret_batch(batch,contract)
        if source_manifest(project)!=batch['project_manifest'] or source_manifest(path)!=manifest:raise ValueError('关系执行期间源码变化')
        return batch['result']

    @staticmethod
    def conclusion(batches):
        facts=[f for b in batches for f in b['result']['failures']];selected=[];seen=set();coverage={}
        for failure in sorted(facts,key=score):
            key=(failure['relation_id'],relations.pair_key(failure_pair(failure)))
            if key not in seen:seen.add(key);selected.append(failure)
        for batch in batches:
            for relation in batch['result']['per_relation']:
                row=coverage.setdefault(relation['id'],dict(id=relation['id'],generated=0,applicable=0,observed=0,failed=0))
                for field in ('generated','applicable','observed','failed'):row[field]+=relation[field]
        search=len(batches[0]['pairs']) if batches else 0;shrink=sum(len(b['pairs']) for b in batches[1:])
        return dict(failures=selected[:16],failure_count=len(facts),distinct_failure_count=len(selected),failures_truncated=len(selected)>16,
            state='UNKNOWN' if not batches or any(b['result']['state']=='UNKNOWN' for b in batches) else 'FAIL' if facts else 'PASS',
            search_pairs=search,search_calls=search*2,shrink_pairs=shrink,shrink_calls=shrink*2,
            observed_calls=sum(len(b['result']['observations'])*2 for b in batches),per_relation=list(coverage.values()))

    def verify(self,candidate_id):
        binding=self.binding(candidate_id)
        if binding is None:return None
        c,task,path,contract,public,identity=binding
        with self.store.connect() as db:row=db.execute('SELECT state,report_ref,report_sha256 FROM relation_runs WHERE candidate_id=?',(candidate_id,)).fetchone()
        if not row or row[0]=='STARTED':raise ValueError('业务关系尚无已确认结果')
        try:
            report=json.loads(self.read_record(row[1],row[2]));batches=report['batches']
            if digest(report['binding'])!=digest(identity) or report['candidate_id']!=candidate_id or report['state']!=row[0]:raise ValueError('业务关系候选绑定变化')
            expected_meta=dict(schema_version=1,seed=contract['seed'],algorithm=contract['algorithm'],public_test_state=public['state'] if public else 'NOT_RUN')
            if digest({key:report[key] for key in expected_meta})!=digest(expected_meta):raise ValueError('关系报告元数据变化')
            if len(batches)>3:raise ValueError('关系批次超过预算')
            proof=report['native_boundary'];axes=None;refs=[];cumulative=[];generated=None
            if proof is not None:
                data=core.NativeCoreClient().verify_proof(proof,'boundary.axes',boundary_payload(relations.sampler(contract)))
                if set(data)!={'axes'} or proof['component']!=identity['native_core']:raise ValueError('关系原生轴绑定变化')
                axes=oracle.checked_axes(relations.sampler(contract),data['axes']);refs,cumulative=self.cumulative(c,identity)
                generated=relations.generate_pairs(contract,axes,cumulative)
            elif batches or report['state'] in ('PASS','FAIL'):raise ValueError('业务关系缺少原生轴证据')
            if report['regression_refs']!=refs:raise ValueError('累计关系证据变化')
            if digest([report['candidate_checks'],report['regression_pairs']])!=digest([generated['candidate_checks'] if generated else 0,generated['regression_pairs'] if generated else 0]):raise ValueError('关系生成或回归计数变化')
            all_ids=[r['id'] for r in contract['relations']];best=None;package,names=(None,None) if 'scope' in contract['signature'] else self.probe_material(path)
            for index,batch in enumerate(batches):
                scope=all_ids if index==0 else [best['relation_id']] if best else []
                expected=generated['pairs'] if index==0 else relations.shrink_pairs(contract,failure_pair(best),best['relation_id'],axes) if best else []
                if batch['pairs']!=expected or not expected or batch['required_ids']!=scope or batch['label']!=('search' if index==0 else 'shrink'):raise ValueError('关系批次输入对或覆盖范围变化')
                token=digest(dict(binding=identity,index=index,label=batch['label'],pairs=expected,required_ids=scope))[:16]
                if batch['token']!=token:raise ValueError('关系观测标记变化')
                if 'scope' in contract['signature']:
                    from nexus.repair import scoped_batches
                    scoped_batches.verify(self,path,contract,batch,c.id,mode='relation',items=expected,token=token)
                else:
                    harness=relation_trace.harness(contract,expected,package,token)
                    if self.read_record(batch['harness_ref'],batch['harness_sha256'])!=harness:raise ValueError('关系测试程序变化')
                    rel=Path(batch['project_path'])
                    if rel.is_absolute() or len(rel.parts)!=2 or rel.parts[0]!='relations' or not re.fullmatch(r'[0-9a-f]{32}',rel.name):raise ValueError('关系工程引用无效')
                    project=self.store.root/rel;manifest={n:sha((path/n).read_bytes()) for n in names};manifest['src/relation_observations_test.cj']=sha(harness)
                    if project.is_symlink() or project.parent.is_symlink() or batch['project_manifest']!=manifest or source_manifest(project)!=manifest:raise ValueError('关系工程材料变化')
                result=self.interpret_batch(batch,contract)
                if digest(result)!=digest(batch['result']):raise ValueError('业务关系日志与结论不符')
                full_argv=[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']]
                if 'scope' not in contract['signature'] and (batch['execution_argv'] not in [[],full_argv[:1],full_argv] or result['state'] in ('PASS','FAIL') and batch['execution_argv']!=full_argv):raise ValueError('关系执行参数变化')
                if index and batches[index-1]['result']['state']!='FAIL':raise ValueError('关系缩减缺少失败依据')
                failures=result['failures'] if index==0 else [f for f in result['failures'] if f['relation_id']==best['relation_id']]
                if failures:best=min(failures,key=score)
            conclusion=self.conclusion(batches)
            for key,value in conclusion.items():
                if key!='state' and digest(report[key])!=digest(value):raise ValueError('关系反例、覆盖或执行计数变化')
            if report['state']!='UNKNOWN' and report['state']!=conclusion['state']:raise ValueError('关系状态证据不足')
            if report['state'] in ('PASS','FAIL') and (not public or public['state']!='PASS' or any(v['state']!='PASS' for v in identity['required_checks'].values())):raise ValueError('关系前置检查未通过')
            return report
        except (KeyError,TypeError,IndexError,json.JSONDecodeError) as exc:raise ValueError('业务关系报告格式无效') from exc

    async def run(self,candidate_id,deadline_at=None):
        binding=self.binding(candidate_id)
        if binding is None:return None
        c,task,path,contract,public,identity=binding
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE');previous=db.execute('SELECT state FROM relation_runs WHERE candidate_id=?',(candidate_id,)).fetchone()
            if not previous:
                db.execute('INSERT INTO relation_runs VALUES (?,?,?,NULL,NULL)',(candidate_id,task.id,'STARTED'))
                self.store._append_event(db,task.id,dict(type='RELATION_STARTED',candidate_id=candidate_id,tree_hash=identity['tree_hash'],relations_hash=identity['relations_hash']))
        if previous:
            if previous[0]=='STARTED':return dict(state='UNKNOWN',candidate_id=candidate_id,reason='业务关系执行待核实，不自动重放')
            return self.verify(candidate_id)
        deadline_at=min(deadline_at if deadline_at is not None else int(time.time()*1000)+90000,int(time.time()*1000)+90000)
        report=dict(schema_version=1,candidate_id=candidate_id,binding=identity,state='UNKNOWN',public_test_state=public['state'] if public else 'NOT_RUN',
            reason='',batches=[],failures=[],failure_count=0,distinct_failure_count=0,failures_truncated=False,
            search_pairs=0,search_calls=0,shrink_pairs=0,shrink_calls=0,observed_calls=0,per_relation=[],
            candidate_checks=0,regression_pairs=0,regression_refs=[],native_boundary=None,seed=contract['seed'],algorithm=contract['algorithm'],
            limitations=['有限输入对采样；不证明任意输入关系成立','缩减有预算限制，不保证全局最小','累计回归限最多16条保留失败组合，未保留原始失败仍归档',
                'search_calls/shrink_calls为生成测试调用数；observed_calls仅计完整匹配的双侧实际观测','未覆盖操作序列、并发或外部状态'])
        try:
            if identity['native_core'] is None:raise ValueError('关系验证原生组件不可用')
            if not public or public['state']!='PASS' or any(v['state']!='PASS' for v in identity['required_checks'].values()):raise ValueError('公开测试或必需前置检查尚未通过')
            proof=await core.NativeCoreClient().call('boundary.axes',boundary_payload(relations.sampler(contract)),deadline_at=deadline_at)
            if proof['component']!=identity['native_core']:raise ValueError('关系原生组件变化')
            axes=oracle.checked_axes(relations.sampler(contract),proof['response']['data']['axes'])
            refs,cumulative=self.cumulative(c,identity);generated=relations.generate_pairs(contract,axes,cumulative)
            report.update(regression_refs=refs,native_boundary=proof,candidate_checks=generated['candidate_checks'],regression_pairs=generated['regression_pairs'])
            result=await self.batch(path,contract,generated['pairs'],deadline_at,'search',[r['id'] for r in contract['relations']],report)
            if result['state']=='FAIL':
                best=min(result['failures'],key=score)
                for _ in range(2):
                    smaller=relations.shrink_pairs(contract,failure_pair(best),best['relation_id'],axes)
                    if not smaller or int(time.time()*1000)>=deadline_at:break
                    reduced=await self.batch(path,contract,smaller,deadline_at,'shrink',[best['relation_id']],report)
                    if reduced['state']=='UNKNOWN':break
                    failures=[f for f in reduced['failures'] if f['relation_id']==best['relation_id']]
                    if not failures:break
                    best=min(failures,key=score)
            report.update(self.conclusion(report['batches']))
        except (ValueError,OSError,KeyError,StopIteration) as exc:
            report.update(self.conclusion(report['batches']));report.update(state='UNKNOWN',reason=str(exc))
        except asyncio.CancelledError:
            report.update(self.conclusion(report['batches']));report.update(state='UNKNOWN',reason='业务关系执行中断，不自动重放');self.finish(task.id,report);raise
        self.finish(task.id,report)
        return self.verify(candidate_id)

    def finish(self,task_id,report):
        ref,hash_=self.write_record(report,'.relations.json')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute('UPDATE relation_runs SET state=?,report_ref=?,report_sha256=? WHERE candidate_id=? AND state=?',(report['state'],ref,hash_,report['candidate_id'],'STARTED')).rowcount
            if changed!=1:raise ValueError('业务关系完成状态冲突')
            self.store._append_event(db,task_id,dict(type='RELATION_FINISHED',candidate_id=report['candidate_id'],tree_hash=report['binding']['tree_hash'],state=report['state'],report_ref=ref,report_sha256=hash_,relations=report))
