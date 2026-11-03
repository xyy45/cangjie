"""Bounded original SDK XML/summary interpretation; no execution or fallback.

XML failure coordinates refer to decoded element text, never raw-byte offsets.
Compiler dependency interpretation is kept separate from case-status parsing.
"""
import re
from pathlib import Path,PurePosixPath
from copy import deepcopy
from xml.etree import ElementTree as ET

from nexus.adapters.cangjie.report_parser import ANSI,SUMMARY,control_text
from nexus.projects.names import local_name,package_name,case_name
from nexus.policy.core import strict_json
from nexus.projects.scopes import read_header

MAX_BYTES=2*1024*1024
MAX_REPORTS=257
MAX_CASES=288


def _case_id(value):
    if type(value) is not str or len(value)>311:raise ValueError('XML用例规范名无效')
    parts=value.split('.')
    if not 3<=len(parts)<=10:raise ValueError('XML用例缺少包身份')
    suite='.'.join(parts[:-1]);package='.'.join(parts[:-2])
    if len(suite)>246:raise ValueError('XML套件名称超过SDK文件名容量')
    local_name(parts[-1]);local_name(parts[-2])
    if len(parts)==4 and re.fullmatch('nexus_verify_[0-9a-f]{16}',parts[1]):
        package_name(parts[0])
    else:case_name(value)
    return suite


def _number(text,limit=MAX_CASES):
    if type(text) is not str or len(text)>10 or not re.fullmatch(r'0|[1-9][0-9]*',text):
        raise ValueError('XML或SDK计数不是规范非负整数')
    number=int(text)
    if number>limit:raise ValueError('XML或SDK计数越界')
    return number


class _BoundedTree(ET.TreeBuilder):
    def __init__(self):super().__init__();self.depth=0;self.nodes=0
    def start(self,tag,attrs):
        self.depth+=1;self.nodes+=1
        if self.depth>8 or self.nodes>8192:raise ValueError('XML结构深度或节点数量越界')
        return super().start(tag,attrs)
    def end(self,tag):
        value=super().end(tag);self.depth-=1;return value
    def doctype(self,name,pubid,system):raise ValueError('SDK报告不允许DTD或实体声明')


def _xml(raw):
    if type(raw) is not bytes:raise ValueError('XML必须来自原始字节')
    text=raw.decode('utf-8',errors='strict')
    declaration=re.match(r'^\ufeff?<\?xml\s+([^?]*)\?>',text)
    if declaration:
        encoding=re.search(r'''\bencoding\s*=\s*(['"])(.*?)\1''',declaration.group(1))
        if encoding and encoding.group(2).casefold()!='utf-8':raise ValueError('SDK报告仅接受UTF-8')
    parser=ET.XMLParser(encoding='utf-8',target=_BoundedTree());parser.feed(raw)
    return parser.close()


def _counts(states):
    return dict(total=len(states),passed=states.count('PASS'),failed=states.count('FAIL'),
                errors=states.count('UNKNOWN'),skipped=states.count('NOT_RUN'))


