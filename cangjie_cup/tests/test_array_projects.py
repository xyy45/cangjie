import pytest
from nexus.benchmark.corpus import CONFIG,LOCK
from nexus.projects.index import inspect_project,validate_project_candidate


def array_project():
    return {'cjpm.toml':CONFIG,'cjpm.lock':LOCK,
      'src/helper.cj':b'package bench\npublic func echoValues(values: Array<Int64>): Array<Int64> { values }\n',
      'src/logic.cj':b'package bench\npublic func resultValues(values: Array<Int64>): Array<Int64> { echoValues(values) }\n',
      'src/logic_test.cj':b'''package bench
import std.unittest.*
import std.unittest.testmacro.*
@Test class ArrayCases {
 @TestCase func empty() { @Expect(resultValues([]), []) }
 @TestCase func signed() { @Expect(resultValues([-9223372036854775808, 9223372036854775807]), [-9223372036854775808, 9223372036854775807]) }
}
'''}


def test_array_project_indexes_original_tests_and_cross_file_signature():
    files=array_project();info=inspect_project(files)
    assert info['test_cases'][0]['args']==[[]] and info['test_cases'][0]['expected']==[]
    assert info['test_cases'][1]['expected']==[-(1<<63),(1<<63)-1]
    assert info['functions'][1]['calls'][0]['name']=='echoValues'
    assert 'src/logic_test.cj' in info['frozen_manifest']
    changed={**files,'src/helper.cj':files['src/helper.cj'].replace(b'{ values }',b'{ [] }')}
    validate_project_candidate(changed,info)
    with pytest.raises(ValueError):validate_project_candidate({**changed,'src/logic_test.cj':files['src/logic_test.cj'].replace(b'[]',b'[0]')},info)

@pytest.mark.parametrize('literal',[b'[true]',b'[1.5]',b'[[1]]',b'[9223372036854775808]',b'['+b','.join([b'0']*17)+b']'])
def test_project_test_array_literal_must_be_strict_bounded_int64(literal):
    files=array_project();files['src/logic_test.cj']=files['src/logic_test.cj'].replace(b'[]',literal)
    with pytest.raises(ValueError):inspect_project(files)
