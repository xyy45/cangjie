"""Scoped upload confirmation/freeze, ownership and four contract versions."""
import json
from copy import deepcopy
import pytest
from nexus.contracts import digest,source_manifest
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from tests.test_package_index import project
from tests.test_package_public_tests import examples


def prepared(tmp_path):
    service=UploadService(RunStore(tmp_path));files=project()
    draft=service.prepare_project('packages',None,'跨包业务行为',actor_id='alice',request_key='one',entries=files)
    args=dict(expected_version=1,function='bench.apply',examples_json=json.dumps(examples()),consent=True,
              actor_id='alice',allowed_paths=['src/order.cj'])
    return service,draft,args


def test_confirmation_freezes_canonical_cases_entry_package_source_graph_and_original_tests(tmp_path):
    service,draft,args=prepared(tmp_path);frozen=service.confirm(draft['id'],**args)
    root=service.source(draft['id'],actor_id='alice');profile=service.profile(draft['id'])
    assert frozen['public_test_package']=='bench'
    assert frozen['source_project_index_hash']==digest(draft['project_index'])
    assert frozen['project_index']['graph_hash']==draft['project_index']['graph_hash']
    for path,raw in project().items():assert (root/path).read_bytes()==raw
    assert set(profile['suite_tests']['target'])==set(frozen['public_test_case_ids']['target'])
    assert set(profile['suite_tests']['regression'])==set(frozen['public_test_case_ids']['regression'])|{c['id'] for c in draft['original_tests']}
    assert all(profile['context_visibility'][path]=='VERIFICATION_ONLY' for path in draft['project_index']['test_paths'])
    assert profile['context_visibility'][frozen['public_test_path']]=='PUBLIC_TEST'
    before=source_manifest(root);assert service.confirm(draft['id'],**args)==frozen and source_manifest(root)==before
    assert not any('bridge' in name for name in before)


def test_draft_ownership_and_idempotence_remain_exact_for_scoped_project(tmp_path):
    service,draft,args=prepared(tmp_path)
    assert service.prepare_project('packages',None,'跨包业务行为',actor_id='alice',request_key='one',entries=project())==draft
    with pytest.raises(LookupError):service.get(draft['id'],actor_id='bob')
    changed=project();changed['src/order.cj']+=b'\n// different request'
    with pytest.raises(ValueError):service.prepare_project('packages',None,'跨包业务行为',actor_id='alice',request_key='one',entries=changed)


@pytest.mark.parametrize('change',['graph','signature','case-id','public-source','original-test','metadata'])
def test_read_and_profile_rederive_frozen_scopes_and_public_generation(tmp_path,change):
    service,draft,args=prepared(tmp_path);frozen=service.confirm(draft['id'],**args)
    value=deepcopy(frozen);root=service.store.root/'uploads'/draft['id']/'project'
    if change=='graph':value['project_index']['graph_hash']='f'*64
    elif change=='signature':value['project_index']['functions'][0]['name']='bench.forged'
    elif change=='case-id':value['public_test_case_ids']['target']=['bench.Foreign.case0']
    elif change=='metadata':value['public_test_package']='bench.other'
    else:
        path=value['public_test_path'] if change=='public-source' else value['original_tests'][0]['path']
        (root/path).write_bytes((root/path).read_bytes()+b'\n// tampered frozen bytes')
        value['manifest']=source_manifest(root)
    # Rewriting a self-reported metadata hash cannot replace source rebinding.
    if 'project_index_hash' in value:value['project_index_hash']=digest(value['project_index'])
    with service.store.connect() as db:db.execute('UPDATE upload_projects SET payload=? WHERE id=?',(json.dumps(value),draft['id']))
    with pytest.raises(ValueError):service.profile(draft['id'])


def state(n):return {'$type':'bench.sale.State','fields':{'amount':n}}


def model(kind):
    domains=dict(state=dict(values=[state(i) for i in range(4)]),n=dict(min=1,max=1,points=[]))
    common=dict(version=6 if kind=='oracle' else 5,function='bench.sale.step',domains=domains,seed=7,excluded_inputs=[])
    if kind=='oracle':return dict(**common,expression='object_with(state,"amount",object_get(state,"amount") + n)',max_cases=16)
    if kind=='properties':return dict(**common,kind='single',properties=[dict(id='PROP-STEP',text='状态量按增量增加',precondition='True',assertion='object_get(result,"amount") == object_get(arg0,"amount") + arg1')],max_cases=16)
    if kind=='relations':return dict(**common,kind='relation',relations=[dict(id='REL-SAME',text='相同输入相同输出',precondition='left_arg0 == right_arg0 and left_arg1 == right_arg1',assertion='left_result == right_result')],max_pairs=16)
    return dict(**common,kind='sequence',state_param='state',initial_states=[state(0)],initial_precondition='True',context_params=[],
        operations=[dict(id='OP-INC',text='递增',args=[1],transition='object_with(state,"amount",object_get(state,"amount") + 1)')],
        invariants=[dict(id='INV-NONNEG',text='非负',precondition='True',assertion='object_get(result,"amount") >= 0')],max_sequences=8,max_steps=3)


@pytest.mark.parametrize('kind',['oracle','properties','relations','sequences'])
def test_all_four_scoped_contracts_freeze_with_source_derived_signature(tmp_path,kind):
    files=project();files['src/sale/state.cj']+=b'\npublic func step(state: State, n: Int64): State { State(state.amount+n) }'
    service=UploadService(RunStore(tmp_path));draft=service.prepare_project('packages',None,'按增量改变状态',actor_id='alice',request_key='one',entries=files)
    values=[dict(args=[state(0),1],expected=state(1),suite='target'),dict(args=[state(1),1],expected=state(2),suite='regression')]
    kwargs={kind+'_json':json.dumps(model(kind))}
    frozen=service.confirm(draft['id'],expected_version=1,function='bench.sale.step',examples_json=json.dumps(values),
        consent=True,actor_id='alice',allowed_paths=['src/sale/state.cj'],**kwargs)
    name='oracle_contract' if kind=='oracle' else kind+'_contract';contract=frozen[name]
    assert contract['signature']['scope']['package']=='bench.sale'
    assert contract['signature']['scope']['graph_hash']==frozen['project_index']['graph_hash']
    assert service.profile(draft['id'])['suite_tests']['target'][0].startswith('bench.sale.')
