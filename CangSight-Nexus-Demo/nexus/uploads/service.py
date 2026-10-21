"""Immutable source + user-confirmed examples, owned by one browser session."""
import json
from pathlib import Path
import re
import shutil
from nexus.analysis.normalize import validate_source
from nexus.contracts import digest,source_manifest,file_hash
from nexus.store import uid
from nexus.uploads.language import inspect_source,validate_examples,validate_candidate,literal


class UploadService:
    def __init__(self,store):
        self.store=store
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS upload_projects(id TEXT PRIMARY KEY,actor_id TEXT NOT NULL,request_key TEXT NOT NULL,payload TEXT NOT NULL,UNIQUE(actor_id,request_key))')
    def _read(self,identity,actor_id=None):
        if not isinstance(identity,str) or not re.fullmatch(r'upload_[a-f0-9]{32}',identity):raise LookupError('上传不存在')
        with self.store.connect() as db:row=db.execute('SELECT actor_id,payload FROM upload_projects WHERE id=?',(identity,)).fetchone()
        if not row or actor_id is not None and row[0]!=actor_id:raise LookupError('上传不存在')
        value=json.loads(row[1]);path=self.store.root/'uploads'/identity/'source.cj'
        if path.is_symlink() or file_hash(path.read_bytes().decode('utf-8'))!=value['source_sha256']:
            raise ValueError('上传原始源码摘要变化')
        return value
    def get(self,identity,*,actor_id):
        if not isinstance(actor_id,str) or not actor_id:raise LookupError('上传不存在')
        return self._read(identity,actor_id)
    def project_access(self,identity,actor_id):
        if isinstance(identity,str) and identity.startswith('upload_'):self.get(identity,actor_id=actor_id)
    def task_access(self,identity,actor_id):
        from nexus.requirements.service import RequirementService
        task=self.store.get_task(identity)
        if task.schema_version==2:
            spec=RequirementService(self.store).get_spec(task.spec_id)
            self.project_access(spec.project_id,actor_id)
    def list(self,*,actor_id):
        with self.store.connect() as db:rows=db.execute('SELECT id FROM upload_projects WHERE actor_id=? ORDER BY rowid DESC LIMIT 20',(actor_id,)).fetchall()
        return [self.get(row[0],actor_id=actor_id) for row in rows]
    def prepare(self,filename,data,goal,*,actor_id,request_key):
        source=validate_source(filename,data);info=inspect_source(source['code'])
        if not isinstance(goal,str) or not 1<=len(goal.strip())<=4000 or not actor_id:
            raise ValueError('请填写不超过4000字的预期行为')
        if not isinstance(request_key,str) or not 1<=len(request_key)<=64:raise ValueError('上传请求标识无效')
        body_hash=digest(dict(filename=filename,source_sha256=source['source_sha256'],goal=goal))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT id,payload FROM upload_projects WHERE actor_id=? AND request_key=?',(actor_id,request_key)).fetchone()
            if old:
                if json.loads(old[1])['body_hash']!=body_hash:raise ValueError('同一上传请求不能更换内容')
                return self.get(old[0],actor_id=actor_id)
            identity='upload_'+uid();directory=self.store.root/'uploads'/identity
            directory.mkdir(parents=True)
            (directory/'source.cj').write_bytes(data)
            value=dict(id=identity,status='DRAFT',version=1,filename=filename,goal=goal,
                source_sha256=source['source_sha256'],functions=info['functions'],body_hash=body_hash)
            db.execute('INSERT INTO upload_projects VALUES (?,?,?,?)',(identity,actor_id,request_key,json.dumps(value,ensure_ascii=False)))
        return value
    def confirm(self,identity,*,expected_version,function,examples_json,consent,actor_id):
        value=self.get(identity,actor_id=actor_id)
        if type(expected_version) is not int or expected_version!=1 or consent is not True:
            raise ValueError('请确认当前版本、公开测试示例及远端发送许可')
        if not isinstance(examples_json,str) or len(examples_json.encode())>8192:raise ValueError('示例JSON最多8KiB')
        try:examples=json.loads(examples_json)
        except (ValueError,RecursionError):raise ValueError('示例JSON格式无效') from None
        original=self.store.root/'uploads'/identity/'source.cj';info=inspect_source(original.read_bytes().decode())
        examples=validate_examples(info,function,examples)
        confirmation_hash=digest(dict(function=function,examples=examples,consent=True))
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=json.loads(db.execute('SELECT payload FROM upload_projects WHERE id=? AND actor_id=?',(identity,actor_id)).fetchone()[0])
            if current['status']=='CONFIRMED':
                if current['confirmation_hash']!=confirmation_hash:raise ValueError('示例已冻结；修改需重新上传')
                self.profile(identity)
                return current
            project=original.parent/'project';staging=original.parent/'.project-staging'
            if staging.exists():shutil.rmtree(staging)
            staging.mkdir();(staging/'src').mkdir()
            try:
                package=info['package'] or 'uploadedrepair'
                prefix=b'' if info['package'] else b'package uploadedrepair\n'
                (staging/'src/uploaded.cj').write_bytes(prefix+original.read_bytes())
                (staging/'cjpm.toml').write_text('[package]\n  cjc-version = "1.0.5"\n  name = "'+package+'"\n  version = "1.0.0"\n  output-type = "static"\n\n[dependencies]\n')
                (staging/'cjpm.lock').write_text('version = 0\n\n[requires]\n')
                header='package '+package+'\n\n'
                tests=header+'import std.unittest.*\nimport std.unittest.testmacro.*\n\n@Test\nclass UploadedTests {\n'
                for index,e in enumerate(examples):
                    args=', '.join(literal(v) for v in e['args'])
                    tests+='    @TestCase\n    func case'+str(index)+'() {\n        @Expect('+function+'('+args+'), '+literal(e['expected'])+')\n    }\n'
                (staging/'src/cases_test.cj').write_text(tests+'}\n')
                if project.exists():raise ValueError('工程已有未核实内容，请重新上传')
                staging.rename(project)
                value.update(status='CONFIRMED',function=function,examples=examples,examples_json=examples_json,
                    confirmation_hash=confirmation_hash,source_prefix=prefix.decode(),manifest=source_manifest(project))
                db.execute('UPDATE upload_projects SET payload=? WHERE id=?',(json.dumps(value,ensure_ascii=False),identity))
            except Exception:
                shutil.rmtree(staging,ignore_errors=True)
                raise
        return value
    def profile(self,identity):
        value=self._read(identity)
        if value['status']!='CONFIRMED':raise ValueError('上传示例尚未确认')
        project=self.store.root/'uploads'/identity/'project'
        if project.is_symlink() or source_manifest(project)!=value['manifest']:raise ValueError('冻结上传工程摘要变化')
        suites={name:['UploadedTests.case'+str(i) for i,e in enumerate(value['examples']) if e['suite']==name] for name in ('target','regression')}
        return dict(project_id=identity,source=str(project),goal=value['goal'],allowed_paths=['src/uploaded.cj'],
            requirements=[dict(id='REQ-UPLOAD',text=value['goal'],observable_behavior='满足用户确认的'+str(len(value['examples']))+'组输入和预期输出',
                preserves=['通过已确认的regression示例'],uncovered=['不证明示例之外的任意输入语义'])],
            required_suites=['target','regression'],suite_tests=suites,requirement_test_map={'REQ-UPLOAD':['target','regression']},
            context_visibility={'src/uploaded.cj':'PRODUCTION','src/cases_test.cj':'PUBLIC_TEST'},
            limitations=['用户确认的公开示例','仅支持Int64/Bool普通函数子集','不证明未覆盖输入的语义正确性'])
    def source(self,identity,*,actor_id):
        self.get(identity,actor_id=actor_id)
        return Path(self.profile(identity)['source'])
    def validate_subject(self,task,path):
        from nexus.requirements.service import RequirementService
        spec=RequirementService(self.store).get_spec(task.spec_id)
        if not spec.project_id.startswith('upload_'):return
        value=self._read(spec.project_id);self.profile(spec.project_id)
        baseline=inspect_source((self.store.root/'uploads'/spec.project_id/'project/src/uploaded.cj').read_bytes().decode())
        validate_candidate((path/'src/uploaded.cj').read_bytes().decode(),baseline)
        current=source_manifest(path)
        if set(current)!=set(value['manifest']) or any(current[p]!=h for p,h in value['manifest'].items() if p!='src/uploaded.cj'):
            raise ValueError('候选修改了冻结测试或工程配置')
    def case(self,identity,*,actor_id):
        value=self.get(identity,actor_id=actor_id);profile=self.profile(identity)
        code=(self.store.root/'uploads'/identity/'project/src/uploaded.cj').read_bytes().decode()
        files=[dict(path='src/uploaded.cj',before=code,after=code)]
        return dict(id=identity,project_id=identity,title='上传修复 · '+value['filename'],category='上传函数',kind='repair',
            can_replay=False,files=files,real_files=files,requirement=value['goal'],requirements=['确认示例'],
            requirement_ids=['REQ-UPLOAD'],limitations=profile['limitations'],metrics=dict(files=1,tests=len(value['examples']),candidates=0,tokens=0,seconds=None),
            tests=[],logs=[],stages=['需求确认','工程检索','候选生成','策略检查','工程验证','人工审阅','交付归档'],
            source_label='上传',origin='REAL_UPLOAD',provider='DeepSeek',verdict='ALLOW')
