"""Read-only statement slices derived from a source-bound MCP program graph."""
import hashlib
import io
import json
import zipfile
from nexus.analysis.normalize import validate_source,validate_graph,normalize,response_failure

ALGORITHM='pdg-backward-v1'

def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2).encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()


def attach_point_graph(report,root):
    """Verify originals and derive a display projection; never rewrite old evidence."""
    unavailable=dict(status='UNAVAILABLE',reason='此记录没有有效PDG，请重新分析获取')
    result=dict(report,point_graph=unavailable)
    if report.get('status') in ('READY','RUNNING','IN_DOUBT'):return result
    source=report['source'];actual=validate_source(source['filename'],source['code'].encode())
    if actual['source_sha256']!=source['source_sha256'] or actual['line_count']!=source['line_count']:
        raise ValueError('按行切片源码绑定变化')
    o=next((o for o in report.get('observations',[]) if o['tool']=='sympas_dep_graph'),None)
    if not o:return result
    if o.get('raw_ref')!='observations/sympas_dep_graph.json':raise ValueError('PDG原始引用无效')
    path=root/o['raw_ref']
    if path.is_symlink():raise ValueError('PDG原始引用无效')
    raw=path.read_bytes()
    if len(raw)>3*1024*1024 or sha(raw)!=o['raw_sha256']:raise ValueError('PDG原始摘要变化')
    record=json.loads(raw);args=record.get('input',{})
    if (record.get('tool')!='sympas_dep_graph' or
            record.get('source_sha256')!=actual['source_sha256'] or o.get('source_sha256')!=actual['source_sha256'] or
            args.get('filename')!=source['filename'] or args.get('code')!=source['code'] or args.get('lang')!='cangjie'):
        raise ValueError('PDG与原始源码请求不符')
    if record.get('http_status')!=200:
        return dict(result,point_graph=dict(status='UNAVAILABLE',reason='图工具请求未成功，无法读取PDG'))
    response=record.get('response');checked=normalize('sympas_dep_graph',response,source['filename'],source['line_count'])
    if checked['status']!=o['status'] or checked['data']!=o['data']:raise ValueError('PDG图工具与原始结果不符')
    failure=response_failure(response)
    if failure is not None:
        return dict(result,point_graph=dict(status='UNAVAILABLE',reason=failure['reason']))
    container=response.get('data') if isinstance(response.get('data'),dict) else response
    graphs=response.get('json_graphs',container.get('json_graphs',[]))
    if not isinstance(graphs,list):
        return dict(result,point_graph=dict(status='INVALID',reason='缺少JSON依赖图'))
    pdgs=[g for g in graphs if isinstance(g,dict) and g.get('graph_type')=='Pdg']
    if not pdgs:return result
    base=dict(origin='MCP_PDG',source_sha256=source['source_sha256'],raw_ref=o['raw_ref'],raw_sha256=o['raw_sha256'])
    try:
        if len(pdgs)!=1:raise ValueError('PDG数量不唯一')
        graph=validate_graph(pdgs[0],source['line_count'])
        result['point_graph']=dict(base,status='VALID',reason='已校验MCP程序依赖图',graph=graph,graph_sha256=sha(encoded(graph)))
    except (ValueError,TypeError,KeyError) as exc:
        result['point_graph']=dict(base,status='INVALID',reason=str(exc))
    return result


def point_slice(report,line):
    source=report['source']
    if type(line) is not int or not 1<=line<=source['line_count']:raise ValueError('切片目标行超出源码范围')
    pg=report.get('point_graph') or {}
    result=dict(schema_version=1,algorithm=ALGORITHM,origin='LOCAL_PDG_BACKWARD',scope='STATEMENT',
        analysis_id=report.get('id'),source_sha256=source['source_sha256'],filename=source['filename'],
        line=line,direction='Bwd',status='UNAVAILABLE',reason=pg.get('reason','此记录没有有效PDG，请重新分析获取'),
        seed_nodes=[],node_ids=[],lines=[],edges=[],raw_ref=pg.get('raw_ref'),raw_sha256=pg.get('raw_sha256'),graph_sha256=pg.get('graph_sha256'))
    if (report.get('status') in ('READY','RUNNING','IN_DOUBT') or pg.get('status')!='VALID' or
            pg.get('source_sha256')!=source['source_sha256']):return result
    graph=pg['graph'];seeds={n['id'] for n in graph['nodes'] if n['line']==line}
    if not seeds:return dict(result,status='EMPTY',reason='该行没有PDG语句节点，请选择可执行语句')
    previous={n['id']:[] for n in graph['nodes']}
    for e in graph['edges']:previous[e['to']].append(e['from'])
    seen=set(seeds);todo=list(seeds)
    while todo:
        for predecessor in previous[todo.pop()]:
            if predecessor not in seen:seen.add(predecessor);todo.append(predecessor)
    return dict(result,status='VALID',reason='从目标语句沿PDG数据及控制依赖反向遍历',seed_nodes=sorted(seeds),node_ids=sorted(seen),
        lines=sorted({n['line'] for n in graph['nodes'] if n['id'] in seen and n['line'] is not None}),
        edges=[e for e in graph['edges'] if e['from'] in seen and e['to'] in seen])


def point_archive(original,report,line):
    derived=point_slice(report,line)
    if derived['status']!='VALID':raise ValueError(derived['reason'])
    original.seek(0)
    with zipfile.ZipFile(original) as z:files={name:z.read(name) for name in z.namelist()}
    if {'point-slice.json','point-manifest.json'}&files.keys():raise ValueError('重复的按行切片产物')
    files['point-slice.json']=encoded(derived)
    manifest=dict(schema_version=1,algorithm=ALGORITHM,source_sha256=derived['source_sha256'],line=line,
        files={name:sha(raw) for name,raw in files.items()})
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for name,raw in files.items():z.writestr(name,raw)
        z.writestr('point-manifest.json',encoded(manifest))
    output.seek(0);return output
