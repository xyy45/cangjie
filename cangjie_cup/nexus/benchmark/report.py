"""Reports derived from verified runs; missing and fixture results stay explicit."""
from decimal import Decimal,InvalidOperation
import json
import re
from pathlib import Path

from nexus.benchmark.corpus import encoded
from nexus.benchmark.runner import BUDGET,MODES,verify_run,execution_run_state
from nexus.contracts import digest


def price_contract(prices):
    if prices is None:return None
    if not isinstance(prices,dict) or set(prices)!={'input_per_million','output_per_million','currency'} or prices['currency'] not in ('CNY','USD'):raise ValueError('须明确输入／输出每百万token价格及CNY或USD币种')
    try:
        rates=[Decimal(str(prices[k])) for k in ('input_per_million','output_per_million')]
        if any(not v.is_finite() or v<0 or v>1000000 for v in rates):raise ValueError('价格无效')
    except InvalidOperation as exc:raise ValueError('价格无效') from exc
    return dict(input_per_million=str(rates[0]),output_per_million=str(rates[1]),currency=prices['currency'],
        assumption='All prompt tokens use input rate; cache discounts, taxes and network charges are not included.')


def metrics(rows,prices):
    known=bool(rows) and all(r['usage_state']=='KNOWN' and all(type(r.get(k)) is int and r[k]>=0 for k in ('prompt_tokens','completion_tokens','total_tokens')) for r in rows)
    values={k:sum(r[k] for r in rows) if known else None for k in ('prompt_tokens','completion_tokens','total_tokens')}
    cost=None
    if prices and known:cost=format((Decimal(values['prompt_tokens'])*Decimal(prices['input_per_million'])+Decimal(values['completion_tokens'])*Decimal(prices['output_per_million']))/Decimal(1000000),'.6f')
    repaired=sum(r['verified_repair'] for r in rows)
    def total(key):return sum(r[key] for r in rows) if all(type(r.get(key)) is int and r[key]>=0 for r in rows) else None
    return dict(tasks=len(rows),verified_repairs=repaired,verified_repair_rate=repaired/len(rows) if rows else None,
        complete_runs=sum(r.get('run_state','COMPLETE')=='COMPLETE' for r in rows),
        missing_runs=sum(r.get('run_state')=='MISSING' for r in rows),unfinished_runs=sum(r.get('run_state')=='UNFINISHED' for r in rows),
        unknown_holdout=sum(r['holdout_state'] not in ('PASS','FAIL') for r in rows),
        total_duration_ms=total('duration_ms'),model_requests=total('model_requests'),
        usage_state='KNOWN' if known else 'UNKNOWN',**values,estimated_cost=cost)


