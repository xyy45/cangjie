"""Source-bound analysis evidence for the registered repair demonstration."""
import asyncio
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from nexus.analysis.normalize import validate_source, LIMITATIONS
from nexus.contracts import digest, tree_hash
from nexus.execution.workspace import WorkspaceStore
from nexus.scenarios import get_profile


def verify_evidence(store,event):
    report=event['analysis_context']
    if digest(report)!=event['context_hash']:raise ValueError('Analysis context changed')
    task=store.get_task(event['task_id']);ws=WorkspaceStore(store.root)
    if tree_hash(ws.verify_baseline(task.baseline_id))!=report['baseline_hash'] or task.baseline_id!=report['baseline_id']:
        raise ValueError('Analysis baseline changed')
    for entry in report['files']:
        if hashlib.sha256(ws.safe_file(task.baseline_id,entry['path']).read_bytes()).hexdigest()!=entry['source_sha256']:
            raise ValueError('Analysis file binding changed')
    for entry in event['evidence_files']:
        ref=Path(entry['record_ref'])
        if ref.parent!=Path('records') or ref.is_absolute():raise ValueError('Invalid analysis evidence reference')
        path=store.root/ref
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
            raise ValueError('Analysis evidence changed')
    return deepcopy(report)


class RepairAnalysis:
    def __init__(self,store,service):
        self.store,self.service=store,service

    async def enrich(self,task,context):
        project=context.get('requirements',{}).get('project_id')
        if not project:return
        from nexus.requirements.service import RequirementService
        profile=RequirementService(self.store).profile(project)
        if not set(task.allowed_paths)<=set(profile['allowed_paths']):
            raise ValueError('Analysis scope differs from registered profile')
        if task.schema_version == 2:
            from nexus.requirements.service import RequirementService
            spec,_=RequirementService(self.store).task_context(task)
            if spec.project_id!=project:raise ValueError('Analysis profile differs from confirmed task')
        context['analysis']=await asyncio.to_thread(self._collect,task,context)

    def _collect(self,task,context):
        ws=WorkspaceStore(self.store.root);baseline=ws.verify_baseline(task.baseline_id)
        paths=[p for p in task.allowed_paths if p.endswith('.cj') and not p.endswith('_test.cj')]
        for path in paths:
            raw=ws.safe_file(task.baseline_id,path).read_bytes();item=context['files'][path]
            if hashlib.sha256(raw).hexdigest()!=item['file_hash'] or item['content'].encode()!=raw:
                raise ValueError('Analysis source differs from model baseline')
        old=next((e for e in self.store.records(task.id,'event') if e['type']=='ANALYSIS_CONTEXT'),None)
        if old:
            report=verify_evidence(self.store,old)
            if report['baseline_hash']!=tree_hash(baseline):raise ValueError('Analysis baseline changed')
            return report
        files=[];evidence=[]
        # Leave room for proposals/feedback; all omitted originals remain archived.
        budget=max(0,min(64000,220000-len(json.dumps(context,ensure_ascii=False).encode())))
        actor='repair-'+task.id
        for index,path in enumerate(paths):
            if self.store.get_task(task.id).status in ('CANCELLED','IN_DOUBT','BLOCKED'):
                raise ValueError('Task stopped before analysis')
            source=validate_source(Path(path).name,ws.safe_file(task.baseline_id,path).read_bytes())
            job=self.service.create(source,actor_id=actor,request_key=f'{task.id}-{index}',origin='REGISTERED')
            self.service.run(job['id'])
            result=self.service.get(job['id'],actor_id=actor)
            if result['status'] in ('READY','RUNNING','IN_DOUBT'):raise ValueError('Analysis outcome unresolved')
            tools=[]
            # Copy exact verified originals into ordinary task evidence so the
            # existing archive collector preserves them without reserialization.
            original={'source.cj':self.service.directory(job['id'])/'source.cj',
                      'result.json':self.service.directory(job['id'])/'result.json'}
            original.update({o['raw_ref']:self.service.directory(job['id'])/o['raw_ref'] for o in result['observations']})
            if result.get('callgraph',{}).get('status')=='SAVED':
                original[result['callgraph']['ref']]=self.service.directory(job['id'])/result['callgraph']['ref']
            for name,actual in original.items():
                raw=actual.read_bytes();ref=f'records/{job["id"]}.analysis.{name.replace("/",".")}'
                target=self.store.root/ref
                if target.exists():
                    if target.read_bytes()!=raw:raise ValueError('Analysis copy changed')
                else:
                    with target.open('xb') as stream:stream.write(raw)
                evidence.append(dict(record_ref=ref,sha256=hashlib.sha256(raw).hexdigest()))
            for o in result['observations']:
                size=len(json.dumps(o['data'],ensure_ascii=False).encode())
                included=o['status']=='VALID' and size<=min(24000,budget)
                if included:budget-=size
                item=dict(tool=o['tool'],status=o['status'],reason=o['reason'],included=included,
                    evidence_id=f'{job["id"]}:{o["tool"]}',raw_sha256=o['raw_sha256'],
                    record_ref=f'records/{job["id"]}.analysis.{o["raw_ref"].replace("/",".")}')
                if included:item['data']=o['data']
                elif o['status']=='VALID':item['reason']='结果超出模型上下文预算；原始记录保留'
                tools.append(item)
            files.append(dict(path=path,analysis_id=job['id'],source_sha256=source['source_sha256'],
                result_sha256=result.get('result_sha256'),status=result['status'],tools=tools))
        included=sum(t['included'] for f in files for t in f['tools'])
        report=dict(schema_version=1,baseline_id=task.baseline_id,baseline_hash=tree_hash(baseline),
            status='COMPLETE' if included==len(paths)*3 and paths else 'PARTIAL' if included else 'UNAVAILABLE',
            files=files,limitations=LIMITATIONS)
        self.store.append_record(task.id,'event',dict(type='ANALYSIS_CONTEXT',analysis_context=report,
            context_hash=digest(report),evidence_files=evidence))
        return report
