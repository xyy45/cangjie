"""Frozen order-case requirement templates in the existing SQLite fact store.

Unsupported semantic edits require a maintainer-provided test mapping; they are
not silently assigned to the existing tests. No model or SDK calls occur here.
"""
import json
from copy import deepcopy

from nexus.contracts import RequirementConfirmation, RequirementSpec, VerificationPlan, digest
from nexus.store import RunStore, uid
from nexus.scenarios import get_profile

ALLOWED_PATHS = ['src/quantity.cj', 'src/fee.cj', 'src/order.cj']
ITEMS = [
    dict(id='REQ-QTY', text='数量范围1–1000，包含上下界',
         observable_behavior='数量0、负数、1001拒绝；1和1000允许',
         preserves=['合法数量继续参与费用计算'], uncovered=['不验证其他数量类型']),
    dict(id='REQ-PRICE', text='单价范围0–1000000，非法订单返回-1',
         observable_behavior='负单价和1000001拒绝；0和1000000允许',
         preserves=['数量校验继续生效'], uncovered=['不验证浮点价格']),
    dict(id='REQ-TOTAL', text='合法订单总额为数量乘单价',
         observable_behavior='3×100=300；2×100=200；7×23=161；零价格总额0',
         preserves=['合法订单乘法计算'], uncovered=['不证明任意输入的语义正确性']),
]
CASES = ['three','two','zeroPrice','zeroQuantity','negativeQuantity','upperQuantity',
         'excessQuantity','negativePrice','upperPrice','excessPrice','differentPrice']


