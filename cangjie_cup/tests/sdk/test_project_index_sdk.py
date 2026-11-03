"""Exercise indexed cross-file declarations against the pinned native compiler."""
import asyncio

import pytest

from nexus.adapters.cangjie.report_parser import parse_test_report
from nexus.execution.runner import run_command
from nexus.projects.index import inspect_project
from tests.test_project_index import project

pytestmark=pytest.mark.sdk


def test_same_package_cross_file_build_preserves_original_case_identifiers(tmp_path):
    files=project();index=inspect_project(files);root=tmp_path/'project';root.mkdir()
    for path,data in files.items():
        dest=root/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    code,log,problem=asyncio.run(run_command(root,['cjpm','test'],private_root=tmp_path))
    assert problem is None,log
    parsed=parse_test_report(log)
    assert code!=0 and parsed.state=='FAIL',log
    assert set(parsed.case_results)=={t['id'] for t in index['test_cases']},log
    assert parsed.case_results['BillingTests.amount']=='FAIL' and parsed.case_results['BillingTests.zero']=='FAIL'
    (root/'src/fee.cj').write_bytes(files['src/fee.cj'].replace(b'x + 1',b'x'))
    code,log,problem=asyncio.run(run_command(root,['cjpm','test'],private_root=tmp_path))
    assert problem is None and code==0,log
    assert parse_test_report(log).state=='PASS',log
    for path in index['frozen_manifest']:assert (root/path).read_bytes()==files[path]
