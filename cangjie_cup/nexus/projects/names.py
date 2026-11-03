"""Separate bounded identities from expressions and user-facing labels.

These functions only validate names. A valid identity grants no source access.
"""
import re

IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]{0,63}')
RESERVED = set('package public private protected func let var if else while return break continue for in true false Int64 Bool String Array import as class struct init this mut main unsafe static open override interface extend prop foreign throw try catch finally match case enum type'.split())
RESERVED.update('print println eprint eprintln readln panic exit sleep Int8 Int16 Int32 IntNative UInt8 UInt16 UInt32 UInt64 UIntNative Float16 Float32 Float64 Rune Unit Nothing CString Any Object'.split())


def local_name(value):
    if type(value) is not str or not IDENTIFIER.fullmatch(value) or value in RESERVED:
        raise ValueError('局部标识符须为非预留ASCII名称，最多64字符')
    return value


def fresh_name(stem,reserved):
    local_name(stem)
    for index in range(len(reserved)+1):
        candidate=stem+('_'+format(index,'x') if index else '')
        local_name(candidate)
        if candidate not in reserved:
            reserved.add(candidate);return candidate
    raise ValueError('无法分配有界验证名称')


def package_name(value):
    if type(value) is not str or len(value) > 191:
        raise ValueError('包名最多191字符')
    parts = value.split('.')
    if not 1 <= len(parts) <= 8 or parts[0] in ('std', 'cangjie'):
        raise ValueError('包名段数或来源无效')
    for part in parts:
        local_name(part)
        if part.casefold().startswith('nexus_verify_'):
            raise ValueError('包名使用了系统保留命名空间')
    return value


def symbol_name(value):
    if type(value) is not str or len(value) > 256 or '.' not in value:
        raise ValueError('规范符号须含包名，最多256字符')
    package, local = value.rsplit('.', 1)
    package_name(package); local_name(local)
    return value


def suite_name(value):
    if type(value) is not str or len(value) > 246:
        raise ValueError('测试套件规范名最多246字符')
    return symbol_name(value)


def case_name(value):
    if type(value) is not str or len(value) > 311 or '.' not in value:
        raise ValueError('测试用例规范名最多311字符')
    suite, local = value.rsplit('.', 1)
    suite_name(suite); local_name(local)
    return value
