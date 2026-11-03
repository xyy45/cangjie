"""Local CLI. list/plan/replay never send model requests."""
import argparse
import asyncio
import json
from pathlib import Path

from nexus.benchmark.corpus import load_corpus,encoded
from nexus.benchmark.quality import validate_quality,verify_quality
from nexus.benchmark.report import build_report
from nexus.benchmark.cohort import build_batch_report,expected_binding
from nexus.benchmark.runner import plan_runs,run_case,trial_stop_reason


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--corpus',default='fixtures/benchmark/v1')
    sub=parser.add_subparsers(dest='command',required=True);sub.add_parser('list')
    for action in ('plan','run'):
        p=sub.add_parser(action);p.add_argument('--tasks',required=True);p.add_argument('--modes',required=True);p.add_argument('--max-model-requests',type=int,required=True)
        if action=='run':p.add_argument('--output',required=True)
    p=sub.add_parser('quality');p.add_argument('--output',required=True)
    p=sub.add_parser('verify-quality');p.add_argument('--output',required=True)
    p=sub.add_parser('trajectory');p.add_argument('--run',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('report');scope=p.add_mutually_exclusive_group(required=True);scope.add_argument('--runs',nargs='+');scope.add_argument('--batch');p.add_argument('--output',required=True);p.add_argument('--prices-json')
    args=parser.parse_args();corpus=load_corpus(args.corpus)
    if args.command=='list':
        result=dict(corpus_hash=corpus['corpus_hash'],count=len(corpus['tasks']),families=len({t['family'] for t in corpus['tasks']}),tasks=[{k:t[k] for k in ('id','family','variant','goal')} for t in corpus['tasks']])
    elif args.command in ('plan','run'):
        plan=plan_runs(corpus,args.tasks.split(','),args.modes.split(','),max_model_requests=args.max_model_requests)
        result=plan
        if args.command=='run':
            root=Path(args.output).resolve();root.mkdir(parents=True,exist_ok=False);(root/'plan.json').write_bytes(encoded(plan))
            async def execute():
                results=[];index={t['id']:t for t in corpus['tasks']}
                for row in plan['runs']:
                    directory=root/(row['task_id']+'-'+row['mode'])
                    try:r=await run_case(corpus,index[row['task_id']],row['mode'],directory,plan_hash=plan['plan_hash'],expected_implementation_hash=plan['implementation_hash'])
                    except Exception as exc:
                        error=dict(plan_hash=plan['plan_hash'],task_id=row['task_id'],mode=row['mode'],error_type=type(exc).__name__)
                        (root/'STOPPED.json').write_bytes(encoded(error))
                        if not directory.is_symlink() and (not directory.exists() or directory.is_dir()):
                            directory.mkdir(exist_ok=True)
                            marker=directory/'ERROR.json'
                            if not marker.exists():
                                with marker.open('xb') as f:f.write(encoded({**expected_binding(plan,row),'error_type':type(exc).__name__}))
                        return dict(batch_state='STOPPED',completed=results,stopped=error)
                    results.append(dict(task_id=r['task_id'],mode=r['mode'],verified_repair=r['verified_repair'],status=r['task_status']))
                    reason=trial_stop_reason(r)
                    if reason:
                        stopped={**expected_binding(plan,row),'reason':reason,'task_status':r['task_status']}
                        (root/'STOPPED.json').write_bytes(encoded(stopped))
                        return dict(batch_state='IN_DOUBT' if r['task_status']=='IN_DOUBT' else 'STOPPED',completed=results,stopped=stopped)
                return dict(batch_state='COMPLETE',completed=results)
            result=dict(plan=plan,**asyncio.run(execute()))
    elif args.command=='quality':
        r=asyncio.run(validate_quality(corpus,args.output));result=dict(state=r['state'],qualified=sum(t['qualified'] for t in r['tasks']),total=len(r['tasks']),result_hash=r['result_hash'])
    elif args.command=='verify-quality':
        r=verify_quality(args.corpus,args.output);result=dict(state=r['state'],total=len(r['tasks']),result_hash=r['result_hash'])
    elif args.command=='trajectory':
        from nexus.benchmark.trajectory import analyze_run
        r=analyze_run(args.corpus,args.run)
        with Path(args.output).open('xb') as stream:stream.write(encoded(r))
        result=dict(state=r['state'],trajectory_hash=r['trajectory_hash'])
    else:
        prices=json.loads(Path(args.prices_json).read_text()) if args.prices_json else None
        r=(build_batch_report(args.corpus,args.batch,args.output,prices=prices) if args.batch else build_report(args.corpus,args.runs,args.output,prices=prices));result=dict(comparison_state=r['comparison_state'],report_hash=r['report_hash'])
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.command in ('quality','verify-quality') and result['state']!='PASS':raise SystemExit(1)
    if args.command=='run' and result['batch_state']!='COMPLETE':raise SystemExit(1)


if __name__=='__main__':main()
