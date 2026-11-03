"""Write sealed compound-rule tasks without changing the legacy generator."""
from pathlib import Path

from nexus.benchmark.corpus import CONFIG,LOCK,encoded,sha
from nexus.benchmark.hard_catalog import VERSION,tasks
from nexus.contracts import digest
from nexus.projects.index import inspect_project
from nexus.repair import oracle


def build_hard_corpus(root,count=10):
    authored=tasks(count)
    root=Path(root);root.mkdir(parents=True,exist_ok=False);files={};task_paths=[]
    for number,task in enumerate(authored):
        index=inspect_project({'cjpm.toml':CONFIG,'cjpm.lock':LOCK,**task['source']})
        signature=next(f for f in index['functions'] if f['name']==task['function'])
        rule=dict(version=1,function=task['function'],domains=task['domains'],expression=task['expression'],seed=45127+number,max_cases=32)
        normalized=oracle.validate_contract(rule,signature,[])
        examples=[dict(args=a,expected=oracle.expected(normalized,a),suite='target' if i==0 else 'regression') for i,a in enumerate(task['public_inputs'])]
        held_rule=oracle.validate_contract({**rule,'seed':rule['seed']+27183,'max_cases':64},signature,[])
        seen={oracle.input_key(e['args']) for e in examples};held=[]
        for args in oracle.generate_inputs(held_rule)+task['holdout_witnesses']:
            key=oracle.input_key(args)
            if key not in seen:
                seen.add(key);held.append(dict(args=args,expected=oracle.expected(normalized,args)))
        search={**rule,'version':2,'excluded_inputs':[e['args'] for e in held]}
        oracle.validate_contract(search,signature,examples)
        meta={k:task[k] for k in ('id','family','variant','function','goal','defect')}
        meta.update(kind=signature['return_type'],provenance='TEAM_AUTHORED_SYNTHETIC',allowed_paths=sorted(task['source']))
        prefix='tasks/'+task['id']+'/'
        material={'task.json':encoded(meta),'public/goal.txt':(task['goal']+'\n').encode(),'public/examples.json':encoded(examples),
                  'public/cjpm.toml':CONFIG,'public/cjpm.lock':LOCK,'private/rule.json':encoded(search),
                  'private/grading-rule.json':encoded(rule),'private/holdout.json':encoded(held)}
        material.update({'public/'+p:raw for p,raw in task['source'].items()})
        material.update({'private/reference/'+p:raw for p,raw in task['reference'].items()})
        for name,raw in material.items():
            dest=root/(prefix+name);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);files[prefix+name]=sha(raw)
        task_paths.append(prefix+'task.json')
    manifest=dict(schema_version=1,generator=VERSION,count=count,tasks=task_paths,files=files)
    manifest['corpus_hash']=digest(manifest);(root/'manifest.json').write_bytes(encoded(manifest));return manifest['corpus_hash']
