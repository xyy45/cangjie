"""Validate tool structures, without upgrading them to compilation/semantic proof."""
import hashlib
import json
import re

TOOLS=('sympas_slice','sympas_dep_graph','ast_symbol_extractor')
MAX_SOURCE=65536
MAX_LINES=1000
LIMITATIONS=[
    '静态结构观察不代替仓颉编译、类型检查或行为测试。',
    '切片行准则在现有工具中可能不精确；高亮仅反映工具返回的行。',
    '复杂语法可能触发中间表示错误；结果按工具分别报告。',
    '源码摘要绑定本次请求字节，不是远端签名或语义正确性证明。',
]


def validate_source(filename,data):
    if not isinstance(filename,str) or not re.fullmatch(r'[^\x00-\x1f\x7f/\\]{1,120}\.cj',filename) or filename.startswith('.'):
        raise ValueError('仅支持安全文件名的 .cj 文件')
    if not isinstance(data,bytes) or not 0<len(data)<=MAX_SOURCE:
        raise ValueError('源码大小应为 1–65536 字节')
    try:code=data.decode('utf-8')
    except UnicodeDecodeError as exc:raise ValueError('源码必须为 UTF-8') from exc
    if not code.strip() or '\x00' in code or len(code.splitlines())>MAX_LINES:
        raise ValueError('源码为空、含空字节或超过1000行')
    return dict(filename=filename,code=code,source_sha256=hashlib.sha256(data).hexdigest(),
                line_count=len(code.splitlines()),size=len(data))


def _result(status,reason,data=None):
    return dict(status=status,reason=reason,data=data or {})


def normalize(tool,response,filename,line_count):
    if tool not in TOOLS:raise ValueError('Unsupported tool')
    if not isinstance(response,dict):return _result('INVALID','响应不是JSON对象')
    logs=[response.get(k) for k in ('engine_log','raw_output','diagnostics','stderr','error','error_code','message','scan_errors')]
    diagnostic=json.dumps(logs,ensure_ascii=False)
    if response.get('status') in ('error','failed','failure') or response.get('error_code') or re.search(
            r'SIL syntax error|Found 0 source files|analy[sz]er.{0,30}failed|compilation failed|fatal error|Traceback|unsupported language|entry procedure.{0,80}not found',diagnostic,re.I):
        return _result('FAILED','工具内部分析失败；查看原始证据')
    if response.get('status') not in ('success','ok','completed'):
        return _result('INVALID','缺少已知成功状态')
    container=response.get('data') if isinstance(response.get('data'),dict) else response
    try:
        if tool=='sympas_slice':
            slices=container.get('backward_slices')
            if not isinstance(slices,dict):return _result('INVALID','缺少结构化切片')
            if not slices:return _result('EMPTY','未返回切片')
            if len(slices)>500:raise ValueError('切片数量超限')
            output={}
            for symbol,files in slices.items():
                if not isinstance(symbol,str) or not symbol or len(symbol)>500 or not isinstance(files,dict):raise ValueError('切片结构无效')
                if set(files)!={filename}:raise ValueError('切片文件不匹配')
                lines=files[filename]
                if not isinstance(lines,list) or len(lines)>MAX_LINES or any(type(n) is not int or not 1<=n<=line_count for n in lines):raise ValueError('切片行号无效')
                if lines:output[symbol]=sorted(set(lines))
            return _result('VALID','静态切片已返回',{'slices':output}) if output else _result('EMPTY','切片未包含源码行')
        if tool=='sympas_dep_graph':
            graphs=response.get('json_graphs',container.get('json_graphs'))
            if not isinstance(graphs,list):return _result('INVALID','缺少JSON依赖图')
            output=[]
            for graph in graphs:
                if not isinstance(graph,dict):raise ValueError('图结构无效')
                if graph.get('graph_type')!='Ddg':continue
                nodes,edges=graph.get('nodes'),graph.get('edges')
                if not isinstance(nodes,list) or not isinstance(edges,list) or len(nodes)>500 or len(edges)>3000:raise ValueError('图结构无效或超限')
                if graph.get('node_count',len(nodes))!=len(nodes) or graph.get('edge_count',len(edges))!=len(edges):raise ValueError('图计数不匹配')
                if not nodes:continue
                normalized=[];ids=set()
                for node in nodes:
                    if not isinstance(node,dict):raise ValueError('节点无效')
                    identity,label=node.get('id'),node.get('label')
                    if not isinstance(identity,str) or not identity or len(identity)>128 or identity in ids or not isinstance(label,str) or len(label)>2000:raise ValueError('节点无效或重复')
                    ids.add(identity);match=re.match(r'^\[L(\d+)\]:',label);line=int(match.group(1)) if match else None
                    if line is not None and not 1<=line<=line_count:raise ValueError('节点行号越界')
                    normalized.append(dict(id=identity,label=label,line=line))
                clean_edges=[]
                for edge in edges:
                    if not isinstance(edge,dict) or edge.get('from') not in ids or edge.get('to') not in ids:raise ValueError('依赖边端点不存在')
                    clean_edges.append({'from':edge['from'],'to':edge['to']})
                output.append(dict(graph_type='Ddg',nodes=normalized,edges=clean_edges))
            return _result('VALID','数据依赖结构已返回',{'graphs':output}) if output else _result('EMPTY','未返回非空DDG')
        symbols=response.get('symbols',container.get('symbols'))
        dependencies=response.get('dependencies',container.get('dependencies',[]))
        if not isinstance(symbols,list) or len(symbols)>1000 or not isinstance(dependencies,list) or len(dependencies)>5000:raise ValueError('符号结构无效或超限')
        clean=[]
        for item in symbols:
            if not isinstance(item,dict) or not isinstance(item.get('symbol'),str) or len(item['symbol'])>2000:raise ValueError('符号字段无效')
            appears=item.get('appears_in',[])
            if not isinstance(appears,list) or any(not isinstance(s,str) or len(s)>100 for s in appears):raise ValueError('符号来源无效')
            clean.append(dict(symbol=item['symbol'],appears_in=appears))
        return _result('VALID','结构线索已返回',{'symbols':clean,'dependency_count':len(dependencies)}) if clean else _result('EMPTY','未返回符号')
    except (ValueError,TypeError,KeyError) as exc:
        return _result('INVALID',str(exc))
