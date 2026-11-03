"""Scoped versions preserve nominal identity through finite business models."""
from copy import deepcopy
import pytest

from nexus.repair import oracle,properties,relations,sequences
from tests.test_object_contracts import signature,raw_oracle,raw_property,raw_relation,sequence_raw,state


def canonical(raw):
    if type(raw) is list:return [canonical(v) for v in raw]
    if type(raw) is dict:return {(('bench.model.'+k) if k=='OrderState' else k):canonical(v) for k,v in raw.items()}
    if raw=='OrderState':return 'bench.model.OrderState'
    return raw


def scoped(sig):
    sig=canonical(deepcopy(sig));local=sig['name'];sig['name']='bench.ops.'+local
    sig['scope']=dict(version=1,root_package='bench',package='bench.ops',local_name=local,
        path='src/ops/entry.cj',graph_hash='a'*64)
    return sig


def contract(module):
    if module is sequences:raw,sig=sequence_raw()
    else:raw,sig=({oracle:raw_oracle,properties:raw_property,relations:raw_relation}[module])(),signature()
    raw=canonical(raw);sig=scoped(sig);raw.update(function=sig['name'],version=6 if module is oracle else 5)
    return raw,sig


@pytest.mark.parametrize('module',[oracle,properties,relations,sequences])
def test_all_scoped_models_keep_source_scope_and_package_nominal_registry(module):
    raw,sig=contract(module);result=module.validate_contract(raw,sig,[])
    assert result['version']==(6 if module is oracle else 5)
    assert result['signature']==sig and result['algorithm'].endswith('packages-v'+str(result['version']))
    sig['scope']['package']='changed';raw['domains'].clear()
    assert result['signature']['scope']['package']=='bench.ops' and result['domains']


@pytest.mark.parametrize('module',[oracle,properties,relations,sequences])
@pytest.mark.parametrize('change',['old-version','missing-scope','null-scope','wrong-source','raw-scope','raw-types'])
def test_scoped_and_legacy_contracts_cannot_mix_and_model_cannot_supply_authority(module,change):
    raw,sig=contract(module)
    if change=='old-version':raw['version']-=1
    elif change=='missing-scope':sig.pop('scope')
    elif change=='null-scope':sig['scope']=None
    elif change=='wrong-source':sig['scope']['path']='src/other/entry.cj'
    elif change=='raw-scope':raw['scope']=sig['scope']
    else:raw['types']=sig['types']
    with pytest.raises(ValueError):module.validate_contract(raw,sig,[])


@pytest.mark.parametrize('kind,value,expression',[
    ('Int64',1,'x'),('Bool',True,'x'),('String','中','x'),('Array<Int64>',[1,2],'x')])
def test_scoped_version_precedes_value_kind_for_scalar_and_array_oracles(kind,value,expression):
    sig=scoped(dict(name='identity',params=[dict(name='x',type=kind)],return_type=kind))
    domain={} if kind=='Bool' else dict(min=0,max=2,points=[]) if kind=='Int64' else dict(values=[value])
    raw=dict(version=6,function=sig['name'],domains={'x':domain},expression=expression,seed=7,max_cases=16,excluded_inputs=[])
    result=oracle.validate_contract(raw,sig,[dict(args=[value],expected=value,suite='target')])
    assert result['signature']['scope']==sig['scope'] and oracle.expected(result,[value])==value
    prop=dict(version=5,kind='single',function=sig['name'],domains={'x':domain},properties=[dict(id='PROP-ID',text='保持值',precondition='True',assertion='result == arg0')],seed=7,max_cases=16,excluded_inputs=[])
    p=properties.validate_contract(prop,sig,[])
    assert properties.version(sig)==5 and properties.evaluate_result(p,[value],value)['state']=='PASS'


def test_object_oracle_expected_sampling_shrink_and_nominal_controls():
    raw,sig=contract(oracle);c=oracle.validate_contract(raw,sig,[])
    before=deepcopy(c);observed=oracle.expected(c,[canonical(state(1)),1])
    assert observed==canonical(state(2)) and c==before
    generated=oracle.generate_inputs(c);assert generated==oracle.generate_inputs(c)
    smaller=oracle.shrink_inputs(c,[canonical(state(3)),1]);assert smaller
    bad=canonical(state(1));bad['$type']='bench.refund.OrderState'
    with pytest.raises(ValueError):oracle.expected(c,[bad,1])
    bad=canonical(state(1));bad['fields']['amount']=True
    with pytest.raises(ValueError):oracle.expected(c,[bad,1])


def test_scoped_properties_relations_and_state_sequence_use_real_value_snapshots():
    raw,sig=contract(properties);p=properties.validate_contract(raw,sig,[])
    assert properties.evaluate_result(p,[canonical(state(1)),1],canonical(state(2)))['state']=='PASS'
    assert properties.evaluate_result(p,[canonical(state(1)),1],canonical(state(3)))['state']=='FAIL'
    raw,sig=contract(relations);r=relations.validate_contract(raw,sig,[])
    pair=dict(left=[canonical(state(1)),1],right=[canonical(state(1)),1])
    assert relations.evaluate_pair(r,pair,canonical(state(2)),canonical(state(3)))['state']=='FAIL'
    assert relations.generate_pairs(r)['pairs']
    raw,sig=contract(sequences);c=sequences.validate_contract(raw,sig,[])
    trace=dict(initial_state=canonical(state(0)),context=['中'],steps=[dict(operation_id='OP-FLIP',args=[0,'中']) for _ in range(3)])
    plan=sequences.reference_trace(c,trace)
    assert [s['expected_state'] for s in plan['steps']]==[canonical(state(1)),canonical(state(0)),canonical(state(1))]
    assert sequences.evaluate_step(c,plan['steps'][0],canonical(state(0)))['state']=='FAIL'
    assert sequences.shrink_traces(c,trace,'MODEL-OP-FLIP')


def test_old_scalar_versions_reject_canonical_function_without_scope():
    sig=dict(name='bench.identity',params=[dict(name='x',type='Int64')],return_type='Int64')
    raw=dict(version=1,function='bench.identity',domains={'x':dict(min=0,max=1)},expression='x',seed=7,max_cases=16)
    with pytest.raises(ValueError):oracle.validate_contract(raw,sig,[])
    with pytest.raises(ValueError):oracle.stable_signature(sig)


def test_reserved_verification_namespace_is_casefold_safe_for_macos():
    from nexus.projects.names import package_name
    for value in ('bench.nexus_verify_fake','bench.NEXUS_VERIFY_fake','bench.Nexus_Verify_fake'):
        with pytest.raises(ValueError):package_name(value)
