import json
import pytest
from nexus.uploads.service import UploadService
from nexus.store import RunStore
from nexus.contracts import digest

SOURCE=b'public func fee(quantity: Int64, price: Int64): Int64 { quantity + price }\n'
EXAMPLES=[dict(args=[3,100],expected=300,suite='target'),dict(args=[1,0],expected=0,suite='regression')]
RULE=dict(version=1,function='fee',domains={'quantity':dict(min=0,max=1000,points=[1]),'price':dict(min=0,max=1000,points=[100])},expression='quantity * price',seed=0,max_cases=64)


def setup(tmp_path):
    service=UploadService(RunStore(tmp_path));draft=service.prepare('fee.cj',SOURCE,'乘法计算',actor_id='alice',request_key='one')
    return service,draft,dict(expected_version=1,function='fee',examples_json=json.dumps(EXAMPLES),consent=True,actor_id='alice',oracle_json=json.dumps(RULE))


def test_optional_rule_is_confirmed_frozen_and_idempotently_bound(tmp_path):
    service,draft,args=setup(tmp_path)
    value=service.confirm(draft['id'],**args)
    assert value['oracle_hash']==digest(value['oracle_contract'])
    root=service.source(draft['id'],actor_id='alice')
    assert json.loads((root/'verification/oracle.json').read_text())==value['oracle_contract']
    assert service.profile(draft['id'])['context_visibility']['verification/oracle.json']=='VERIFICATION_ONLY'
    assert service.confirm(draft['id'],**args)==value
    with pytest.raises(ValueError):service.confirm(draft['id'],**{**args,'oracle_json':json.dumps({**RULE,'expression':'quantity + price'})})
    (root/'verification/oracle.json').write_text('{}')
    with pytest.raises(ValueError):service.profile(draft['id'])


def test_inconsistent_or_executable_rule_never_confirms_upload(tmp_path):
    service,draft,args=setup(tmp_path)
    for expression in ['quantity + price',"__import__('os')"]:
        with pytest.raises(ValueError):service.confirm(draft['id'],**{**args,'oracle_json':json.dumps({**RULE,'expression':expression})})
        assert service.get(draft['id'],actor_id='alice')['status']=='DRAFT'
