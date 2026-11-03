import io,importlib,importlib.util,stat,zipfile
import pytest


def reader():
    assert importlib.util.find_spec('nexus.projects.archive') is not None,'project archive reader missing'
    return importlib.import_module('nexus.projects.archive')


def archive(entries):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as z:
        for name,data in entries:
            z.writestr(name,data)
    return stream.getvalue()


def project(prefix=''):
    return {prefix+'cjpm.toml':b'[package]\nname="billing"\n',prefix+'src/order.cj':b'package billing\npublic func total(x: Int64): Int64 { fee(x) }\n',prefix+'src/fee.cj':b'package billing\npublic func fee(x: Int64): Int64 { x + 1 }\n',prefix+'src/cases_test.cj':b'// frozen test bytes\n'}


def test_archive_and_directory_entries_preserve_exact_project_bytes():
    m=reader();files=project('billing/')
    assert m.read_archive(archive(files.items()))==project()
    assert m.read_entries(files)==project()


@pytest.mark.parametrize('name',['../escape.cj','/tmp/escape.cj','C:/escape.cj','src/../escape.cj','src\\escape.cj','src/.hidden.cj','build.cj','src/build.cj','.env'])
def test_traversal_hidden_or_executable_material_is_rejected(name):
    m=reader()
    with pytest.raises(ValueError):m.read_archive(archive([*project().items(),(name,b'bad')]))


def test_duplicates_case_and_unicode_normalization_collisions_are_rejected():
    m=reader()
    for extras in [[('src/fee.cj',b'again')],[('src/FEE.cj',b'again')],[('src/é.cj',b'a'),('src/e\u0301.cj',b'b')]]:
        with pytest.raises(ValueError):
            if extras[0][0]=='src/fee.cj':
                with pytest.warns(UserWarning,match='Duplicate name'):payload=archive([*project().items(),*extras])
            else:payload=archive([*project().items(),*extras])
            m.read_archive(payload)


def test_links_bombs_and_ambiguous_roots_are_rejected_without_extraction(tmp_path):
    m=reader();stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        for n,v in project().items():z.writestr(n,v)
        info=zipfile.ZipInfo('src/link.cj');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'/etc/passwd')
    with pytest.raises(ValueError):m.read_archive(stream.getvalue())
    with pytest.raises(ValueError):m.read_archive(archive([*project().items(),('src/large.cj',b'x'*(128*1024+1))]))
    with pytest.raises(ValueError):m.read_archive(archive([*project('one/').items(),*project('two/').items()]))
    with pytest.raises(ValueError):m.read_archive(b'not a zip')
    assert list(tmp_path.iterdir())==[]

@pytest.mark.parametrize('extras',[
    [('src/Group/one.cj',b'a'),('src/group/two.cj',b'b')],
    [('src/fee.cj/nested.cj',b'a')],
])
def test_parent_directory_aliases_and_file_directory_conflicts_are_rejected(extras):
    with pytest.raises(ValueError):reader().read_archive(archive([*project().items(),*extras]))


def test_archive_entry_file_count_and_total_size_limits():
    m=reader()
    with pytest.raises(ValueError):m.read_archive(b'x'*(2*1024*1024+1))
    with pytest.raises(ValueError):m.read_entries({**project(),**{f'note{i}.md':b'x' for i in range(97)}})
    with pytest.raises(ValueError):m.read_archive(archive([*project().items(),*[(f'note{i}.md',b'x'*(128*1024)) for i in range(17)]]))


def test_non_utf8_or_oversized_cangjie_sources_are_not_imported():
    m=reader()
    for data in [b'\xff',b'x'*65537,b'x\0',b'//\n'*1001]:
        with pytest.raises(ValueError):m.read_entries({**project(),'src/order.cj':data})