def summarize(rows,*,prices=None):
    if not rows:raise ValueError('没有实际评测运行，不能生成成功率')
    rows=[{**r,'run_state':execution_run_state(r)} for r in rows]
    if len({(r['task_id'],r['mode']) for r in rows})!=len(rows) or any(r['mode'] not in MODES or r['origin'] not in ('LIVE','FIXTURE') for r in rows):raise ValueError('评测任务／流程重复或无效')
    price=price_contract(prices);origins={r['origin'] for r in rows};models={tuple(r['model_ids']) for r in rows}
    same_tasks=len({tuple(sorted(r['task_id'] for r in rows if r['mode']==mode)) for mode in MODES})==1
    same_budget=all(r['budget']==BUDGET for r in rows)
    versions={r.get('implementation_hash') for r in rows}
    same_version=len(versions)==1 and all(isinstance(v,str) and re.fullmatch('[0-9a-f]{64}',v) for v in versions)
    common=(same_version and same_tasks and same_budget and len({r['corpus_hash'] for r in rows})==1 and all(r.get('run_state','COMPLETE')=='COMPLETE' for r in rows))
    state=('FIXTURE_ONLY' if origins=={'FIXTURE'} else 'LIVE_COMPARABLE' if origins=={'LIVE'} and common and len(models)==1 and all(len(m)==1 for m in models) else 'INCOMPLETE_OR_MISMATCHED')
    return dict(schema_version=1,comparison_state=state,pricing=price,
        limitations=['团队自建合成任务；参数变体按family披露，不代表独立工业分布。','DIRECT含公开验证反馈；三种模式最多3请求／480秒／每次6000输出tokens。',
            '最终私有验收在循环之后执行，另有60秒上限，不进入任何修复反馈。','FIXTURE不是实际模型修复率；缺少usage或价格时成本为UNKNOWN。'],
        implementation_hashes=sorted(v for v in versions if isinstance(v,str)),
        corpus_hashes=sorted({r['corpus_hash'] for r in rows}),model_ids=sorted({m for r in rows for m in r['model_ids']}),
        modes=[dict(mode=mode,**metrics([r for r in rows if r['mode']==mode],price)) for mode in MODES],
        families=[dict(family=f,**metrics([r for r in rows if r['family']==f],price),
            modes=[dict(mode=m,**metrics([r for r in rows if r['family']==f and r['mode']==m],price)) for m in MODES]) for f in sorted({r['family'] for r in rows})],
        tasks=[{**{k:r[k] for k in ('task_id','family','variant','mode','origin','verified_repair','build_state','public_state','holdout_state','duration_ms','model_requests','prompt_tokens','completion_tokens','total_tokens','usage_state')},'implementation_hash':r.get('implementation_hash'),'task_status':r.get('task_status'),'run_state':r.get('run_state','COMPLETE')} for r in rows])


def cell(value):return 'UNKNOWN' if value is None else str(value).replace('|','\\|').replace('\n',' ')


def markdown(report):
    text='# 仓颉业务缺陷评测\n\n比较状态：'+report['comparison_state']+'\n\n'
    if report.get('cohort_kind')=='DECLARED_PLAN':text+='计划摘要：'+report['plan_hash']+'\n\n计划运行数：'+str(report['planned_runs'])+'，缺失／未完成项保留在分母。\n\n'
    else:text+='统计范围仅限明确提供的结果；没有批次计划，不能代表完整计划的成绩。\n\n'
    text+='\n'.join('- '+s for s in report['limitations'])+'\n\n'
    text+='| 流程 | 统计任务 | 完成 | 缺失 | 未完成 | 可验证修复 | 比例 | 私有验收未知 | 总耗时ms | 请求 | 总tokens | 估算费用 |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n'
    for row in report['modes']:
        text+='| '+' | '.join(cell(row[k]) for k in ('mode','tasks','complete_runs','missing_runs','unfinished_runs','verified_repairs','verified_repair_rate','unknown_holdout','total_duration_ms','model_requests','total_tokens','estimated_cost'))+' |\n'
    text+='\n| 任务 | 业务族／变体 | 流程 | 来源 | 运行状态 | 任务状态 | 构建 | 公开测试 | 私有验收 | 可验证修复 |\n|---|---|---|---|---|---|---|---|---|---|\n'
    for row in report['tasks']:
        text+='| '+' | '.join(cell(v) for v in (row['task_id'],row['family']+'/'+str(row['variant']),row['mode'],row['origin'],row['run_state'],row.get('task_status'),row['build_state'],row['public_state'],row['holdout_state'],row['verified_repair']))+' |\n'
    if report['pricing']:text+='\n计价假设：'+json.dumps(report['pricing'],ensure_ascii=False)+'\n'
    return text


def build_report(corpus_root,run_roots,output,*,prices=None):
    rows=[verify_run(corpus_root,p) for p in run_roots];report=summarize(rows,prices=prices)
    report['cohort_kind']='EXPLICIT_ROWS_ONLY'
    if report['comparison_state']=='LIVE_COMPARABLE':report['comparison_state']='LIVE_UNPLANNED'
    report['runs']=[dict(result_hash=r['result_hash'],task_id=r['task_id'],mode=r['mode']) for r in rows]
    report['report_hash']=digest(report)
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    (output/'report.json').write_bytes(encoded(report));(output/'report.md').write_text(markdown(report));return report
