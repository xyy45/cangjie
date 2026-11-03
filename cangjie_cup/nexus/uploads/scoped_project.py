"""Source-derived scoped upload metadata; hashes alone are not authority."""
from nexus.contracts import digest
from nexus.projects.index import inspect_project
from nexus.uploads.scoped_public_tests import render


def original(value,root):
    files={name:(root/name).read_bytes() for name in value['original_manifest']}
    index=inspect_project(files)
    if (index['version']!=2 or digest(index)!=value.get('source_project_index_hash') or
            digest(value['project_index'])!=value.get('project_index_hash') or
            value['original_tests']!=index['test_cases'] or value['production_paths']!=index['production_paths']):
        raise ValueError('上传作用域元数据与原始源码不一致')
    if value['status']=='DRAFT' and index!=value['project_index']:raise ValueError('草案作用域变化')
    return files,index


def frozen(value,original_root,project):
    files,initial=original(value,original_root)
    for name,raw in files.items():
        if (project/name).read_bytes()!=raw:raise ValueError('冻结工程与原始上传文件不一致')
    if 'cjpm.lock' not in files:files['cjpm.lock']=(project/'cjpm.lock').read_bytes()
    index=inspect_project(files)
    if index!=value['project_index'] or index['graph_hash']!=initial['graph_hash']:
        raise ValueError('冻结工程作用域与源文件不一致')
    source,metadata=render(index,value['function'],value['examples'])
    if any(value.get(key)!=item for key,item in metadata.items()):raise ValueError('公开测试命名绑定变化')
    if (project/metadata['public_test_path']).read_bytes()!=source.encode():raise ValueError('冻结公开测试不符合生成依据')
    return index
