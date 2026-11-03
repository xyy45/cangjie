"""Hard synthetic tasks remain byte-bound data, not model-success evidence."""
import importlib
import importlib.util
import json
import re
from collections import Counter

import pytest

from nexus.benchmark.catalog import VERSION as LEGACY_VERSION
from nexus.benchmark.corpus import CONFIG, LOCK, build_corpus, load_corpus, public_material
from nexus.contracts import digest
from nexus.projects.index import inspect_project
from nexus.repair import oracle

LEGACY_HASHES={30:'d7cc0ee64e24230091bf891d94e11dc671cc180419dee4062937c5681e15333d',
               100:'d16e7982a09999f55206b564d91383c96bf2072debb2228942c4a1ef70389bd1'}


def modules():
    assert importlib.util.find_spec('nexus.benchmark.hard_catalog') is not None, 'hard business catalog missing'
    assert importlib.util.find_spec('nexus.benchmark.hard_corpus') is not None, 'hard corpus builder missing'
    return (importlib.import_module('nexus.benchmark.hard_catalog'),
            importlib.import_module('nexus.benchmark.hard_corpus'))


def hard(root):
    catalog,builder=modules()
    identity=builder.build_hard_corpus(root,count=10)
    loaded=load_corpus(root)
    assert loaded['generator']==catalog.VERSION and loaded['corpus_hash']==identity
    return loaded


def test_hard_ten_families_and_interfaces(tmp_path):
    catalog,_=modules();authored=catalog.tasks(10)
    assert len(authored)==len({t['family'] for t in authored})==10
    sizes=[];arities=[];bool_inputs=False
    for task in authored:
        assert task['variant']==1 and task['source']!=task['reference']
        assert task['goal'].strip() and task['defect'].strip()
        assert 1<=len(task['source'])<=3 and set(task['source'])==set(task['reference'])
        index=inspect_project({'cjpm.toml':CONFIG,'cjpm.lock':LOCK,**task['source']})
        reference=inspect_project({'cjpm.toml':CONFIG,'cjpm.lock':LOCK,**task['reference']})
        signature=next(f for f in index['functions'] if f['name']==task['function'])
        stable=lambda x:[{k:f[k] for k in ('name','params','return_type','public','path')} for f in x['functions']]
        assert stable(index)==stable(reference)
        arities.append(len(signature['params']));sizes.append((len(task['source']),len(index['functions'])))
        bool_inputs|=any(p['type']=='Bool' for p in signature['params'])
        assert task['public_inputs'] and task['holdout_witnesses']
    assert max(arities)==4 and bool_inputs
    assert any(files>=2 and functions>=3 for files,functions in sizes)
    assert len(hard(tmp_path/'hard')['tasks'])==10


@pytest.mark.parametrize('count',[30,100])
def test_old_corpus_bytes_and_profiles_unchanged(tmp_path,count):
    root=tmp_path/'legacy'
    assert build_corpus(root,count=count)==LEGACY_HASHES[count]
    assert load_corpus(root)['generator']==LEGACY_VERSION


@pytest.mark.parametrize('version,count',[('unknown-hard-version',10),(LEGACY_VERSION,10),('HARD',100),(None,10),([],10),({},10),('HARD',10.0),('HARD',True)])
def test_hard_unknown_version_count_combinations_are_rejected(tmp_path,version,count):
    catalog,_=modules();root=tmp_path/'hard';hard(root)
    manifest=json.loads((root/'manifest.json').read_bytes())
    manifest.update(generator=catalog.VERSION if version=='HARD' else version,count=count)
    manifest['corpus_hash']=digest({k:v for k,v in manifest.items() if k!='corpus_hash'})
    (root/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='版本'):load_corpus(root)