def tests(reports,*,expected,stdout,exit_code):
    """All expected canonical cases must be represented; partial never PASS."""
    unknown=dict(state='UNKNOWN',counts={},case_results={},failures={},diagnostics='')
    try:
        if type(expected) is not list or not 1<=len(expected)<=MAX_CASES or len(set(expected))!=len(expected):
            raise ValueError('冻结用例为空、重复或数量越界')
        suites={}
        for identity in expected:suites.setdefault(_case_id(identity),set()).add(identity)
        names={'test-'+suite+'.xml' for suite in suites}
        if (type(reports) is not dict or not 1<=len(reports)<=MAX_REPORTS or set(reports)!=names or
                any(type(raw) is not bytes for raw in reports.values())):
            raise ValueError('XML文件集合与冻结套件不一致')
        if type(stdout) is not str or sum(len(raw) for raw in reports.values())+len(stdout.encode('utf-8'))>MAX_BYTES:
            raise ValueError('SDK日志与XML原件合计超过2MiB')
        if type(exit_code) is not int:raise ValueError('SDK进程退出状态无效')
        results={};failures={}
        for name,raw in sorted(reports.items()):
            root=_xml(raw)
            allowed={'name','tests','failures','errors','skipped','time','timestamp'}
            if root.tag!='testsuite' or set(root.attrib)-allowed or not {'name','tests','failures','errors','skipped'}<=set(root.attrib):
                raise ValueError('XML套件根或属性无效')
            suite=root.attrib['name']
            if suite not in suites or name!='test-'+suite+'.xml':raise ValueError('XML套件身份与文件不一致')
            states=[];seen=set()
            for case in root:
                if case.tag!='testcase' or set(case.attrib)-{'name','classname','assertions','time'}:
                    raise ValueError('XML存在未知的测试节点或状态属性')
                if case.get('classname')!=suite:raise ValueError('XML用例所属套件不一致')
                identity=suite+'.'+local_name(case.get('name'));_case_id(identity)
                if identity not in suites[suite] or identity in seen or identity in results:raise ValueError('XML用例外来或重复')
                if 'assertions' in case.attrib:_number(case.attrib['assertions'],1_000_000_000)
                seen.add(identity);tags=[];messages=[]
                for child in case:
                    if child.tag not in ('failure','error','skipped','system-out','system-err') or len(child):
                        raise ValueError('XML用例包含未知或嵌套节点')
                    if set(child.attrib)-{'message','type'}:raise ValueError('XML用例诊断属性无效')
                    if child.tag in ('system-out','system-err'):continue
                    tags.append(child.tag)
                    if child.tag=='failure':
                        text=child.text or '';index=len(messages)
                        messages.append(dict(text=text,source=dict(report=name,case_id=identity,failure_index=index,
                            coordinate='XML_FAILURE_TEXT',start_char=0,end_char=len(text))))
                if len(set(tags))>1:raise ValueError('XML用例失败、错误或跳过状态冲突')
                state='FAIL' if 'failure' in tags else 'UNKNOWN' if 'error' in tags else 'NOT_RUN' if 'skipped' in tags else 'PASS'
                states.append(state);results[identity]=state
                if messages:failures[identity]=messages
            if seen!=suites[suite]:raise ValueError('XML套件未覆盖全部冻结用例')
            count=_counts(states)
            actual={key:_number(root.attrib[attr]) for key,attr in (('total','tests'),('failed','failures'),('errors','errors'),('skipped','skipped'))}
            if any(actual[key]!=count[key] for key in actual):raise ValueError('XML套件计数与逐例状态不一致')
        if set(results)!=set(expected):raise ValueError('XML缺少冻结用例')
        count=_counts(list(results.values()));clean=ANSI.sub('',stdout);controls=control_text(clean)
        summaries=list(SUMMARY.finditer(controls))
        if not summaries:raise ValueError('SDK缺少最终测试汇总')
        total,passed,skipped,errors,failed=(_number(value) for value in summaries[-1].groups())
        summary=dict(total=total,passed=passed,skipped=skipped,errors=errors,failed=failed)
        if summary!=count:raise ValueError('XML与SDK汇总计数不一致')
        failed_run=bool(failed or errors)
        tail='Error: cjpm test failed' if failed_run else 'cjpm test success'
        if not clean.rstrip().endswith(tail) or (exit_code<=0 if failed_run else exit_code!=0):
            raise ValueError('SDK汇总与进程退出不一致')
        state='UNKNOWN' if errors or skipped else 'FAIL' if failed else 'PASS'
        return dict(state=state,counts=count,case_results=results,failures=failures,diagnostics='')
    except (ValueError,TypeError,KeyError,UnicodeError,ET.ParseError,RecursionError,OverflowError) as exc:
        return {**unknown,'diagnostics':str(exc)}


def _source(path,root):
    if (not path.is_absolute() or path.is_symlink() or path.resolve(strict=True)!=path or
            not path.is_relative_to(root) or not path.is_file() or path.stat().st_nlink!=1 or path.stat().st_size>65536):
        raise ValueError('SDK依赖坐标必须属于本工程常规源文件')
    raw=path.read_bytes()
    if len(raw)>65536:raise ValueError('SDK依赖源文件超限')
    return raw,raw.decode('utf-8',errors='strict')


