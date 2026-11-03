"""Closed primitive values shared by String contracts and trusted source literals.

No normalization, implicit casts, expression evaluation or candidate execution.
"""

MAX_STRING_BYTES=256
MAX_ARRAY_LENGTH=16
LOW=-(1<<63)
HIGH=(1<<63)-1


def string(value):
    if type(value) is not str:raise ValueError('字符串必须为原始String值')
    try:encoded=value.encode('utf-8',errors='strict')
    except UnicodeError:raise ValueError('String不能包含Unicode代理字符') from None
    if len(encoded)>MAX_STRING_BYTES:raise ValueError('String最多256个UTF-8字节')
    return value


def byte_len(value):return len(string(value).encode('utf-8'))


def rune_len(value):return len(string(value))


def array(value):
    if type(value) is not list or len(value)>MAX_ARRAY_LENGTH:
        raise ValueError('Array<Int64>必须为最多16项的原始数组')
    return [primitive(item,'Int64') for item in value]


def primitive(value,kind,types=None):
    if kind=='Array<Int64>':return array(value)
    if kind=='String':return string(value)
    if kind=='Bool' and type(value) is bool:return value
    if kind=='Int64' and type(value) is int and LOW<=value<=HIGH:return value
    if types is not None:
        from nexus.repair import object_values
        return object_values.value(value,kind,types)
    raise ValueError('原始值类型或Int64范围无效')


def typed_key(value,types=None):
    if type(value) is dict:
        from nexus.repair import object_values
        return object_values.typed_key(value,types)
    if type(value) is list:return 'Array<Int64>',tuple(array(value))
    kind={bool:'Bool',int:'Int64',str:'String'}.get(type(value))
    primitive(value,kind)
    return kind,value


def primitive_weight(value,types=None):
    if type(value) is dict:
        from nexus.repair import object_values
        return object_values.weight(value,types)
    kind,_=typed_key(value)
    if kind=='Array<Int64>':return len(value)+sum(abs(item) for item in value)
    return byte_len(value) if kind=='String' else abs(int(value))


def string_literal(value):
    # Escape every scalar, including dollar signs: data cannot become interpolation.
    return '"'+''.join(chr(92)+'u{'+format(ord(c),'x')+'}' for c in string(value))+'"'


def decode_string_literal(text):
    if type(text) is not str or len(text)<2 or text[0]!='"' or text[-1]!='"':
        raise ValueError('仅支持普通双引号String字面量')
    result=[];i=1;end=len(text)-1
    escapes={'n':chr(10),'r':chr(13),'t':chr(9),'"':'"',chr(92):chr(92)}
    while i<end:
        c=text[i]
        if c==chr(92):
            i+=1
            if i>=end:raise ValueError('String转义未结束')
            escape=text[i]
            if escape in escapes:result.append(escapes[escape]);i+=1;continue
            if escape!='u' or i+1>=end or text[i+1]!='{':raise ValueError('String转义不属于支持子集')
            close=text.find('}',i+2,end);digits=text[i+2:close] if close>=0 else ''
            if not 1<=len(digits)<=6 or any(c not in '0123456789abcdefABCDEF' for c in digits):
                raise ValueError('String Unicode转义无效')
            point=int(digits,16)
            if point>0x10ffff or 0xd800<=point<=0xdfff:raise ValueError('String转义必须为Unicode标量')
            result.append(chr(point));i=close+1
        else:
            if c=='"' or ord(c)<32 or c=='$' and i+1<end and text[i+1]=='{':
                raise ValueError('String不支持插值、原始控制字符或未转义引号')
            result.append(c);i+=1
    return string(''.join(result))


def has_strings(signature):
    return signature['return_type']=='String' or any(p['type']=='String' for p in signature['params'])


def has_arrays(signature):
    return signature['return_type']=='Array<Int64>' or any(p['type']=='Array<Int64>' for p in signature['params'])
