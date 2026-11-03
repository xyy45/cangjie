"""Real V5 object-state/Array-context steps and runtime UNKNOWN controls."""
import asyncio,hashlib,json
from copy import deepcopy
import pytest

from nexus.adapters.cangjie.sdk import SDK
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.contracts import source_manifest
from nexus.execution.runner import run_command
from nexus.repair import sequences,sequence_trace,scoped_trace
from nexus.repair.scoped_material import material
from tests.test_object_contracts import sequence_raw,state
from tests.test_package_contracts import canonical
from tests.test_package_material import selected,NONCE
from tests.sdk.test_objects_sdk import declaration

pytestmark=pytest.mark.sdk


@pytest.mark.parametrize('name',['OrderState','case0'])
@pytest.mark.parametrize('control',['bug','fixed','overflow'])
def test_v5_actual_object_sequence_chains_stops_and_never_invents_calls(tmp_path,name,control):
    declaration_source=declaration('class',name)
    expression='state.amount + 1' if control=='bug' else '1 - state.amount' if control=='fixed' else 'state.amount + mode'
    source='package bench.ops\nimport bench.model.'+name+' as Model\nfunc advance(mode: Int64, state: Model, label: Array<Int64>): Model {\nlet next = '+expression+' + label.size * 0\nModel(next, state.label, state.active, state.items)\n}\n'
    files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,'src/anchor.cj':b'package bench\npublic func anchor(x: Int64): Int64 { x }',
        'src/model/state.cj':('package bench.model\n'+declaration_source).encode(),'src/ops/advance.cj':source.encode()}
    signature=selected(files,'bench.ops.advance');raw,_=sequence_raw();raw=canonical(raw)
    def renamed(value):
        if type(value) is list:return [renamed(v) for v in value]
        if type(value) is dict:return {k:renamed(v) for k,v in value.items()}
        return 'bench.model.'+name if value=='bench.model.OrderState' else value
    raw=renamed(raw);raw.update(version=5,function=signature['name'])
    raw['domains']['label']={'values':[[],[1,2]]}
    if control=='overflow':
        raw['domains']['mode']={'min':(1<<63)-1,'max':(1<<63)-1,'points':[]}
        raw['operations'][0]['args'][0]=(1<<63)-1
        raw['initial_states']=[renamed(canonical(state(1)))]
    contract=sequences.validate_contract(raw,signature,[])
    trace=dict(initial_state=deepcopy(raw['initial_states'][0]),context=[[1,2]],steps=[dict(operation_id='OP-FLIP',args=[raw['operations'][0]['args'][0],[1,2]]) for _ in range(3)])
    before=deepcopy(files);derived=material(files,signature,NONCE);binding=derived['binding']
    rendered=scoped_trace.render(signature,[trace],nonce=NONCE,mode='sequence',binding=binding,contract=contract)
    assert sequence_trace.harness(contract,[trace],binding['package'],NONCE,binding=binding)==rendered['source']
    root=tmp_path/'project';root.mkdir()
    for path,blob in {**derived['files'],rendered['path']:rendered['source']}.items():
        dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(blob)
    manifest=source_manifest(root);argv=[]
    code,log,problem=asyncio.run(run_command(root,['cjpm','test'],private_root=tmp_path,test_output='all',execution_argv=argv))
    (tmp_path/'sdk.log').write_text(log)
    result=sequence_trace.interpret(contract,[trace],NONCE,log,code,problem)
    (tmp_path/'input.json').write_text(json.dumps(dict(control=control,signature=signature,contract=contract,traces=[trace],binding=binding,
        source_before=manifest,original_manifest=derived['original_manifest']),ensure_ascii=True,indent=2))
    (tmp_path/'result.json').write_text(json.dumps(dict(result=result,exit_code=code,problem=problem,execution_argv=argv,source_after=source_manifest(root),
        sdk_tools={p:hashlib.sha256((SDK/p).read_bytes()).hexdigest() for p in ('bin/cjc','bin/cjc-frontend','tools/bin/cjpm')},
        test_binary_sha256={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'target/release/unittest_bin').glob('*') if p.is_file()}),ensure_ascii=True,indent=2))
    assert problem is None and files==before and manifest==source_manifest(root),log
    assert argv==[['cjpm','test','--no-run'],['cjpm','test','--skip-build','--show-all-output']],log
    assert result['state']=={'bug':'FAIL','fixed':'PASS','overflow':'UNKNOWN'}[control],(result,log)
    if control=='overflow':
        assert code!=0 and result['observations']==[] and 'overflow' in log.lower(),log
    else:
        assert code==0 and result['observed_calls']==(2 if control=='bug' else 3),(result,log)
        steps=result['observations'][0]['steps']
        assert steps[1]['before_state']==steps[0]['actual_return']
        if control=='bug':
            assert result['unexecuted_calls']==1 and result['failures'][0]['step_index']==1
            assert result['failures'][0]['actual_return']['fields']['amount']==2
        else:assert [s['actual_return']['fields']['amount'] for s in steps]==[1,0,1]
