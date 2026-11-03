"""Actual fixed SDK with scoped source; report completeness lands in Task4."""
import asyncio
import hashlib
import json
import re

import pytest

from nexus.contracts import source_manifest
from nexus.adapters.cangjie.report_parser import ANSI
from nexus.adapters.cangjie.sdk import SDK
from nexus.execution.runner import run_command
from nexus.projects.index import inspect_project
from tests.test_package_index import project

pytestmark=pytest.mark.sdk


@pytest.mark.parametrize('control',['valid','private','cycle'])
def test_scoped_index_matches_real_sdk_visibility_and_nominal_bindings(tmp_path,control):
    files=project()
    if control=='private':
        files['src/sale/state.cj']=files['src/sale/state.cj'].replace(b'public func fee',b'func fee')
    elif control=='cycle':
        files['src/refund/state.cj']=files['src/refund/state.cj'].replace(b'package bench.refund',b'package bench.refund\nimport bench.sale.fee')
        files['src/sale/state.cj']=files['src/sale/state.cj'].replace(b'package bench.sale',b'package bench.sale\nimport bench.refund.State as RefundState')
    if control=='valid':
        index=inspect_project(files);assert index['version']==2 and len(index['test_cases'])==3
        (tmp_path/'index.json').write_text(json.dumps(index,ensure_ascii=False,indent=2))
    else:
        with pytest.raises(ValueError):inspect_project(files)
    root=tmp_path/'project';root.mkdir()
    for path,raw in files.items():
        target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    before=source_manifest(root);argv=[]
    code,log,problem=asyncio.run(run_command(root,['cjpm','test'],private_root=tmp_path,
        test_output='all',execution_argv=argv))
    (tmp_path/'sdk.log').write_text(log)
    (tmp_path/'sdk-result.json').write_text(json.dumps(dict(control=control,exit_code=code,problem=problem,
        execution_argv=argv,source_before=before,source_after=source_manifest(root),
        test_source_sha256=hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
        sdk_tools={n:hashlib.sha256((SDK/n).read_bytes()).hexdigest() for n in ('bin/cjc','bin/cjc-frontend','tools/bin/cjpm')},
        compiled_test_bytes={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (root/'target/release/unittest_bin').glob('*') if p.is_file()}),indent=2))
    assert problem is None and before==source_manifest(root),log
    if control=='valid':
        assert code==0,log
        # This confirms compilation/execution only; exact per-package XML comes later.
        clean=ANSI.sub('',log)
        assert set(re.findall(r'(?m)^TP: ([A-Za-z_][A-Za-z0-9_.]*),',clean))=={'bench','bench.sale','bench.refund'},log
        assert len(re.findall(r'(?m)^\s+TCS: Cases,',clean))==3,log
    else:
        assert code!=0,log
        assert ('not accessible' in log if control=='private' else 'cyclic' in log.lower()),log
