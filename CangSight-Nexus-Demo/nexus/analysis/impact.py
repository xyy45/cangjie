"""Explicit, immutable candidate comparisons; static observations are not correctness proofs."""
from datetime import datetime,timezone
from copy import deepcopy
import difflib
import io
import json
from pathlib import Path
import re
import time
import zipfile

from nexus.analysis.normalize import validate_source,LIMITATIONS
from nexus.analysis.service import AnalysisConflict,encoded,sha,slice_criterion,ACTIVE
from nexus.contracts import digest,tree_hash
from nexus.execution.ownership import verify_write_owner
from nexus.execution.workspace import WorkspaceStore
from nexus.store import uid


def function_spans(code):
    code=code.replace('\r\n','\n').replace('\r','\n')
    # Preserve offsets and newlines while hiding braces/declarations in comments/strings.
    masked=re.sub(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/',
        lambda m:re.sub(r'[^\n]',' ',m[0]),code)
    spans=[]
    for match in re.finditer(r'\bfunc\s+([A-Za-z_]\w*)\s*(?:<[^{}]*?>)?\s*\(|\b(main)\s*\(',masked):
        begin=masked.find('{',match.end())
        if begin<0:continue
        depth=1;end=begin+1
        while end<len(masked) and depth:
            depth+=(masked[end]=='{')-(masked[end]=='}');end+=1
        if depth:continue
        spans.append(dict(name=match[1] or match[2],start_line=code.count('\n',0,match.start())+1,
            end_line=code.count('\n',0,end)+1,origin='SOURCE_TEXT'))
    return spans


def describe_change(before,after):
    a,b=before.splitlines(),after.splitlines();old,new,hunks=[],[],[]
    for kind,a1,a2,b1,b2 in difflib.SequenceMatcher(None,a,b,autojunk=False).get_opcodes():
        if kind=='equal':continue
        left,right=list(range(a1+1,a2+1)),list(range(b1+1,b2+1))
        old.extend(left);new.extend(right)
        hunks.append(dict(kind=kind,before_lines=left,after_lines=right,before_at=a1+1,after_at=b1+1))
    functions=[]
    for side,code,lines in (('before',before,old),('after',after,new)):
        for span in function_spans(code):
            if any(span['start_line']<=line<=span['end_line'] for line in lines):functions.append(dict(side=side,**span))
    return dict(before_lines=old,after_lines=new,hunks=hunks,functions=functions)


def graph_neighborhood(result,changed_lines):
    observed=next((o for o in result['observations'] if o['tool']=='sympas_dep_graph'),{})
    output=dict(status=observed.get('status','NOT_RUN'),reason=observed.get('reason','尚未分析'),
        nodes=[],edges=[],anchor_ids=[],total_nodes=0,total_edges=0,truncated=False)
    graphs=observed.get('data',{}).get('graphs',[]) if observed.get('status')=='VALID' else []
    graph_type='Ddg'
    if not graphs:
        pg=result.get('point_graph') or {}
        if (pg.get('status')!='VALID' or not pg.get('source_sha256') or
                pg['source_sha256']!=result.get('source',{}).get('source_sha256')):return output
        graphs=[pg['graph']];graph_type='Pdg'
        output.update({k:pg.get(k) for k in ('source_sha256','raw_ref','raw_sha256','graph_sha256')})
    output.update(status='VALID',graph_type=graph_type,origin='MCP_PDG' if graph_type=='Pdg' else 'MCP_DDG')
    # Each graph owns its IDs: choose the most relevant graph, never merge IDs.
    index=max(range(len(graphs)),key=lambda i:sum(n['line'] in changed_lines for n in graphs[i]['nodes']))
    graph=graphs[index];nodes,edges=graph['nodes'],graph['edges']
    output.update(graph_index=index,graph_count=len(graphs))
    anchors={n['id'] for n in nodes if n['line'] in changed_lines}
    selected=set(anchors)
    for edge in edges:
        if edge['from'] in anchors or edge['to'] in anchors:selected.update((edge['from'],edge['to']))
    chosen=sorted((n for n in nodes if n['id'] in selected),key=lambda n:(n['id'] not in anchors,n['line'] or 0,n['id']))[:80]
    ids={n['id'] for n in chosen};subset=[e for e in edges if e['from'] in ids and e['to'] in ids]
    output.update(nodes=chosen,edges=subset[:300],anchor_ids=sorted(anchors&ids),total_nodes=len(nodes),
        total_edges=len(edges),truncated=len(chosen)<len(selected) or len(subset)>300,
        reason='修改行节点及一跳邻接；各版本独立显示，不按节点ID跨版本匹配' if anchors else '有效'+graph_type.upper()+'中没有与修改行对应的节点')
    return output


