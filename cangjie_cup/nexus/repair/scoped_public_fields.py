"""Map bound XML failure text to frozen Cangjie assertion tokens and leaf types.

Original-test observations remain verification-only. String differences are
text evidence, never a canonical complete return value.
"""
from copy import deepcopy
import re
from nexus.contracts import digest,file_hash
from nexus.repair import public_fields as shared,values

# Capture the outer SDK envelope first. Backticks and comparison operators can
# be literal String data inside either operand; split only outside quotes.
EQUALITY=re.compile(r'^[ \t]*Expect Failed: `\(([^\n]{1,69636})\)`[ \t]*\n[ \t]*left: ([^\n]{1,4096})\n[ \t]*right: ([^\n]{1,4096})',re.M)
STRING=re.compile(shared.STRING.pattern.replace('{1,8192}','{1,65536}').replace('{8}','{4,8}'),re.M)
SHORT_STRING=re.compile(r'^[ \t]*Expect Failed: ([^\n]{1,65536}) != ([^\n]{1,4096})\n((?:[ \t]+[^\n]*\n){1,8})',re.M)


def _operands(header,marker):
    quoted=False;separator=None;index=0
    while index<len(header):
        char=header[index]
        if quoted and char==chr(92):
            index+=2;continue
        if char=='"':quoted=not quoted
        elif not quoted and header.startswith(marker,index):
            if separator is not None:raise ValueError('XML断言分隔不唯一')
            separator=index;index+=len(marker);continue
        index+=1
    if quoted or separator is None:raise ValueError('XML断言分隔无效')
    left,right=header[:separator].strip(),header[separator+len(marker):].strip()
    if not 1<=len(left)<=65536 or not 1<=len(right)<=4096:raise ValueError('XML断言操作数超限')
    return left,right


def _string_operands(match):
    return _operands(match.group(1)+' != '+match.group(2),' != ')


def _display_tokens(tokens):
    """Undo exactly the SDK's Stringify display layer, not user evaluation."""
    result=[]
    for token in tokens:
        if token.startswith('"'):
            token='"'+values.decode_string_literal(token)+'"'
            values.decode_string_literal(token)  # The recovered source spelling must itself be a valid Cj literal.
        result.append(token)
    return tuple(result)


def _expected(text,kind,types,expected):
    value=shared.leaf(text,kind,types)
    if kind=='String' and values.typed_key(value)!=values.typed_key(expected):
        value=shared.leaf(''.join(_display_tokens(shared.token_key(text))),kind,types)
    return value


