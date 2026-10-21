"""Owned sample sources and explicitly labeled, source-verified live snapshots."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
from nexus.analysis.normalize import validate_source
from nexus.analysis.recovery import attach_recovery,encoded

ROOT=Path(__file__).resolve().parents[2]/'fixtures/analysis'
SAMPLES=[dict(id='sum3',title='直线依赖',file='l1_sum3.cj'),
         dict(id='loop',title='循环累加',file='l2_loop.cj'),
         dict(id='calls',title='跨函数调用',file='l3_calls.cj')]


def sample(identity):
    entry=next((s for s in SAMPLES if s['id']==identity),None)
    if not entry:raise ValueError('未知分析样例')
    return dict(entry,source=validate_source(entry['file'],(ROOT/entry['file']).read_bytes()))


def snapshot(identity):
    entry=sample(identity);root=ROOT/'snapshots'/identity;manifest=root/'manifest.json'
    if not manifest.is_file():return None
    data=json.loads(manifest.read_text())
    if data['source_sha256']!=entry['source']['source_sha256']:raise ValueError('样例与快照源码摘要不符')
    for name,expected in data['files'].items():
        if name not in ('result.json','source.cj') and name not in ('observations/sympas_slice.json','observations/sympas_dep_graph.json','observations/ast_symbol_extractor.json'):
            raise ValueError('未知快照产物')
        path=root/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('快照产物摘要不符')
    result=json.loads((root/'result.json').read_text())
    if result['source']['source_sha256']!=entry['source']['source_sha256'] or result['source']['code']!=entry['source']['code']:
        raise ValueError('快照结果不属于当前源码')
    result['display_origin']='SAMPLE_SNAPSHOT'
    return attach_recovery(result,root)


def catalog():
    return [dict(id=s['id'],title=s['title'],filename=s['file'],has_snapshot=(ROOT/'snapshots'/s['id']/'manifest.json').is_file()) for s in SAMPLES]


def snapshot_archive(identity):
    result=snapshot(identity)
    if not result:raise LookupError('暂无样例快照')
    root=ROOT/'snapshots'/identity;manifest=json.loads((root/'manifest.json').read_text());stream=io.BytesIO()
    files={name:(root/name).read_bytes() for name in [*manifest['files'],'manifest.json']}
    if result.get('derived_slice'):
        files['derived-slices.json']=encoded(result['derived_slice'])
        files['derived-manifest.json']=encoded(dict(schema_version=1,
            collection='Original snapshot bytes plus display-only text-slice derivation',
            files={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}))
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in files.items():z.writestr(name,raw)
    stream.seek(0);return stream
