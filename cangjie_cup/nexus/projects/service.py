"""Project import persistence shared by the existing private upload workflow."""
import json
import hashlib
import re
import shutil

from nexus.contracts import digest,source_manifest
from nexus.projects.archive import read_archive,read_entries
from nexus.projects.index import inspect_project
from nexus.store import uid


def prepare_project(service,filename,data,goal,*,actor_id,request_key,entries=None):
    if not isinstance(filename,str) or len(filename)>120 or not re.fullmatch(r'[^/\\\x00-\x1f]+',filename):raise ValueError('工程显示文件名无效')
    if not isinstance(goal,str) or not 1<=len(goal.strip())<=4000 or not actor_id:raise ValueError('请填写不超过4000字的预期行为')
    if not isinstance(request_key,str) or not 1<=len(request_key)<=64:raise ValueError('上传请求标识无效')
    files=read_entries(entries) if entries is not None else read_archive(data)
    info=inspect_project(files)
    if any(p.casefold()=='src/nexus_uploaded_test.cj' for p in files) or any(t['id'].split('.')[0] in ('UploadedTests','BoundaryTests') for t in info['test_cases']):
        raise ValueError('工程使用了系统验证保留文件或测试类名')
    source_hash=digest(info['manifest']);body_hash=digest(dict(kind='PROJECT',filename=filename,source_sha256=source_hash,goal=goal))
    with service.store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old=db.execute('SELECT id,payload FROM upload_projects WHERE actor_id=? AND request_key=?',(actor_id,request_key)).fetchone()
        if old:
            if json.loads(old[1])['body_hash']!=body_hash:raise ValueError('同一上传请求不能更换内容')
            return service.get(old[0],actor_id=actor_id)
        identity='upload_'+uid();directory=service.store.root/'uploads'/identity;original=directory/'original'
        original.mkdir(parents=True)
        try:
            for path,raw in files.items():
                target=original/path;target.parent.mkdir(exist_ok=True,parents=True);target.write_bytes(raw)
            if source_manifest(original)!=info['manifest']:raise ValueError('工程持久化摘要不一致')
            value=dict(id=identity,kind='PROJECT',status='DRAFT',version=1,filename=filename,goal=goal,
                source_sha256=source_hash,functions=info['functions'],body_hash=body_hash,original_manifest=info['manifest'],
                production_paths=info['production_paths'],project_index=info,build_root='.',original_tests=info['test_cases'])
            if info['version']==2:
                value.update(source_project_index_hash=digest(info),project_index_hash=digest(info))
            if entries is None:
                (directory/'original.zip').write_bytes(data)
                value['archive_sha256']=hashlib.sha256(data).hexdigest()
            db.execute('INSERT INTO upload_projects VALUES (?,?,?,?)',(identity,actor_id,request_key,json.dumps(value,ensure_ascii=False)))
        except Exception:
            shutil.rmtree(directory,ignore_errors=True)
            raise
    return value
