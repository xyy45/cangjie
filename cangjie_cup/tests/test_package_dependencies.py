"""Dependency-shape fixtures based on actual SDK discovery, no execution here."""
from copy import deepcopy
import json
import pytest

from nexus.adapters.cangjie import scoped_reports
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.projects.index import inspect_project


def fixture(tmp_path):
    files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,
        'src/order.cj':'package bench\r\n// 中文\r\nimport /*中*/ bench.money.fee as cost\r\npublic func total(x: Int64): Int64 { cost(x) }\r\n'.encode(),
        'src/wild.cj':b'package bench\nimport bench.money.*\npublic func other(x: Int64): Int64 { fee(x) }',
        'src/qualified.cj':b'package bench\nimport bench.money as finance\npublic func qualified(x: Int64): Int64 { finance.fee(x) }',
        'src/money/fee.cj':b'package bench.money\npublic func fee(x: Int64): Int64 { x+1 }',
        'src/empty/namespace.cj':b'package bench.empty\n'}
    root=tmp_path/'project';root.mkdir()
    for path,raw in files.items():
        target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    graph=inspect_project(files)['dependency_graph']
    def position(path,line):
        return dict(file=str(root/path),begin=dict(line=line,column=1),end=dict(line=line,column=len(files[path].splitlines()[line-1])+1))
    packet=dict(package='bench',isMacro=False,accessLevel='public',dependencies=[
        dict(package='bench.money',isStd=False,imports=[position('src/wild.cj',2),position('src/qualified.cj',2)]),
        dict(package='bench.money',orPackage='bench.money.fee',isStd=False,imports=[position('src/order.cj',3)])])
    return root,graph,packet


def parse(root,graph,packet,package='bench'):
    return scoped_reports.dependencies(json.dumps(packet).encode(),package=package,source_root=root,graph=graph)


def test_package_wildcard_and_symbol_alias_occurrences_match_source_declarations(tmp_path):
    root,graph,packet=fixture(tmp_path);result=parse(root,graph,packet)
    assert result['state']=='PASS' and result['package']=='bench'
    assert [(d['path'],d['line'],d['specifier'],d['kind']) for d in result['imports']]==[
        ('src/order.cj',3,'bench.money.fee','symbol'),('src/qualified.cj',2,'bench.money','package'),('src/wild.cj',2,'bench.money.*','wildcard')]
    position=packet['dependencies'][1]['imports'][0]
    assert result['imports'][0]['range']==dict(begin=position['begin'],end=position['end'],coordinate='SDK_SOURCE_RANGE')


def test_empty_dependency_array_is_valid_only_for_actual_package_without_imports(tmp_path):
    root,graph,packet=fixture(tmp_path)
    packet=dict(package='bench.empty',isMacro=False,accessLevel='public',dependencies=[])
    assert parse(root,graph,packet,'bench.empty')['state']=='PASS'
    packet['package']='bench'
    assert parse(root,graph,packet)['state']=='UNKNOWN'


def test_sdk_package_alias_parent_encoding_still_requires_exact_source_occurrence(tmp_path):
    root,graph,packet=fixture(tmp_path)
    # Actual SDK also emits a package alias as parent package + orPackage.
    qualified=packet['dependencies'][0]['imports'].pop()
    packet['dependencies'].append(dict(package='bench',orPackage='bench.money',isStd=False,imports=[qualified]))
    result=parse(root,graph,packet)
    assert result['state']=='PASS' and result['imports'][1]['target_package']=='bench.money'
    packet['dependencies'][-1]['orPackage']='bench.empty'
    assert parse(root,graph,packet)['state']=='UNKNOWN'


@pytest.mark.parametrize('change',['wrong-package','macro','wrong-access','missing','extra','std','wrong-target','wrong-original','foreign-file','wrong-file-package','wrong-line','bad-column','end-before-start','bool-line','duplicate','extra-key','invalid-json','duplicate-json-key','missing-file','symlink-file','hardlink-file'])
def test_empty_partial_foreign_or_inconsistent_sdk_graph_is_unknown(tmp_path,change):
    root,graph,packet=fixture(tmp_path);item=packet['dependencies'][1]['imports'][0]
    if change=='wrong-package':packet['package']='other'
    elif change=='macro':packet['isMacro']=True
    elif change=='wrong-access':packet['accessLevel']='private'
    elif change=='missing':packet['dependencies'].pop()
    elif change=='extra':packet['dependencies'].append(dict(package='bench.empty',isStd=False,imports=[deepcopy(item)]))
    elif change=='std':packet['dependencies'][1]['isStd']=True
    elif change=='wrong-target':packet['dependencies'][1]['package']='bench.empty'
    elif change=='wrong-original':packet['dependencies'][1]['orPackage']='bench.money.missing'
    elif change=='foreign-file':item['file']=str(tmp_path/'outside.cj')
    elif change=='wrong-file-package':item['file']=str(root/'src/money/fee.cj')
    elif change=='wrong-line':item['begin']['line']=2
    elif change=='bad-column':item['end']['column']=10000
    elif change=='end-before-start':item['end']['line']=1
    elif change=='bool-line':item['begin']['line']=True
    elif change=='duplicate':packet['dependencies'][1]['imports'].append(deepcopy(item))
    elif change=='extra-key':packet['verified']=True
    elif change=='missing-file':(root/'src/order.cj').unlink()
    elif change=='symlink-file':
        actual=root/'src/order.cj';outside=tmp_path/'outside.cj';actual.replace(outside);actual.symlink_to(outside)
    elif change=='hardlink-file':
        import os
        os.link(root/'src/order.cj',tmp_path/'linked.cj')
    raw=json.dumps(packet).encode()
    if change=='invalid-json':raw=b'{} trailing'
    elif change=='duplicate-json-key':raw=raw.replace(b'"isMacro": false',b'"isMacro": false, "isMacro": false')
    result=scoped_reports.dependencies(raw,package='bench',source_root=root,graph=graph)
    assert result['state']=='UNKNOWN'
