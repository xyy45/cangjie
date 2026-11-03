"""Actual V5 scoped observations; self-built bugs/fixes, no model/remote calls."""
import asyncio,hashlib,json
from copy import deepcopy
import pytest

from nexus.adapters.cangjie.sdk import SDK
from nexus.contracts import source_manifest
from nexus.execution.runner import run_command
from nexus.repair import oracle,properties,relations,primitive_trace,property_trace,relation_trace,scoped_trace,scoped_values
from nexus.repair.scoped_material import material
from tests.test_package_index import project
from tests.test_package_material import selected,NONCE
from nexus.benchmark.corpus import CONFIG,LOCK

pytestmark=pytest.mark.sdk


def write_and_execute(owner,files,signature,cases,mode,*,contract=None):
    before=deepcopy(files);derived=material(files,signature,NONCE);binding=derived['binding']
    if mode=='single':source=property_trace.harness(contract,cases,binding['package'],NONCE,binding=binding)
    elif mode=='relation':source=relation_trace.harness(contract,cases,binding['package'],NONCE,binding=binding)
    else:source=primitive_trace.harness(signature,cases,binding['package'],NONCE,mode,version=5,binding=binding)
    inputs=relation_trace.flatten(cases) if mode=='relation' else cases
    rendered=scoped_trace.render(signature,inputs,nonce=NONCE,mode=mode,binding=binding)
    assert source==rendered['source'] and files==before
    root=owner/'project';root.mkdir(parents=True)
    for path,raw in {**derived['files'],rendered['path']:source}.items():
        destination=root/path;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(raw)
    manifest=source_manifest(root);argv=[]
    code,log,problem=asyncio.run(run_command(root,['cjpm','test'],private_root=owner,test_output='all',execution_argv=argv))
    (owner/'sdk.log').write_text(log)
    (owner/'input.json').write_text(json.dumps(dict(signature=signature,contract=contract,cases=cases,mode=mode,nonce=NONCE,
        original_manifest=derived['original_manifest'],binding=binding,source_before=manifest),ensure_ascii=True,indent=2))
    execution=dict(exit_code=code,problem=problem,execution_argv=argv,source_after=source_manifest(root),
        sdk_tools={p:hashlib.sha256((SDK/p).read_bytes()).hexdigest() for p in ('bin/cjc','bin/cjc-frontend','tools/bin/cjpm')},
        test_binary_sha256={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'target/release/unittest_bin').glob('*') if p.is_file()})
    (owner/'execution.json').write_text(json.dumps(execution,indent=2))
    assert code==0 and problem is None,log
    assert source_manifest(root)==manifest and files==before
    if mode=='single':result=property_trace.interpret(contract,cases,NONCE,log,code,problem)
    elif mode=='relation':result=relation_trace.interpret(contract,cases,NONCE,log,code,problem)
    else:result=primitive_trace.read(signature,cases,NONCE,mode,log,code,problem,version=5)
    (owner/'result.json').write_text(json.dumps(result,ensure_ascii=True,indent=2))
    assert result['state']!='UNKNOWN',(result,log)
    return result,rendered,log


def nominal(package,amount):return {'$type':'bench.'+package+'.State','fields':{'amount':amount}}


@pytest.mark.parametrize('mode',['oracle','single','relation'])
def test_v5_private_crosspackage_defect_actual_observation_then_reference_fix(tmp_path,mode):
    files=project();files['src/order.cj']=files['src/order.cj'].replace(b'RefundState(next.net() + cost(n) + refunds.fee(0))',b'RefundState(next.net() + n)')
    files['src/cases_test.cj']=files['src/cases_test.cj'].replace(b'apply(SaleState(10), 2).amount, 16',b'apply(SaleState(0), 0).amount, 0')
    signature=selected(files);domains=dict(state=dict(values=[nominal('sale',0),nominal('sale',10)]),n=dict(min=0,max=2,points=[]))
    common=dict(version=6 if mode=='oracle' else 5,function=signature['name'],domains=domains,seed=7,excluded_inputs=[])
    if mode=='oracle':
        raw=dict(**common,expression='object_new("bench.refund.State", object_get(state,"amount") + n)',max_cases=16)
        contract=oracle.validate_contract(raw,signature,[]);cases=[[nominal('sale',10),2]]
    elif mode=='single':
        raw=dict(**common,kind='single',properties=[dict(id='PROP-AMOUNT',text='累计值等于初值加请求',precondition='True',assertion='object_get(result,"amount") == object_get(arg0,"amount") + arg1')],max_cases=16)
        contract=properties.validate_contract(raw,signature,[]);cases=[[nominal('sale',10),2]]
    else:
        raw=dict(**common,kind='relation',relations=[dict(id='REL-STEP',text='请求增加一，结果增加一',precondition='left_arg0 == right_arg0 and right_arg1 == left_arg1 + 1',assertion='object_get(right_result,"amount") == object_get(left_result,"amount") + 1')],max_pairs=16)
        contract=relations.validate_contract(raw,signature,[]);cases=[dict(left=[nominal('sale',10),0],right=[nominal('sale',10),1])]
    original=deepcopy(files)
    for label in ('bug','fixed'):
        current=files if label=='bug' else {**files,'src/order.cj':files['src/order.cj'].replace(b'RefundState(next.net() + n)',b'RefundState(next.net())')}
        result,rendered,log=write_and_execute(tmp_path/label,current,signature,cases,mode,contract=contract)
        if mode=='oracle':
            actual=result['observations'][0]['actual_return'];expected=oracle.expected(contract,cases[0])
            assert actual==nominal('refund',14 if label=='bug' else 12)
            assert (actual==expected)==(label=='fixed')
        else:assert result['state']==('FAIL' if label=='bug' else 'PASS'),result
        assert files==original


