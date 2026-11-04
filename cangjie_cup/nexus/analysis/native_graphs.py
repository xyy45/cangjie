"""Bounded original MCP graph assets. No dependency inference or SVG rewriting."""
import asyncio
import hashlib
import json
import math
from pathlib import Path
import re
from urllib.parse import parse_qsl,urljoin,urlsplit
from xml.etree import ElementTree

import httpx

GRAPH_TYPES=('Cfg','Cg','Cdg','Ddg','Pdg','Sdg','Dfg')
MAX_SVG_BYTES=2*1024*1024
MAX_TOTAL_BYTES=8*1024*1024
TOTAL_SECONDS=30
REFS={kind:'artifacts/'+('callgraph' if kind=='Cg' else kind.lower())+'.svg' for kind in GRAPH_TYPES}


def sha(raw):return hashlib.sha256(raw).hexdigest()


def _links(payload):
    found={kind:set() for kind in GRAPH_TYPES};failed=set()
    def walk(value,depth=0):
        if depth>16:return
        if isinstance(value,dict):
            kind=value.get('graph_type');svg=value.get('svg')
            if isinstance(kind,str) and kind in found and isinstance(svg,dict):
                if value.get('generated') is False:failed.add(kind)
                url=svg.get('download_url') or svg.get('url')
                if isinstance(url,str) and len(url)<=8192:found[kind].add(url)
            for child in value.values():walk(child,depth+1)
        elif isinstance(value,list):
            for child in value:walk(child,depth+1)
    walk(payload)
    return found,failed


def _aspect(raw,secrets):
    text=raw.decode('utf-8-sig')
    if re.search(r'<!\s*ENTITY\b',text,re.I):raise ValueError('Entity declaration')
    root=ElementTree.fromstring(text)
    if root.tag!='{http://www.w3.org/2000/svg}svg':raise ValueError('Not SVG')
    decoded=ElementTree.tostring(root,encoding='unicode')
    if any(s and (s in text or s in decoded) for s in secrets):raise ValueError('Credential echo')
    box=root.get('viewBox','').replace(',',' ').split()
    try:
        if len(box)==4:w,h=map(float,box[2:])
        else:
            w=float(re.sub(r'(?:px|pt)$','',root.get('width','800')))
            h=float(re.sub(r'(?:px|pt)$','',root.get('height','500')))
        if not all(math.isfinite(x) and 0<x<=1000000 for x in (w,h)):raise ValueError('Invalid dimensions')
        return w/h
    except (ValueError,TypeError,OverflowError):return 1.6


async def fetch_graphs(client,payload,*,base_url,token):
    entries={kind:dict(status='UNAVAILABLE',reason='MCP未返回此类图的SVG') for kind in GRAPH_TYPES}
    binary={};links,failed=_links(payload);spent=0;base=urlsplit(base_url)
    from nexus.analysis.normalize import response_failure
    if response_failure(payload) is not None:
        return dict(native_graphs=dict(schema_version=1,graphs={kind:dict(status='UNAVAILABLE',reason='MCP图工具返回失败，未读取残留图链接') for kind in GRAPH_TYPES}),_native_graph_bytes={})
    try:
        async with asyncio.timeout(TOTAL_SECONDS):
            for kind in GRAPH_TYPES:
                if kind in failed:
                    entries[kind]['reason']='MCP声明该类图未生成';continue
                choices=links[kind]
                if not choices:continue
                if len(choices)!=1:
                    entries[kind]['reason']='MCP返回多个冲突的同类型图地址';continue
                if spent>=MAX_TOTAL_BYTES:
                    entries[kind]['reason']='SVG累计大小超过预算';continue
                try:
                    parsed=urlsplit(urljoin(base_url+'/',next(iter(choices))))
                    if ((parsed.scheme,parsed.netloc)!=(base.scheme,base.netloc) or parsed.fragment or
                            not re.fullmatch(r'/artifacts/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+\.svg',parsed.path)):
                        raise ValueError('Unapproved location')
                    raw=bytearray()
                    async with client.stream('GET',parsed.geturl()) as response:
                        if response.status_code!=200:raise ValueError('Non-200 SVG')
                        async for chunk in response.aiter_bytes():
                            spent+=len(chunk)
                            if len(raw)+len(chunk)>MAX_SVG_BYTES or spent>MAX_TOTAL_BYTES:
                                raise ValueError('SVG size budget')
                            raw.extend(chunk)
                    raw=bytes(raw)
                    secrets=[v for k,v in parse_qsl(parsed.query) if v and re.search(r'key|token|secret|signature|authorization',k,re.I)]+([token] if token else [])
                    aspect=_aspect(raw,secrets)
                    binary[kind]=raw
                    entries[kind]=dict(status='SAVED',upstream_path=parsed.path,aspect_ratio=aspect)
                except (httpx.HTTPError,ValueError,UnicodeError,ElementTree.ParseError,LookupError):
                    entries[kind]['reason']='此类SVG获取失败、内容无效或超过预算；未自动重试'
    except TimeoutError:
        for entry in entries.values():
            if entry['status']!='SAVED':entry['reason']='整组SVG下载达到时限；未自动重试'
    return dict(native_graphs=dict(schema_version=1,graphs=entries),_native_graph_bytes=binary)


