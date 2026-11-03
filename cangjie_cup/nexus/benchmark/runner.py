"""Three bounded repair treatments followed by the same private final grading."""
import io
import json
import re
from pathlib import Path
import time
import zipfile

from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.analysis.repair import RepairAnalysis
from nexus.analysis.service import AnalysisService
from nexus.benchmark.corpus import encoded,sha,load_corpus,public_material
from nexus.benchmark.quality import toolchain_identity
from nexus.benchmark.identity import implementation_identity,implementation_hash
from nexus.contracts import digest,source_manifest
from nexus.demo.deepseek import DeepSeekProvider
from nexus.execution.workspace import WorkspaceStore
from nexus.repair.cegis_loop import RepairLoop
from nexus.repair.exploration import ExplorationService
from nexus.repair.focus_service import FocusService
from nexus.requirements.service import RequirementService
from nexus.store import RunStore
from nexus.uploads.service import UploadService

MODES=('direct','mcp','cegis')
BUDGET=dict(max_rounds=3,timeout_seconds=480,max_output_tokens=6000,temperature=0.2)


def plan_runs(corpus,task_ids,modes,*,max_model_requests,origin='LIVE'):
    index={t['id']:t for t in corpus['tasks']}
    if (origin not in ('LIVE','FIXTURE') or not isinstance(task_ids,list) or not task_ids or len(set(task_ids))!=len(task_ids) or not set(task_ids)<=set(index) or
            not isinstance(modes,list) or not modes or len(set(modes))!=len(modes) or not set(modes)<=set(MODES)):
        raise ValueError('必须明确唯一任务和流程')
    required=len(task_ids)*len(modes)*3
    if type(max_model_requests) is not int or max_model_requests<required:raise ValueError('请求预算小于所选任务的最大请求数')
    implementation=implementation_identity()
    plan=dict(schema_version=3,implementation_identity=implementation,implementation_hash=digest(implementation),origin=origin,corpus_hash=corpus['corpus_hash'],max_model_requests=required,
        max_completion_tokens=required*6000,prompt_tokens='UNKNOWN_UNTIL_EXECUTED',
        runs=[dict(task_id=t,mode=m,budget=dict(BUDGET)) for t in task_ids for m in modes])
    return {**plan,'plan_hash':digest(plan)}


def execution_run_state(result):
    if result.get('run_state') in ('MISSING','UNFINISHED'):return result['run_state']
    if result.get('task_status') in ('READY','DIAGNOSING','GENERATING','APPLYING','BUILDING','TESTING','EXPORTING','IN_DOUBT'):
        return 'UNFINISHED'
    return 'COMPLETE'


def trial_stop_reason(result):
    if result.get('task_status') not in ('REVIEW_PENDING','UNREPAIRED'):
        return 'TASK_NOT_COMPLETED'
    if any(result.get(k) in ('UNKNOWN','UNAVAILABLE') for k in ('build_state','public_state','holdout_state','independent_search_state')):
        return 'VERIFICATION_UNKNOWN'
    if result.get('candidate_id') and any(result.get(k) not in ('PASS','FAIL') for k in ('build_state','holdout_state')):
        return 'VERIFICATION_NOT_COMPLETED'
    return None


def usage_metrics(calls):
    starts=[r for r in calls if r['status']=='STARTED'];results={r['id']:r for r in calls if r['status']!='STARTED'}
    metrics=dict(model_requests=len(starts),prompt_tokens=None,completion_tokens=None,total_tokens=None,usage_state='UNKNOWN')
    values=[]
    for row in starts:
        result=results.get(row['id']+'-result');usage=result.get('usage',{}) if result else {}
        if not result or any(type(usage.get(k)) is not int or usage[k]<0 for k in ('prompt_tokens','completion_tokens','total_tokens')) or usage['total_tokens']!=usage['prompt_tokens']+usage['completion_tokens']:
            return metrics
        values.append(usage)
    if values:metrics.update({k:sum(v[k] for v in values) for k in ('prompt_tokens','completion_tokens','total_tokens')});metrics['usage_state']='KNOWN'
    return metrics


def material_hash(case):
    public=public_material(case);public['files']={p:sha(raw) for p,raw in public['files'].items()};return digest(public)


def record_manifest(store):
    if store.root.is_symlink() or (store.root/'records').is_symlink():raise ValueError('评测原件目录不得为链接')
    files={}
    for p in (store.root/'records').rglob('*'):
        if p.is_symlink():raise ValueError('评测原件不得使用链接')
        if p.is_file():files[p.relative_to(store.root).as_posix()]=sha(p.read_bytes())
    return files


