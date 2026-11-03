"""Validate/copy scoped callable data; frozen-source rebinding is still required.

A well-formed scope is not an authorization or proof of source ownership. The
upload/probe services must independently rebuild it from their frozen index.
"""
from copy import deepcopy
from pathlib import PurePosixPath
import re

from nexus.projects.archive import safe_name
from nexus.projects.names import local_name, package_name, symbol_name
from nexus.repair import object_values

SCOPE_KEYS={'version','root_package','package','local_name','path','graph_hash'}


def reject_qualified_legacy(signature):
    """Canonical identities require a scope; old versions cannot discard it."""
    if type(signature) is dict and 'scope' not in signature:
        name=signature.get('name'); types=signature.get('types',{})
        if (type(name) is str and '.' in name or type(types) is dict and
                any(type(key) is str and '.' in key for key in types)):
            raise ValueError('带包规范名必须使用Scoped签名与版本')


def validate(signature):
    if type(signature) is not dict or not {'name','params','return_type','scope'} <= set(signature):
        raise ValueError('Scoped签名缺少必要字段')
    scope=signature['scope']
    if (type(scope) is not dict or set(scope)!=SCOPE_KEYS or
            type(scope['version']) is not int or scope['version']!=1):
        raise ValueError('Scoped来源结构或版本无效')
    root=package_name(scope['root_package']); package=package_name(scope['package'])
    local=local_name(scope['local_name'])
    if '.' in root or not (package==root or package.startswith(root+'.')):
        raise ValueError('Scoped包不属于冻结构建根')
    name=symbol_name(signature['name'])
    if name!=package+'.'+local:raise ValueError('规范函数名与scope不一致')
    if type(scope['graph_hash']) is not str or not re.fullmatch('[0-9a-f]{64}',scope['graph_hash']):
        raise ValueError('Scoped依赖图摘要无效')
    path=scope['path']
    if type(path) is not str:raise ValueError('Scoped来源路径须为字符串')
    safe_name(path); parsed=PurePosixPath(path)
    expected='/'.join(['src',*package.split('.')[1:]])
    if parsed.suffix!='.cj' or path.endswith('_test.cj') or str(parsed.parent)!=expected:
        raise ValueError('Scoped入口必须来自对应包的生产文件')
    declarations=object_values.registry(signature.get('types',{}))
    for identifier in declarations:
        symbol_name(identifier); owner=identifier.rsplit('.',1)[0]
        if not (owner==root or owner.startswith(root+'.')):
            raise ValueError('Scoped对象注册表必须来自同一构建根')
    kinds=object_values.LEAVES|set(declarations)
    params=object_values.parameters(signature['params'],kinds,4)
    for param in params:local_name(param['name'])
    returned=signature['return_type']
    if type(returned) is not str or returned not in kinds:raise ValueError('Scoped返回类型无效')
    result=dict(name=name,params=params,return_type=returned,scope=deepcopy(scope))
    if returned in declarations or any(p['type'] in declarations for p in params):
        result['types']=declarations
    return result