def dependencies(raw,*,package,source_root,graph):
    """Match SDK occurrences against declarations and current source headers."""
    unknown=dict(state='UNKNOWN',package=package,imports=[],diagnostics='')
    try:
        package_name(package)
        if type(raw) is not bytes or len(raw)>MAX_BYTES:raise ValueError('SDK依赖原件须为有界字节')
        packet=strict_json(raw)
        if (type(packet) is not dict or set(packet)!={'package','isMacro','accessLevel','dependencies'} or
                packet['package']!=package or packet['isMacro'] is not False or packet['accessLevel']!='public' or
                type(packet['dependencies']) is not list or len(packet['dependencies'])>400):
            raise ValueError('SDK依赖包身份、宏状态或结构无效')
        if (type(graph) is not dict or type(graph.get('version')) is not int or graph['version']!=1 or
                type(graph.get('packages')) is not list or not 1<=len(graph['packages'])<=16 or
                len(set(graph['packages']))!=len(graph['packages']) or package not in graph['packages']):
            raise ValueError('SDK依赖缺少冻结包图')
        packages=sorted(package_name(p) for p in graph['packages']);base=packages[0]
        if '.' in base or any(p!=base and not p.startswith(base+'.') for p in packages):raise ValueError('依赖图必须属于单个构建根')
        root=Path(source_root)
        if root.is_symlink() or not root.is_dir():raise ValueError('SDK源根无效')
        root=root.resolve(strict=True);relative='/'.join(['src',*package.split('.')[1:]])
        directory=root/relative
        if directory.is_symlink() or not directory.is_dir() or directory.resolve()!=directory:raise ValueError('SDK包目录不匹配')
        expected={};source_headers={}
        for path in sorted(directory.glob('*.cj')):
            if path.name.endswith('_test.cj'):continue
            raw_source,text=_source(path,root);name=path.relative_to(root).as_posix()
            header=read_header(text,name,base)
            if header['package']!=package:raise ValueError('源文件声明不属于扫描包')
            source_headers[name]=header
        if not source_headers:raise ValueError('扫描包没有生产源文件')
        if type(graph.get('imports')) is not list:raise ValueError('冻结导入表无效')
        for declaration in graph['imports']:
            if type(declaration) is not dict:raise ValueError('冻结导入声明无效')
            path=declaration.get('path')
            if path not in source_headers:continue
            if declaration.get('origin')!='WORKSPACE' or declaration.get('target_package') not in packages:
                raise ValueError('生产依赖必须来自冻结工作区')
            key=(path,declaration.get('line'),declaration.get('target_package'),declaration.get('specifier') if declaration.get('kind')=='symbol' else None)
            if key in expected:raise ValueError('冻结导入坐标重复')
            expected[key]=declaration
        for path,header in source_headers.items():
            frozen=[dict(specifier=d['specifier'],alias=d['alias'],line=d['line']) for d in graph['imports'] if d.get('path')==path]
            if header['imports']!=frozen:raise ValueError('源文件导入与冻结声明变化')
        seen=set();matches=[]
        for dependency in packet['dependencies']:
            if (type(dependency) is not dict or set(dependency)-{'package','orPackage','isStd','imports'} or
                    not {'package','isStd','imports'}<=set(dependency) or dependency['isStd'] is not False or
                    dependency['package'] not in packages or type(dependency['imports']) is not list or not dependency['imports']):
                raise ValueError('SDK依赖来源或导入集合无效')
            original=dependency.get('orPackage')
            if original is not None and type(original) is not str:raise ValueError('SDK原始符号导入无效')
            for occurrence in dependency['imports']:
                if type(occurrence) is not dict or set(occurrence)!={'file','begin','end'} or type(occurrence['file']) is not str:
                    raise ValueError('SDK依赖源坐标结构无效')
                file=Path(occurrence['file']);source_bytes,_=_source(file,root);name=file.relative_to(root).as_posix()
                if str(file.parent)!=str(directory) or name not in source_headers:raise ValueError('SDK依赖坐标跨出当前包')
                lines=source_bytes.splitlines();positions=[]
                for label in ('begin','end'):
                    position=occurrence[label]
                    if (type(position) is not dict or set(position)!={'line','column'} or
                            type(position['line']) is not int or type(position['column']) is not int or
                            not 1<=position['line']<=len(lines) or not 1<=position['column']<=len(lines[position['line']-1])+1):
                        raise ValueError('SDK行列超出冻结源文件')
                    positions.append((position['line'],position['column']))
                if positions[1]<positions[0]:raise ValueError('SDK源范围反向')
                key=(name,positions[0][0],dependency['package'],original)
                if key not in expected and original is not None:
                    # The fixed SDK can encode `import pkg.child as alias` as
                    # either pkg.child/None or parent pkg/orPackage=pkg.child.
                    alternate=(name,positions[0][0],original,None)
                    declaration=expected.get(alternate)
                    if (declaration is not None and declaration['kind']=='package' and
                            original.rpartition('.')[0]==dependency['package']):key=alternate
                if key not in expected or key in seen:raise ValueError('SDK缺失、重复或额外依赖坐标')
                seen.add(key);declaration=expected[key]
                matches.append({**deepcopy(declaration),'range':dict(begin=deepcopy(occurrence['begin']),end=deepcopy(occurrence['end']),coordinate='SDK_SOURCE_RANGE')})
        if seen!=set(expected):raise ValueError('SDK依赖未覆盖全部冻结导入')
        return dict(state='PASS',package=package,imports=sorted(matches,key=lambda d:(d['path'],d['line'],d['specifier'])),diagnostics='')
    except (ValueError,TypeError,KeyError,OSError,UnicodeError,RecursionError,OverflowError) as exc:
        return {**unknown,'diagnostics':str(exc)}
