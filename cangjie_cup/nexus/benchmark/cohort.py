"""Plan-bound reports keep missing/unfinished tasks in their original cohort.

Reading partial evidence never starts/replays a repair or asserts a worker died.
"""
import json
from pathlib import Path,PurePosixPath
import re
import sqlite3
from types import SimpleNamespace

from nexus.benchmark.corpus import encoded,load_corpus,sha
from nexus.benchmark.report import summarize,markdown
from nexus.benchmark.runner import plan_runs,verify_run,record_manifest,usage_metrics,BUDGET,execution_run_state
from nexus.contracts import digest,ModelCall
from nexus.benchmark.identity import implementation_hash


def read_json(path,limit=131072):
    if path.is_symlink():raise ValueError('批次证据不得为链接')
    if path.stat().st_size>limit:raise ValueError('批次证据大小无效')
    return json.loads(path.read_bytes())


def load_plan(corpus,root):
    plan=read_json(root/'plan.json')
    try:
        tasks=list(dict.fromkeys(r['task_id'] for r in plan['runs']));modes=list(dict.fromkeys(r['mode'] for r in plan['runs']))
        canonical=plan_runs(corpus,tasks,modes,max_model_requests=plan['max_model_requests'],origin=plan['origin'])
        if plan.get('schema_version')==2:
            canonical={k:v for k,v in canonical.items() if k not in ('implementation_identity','implementation_hash','plan_hash')}
            canonical['schema_version']=2;canonical['plan_hash']=digest(canonical)
        if canonical!=plan:raise ValueError('批次计划摘要／数据／预算／执行版本变化')
    except (KeyError,TypeError) as exc:raise ValueError('批次计划无效') from exc
    return plan


def expected_binding(plan,slot):
    binding=dict(corpus_hash=plan['corpus_hash'],task_id=slot['task_id'],mode=slot['mode'],origin=plan['origin'],budget=slot['budget'],plan_hash=plan['plan_hash'])
    if plan.get('schema_version')==3:binding['implementation_hash']=plan['implementation_hash']
    return binding


def marker_snapshot(root,binding,*,require_started=False):
    evidence={}
    for marker in ('STARTED.json','ERROR.json'):
        p=root/marker
        if p.exists() or p.is_symlink():
            value=read_json(p)
            if any(value.get(k)!=v for k,v in binding.items()):raise ValueError('未完成运行与计划绑定不符')
            evidence[marker]=sha(p.read_bytes())
    if require_started and 'STARTED.json' not in evidence:raise ValueError('完成结果缺少原始计划绑定')
    return evidence


def incomplete_snapshot(root,binding):
    evidence=marker_snapshot(root,binding);calls=[];calls_known=False;native_task_id=None
    runtime=root/'runtime'
    if runtime.is_symlink():raise ValueError('批次运行证据链接无效')
    if runtime.exists():
        before=record_manifest(SimpleNamespace(root=runtime));database=runtime/'runs.sqlite3'
        if database.is_symlink():raise ValueError('批次数据库不得为链接')
        if database.exists():
            with sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True) as db:
                tasks=db.execute('SELECT id FROM tasks').fetchall()
                if len(tasks)>1:raise ValueError('未完成运行存在多个任务')
                if tasks:
                    native_task_id=tasks[0][0]
                    refs=db.execute("SELECT ref FROM records WHERE task_id=? AND kind='model_call' ORDER BY rowid",(native_task_id,)).fetchall()
                    for ref, in refs:
                        if not isinstance(ref,str) or not re.fullmatch(r'records/[a-f0-9]{32}\.json',ref):raise ValueError('未完成模型原件引用无效')
                        call=ModelCall.model_validate(read_json(runtime/ref,1048576)).model_dump()
                        if call['task_id']!=native_task_id:raise ValueError('未完成模型原件任务不符')
                        for key in ('request_ref','response_ref'):
                            reference=call.get(key)
                            if reference is None:continue
                            p=PurePosixPath(reference)
                            if p.is_absolute() or len(p.parts)!=2 or p.parts[0]!='records' or '..' in p.parts or '\\' in reference or str(p)!=reference or reference not in before:raise ValueError('未完成模型请求原件缺失或引用无效')
                        calls.append(call)
                    calls_known=True
        if record_manifest(SimpleNamespace(root=runtime))!=before:raise ValueError('未完成原件正在变化，请稍后重放')
        evidence['record_manifest']=before
    metrics=usage_metrics(calls)
    if not calls_known:metrics['model_requests']=None
    return dict(native_task_id=native_task_id,evidence=evidence,model_ids=sorted({c['model_id'] for c in calls}),**metrics)


def build_batch_report(corpus_root,batch_root,output,*,prices=None):
    root=Path(batch_root)
    if root.is_symlink():raise ValueError('批次目录不得为链接')
    root=root.resolve();corpus=load_corpus(corpus_root);plan=load_plan(corpus,root)
    index={t['id']:t for t in corpus['tasks']};rows=[];snapshots=[]
    for slot in plan['runs']:
        binding=expected_binding(plan,slot);run=root/(slot['task_id']+'-'+slot['mode'])
        if run.is_symlink():raise ValueError('批次运行目录不得为链接')
        if (run/'result.json').exists() or (run/'result.json').is_symlink():
            markers=marker_snapshot(run,binding,require_started=True)
            result=verify_run(corpus_root,run)
            if any(result.get(k)!=v for k,v in binding.items()):raise ValueError('完成结果与批次计划绑定不符')
            case=index[slot['task_id']]
            if result['family']!=case['family'] or result['variant']!=case['variant']:raise ValueError('完成结果业务族不符')
            rows.append({**result,'run_state':execution_run_state(result)});snapshots.append(dict(task_id=slot['task_id'],mode=slot['mode'],run_state=execution_run_state(result),task_status=result.get('task_status'),result_hash=result['result_hash'],markers=markers))
        else:
            case=index[slot['task_id']];snapshot=incomplete_snapshot(run,binding) if run.exists() else dict(native_task_id=None,evidence={},model_ids=[],model_requests=None,prompt_tokens=None,completion_tokens=None,total_tokens=None,usage_state='UNKNOWN')
            state='UNFINISHED' if run.exists() else 'MISSING'
            rows.append({**binding,'family':case['family'],'variant':case['variant'],'run_state':state,
                'verified_repair':False,'build_state':'UNKNOWN','public_state':'UNKNOWN','holdout_state':'UNKNOWN',
                'duration_ms':None,'repair_duration_ms':None,**{k:v for k,v in snapshot.items() if k!='evidence'}})
            snapshots.append(dict(task_id=slot['task_id'],mode=slot['mode'],run_state=state,**snapshot))
    if load_plan(corpus,root)!=plan:raise ValueError('批次计划在报告期间变化')
    report=summarize(rows,prices=prices)
    report.update(cohort_kind='DECLARED_PLAN',plan_hash=plan['plan_hash'],planned_runs=len(plan['runs']),plan=plan,runs=snapshots,
        completion_state='COMPLETE' if all(r['run_state']=='COMPLETE' for r in rows) else 'INCOMPLETE')
    report['report_hash']=digest(report);target=Path(output);target.mkdir(parents=True,exist_ok=False)
    (target/'report.json').write_bytes(encoded(report));(target/'report.md').write_text(markdown(report));return report