class RequirementService:
    def __init__(self, store: RunStore):
        self.store = store
        with store.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS requirement_drafts(
                    id TEXT PRIMARY KEY, payload TEXT NOT NULL, status TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS requirement_specs(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS verification_plans(id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            ''')

    def profile(self,project_id):
        if isinstance(project_id,str) and project_id.startswith('upload_'):
            from nexus.uploads.service import UploadService
            return UploadService(self.store).profile(project_id)
        return get_profile(project_id)

    def prepare_requirement(self, project_id: str, goal: str, *, previous_spec_id: str | None = None) -> dict:
        profile=self.profile(project_id)
        if project_id.startswith('upload_') and goal!=profile['goal']:raise ValueError('上传需求已冻结')
        if not isinstance(goal,str) or not goal.strip() or len(goal)>4000:
            raise ValueError('A nonempty goal of at most 4000 characters is required')
        version=1
        if previous_spec_id:
            old=self.get_spec(previous_spec_id)
            if old.project_id != project_id:
                raise ValueError('Requirement revision belongs to another project')
            version=old.version+1
        draft=dict(schema_version=1,id=uid(),version=version,project_id=project_id,
                   source_text=goal,requirements=deepcopy(profile['requirements']),allowed_paths=list(profile['allowed_paths']))
        with self.store.connect() as db:
            db.execute('INSERT INTO requirement_drafts VALUES (?,?,?)',
                       (draft['id'],json.dumps(draft,ensure_ascii=False),'DRAFT'))
        return draft

    def confirm_requirement(self, draft_id: str, edited_spec: dict, *, actor_id: str) -> RequirementSpec:
        edited=RequirementConfirmation.model_validate(edited_spec)
        if not isinstance(actor_id,str) or not actor_id.strip():
            raise ValueError('Trusted local actor is required')
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT payload,status FROM requirement_drafts WHERE id=?',(draft_id,)).fetchone()
            if not row:
                raise ValueError('Unknown requirement draft')
            if row[1]!='DRAFT':
                raise ValueError('Requirement draft already confirmed')
            draft=json.loads(row[0])
            profile=self.profile(draft['project_id'])
            if not set(edited.allowed_paths)<=set(profile['allowed_paths']):
                raise ValueError('Unknown allowed source path')
            submitted={item.id:item.model_dump() for item in edited.requirements}
            if submitted!={item['id']:item for item in profile['requirements']}:
                raise ValueError('Required behavior is missing or unmapped; a maintainer test mapping is needed')
            if draft['schema_version']!=1 or edited.expected_version!=draft['version']:
                raise ValueError('Requirement draft version changed')
            payload=dict(schema_version=1,id=uid(),version=draft['version'],project_id=draft['project_id'],
                source_text=draft['source_text'],requirements=[i.model_dump() for i in edited.requirements],
                allowed_paths=edited.allowed_paths,confirmed_by=actor_id)
            spec=RequirementSpec(**payload,spec_hash=digest(payload))
            db.execute('INSERT INTO requirement_specs VALUES (?,?)',(spec.id,spec.model_dump_json()))
            db.execute("UPDATE requirement_drafts SET status='CONFIRMED' WHERE id=?",(draft_id,))
        return spec

    def get_spec(self, spec_id: str) -> RequirementSpec:
        with self.store.connect() as db:
            row=db.execute('SELECT payload FROM requirement_specs WHERE id=?',(spec_id,)).fetchone()
        if not row:
            raise ValueError('Requirement is unconfirmed or unknown')
        spec=RequirementSpec.model_validate_json(row[0])
        if spec.id!=spec_id or digest(spec.model_dump(exclude={'spec_hash'}))!=spec.spec_hash:
            raise ValueError('Confirmed requirement content changed')
        return spec

    def build_verification_plan(self, spec_id: str, *, baseline_hash: str, toolchain_id: str) -> VerificationPlan:
        spec=self.get_spec(spec_id)
        profile=self.profile(spec.project_id)
        payload=dict(schema_version=1,id=uid(),version=1,baseline_hash=baseline_hash,
            spec_hash=spec.spec_hash,toolchain_id=toolchain_id,
            required_suites=profile['required_suites'],suite_tests=profile['suite_tests'],
            requirement_test_map=profile['requirement_test_map'],
            context_visibility=profile['context_visibility'],limitations=profile['limitations'])
        plan=VerificationPlan(**payload,plan_hash=digest(payload))
        with self.store.connect() as db:
            db.execute('INSERT INTO verification_plans VALUES (?,?)',(plan.id,plan.model_dump_json()))
        return plan

    def get_plan(self, plan_id: str) -> VerificationPlan:
        with self.store.connect() as db:
            row=db.execute('SELECT payload FROM verification_plans WHERE id=?',(plan_id,)).fetchone()
        if not row:
            raise ValueError('Unknown verification plan')
        plan=VerificationPlan.model_validate_json(row[0])
        if plan.id!=plan_id or digest(plan.model_dump(exclude={'plan_hash'}))!=plan.plan_hash:
            raise ValueError('Frozen verification plan changed')
        return plan

    def prepare_task(self, project_id: str, spec_id: str, baseline_id: str):
        from nexus.contracts import TaskRecord, tree_hash
        from nexus.execution.workspace import WorkspaceStore
        from nexus.adapters.cangjie.sdk import SDK, MACOS_SDK
        import hashlib
        spec=self.get_spec(spec_id)
        if spec.project_id!=project_id:
            raise ValueError('Requirement project binding mismatch')
        toolchain=digest({name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in {
            'cjc':SDK/'bin/cjc','cjpm':SDK/'tools/bin/cjpm'}.items()})
        if not MACOS_SDK.is_dir():
            raise ValueError('Pinned macOS SDK unavailable')
        baseline=WorkspaceStore(self.store.root).verify_baseline(baseline_id)
        plan=self.build_verification_plan(spec.id,baseline_hash=tree_hash(baseline),toolchain_id=toolchain)
        return TaskRecord(schema_version=2,id=uid(),baseline_id=baseline_id,goal=spec.source_text,
            allowed_paths=spec.allowed_paths,spec_id=spec.id,spec_hash=spec.spec_hash,
            verification_plan_id=plan.id,verification_plan_hash=plan.plan_hash,
            runtime_binding={'implementation':'CangSight native RunStore','sympas_integration':'UNCONFIRMED'},
            allowed_tools=['workspace.list_files','workspace.read_file','workspace.search','project.diagnose',
                'candidate.apply','candidate.diff','candidate.build','candidate.test','candidate.export'])

    def task_context(self, task):
        from nexus.contracts import tree_hash
        from nexus.execution.workspace import WorkspaceStore
        if task.schema_version!=2:
            raise ValueError('Legacy task has no V1.1 requirement binding')
        spec=self.get_spec(task.spec_id)
        plan=self.get_plan(task.verification_plan_id)
        if (task.spec_hash!=spec.spec_hash or task.verification_plan_hash!=plan.plan_hash or
                plan.spec_hash!=spec.spec_hash or task.goal!=spec.source_text or task.allowed_paths!=spec.allowed_paths or
                task.budget!={'candidates':3,'seconds':480,'output_tokens':20000}):
            raise ValueError('Task requirement/plan binding changed')
        baseline=WorkspaceStore(self.store.root).verify_baseline(task.baseline_id)
        if tree_hash(baseline)!=plan.baseline_hash:
            raise ValueError('Task baseline/plan binding changed')
        return spec,plan
