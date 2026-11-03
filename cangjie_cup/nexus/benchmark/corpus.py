"""Byte-bound synthetic data, with separate public material and private answers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path,PurePosixPath

from nexus.benchmark.catalog import VERSION,families
from nexus.benchmark.hard_catalog import VERSION as HARD_VERSION
from nexus.contracts import digest
from nexus.projects.index import inspect_project
from nexus.repair import oracle

CONFIG=b'[package]\nname = "bench"\nversion = "1.0.0"\ncjc-version = "1.0.5"\noutput-type = "static"\n\n[dependencies]\n'
LOCK=b'version = 0\n[requires]\n'


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()


def _source(name,params,kind,body):
    args=', '.join(p+': '+('Bool' if p=='v' else 'Int64') for p in params)
    return ('package bench\n\npublic func '+name+'('+args+'): '+kind+' {\n    '+body.replace('\n','\n    ')+'\n}\n').encode()


def build_corpus(root,count=30):
    if type(count) is not int or count not in (30,100):raise ValueError('数据集规模只支持30或100')
    root=Path(root);root.mkdir(parents=True,exist_ok=False);files={};task_paths=[]
    for i in range(count):
        variant=i//30+1;family,params,kind,goal,bad,good,expression,witness=families(variant)[i%30]
        task_id=f'business_{i+1:03}';function=f'calc{i+1:03}';helper=f'helper{i+1:03}'
        source={'src/logic.cj':_source(function,params,kind,bad.replace('helper(',helper+'('))}
        reference={'src/logic.cj':_source(function,params,kind,good.replace('helper(',helper+'('))}
        if family=='cross_file_fee':
            source['src/amount.cj']=_source(helper,['x'],'Int64','return x+1')
            reference['src/amount.cj']=_source(helper,['x'],'Int64','return x')
        domains={p:({} if p=='v' else dict(min=-2 if family in ('quantity','price','page_size') or family=='ledger_balance' and p=='y' else 1 if family=='installment' and p=='y' else 0,
            max=1000,points=list(dict.fromkeys([witness[j],10+variant*3,3+variant])))) for j,p in enumerate(params)}
        rule=dict(version=1,function=function,domains=domains,expression=expression,seed=1729+i,max_cases=32)
        index=inspect_project({'cjpm.toml':CONFIG,'cjpm.lock':LOCK,**source})
        signature=next(f for f in index['functions'] if f['name']==function)
        normalized=oracle.validate_contract(rule,signature,[])
        # Public tests are deliberately small. Final holdout inputs are disjoint.
        inputs=[[False if p=='v' else domains[p]['min'] for p in params],[True if p=='v' else domains[p]['max'] for p in params]]
        examples=[dict(args=a,expected=oracle.expected(normalized,a),suite=s) for a,s in zip(inputs,['target','regression'])]
        # Separate sealed pool; v2 reserves exact typed rows from ALL feedback
        # paths, including shrinking. Final grading retains the unfiltered v1 rule.
        grading_rule=dict(rule)
        held_rule=oracle.validate_contract({**grading_rule,'seed':rule['seed']+27183,'max_cases':64},signature,[])
        candidates=oracle.generate_inputs(held_rule)+[witness]
        keys={json.dumps(a) for a in inputs};holdout=[]
        for a in candidates:
            key=json.dumps(a)
            if key not in keys:
                keys.add(key);holdout.append(dict(args=a,expected=oracle.expected(normalized,a)))
        rule={**rule,'version':2,'excluded_inputs':[e['args'] for e in holdout]}
        oracle.validate_contract(rule,signature,examples)
        meta=dict(id=task_id,family=family,variant=variant,function=function,kind=kind,
                  provenance='TEAM_AUTHORED_SYNTHETIC',goal=goal,allowed_paths=sorted(source))
        prefix='tasks/'+task_id+'/'
        entries={'task.json':encoded(meta),'public/goal.txt':(goal+'\n').encode(),'public/examples.json':encoded(examples),
                 'public/cjpm.toml':CONFIG,'public/cjpm.lock':LOCK,'private/rule.json':encoded(rule),'private/grading-rule.json':encoded(grading_rule),'private/holdout.json':encoded(holdout)}
        entries.update({'public/'+p:raw for p,raw in source.items()})
        entries.update({'private/reference/'+p:raw for p,raw in reference.items()})
        for name,raw in entries.items():
            path=root/(prefix+name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);files[prefix+name]=sha(raw)
        task_paths.append(prefix+'task.json')
    manifest=dict(schema_version=1,generator=VERSION,count=count,tasks=task_paths,files=files)
    manifest['corpus_hash']=digest(manifest);(root/'manifest.json').write_bytes(encoded(manifest))
    return manifest['corpus_hash']


def load_corpus(root,*,expected_hash=None,limit=None):
    root=Path(root)
    if root.is_symlink() or (root/'manifest.json').is_symlink():raise ValueError('数据集不得使用链接')
    manifest=json.loads((root/'manifest.json').read_bytes());identity=manifest.get('corpus_hash')
    if identity!=digest({k:v for k,v in manifest.items() if k!='corpus_hash'}):raise ValueError('数据集清单摘要变化')
    if expected_hash is not None and expected_hash!=identity:raise ValueError('数据集版本变化')
    profiles={VERSION:(30,100),HARD_VERSION:(10,30)}
    version=manifest.get('generator');count=manifest.get('count')
    if (manifest.get('schema_version')!=1 or type(version) is not str or type(count) is not int or
            count not in profiles.get(version,())):raise ValueError('数据集版本无效')
    if not isinstance(manifest.get('files'),dict) or len(manifest['files'])>1400:raise ValueError('数据集清单无效')
    actual=set()
    for p in root.rglob('*'):
        if p.is_symlink():raise ValueError('数据集不得使用链接')
        if p.is_file() and p.name!='manifest.json':actual.add(p.relative_to(root).as_posix())
    if actual!=set(manifest['files']):raise ValueError('数据集文件清单变化')
    raw={}
    for name,identity_file in manifest['files'].items():
        path=PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or '\\' in name or str(path)!=name:raise ValueError('数据集路径无效')
        data=(root/name).read_bytes()
        if len(data)>131072 or sha(data)!=identity_file:raise ValueError('数据集文件摘要变化')
        raw[name]=data
    task_paths=manifest['tasks']
    if len(task_paths)!=manifest['count'] or len(set(task_paths))!=len(task_paths):raise ValueError('任务清单无效')
    tasks=[]
    for name in task_paths:
        meta=json.loads(raw[name]);prefix='tasks/'+meta['id']+'/'
        if name!=prefix+'task.json' or not meta['id'].startswith('business_'):raise ValueError('任务路径无效')
        public={p[len(prefix+'public/'):]:v for p,v in raw.items() if p.startswith(prefix+'public/')}
        source={p:v for p,v in public.items() if p.endswith('.cj')}
        reference={p[len(prefix+'private/reference/'):]:v for p,v in raw.items() if p.startswith(prefix+'private/reference/')}
        files={p:v for p,v in public.items() if p not in ('goal.txt','examples.json')}
        index=inspect_project(files);reference_index=inspect_project({**files,**reference})
        if sorted(source)!=meta['allowed_paths'] or set(source)!=set(reference) or index['functions']!=reference_index['functions']:
            # Full metadata includes spans/calls, which may legitimately differ.
            stable=lambda value:[{k:f[k] for k in ('name','params','return_type','public','path')} for f in value['functions']]
            if sorted(source)!=meta['allowed_paths'] or set(source)!=set(reference) or stable(index)!=stable(reference_index):raise ValueError('参考工程接口变化')
        examples=json.loads(public['examples.json']);holdout=json.loads(raw[prefix+'private/holdout.json']);rule=json.loads(raw[prefix+'private/rule.json'])
        if not examples or not holdout or {'target','regression'}!={e.get('suite') for e in examples}:raise ValueError('公开／验收用例无效')
        signature=next(f for f in index['functions'] if f['name']==meta['function'])
        grading_rule=json.loads(raw[prefix+'private/grading-rule.json'])
        if grading_rule.get('version')!=1:raise ValueError('最终验收必须使用无排除的v1规则')
        normalized=oracle.validate_contract(grading_rule,signature,examples+holdout)
        search=oracle.validate_contract(rule,signature,examples)
        if rule.get('version')!=2 or {oracle.input_key(a) for a in rule['excluded_inputs']}!={oracle.input_key(e['args']) for e in holdout}:raise ValueError('搜索排除集合与冻结验收输入不一致')
        if {k:v for k,v in rule.items() if k not in ('version','excluded_inputs')}!={k:v for k,v in grading_rule.items() if k!='version'}:raise ValueError('搜索与验收业务规则不一致')
        public_keys={json.dumps(e['args']) for e in examples}
        if len({json.dumps(e['args']) for e in holdout})!=len(holdout) or any(json.dumps(e['args']) in public_keys for e in holdout):raise ValueError('验收用例与公开用例重叠')
        if public['goal.txt'].decode().strip()!=meta['goal']:raise ValueError('任务需求不一致')
        tasks.append({**meta,'source':source,'reference':reference,'files':files,'examples':examples,'holdout':holdout,'oracle':rule,'normalized_oracle':normalized})
    if len({t['id'] for t in tasks})!=len(tasks):raise ValueError('任务标识重复')
    if limit is not None:
        if type(limit) is not int or not 1<=limit<=len(tasks):raise ValueError('任务数量无效')
        tasks=tasks[:limit]
    return dict(schema_version=1,corpus_hash=identity,generator=manifest['generator'],tasks=tasks)


def public_material(task):
    return deepcopy({k:task[k] for k in ('id','goal','function','allowed_paths','files','examples')})
