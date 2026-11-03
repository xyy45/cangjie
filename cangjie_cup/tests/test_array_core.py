"""Actual native Array IPC, no transport fixture."""
import asyncio,json
from copy import deepcopy
import pytest
from nexus.policy.core import NativeCoreClient
from nexus.repair import oracle


def payload(domain):return dict(domains=[dict(name='items',type='Array<Int64>',domain=domain),dict(name='enabled',type='Bool',domain={}),dict(name='label',type='String',domain=dict(values=['','中']))])


def test_native_array_axes_preserve_empty_extremes_and_order_with_consumer_recheck(tmp_path):
    p=payload(dict(values=[[],[0],[-(1<<63)]*16,[(1<<63)-1,-1]]));core=NativeCoreClient();proof=asyncio.run(core.call('boundary.axes',p));(tmp_path/'proof.json').write_text(json.dumps(proof,indent=2))
    data=core.verify_proof(proof,'boundary.axes',p);assert data==dict(axes=[p['domains'][0]['domain']['values'],[False,True],['','中']])
    c=dict(signature=dict(name='f',params=[dict(name=d['name'],type=d['type']) for d in p['domains']],return_type='Bool'),domains={d['name']:d['domain'] for d in p['domains']})
    assert oracle.checked_axes(c,data['axes'])==data['axes']
    changed=deepcopy(proof);changed['response']['data']['axes'][0][1]=[False]
    with pytest.raises(ValueError):oracle.checked_axes(c,core.verify_proof(changed,'boundary.axes',p)['axes'])

@pytest.mark.parametrize('domain',[{},dict(values=[]),dict(values=[[],[]]),dict(values=[True]),dict(values=[[True]]),dict(values=[[1.0]]),dict(values=[[[1]]]),dict(values=[[1<<63]]),dict(values=[[0]*17]),dict(values=[[i] for i in range(17)]),dict(values=[[]],extra=1)])
def test_native_array_invalid_domains_are_rejected_before_valid_proof(tmp_path,domain):
    p=payload(domain);(tmp_path/'request.json').write_text(json.dumps(p))
    with pytest.raises(ValueError) as error:asyncio.run(NativeCoreClient().call('boundary.axes',p))
    (tmp_path/'rejection.txt').write_text(str(error.value))
