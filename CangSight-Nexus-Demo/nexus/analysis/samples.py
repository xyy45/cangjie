"""Owned sample sources and explicitly labeled, source-verified live snapshots."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
from nexus.analysis.normalize import validate_source,SUPPORTED_TOOLS,normalize
from nexus.analysis.recovery import attach_recovery,encoded
from nexus.analysis.point import attach_point_graph

ROOT=Path(__file__).resolve().parents[2]/'fixtures/analysis'
NATIVE_SNAPSHOTS=ROOT/'snapshots-native'
POINT_SNAPSHOTS=ROOT/'snapshots-point'

def snapshot_root(identity):
    if (POINT_SNAPSHOTS/identity/'manifest.json').is_file():return POINT_SNAPSHOTS/identity
    return NATIVE_SNAPSHOTS/identity if (NATIVE_SNAPSHOTS/identity/'manifest.json').is_file() else ROOT/'snapshots'/identity

SAMPLES=[dict(id='sum3',title='直线依赖',file='l1_sum3.cj'),
         dict(id='loop',title='循环累加',file='l2_loop.cj'),
         dict(id='calls',title='跨函数调用',file='l3_calls.cj'),
         dict(id='reassign',title='重新赋值',file='l4_reassign.cj'),
         dict(id='branch',title='条件分支',file='l5_branch.cj')]


def sample(identity):
    entry=next((s for s in SAMPLES if s['id']==identity),None)
    if not entry:raise ValueError('未知分析样例')
    return dict(entry,source=validate_source(entry['file'],(ROOT/entry['file']).read_bytes()))


def snapshot(identity):
    entry=sample(identity);root=snapshot_root(identity);manifest=root/'manifest.json'
    if not manifest.is_file():return None
    data=json.loads(manifest.read_text())
    if data['source_sha256']!=entry['source']['source_sha256']:raise ValueError('样例与快照源码摘要不符')
    for name,expected in data['files'].items():
        if name not in ('result.json','source.cj') and name not in tuple(f'observations/{tool}.json' for tool in SUPPORTED_TOOLS)+('artifacts/callgraph.svg',):
            raise ValueError('未知快照产物')
        path=root/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('快照产物摘要不符')
    result=json.loads((root/'result.json').read_text())
    if result['source']['source_sha256']!=entry['source']['source_sha256'] or result['source']['code']!=entry['source']['code']:
        raise ValueError('快照结果不属于当前源码')
    for observed in result.get('observations',[]):
        if observed['tool']=='sympas_slice_table':
            ref=observed['raw_ref']
            if ref!='observations/sympas_slice_table.json' or ref not in data['files']:raise ValueError('样例切片表引用无效')
            raw=(root/ref).read_bytes()
            if observed['raw_sha256']!=hashlib.sha256(raw).hexdigest():raise ValueError('样例切片表摘要不符')
            record=json.loads(raw);args=record['input']
            if (record.get('tool')!='sympas_slice_table' or record.get('source_sha256')!=entry['source']['source_sha256'] or
                    observed.get('source_sha256')!=entry['source']['source_sha256'] or result.get('slice_scope')!='VARIABLE_TABLE' or
                    args.get('lang')!='cangjie' or args.get('table_formats')!=['json'] or args.get('code')!=entry['source']['code'] or args.get('filename')!=entry['source']['filename'] or
                    args.get('direction')!='Bwd' or args.get('method')!='SymPas' or 'line' in args):raise ValueError('样例切片表请求不符')
            checked=normalize('sympas_slice_table',record['response'],entry['source']['filename'],entry['source']['line_count'])
            if observed['status']=='VALID' and (record.get('http_status')!=200 or checked['status']!='VALID' or checked['data']!=observed['data']):raise ValueError('样例切片表结果不符')
    result['display_origin']='SAMPLE_SNAPSHOT'
    return attach_point_graph(attach_recovery(result,root),root)


def catalog():
    return [dict(id=s['id'],title=s['title'],filename=s['file'],has_snapshot=(snapshot_root(s['id'])/'manifest.json').is_file()) for s in SAMPLES]


def snapshot_archive(identity):
    result=snapshot(identity)
    if not result:raise LookupError('暂无样例快照')
    root=snapshot_root(identity);manifest=json.loads((root/'manifest.json').read_text());stream=io.BytesIO()
    files={name:(root/name).read_bytes() for name in [*manifest['files'],'manifest.json']}
    if result.get('derived_slice'):
        files['derived-slices.json']=encoded(result['derived_slice'])
        files['derived-manifest.json']=encoded(dict(schema_version=1,
            collection='Original snapshot bytes plus display-only text-slice derivation',
            files={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}))
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in files.items():z.writestr(name,raw)
    stream.seek(0);return stream


def callgraph_bytes(identity):
    result=snapshot(identity)
    cg=result.get('callgraph',{}) if result else {}
    if cg.get('status')!='SAVED':raise LookupError('暂无样例调用图')
    root=snapshot_root(identity);manifest=json.loads((root/'manifest.json').read_text())
    if (cg.get('ref')!='artifacts/callgraph.svg' or cg['ref'] not in manifest['files'] or
            cg.get('source_sha256')!=result['source']['source_sha256'] or cg.get('analysis_id')!=result['id']):
        raise ValueError('样例调用图绑定无效')
    path=root/cg['ref']
    raw=path.read_bytes()
    if path.parent.is_symlink() or hashlib.sha256(raw).hexdigest()!=cg['sha256'] or len(raw)!=cg['size_bytes']:
        raise ValueError('样例调用图摘要不符')
    return raw