@pytest.mark.parametrize('kind,cases',[
    ('Int64',[[-(1<<63)],[(1<<63)-1]]),('Bool',[[False],[True]]),
    ('String',[['中\x00\n|NEXUS_SEQUENCE_END_V5|']]),
    ('Array<Int64>',[[],[-(1<<63)]*16])])
def test_v5_scoped_primitive_values_do_not_fall_back_to_old_protocol(tmp_path,kind,cases):
    # Array inputs are argument rows, so each array value gets its own one-arg row.
    if kind=='Array<Int64>':cases=[[items] for items in cases]
    files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,
        'src/identity.cj':('package bench\npublic func identity(x: '+kind+'): '+kind+' { x }').encode(),
        'src/leaf/other.cj':b'package bench.leaf\npublic func other(n: Int64): Int64 { n }'}
    signature=selected(files,'bench.identity');result,rendered,log=write_and_execute(tmp_path/'actual',files,signature,cases,'oracle')
    assert [o['actual_return'] for o in result['observations']]==[row[0] for row in cases]
    assert all('bench.nexus_verify_' in o['test_id'] for o in result['observations'])
    assert b'NEXUS_ORACLE_V5|' in rendered['source']


@pytest.mark.parametrize('entry',['root-public','long-private'])
def test_v5_real_maximum_canonical_type_and_four_string_fields(tmp_path,entry):
    package='.'.join(['a'*23]*8);name='b'*64;kind=package+'.'+name;root_name=package.split('.')[0]
    config=('[package]\nname="'+root_name+'"\nversion="1.0.0"\ncjc-version="1.0.5"\noutput-type="static"\n[dependencies]\n').encode()
    fields=[f'p{i}' for i in range(4)]
    declaration='package '+package+'\npublic class '+name+' {\n'+''.join('public let '+field+': String\n' for field in fields)
    declaration+='public init('+', '.join(f+': String' for f in fields)+') {\n'+''.join('this.'+f+' = '+f+'\n' for f in fields)+'}\n}\n'
    identity='c'*64
    if entry=='long-private':declaration+='func '+identity+'(value: '+name+'): '+name+' { value }\n'
    files={'cjpm.toml':config,'cjpm.lock':LOCK,
        'src/identity.cj':(('package '+root_name+'\nimport '+package+' as Model\npublic func identity(value: Model.'+name+'): Model.'+name+' { value }') if entry=='root-public' else ('package '+root_name+'\npublic func anchor(n: Int64): Int64 { n }')).encode(),
        'src/'+'/'.join(package.split('.')[1:])+'/state.cj':declaration.encode()}
    # CJPM1.0.5 traverses a child only when every ancestor contains .cj.
    # These are explicit original namespace files, never synthesized in a candidate.
    for depth in range(1,7):
        prefix='.'.join(package.split('.')[:depth+1]);path='src/'+'/'.join(package.split('.')[1:depth+1])+'/namespace.cj'
        files[path]=('package '+prefix+'\n').encode()
    signature=selected(files,root_name+'.identity' if entry=='root-public' else package+'.'+identity)
    value={'$type':kind,'fields':{f:'x'*256 for f in fields}}
    result,rendered,log=write_and_execute(tmp_path/'maximum',files,signature,[[value]],'oracle')
    actual=result['observations'][0]['actual_return']
    assert actual==value and len(scoped_values.encode(actual,kind,signature['types']))==2333
