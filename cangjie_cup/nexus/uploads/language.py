"""A restricted bounded-value Cangjie gate, not a general Cangjie type checker.

Every identifier is a local primitive or a declared function; there are no imports,
general members, macros, constructors, attributes or top-level initialization.
The pinned compiler still decides whether a permitted program compiles.
"""
import re
from nexus.repair.values import decode_string_literal,string_literal,primitive,array

TOKEN=re.compile(r'\s+|//[^\n]*|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|==|!=|<=|>=|&&|\|\||[{}\[\]():,;=+*/%!<>.-]')
NAME=re.compile(r'[A-Za-z_][A-Za-z_0-9]{0,63}\Z')
RESERVED=set('package public func let var if else while return break continue for in true false Int64 Bool String import class unsafe'.split())
PRELUDE_NAMES={'print','println','eprint','eprintln','readln','panic','exit','sleep'}
PRECEDENCE={'||':1,'&&':2,'==':3,'!=':3,'<':4,'>':4,'<=':4,'>=':4,'+':5,'-':5,'*':6,'/':6,'%':6}


def tokens(source,*,pattern=TOKEN):
    if not isinstance(source,str) or not source.strip() or len(source.encode())>65536 or len(source.splitlines())>1000:
        raise ValueError('源码限64KiB／1000行')
    # Keep comment boundaries identical to the compiler's common newline forms.
    # Source bytes remain unchanged; only the syntax gate normalizes CRLF.
    source=source.replace('\r\n','\n')
    if any((ord(c)<32 and c not in '\n\t') or c in '\u0085\u2028\u2029' for c in source):
        raise ValueError('源码仅支持LF或CRLF换行，不支持其他控制字符')
    result=[];pos=0
    while pos<len(source):
        if source.startswith('/*',pos):
            depth=1;pos+=2
            while depth:
                match=re.search(r'/\*|\*/',source[pos:])
                if match is None:raise ValueError('块注释未结束')
                if match.group()=='/*':raise ValueError('暂不支持嵌套块注释')
                pos+=match.end();depth-=1
            continue
        start=pos
        if source[pos]=='"':
            if result and result[-1][0].startswith('"'):raise ValueError('不支持相邻或多行String字面量')
            end=pos+1
            while end<len(source):
                if source[end]==chr(92):end+=2;continue
                if source[end]=='"':break
                end+=1
            if end>=len(source):raise ValueError('String字面量未结束')
            value=source[pos:end+1];decode_string_literal(value);pos=end+1
        else:
            match=pattern.match(source,pos)
            if not match:raise ValueError('仅支持Int64/Bool/String普通函数及明确的长度操作')
            value=match.group();pos=match.end()
        if value.isspace() or value.startswith('//'):continue
        result.append((value,source.count('\n',0,start)+1))
        if len(result)>4000:raise ValueError('源码过于复杂（最多4000个语法单元）')
    return result+[('<eof>',len(source.splitlines())+1)]


