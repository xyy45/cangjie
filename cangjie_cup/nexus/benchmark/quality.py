"""Execute authored defects and reference fixes with the real pinned SDK.

Shards combine uniquely named task functions without rewriting source bytes.
They measure corpus validity, never a model's repair ability.
"""
import hashlib
import json
from pathlib import Path,PurePosixPath
import time

from nexus.adapters.cangjie import report_parser, sdk
from nexus.adapters.cangjie.report_parser import parse_test_report
from nexus.benchmark.corpus import CONFIG,LOCK,encoded,sha,load_corpus
from nexus.benchmark import corpus as corpus_module
from nexus.repair import oracle
from nexus.contracts import digest,source_manifest
from nexus.execution import runner
from nexus.execution.runner import run_command
from nexus.uploads.language import literal


def engine_identity():
    return digest({p.name:sha(p.read_bytes()) for p in (Path(__file__),Path(report_parser.__file__),Path(runner.__file__),Path(sdk.__file__),Path(corpus_module.__file__),Path(oracle.__file__))})


def toolchain_identity():return {p:sha((sdk.SDK/p).read_bytes()) for p in ('bin/cjc','tools/bin/cjpm')}


def harness(task):
    cls='Bench'+task['id'].split('_')[-1]
    text='package bench\nimport std.unittest.*\nimport std.unittest.testmacro.*\n@Test\nclass '+cls+' {\n'
    identities={}
    for group,cases in (('public',task['examples']),('holdout',task['holdout'])):
        identities[group]=[]
        for i,case in enumerate(cases):
            name=group+str(i);identities[group].append(cls+'.'+name)
            text+='@TestCase\nfunc '+name+'() {\n@Expect('+task['function']+'('+', '.join(literal(a) for a in case['args'])+'), '+literal(case['expected'])+')\n}\n'
    return (text+'}\n').encode(),identities


def bundle(tasks,version):
    files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK};cases={}
    for task in tasks:
        for path,raw in task['source' if version=='baseline' else 'reference'].items():
            files['src/'+task['id']+'_'+Path(path).name]=raw
        tests,case_ids=harness(task);files['src/'+task['id']+'_test.cj']=tests;cases[task['id']]=case_ids
    return files,cases


def verdict(parsed,ids):
    states=[parsed.case_results.get(i,'UNKNOWN') for i in ids]
    if not ids or any(s not in ('PASS','FAIL') for s in states):return 'UNKNOWN'
    return 'FAIL' if 'FAIL' in states else 'PASS'


def assess(tasks,batches):
    rows={t['id']:dict(id=t['id'],family=t['family'],variant=t['variant']) for t in tasks}
    for batch in batches:
        parsed=parse_test_report(batch['log']);ids=batch['case_ids'];expected={i for value in ids.values() for group in value.values() for i in group}
        complete=(batch['problem'] is None and parsed.state in ('PASS','FAIL') and set(parsed.case_results)==expected and
            (parsed.state=='PASS' and batch['exit_code']==0 or parsed.state=='FAIL' and type(batch['exit_code']) is int and batch['exit_code']>0))
        for task_id,groups in ids.items():
            row=rows[task_id];version=batch['version'];row[version+'_build']='PASS' if complete else 'UNKNOWN'
            for group,case_ids in groups.items():row[version+'_'+group]=verdict(parsed,case_ids) if complete else 'UNKNOWN'
    result=list(rows.values())
    for row in result:
        row['qualified']=(row.get('baseline_build')=='PASS' and row.get('baseline_holdout')=='FAIL' and
            row.get('reference_build')==row.get('reference_public')==row.get('reference_holdout')=='PASS')
    return result


async def validate_quality(corpus,output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False);(output/'logs').mkdir()
    tasks=corpus['tasks'];batches=[];started=time.monotonic()
    for start in range(0,len(tasks),10):
        selected=tasks[start:start+10]
        for version in ('baseline','reference'):
            name=str(start//10+1)+'-'+version;project=output/'projects'/name;project.mkdir(parents=True)
            files,cases=bundle(selected,version)
            for path,raw in files.items():dest=project/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
            before=source_manifest(project);commands=[]
            code,log,problem=await run_command(project,['cjpm','test'],timeout=90,private_root=output,execution_argv=commands)
            if source_manifest(project)!=before:raise ValueError('质量验证执行时源码变化')
            ref='logs/'+name+'.log';(output/ref).write_text(log)
            batches.append(dict(version=version,task_ids=[t['id'] for t in selected],project_path=project.relative_to(output).as_posix(),
                source_manifest=before,case_ids=cases,exit_code=code,problem=problem,execution_argv=commands,log_ref=ref,log_sha256=sha(log.encode()),log=log))
    rows=assess(tasks,batches)
    result=dict(schema_version=1,kind='CORPUS_QUALITY_NOT_MODEL_EVALUATION',corpus_hash=corpus['corpus_hash'],
        engine_hash=engine_identity(),toolchain=toolchain_identity(),duration_ms=round((time.monotonic()-started)*1000),
        state='PASS' if rows and all(r['qualified'] for r in rows) else 'FAIL',tasks=rows,batches=[{k:v for k,v in b.items() if k!='log'} for b in batches])
    result['result_hash']=digest(result);(output/'result.json').write_bytes(encoded(result));return result


def verify_quality(corpus_root,output):
    output=Path(output).resolve()
    if (output/'result.json').is_symlink():raise ValueError('质量证据不得为链接')
    result=json.loads((output/'result.json').read_bytes())
    if result.get('result_hash')!=digest({k:v for k,v in result.items() if k!='result_hash'}):raise ValueError('质量证据摘要变化')
    corpus=load_corpus(corpus_root,expected_hash=result['corpus_hash']);index={t['id']:t for t in corpus['tasks']}
    if result['engine_hash']!=engine_identity() or result['toolchain']!=toolchain_identity():raise ValueError('质量验证器／SDK版本变化')
    batches=[];selected=[];seen=set()
    for batch in result['batches']:
        if batch['version'] not in ('baseline','reference'):raise ValueError('质量版本无效')
        tasks=[index[i] for i in batch['task_ids']]
        files,cases=bundle(tasks,batch['version']);manifest={p:sha(raw) for p,raw in files.items()}
        if batch['case_ids']!=cases or batch['source_manifest']!=manifest:raise ValueError('质量源码或用例摘要变化')
        for ref in (batch['project_path'],batch['log_ref']):
            path=PurePosixPath(ref)
            if path.is_absolute() or '..' in path.parts or str(path)!=ref or '\\' in ref:raise ValueError('质量证据路径无效')
            actual=output/path
            if actual.is_symlink() or not actual.resolve().is_relative_to(output):raise ValueError('质量证据链接无效')
        project=output/batch['project_path']
        if source_manifest(project)!=manifest:raise ValueError('质量工程摘要变化')
        raw=(output/batch['log_ref']).read_bytes()
        if sha(raw)!=batch['log_sha256']:raise ValueError('质量日志摘要变化')
        batches.append({**batch,'log':raw.decode()})
        for task in tasks:
            key=(task['id'],batch['version'])
            if key in seen:raise ValueError('质量任务版本重复')
            seen.add(key)
            if batch['version']=='baseline':selected.append(task)
    if seen!={(t['id'],v) for t in selected for v in ('baseline','reference')}:raise ValueError('质量任务版本缺失')
    rows=assess(selected,batches);state='PASS' if rows and all(r['qualified'] for r in rows) else 'FAIL'
    if result['tasks']!=rows or result['state']!=state:raise ValueError('质量结论不能从日志重建')
    return result
