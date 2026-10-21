"""A restricted primitive Cangjie gate, not a general Cangjie type checker.

Every identifier is a local primitive or a declared function; there are no imports,
members, strings, macros, constructors, attributes or top-level initialization.
The pinned compiler still decides whether a permitted program compiles.
"""
import re

TOKEN=re.compile(r'\s+|//[^\n]*|[A-Za-z_][A-Za-z_0-9]*|[0-9]+|==|!=|<=|>=|&&|\|\||[{}():,;=+*/%!<>-]')
NAME=re.compile(r'[A-Za-z_][A-Za-z_0-9]{0,63}\Z')
RESERVED=set('package public func let var if else while return break continue true false Int64 Bool import class unsafe'.split())
PRELUDE_NAMES={'print','println','eprint','eprintln','readln','panic','exit','sleep'}
PRECEDENCE={'||':1,'&&':2,'==':3,'!=':3,'<':4,'>':4,'<=':4,'>=':4,'+':5,'-':5,'*':6,'/':6,'%':6}


def tokens(source):
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
        match=TOKEN.match(source,pos)
        if not match:raise ValueError('仅支持普通Int64/Bool函数；不支持字符串、导入、成员访问或宏')
        value=match.group();start=pos;pos=match.end()
        if value.isspace() or value.startswith('//'):continue
        result.append((value,source.count('\n',0,start)+1))
        if len(result)>4000:raise ValueError('源码过于复杂（最多4000个语法单元）')
    return result+[('<eof>',len(source.splitlines())+1)]


class Parser:
    def __init__(self,source):
        self.items=tokens(source);self.pos=0;self.locals={};self.calls=[];self.depth=0;self.declared={}
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
        if not NAME.fullmatch(value) or value in RESERVED:raise ValueError('函数或变量名无效')
        return value
    def type(self):
        value=self.take()
        if value not in ('Int64','Bool'):raise ValueError('仅支持Int64和Bool参数及返回值')
        return value
    def program(self,headers_only=False):
        package=None;functions=[]
        if self.accept('package'):package=self.name();self.accept(';')
        while self.peek()!='<eof>':
            self.accept('public');self.take('func');line=self.items[self.pos][1];name=self.name()
            if name=='main' or name in PRELUDE_NAMES or any(f['name']==name for f in functions):raise ValueError('不支持main、标准输入输出预留名或函数重载')
            self.take('(');params=[]
            if self.peek()!=')':
                while True:
                    param=self.name();self.take(':');kind=self.type()
                    if any(p['name']==param for p in params) or len(params)>=4:raise ValueError('参数重复或超过4个')
                    params.append(dict(name=param,type=kind))
                    if not self.accept(','):break
            self.take(')');self.take(':');kind=self.type();self.locals={p['name']:p['type'] for p in params};self.return_type=kind
            if headers_only:
                self.take('{');depth=1
                while depth:
                    token=self.take()
                    if token=='<eof>':raise ValueError('函数体未结束')
                    depth+=int(token=='{')-int(token=='}')
            else:self.block()
            functions.append(dict(name=name,params=params,return_type=kind,line=line))
            if len(functions)>16:raise ValueError('最多16个函数')
        if not functions:raise ValueError('未找到支持的函数')
        signatures={f['name']:len(f['params']) for f in functions}
        for name,count in self.calls:
            if name not in signatures or signatures[name]!=count:raise ValueError('只允许参数个数匹配的文件内函数调用')
        return dict(package=package,functions=functions)
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
        elif value in ('true','false'):kind='Bool'
        elif value.isascii() and value.isdigit() and len(value)<=19:kind='Int64'
        elif NAME.fullmatch(value) and value not in RESERVED:
            if self.accept('('):
                args=[]
                if self.peek()!=')':
                    while True:
                        args.append(self.expr(0,depth+1))
                        if len(args)>4:raise ValueError('调用参数过多')
                        if not self.accept(','):break
                self.take(')');declared=self.declared.get(value)
                if not declared or args!=[p['type'] for p in declared['params']]:raise ValueError('只允许类型完全匹配的文件内函数调用')
                kind=declared['return_type'];self.calls.append((value,len(args)))
            else:
                if value not in self.locals:raise ValueError('只能引用局部变量和参数')
                kind=self.locals[value]
        else:raise ValueError('表达式不属于支持的普通函数子集')
        while PRECEDENCE.get(self.peek(),-1)>=minimum:
            operator=self.take();right=self.expr(PRECEDENCE[operator]+1,depth+1)
            if operator in ('&&','||'):
                if kind!='Bool' or right!='Bool':raise ValueError('逻辑运算需要Bool')
                kind='Bool'
            elif operator in ('==','!='):
                if kind!=right:raise ValueError('相等比较类型不匹配')
                kind='Bool'
            else:
                if kind!='Int64' or right!='Int64':raise ValueError('算术或大小比较需要Int64')
                kind='Bool' if operator in ('<','<=','>','>=') else 'Int64'
        return kind


def inspect_source(source):
    try:
        parser=Parser(source);headers=parser.program(headers_only=True)
        parser.pos=0;parser.declared={f['name']:f for f in headers['functions']}
        return parser.program()
    except (RecursionError,IndexError):raise ValueError('源码嵌套或语法无效') from None


def signatures(info):
    return {f['name']:([p['type'] for p in f['params']],f['return_type']) for f in info['functions']}


def validate_candidate(source,baseline_info):
    info=inspect_source(source)
    if info['package']!=baseline_info['package'] or signatures(info)!=signatures(baseline_info):
        raise ValueError('候选不能改变包名或函数接口')


def validate_examples(info,function,examples):
    selected=next((f for f in info['functions'] if f['name']==function),None)
    if selected is None or not isinstance(examples,list) or not 2<=len(examples)<=12:
        raise ValueError('请选择函数并提供2至12组示例')
    def primitive(value,kind):
        return type(value) is bool if kind=='Bool' else type(value) is int and -(1<<63)<=value<(1<<63)
    suites=set()
    for example in examples:
        if not isinstance(example,dict) or set(example)!={'args','expected','suite'}:raise ValueError('示例只允许args、expected和suite')
        args=example['args'];suite=example['suite']
        if not isinstance(args,list) or len(args)!=len(selected['params']) or not all(primitive(v,p['type']) for v,p in zip(args,selected['params'])):
            raise ValueError('示例参数个数或类型不匹配')
        if not primitive(example['expected'],selected['return_type']) or suite not in ('target','regression'):
            raise ValueError('预期值类型或测试分组无效')
        suites.add(suite)
    if suites!={'target','regression'}:raise ValueError('至少各一组target和regression示例')
    return examples


def literal(value):
    return str(value).lower() if type(value) is bool else str(value)