def evidence_bytes(store,ref):
    path=Path(ref)
    if path.parent!=Path('records') or not re.fullmatch(r'[0-9a-f]{32}\.analysis\.[A-Za-z0-9_.-]+',path.name):
        raise ValueError('影响证据引用无效')
    actual=store.root/path
    if actual.is_symlink():raise ValueError('影响证据引用无效')
    return actual.read_bytes()


def verify_impact_event(store,event):
    raw=evidence_bytes(store,event['report_ref'])
    if sha(raw)!=event['report_sha256']:raise ValueError('影响报告摘要变化')
    report=json.loads(raw);ws=WorkspaceStore(store.root);c=ws.candidate(event['candidate_id'])
    task=store.get_task(c.task_id)
    if (report['candidate_id']!=c.id or report['task_id']!=c.task_id or report['tree_hash']!=c.tree_hash or
            report['baseline_hash']!=tree_hash(ws.verify_baseline(task.baseline_id))):
        raise ValueError('影响报告候选或基线绑定变化')
    if report['evidence_files']!=event['evidence_files']:raise ValueError('影响证据索引不符')
    for entry in event['evidence_files']:
        if sha(evidence_bytes(store,entry['record_ref']))!=entry['sha256']:raise ValueError('影响证据摘要变化')
    return report


