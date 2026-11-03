"""Actual native IPC for String axes; never a transport fixture."""
import asyncio
import json
from copy import deepcopy
import pytest
from nexus.policy.core import NativeCoreClient
from nexus.repair import oracle


def payload(items):return dict(domains=[dict(name='code',type='String',domain=dict(values=items)),dict(name='enabled',type='Bool',domain={})])


def test_native_string_axes_preserve_exact_order_unicode_and_empty_values(tmp_path):
    core=NativeCoreClient();p=payload(['中','',chr(0)+chr(10),'中'*85+'x']);proof=asyncio.run(core.call('boundary.axes',p))
    (tmp_path/'native-string-proof.json').write_text(json.dumps(proof,ensure_ascii=True,indent=2))
    assert proof['response']['data']==dict(axes=[p['domains'][0]['domain']['values'],[False,True]])
    assert core.verify_proof(proof,'boundary.axes',p)==proof['response']['data']
    changed=deepcopy(proof);changed['response']['data']['axes'][0][0]='different'
    settings=dict(signature=dict(name='f',params=[dict(name=d['name'],type=d['type']) for d in p['domains']],return_type='Bool'),domains={d['name']:d['domain'] for d in p['domains']})
    # The IPC envelope is not a signature; the consumer independently checks data.
    with pytest.raises(ValueError):oracle.checked_axes(settings,core.verify_proof(changed,'boundary.axes',p)['axes'])


@pytest.mark.parametrize('domain',[{},dict(values=[]),dict(values=['a','a']),dict(values=[True]),dict(values=[1]),dict(values=['x'*257]),dict(values=[str(i) for i in range(17)]),dict(values=['a'],extra=1)])
def test_native_string_invalid_domains_fail_before_a_valid_axes_proof(tmp_path,domain):
    p=payload(['a']);p['domains'][0]['domain']=domain
    (tmp_path/'request.json').write_text(json.dumps(p,ensure_ascii=True))
    with pytest.raises(ValueError) as error:asyncio.run(NativeCoreClient().call('boundary.axes',p))
    (tmp_path/'rejection.txt').write_text(str(error.value))
