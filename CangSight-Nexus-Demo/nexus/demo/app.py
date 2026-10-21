"""Local presentation shell with direct access, CSRF and policy checks."""
import argparse
import asyncio
from pathlib import Path
import secrets
import threading

from flask import jsonify, render_template, send_file, session, request

from nexus.demo.cases import case_catalog, download_case, load_cases
from nexus.demo.provider import RuleProvider
from nexus.analysis.routes import svg_links,svg_response
from nexus.demo.deepseek import DeepSeekProvider, model_config
from nexus.execution.delivery import DeliveryService
from nexus.execution.ownership import RuntimeOwner
from nexus.repair.cegis_loop import RepairLoop
from nexus.store import RunStore, uid
from nexus.web.app import create_app

ROOT = Path(__file__).resolve().parents[2]


def rule_readiness():
    from nexus.execution.environment import readiness
    report = readiness()
    # This provider makes no model requests. SDK/Policy checks remain mandatory.
    report['missing'] = [m for m in report['missing'] if m['code'] != 'MODEL_NOT_CONFIGURED']
    report['ready'] = not report['missing']
    report['provider'] = 'RULE'
    return report


def create_demo_app(root, *, session_key=None, writes_enabled=True, provider='deepseek'):
    store = RunStore(root)
    if provider not in ('rule','deepseek'):raise ValueError('Unknown configured provider')
    def current_readiness():
        report=rule_readiness()
        report['provider']='DeepSeek' if provider=='deepseek' else 'RULE'
        if provider=='deepseek' and not all(model_config().values()):
            report['ready']=False
            report['missing'].append(dict(code='MODEL_NOT_CONFIGURED',message='DeepSeek未配置'))
        return report
    loop=RepairLoop(store,provider_factory=DeepSeekProvider if provider=='deepseek' else RuleProvider)
    app = create_app(store, loop, DeliveryService(store),
        require_operator=False,session_key=session_key,writes_enabled=writes_enabled,
        readiness_check=current_readiness)
    app.template_folder = str(Path(__file__).parent/'templates')
    # Keep inherited assets at /static and presentation assets at /demo-static.
    from flask import Blueprint
    assets=Blueprint('demo_assets',__name__,static_folder='static',static_url_path='/demo-static')
    app.register_blueprint(assets)
    from nexus.analysis.routes import register_analysis
    register_analysis(app,store)
    from nexus.uploads.routes import register_uploads
    register_uploads(app,store)
    from nexus.analysis.impact import ImpactService
    impact=ImpactService(store,app.extensions['analysis_service'])
    app.extensions['impact_service']=impact
    app.config['RUN_IMPACTS']=True
    if provider=='deepseek':
        from nexus.analysis.repair import RepairAnalysis
        loop.context_enricher=RepairAnalysis(store,app.extensions['analysis_service']).enrich
    cases=load_cases()

    def page():
        session.setdefault('csrf',secrets.token_urlsafe(32))
        session.setdefault('actor_id','local-'+uid())
        return render_template('demo.html',csrf=session['csrf'])
    app.view_functions['page']=page

    @app.get('/favicon.ico')
    def demo_favicon():
        return '',204

    @app.get('/demo/cases')
    def catalog():
        return jsonify(cases=case_catalog(cases))

    @app.get('/demo/cases/<case_id>')
    def details(case_id):
        if case_id.startswith('upload_'):
            return jsonify(app.extensions['upload_service'].case(case_id,actor_id=session['actor_id']))
        if case_id not in cases:return jsonify(error='案例不存在'),404
        return jsonify(cases[case_id])

    @app.get('/demo/download/<case_id>')
    def demo_download(case_id):
        if case_id not in cases:return jsonify(error='案例不存在'),404
        if cases[case_id]['verdict']=='DENY' or not cases[case_id]['can_replay']:return jsonify(error='不可导出'),409
        return send_file(download_case(cases[case_id]),mimetype='application/zip',as_attachment=True,
            download_name=f'CangSight-{case_id}-{cases[case_id]["origin"]}.zip')

    @app.get('/demo/environment')
    def demo_environment():
        report=current_readiness()
        report['policy_ready']=not any(m['code'] in ('SDK_NOT_READY','POLICY_NOT_READY') for m in report['missing'])
        return jsonify(report)

    @app.post('/api/demo/probes/<case_id>')
    def run_probe(case_id):
        from nexus.demo.probes import execute_probe
        if not app.config['WRITES_ENABLED']:return jsonify(error='实例被占用'),503
        if request.get_json(silent=True)!={}:return jsonify(error='请求无效'),400
        return jsonify(asyncio.run(execute_probe(store,case_id)))

    @app.get('/api/demo/candidates/<candidate_id>')
    def real_source(candidate_id):
        from nexus.execution.workspace import WorkspaceStore
        ws=WorkspaceStore(store.root)
        candidate=ws.candidate(candidate_id)
        task=store.get_task(candidate.task_id)
        advice=next((e for e in reversed(store.records(task.id,'event'))
            if e.get('type')=='MODEL_SUGGESTION' and e.get('model_call_id')==candidate.model_call_id),None)
        return jsonify(attempt=candidate.attempt,model_call_id=candidate.model_call_id,edits=[e.model_dump() for e in candidate.edits],advice=advice,
            source_files=[dict(path=e.path,before=ws.read_file(task.baseline_id,e.path),
                after=e.content) for e in candidate.edits])

    @app.get('/api/demo/candidates/<candidate_id>/impact')
    def impact_report(candidate_id):
        return jsonify(impact.get(candidate_id))

    @app.post('/api/demo/candidates/<candidate_id>/impact')
    def impact_start(candidate_id):
        from nexus.analysis.service import AnalysisConflict
        if request.get_json(silent=True)!={}:raise ValueError('影响对比不接受客户端源码或路径')
        try:report,created=impact.start(candidate_id)
        except AnalysisConflict as exc:return jsonify(error=str(exc),code='ANALYSIS_BUSY'),409
        if created and app.config['RUN_IMPACTS']:
            threading.Thread(target=impact.run,args=(candidate_id,),daemon=True).start()
        return jsonify(report),202 if created else 200

    @app.get('/api/demo/candidates/<candidate_id>/impact/evidence')
    def impact_evidence(candidate_id):
        from nexus.analysis.service import AnalysisConflict
        try:stream=impact.export(candidate_id)
        except AnalysisConflict as exc:return jsonify(error=str(exc)),409
        return send_file(stream,mimetype='application/zip',as_attachment=True,
            download_name=f'CangSight-impact-{candidate_id}.zip')

    @app.get('/api/demo/candidates/<candidate_id>/impact/analysis/<analysis_id>')
    @app.get('/api/demo/candidates/<candidate_id>/impact/analysis/<analysis_id>/evidence')
    @app.get('/api/demo/candidates/<candidate_id>/impact/analysis/<analysis_id>/callgraph.svg')
    def impact_analysis(candidate_id,analysis_id):
        report=impact.get(candidate_id)
        entry=next(((file,side) for file in report['files'] for side in ('before','after')
            if file[side] and file[side]['analysis_id']==analysis_id),None)
        if entry is None:raise ValueError('分析不属于当前候选影响报告')
        file,side=entry;actor='repair-'+report['task_id']
        service=app.extensions['analysis_service'];result=service.get(analysis_id,actor_id=actor)
        if result['source']['source_sha256']!=file[side]['source_sha256'] or result['slice_criterion']!=file[side]['slice_criterion']:
            raise ValueError('影响分析版本或准则变化')
        if request.path.endswith('/callgraph.svg'):return svg_response(service.callgraph_bytes(analysis_id,actor_id=actor),analysis_id)
        if request.path.endswith('/evidence'):
            return send_file(service.export(analysis_id,actor_id=actor),mimetype='application/zip',as_attachment=True,
                download_name=f'CangSight-impact-analysis-{analysis_id}.zip')
        return jsonify(**svg_links(result,request.path),display_origin='REGISTERED_BOUND',bound_path=file['path'],
            bound_label=('修复前 · 基线' if side=='before' else '修复后 · 第'+str(report['attempt'])+'轮'),
            evidence_url=request.path+'/evidence')

    @app.get('/api/demo/tasks/<task_id>/analysis')
    def repair_analysis(task_id):
        from nexus.analysis.repair import verify_evidence
        event=next((e for e in store.records(task_id,'event') if e['type']=='ANALYSIS_CONTEXT'),None)
        if event is None:return jsonify(analysis=None)
        return jsonify(analysis=verify_evidence(store,event))

    @app.get('/api/demo/tasks/<task_id>/analysis/<analysis_id>')
    @app.get('/api/demo/tasks/<task_id>/analysis/<analysis_id>/evidence')
    @app.get('/api/demo/tasks/<task_id>/analysis/<analysis_id>/callgraph.svg')
    def repair_analysis_file(task_id,analysis_id):
        from nexus.analysis.repair import verify_evidence
        event=next((e for e in store.records(task_id,'event') if e['type']=='ANALYSIS_CONTEXT'),None)
        if event is None:raise ValueError('No bound analysis')
        report=verify_evidence(store,event)
        entry=next((f for f in report['files'] if f['analysis_id']==analysis_id),None)
        if entry is None:raise ValueError('Analysis does not belong to this task')
        service=app.extensions['analysis_service']
        result=service.get(analysis_id,actor_id='repair-'+task_id)
        if result['source']['source_sha256']!=entry['source_sha256']:raise ValueError('Analysis source changed')
        if request.path.endswith('/callgraph.svg'):return svg_response(service.callgraph_bytes(analysis_id,actor_id='repair-'+task_id),analysis_id)
        if request.path.endswith('/evidence'):
            return send_file(service.export(analysis_id,actor_id='repair-'+task_id),mimetype='application/zip',
                as_attachment=True,download_name=f'CangSight-repair-analysis-{analysis_id}.zip')
        return jsonify(**svg_links(result,request.path),display_origin='REGISTERED_BOUND',bound_path=entry['path'],
            evidence_url=request.path+'/evidence')

    @app.post('/api/demo/tasks/<task_id>/approval-probe')
    def approval_probe(task_id):
        from nexus.demo.probes import execute_approval_probe
        if not app.config['WRITES_ENABLED']:return jsonify(error='实例被占用'),503
        if request.get_json(silent=True)!={}:return jsonify(error='请求无效'),400
        return jsonify(asyncio.run(execute_approval_probe(store,task_id)))

    return app


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8877)
    parser.add_argument('--provider',choices=['deepseek','rule'],default='deepseek')
    args=parser.parse_args()
    owner=RuntimeOwner(ROOT/'.runtime/demo-workbench')
    try:
        writable=owner.acquire()
        if writable:owner.reconcile(RunStore(owner.root))
        app=create_demo_app(owner.root,session_key=owner.session_key(),
            writes_enabled=writable,provider=args.provider)
        if writable:
            app.extensions['analysis_service'].reconcile()
            app.extensions['impact_service'].reconcile()
        print(f'CangSight Nexus: http://127.0.0.1:{args.port}',flush=True)
        app.run(host='127.0.0.1',port=args.port,debug=False,threaded=True)
    finally:owner.close()


if __name__=='__main__':main()