def prepare(store,case,mode):
    data=public_material(case);buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w') as z:
        for p,raw in sorted(data['files'].items()):z.writestr(zipfile.ZipInfo(p),raw)
    uploads=UploadService(store);draft=uploads.prepare_project(data['id']+'.zip',buf.getvalue(),data['goal'],actor_id='BENCHMARK',request_key='benchmark')
    uploads.confirm(draft['id'],expected_version=1,function=data['function'],examples_json=json.dumps(data['examples']),
        oracle_json=json.dumps(case['oracle']) if mode=='cegis' else None,consent=True,actor_id='BENCHMARK',allowed_paths=data['allowed_paths'])
    root=uploads.source(draft['id'],actor_id='BENCHMARK');baseline=WorkspaceStore(store.root,registered=[root]).import_project(root,'.')
    requirements=RequirementService(store);spec_draft=requirements.prepare_requirement(draft['id'],data['goal'])
    spec=requirements.confirm_requirement(spec_draft['id'],dict(schema_version=1,expected_version=1,requirements=spec_draft['requirements'],allowed_paths=data['allowed_paths']),actor_id='BENCHMARK')
    task=requirements.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    return task


def selected_candidate(store,task_id):
    candidates=store.records(task_id,'candidate');events=store.records(task_id,'event')
    selected=[e['selected_candidate_id'] for e in events if e.get('selected_candidate_id')]
    identity=selected[-1] if selected else candidates[-1]['id'] if candidates else None
    return next((c for c in candidates if c['id']==identity),None)


def grade_summary(store,task_id,case,mode,holdout):
    task=store.get_task(task_id);candidate=selected_candidate(store,task_id)
    build=public='NOT_RUN';independent='NOT_ENABLED' if mode!='cegis' else 'NOT_RUN'
    tree=None;holdout_state='NOT_RUN'
    if candidate:
        path,tree,plan=CangjieVerifier(store.root,task_id).identity(candidate['id'])
        if tree!=candidate['tree_hash']:raise ValueError('评测候选树变化')
        checks=[r for r in store.records(task_id,'check') if r['subject_id']==candidate['id'] and r['tree_hash']==tree and r['plan_hash']==plan]
        for kind in ('build','test'):
            rows=[r for r in checks if r['kind']==kind];state=rows[-1]['state'] if rows else 'NOT_RUN'
            if kind=='build':build=state
            else:public=state
        if mode=='cegis':
            service=ExplorationService(store)
            with store.connect() as db:search_state=db.execute('SELECT state FROM exploration_runs WHERE candidate_id=?',(candidate['id'],)).fetchone()
            if search_state is None:independent='NOT_RUN'
            elif search_state[0]=='STARTED':independent='UNKNOWN'
            else:
                search=service.verify(candidate['id']);independent=search['state']
        if holdout is not None:
            if holdout['candidate_id']!=candidate['id'] or holdout['tree_hash']!=tree:raise ValueError('验收版本变化')
            batch=holdout['batch'];service=ExplorationService(store)
            inputs=[e['args'] for e in case['holdout']]
            if batch['inputs']!=inputs or batch['label']!='FINAL_HOLDOUT_NOT_FEEDBACK':raise ValueError('验收输入变化')
            # Copy bytes and test harness must still be the original grading material.
            project=store.root/batch['project_path']
            if project.is_symlink() or not project.resolve().is_relative_to(store.root):raise ValueError('验收工程路径无效')
            if source_manifest(project)!=batch['project_manifest']:raise ValueError('验收工程摘要变化')
            package,names=service.probe_material(path)
            for name in names:
                if (project/name).read_bytes()!=(path/name).read_bytes():raise ValueError('验收源码不等于最终候选')
            expected_harness=service.harness(case['normalized_oracle'],inputs,package)
            if service.read_record(batch['harness_ref'],batch['harness_sha256'])!=expected_harness or (project/'src/boundary_test.cj').read_bytes()!=expected_harness:raise ValueError('验收测试摘要变化')
            holdout_state=service.interpret(batch,case['normalized_oracle'])['state']
    calls=store.records(task_id,'model_call');models=sorted({c['model_id'] for c in calls})
    return dict(task_status=task.status,candidate_id=candidate['id'] if candidate else None,tree_hash=tree,
        build_state=build,public_state=public,holdout_state=holdout_state,independent_search_state=independent,
        verified_repair=build==public==holdout_state=='PASS' and (mode!='cegis' or independent=='PASS'),
        attempt_count=task.attempt_count,model_ids=models,**usage_metrics(calls))


