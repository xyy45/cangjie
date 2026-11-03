"""V5 scoped harness and complete single-package observation binding.

This raw observation layer does not evaluate the business contract. Whole user
project verification additionally requires compiler-graph/XML evidence.
"""
from copy import deepcopy
import re

from nexus.adapters.cangjie.report_parser import ANSI,parse_test_report
from nexus.contracts import digest
from nexus.repair import scoped_values,values
from nexus.repair.scoped_material import material,nonce as valid_nonce,fresh
from nexus.repair.scoped_signature import validate
from nexus.repair import scoped_harness

TP_HEADER=re.compile(r'^\s*TP:\s*([A-Za-z_][A-Za-z0-9_.]*),\s*(?:time elapsed:\s*\d+(?:\.\d+)?\s*(?:ns|[μµu]s|ms|s),\s*)?RESULT:\s*$')


def case_ids(signature,count,nonce,mode):
    signature=validate(signature);valid_nonce(nonce)
    if type(mode) is not str or mode not in (*scoped_values.PROTOCOLS,'sequence'):raise ValueError('V5观测模式无效')
    if type(count) is not int or not 1<=count<=(16 if mode=='sequence' else 256 if mode=='oracle' else 128):raise ValueError('V5观测数量无效')
    package=signature['scope']['root_package']+'.nexus_verify_'+nonce
    cls=('NexusSequencesV5' if mode=='sequence' else scoped_values.PROTOCOLS[mode][1])+nonce
    return [package+'.'+cls+'.case'+str(i) for i in range(count)]


def validate_inputs(signature,inputs):
    signature=validate(signature)
    if type(inputs) is not list or not 1<=len(inputs)<=256:raise ValueError('V5输入数量无效')
    for args in inputs:
        if type(args) is not list or len(args)!=len(signature['params']):raise ValueError('V5参数数量无效')
        for item,param in zip(args,signature['params']):values.primitive(item,param['type'],signature.get('types',{}))
    return signature


def render(signature,cases,*,nonce,mode,binding,contract=None):
    if mode=='sequence':
        from nexus.repair import scoped_sequence
        return scoped_sequence.render(signature,cases,nonce=nonce,binding=binding,contract=contract)
    signature=validate_inputs(signature,cases);ids=case_ids(signature,len(cases),nonce,mode)
    if contract is not None:raise ValueError('单次V5观测不接收序列契约')
    cls=ids[0].rsplit('.',2)[1];parts=scoped_harness.header(signature,binding,nonce,cls)
    text=parts['source'];kind=signature['return_type'];prefix=scoped_values.PROTOCOLS[mode][0]
    for index,(args,identity) in enumerate(zip(cases,ids)):
        variable=fresh('__nexusObserved_'+nonce,parts['reserved'])
        text+='@TestCase\nfunc case'+str(index)+'() {\n'
        text+='let '+variable+' = '+parts['target']+'('+', '.join(scoped_harness.input_literal(v,p['type'],parts) for v,p in zip(args,signature['params']))+')\n'
        text+=scoped_harness.limit_guard(kind,variable,parts,nonce,identity)
        text+=parts['output']+'("'+prefix+nonce+'|'+identity+'|'+kind+'|${'+scoped_harness.wire(kind,variable,parts)+'}")\n}\n'
    return dict(source=(text+'}\n').encode(),path='src/nexus_verify_'+nonce+'/nexus_observations_test.cj',
        case_ids=ids,binding_hash=digest(binding))