class ImpactService:
    def __init__(self,store,analysis):
        self.store,self.analysis=store,analysis;self.ws=WorkspaceStore(store.root)
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS impact_jobs(candidate_id TEXT PRIMARY KEY, status TEXT NOT NULL, payload TEXT NOT NULL)')
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS impact_single_active ON impact_jobs((1)) WHERE status IN ('READY','RUNNING')")

    def _preview(self,candidate_id):
        c=self.ws.candidate(candidate_id);task=self.store.get_task(c.task_id)
        baseline=self.ws.verify_baseline(task.baseline_id)
        if tree_hash(baseline)!=c.baseline_hash:raise ValueError('候选基线绑定变化')
        files=[]
        for edit in c.edits:
            before=self.ws.safe_file(task.baseline_id,edit.path).read_bytes().decode('utf-8')
            after=(self.ws.subject_path(c.id)/edit.path).read_bytes().decode('utf-8')
            if after!=edit.content:raise ValueError('候选文件与编辑记录不符')
            if max(len(before.splitlines()),len(after.splitlines()))>1000 or max(len(before.encode()),len(after.encode()))>65536:
                raise ValueError('影响对比仅支持每文件64KiB、1000行以内的候选')
            files.append(dict(path=edit.path,before_code=before,after_code=after,changes=describe_change(before,after),before=None,after=None))
        return dict(schema_version=1,candidate_id=c.id,task_id=c.task_id,baseline_id=task.baseline_id,
            baseline_hash=c.baseline_hash,tree_hash=c.tree_hash,attempt=c.attempt,files=files,
            limitations=LIMITATIONS+['函数范围按源码文本定位，未声明为编译器AST。',
                '依赖图仅展示修改行对应节点及一跳邻接；静态结构差异不证明修复正确。'])

    def _row(self,candidate_id):
        with self.store.connect() as db:row=db.execute('SELECT status,payload FROM impact_jobs WHERE candidate_id=?',(candidate_id,)).fetchone()
        return (row[0],json.loads(row[1])) if row else None

    def get(self,candidate_id):
        preview=self._preview(candidate_id);row=self._row(candidate_id)
        if not row:return dict(preview,status='NOT_STARTED',evidence_files=[])
        status,report=row
        if any(report[k]!=preview[k] for k in ('candidate_id','task_id','baseline_id','baseline_hash','tree_hash')):
            raise ValueError('影响报告不属于当前候选版本')
        if report.get('report_ref'):
            raw=self._evidence(report['report_ref'])
            if sha(raw)!=report['report_sha256']:raise ValueError('影响报告摘要变化')
            persisted=json.loads(raw)
            if persisted['candidate_id']!=candidate_id or persisted['tree_hash']!=preview['tree_hash']:raise ValueError('影响报告版本错误')
            for entry in report['evidence_files']:
                if sha(self._evidence(entry['record_ref']))!=entry['sha256']:raise ValueError('影响分析证据变化')
            return self._display_graphs(dict(persisted,status=status,report_ref=report['report_ref'],report_sha256=report['report_sha256']))
        return self._display_graphs(dict(report,status=status))

    def _display_graphs(self,report):
        """Project verified PDGs into legacy views without rewriting recorded evidence."""
        result=deepcopy(report)
        for file in result['files']:
            for side in ('before','after'):
                entry=file[side]
                if not entry or entry['graph']['status']=='VALID':continue
                try:analysis=self.analysis.get(entry['analysis_id'],actor_id='repair-'+report['task_id'])
                except (LookupError,OSError):continue
                if (analysis['source']['source_sha256']!=entry['source_sha256'] or
                        analysis['source']['code']!=file[side+'_code'] or analysis['slice_criterion']!=entry['slice_criterion'] or
                        {o['tool']:o['raw_sha256'] for o in analysis['observations']}!=
                        {o['tool']:o['raw_sha256'] for o in entry['tools']}):
                    raise ValueError('影响图与原始分析绑定变化')
                graph=graph_neighborhood(analysis,file['changes'][side+'_lines'])
                if graph.get('graph_type')=='Pdg' and graph['status']=='VALID':entry['display_graph']=graph
        return result

    def _evidence(self,ref):
        return evidence_bytes(self.store,ref)

    def start(self,candidate_id):
        verify_write_owner(self.store.root,self.analysis.owner)
        report=self.get(candidate_id)
        if report['status']!='NOT_STARTED':return report,False
        if self.store.get_task(report['task_id']).status in ('READY','DIAGNOSING','GENERATING','APPLYING','BUILDING','TESTING','EXPORTING'):
            raise AnalysisConflict('请先等待修复运行结束，再生成影响对比')
        report.update(id=uid(),status='READY',created_at=datetime.now(timezone.utc).isoformat(),evidence_files=[],progress='等待分析')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM impact_jobs WHERE candidate_id=?',(candidate_id,)).fetchone():return self.get(candidate_id),False
            if db.execute("SELECT 1 FROM impact_jobs WHERE status IN ('READY','RUNNING')").fetchone():raise AnalysisConflict('已有影响对比正在分析')
            if db.execute("SELECT 1 FROM analysis_jobs WHERE status IN ('READY','RUNNING')").fetchone():raise AnalysisConflict('已有源码正在分析')
            db.execute('INSERT INTO impact_jobs VALUES (?,?,?)',(candidate_id,'READY',json.dumps(report,ensure_ascii=False)))
        return report,True

    def _save(self,report,status):
        verify_write_owner(self.store.root,self.analysis.owner)
        with self.store.connect() as db:
            changed=db.execute("UPDATE impact_jobs SET status=?,payload=? WHERE candidate_id=? AND status='RUNNING'",
                (status,json.dumps(report,ensure_ascii=False),report['candidate_id'])).rowcount
        if not changed:raise AnalysisConflict('影响分析已停止，未重新执行')

    def _analyze(self,source,line,actor,impact_id):
        criterion=slice_criterion(source,line)
        with self.store.connect() as db:
            rows=db.execute('SELECT id,status,payload FROM analysis_jobs WHERE actor_id=? ORDER BY rowid DESC',(actor,)).fetchall()
        for identity,status,raw in rows:
            payload=json.loads(raw)
            if (payload.get('analysis_profile')==5 and payload.get('slice_scope')=='VARIABLE_TABLE' and payload['origin']=='REGISTERED' and all(payload['source'][k]==source[k] for k in ('filename','source_sha256')) and
                    payload.get('slice_criterion',slice_criterion(source))==criterion):
                if status in ACTIVE:raise AnalysisConflict('对应源码分析仍在运行')
                return self.analysis.get(identity,actor_id=actor),True
        job=self.analysis.create(source,actor_id=actor,request_key='impact-'+digest(dict(source=source['source_sha256'],
            filename=source['filename'],criterion=criterion)),origin='REGISTERED',slice_line=line,impact_id=impact_id)
        self.analysis.run(job['id'])
        return self.analysis.get(job['id'],actor_id=actor),False

    def _copy(self,result,report):
        root=self.analysis.directory(result['id'])
        originals={'source.cj':root/'source.cj'}
        if result.get('result_sha256'):originals['result.json']=root/'result.json'
        originals.update({o['raw_ref']:root/o['raw_ref'] for o in result['observations']})
        if result.get('callgraph',{}).get('status')=='SAVED':originals[result['callgraph']['ref']]=root/result['callgraph']['ref']
        for name,path in originals.items():
            raw=path.read_bytes();ref=f'records/{result["id"]}.analysis.{name.replace("/",".")}'
            target=self.store.root/ref
            if target.exists():
                if self._evidence(ref)!=raw:raise ValueError('已有分析证据不一致')
            else:
                with target.open('xb') as stream:stream.write(raw)
            entry=dict(record_ref=ref,sha256=sha(raw))
            if entry not in report['evidence_files']:report['evidence_files'].append(entry)

    def run(self,candidate_id):
        verify_write_owner(self.store.root,self.analysis.owner)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            claimed=db.execute("UPDATE impact_jobs SET status='RUNNING' WHERE candidate_id=? AND status='READY'",(candidate_id,)).rowcount
        if not claimed:return False
        _,report=self._row(candidate_id);started=time.monotonic();status='FAILED'
        try:
            for file in report['files']:
                for side in ('before','after'):
                    self._preview(candidate_id)
                    report['progress']=file['path']+' · '+('修复前' if side=='before' else '修复后');self._save(report,'RUNNING')
                    source=validate_source(Path(file['path']).name,file[side+'_code'].encode())
                    lines=file['changes'][side+'_lines']
                    anchor=file['changes']['hunks'][0][side+'_at'] if file['changes']['hunks'] else 3
                    line=lines[0] if lines else max(1,min(anchor,source['line_count']))
                    result,reused=self._analyze(source,line,'repair-'+report['task_id'],report['id'])
                    if result['source']['source_sha256']!=source['source_sha256'] or result['source']['code']!=source['code']:
                        raise ValueError('分析源码版本错误')
                    self._copy(result,report)
                    file[side]=dict(analysis_id=result['id'],source_sha256=source['source_sha256'],slice_criterion=result['slice_criterion'],slice_scope=result.get('slice_scope'),
                        status=result['status'],reused=reused,graph=graph_neighborhood(result,lines),
                        tools=[dict(tool=o['tool'],status=o['status'],reason=o['reason'],raw_sha256=o['raw_sha256']) for o in result['observations']])
                    self._save(report,'RUNNING')
            self._preview(candidate_id)
            states=[file[side]['status'] for file in report['files'] for side in ('before','after')]
            valid=any(t['status']=='VALID' for f in report['files'] for side in ('before','after') for t in f[side]['tools'])
            status='COMPLETE' if all(s=='COMPLETE' for s in states) else 'PARTIAL' if valid else 'FAILED'
        except Exception:
            report['error']='分析未完整结束；已保留返回结果，不会自动重发。'
            status='PARTIAL' if any(f[s] for f in report['files'] for s in ('before','after')) else 'FAILED'
        report.update(status=status,elapsed_ms=round((time.monotonic()-started)*1000),progress='分析结束')
        raw=encoded(report);ref=f'records/{report["id"]}.analysis.impact.json'
        verify_write_owner(self.store.root,self.analysis.owner)
        with (self.store.root/ref).open('xb') as stream:stream.write(raw)
        report.update(report_ref=ref,report_sha256=sha(raw))
        try:
            with self.store.connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT status FROM impact_jobs WHERE candidate_id=?',(candidate_id,)).fetchone()
                if not row or row[0]!='RUNNING':raise AnalysisConflict('影响分析已停止')
                self.store._append_event(db,report['task_id'],dict(type='IMPACT_ANALYSIS',candidate_id=candidate_id,
                    tree_hash=report['tree_hash'],report_ref=ref,report_sha256=sha(raw),evidence_files=report['evidence_files']))
                db.execute('UPDATE impact_jobs SET status=?,payload=? WHERE candidate_id=?',
                    (status,json.dumps(report,ensure_ascii=False),candidate_id))
        except Exception:
            # No completed report without its archive index; never replay tools.
            verify_write_owner(self.store.root,self.analysis.owner)
            report.pop('report_ref',None);report.pop('report_sha256',None)
            report.update(status='IN_DOUBT',error='影响证据提交未确认；未自动重新分析。')
            with self.store.connect() as db:
                db.execute("UPDATE impact_jobs SET status='IN_DOUBT',payload=? WHERE candidate_id=? AND status='RUNNING'",
                    (json.dumps(report,ensure_ascii=False),candidate_id))
        return True

    def reconcile(self):
        verify_write_owner(self.store.root,self.analysis.owner)
        with self.store.connect() as db:db.execute("UPDATE impact_jobs SET status='IN_DOUBT' WHERE status IN ('READY','RUNNING')")

    def export(self,candidate_id):
        report=self.get(candidate_id)
        if report['status'] in (*ACTIVE,'NOT_STARTED') or not report.get('report_ref'):raise AnalysisConflict('尚无完整可导出的影响证据')
        files={'report.json':self._evidence(report['report_ref'])}
        files.update({e['record_ref']:self._evidence(e['record_ref']) for e in report['evidence_files']})
        projected=[dict(path=f['path'],**{side:dict(analysis_id=f[side]['analysis_id'],
            source_sha256=f[side]['source_sha256'],graph=f[side]['display_graph'])
            for side in ('before','after') if f[side] and f[side].get('display_graph')})
            for f in report['files'] if any(f[s] and f[s].get('display_graph') for s in ('before','after'))]
        if projected:files['display-graphs.json']=encoded(dict(schema_version=1,origin='VERIFIED_ANALYSIS_PROJECTION',
            candidate_id=candidate_id,tree_hash=report['tree_hash'],report_sha256=report['report_sha256'],files=projected))
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
            for name,raw in files.items():archive.writestr(name,raw)
            archive.writestr('manifest.json',encoded(dict(candidate_id=candidate_id,tree_hash=report['tree_hash'],
                files={name:sha(raw) for name,raw in files.items()})))
        stream.seek(0);return stream