async def run_case(corpus,case,mode,output,*,origin='LIVE',provider_factory=DeepSeekProvider,analysis_factory=None,plan_hash=None,expected_implementation_hash=None):
    if mode not in MODES or origin not in ('LIVE','FIXTURE'):raise ValueError('评测流程或来源无效')
    if plan_hash is not None and (not isinstance(plan_hash,str) or not re.fullmatch(r'[a-f0-9]{64}',plan_hash)):raise ValueError('评测计划摘要无效')
    if origin=='LIVE' and provider_factory is not DeepSeekProvider:raise ValueError('真实模型标记只允许真实提供器')
    execution_hash=implementation_hash()
    if expected_implementation_hash is not None and expected_implementation_hash!=execution_hash:raise ValueError('执行版本与计划不符')
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    # This marker is never removed: uncertain/failed runs cannot silently replay.
    (output/'STARTED.json').write_bytes(encoded(dict(corpus_hash=corpus['corpus_hash'],task_id=case['id'],mode=mode,origin=origin,budget=BUDGET,plan_hash=plan_hash,implementation_hash=execution_hash)))
    store=RunStore(output/'runtime');task=prepare(store,case,mode);kwargs={}
    if mode!='direct':
        analysis=analysis_factory(store) if analysis_factory else AnalysisService(store.root)
        kwargs=dict(context_enricher=RepairAnalysis(store,analysis).enrich,focus_enricher=FocusService(store).enrich)
    started=time.monotonic();await RepairLoop(store,provider_factory=provider_factory,**kwargs).run(task.id)
    repair_ms=round((time.monotonic()-started)*1000);candidate=selected_candidate(store,task.id);holdout=None
    if candidate:
        path,tree,_=CangjieVerifier(store.root,task.id).identity(candidate['id']);service=ExplorationService(store)
        batch,_=await service.batch(path,case['normalized_oracle'],[e['args'] for e in case['holdout']],int(time.time()*1000)+60000,'FINAL_HOLDOUT_NOT_FEEDBACK')
        holdout=dict(candidate_id=candidate['id'],tree_hash=tree,batch=batch)
    if implementation_hash()!=execution_hash:raise ValueError('运行期间执行版本变化，结果未封存')
    result=dict(schema_version=2,implementation_hash=execution_hash,kind='MODEL_REPAIR_EVALUATION',origin=origin,corpus_hash=corpus['corpus_hash'],
        task_id=case['id'],native_task_id=task.id,family=case['family'],variant=case['variant'],mode=mode,budget=dict(BUDGET),plan_hash=plan_hash,
        public_material_hash=material_hash(case),toolchain=toolchain_identity(),repair_duration_ms=repair_ms,
        duration_ms=round((time.monotonic()-started)*1000),holdout=holdout,holdout_budget_seconds=60,
        **grade_summary(store,task.id,case,mode,holdout),record_manifest=record_manifest(store))
    result['result_hash']=digest(result);(output/'result.json').write_bytes(encoded(result));return result


def verify_run(corpus_root,output):
    output=Path(output)
    if output.is_symlink():raise ValueError('评测目录不得为链接')
    output=output.resolve()
    if (output/'result.json').is_symlink():raise ValueError('评测结果不得为链接')
    result=json.loads((output/'result.json').read_bytes())
    if result.get('result_hash')!=digest({k:v for k,v in result.items() if k!='result_hash'}):raise ValueError('评测结果摘要变化')
    started_path=output/'STARTED.json'
    if started_path.is_symlink():raise ValueError('原始运行绑定不得为链接')
    started=json.loads(started_path.read_bytes())
    if any(started.get(k)!=result.get(k) for k in ('corpus_hash','task_id','mode','origin','budget','plan_hash','implementation_hash')):raise ValueError('结果与原始运行绑定不符')
    if result.get('schema_version')==2 and result.get('implementation_hash')!=implementation_hash():raise ValueError('执行版本与封存结果不符')
    corpus=load_corpus(corpus_root,expected_hash=result['corpus_hash']);case=next(t for t in corpus['tasks'] if t['id']==result['task_id'])
    if result['public_material_hash']!=material_hash(case) or result['budget']!=BUDGET or result['toolchain']!=toolchain_identity():raise ValueError('评测数据／预算／SDK版本变化')
    runtime=output/'runtime'
    if runtime.is_symlink() or (runtime/'records').is_symlink():raise ValueError('评测原件目录不得为链接')
    store=RunStore(runtime)
    if record_manifest(store)!=result['record_manifest']:raise ValueError('评测原件摘要变化')
    summary=grade_summary(store,result['native_task_id'],case,result['mode'],result['holdout'])
    if any(result[k]!=v for k,v in summary.items()):raise ValueError('评测结论不能从原件重建')
    if result.get('schema_version')==2 and result.get('implementation_hash')!=implementation_hash():raise ValueError('核验期间执行版本变化')
    return result
