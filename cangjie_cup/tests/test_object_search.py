"""Finite object domains, model rejection, deterministic shrink and snapshot safety."""
from copy import deepcopy
import pytest
from nexus.repair import oracle,properties,relations,sequences,values
from tests.test_object_contracts import signature,raw_oracle,raw_property,raw_relation,sequence_raw,state


@pytest.mark.parametrize('change',['empty','seventeen','duplicate','missing','extra','wrong-tag','bool-int','nested','array-bool','long-string','raw-types'])
def test_object_oracle_domains_reject_non_closed_or_untyped_values(change):
    raw=raw_oracle();axis=raw['domains']['state']['values']
    if change=='empty':axis.clear()
    elif change=='seventeen':raw['domains']['state']['values']=[state(i) for i in range(17)]
    elif change=='duplicate':axis.append(deepcopy(axis[0]))
    elif change=='missing':del axis[0]['fields']['amount']
    elif change=='extra':axis[0]['fields']['extra']=0
    elif change=='wrong-tag':axis[0]['$type']='OtherState'
    elif change=='bool-int':axis[0]['fields']['amount']=False
    elif change=='nested':axis[0]['fields']['amount']=state()
    elif change=='array-bool':axis[0]['fields']['items']=[True]
    elif change=='long-string':axis[0]['fields']['label']='a'*257
    else:raw['types']=signature()['types']
    with pytest.raises(ValueError):oracle.validate_contract(raw,signature(),[])


@pytest.mark.parametrize('module,raw',[(properties,raw_property),(relations,raw_relation)])
@pytest.mark.parametrize('version',[1,2,3,5])
def test_object_other_models_require_version_four(module,raw,version):
    value=raw();value['version']=version
    with pytest.raises(ValueError):module.validate_contract(value,signature(),[])


@pytest.mark.parametrize('version',[1,2,3,5])
def test_object_sequence_requires_version_four(version):
    raw,sig=sequence_raw();raw['version']=version
    with pytest.raises(ValueError):sequences.validate_contract(raw,sig,[])


def test_object_sampler_uses_finite_domain_and_checks_nominal_native_axes():
    c=oracle.validate_contract(raw_oracle(),signature(),[]);axes=oracle.checked_axes(c);rows=oracle.generate_inputs(c)
    assert rows==oracle.generate_inputs(c) and len(rows)==8 and len({oracle.input_key(a) for a in rows})==8
    assert all(a[0] in c['domains']['state']['values'] for a in rows)
    assert rows[:4]==[[state(0),0],[state(1),0],[state(2),0],[state(3),0]]
    assert oracle.checked_axes(c,deepcopy(axes))==axes
    for field,value in [('amount',False),('items',[True])]:
        bad=deepcopy(axes);bad[0][0]['fields'][field]=value
        with pytest.raises(ValueError):oracle.checked_axes(c,bad)
    bad=deepcopy(axes);bad[0][0]['$type']='OtherState'
    with pytest.raises(ValueError):oracle.checked_axes(c,bad)
    rows[0][0]['fields']['items'].append(99);axes[0][1]['fields']['items'].append(99)
    assert oracle.generate_inputs(c)[0]==[state(0),0] and c['domains']['state']['values'][1]==state(1)


def test_object_shrink_is_domain_only_preserves_reserved_and_independent():
    raw=raw_oracle();raw['excluded_inputs']=[[state(0),1]];c=oracle.validate_contract(raw,signature(),[])
    original=[state(3),1];before=deepcopy(original);small=oracle.shrink_inputs(c,original)
    assert small and small==oracle.shrink_inputs(c,original) and [state(0),1] not in small
    assert all(row[0] in c['domains']['state']['values'] and sum(values.primitive_weight(v) for v in row)<sum(values.primitive_weight(v) for v in original) for row in small)
    small[0][0]['fields']['items'].append(99);assert original==before and c['domains']['state']['values'][0]==state(0)


