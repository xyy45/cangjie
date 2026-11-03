"""V5 sequence source: pass actual returns forward and stop at first mismatch."""
from nexus.contracts import digest
from nexus.repair import scoped_harness,scoped_values
from nexus.repair.scoped_material import fresh
from nexus.repair.scoped_signature import validate


def render(signature,traces,*,nonce,binding,contract):
    signature=validate(signature)
    if (type(contract) is not dict or type(contract.get('version')) is not int or contract['version']!=5 or
            contract.get('signature')!=signature):raise ValueError('V5序列需要匹配的冻结契约')
    from nexus.repair import sequence_trace,scoped_trace
    plans=sequence_trace._traces(contract,traces);ids=scoped_trace.case_ids(signature,len(traces),nonce,'sequence')
    cls=ids[0].rsplit('.',2)[1];parts=scoped_harness.header(signature,binding,nonce,cls)
    text=parts['source'];kind=signature['return_type'];cj_type=parts['cj_types'].get(kind,kind)
    for case,(trace,plan,identity) in enumerate(zip(traces,plans,ids)):
        text+='@TestCase\nfunc case'+str(case)+'() {\n'
        previous=scoped_harness.input_literal(trace['initial_state'],kind,parts)
        for index,step in enumerate(plan['steps']):
            before=fresh('__nexusBefore_'+nonce,parts['reserved']);after=fresh('__nexusAfter_'+nonce,parts['reserved'])
            text+='let '+before+': '+cj_type+' = '+previous+'\n'
            args=[before if i==contract['state_index'] else scoped_harness.input_literal(value,p['type'],parts) for i,(value,p) in enumerate(zip(step['args'],signature['params']))]
            text+='let '+after+' = '+parts['target']+'('+', '.join(args)+')\n'
            text+=scoped_harness.limit_guard(kind,after,parts,nonce,identity)
            before_wire=scoped_harness.wire(kind,before,parts);after_wire=scoped_harness.wire(kind,after,parts)
            text+=parts['output']+'("'+scoped_values.SEQUENCE+nonce+'|'+identity+'|step'+str(index)+'|'+kind+'|${'+before_wire+'}|${'+after_wire+'}")\n'
            # All codecs emit ASCII with no quote/backslash/dollar; this literal
            # is bounded wire data (up to2333), not a business String value.
            expected=scoped_values.encode(step['expected_state'],kind,signature.get('types',{}))
            text+='if ("${'+after_wire+'}" != "'+expected+'") {\n'
            text+=parts['output']+'("'+scoped_values.END+nonce+'|'+identity+'|'+str(index+1)+'|MODEL_MISMATCH")\nreturn\n}\n'
            previous=after
        text+=parts['output']+'("'+scoped_values.END+nonce+'|'+identity+'|'+str(len(plan['steps']))+'|COMPLETE")\n}\n'
    return dict(source=(text+'}\n').encode(),path='src/nexus_verify_'+nonce+'/nexus_observations_test.cj',case_ids=ids,binding_hash=digest(binding))
