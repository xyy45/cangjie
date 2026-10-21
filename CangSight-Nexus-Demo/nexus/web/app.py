"""Local-only workbench over the existing MCP repair and delivery services."""
import asyncio
from pathlib import Path
import secrets
import threading
import time
import zipfile

from flask import Flask, jsonify, render_template, request, session, send_file
from werkzeug.exceptions import BadRequest

from nexus.contracts import digest
from nexus.execution.delivery import DeliveryService
from nexus.execution.workspace import WorkspaceStore
from nexus.mcp.client import ToolClient
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore, uid
from nexus.requirements.service import RequirementService
from nexus.execution.environment import readiness
from nexus.execution.review import ReviewService
from nexus.scenarios import registered_projects

class WorkbenchError(ValueError):
    def __init__(self, code, message, *, record_refs=None):
        self.code = code
        self.record_refs=record_refs or []
        super().__init__(message)


ROOT = Path(__file__).resolve().parents[2]
PROJECTS = registered_projects()


def create_app(store: RunStore, loop: RepairLoop, delivery: DeliveryService, *, session_key=None, writes_enabled=True, operator_key=None, readiness_check=None, require_operator=True) -> Flask:
    app = Flask(__name__)
    def environment_readiness():
        return (readiness_check or readiness)()
    app.secret_key = session_key or secrets.token_bytes(32)
    if require_operator:
        if operator_key is None:operator_key=secrets.token_hex(32)
        if not isinstance(operator_key,str) or len(operator_key)!=64 or any(c not in '0123456789abcdef' for c in operator_key):
            raise ValueError('Invalid operator credential')
    operator_epoch=secrets.token_hex(32) if require_operator else None

    def paired():
        return not require_operator or session.get('operator_epoch')==operator_epoch

    requirements = RequirementService(store)
    from nexus.uploads.service import UploadService
    uploads=UploadService(store)
    app.config.update(MAX_CONTENT_LENGTH=131072, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Strict', RUN_TASKS=True, WRITES_ENABLED=writes_enabled)
    with store.connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS starts(key TEXT PRIMARY KEY, body_hash TEXT NOT NULL, task_id TEXT NOT NULL)')

    @app.before_request
    def local_guard():
        if request.remote_addr not in ('127.0.0.1','::1') or request.host.split(':')[0] not in ('localhost','127.0.0.1'):
            return jsonify(error='Local workbench only'),403
        if request.method != 'GET':
            if not app.config['WRITES_ENABLED'] and request.path!='/api/operator/authorize':
                return jsonify(error='Runtime ownership unconfirmed; read-only until manual reconciliation',code='OWNER_UNCONFIRMED'),503
            if request.headers.get('Origin') != request.host_url.rstrip('/') or not session.get('csrf') or request.headers.get('X-CSRF-Token') != session['csrf']:
                return jsonify(error='Local user session required'),403
        if not require_operator and request.method=='GET':
            session.setdefault('csrf',secrets.token_urlsafe(32))
            session.setdefault('actor_id','local-'+uid())
        protected=request.path.startswith(('/api/','/downloads/','/agents/'))
        public=request.path in ('/api/environment','/api/operator/authorize')
        if protected and not public and not paired():
            return jsonify(error='请先使用本机操作者凭据授权此浏览器会话。',code='OPERATOR_REQUIRED'),403

    @app.errorhandler(ValueError)
    @app.errorhandler(BadRequest)
    def invalid(error):
        if isinstance(error,WorkbenchError):
            return jsonify(error=str(error),code=error.code,record_refs=error.record_refs),400
        # Validation errors may contain submitted data. Do not echo or log it.
        app.logger.info('Invalid local request: %s',type(error).__name__)
        return jsonify(error='请求无效，请检查输入并刷新页面后重试。',code='INVALID_REQUEST'),400

    @app.errorhandler(OSError)
    @app.errorhandler(zipfile.BadZipFile)
    def unavailable(error):
        return jsonify(error='本机证据或运行环境不可用，请检查环境与技术记录。',code='LOCAL_EVIDENCE_UNAVAILABLE'),503

    @app.errorhandler(LookupError)
    def private_not_found(error):return jsonify(error='记录不存在或不属于当前会话',code='NOT_FOUND'),404

    @app.before_request
    def upload_ownership():
        args=request.view_args or {};actor=session.get('actor_id')
        task_id=args.get('task_id') or args.get('run_id')
        candidate_id=args.get('candidate_id')
        if args.get('export_id'):
            with store.connect() as db:row=db.execute('SELECT candidate_id FROM acceptances WHERE export_id=?',(args['export_id'],)).fetchone()
            if row:candidate_id=row[0]
        if candidate_id:
            with store.connect() as db:row=db.execute("SELECT task_id FROM records WHERE kind='candidate' AND object_id=?",(candidate_id,)).fetchone()
            if row:task_id=row[0]
        if task_id:
            with store.connect() as db:exists=db.execute('SELECT 1 FROM tasks WHERE id=?',(task_id,)).fetchone()
            if exists:uploads.task_access(task_id,actor)
        if args.get('draft_id'):
            with store.connect() as db:row=db.execute('SELECT payload FROM requirement_drafts WHERE id=?',(args['draft_id'],)).fetchone()
            if row:
                import json
                uploads.project_access(json.loads(row[0])['project_id'],actor)

    def action_error(task_id, code, message, reason):
        ref=store.append_record(task_id,'event',dict(type='API_REJECTED',operation=request.endpoint,
            actor_id=session.get('actor_id'),business_code=code,technical_reason=str(reason)))
        return WorkbenchError(code,message,record_refs=[ref])

    @app.get('/')
    def page():
        session.setdefault('csrf',secrets.token_urlsafe(32))
        session.setdefault('actor_id','local-'+uid())
        return render_template('workbench.html' if paired() else 'operator.html',csrf=session['csrf'])

    def authorize_operator():
        body=request.get_json(silent=True)
        key=body.get('key') if isinstance(body,dict) and set(body)=={'key'} else None
        if (not isinstance(key,str) or len(key)!=64 or any(c not in '0123456789abcdef' for c in key)
                or not secrets.compare_digest(key,operator_key)):
            return jsonify(error='本机操作者凭据无效。',code='OPERATOR_REQUIRED'),403
        session['operator_epoch']=operator_epoch
        return jsonify(authorized=True)

    if require_operator:
        app.add_url_rule('/api/operator/authorize',view_func=authorize_operator,methods=['POST'])

    @app.get('/api/environment')
    def environment():
        report=environment_readiness()
        if not app.config['WRITES_ENABLED']:
            report['ready']=False
            report['missing'].append(dict(code='OWNER_UNCONFIRMED',message='执行所有者未确认，当前仅可查看；请先核查其他运行实例。'))
        return jsonify(report)

    @app.post('/api/requirements/drafts')
    def requirement_draft():
        body=request.get_json()
        if not isinstance(body,dict) or set(body)!={'project','goal'}:
            raise ValueError('project and goal required')
        uploads.project_access(body['project'],session.get('actor_id'))
        return jsonify(requirements.prepare_requirement(body['project'],body['goal']))

    @app.post('/api/requirements/drafts/<draft_id>/confirm')
    def confirm_requirement(draft_id):
        body=request.get_json()
        if not isinstance(body,dict):
            raise ValueError('Versioned requirement confirmation required')
        return jsonify(requirements.confirm_requirement(draft_id,body,actor_id=session['actor_id']).model_dump())

    @app.post('/api/tasks')
    def start():
        return start_task(request.get_json())

    def start_task(body, *, base_commit=None, adapter_sha256=None, dispatch=None):
        if not isinstance(body,dict) or set(body)!={'project','spec_id','idempotency_key'}:
            raise ValueError('project, confirmed spec_id and idempotency_key required')
        if not isinstance(body['project'],str) or not isinstance(body['spec_id'],str):
            raise ValueError('Select a registered project and confirmed requirements')
        uploads.project_access(body['project'],session.get('actor_id'))
        source=PROJECTS.get(body['project'])
        if source is None:source=uploads.source(body['project'],actor_id=session.get('actor_id'))
        key = body['idempotency_key']
        if not isinstance(key,str) or not 1<=len(key)<=64: raise ValueError('invalid start key')
        body_hash = digest({'project':body['project'],'spec_id':body['spec_id']})
        if base_commit is not None:
            body_hash = digest(dict(body_hash=body_hash,base_commit=base_commit))
        with store.connect() as db:
            old = db.execute('SELECT body_hash,task_id FROM starts WHERE key=?',(key,)).fetchone()
        if old:
            if old[0]!=body_hash: raise ValueError('start key reused with changed arguments')
            return jsonify(store.get_task(old[1]).model_dump())
        try:
            spec = requirements.get_spec(body['spec_id'])
        except ValueError as exc:
            raise WorkbenchError('REQUIREMENT_UNCONFIRMED','需求尚未确认或已失效，请重新准备并确认。') from exc
        if spec.project_id!=body['project']:
            raise ValueError('Requirement project binding mismatch')
        if app.config['RUN_TASKS'] and not environment_readiness()['ready']:
            raise WorkbenchError('ENVIRONMENT_NOT_READY','运行环境未就绪，请先查看环境提示。')
        baseline = WorkspaceStore(store.root,registered=[source]).import_project(source,'.')
        task = requirements.prepare_task(body['project'],spec.id,baseline)
        if base_commit is not None:
            task.runtime_binding = dict(implementation='CangSight native RunStore',
                sympas_integration='DERIVED_GATEWAY',base_commit=base_commit,
                adapter_sha256=adapter_sha256,contract_version=1,
                external_run_id=task.id,internal_task_id=task.id)
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT body_hash,task_id FROM starts WHERE key=?',(key,)).fetchone()
            if old:
                if old[0]!=body_hash: raise ValueError('start key reused with changed arguments')
                return jsonify(store.get_task(old[1]).model_dump())
            db.execute('INSERT INTO tasks VALUES (?,?)',(task.id,task.model_dump_json()))
            db.execute('INSERT INTO starts VALUES (?,?,?)',(key,body_hash,task.id))
        if app.config['RUN_TASKS']:
            if dispatch is None:
                threading.Thread(target=lambda: asyncio.run(loop.run(task.id)),daemon=True).start()
            else:
                dispatch(task.id)
        return jsonify(store.get_task(task.id).model_dump() if dispatch else task.model_dump())

    def current_checks(task_id,subject_id):
        from nexus.adapters.cangjie.verifier import CangjieVerifier
        checks=[r for r in store.records(task_id,'check') if r['subject_id']==subject_id]
        if not checks: return []
        try: _,identity,plan=CangjieVerifier(store.root,task_id).identity(subject_id)
        except (ValueError,OSError): identity,plan=None,None
        return [r if r['tree_hash']==identity and r['plan_hash']==plan else
                {**r,'state':'UNKNOWN','diagnostics':'检查对应旧源码或验证配置，需重新验证'} for r in checks]

    @app.get('/api/tasks')
    def history():
        with store.connect() as db:
            tasks=[store._decode_task(row[0]) for row in db.execute('SELECT payload FROM tasks ORDER BY rowid DESC LIMIT 50')]
        visible=[]
        for t in tasks:
            try:uploads.task_access(t.id,session.get('actor_id'))
            except LookupError:continue
            visible.append(dict(id=t.id,goal=t.goal,status=t.status,revision=t.revision,schema_version=t.schema_version))
        return jsonify(tasks=visible,limit=50)

    @app.get('/api/tasks/<task_id>/events')
    def events(task_id):
        after=request.args.get('after','0')
        if not after.isascii() or not after.isdigit():raise ValueError('Nonnegative event sequence required')
        records=store.records(task_id,'event')
        versioned=[event for event in records if 'sequence' in event]
        selected=[event for event in versioned if event['sequence']>int(after)][:100]
        return jsonify(events=selected,last_sequence=selected[-1]['sequence'] if selected else int(after),
            legacy_event_count=len(records)-len(versioned),limit=100)

    @app.get('/api/tasks/<task_id>')
    def task(task_id):
        data = store.get_task(task_id).model_dump()
        candidates = store.records(task_id,'candidate')
        data['candidates']=[]
        for r in candidates:
            checks=current_checks(task_id,r['id'])
            data['candidates'].append({**{key:r.get(key) for key in ('id','attempt','tree_hash','model_call_id')},
                **{kind+'_state':next((c['state'] for c in reversed(checks) if c['kind']==kind),'NOT_RUN')
                   for kind in ('build','test')}})
        selected = [e['selected_candidate_id'] for e in store.records(task_id,'event') if 'selected_candidate_id' in e]
        data['candidate_id'] = selected[-1] if selected else (candidates[-1]['id'] if candidates else None)
        data['download_url'] = None
        data['review_notice']=''
        if data['status']=='DELIVERED' and data['candidate_id']:
            with store.connect() as db:
                delivered=db.execute("SELECT id,export_id FROM acceptances WHERE candidate_id=? AND status='DELIVERED' ORDER BY rowid DESC",(data['candidate_id'],)).fetchone()
            if delivered:
                try:
                    approval,_,_=delivery.acceptance(data['candidate_id'],delivered[0],actor_id=session.get('actor_id'))
                    delivery.verify_archive(delivered[1],approval)
                    data['download_url']='/downloads/'+delivered[1]
                except (ValueError,OSError,KeyError,zipfile.BadZipFile):
                    data['review_notice']='历史检查、审批或归档已失效；请新建任务，不会自动重新调用模型。'
        if data['schema_version']==2:
            spec, plan = requirements.task_context(store.get_task(task_id))
            data['requirement_spec'] = spec.model_dump()
            data['limitations'] = plan.limitations
        else:
            data['requirement_spec'] = None
            data['limitations'] = ['V1历史任务，不包含V1.1确认需求和计划绑定']
        data['events'] = store.records(task_id,'event')
        data['model_calls']=[{k:r.get(k) for k in ('id','origin','model_id','status','usage')}
                             for r in store.records(task_id,'model_call')]
        cancelled=[event for event in data['events'] if event.get('type')=='USER_CANCELLED']
        if data['status']=='CANCELLED' and cancelled and cancelled[-1].get('in_flight_unknown'):
            data['review_notice']='后续步骤已停止；在途操作和已发生费用仍需核实，不会自动重试或承诺撤销。'
        data['baseline_checks'] = current_checks(task_id,data['baseline_id'])
        return jsonify(data)

    @app.get('/api/candidates/<candidate_id>')
    def candidate(candidate_id):
        ws = WorkspaceStore(store.root)
        c = ws.candidate(candidate_id)
        checks = current_checks(c.task_id,c.id)
        data = dict(id=c.id,task_id=c.task_id,tree_hash=c.tree_hash,diff=ws.diff(c.id),checks=checks)
        task = store.get_task(c.task_id)
        data['task_revision']=task.revision
        data['task_schema_version']=task.schema_version
        selected=[e['selected_candidate_id'] for e in store.records(task.id,'event') if 'selected_candidate_id' in e]
        data['is_current_review']=task.status=='REVIEW_PENDING' and bool(selected) and selected[-1]==c.id
        data['requirement_results'] = []
        data['limitations'] = []
        if task.schema_version==2:
            from nexus.requirements.review import assess_requirements
            from nexus.contracts import CheckResult
            spec, frozen = requirements.task_context(task)
            builds = [r for r in checks if r['kind']=='build']
            tests = [r for r in checks if r['kind']=='test']
            test = CheckResult.model_validate(tests[-1]) if tests else CheckResult(state='NOT_RUN')
            data['requirement_results'] = assess_requirements(spec,frozen,test,build_state=builds[-1]['state'] if builds else 'NOT_RUN')
            data['limitations'] = frozen.limitations
        try: data['check_set_hash'] = delivery.check_set_hash(c.id)
        except ValueError: data['check_set_hash'] = None
        return jsonify(data)

    @app.post('/api/candidates/<candidate_id>/accept')
    def accept(candidate_id):
        body = request.get_json()
        c=WorkspaceStore(store.root).candidate(candidate_id)
        expected={'check_set_hash','task_revision'} if store.get_task(c.task_id).schema_version==2 else {'check_set_hash'}
        if not isinstance(body,dict) or set(body)!=expected: raise ValueError('Current check_set_hash and task_revision required')
        try:
            approval=delivery.accept(candidate_id,body['check_set_hash'],actor_id=session['actor_id'],
                task_revision=body.get('task_revision'))
        except ValueError as exc:
            raise action_error(c.task_id,'CHECKS_NOT_PASS','检查或审阅状态已变化，暂不能接受；请刷新后核对当前候选与验证结果。',exc) from exc
        return jsonify(approval.model_dump())

    @app.post('/api/candidates/<candidate_id>/reject')
    def reject(candidate_id):
        body=request.get_json()
        if not isinstance(body,dict) or not {'task_revision'}<=set(body)<={'task_revision','reason'}:
            raise ValueError('Current task_revision and optional reason required')
        return jsonify(ReviewService(store).reject(candidate_id,body['task_revision'],
            actor_id=session['actor_id'],reason=body.get('reason','')).model_dump())

    @app.post('/api/tasks/<task_id>/cancel')
    def cancel(task_id):
        body=request.get_json()
        if not isinstance(body,dict) or set(body)!={'task_revision'}:
            raise ValueError('Current task_revision required')
        result=ReviewService(store).cancel(task_id,body['task_revision'],actor_id=session['actor_id'])
        return jsonify(**result,code='RESULT_IN_DOUBT' if result['in_flight_unknown'] else 'CANCELLED')

    @app.post('/api/candidates/<candidate_id>/export')
    def export(candidate_id):
        body = request.get_json()
        if not isinstance(body,dict) or set(body)!={'acceptance_id'}: raise ValueError('acceptance_id required')
        c = WorkspaceStore(store.root).candidate(candidate_id)
        try:
            delivery.acceptance(c.id,body['acceptance_id'],actor_id=session['actor_id'])
        except ValueError as exc:
            raise action_error(c.task_id,'APPROVAL_INVALID','批准已失效或不属于当前会话；请刷新核对，已交付任务需新建任务重新审阅。',exc) from exc
        async def invoke():
            async with ToolClient(store.root) as client:
                return await client.call_tool('candidate.export',dict(task_id=c.task_id,request_id=uid(),
                    candidate_id=c.id,acceptance_id=body['acceptance_id']))
        result = asyncio.run(invoke())
        if result.operation_status!='OK':
            uncertain=result.operation_status=='IN_DOUBT'
            code='RESULT_IN_DOUBT' if uncertain else 'EXPORT_BLOCKED'
            message=('导出结果待核实，请查看原操作记录，不要重复执行或假定已经撤销。' if uncertain else
                '导出被阻止，请检查环境和验证记录，修复原因后重新审阅。')
            failure=action_error(c.task_id,code,message,result.error or result.operation_status)
            return jsonify(error=str(failure),code=code,operation_status=result.operation_status,
                record_refs=[*result.record_refs,*failure.record_refs]),409
        data = result.data
        if data.get('download_ref'): data['download_url']='/downloads/'+data['export_id']
        return jsonify(data)

    @app.post('/api/policy-probe')
    def policy_probe():
        from nexus.policy.gate import gate_and_execute
        from nexus.contracts import ToolResult, tree_hash
        source = PROJECTS['order-demo-bug']
        ws = WorkspaceStore(store.root,registered=list(PROJECTS.values()))
        baseline = ws.import_project(source,'.')
        task = store.create_task(baseline,'演示拒绝修改冻结测试',['src/quantity.cj'])
        before = tree_hash(ws.subject_path(baseline))
        executed = []
        async def invoke():
            async def action():
                executed.append(True)
                return ToolResult(operation_status='ERROR',error='Protection probe unexpectedly allowed')
            return await gate_and_execute(dict(schema_version=1,policy_version='1.1',deadline_at=int(time.time()*1000)+30000,approval_binding='',
                action='candidate.apply',task_id=task.id,request_id=uid(),
                paths=['src/order_test.cj'],input_tree_hash=before,arguments_hash=digest({'path':'src/order_test.cj'}),
                remaining_budget=3,accepted=False),action,
                audit=lambda payload: store.append_record(task.id,'event',{'policy':payload}))
        result = asyncio.run(invoke())
        unchanged = tree_hash(ws.subject_path(baseline)) == before
        denied = result.error=='PROTECTED_PATH' and not executed and unchanged
        store.update_task(task.id,status='REJECTED' if denied else 'BLOCKED')
        return jsonify(decision='Deny' if denied else 'Unknown',reason=result.error,
                       unchanged=unchanged,action_executed=bool(executed))

    @app.get('/downloads/<export_id>')
    def download(export_id):
        if not session.get('actor_id'):
            raise ValueError('Local review session required to download')
        if len(export_id)!=32 or any(c not in '0123456789abcdef' for c in export_id): raise ValueError('invalid export')
        with store.connect() as db:
            row = db.execute("SELECT payload FROM acceptances WHERE export_id=? AND status='DELIVERED'",(export_id,)).fetchone()
        if not row: raise ValueError('export is not delivered')
        from nexus.contracts import AcceptanceRecord
        a = AcceptanceRecord.model_validate_json(row[0])
        # Revalidate content/evidence before serving a completed artifact.
        delivery.acceptance(a.candidate_id,a.id,actor_id=session.get('actor_id'))
        artifact=delivery.verify_archive(export_id,a)
        return send_file(artifact,as_attachment=True,download_name='CangSight-order-repaired.zip')

    from nexus.integrations.sympas_runtime import gateway
    app.register_blueprint(gateway(store,start_task,task,lambda task_id:asyncio.run(loop.run(task_id))))
    return app


if __name__ == '__main__':
    from nexus.execution.ownership import RuntimeOwner
    owner=RuntimeOwner(ROOT/'.runtime/workbench')
    try:
        writable=owner.acquire()
        store=RunStore(owner.root)
        if writable:owner.reconcile(store)
        create_app(store,RepairLoop(store),DeliveryService(store),session_key=owner.session_key(),
            operator_key=owner.operator_key(),writes_enabled=writable).run(host='127.0.0.1',port=8765,debug=False)
    finally:owner.close()
