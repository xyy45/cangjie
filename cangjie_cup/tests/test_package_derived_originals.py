"""Derived bridge originals are recorded even before an SDK scan can complete."""
import asyncio,hashlib,time
from types import SimpleNamespace
import pytest
from nexus.contracts import source_manifest
from nexus.repair import scoped_probe,scoped_batches
from tests.test_package_probe_material import prepared,TOKEN


@pytest.mark.parametrize('mode',['oracle','single','relation','sequence'])
def test_derived_source_original_is_immutable_and_not_only_a_live_probe_file(tmp_path,monkeypatch,mode):
    files,signature,contract,items=prepared(mode)
    derived=scoped_probe.prepare(files,signature,TOKEN,mode,items,contract=contract)
    candidate=tmp_path/'candidate';candidate.mkdir();(tmp_path/'records').mkdir()
    for path,raw in files.items():
        target=candidate/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    events=[];store=SimpleNamespace(root=tmp_path,append_record=lambda task,kind,data:events.append(data))
    def write(raw,suffix):
        from nexus.store import uid
        ref='records/'+uid()+suffix;(tmp_path/ref).write_bytes(raw)
        return ref,hashlib.sha256(raw).hexdigest()
    def read(ref,expected):
        raw=(tmp_path/ref).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Explicit original hash mismatch')
        return raw
    service=SimpleNamespace(store=store,write_record=write,read_record=read,
        string_interpret=lambda *_:dict(state='UNKNOWN',failures=[],counts={}),
        interpret_batch=lambda *_:dict(state='UNKNOWN',failures=[],counts={}))
    monkeypatch.setattr(scoped_batches,'materials',lambda *_:derived)
    async def stop_scan(project,index,**kwargs):
        return dict(state='UNKNOWN',diagnostics='EXPLICIT STOP BEFORE SDK',source_before=source_manifest(project),
            source_after=source_manifest(project),tool_before={},tool_after={},scans=[])
    monkeypatch.setattr(scoped_batches.package_validation,'scan',stop_scan)
    report=dict(candidate_id='fixture-candidate',binding=dict(task_id='fixture-task'),batches=[])
    asyncio.run(scoped_batches.batch(service,candidate,contract,items,int(time.time()*1000)+60000,'search',report,mode=mode,token=TOKEN,
        required_ids=['FIXTURE'] if mode in ('single','relation') else None))
    row=report['batches'][0];ref=row['scoped']['derived_source_ref']
    assert read(ref,row['scoped']['derived_source_sha256'])==derived['files'][derived['binding']['bridge_path']]
    assert events[0]['derived_source_ref']==ref
    scoped_batches.verify(service,candidate,contract,row,'fixture-candidate',mode=mode,items=items,token=TOKEN)
    (tmp_path/ref).write_bytes(b'tampered source original')
    with pytest.raises(ValueError):scoped_batches.verify(service,candidate,contract,row,'fixture-candidate',mode=mode,items=items,token=TOKEN)
