"""Real native stdio object axes; no model, remote MCP or graph transport."""
import asyncio,json,subprocess
from copy import deepcopy
from nexus.policy.core import NativeCoreClient
from nexus.contracts import digest
from nexus.adapters.cangjie.sdk import sdk_environment
from nexus.repair import oracle
from nexus.repair.exploration import boundary_payload
from tests.test_object_contracts import raw_oracle,signature,state
import pytest


def payload():
    c=oracle.validate_contract(raw_oracle(),signature(),[])
    return dict(domains=[dict(name=p['name'],type=p['type'],domain=c['domains'][p['name']]) for p in c['signature']['params']],types={k:{key:deepcopy(v[key]) for key in ('kind','fields')} for k,v in c['signature']['types'].items()})


def test_object_boundary_payload_has_value_projection_only_and_copies():
    c=oracle.validate_contract(raw_oracle(),signature(),[]);p=boundary_payload(c);assert p==payload()
    p['domains'][0]['domain']['values'][0]['fields']['items'].append(9);p['types']['OrderState']['fields'][0]['name']='other'
    assert c['domains']['state']['values'][0]==state(0) and c['signature']['types']['OrderState']['fields'][0]['name']=='amount'
    plain=dict(signature=dict(params=[dict(name='n',type='Bool')],return_type='Bool'),domains=dict(n={}))
    assert boundary_payload(plain)==dict(domains=[dict(name='n',type='Bool',domain={})])


@pytest.mark.parametrize('kind',['struct','class'])
def test_native_objects_axes_are_nominal_complete_ordered_and_rechecked(tmp_path,kind):
    p=payload();p['types']['OrderState']['kind']=kind;core=NativeCoreClient();proof=asyncio.run(core.call('boundary.axes',p))
    (tmp_path/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2))
    result=core.verify_proof(proof,'boundary.axes',p);c=oracle.validate_contract(raw_oracle(),signature(),[])
    assert result==dict(axes=[p['domains'][0]['domain']['values'],[0,1]]) and oracle.checked_axes(c,result['axes'])==result['axes']
    changed=deepcopy(proof);changed['response']['data']['axes'][0][0]['fields']['amount']=False
    with pytest.raises(ValueError):oracle.checked_axes(c,core.verify_proof(changed,'boundary.axes',p)['axes'])


def rejection(p,tmp_path):
    core=NativeCoreClient();request=dict(schema_version=1,core_version='2.0',operation='boundary.axes',request_id='object-rejection',payload_hash=digest(p),payload=p)
    result=subprocess.run([str(core.root/'.runtime/core')],input=json.dumps(request,ensure_ascii=False).encode()+b'\n',stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=sdk_environment(),timeout=2)
    (tmp_path/'request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2));(tmp_path/'stdout.bin').write_bytes(result.stdout);(tmp_path/'stderr.bin').write_bytes(result.stderr)
    (tmp_path/'component.json').write_text(json.dumps(core.component_identity(),indent=2));assert result.returncode==0
    response=json.loads(result.stdout);assert response['status']=='ERROR' and response['reason']=='INVALID_REQUEST' and response['data']=={}


@pytest.mark.parametrize('change',['missing-types','empty-types','five-types','bad-kind','unknown-kind','extra-registry','extra-type','reserved-name','duplicate-field','empty-fields','five-fields','nested-field','wrong-tag','missing-field','extra-field','bool-int','float-int','array-bool','array-length','long-string','duplicate-order','empty-domain','seventeen-domain','extra-value','extra-domain'])
def test_native_objects_reject_untrusted_registry_and_closed_values(tmp_path,change):
    p=payload();t=p['types'];d=t['OrderState'];axis=p['domains'][0]['domain']['values'];fields=axis[0]['fields']
    if change=='missing-types':del p['types']
    elif change=='empty-types':p['types']={}
    elif change=='five-types':p['types']={'State'+str(i):deepcopy(d) for i in range(5)}
    elif change=='bad-kind':d['kind']='interface'
    elif change=='unknown-kind':p['domains'][0]['type']='OtherState'
    elif change=='extra-registry':p['other']=0
    elif change=='extra-type':d['methods']=[]
    elif change=='reserved-name':t['Int64']=t.pop('OrderState')
    elif change=='duplicate-field':d['fields'][1]=deepcopy(d['fields'][0])
    elif change=='empty-fields':d['fields']=[]
    elif change=='five-fields':d['fields'].append(dict(name='extra',type='Int64'))
    elif change=='nested-field':d['fields'][0]['type']='OrderState'
    elif change=='wrong-tag':axis[0]['$type']='OtherState'
    elif change=='missing-field':del fields['amount']
    elif change=='extra-field':fields['other']=0
    elif change=='bool-int':fields['amount']=False
    elif change=='float-int':fields['amount']=1.0
    elif change=='array-bool':fields['items']=[True]
    elif change=='array-length':fields['items']=[0]*17
    elif change=='long-string':fields['label']='中'*86
    elif change=='duplicate-order':axis.append({'fields':dict(reversed(list(fields.items()))),'$type':'OrderState'})
    elif change=='empty-domain':axis.clear()
    elif change=='seventeen-domain':p['domains'][0]['domain']['values']=[state(i) for i in range(17)]
    elif change=='extra-value':axis[0]['other']=0
    else:p['domains'][0]['domain']['other']=0
    rejection(p,tmp_path)
