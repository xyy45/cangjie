"""Bounded model-visible interfaces; no nonselected body or original test source."""
from copy import deepcopy
from nexus.contracts import digest,file_hash
from nexus.projects.index import inspect_project
from nexus.execution.workspace import WorkspaceStore
from nexus.uploads.service import UploadService
from nexus.repair.scoped_signature import validate


def material(store,task,value):
    uploads=UploadService(store);uploads.profile(value['id'])
    baseline=WorkspaceStore(store.root).verify_baseline(task.baseline_id)
    index=inspect_project({p:(baseline/p).read_bytes() for p in value['project_index']['manifest']})
    if digest(index)!=value['project_index_hash']:raise ValueError('Scoped model context source changed')
    signature=validate(next(f for f in index['functions'] if f['name']==value['function']))
    imports={}
    for declaration in index['dependency_graph']['imports']:
        if declaration['path'].endswith('_test.cj'):continue
        imports.setdefault(declaration['path'],[]).append(deepcopy(declaration))
    production_graph=dict(packages=sorted(p for p,info in index['packages'].items() if info['production_paths']),
        production_edges=deepcopy(index['dependency_graph']['production_edges']),imports=imports)
    heads=[{k:deepcopy(f[k]) for k in ('name','params','return_type','path','public','package')}
        for f in index['functions'] if f['public'] or f['path'] in task.allowed_paths]
    paths=set(task.allowed_paths)|{value['public_test_path']}
    return baseline,dict(version=1,signature=signature,graph_hash=index['graph_hash'],origin='SOURCE_DECLARATIONS',
        compiler_verification='BOUND_CHECK_RESULT_REQUIRED',production_graph=production_graph,
        readonly_dependencies=True,interfaces=heads,types=deepcopy(index.get('types',{}))),paths


def prepare(store,task,value,context):
    baseline,metadata,paths=material(store,task,value)
    if set(context['files'])!=paths:raise ValueError('Scoped model source visibility differs from frozen scope')
    for path,item in context['files'].items():
        source=(baseline/path).read_bytes().decode('utf-8')
        if item['content']!=source or item['file_hash']!=file_hash(source):raise ValueError('Scoped model source binding changed')
    context['scoped_project']=metadata
    constraints=context['upload_constraints']
    constraints.update(readonly_dependencies=True,preserve_package_and_imports=True,
        allowed=constraints['allowed']+'；通过冻结逐文件导入与公开接口调用跨包函数／方法',
        forbidden=constraints['forbidden'].replace('导入','修改冻结导入',1),
        source_notice='冻结跨包工程；仅allowed_paths内正文可编辑，其他依赖仅提供公开接口和源码声明图',
        analysis_scope='PER_FILE_WITH_SOURCE_SCOPES')
    # Original SDK diagnostics can contain readonly code or original assertions.
    # Actual independent feedback is separately reconstructed from bound evidence.
    context['diagnostics']={kind:{k:deepcopy(v) for k,v in context['diagnostics'].get(kind,{}).items()
        if k in ('state','kind','exit_code','counts')} for kind in ('build','test')}


def enforce(store,task,value,context):
    baseline,metadata,paths=material(store,task,value)
    if context.get('scoped_project')!=metadata or set(context['files'])!=paths:
        raise ValueError('Scoped model context visibility or interfaces changed')
    for path,item in context['files'].items():
        text=(baseline/path).read_bytes().decode('utf-8')
        if item['content']!=text or item['file_hash']!=file_hash(text):raise ValueError('Scoped model source changed before send')