class Parser:
    def __init__(self,source,types=None):
        self.items=tokens(source);self.pos=0;self.locals={};self.calls=[];self.depth=0;self.declared={}
        self.types={};self.object_headers=None;self.receiver_type=None;self.call_sites=[]
        if types is not None or any(v in ('struct','class') for v,_ in self.items):
            from nexus.repair import object_values
            from nexus.uploads.object_types import collect
            self.object_headers=collect(source,validate=False)
            supplied=object_values.registry(types or {});merged={**supplied,**self.object_headers['types']}
            self.types=object_values.registry(merged)
            if any(self.types[n]!=supplied[n] for n in self.object_headers['types'] if n in supplied):raise ValueError('源码对象声明与同包注册表不一致')
            self.items=self.object_headers['top_items']
    def peek(self):return self.items[self.pos][0]
    def take(self,value=None):
        found=self.peek()
        if value is not None and found!=value:raise ValueError('不支持的函数语法，预期 '+value)
        self.pos+=1
        return found
    def accept(self,value):
        if self.peek()==value:self.take();return True
        return False
    def name(self):
        value=self.take()
        if (not NAME.fullmatch(value) or value in RESERVED or value in self.types or
                self.types and value in ('struct','init','this','mut','private','static','interface','extend','prop')):raise ValueError('函数或变量名无效或遮蔽类型')
        return value
    def function_name(self):return self.name()
    def reference(self,value):return value
    def type(self):
        value=self.take()
        if value=='Array':
            self.take('<');self.take('Int64');self.take('>');return 'Array<Int64>'
        if value not in ('Int64','Bool','String') and value not in self.types:raise ValueError('仅支持有界值或已声明对象类型')
        return value
    def call_signature(self,name):
        if name in self.declared:return self.declared[name]
        if name in self.types:return dict(params=self.types[name]['constructor'],return_type=name)
        if '.' in name:
            owner,method=name.rsplit('.',1)
            return next((m for m in self.types.get(owner,{}).get('methods',[]) if m['name']==method),None)
        return None
    def arguments(self,depth):
        args=[]
        if self.peek()!=')':
            while True:
                args.append(self.expr(0,depth+1))
                if len(args)>4:raise ValueError('调用参数过多')
                if not self.accept(','):break
        self.take(')');return args
    def method_record(self,method,headers_only):
        body=method['body'];owner=method['owner'];qualified=owner+'.'+method['name'];calls=[]
        if any(p['name'] in self.types for p in method['params']):raise ValueError('方法参数不能遮蔽已声明对象类型')
        if not headers_only:
            parser=type(self).__new__(type(self));parser.items=body+[('<eof>',body[-1][1])];parser.pos=0
            parser.scope=getattr(self,'scope',None)
            parser.types=self.types;parser.receiver_type=owner;parser.locals={'this':owner,**{p['name']:p['type'] for p in method['params']}}
            parser.calls=[];parser.call_sites=[];parser.depth=0;parser.declared=self.declared;parser.return_type=method['return_type']
            parser.block()
            if parser.peek()!='<eof>':raise ValueError('对象方法体未完整解析')
            self.calls.extend(parser.calls);calls=parser.call_sites
        statements=[row for value,row in body if value not in ('{','}',';')]
        return dict(name=qualified,receiver_type=owner,params=method['params'],return_type=method['return_type'],line=method['line'],end_line=method['end_line'],
            public=True,return_lines=sorted({row for value,row in body if value=='return'}),final_line=statements[-1] if statements else method['line'],calls=calls)
    def program(self,headers_only=False):
        package=None;functions=[]
        if self.accept('package'):package=self.name();self.accept(';')
        while self.peek()!='<eof>':
            public=self.accept('public');self.take('func');line=self.items[self.pos][1];name=self.function_name()
            if name=='main' or name in PRELUDE_NAMES or any(f['name']==name for f in functions):raise ValueError('不支持main、标准输入输出预留名或函数重载')
            self.take('(');params=[]
            if self.peek()!=')':
                while True:
                    param=self.name();self.take(':');kind=self.type()
                    if any(p['name']==param for p in params) or len(params)>=4:raise ValueError('参数重复或超过4个')
                    params.append(dict(name=param,type=kind))
                    if not self.accept(','):break
            self.take(')');self.take(':');kind=self.type();self.locals={p['name']:p['type'] for p in params};self.return_type=kind
            body_start=self.pos;call_start=len(self.call_sites)
            if headers_only:
                self.take('{');depth=1
                while depth:
                    token=self.take()
                    if token=='<eof>':raise ValueError('函数体未结束')
                    depth+=int(token=='{')-int(token=='}')
            else:self.block()
            body=self.items[body_start:self.pos]
            calls=[dict(name=value,line=row) for i,(value,row) in enumerate(body[:-1])
                if NAME.fullmatch(value) and value not in RESERVED and body[i+1][0]=='(' and (i==0 or body[i-1][0]!='.')]
            if (self.types or getattr(self,'scope',None)) and not headers_only:calls=self.call_sites[call_start:]
            statements=[row for value,row in body if value not in ('{','}',';')]
            functions.append(dict(name=name,params=params,return_type=kind,line=line,public=bool(public),
                end_line=body[-1][1],return_lines=sorted({row for value,row in body if value=='return'}),
                final_line=statements[-1] if statements else line,calls=calls))
            if len(functions)>16:raise ValueError('最多16个函数')
        methods=[self.method_record(m,headers_only) for m in (self.object_headers or {}).get('methods',[])]
        if len(functions)+len(methods)>16:raise ValueError('顶层函数与实例方法共最多16个函数体')
        if not functions and not (self.object_headers or {}).get('types'):raise ValueError('未找到支持的函数')
        signatures={name:len(f['params']) for name,f in self.declared.items()} if self.declared else {f['name']:len(f['params']) for f in functions}
        for name,definition in self.types.items():
            signatures[name]=len(definition['constructor'])
            signatures.update({name+'.'+m['name']:len(m['params']) for m in definition['methods']})
        for name,count in self.calls:
            if name not in signatures or signatures[name]!=count:raise ValueError('只允许参数个数匹配的文件内函数调用')
        result=dict(package=package,functions=functions)
        if self.types:
            result.update(types=self.types,methods=methods)
            for f in functions:
                if f['return_type'] in self.types or any(p['type'] in self.types for p in f['params']):f['types']=self.types
        return result
    def block(self):
        self.depth+=1
        if self.depth>32:raise ValueError('语法嵌套过深')
        saved=dict(self.locals);self.take('{')
        while self.peek()!='}':
            if self.peek()=='<eof>':raise ValueError('函数体未结束')
            if self.peek() in ('let','var'):
                self.take();name=self.name()
                if name in self.locals:raise ValueError('暂不支持变量遮蔽')
                annotation=self.type() if self.accept(':') else None
                self.take('=');inferred=self.expr()
                if annotation and annotation!=inferred:raise ValueError('局部变量类型不匹配')
                self.locals[name]=annotation or inferred
            elif self.accept('return'):
                if self.expr()!=self.return_type:raise ValueError('返回值类型不匹配')
            elif self.accept('for'):
                self.take('(');name=self.name()
                if name in self.locals:raise ValueError('循环变量不能遮蔽参数或局部变量')
                self.take('in')
                if self.expr()!='Array<Int64>':raise ValueError('for仅支持遍历Array<Int64>')
                self.take(')');outer=dict(self.locals);self.locals[name]='Int64'
                self.block();self.locals=outer
            elif self.peek() in ('if','while'):
                control=self.take();self.take('(')
                if self.expr()!='Bool':raise ValueError('条件必须为Bool')
                self.take(')');self.block()
                if control=='if' and self.accept('else'):self.block()
            elif self.peek() in ('break','continue'):self.take()
            elif self.peek() in self.locals and self.items[self.pos+1][0]=='=':
                name=self.take();self.take('=')
                if self.expr()!=self.locals[name]:raise ValueError('赋值类型不匹配')
            else:self.expr()
            self.accept(';')
        self.take('}');self.locals=saved;self.depth-=1
    def expr(self,minimum=0,depth=0):
        if depth>64:raise ValueError('表达式嵌套过深')
        value=self.take()
        if value in ('!','-','+'):
            kind=self.expr(7,depth+1)
            if kind!=('Bool' if value=='!' else 'Int64'):raise ValueError('一元运算类型不匹配')
        elif value=='(':
            kind=self.expr(0,depth+1);self.take(')')
        elif value=='[':
            count=0
            if self.peek()!=']':
                while True:
                    if self.expr(0,depth+1)!='Int64':raise ValueError('数组元素必须为Int64')
                    count+=1
                    if count>16:raise ValueError('数组字面量最多16项')
                    if not self.accept(','):break
            self.take(']');kind='Array<Int64>'
        elif value in ('true','false'):kind='Bool'
        elif value.startswith('"'):decode_string_literal(value);kind='String'
        elif value.isascii() and value.isdigit() and len(value)<=19:kind='Int64'
        elif value=='this' and self.receiver_type:kind=self.receiver_type
        elif NAME.fullmatch(value) and value not in RESERVED:
            value=self.reference(value)
            if self.accept('('):
                if self.receiver_type and any(m['name']==value for m in self.types[self.receiver_type]['methods']):
                    raise ValueError('实例方法调用须显式使用this接收者，不能与顶层函数混用')
                line=self.items[self.pos-2][1];args=self.arguments(depth);declared=self.call_signature(value)
                if not declared or args!=[p['type'] for p in declared['params']]:raise ValueError('只允许类型完全匹配的文件内函数调用')
                kind=declared['return_type'];self.calls.append((value,len(args)))
                self.call_sites.append(dict(name=value,line=line))
            else:
                if value not in self.locals:raise ValueError('只能引用局部变量和参数')
                kind=self.locals[value]
        else:raise ValueError('表达式不属于支持的普通函数子集')
        while self.peek() in ('.','['):
            if self.accept('['):
                if kind!='Array<Int64>' or self.expr(0,depth+1)!='Int64':raise ValueError('下标只接受Array<Int64>及Int64索引')
                self.take(']');kind='Int64';continue
            self.take('.')
            if kind in self.types:
                member_line=self.items[self.pos][1];member=self.take();owner=kind;definition=self.types[owner]
                if self.accept('('):
                    args=self.arguments(depth);declared=self.call_signature(owner+'.'+member)
                    if declared is None or args!=[p['type'] for p in declared['params']]:raise ValueError('实例方法不存在或参数类型不符')
                    kind=declared['return_type'];self.calls.append((owner+'.'+member,len(args)))
                    self.call_sites.append(dict(name=owner+'.'+member,line=member_line,receiver_type=owner))
                else:
                    field=next((f for f in definition['fields'] if f['name']==member),None)
                    if field is None:raise ValueError('对象字段未声明')
                    kind=field['type']
                continue
            if kind not in ('String','Array<Int64>'):raise ValueError('长度操作只接受String或Array<Int64>')
            member=self.take()
            if member=='size':kind='Int64'
            elif kind=='String' and member=='toRuneArray':
                self.take('(');self.take(')');self.take('.');self.take('size');kind='Int64'
            else:raise ValueError('仅允许size和String.toRuneArray().size')
        while PRECEDENCE.get(self.peek(),-1)>=minimum:
            operator=self.take();right=self.expr(PRECEDENCE[operator]+1,depth+1)
            if operator in ('&&','||'):
                if kind!='Bool' or right!='Bool':raise ValueError('逻辑运算需要Bool')
                kind='Bool'
            elif operator=='+' and kind==right=='String':kind='String'
            elif operator in ('==','!='):
                if kind!=right or kind in self.types:raise ValueError('相等比较类型不匹配或对象须逐字段比较')
                kind='Bool'
            else:
                if kind!='Int64' or right!='Int64':raise ValueError('算术或大小比较需要Int64')
                kind='Bool' if operator in ('<','<=','>','>=') else 'Int64'
        return kind


