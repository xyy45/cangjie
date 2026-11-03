"""Collect closed object headers; body acceptance remains the typed Parser's job."""
from nexus.repair import object_values


class Cursor:
    def __init__(self,items):self.items=items;self.pos=0
    def peek(self):return self.items[self.pos][0]
    def take(self,expected=None):
        value=self.peek()
        if value=='<eof>' or expected is not None and value!=expected:raise ValueError('对象声明语法无效，预期 '+str(expected))
        self.pos+=1;return value
    def accept(self,value):
        if self.peek()!=value:return False
        self.pos+=1;return True
    def name(self):return object_values.name(self.take())
    def type(self):
        value=self.take()
        if value=='Array':
            self.take('<');self.take('Int64');self.take('>');return 'Array<Int64>'
        if value in object_values.LEAVES:return value
        parts=[object_values.name(value)]
        while self.accept('.'):parts.append(object_values.name(self.take()))
        return '.'.join(parts)
    def params(self):
        self.take('(');result=[]
        if self.peek()!=')':
            while True:
                identifier=self.name();self.take(':');kind=self.type()
                if len(result)>=4 or identifier in {p['name'] for p in result}:raise ValueError('对象参数重复或超过4项')
                result.append(dict(name=identifier,type=kind))
                if not self.accept(','):break
        self.take(')');return result
    def block(self):
        start=self.pos;self.take('{');depth=1
        while depth:
            value=self.take();depth+=int(value=='{')-int(value=='}')
            if depth>32:raise ValueError('对象方法嵌套过深')
        return self.items[start:self.pos]


def collect(source,*,validate=True,header=None):
    from nexus.uploads.language import tokens
    items=header['body_items'] if header is not None else tokens(source)
    cursor=Cursor(items);types={};declarations={};methods=[];top=[];package=header['package'] if header is not None else None
    if cursor.peek()=='package':
        start=cursor.pos;cursor.take();package=cursor.name();cursor.accept(';');top.extend(items[start:cursor.pos])
    while cursor.peek()!='<eof>':
        start=cursor.pos;public=cursor.accept('public');kind=cursor.peek()
        if kind=='func':
            # Preserve every original token and line for the existing typed gate.
            cursor.take()
            while cursor.peek()!='{':cursor.take()
            cursor.block();top.extend(items[start:cursor.pos]);continue
        if not public or kind not in ('struct','class'):raise ValueError('仅支持public对象声明与普通顶层函数')
        cursor.take();identifier=cursor.name();line=items[start][1]
        if identifier in types or len(types)>=4:raise ValueError('对象类型重复或超过4项')
        cursor.take('{');fields=[]
        while cursor.peek()=='public' and items[cursor.pos+1][0]=='let':
            cursor.take('public');cursor.take('let');field=cursor.name();cursor.take(':');field_type=cursor.type()
            fields.append(dict(name=field,type=field_type));cursor.accept(';')
        fields=object_values.parameters(fields,object_values.LEAVES,4,1)
        cursor.take('public');constructor_line=items[cursor.pos][1];cursor.take('init');constructor=cursor.params()
        if constructor!=fields:raise ValueError('构造参数必须与字段名称、类型及顺序相同')
        cursor.take('{')
        for field in fields:
            cursor.take('this');cursor.take('.');cursor.take(field['name']);cursor.take('=');cursor.take(field['name']);cursor.accept(';')
        cursor.take('}');constructor_end=items[cursor.pos-1][1];declared_methods=[];seen={f['name'] for f in fields}|{identifier}
        while cursor.peek()!='}':
            cursor.take('public');cursor.take('func');method_line=items[cursor.pos][1];method=cursor.name()
            if method in seen or len(declared_methods)>=4:raise ValueError('方法重复、遮蔽或超过4项')
            params=cursor.params();cursor.take(':');returned=cursor.type();body=cursor.block();signature=dict(name=method,params=params,return_type=returned)
            declared_methods.append(signature);seen.add(method)
            methods.append(dict(owner=identifier,**signature,line=method_line,end_line=body[-1][1],body=body))
        cursor.take('}');cursor.accept(';')
        types[identifier]=dict(kind=kind,fields=fields,constructor=constructor,methods=declared_methods)
        declarations[identifier]=dict(line=line,end_line=items[cursor.pos-1][1],constructor_line=constructor_line,constructor_end_line=constructor_end)
    if validate:types=object_values.registry(types)
    top.append(items[-1])
    return dict(package=package,types=types,declarations=declarations,methods=methods,top_items=top)
