"""Rehashed nested object tampering must fail reconstruction, fixture SDK only."""
import asyncio,json
from copy import deepcopy
import pytest
from nexus.contracts import digest
from nexus.repair import exploration
from tests.test_object_services import setup,fake_sdk

TABLES=dict(oracle='exploration_runs',property='property_runs',relation='relation_runs',sequence='sequence_runs')


def target(report,kind,scope):
    batch=report['batches'][0]
    if scope=='native':
        axes=report['native_boundary']['response']['data']['axes'];return axes[1 if kind=='sequence' else 0][0]
    if scope=='input':
        return batch['traces'][0]['initial_state'] if kind=='sequence' else batch['pairs'][0]['left'][0] if kind=='relation' else batch['inputs'][0][0]
    item=batch['result']['observations'][0]
    return item['steps'][0]['actual_return'] if kind=='sequence' else item['left']['actual_return'] if kind=='relation' else item['actual_return']


@pytest.mark.parametrize('kind',['oracle','property','relation','sequence'])
@pytest.mark.parametrize('scope',['native','input','observation'])
@pytest.mark.parametrize('change',['bool-int','nominal-tag'])
def test_rehashed_object_values_never_inherit_valid_evidence(kind,scope,change,tmp_path,monkeypatch):
    store,ws,task,apply,engine=setup(tmp_path,kind);fake_sdk(monkeypatch,kind,good=True);c=apply();original=asyncio.run(engine.run(c.id));assert original['state']=='PASS'
    table=TABLES[kind]
    with store.connect() as db:ref,hash_=db.execute('SELECT report_ref,report_sha256 FROM '+table+' WHERE candidate_id=?',(c.id,)).fetchone()
    path=store.root/ref;before=path.read_bytes();changed=deepcopy(original);value=target(changed,kind,scope)
    if change=='bool-int':value['fields']['amount']=False
    else:value['$type']='OtherState'
    raw=exploration.encoded(changed);path.write_bytes(raw)
    with store.connect() as db:db.execute('UPDATE '+table+' SET report_sha256=? WHERE candidate_id=?',(exploration.sha(raw),c.id))
    try:
        with pytest.raises(ValueError):engine.verify(c.id)
    finally:
        path.write_bytes(before)
        with store.connect() as db:db.execute('UPDATE '+table+' SET report_sha256=? WHERE candidate_id=?',(hash_,c.id))
    assert digest(engine.verify(c.id))==digest(original)