def execution(log,signature,expected,*,nonce,mode,exit_code,problem):
    """Check the sole generated test package, not the whole uploaded project."""
    signature=validate(signature)
    if type(expected) is not list or expected!=case_ids(signature,len(expected),nonce,mode):raise ValueError('V5用例绑定无效')
    unknown=dict(state='UNKNOWN',execution_state='UNKNOWN',counts={},reason='V5执行或用例绑定不完整')
    try:size=len(log.encode('utf-8')) if type(log) is str else 2*1024*1024+1
    except UnicodeError:return unknown
    if size>2*1024*1024:return unknown
    try:parsed=parse_test_report(log)
    except (ValueError,TypeError,RecursionError,OverflowError):return unknown
    unknown.update(execution_state=parsed.state,counts=parsed.counts)
    package,cls,_=expected[0].rsplit('.',2);local_ids={cls+'.'+i.rsplit('.',1)[1] for i in expected}
    counts=dict(total=len(expected),passed=len(expected),skipped=0,errors=0,failed=0)
    if (type(exit_code) is not int or exit_code!=0 or problem is not None or parsed.state!='PASS' or
            parsed.counts!=counts or set(parsed.case_results)!=local_ids or any(s!='PASS' for s in parsed.case_results.values())):
        return unknown
    from nexus.repair.primitive_trace import OBSERVATION_PREFIXES,SUITE_HEADER
    clean=ANSI.sub('',log);detail=clean.split('Summary:',1)[0]
    packages=[];suites=[]
    for line in detail.splitlines():
        if line.strip().startswith(OBSERVATION_PREFIXES):continue
        if line.strip().startswith('TP:'):
            match=TP_HEADER.fullmatch(line)
            if not match:return unknown
            packages.append(match.group(1))
        match=SUITE_HEADER.fullmatch(line)
        if match:suites.append(match.group(1))
    if packages!=[package] or suites!=[cls] or any(line.strip().startswith(OBSERVATION_PREFIXES) for line in clean[len(detail):].splitlines()):return unknown
    return dict(state='PASS',execution_state='PASS',counts=parsed.counts,reason='',clean=clean,detail=detail,package=package)


def read(log,signature,expected,*,nonce,mode,exit_code,problem):
    if mode=='sequence':raise ValueError('逐步序列观测需要对应的序列契约解释器')
    checked=execution(log,signature,expected,nonce=nonce,mode=mode,exit_code=exit_code,problem=problem)
    unknown={k:checked[k] for k in ('execution_state','counts','reason')};unknown.update(state='UNKNOWN',observations=[])
    if checked['state']!='PASS':return unknown
    from nexus.repair.primitive_trace import OBSERVATION_PREFIXES,SUITE_HEADER,CASE
    prefix=scoped_values.PROTOCOLS[mode][0];suite=None;case=None;stdout=False;found={};offset=0
    for line in checked['detail'].splitlines(keepends=True):
        stripped=line.strip();reserved=stripped.startswith(OBSERVATION_PREFIXES)
        header=None if reserved else SUITE_HEADER.fullmatch(line.rstrip('\r\n'))
        item=None if reserved else CASE.fullmatch(line.rstrip('\r\n'))
        if header:suite=checked['package']+'.'+header.group(1);case=None;stdout=False
        elif item:case=suite+'.'+item.group(2) if suite else None;stdout=False
        elif stripped in ('STDOUT:','STDERR:'):stdout=stripped=='STDOUT:'
        elif reserved:
            fields=line.lstrip().rstrip('\r\n').split('|')
            if (not stripped.startswith(prefix) or not stdout or case not in expected or case in found or len(fields)!=5 or
                    fields[1]!=nonce or fields[2]!=case or fields[3]!=signature['return_type']):return unknown
            try:actual=scoped_values.decode(fields[4],signature['return_type'],signature.get('types',{}))
            except ValueError:return unknown
            found[case]=dict(test_id=case,actual_return=actual,source=dict(coordinate='ANSI_STRIPPED_FULL_LOG',start_char=offset,end_char=offset+len(line.rstrip('\r\n'))))
        offset+=len(line)
    if set(found)!=set(expected):return unknown
    return dict(state='PASS',execution_state='PASS',counts=checked['counts'],observations=[deepcopy(found[i]) for i in expected],reason='')
