"""Deterministic display-only derivation from a source-bound SymPas text table.

The original engine verdict and response bytes are never upgraded or rewritten.
"""
import hashlib
import json
import re

from nexus.analysis.normalize import validate_source

PARSER_VERSION='sympas-text-v1'
NOTICE='从工具文本日志解析；原引擎后续检查未通过，未验证切片语义正确性，不作为有效模型依据。'


def encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2).encode()


def recover(record_bytes,source,observation):
    """Return a bounded derived object, or None when no known table is present."""
    expected=observation['raw_sha256']
    if len(record_bytes)>3*1024*1024 or hashlib.sha256(record_bytes).hexdigest()!=expected:
        raise ValueError('切片原始记录摘要不符')
    record=json.loads(record_bytes)
    actual=validate_source(source['filename'],source['code'].encode())
    args=record.get('input',{})
    if (actual['source_sha256']!=source['source_sha256'] or record.get('source_sha256')!=actual['source_sha256'] or
            observation.get('source_sha256')!=actual['source_sha256'] or record.get('tool')!='sympas_slice' or
            args.get('code')!=actual['code'] or args.get('filename')!=actual['filename'] or
            args.get('lang')!='cangjie' or args.get('direction')!='Bwd' or args.get('method')!='SymPas'):
        raise ValueError('切片日志不属于当前源码或支持的分析方式')
    response=record.get('response')
    if record.get('http_status')!=200 or not isinstance(response,dict):return None
    log=response.get('raw_output')
    if not isinstance(log,str) or 'Backward Static SliceTable:' not in log:return None
    base=dict(schema_version=1,status='REJECTED',origin='TOOL_LOG',parser_version=PARSER_VERSION,
        source_sha256=actual['source_sha256'],raw_sha256=expected,raw_ref=observation['raw_ref'],
        original_status=observation['status'],notice=NOTICE,slices={})
    lines=log.splitlines()
    try:
        markers=[i for i,line in enumerate(lines) if line.strip()=='Backward Static SliceTable:']
        if len(markers)!=1:raise ValueError('切片表数量不唯一')
        marker=markers[0]
        headers=[i for i in range(marker+1,min(len(lines),marker+12))
            if re.fullmatch(r'Variable\s+SrcLineNumbers',lines[i].strip())]
        if len(headers)!=1:raise ValueError('缺少已知切片表头')
        header=headers[0]
        if header+1>=len(lines) or not re.fullmatch(r'-{3,}',lines[header+1].strip()):
            raise ValueError('切片表分隔符不符合格式')
        result={};end=header+2
        while end<len(lines) and lines[end].strip():
            if len(result)>=500:raise ValueError('切片变量数量超限')
            row=re.fullmatch(r'\s*([\w.$:@%<>-]{1,500})\s+\{\s*"([^"\r\n]+)"\s*\}\s*',lines[end])
            if not row:raise ValueError('切片表存在畸形行')
            symbol,payload=row.groups()
            if symbol in result:raise ValueError('切片变量重复')
            content=re.fullmatch(r'([^:\[\]]+):\s*\[([0-9, \t]*)\]',payload)
            if not content or content[1]!=actual['filename']:raise ValueError('切片文件不匹配或行号格式无效')
            tokens=content[2].split(',') if content[2].strip() else []
            if len(tokens)>1000 or any(not re.fullmatch(r'[0-9]{1,4}',n.strip()) for n in tokens):
                raise ValueError('切片行号格式无效或数量超限')
            numbers=[int(n) for n in tokens]
            if any(not 1<=n<=actual['line_count'] for n in numbers):raise ValueError('切片行号超出源码范围')
            result[symbol]=sorted(set(numbers));end+=1
        if not result or not any(result.values()):raise ValueError('切片表为空')
        base.update(status='RECOVERED',slices=result,log_line_range=[header+3,end],reason='已校验文本表格式、文件名与源码行号范围')
    except ValueError as exc:
        base['reason']=str(exc)
    return base


def attach_recovery(report,root):
    """A presentation projection only; no RunStore/result.json changes."""
    if report.get('status') in ('READY','RUNNING','IN_DOUBT'):return report
    if any(o['tool']=='sympas_slice_table' for o in report.get('observations',[])):return report
    observed=next((o for o in report.get('observations',[]) if o['tool']=='sympas_slice'),None)
    if not observed or observed['status']=='VALID':return report
    if observed.get('raw_ref')!='observations/sympas_slice.json':raise ValueError('未知切片原始引用')
    path=root/observed['raw_ref']
    if path.is_symlink():raise ValueError('切片原始记录引用无效')
    derived=recover(path.read_bytes(),report['source'],observed)
    if derived:report['derived_slice']=derived
    return report
