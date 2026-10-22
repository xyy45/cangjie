"""One claimed analysis per job, short transactions, source-bound immutable evidence."""
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import re
import time
import zipfile

from nexus.analysis.client import ResearchClient,AnalysisUnavailable
from nexus.analysis.normalize import TOOLS,SUPPORTED_TOOLS,LIMITATIONS,normalize
from nexus.analysis.recovery import attach_recovery
from nexus.analysis.point import attach_point_graph
from nexus.execution.ownership import owner_token,verify_write_owner
from nexus.store import RunStore,uid

ACTIVE=('READY','RUNNING')


class AnalysisConflict(ValueError):pass


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2).encode()
def sha(value):return hashlib.sha256(value).hexdigest()

def slice_criterion(source,line=None):
    line=min(3,source['line_count']) if line is None else line
    if type(line) is not int or not 1<=line<=source['line_count']:
        raise ValueError('切片目标行超出源码范围')
    return dict(line=line,direction='Bwd',method='SymPas')


class AnalysisService:
    def __init__(self,root,*,client_factory=ResearchClient):
        self.store=RunStore(Path(root));self.root=self.store.root/'analysis'
        self.root.mkdir(exist_ok=True,mode=0o700);self.client_factory=client_factory
        self.owner=owner_token(self.store.root)
        with self.store.connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS analysis_jobs(
                id TEXT PRIMARY KEY,actor_id TEXT NOT NULL,request_key TEXT NOT NULL,
                request_hash TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL,
                UNIQUE(actor_id,request_key))''')
            db.execute("CREATE UNIQUE INDEX IF NOT EXISTS analysis_single_active ON analysis_jobs((1)) WHERE status IN ('READY','RUNNING')")

    def directory(self,identity):
        if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{32}',identity):raise LookupError('未知分析记录')
        path=self.root/identity
        if path.is_symlink():raise ValueError('分析目录无效')
        return path

    def create(self,source,*,actor_id,request_key,origin,slice_line=None,impact_id=None):
        verify_write_owner(self.store.root,self.owner)
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',request_key or '') or origin not in ('SAMPLE','UPLOAD','REGISTERED'):raise ValueError('无效分析请求')
        criterion=slice_criterion(source,slice_line)
        identity=dict(filename=source['filename'],source_sha256=source['source_sha256'],origin=origin)
        fingerprint=sha(encoded(dict(**identity,profile_version=5,slice_criterion=criterion)))
        previous=[sha(encoded(dict(**identity,profile_version=n,slice_criterion=criterion))) for n in (2,3,4)]
        legacy=sha(encoded(dict(**identity,profile_version=1))) if criterion==slice_criterion(source) else None
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT id,request_hash FROM analysis_jobs WHERE actor_id=? AND request_key=?',(actor_id,request_key)).fetchone()
            if old:
                if old[1] not in (fingerprint,*previous,legacy):raise AnalysisConflict('同一请求标识不能绑定不同源码或切片目标')
                return {'id':old[0]}
            has_impact=db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='impact_jobs'").fetchone()
            impact=db.execute("SELECT status,payload FROM impact_jobs WHERE status IN ('READY','RUNNING')").fetchone() if has_impact else None
            lease=json.loads(impact[1]) if impact else None
            if impact and (impact[0]!='RUNNING' or impact_id!=lease['id'] or origin!='REGISTERED' or actor_id!='repair-'+lease['task_id']):
                raise AnalysisConflict('已有影响对比正在分析，请等待完成')
            if impact_id and not impact:raise AnalysisConflict('影响分析预约已失效')
            if db.execute("SELECT 1 FROM analysis_jobs WHERE status IN ('READY','RUNNING')").fetchone():raise AnalysisConflict('已有源码正在分析，请等待完成')
            identity=uid();root=self.directory(identity);root.mkdir(mode=0o700)
            path=root/'source.cj'
            with path.open('xb') as stream:path.chmod(0o600);stream.write(source['code'].encode())
            payload=dict(schema_version=1,id=identity,origin=origin,source={k:v for k,v in source.items() if k!='code'},
                created_at=datetime.now(timezone.utc).isoformat(),updated_at=datetime.now(timezone.utc).isoformat(),
                analysis_profile=5,slice_scope='VARIABLE_TABLE',observations=[],limitations=LIMITATIONS,active_tool=None,elapsed_ms=None,slice_criterion=criterion)
            db.execute('INSERT INTO analysis_jobs VALUES (?,?,?,?,?,?)',(identity,actor_id,request_key,fingerprint,'READY',json.dumps(payload,ensure_ascii=False)))
        return {'id':identity}

    def _row(self,identity,actor_id=None):
        self.directory(identity)
        with self.store.connect() as db:
            row=db.execute('SELECT actor_id,status,payload FROM analysis_jobs WHERE id=?',(identity,)).fetchone()
        if not row or (actor_id is not None and row[0]!=actor_id):raise LookupError('未知分析记录')
        return row[1],json.loads(row[2])

    def _source(self,identity,payload):
        path=self.directory(identity)/'source.cj'
        if path.is_symlink():raise ValueError('源码引用无效')
        data=path.read_bytes()
        if sha(data)!=payload['source']['source_sha256']:raise ValueError('分析源码已变化')
        return dict(payload['source'],code=data.decode('utf-8'))

    def _save(self,identity,status,payload):
        verify_write_owner(self.store.root,self.owner)
        payload['updated_at']=datetime.now(timezone.utc).isoformat()
        with self.store.connect() as db:
            db.execute('UPDATE analysis_jobs SET status=?,payload=? WHERE id=?',(status,json.dumps(payload,ensure_ascii=False),identity))

    def run(self,identity):
        verify_write_owner(self.store.root,self.owner)
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            claimed=db.execute("UPDATE analysis_jobs SET status='RUNNING' WHERE id=? AND status='READY'",(identity,)).rowcount
        if not claimed:return False
        started=time.monotonic();_,payload=self._row(identity)
        try:
            source=self._source(identity,payload)
            with self.client_factory() as client:
                for tool in TOOLS:
                    verify_write_owner(self.store.root,self.owner)
                    payload['active_tool']=tool;self._save(identity,'RUNNING',payload)
                    args=dict(code=source['code'],filename=source['filename'],lang='cangjie')
                    if tool=='sympas_slice_table':args.update(direction='Bwd',method='SymPas',table_formats=['json'],timeout_sec=40)
                    if tool=='sympas_slice':args.update(**payload.get('slice_criterion',slice_criterion(source)),format='json')
                    if tool=='sympas_dep_graph':args.update(graph_types='Ddg,Cg,Pdg',formats=['dot','svg'])
                    try:
                        reply=client.analyze(tool,args)
                        observation=normalize(tool,reply.get('response'),source['filename'],source['line_count']) if reply.get('http_status')==200 else dict(status='UNAVAILABLE',reason='分析服务返回非200状态',data={})
                    except AnalysisUnavailable as exc:
                        reply=dict(http_status=None,response=None,elapsed_ms=None,transport='group_http_tools',error=str(exc))
                        observation=dict(status='UNAVAILABLE',reason=str(exc),data={})
                    svg=reply.pop('_callgraph_bytes',None)
                    if tool=='sympas_dep_graph':
                        cg=dict(reply.get('callgraph') or dict(status='UNAVAILABLE',reason='此记录未取得调用图 SVG，请重新分析'))
                        if cg.get('status')=='SAVED' and isinstance(svg,bytes):
                            ref='artifacts/callgraph.svg';path=self.directory(identity)/ref;path.parent.mkdir(exist_ok=True,mode=0o700)
                            with path.open('xb') as stream:path.chmod(0o600);stream.write(svg)
                            cg.update(analysis_id=identity,source_sha256=source['source_sha256'],ref=ref,sha256=sha(svg),size_bytes=len(svg),graph_type='Cg')
                        else:cg=dict(status='UNAVAILABLE',reason=cg.get('reason','未取得调用图 SVG'))
                        reply['callgraph']=cg
                    record=dict(schema_version=1,request_id=f'{identity}-{tool}',tool=tool,
                        source_sha256=source['source_sha256'],input=args,observed_at=datetime.now(timezone.utc).isoformat(),**reply)
                    ref=f'observations/{tool}.json';path=self.directory(identity)/ref;path.parent.mkdir(exist_ok=True,mode=0o700)
                    raw=encoded(record)
                    with path.open('xb') as stream:path.chmod(0o600);stream.write(raw)
                    if tool=='sympas_dep_graph':payload['callgraph']=dict(cg,raw_ref=ref,raw_sha256=sha(raw))
                    payload['observations'].append(dict(tool=tool,request_id=record['request_id'],
                        observed_at=record['observed_at'],source_sha256=source['source_sha256'],raw_ref=ref,raw_sha256=sha(raw),
                        http_status=reply.get('http_status'),elapsed_ms=reply.get('elapsed_ms'),**observation))
                    self._save(identity,'RUNNING',payload)
            valid=sum(o['status']=='VALID' for o in payload['observations'])
            status='COMPLETE' if valid==len(TOOLS) else 'PARTIAL' if valid else 'FAILED'
        except Exception as exc:
            # No exception body/source/header enters logs or a public error.
            payload['error']='分析未完整结束，请检查证据；未自动重试'
            status='IN_DOUBT' if payload['observations'] else 'FAILED'
        payload['active_tool']=None;payload['elapsed_ms']=round((time.monotonic()-started)*1000)
        try:source=self._source(identity,payload)
        except (ValueError,OSError):
            payload['error']='分析输入摘要变化；没有可交付结果'
            self._save(identity,'FAILED',payload);return True
        result=dict(payload,status=status,source=source)
        raw=encoded(result);path=self.directory(identity)/'result.json'
        with path.open('xb') as stream:path.chmod(0o600);stream.write(raw)
        payload['result_sha256']=sha(raw);self._save(identity,status,payload)
        return True

    def get(self,identity,*,actor_id):
        status,payload=self._row(identity,actor_id);source=self._source(identity,payload)
        root=self.directory(identity)
        for o in payload['observations']:
            if o['raw_ref'] not in {f'observations/{tool}.json' for tool in SUPPORTED_TOOLS}:raise ValueError('未知证据引用')
            path=root/o['raw_ref']
            if path.is_symlink() or sha(path.read_bytes())!=o['raw_sha256']:raise ValueError('分析证据已变化')
        if payload.get('result_sha256'):
            path=root/'result.json'
            if path.is_symlink() or sha(path.read_bytes())!=payload['result_sha256']:raise ValueError('分析结果已变化')
        cg=payload.get('callgraph')
        if cg and cg.get('status')=='SAVED':
            observed=next((o for o in payload['observations'] if o['tool']=='sympas_dep_graph'),None)
            if (cg.get('ref')!='artifacts/callgraph.svg' or cg.get('analysis_id')!=identity or
                    cg.get('source_sha256')!=source['source_sha256'] or not observed or
                    cg.get('raw_ref')!=observed['raw_ref'] or cg.get('raw_sha256')!=observed['raw_sha256']):
                raise ValueError('调用图绑定无效')
            original=json.loads((root/observed['raw_ref']).read_bytes()).get('callgraph')
            if original!={k:v for k,v in cg.items() if k not in ('raw_ref','raw_sha256')}:
                raise ValueError('调用图与原始证据不符')
            path=root/cg['ref']
            try:valid=not path.parent.is_symlink() and not path.is_symlink() and sha(path.read_bytes())==cg['sha256'] and path.stat().st_size==cg['size_bytes']
            except OSError:valid=False
            if not valid:
                raise ValueError('调用图证据已变化')
        criterion=payload.get('slice_criterion',slice_criterion(source))
        if criterion!=slice_criterion(source,criterion.get('line')):raise ValueError('切片参数无效')
        observed=next((o for o in payload['observations'] if o['tool']=='sympas_slice'),None)
        if observed:
            args=json.loads((root/observed['raw_ref']).read_bytes())['input']
            if any(args.get(k)!=v for k,v in criterion.items()):raise ValueError('切片参数与原始请求不符')
        native=next((o for o in payload['observations'] if o['tool']=='sympas_slice_table'),None)
        if native:
            raw=json.loads((root/native['raw_ref']).read_bytes())
            args=raw.get('input',{})
            if (raw.get('tool')!='sympas_slice_table' or raw.get('source_sha256')!=source['source_sha256'] or
                    args.get('code')!=source['code'] or args.get('filename')!=source['filename'] or
                    args.get('lang')!='cangjie' or args.get('direction')!='Bwd' or args.get('method')!='SymPas' or
                    args.get('table_formats')!=['json'] or 'line' in args or payload.get('slice_scope')!='VARIABLE_TABLE'):
                raise ValueError('切片表与原始请求绑定不符')
            if native['status']=='VALID':
                checked=normalize('sympas_slice_table',raw.get('response'),source['filename'],source['line_count'])
                if raw.get('http_status')!=200 or checked['status']!='VALID' or checked['data']!=native['data']:
                    raise ValueError('切片表与原始结果不符')
        return attach_point_graph(attach_recovery(dict(payload,status=status,source=source,slice_criterion=criterion,
            callgraph=cg or dict(status='UNAVAILABLE',reason='此记录没有调用图 SVG，请重新分析')),root),root)

    def callgraph_bytes(self,identity,*,actor_id):
        result=self.get(identity,actor_id=actor_id)
        if result['callgraph']['status']!='SAVED':raise LookupError('调用图 SVG 不可用，请重新分析')
        raw=(self.directory(identity)/result['callgraph']['ref']).read_bytes()
        if sha(raw)!=result['callgraph']['sha256']:raise ValueError('调用图证据已变化')
        return raw

    def list(self,actor_id):
        with self.store.connect() as db:
            rows=db.execute('SELECT id,status,payload FROM analysis_jobs WHERE actor_id=? ORDER BY rowid DESC LIMIT 20',(actor_id,)).fetchall()
        return [dict(id=identity,status=status,filename=(data:=json.loads(payload))['source']['filename'],origin=data['origin'],slice_scope=data.get('slice_scope'),
            slice_criterion=data.get('slice_criterion',slice_criterion(data['source']))) for identity,status,payload in rows]

    def export(self,identity,*,actor_id):
        result=self.get(identity,actor_id=actor_id)
        if result['status'] in ACTIVE:raise AnalysisConflict('分析尚未结束')
        root=self.directory(identity);source_bytes=(root/'source.cj').read_bytes()
        if sha(source_bytes)!=result['source']['source_sha256']:raise ValueError('导出源码摘要变化')
        result_bytes=(root/'result.json').read_bytes() if result.get('result_sha256') else encoded(result)
        if result.get('result_sha256') and sha(result_bytes)!=result['result_sha256']:raise ValueError('导出结果摘要变化')
        files={'source.cj':source_bytes,'result.json':result_bytes}
        if result['callgraph']['status']=='SAVED':files[result['callgraph']['ref']]=self.callgraph_bytes(identity,actor_id=actor_id)
        for observation in result['observations']:
            raw=(root/observation['raw_ref']).read_bytes()
            if sha(raw)!=observation['raw_sha256']:raise ValueError('导出证据摘要变化')
            files[observation['raw_ref']]=raw
        if result.get('derived_slice'):
            files['derived-slices.json']=encoded(result['derived_slice'])
        manifest=dict(schema_version=1,source_sha256=result['source']['source_sha256'],origin=result['origin'],
            status=result['status'],files={name:sha(raw) for name,raw in files.items()})
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
            for name,raw in files.items():z.writestr(name,raw)
            z.writestr('manifest.json',encoded(manifest))
        stream.seek(0);return stream

    def reconcile(self):
        verify_write_owner(self.store.root,self.owner)
        with self.store.connect() as db:db.execute("UPDATE analysis_jobs SET status='IN_DOUBT' WHERE status IN ('READY','RUNNING')")
