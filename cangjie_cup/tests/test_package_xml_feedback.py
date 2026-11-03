"""XML facts can be public while the enclosing raw SDK log remains withheld."""
import pytest
from nexus.contracts import CandidateRecord,CheckResult
from nexus.repair.feedback import build_feedback
from tests.test_package_public_fields import fixture,api


def test_scoped_public_xml_facts_survive_withheld_raw_diagnostics(tmp_path):
    value,index,files,check,parsed=fixture(tmp_path);facts=api().resolve(check,value,index,files,parsed)['failures']
    public=[f for f in facts if f['visibility']=='PUBLIC']
    candidate=CandidateRecord(id='c',task_id='t',baseline_hash='a'*64,
        edits=[dict(path='src/step.cj',before_hash='a'*64,content=files['src/step.cj'].decode())],
        tree_hash='b'*64,diff_ref='records/diff',attempt=1)
    check.subject_id='c';check.tree_hash=candidate.tree_hash;check.diagnostics='PRIVATE ORIGINAL ASSERTIONS MUST STAY WITHHELD'
    build=CheckResult(kind='build',state='PASS',subject_id='c',tree_hash=candidate.tree_hash)
    result=build_feedback(candidate,dict(tree_hash=candidate.tree_hash,diff='+ explicit fixture'),build.model_dump(),check.model_dump(),
        remaining_budget=2,requirement_refs=['REQ-UPLOAD'],diagnostics_public=False,public_failure_cases=public)
    assert result.failure_cases==public and all(s['text']=='' and s['visibility']=='WITHHELD' for s in result.diagnostic_snippets)
    with pytest.raises(ValueError):build_feedback(candidate,dict(tree_hash=candidate.tree_hash,diff='fixture'),build.model_dump(),check.model_dump(),
        remaining_budget=2,requirement_refs=['REQ-UPLOAD'],diagnostics_public=False,public_failure_cases=facts)
