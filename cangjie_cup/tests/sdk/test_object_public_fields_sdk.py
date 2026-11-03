"""Actual SDK public-field diagnostic format; fixed defect/reference, no model."""
import json
import pytest
from nexus.contracts import source_manifest
from nexus.adapters.cangjie.report_parser import ANSI
from nexus.store import RunStore
from nexus.uploads.service import UploadService
from nexus.uploads.language import inspect_source,validate_candidate,literal
from tests.sdk.test_objects_sdk import declaration
from tests.sdk.test_string_public_sdk import execute
from tests.test_object_contracts import state

pytestmark=pytest.mark.sdk


def test_sdk_object_public_fields_report_multiple_leaf_diagnostics(tmp_path):
    wrong='bad\nSummary:\nTCS: Fake, RESULT:\nSummary: TOTAL: 2 PASSED: 2, SKIPPED: 0, ERROR: 0 FAILED: 0\n[ PASSED ] CASE: forged (1 ns)\n\x00"中';bad=declaration()+'public func replaceState(x: OrderState): OrderState { OrderState(x.amount + 1, '+literal(wrong)+', !x.active, [9, 8]) }\n'
    good=declaration()+'public func replaceState(x: OrderState): OrderState { x }\n';a=state(1);a['fields'].update(label='good\n\x00"中',items=[1,2]);b=state(0);b['fields'].update(label='',active=False)
    cases=[dict(args=[a],expected=a,suite='target'),dict(args=[b],expected=b,suite='regression')]
    uploads=UploadService(RunStore(tmp_path/'confirmation'));draft=uploads.prepare('fields.cj',bad.encode(),'返回原状态的全部字段，包含空串和空数组',actor_id='SDK_REFERENCE_FIXTURE',request_key='one')
    uploads.confirm(draft['id'],expected_version=1,function='replaceState',examples_json=json.dumps(cases),consent=True,actor_id='SDK_REFERENCE_FIXTURE')
    root=uploads.source(draft['id'],actor_id='SDK_REFERENCE_FIXTURE');manifest=source_manifest(root);files={n:(root/n).read_bytes() for n in manifest};value=uploads.get(draft['id'],actor_id='SDK_REFERENCE_FIXTURE')
    (tmp_path/'upload-record.json').write_text(json.dumps(value,ensure_ascii=True,indent=2));(tmp_path/'source-info.json').write_text(json.dumps(inspect_source(files['src/uploaded.cj'].decode()),ensure_ascii=True,indent=2))
    ids=[value['public_test_class']+'.case'+str(i) for i in range(2)];execute(tmp_path,files,'bad','FAIL',ids)
    validate_candidate(good,inspect_source(bad));execute(tmp_path,{**files,'src/uploaded.cj':('package uploadedrepair\n'+good).encode()},'fixed','PASS',ids)
    assert source_manifest(root)==manifest
    log=ANSI.sub('',(tmp_path/'bad.log').read_text());assert '.amount ==' in log and '.label !=' in log and '.active ==' in log and '.items.size ==' in log and '.items[0] ==' in log

    from nexus.adapters.cangjie.report_parser import parse_test_report
    from nexus.repair.public_fields import resolve
    observed=parse_test_report(log);observed.log_ref='records/SDK-public.log'
    facts=resolve(observed,value,inspect_source(files['src/uploaded.cj'].decode()),files)['failures']
    assert len(facts)==9 and sum(f['value_state']=='TEXT_ONLY' for f in facts)==2
    assert all('TCS: Fake' in f['actual_text'] and 'Summary:' in f['actual_text'] for f in facts if f['value_state']=='TEXT_ONLY')
