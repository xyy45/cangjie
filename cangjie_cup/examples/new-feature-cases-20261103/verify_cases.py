"""Actual 4C parser/SDK/native verification, never model or remote MCP calls."""
from pathlib import Path
import asyncio
import json
import sys

ROOT=Path(__file__).resolve().parent
ACTIVE=ROOT.parents[1]/'.runtime/active-stage-4C'
sys.path.insert(0,str(ACTIVE))
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.execution.workspace import WorkspaceStore
from nexus.requirements.service import RequirementService
from nexus.contracts import CandidateProposal,file_hash
from nexus.adapters.cangjie.verifier import CangjieVerifier
from nexus.repair import oracle,properties,relations,sequences
from nexus.repair.exploration import ExplorationService
from nexus.repair.sequence_service import SequenceService
from nexus.projects.index import inspect_project


async def verify(folder,kind):
    data=ROOT/folder;meta=json.loads((data/'案例信息.json').read_bytes())
    files={p.relative_to(data/'工程源码').as_posix():p.read_bytes() for p in (data/'工程源码').rglob('*') if p.is_file()}
    examples=json.loads((data/'输入与预期输出.json').read_bytes());info=inspect_project(files)
    sig=next(f for f in info['functions'] if f['name']==meta['function'])
    if info.get('types'):sig={**sig,'types':info['types']}
    models={}
    for label,module in [('独立业务规则',oracle),('业务属性',properties),('成对关系',relations),('连续操作状态模型',sequences)]:
        path=data/(label+'.json')
        if path.exists():models[label]=json.loads(path.read_bytes());module.validate_contract(models[label],sig,examples)
    runtime=ROOT/'验证原件'/folder;runtime.mkdir(parents=True,exist_ok=False)
    store=RunStore(runtime);uploads=UploadService(store)
    draft=uploads.prepare_project(folder,None,(data/'预期行为.txt').read_text(),actor_id='EXAMPLE_SDK_TEST',request_key='one',entries=files)
    key,label=('oracle_json','独立业务规则') if kind=='oracle' else ('sequences_json','连续操作状态模型')
    uploaded=uploads.confirm(draft['id'],expected_version=1,function=meta['function'],examples_json=json.dumps(examples),consent=True,
        actor_id='EXAMPLE_SDK_TEST',allowed_paths=meta['allowed_paths'],**{key:json.dumps(models[label])})
    source=uploads.source(draft['id'],actor_id='EXAMPLE_SDK_TEST');ws=WorkspaceStore(runtime,registered=[source]);baseline=ws.import_project(source,'.')
    requirements=RequirementService(store);d=requirements.prepare_requirement(draft['id'],uploaded['goal'])
    spec=requirements.confirm_requirement(d['id'],dict(schema_version=1,expected_version=1,requirements=d['requirements'],allowed_paths=d['allowed_paths']),actor_id='EXAMPLE_SDK_TEST')
    task=requirements.prepare_task(draft['id'],spec.id,baseline)
    with store.connect() as db:db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
    results=[]
    for fixed in (False,True):
        edits=[]
        for path in meta['allowed_paths']:
            original=files[path].decode();reference=data/'参考修复_不要上传'/path
            content=reference.read_text() if fixed else original+'\n// local defect validation\n'
            edits.append(dict(path=path,before_hash=file_hash(original),content=content))
        candidate=ws.apply_candidate(store.get_task(task.id),CandidateProposal(edits=edits,requirement_refs=['REQ-UPLOAD']))
        engine=CangjieVerifier(runtime,task.id);build=await engine.build(candidate.id);assert build.state=='PASS',build
        public=await engine.test(candidate.id)
        expected_public='PASS' if fixed or kind=='sequence' else 'FAIL'
        assert public.state==expected_public,public
        independent=None
        # Search is only admitted after the public tests pass.
        if public.state=='PASS':
            service=ExplorationService(store) if kind=='oracle' else SequenceService(store)
            independent=await service.run(candidate.id)
            assert independent['state']==('PASS' if fixed else 'FAIL'),independent
        results.append(dict(candidate='reference' if fixed else 'buggy',build=build.state,public=public.state,
            independent=independent['state'] if independent else 'NOT_RUN_PUBLIC_FAILED',report=independent))
    return dict(case=folder,function=meta['function'],contract_files_validated=list(models),results=results)


async def main():
    result=[]
    for folder,kind in [('案例1_数组退款与跨文件','oracle'),('案例2_对象额度与连续操作','sequence')]:
        row=await verify(folder,kind);result.append(row)
        print(json.dumps(dict(case=folder,states=[{k:v for k,v in r.items() if k!='report'} for r in row['results']]),ensure_ascii=False),flush=True)
    report=dict(state='PASS',origin='REAL_LOCAL_SDK_WITH_HANDWRITTEN_REFERENCE',model_calls=0,remote_mcp_calls=0,cases=result)
    (ROOT/'本地验证结果.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':asyncio.run(main())
