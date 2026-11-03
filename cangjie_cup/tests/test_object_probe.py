"""Shared probe material must see the same frozen same-package declarations."""
import pytest
from nexus.repair.exploration import ExplorationService
from tests.sdk.test_object_loop_sdk import scenario
from nexus.benchmark.corpus import CONFIG,LOCK


def material(root):
    files={'cjpm.toml':CONFIG,'cjpm.lock':LOCK,**scenario('oracle')['files']}
    for name,raw in files.items():p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    return files


def test_probe_package_headers_share_nominal_types_without_tests_or_private_rules(tmp_path):
    files=material(tmp_path);(tmp_path/'src/cases_test.cj').write_text('not production');(tmp_path/'verification').mkdir();(tmp_path/'verification/oracle.json').write_text('{}')
    package,names=ExplorationService.probe_material(tmp_path);assert package=='bench' and names==sorted(files)


@pytest.mark.parametrize('change',['package','duplicate'])
def test_probe_package_rejects_mixed_packages_or_ambiguous_types(tmp_path,change):
    files=material(tmp_path)
    if change=='package':(tmp_path/'src/order.cj').write_bytes(files['src/order.cj'].replace(b'package bench',b'package other'))
    else:(tmp_path/'src/duplicate.cj').write_bytes(files['src/state.cj'])
    with pytest.raises(ValueError):ExplorationService.probe_material(tmp_path)