def test_object_pair_cumulative_shrink_and_failure_snapshots():
    c=relations.validate_contract(raw_relation(),signature(),[]);pair=dict(left=[state(3),1],right=[state(3),1]);before=deepcopy(pair)
    planned=relations.generate_pairs(c,cumulative=[pair]);assert planned['pairs'][0]==pair and planned['regression_pairs']==1
    smaller=relations.shrink_pairs(c,pair,'REL-IDENTITY');assert smaller and all(relations.pair_score(p)<relations.pair_score(pair) for p in smaller)
    actual=state(2);failed=relations.evaluate_pair(c,pair,actual,state(3));failed['failures'][0]['left_actual_return']['fields']['items'].append(99)
    planned['pairs'][0]['left'][0]['fields']['items'].append(88);smaller[0]['right'][0]['fields']['amount']=99
    assert pair==before and actual==state(2)
    with pytest.raises(ValueError):relations.generate_pairs(c,cumulative=[dict(left=[state(i%4),i//4%2],right=[state(i//8%4),i//32%2]) for i in range(17)])


def test_object_sequence_fixed_array_context_and_object_constant_are_not_markers():
    raw,sig=sequence_raw();sig['params'][2]['type']='Array<Int64>';raw['domains']['label']={'values':[[],[1,2]]}
    c=sequences.validate_contract(raw,sig,[]);plan=sequences.generate_traces(c)
    assert plan['traces'] and all(s['args'][1]==t['context'][0] for t in plan['traces'] for s in t['steps'])
    # A nominal object literal in a nonstate slot is frozen data, not a domain marker.
    raw,sig=sequence_raw();sig['params'][0]['type']='OrderState';raw['domains']['mode']={'values':[state(0),state(1)]};raw['operations'][0]['args'][0]=state(1)
    c=sequences.validate_contract(raw,sig,[]);traces=sequences.generate_traces(c)['traces'];assert all(s['args'][0]==state(1) for t in traces for s in t['steps'])
    broken=deepcopy(traces[0]);broken['steps'][0]['args'][0]=state(0)
    with pytest.raises(ValueError):sequences.reference_trace(c,broken)


def test_object_sequence_reachable_shrink_context_and_plan_aliases():
    raw,sig=sequence_raw();c=sequences.validate_contract(raw,sig,[])
    trace=dict(initial_state=state(0),context=['中'],steps=[dict(operation_id='OP-FLIP',args=[0,'中']) for _ in range(4)]);before=deepcopy(trace)
    smaller=sequences.shrink_traces(c,trace,'MODEL-OP-FLIP');assert smaller and all(sequences.trace_score(t)<sequences.trace_score(trace) for t in smaller)
    plan=sequences.reference_trace(c,trace);plan['steps'][0]['expected_state']['fields']['items'].append(99)
    assert plan['steps'][1]['before_state']==state(1) and trace==before
    bad=deepcopy(trace);bad['steps'][1]['args'][1]='a'
    with pytest.raises(ValueError):sequences.reference_trace(c,bad)
    cumulative=[dict(initial_state=state(i%2),context=['a' if i%4<2 else '中'],steps=[dict(operation_id='OP-FLIP',args=[0,'a' if i%4<2 else '中']) for _ in range(2+i//4)]) for i in range(9)]
    c['initial_states']=[state(0),state(1)]
    with pytest.raises(ValueError):sequences.generate_traces(c,cumulative=cumulative)


@pytest.mark.parametrize('change',['out-initial','out-transition','contradiction','invariant','public-conflict'])
def test_object_sequence_rejects_unreachable_or_conflicting_models(change):
    raw,sig=sequence_raw();examples=[]
    if change=='out-initial':raw['initial_states']=[state(9)]
    elif change=='out-transition':raw['operations'][0]['transition']='object_with(state,"amount",9)'
    elif change=='contradiction':raw['operations'].append({**raw['operations'][0],'id':'OP-OTHER','transition':'state'})
    elif change=='invariant':raw['invariants'][0]['assertion']='object_get(result,"amount") == 0'
    else:examples=[dict(args=[0,state(0),'a'],expected=state(0))]
    with pytest.raises(ValueError):sequences.validate_contract(raw,sig,examples)


def test_object_scalar_expected_and_public_values_require_nominal_exactness():
    raw=raw_oracle();raw['expression']='object_get(state,"amount")+n';sig=signature('Int64')
    c=oracle.validate_contract(raw,sig,[dict(args=[state(1),1],expected=2)]);assert oracle.expected(c,[state(2),1])==3
    with pytest.raises(ValueError):oracle.validate_contract(raw,sig,[dict(args=[state(1),1],expected=True)])
    p=properties.validate_contract(raw_property(),signature(),[]);bad=state(1);bad['fields']['active']=1
    with pytest.raises(ValueError):properties.evaluate_result(p,[state(0),1],bad)
