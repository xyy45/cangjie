"""A reproducible synthetic corpus is data, never model success evidence."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from nexus.benchmark.corpus import build_corpus,load_corpus,public_material
from nexus.contracts import digest


def test_first_thirty_are_distinct_semantics_and_inputs_are_private(tmp_path):
    build_corpus(tmp_path/'data',count=30)
    corpus=load_corpus(tmp_path/'data')
    assert len(corpus['tasks'])==30
    assert len({t['family'] for t in corpus['tasks']})==30
    for task in corpus['tasks']:
        material=public_material(task)
        assert len(material['examples'])>=2 and task['holdout']
        assert {'target','regression'}=={e['suite'] for e in material['examples']}
        assert all('private' not in name and 'reference' not in name for name in material['files'])
        assert 'oracle' not in material and 'holdout' not in material and 'reference' not in material
        assert task['function'] in ''.join(raw.decode() for raw in material['files'].values())
        assert task['source']!=task['reference']
        public_keys={json.dumps(e['args']) for e in material['examples']}
        assert all(json.dumps(e['args']) not in public_keys for e in task['holdout'])


def test_expansion_is_deterministic_and_discloses_family_variants(tmp_path):
    build_corpus(tmp_path/'a',count=100);build_corpus(tmp_path/'b',count=100)
    a=load_corpus(tmp_path/'a');b=load_corpus(tmp_path/'b')
    assert a['corpus_hash']==b['corpus_hash']
    assert len(a['tasks'])==100 and len({t['family'] for t in a['tasks']})==30
    assert all(t['variant']==1 for t in a['tasks'][:30])
    assert max(t['variant'] for t in a['tasks'])==4
    assert len({digest({p:hashlib.sha256(raw).hexdigest() for p,raw in t['source'].items()}) for t in a['tasks']})==100
    assert any(len(t['source'])==2 for t in a['tasks'])


def test_mutation_and_symlink_are_rejected_before_loading(tmp_path):
    root=tmp_path/'data';build_corpus(root,count=30)
    manifest=json.loads((root/'manifest.json').read_text())
    path=root/next(p for p in manifest['files'] if p.endswith('holdout.json'))
    before=path.read_bytes();path.write_bytes(before+b' ')
    with pytest.raises(ValueError,match='摘要'):load_corpus(root)
    path.unlink();external=tmp_path/'original.json';external.write_bytes(before);path.symlink_to(external)
    with pytest.raises(ValueError,match='链接'):load_corpus(root)


def test_rejects_overwrite_bad_count_and_unbound_manifest(tmp_path):
    root=tmp_path/'data';build_corpus(root,count=30);corpus=load_corpus(root)
    with pytest.raises(FileExistsError):build_corpus(root,count=30)
    with pytest.raises(ValueError):build_corpus(tmp_path/'bad',count=31)
    with pytest.raises(ValueError,match='版本'):load_corpus(root,expected_hash='f'*64)
    assert load_corpus(root,expected_hash=corpus['corpus_hash'])['corpus_hash']==corpus['corpus_hash']


def test_public_material_is_a_copy(tmp_path):
    build_corpus(tmp_path/'data',count=30);task=load_corpus(tmp_path/'data')['tasks'][0]
    before=copy.deepcopy(task);view=public_material(task);view['examples'][0]['expected']='forged'
    assert task==before


def test_sealed_holdout_is_excluded_from_search_and_shrink(tmp_path):
    from nexus.repair import oracle
    build_corpus(tmp_path/'data',count=30)
    for task in load_corpus(tmp_path/'data')['tasks']:
        signature=task['normalized_oracle']['signature']
        search=oracle.validate_contract(task['oracle'],signature,task['examples'])
        sealed={json.dumps(e['args']) for e in task['holdout']}
        generated=oracle.generate_inputs(search)
        assert generated and not sealed.intersection(json.dumps(a) for a in generated)
        for a in generated:assert not sealed.intersection(json.dumps(s) for s in oracle.shrink_inputs(search,a))