def save_graphs(root,identity,source_sha256,reply,*,line_count=1000):
    bundle=reply.get('native_graphs');binary=reply.pop('_native_graph_bytes',{})
    if bundle is None:return None
    if type(bundle) is not dict or type(bundle.get('schema_version')) is not int or bundle['schema_version']!=1 or set(bundle.get('graphs',{}))!=set(GRAPH_TYPES):
        raise ValueError('Invalid native graph collection')
    if set(binary)-set(GRAPH_TYPES) or sum(len(raw) for raw in binary.values())>MAX_TOTAL_BYTES:
        raise ValueError('Invalid native graph bytes')
    for kind,entry in bundle['graphs'].items():
        if entry.get('status')!='SAVED':
            if kind in binary:raise ValueError('Unbound graph bytes')
            continue
        raw=binary.get(kind)
        if not isinstance(raw,bytes) or not 0<len(raw)<=MAX_SVG_BYTES:raise ValueError('Missing original SVG')
        path=root/REFS[kind];path.parent.mkdir(exist_ok=True,mode=0o700)
        if path.parent.is_symlink():raise ValueError('Invalid artifact directory')
        if path.exists():
            if path.is_symlink() or path.read_bytes()!=raw:raise ValueError('Original SVG already differs')
        else:
            with path.open('xb') as stream:path.chmod(0o600);stream.write(raw)
        entry.update(analysis_id=identity,source_sha256=source_sha256,graph_type=kind,
            ref=REFS[kind],sha256=sha(raw),size_bytes=len(raw),aspect_ratio=_aspect(raw,[]))
        response=reply.get('response',{});container=response.get('data') if isinstance(response.get('data'),dict) else response
        candidates=response.get('json_graphs',container.get('json_graphs',[]))
        if isinstance(candidates,list):
            matching=[g for g in candidates if isinstance(g,dict) and g.get('graph_type')==kind]
            if len(matching)==1:
                from nexus.analysis.normalize import validate_graph
                try:
                    checked=validate_graph(matching[0],line_count)
                    entry.update(node_count=len(checked['nodes']),edge_count=len(checked['edges']))
                except (ValueError,KeyError,TypeError):pass
    return bundle


def verify_graphs(root,identity,source,recorded,observation):
    if recorded is None:return
    if (type(recorded) is not dict or type(recorded.get('schema_version')) is not int or recorded['schema_version']!=1 or
            set(recorded.get('graphs',{}))!=set(GRAPH_TYPES) or not observation or
            recorded.get('raw_ref')!=observation['raw_ref'] or recorded.get('raw_sha256')!=observation['raw_sha256']):
        raise ValueError('Native graph evidence binding changed')
    original=json.loads((root/observation['raw_ref']).read_bytes())
    if (original.get('tool')!='sympas_dep_graph' or original.get('http_status')!=200 or original.get('source_sha256')!=source['source_sha256'] or
            original.get('input',{}).get('code')!=source['code'] or
            original.get('input',{}).get('filename')!=source['filename'] or original.get('input',{}).get('lang')!='cangjie' or
            original.get('native_graphs')!={k:v for k,v in recorded.items() if k not in ('raw_ref','raw_sha256')}):
        raise ValueError('Native graph original differs')
    total=0
    for kind,entry in recorded['graphs'].items():
        if entry.get('status')!='SAVED':
            if entry.get('status')!='UNAVAILABLE':raise ValueError('Invalid SVG state')
            continue
        if (entry.get('analysis_id')!=identity or entry.get('source_sha256')!=source['source_sha256'] or
                entry.get('graph_type')!=kind or entry.get('ref')!=REFS[kind] or
                type(entry.get('size_bytes')) is not int or not 0<entry['size_bytes']<=MAX_SVG_BYTES):
            raise ValueError('Native graph identity differs')
        path=root/REFS[kind]
        if path.parent.is_symlink() or path.is_symlink():raise ValueError('Invalid graph path')
        try:
            size=path.stat().st_size
            if size!=entry['size_bytes'] or size>MAX_SVG_BYTES:raise ValueError('Graph size differs')
            if sha(path.read_bytes())!=entry.get('sha256'):raise ValueError('Graph original changed')
        except OSError as exc:raise ValueError('Graph original unavailable') from exc
        total+=size
    if total>MAX_TOTAL_BYTES:raise ValueError('Graph collection exceeds budget')
