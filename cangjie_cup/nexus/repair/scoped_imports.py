"""SDK1.0.5 caps an import specifier at200, not canonical symbol identity."""
from nexus.projects.names import local_name,symbol_name,fresh_name

MAX_SPECIFIER=200


def imports(refs):
    output=[];aliases={}
    for symbol,reference in refs.items():
        symbol_name(symbol)
        if type(reference) is not str:raise ValueError('SDK符号引用须为名称')
        parts=reference.split('.')
        if not 1<=len(parts)<=2:raise ValueError('SDK引用仅支持别名或包别名成员')
        for part in parts:local_name(part)
        if len(parts)==1:
            if len(symbol)>MAX_SPECIFIER:raise ValueError('长符号不能直接导入')
            specifier=symbol;context=('symbol',symbol)
        else:
            owner,member=symbol.rsplit('.',1)
            if parts[1]!=member:raise ValueError('SDK成员引用与规范身份不一致')
            specifier=owner;context=('package',owner)
        if parts[0] in aliases and aliases[parts[0]]!=context:raise ValueError('SDK导入别名来源冲突')
        aliases[parts[0]]=context
        statement='import '+specifier+' as '+parts[0]
        if statement not in output:output.append(statement)
    return output


def references(symbols,reserved):
    long_owners={symbol_name(symbol).rsplit('.',1)[0] for symbol,_ in symbols if len(symbol)>MAX_SPECIFIER}
    packages={};refs={}
    for symbol,stem in symbols:
        owner,member=symbol.rsplit('.',1)
        if owner in long_owners:
            if owner not in packages:packages[owner]=fresh_name(stem,reserved)
            refs[symbol]=packages[owner]+'.'+member
        else:refs[symbol]=fresh_name(stem,reserved)
    return refs,imports(refs)