def inspect_source(source):
    try:
        parser=Parser(source);headers=parser.program(headers_only=True)
        parser.pos=0;parser.declared={f['name']:f for f in headers['functions']}
        result=parser.program()
        if not result['functions']:raise ValueError('单文件上传须提供普通顶层入口函数')
        return result
    except (RecursionError,IndexError):raise ValueError('源码嵌套或语法无效') from None


def signatures(info):
    return {f['name']:([p['type'] for p in f['params']],f['return_type']) for f in info['functions']}


def validate_candidate(source,baseline_info):
    info=inspect_source(source)
    if info['package']!=baseline_info['package'] or signatures(info)!=signatures(baseline_info) or info.get('types')!=baseline_info.get('types'):
        raise ValueError('候选不能改变包名或函数接口')


def validate_examples(info,function,examples):
    selected=next((f for f in info['functions'] if f['name']==function),None)
    if selected is None or not isinstance(examples,list) or not 2<=len(examples)<=12:
        raise ValueError('请选择函数并提供2至12组示例')
    def matches(value,kind):
        try:primitive(value,kind,info.get('types'));return True
        except ValueError:return False
    suites=set()
    for example in examples:
        if not isinstance(example,dict) or set(example)!={'args','expected','suite'}:raise ValueError('示例只允许args、expected和suite')
        args=example['args'];suite=example['suite']
        if not isinstance(args,list) or len(args)!=len(selected['params']) or not all(matches(v,p['type']) for v,p in zip(args,selected['params'])):
            raise ValueError('示例参数个数或类型不匹配')
        if not matches(example['expected'],selected['return_type']) or suite not in ('target','regression'):
            raise ValueError('预期值类型或测试分组无效')
        suites.add(suite)
    if suites!={'target','regression'}:raise ValueError('至少各一组target和regression示例')
    return examples


def literal(value,types=None):
    if type(value) is dict:
        from nexus.repair import object_values
        return object_values.literal(value,value.get('$type'),types)
    if type(value) is list:return '['+', '.join(str(n) for n in array(value))+']'
    if type(value) is str:return string_literal(value)
    return str(value).lower() if type(value) is bool else str(value)
