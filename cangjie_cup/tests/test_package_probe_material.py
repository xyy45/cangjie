"""Four-model scoped probe derivation without executing candidates."""
import importlib
from copy import deepcopy
import pytest
from nexus.projects.index import inspect_project
from nexus.repair.scoped_signature import validate
from nexus.repair import oracle,properties,relations,sequences
from tests.test_package_index import project,cases
from tests.test_package_uploads import model,state

TOKEN='0123456789abcdef'


def prepared(mode):
    files=project();files['src/sale/state.cj']+=b'\nfunc step(state: State, n: Int64): State { State(state.amount+n) }'
    index=inspect_project(files);signature=validate(next(f for f in index['functions'] if f['name']=='bench.sale.step'))
    key={'oracle':'oracle','single':'properties','relation':'relations','sequence':'sequences'}[mode]
    module={'oracle':oracle,'single':properties,'relation':relations,'sequence':sequences}[mode]
    contract=module.validate_contract(model(key),signature,[])
    items=([dict(initial_state=state(0),context=[],steps=[dict(operation_id='OP-INC',args=[1]) for _ in range(3)])] if mode=='sequence' else
           [dict(left=[state(0),1],right=[state(0),1])] if mode=='relation' else [[state(0),1]])
    return files,signature,contract,items


@pytest.mark.parametrize('mode',['oracle','single','relation','sequence'])
def test_probe_material_uses_controller_bridge_and_complete_derived_scan_index(mode):
    files,signature,contract,items=prepared(mode);before=deepcopy(files)
    module=importlib.import_module('nexus.repair.scoped_probe')
    result=module.prepare(files,signature,TOKEN,mode,items,contract=contract)
    assert files==before and not any('nexus_verify_' in p for p in before)
    assert result['binding']['private'] and result['binding']['bridge_path'] in result['files']
    assert all(not p.endswith('_test.cj') or p==result['harness_path'] for p in result['files'])
    assert result['harness_path'].startswith('src/nexus_verify_'+TOKEN+'/')
    assert result['scan_index']['graph_hash']!=signature['scope']['graph_hash']
    assert result['original_graph_hash']==signature['scope']['graph_hash']
    assert not result['scan_index']['dependency_graph']['test_edges']
    assert result['case_ids'][0].startswith('bench.nexus_verify_'+TOKEN+'.')
    assert len(result['case_ids'])==(2 if mode=='relation' else 1)


def test_probe_strips_test_only_packages_without_inventing_namespace_sources():
    files,signature,contract,items=prepared('oracle')
    files['src/checks/cases_test.cj']=cases('bench.checks','fee(1), 2','import bench.sale.fee')
    # New test-only package changes the frozen graph, hence requires a newly derived signature/contract.
    index=inspect_project(files);signature=validate(next(f for f in index['functions'] if f['name']=='bench.sale.step'))
    contract=oracle.validate_contract(model('oracle'),signature,[])
    result=importlib.import_module('nexus.repair.scoped_probe').prepare(files,signature,TOKEN,'oracle',items,contract=contract)
    assert 'bench.checks' not in result['scan_index']['packages']
    assert not any('/checks/' in p for p in result['files'])
    assert not any(p.endswith('namespace.cj') for p in result['files'])


def test_source_bound_signature_and_frozen_contract_cannot_be_swapped_during_derivation():
    files,signature,contract,items=prepared('oracle');module=importlib.import_module('nexus.repair.scoped_probe')
    bad=deepcopy(contract);bad['signature']['scope']['graph_hash']='f'*64
    with pytest.raises(ValueError):module.prepare(files,signature,TOKEN,'oracle',items,contract=bad)


def test_snapshot_can_record_derived_files_after_original_admission_without_lowering_user_limit(tmp_path):
    from nexus.execution.package_validation import _snapshot
    from nexus.repair.scoped_probe import prepare
    files,_,_,items=prepared('oracle');files={p:raw for p,raw in files.items() if not p.endswith('_test.cj')}
    for i in range(99-len(files)):files['README_'+str(i)+'.md']=b'original documentation'
    index=inspect_project(files);signature=validate(next(f for f in index['functions'] if f['name']=='bench.sale.step'))
    contract=oracle.validate_contract(model('oracle'),signature,[])
    result=prepare(files,signature,TOKEN,'oracle',items,contract=contract)
    assert len(files)==99 and len(result['files'])==101
    root=tmp_path/'project';root.mkdir()
    for name,raw in result['files'].items():
        path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    assert _snapshot(root)==result['manifest']
