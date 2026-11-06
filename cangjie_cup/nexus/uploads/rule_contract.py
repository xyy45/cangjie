"""Bounded suggestions, never authoritative business specifications.

Only user-confirmed material may later become a frozen oracle. This module does
not execute uploaded code, start a task, invoke a model, or write project files.
"""
from copy import deepcopy
import hashlib
import json

from pydantic import BaseModel,ConfigDict,Field,ValidationError

from nexus.contracts import digest
from nexus.policy.core import strict_json
from nexus.uploads.language import inspect_source,validate_examples
from nexus.uploads.service import validate_goal
from nexus.repair.oracle import validate_contract,input_key,stable_signature
from nexus.repair.values import has_strings,has_arrays
from nexus.repair.object_values import has_objects

PROTOCOL='business-rule-draft-v1'
MAX_RESPONSE=1024*1024
MAX_CONTEXT=220000
RESULT_VERSION=2


def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()


class RuleSuggestion(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    schema_version:int
    summary:str=Field(min_length=1,max_length=2000)
    assumptions:list[str]=Field(max_length=10)
    questions:list[str]=Field(max_length=10)
    examples:list[dict]|None=None
    oracle:dict|None=None


def draft_snapshot(uploads,identity,*,actor_id,expected_version,function,allowed_paths=None):
    value=uploads.get(identity,actor_id=actor_id)
    if (type(expected_version) is not int or expected_version!=value['version'] or value['status']!='DRAFT' or
            not isinstance(function,str)):
        raise ValueError('请选择当前未冻结的上传版本和函数')
    validate_goal(value['goal'])
    directory=uploads.store.root/'uploads'/identity
    if value.get('kind')=='PROJECT':
        from nexus.projects.index import inspect_project
        original=directory/'original'
        material={p:(original/p).read_bytes() for p in value['original_manifest']}
        info=inspect_project(material)
        if info!=value['project_index']:raise ValueError('工程索引与原始源码不符')
        allowed=info['production_paths'] if allowed_paths is None else allowed_paths
        if (type(allowed) is not list or not 1<=len(allowed)<=3 or any(type(p) is not str or p not in info['production_paths'] for p in allowed) or
                len(set(allowed))!=len(allowed)):
            raise ValueError('请选择1至3个已有生产文件')
        paths=sorted(allowed);files={p:material[p].decode('utf-8') for p in paths}
        selected=next((f for f in info['functions'] if f['name']==function and f['path'] in paths),None)
    else:
        if allowed_paths is not None:raise ValueError('单文件草案不接受工程路径参数')
        raw=(directory/'source.cj').read_bytes();info=inspect_source(raw.decode('utf-8'))
        paths=['src/uploaded.cj'];files={paths[0]:raw.decode('utf-8')}
        selected=next((f for f in info['functions'] if f['name']==function),None)
    if selected is None:raise ValueError('函数不在选定的生产源码范围内')
    signature=stable_signature(selected)
    snapshot=dict(schema_version=1,protocol=PROTOCOL,upload_id=identity,upload_version=value['version'],
                  source_sha256=value['source_sha256'],goal=value['goal'],signature=signature,
                  allowed_paths=paths,files=files)
    if len(encoded(snapshot))>MAX_CONTEXT:raise ValueError('所选源码和需求超出草案上下文预算')
    return {**snapshot,'binding_hash':digest(snapshot)}


def validate_suggestion(raw,snapshot,*,result_version=RESULT_VERSION):
    if type(result_version) is not int or result_version not in (1,RESULT_VERSION):
        raise ValueError('草案结果版本无效')
    if (type(snapshot) is not dict or snapshot.get('binding_hash')!=digest({k:v for k,v in snapshot.items() if k!='binding_hash'}) or
            snapshot.get('protocol')!=PROTOCOL):
        raise ValueError('草案输入绑定已变化')
    base=dict(schema_version=result_version,binding_hash=snapshot['binding_hash'],business_verified=False,
              examples_json=None,oracle_json=None,normalized_oracle=None,suggestion=None,raw_hash=None,normalized_hash=None)
    def invalid(code,reason):return {**base,'status':'INVALID','code':code,'reason':reason}
    if type(raw) is not str or len(raw.encode('utf-8'))>MAX_RESPONSE:
        return invalid('RESPONSE_LIMIT','草案响应为空、类型无效或超过1MiB')
    base['raw_hash']=hashlib.sha256(raw.encode('utf-8')).hexdigest()
    try:parsed=strict_json(raw)
    except (ValueError,TypeError,RecursionError):return invalid('JSON_INVALID','草案必须是无重复字段的有限JSON对象')
    try:
        if type(parsed) is not dict or type(parsed.get('schema_version')) is not int or parsed['schema_version']!=1:
            raise ValueError('schema')
        fields=parsed
        if result_version>=2 and type(parsed.get('oracle')) is not dict:
            fields={**parsed,'oracle':None}
        suggestion=RuleSuggestion.model_validate(fields)
        if (not suggestion.summary.strip() or any(not x.strip() or len(x)>400 for x in suggestion.assumptions+suggestion.questions)):
            raise ValueError('text')
    except (ValueError,ValidationError,TypeError,RecursionError):return invalid('SCHEMA_INVALID','草案字段、版本、文本长度或类型无效')
    clean=suggestion.model_dump()
    if suggestion.questions:
        # Even a coherent provisional rule cannot be applied until clarified.
        clean.update(examples=None,oracle=None)
        return {**base,'status':'NEEDS_CLARIFICATION','reason':'请补全预期行为后重新准备上传，草案尚不能应用',
                'suggestion':clean,'normalized_hash':digest(clean)}
    try:
        examples=deepcopy(validate_examples({'functions':[snapshot['signature']],**({'types':snapshot['signature']['types']} if has_objects(snapshot['signature']) else {})},snapshot['signature']['name'],suggestion.examples))
        seen={}
        for e in examples:
            k=input_key(e['args']);value=(type(e['expected']).__name__,e['expected'])
            if k in seen and seen[k]!=value:raise ValueError('contradictory examples')
            seen[k]=value
        examples_json=json.dumps(examples,ensure_ascii=False,indent=2)
        if len(examples_json.encode('utf-8'))>8192:raise ValueError('examples budget')
    except (ValueError,TypeError,KeyError,RecursionError):return invalid('EXAMPLES_INVALID','公开示例必须含target和regression，参数、预期类型有效且无矛盾')
    clean.update(examples=examples)
    try:
        strings=has_strings(snapshot['signature']);arrays=has_arrays(snapshot['signature']);objects=has_objects(snapshot['signature'])
        scoped='scope' in snapshot['signature']
        if (type(suggestion.oracle) is not dict or type(suggestion.oracle.get('version')) is not int or
                suggestion.oracle['version']!=(6 if scoped else 5 if objects else 4 if arrays else 3 if strings else 1) or (scoped or strings or arrays or objects) and suggestion.oracle.get('excluded_inputs')!=[]):
            raise ValueError('草案仅支持公开规则：数值v1、String v3或Array v4，新版本排除集合必须为空')
        normalized=validate_contract(deepcopy(suggestion.oracle),snapshot['signature'],examples)
        oracle_json=json.dumps(suggestion.oracle,ensure_ascii=False,indent=2)
        if len(oracle_json.encode('utf-8'))>8192:raise ValueError('rule budget')
    except (ValueError,TypeError,KeyError,RecursionError,OverflowError):
        if result_version==1:
            return invalid('RULE_INVALID','独立规则的字段、参数域、表达式或公开例子一致性校验未通过')
        omitted=parsed.get('oracle') is None
        clean.update(oracle=None)
        return {**base,'status':'EXAMPLES_READY','code':'RULE_OMITTED' if omitted else 'RULE_INVALID',
                'reason':'未生成独立规则' if omitted else '独立规则校验未通过',
                'suggestion':clean,'normalized_hash':digest(clean),'examples_json':examples_json}
    return {**base,'status':'DRAFT_READY','reason':'结构和例子一致性已校验，业务含义仍需用户逐项确认',
            'suggestion':clean,'normalized_hash':digest(clean),'examples_json':examples_json,'oracle_json':oracle_json,'normalized_oracle':normalized}
