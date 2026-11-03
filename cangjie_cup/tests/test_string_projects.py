import copy
import pytest
from nexus.projects.index import inspect_project,validate_project_candidate
from tests.test_project_index import project


def string_project():
    files=project();files['src/order.cj']='package billing\npublic func total(x: String): String { fee(x) + "!" }\n'.encode()
    files['src/fee.cj']='package billing\npublic func fee(x: String): String { x }\n'.encode()
    files['src/cases_test.cj']='package billing\nimport std.unittest.*\nimport std.unittest.testmacro.*\n@Test\nclass StringTests {\n@TestCase func empty() { @Expect(total(""), "!") }\n@TestCase func escaped() { @Expect(fee("\\u{4e2d}\\n\\u{24}{text}"), "\\u{4e2d}\\n\\u{24}{text}") }\n}\n'.encode()
    return files


def test_two_file_string_project_indexes_immutable_literal_tests():
    files=string_project();before=copy.deepcopy(files);info=inspect_project(files)
    assert files==before
    assert info['test_cases'][0]['args']==[''] and info['test_cases'][0]['expected']=='!'
    assert info['test_cases'][1]['args']==['中\n${text}']
    assert info['test_cases'][1]['expected']=='中\n${text}'
    assert info['functions'][0]['return_type']=='String'
    changed={**files,'src/fee.cj':files['src/fee.cj'].replace(b'{ x }',b'{ x + "a" }')};validate_project_candidate(changed,info)
    with pytest.raises(ValueError):validate_project_candidate({**changed,'src/cases_test.cj':files['src/cases_test.cj']+b'// changed'},info)


@pytest.mark.parametrize('before,after',[(b'@Expect(total(""), "!")',b'@Expect(total(0), "!")'),(b'@Expect(total(""), "!")',b'@Expect(total(""), false)'),(b'@Expect(total(""), "!")',b'@Expect(total(""), readln())')])
def test_string_project_tests_cannot_execute_setup_or_mix_types(before,after):
    files=string_project();assert before in files['src/cases_test.cj'];files['src/cases_test.cj']=files['src/cases_test.cj'].replace(before,after)
    with pytest.raises(ValueError):inspect_project(files)