def test_hard_material_visibility_and_reserved_inputs(tmp_path):
    corpus=hard(tmp_path/'hard')
    for task in corpus['tasks']:
        assert task['provenance']=='TEAM_AUTHORED_SYNTHETIC'
        public=public_material(task)
        assert set(public)=={'id','goal','function','allowed_paths','files','examples'}
        assert all(not p.startswith(('private/','verification/')) for p in public['files'])
        public_keys={oracle.input_key(e['args']) for e in task['examples']}
        sealed={oracle.input_key(e['args']) for e in task['holdout']}
        assert sealed and not public_keys.intersection(sealed)
        assert task['oracle']['version']==2
        assert {oracle.input_key(a) for a in task['oracle']['excluded_inputs']}==sealed
        search=oracle.validate_contract(task['oracle'],task['normalized_oracle']['signature'],task['examples'])
        inputs=oracle.generate_inputs(search)
        assert inputs and not sealed.intersection(oracle.input_key(a) for a in inputs)
        assert not sealed.intersection(oracle.input_key(a) for a in oracle.shrink_inputs(search,inputs[0]))


def test_hard_determinism_and_reject_overwrite_or_unsupported_size(tmp_path):
    _,builder=modules();a=tmp_path/'a';b=tmp_path/'b'
    assert builder.build_hard_corpus(a,count=10)==builder.build_hard_corpus(b,count=10)
    with pytest.raises(FileExistsError):builder.build_hard_corpus(a,count=10)
    for count in (True,0,11,100):
        with pytest.raises(ValueError):builder.build_hard_corpus(tmp_path/str(count),count=count)


def test_hard_tampered_private_material_and_links_are_rejected(tmp_path):
    root=tmp_path/'hard';hard(root);manifest=json.loads((root/'manifest.json').read_bytes())
    path=root/next(p for p in manifest['files'] if p.endswith('holdout.json'))
    raw=path.read_bytes();path.write_bytes(raw+b' ')
    with pytest.raises(ValueError,match='摘要'):load_corpus(root)
    path.unlink();external=tmp_path/'original';external.write_bytes(raw);path.symlink_to(external)
    with pytest.raises(ValueError,match='链接'):load_corpus(root)


def test_hard_thirty_defects_not_numeric_clones(tmp_path):
    catalog,builder=modules();authored=catalog.tasks(30)
    assert len(authored)==30 and authored[:10]==catalog.tasks(10)
    assert set(Counter(t['family'] for t in authored).values())=={3}
    for family in {t['family'] for t in authored}:
        variants=[t for t in authored if t['family']==family]
        assert {t['variant'] for t in variants}=={1,2,3}
        assert len({t['defect'] for t in variants})==3
        # Names and numeric substitutions cannot count as a new defect.
        canonical=lambda t:re.sub(r'\d+','N',''.join(v.decode() for v in t['source'].values()))
        assert len({canonical(t) for t in variants})==3
        assert len({json.dumps(t['holdout_witnesses']) for t in variants})==3
    builder.build_hard_corpus(tmp_path/'hard',30)
    loaded=load_corpus(tmp_path/'hard')
    assert len(loaded['tasks'])==30
    for task,original in zip(loaded['tasks'],authored,strict=True):
        sealed={oracle.input_key(e['args']) for e in task['holdout']}
        assert all(oracle.input_key(a) in sealed for a in original['holdout_witnesses'])
        assert {oracle.input_key(a) for a in task['oracle']['excluded_inputs']}==sealed
        search=oracle.validate_contract(task['oracle'],task['normalized_oracle']['signature'],task['examples'])
        for args in oracle.generate_inputs(search):
            assert oracle.input_key(args) not in sealed
            assert not sealed.intersection(oracle.input_key(a) for a in oracle.shrink_inputs(search,args))


@pytest.mark.parametrize('mutation',['reference-interface','allowed-path'])
def test_hard_rehashed_interface_or_path_mutation_is_rejected(tmp_path,mutation):
    root=tmp_path/'hard';hard(root);manifest=json.loads((root/'manifest.json').read_bytes())
    name=next(p for p in manifest['files'] if p.endswith('private/reference/src/logic.cj')) if mutation=='reference-interface' else manifest['tasks'][0]
    path=root/name
    if mutation=='reference-interface':
        path.write_bytes(path.read_bytes().replace(b'requested: Int64)',b'requested: Int64, audit: Int64)'))
    else:
        meta=json.loads(path.read_bytes());meta['allowed_paths']=['src/other.cj'];path.write_bytes(json.dumps(meta).encode())
    import hashlib
    manifest['files'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest['corpus_hash']=digest({k:v for k,v in manifest.items() if k!='corpus_hash'})
    (root/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='接口变化'):load_corpus(root)