def resolve(check,value,info,files,parsed):
    try:
        if (check.kind!='test' or check.state!='FAIL' or parsed['state']!='FAIL' or
                parsed['case_results']!=check.case_results):raise ValueError('Scoped字段必须属于完整XML失败结果')
        types,mapping,original=shared._mapping(value,info,files);failures=[];cases=[];seen=set();truncated=False
        reports=check.package_evidence['test']['reports']
        for identity,items in parsed['failures'].items():
            if check.case_results.get(identity)!='FAIL':raise ValueError('XML字段引用其他用例')
            report='test-'+identity.rsplit('.',1)[0]+'.xml'
            if report not in reports:raise ValueError('XML字段缺少该次报告绑定')
            for number,item in enumerate(items):
                text=item['text'];origin=item['source']
                if (type(text) is not str or origin!=dict(report=report,case_id=identity,failure_index=number,
                        coordinate='XML_FAILURE_TEXT',start_char=0,end_char=len(text))):
                    raise ValueError('XML字段原文坐标无效')
                typed=list(EQUALITY.finditer(shared.control_text(text)))
                long_strings=list(STRING.finditer(text));other_starts={m.start() for m in (*typed,*long_strings)}
                found=sorted([(m.start(),m,'TYPED') for m in typed]+
                             [(m.start(),m,'TEXT_ONLY') for m in long_strings]+
                             [(m.start(),m,'TEXT_ONLY') for m in SHORT_STRING.finditer(text) if m.start() not in other_starts],key=lambda row:row[0])
                if not found:raise ValueError('XML断言没有可绑定的完整字段文本')
                for _,match,mode in found:
                    typed_diagnostic=mode=='TYPED'
                    expression,expected_text=(_string_operands(match) if mode=='TEXT_ONLY' else
                                              _operands(match.group(1),' == '))
                    raw_tokens=shared.token_key(expression);tokens=raw_tokens
                    binding=mapping.get((identity,tokens))
                    if binding is None and identity not in original:
                        tokens=_display_tokens(tokens);binding=mapping.get((identity,tokens))
                    visibility='PUBLIC';spelling=value['function'].rsplit('.',1)[1];call_tokens=None
                    if binding is None and identity in original:
                        entry=original[identity];call_tokens=entry['call_tokens'];projection=entry.get('projection',[])
                        expected_tokens=tuple(call_tokens)+tuple(token for field in projection for token in ('.',field))
                        # Original assertion spellings may contain escaped quotes,
                        # newlines or backslashes. Match the frozen tokens before
                        # trying the legacy display-layer fallback.
                        if raw_tokens!=expected_tokens:tokens=_display_tokens(raw_tokens)
                        if raw_tokens!=expected_tokens and tokens!=expected_tokens:raise ValueError('XML原调用拼写与冻结token不一致')
                        returned=next(f['return_type'] for f in info['functions'] if f['name']==entry['function'])
                        kind=entry['expected_type'] if projection else returned
                        if kind in types:raise ValueError('对象返回必须逐字段映射')
                        binding=dict(function=entry['function'],args=deepcopy(entry['args']),field_path=projection,
                            expected_value=deepcopy(entry['expected']),value_type=kind,
                            public_test=dict(path=entry['path'],sha256=file_hash(files[entry['path']].decode('utf-8'))))
                        spelling=entry['function_spelling'];visibility='VERIFICATION_ONLY'
                    if binding is None:raise ValueError('XML断言不属于冻结公开模板或原调用')
                    kind=binding['value_type'];expected=binding['expected_value']
                    if values.typed_key(_expected(expected_text,kind,types,expected))!=values.typed_key(expected):
                        raise ValueError('XML断言预期与冻结业务值不一致')
                    if kind=='String':mode='TEXT_ONLY'
                    if mode=='TYPED':
                        actual=shared.leaf(match.group(2).strip(),kind,types)
                        if values.typed_key(shared.leaf(match.group(3).strip(),kind,types))!=values.typed_key(expected):
                            raise ValueError('XML诊断右值变化')
                        actual_text=match.group(2).strip()
                    else:
                        if kind!='String':raise ValueError('仅String允许差异文本反馈')
                        actual=None;actual_text=match.group(2 if typed_diagnostic else 3)
                    key=(identity,tuple(binding['field_path']))
                    if key in seen:raise ValueError('XML字段断言重复')
                    seen.add(key)
                    reference=reports[report]
                    source=dict(log_ref=check.log_ref,coordinate='XML_FAILURE_TEXT',xml_ref=reference['ref'],
                        xml_sha256=reference['sha256'],report=report,case_id=identity,failure_index=number,
                        start_char=match.start(),end_char=match.end())
                    call_id='PUBLIC_FIELD-'+digest(dict(test_id=identity,path=binding['field_path'],source=source))[:16]
                    fact=dict(kind='public_field',test_id=identity,call_id=call_id,**deepcopy(binding),
                        function_spelling=spelling,call_tokens=deepcopy(call_tokens),visibility=visibility,
                        actual_value=deepcopy(actual),value_state=mode,actual_text=actual_text[:1024],text_truncated=len(actual_text)>1024,
                        actual=actual_text[:1024],expected=shared.json_text(expected),requirement_refs=['REQ-UPLOAD'],
                        mapping_basis='FROZEN_SCOPED_XML_FIELD',source=source)
                    failures.append(fact)
                    cases.append({key:deepcopy(fact[key]) for key in ('test_id','call_id','function','args','field_path','expected_value','value_type','requirement_refs','visibility')})
                    if len(failures)==50:truncated=True;break
                if truncated:break
            if truncated:break
        return dict(cases=cases,failures=failures,truncated=truncated)
    except (KeyError,TypeError,StopIteration,IndexError,UnicodeError,RecursionError) as exc:
        raise ValueError('Scoped XML字段映射无效') from exc
