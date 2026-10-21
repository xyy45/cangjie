"""Recover real text tables, without replacing the engine verdict or raw bytes."""
import hashlib
import io
import json
from pathlib import Path
import zipfile
import pytest

from nexus.analysis import samples
from nexus.analysis.normalize import validate_source
from nexus.analysis.service import AnalysisService
from tests.analysis.test_service import FakeClient, SOURCE


def test_existing_real_calls_snapshot_recovers_ten_variables_without_changing_verdict():
    report=samples.snapshot('calls')
    assert report['status']=='PARTIAL'
    assert next(o for o in report['observations'] if o['tool']=='sympas_slice')['status']=='FAILED'
    derived=report.get('derived_slice')
    assert derived is not None, 'Missing local derivation of the saved tool text table'
    assert derived['status']=='RECOVERED' and derived['origin']=='TOOL_LOG'
    assert len(derived['slices'])==10
    assert derived['slices']['index@aggregate']==[14,15,17,21,23,25,26,27]
    assert derived['source_sha256']==report['source']['source_sha256']


def test_loop_recovers_four_but_native_json_still_wins_for_sum3():
    assert len(samples.snapshot('loop')['derived_slice']['slices'])==4
    assert 'derived_slice' not in samples.snapshot('sum3')


def response(log):
    return {'status':'success','data':{'backward_slices':{}},'engine_log':'Found 0 source files',
        'raw_output':log,'engine_warnings':['SIL syntax error: unexpected token )']}


def table(rows):
    return 'Backward Static SliceTable:\n\t#Insts_sliced = 2\n\n Variable      SrcLineNumbers\n--------------------\n'+rows+'\n\nTextual SIL exported: source.sil\n'


class TextClient(FakeClient):
    log=table('result@add {"add.cj: [2,3]"}')
    def analyze(self,tool,args):
        reply=super().analyze(tool,args)
        if tool=='sympas_slice':reply['response']=response(self.log)
        return reply


def run(tmp_path,log):
    class Client(TextClient):pass
    Client.log=log
    service=AnalysisService(tmp_path,client_factory=Client)
    job=service.create(validate_source('add.cj',SOURCE),actor_id='actor',request_key='first',origin='UPLOAD')
    service.run(job['id'])
    return service,job['id']


def test_saved_upload_recovery_is_read_only_and_download_preserves_originals(tmp_path):
    service,identity=run(tmp_path,TextClient.log);directory=service.directory(identity)
    before={p.relative_to(directory).as_posix():p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    report=service.get(identity,actor_id='actor')
    assert report.get('derived_slice',{}).get('slices')=={'result@add':[2,3]}
    assert report['derived_slice']['raw_sha256']==hashlib.sha256(before['observations/sympas_slice.json']).hexdigest()
    with zipfile.ZipFile(service.export(identity,actor_id='actor')) as z:
        assert z.read('result.json')==before['result.json']
        assert z.read('observations/sympas_slice.json')==before['observations/sympas_slice.json']
        assert json.loads(z.read('derived-slices.json'))==report['derived_slice']
        manifest=json.loads(z.read('manifest.json'))
        assert hashlib.sha256(z.read('derived-slices.json')).hexdigest()==manifest['files']['derived-slices.json']
    assert before=={p.relative_to(directory).as_posix():p.read_bytes() for p in directory.rglob('*') if p.is_file()}


@pytest.mark.parametrize('rows',[
    'value {"other.cj: [2]"}', 'value {"add.cj: [0]"}', 'value {"add.cj: [5]"}',
    'value {"add.cj: [true]"}', 'value {"add.cj: [2,]"}', 'value {"add.cj: [-1]"}',
    'value {"add.cj: [2]"}\nvalue {"add.cj: [3]"}',
    'value {"add.cj: [2]"}\nbroken row',
])
def test_any_malformed_row_rejects_entire_recovery(tmp_path,rows):
    service,identity=run(tmp_path,table(rows))
    result=service.get(identity,actor_id='actor')
    assert result.get('derived_slice',{}).get('status')=='REJECTED'
    assert not result['derived_slice'].get('slices')


def test_snapshot_download_adds_a_separate_manifest_preserving_original_manifest():
    root=samples.ROOT/'snapshots/calls'
    with zipfile.ZipFile(samples.snapshot_archive('calls')) as z:
        assert z.read('manifest.json')==(root/'manifest.json').read_bytes()
        derived=json.loads(z.read('derived-slices.json'));assert len(derived['slices'])==10
        manifest=json.loads(z.read('derived-manifest.json'))
        assert all(hashlib.sha256(z.read(name)).hexdigest()==sha for name,sha in manifest['files'].items())


def test_derivation_rejects_a_request_bound_to_other_source_even_with_a_matching_record_hash(tmp_path):
    from nexus.analysis.recovery import recover
    service,identity=run(tmp_path,TextClient.log);report=service.get(identity,actor_id='actor')
    original=next(o for o in report['observations'] if o['tool']=='sympas_slice')
    raw=json.loads((service.directory(identity)/original['raw_ref']).read_bytes())
    raw['input']['code']='different source'
    changed=json.dumps(raw).encode();observed={**original,'raw_sha256':hashlib.sha256(changed).hexdigest()}
    with pytest.raises(ValueError):recover(changed,report['source'],observed)


@pytest.mark.parametrize('log',[
    table('value {"add.cj: [2]"}')+table('other {"add.cj: [3]"}'),
    table('value {"add.cj: [2]"}').replace('Variable      SrcLineNumbers','unrecognized header'),
    table('value {"add.cj: ['+','.join(['1']*1001)+']"}'),
    table('value {"add.cj: [100000000000000000000000]"}'),
])
def test_ambiguous_tables_unknown_headers_and_oversized_values_are_rejected(tmp_path,log):
    service,identity=run(tmp_path,log)
    assert service.get(identity,actor_id='actor')['derived_slice']['status']=='REJECTED'


def test_public_sample_route_exposes_derived_data_without_changing_original_observation():
    from tempfile import TemporaryDirectory
    from nexus.demo.app import create_demo_app
    with TemporaryDirectory() as root:
        app=create_demo_app(root,provider='rule');app.config['TESTING']=True
        with app.test_client() as client:
            report=client.get('/analysis/samples/calls').json['snapshot']
            assert report['derived_slice']['slices']['index@aggregate']==[14,15,17,21,23,25,26,27]
            assert next(o for o in report['observations'] if o['tool']=='sympas_slice')['status']=='FAILED'
