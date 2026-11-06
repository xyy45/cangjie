"""Preparing and confirming uploads does not invoke tools or a model."""
from flask import request,session,jsonify
from nexus.analysis.normalize import MAX_SOURCE
from nexus.uploads.service import UploadService,UploadGoalConflict
from nexus.projects.archive import MAX_ARCHIVE,MAX_FILE,MAX_FILES,MAX_TOTAL
import json
import threading


def register_uploads(app,store):
    service=UploadService(store);app.extensions['upload_service']=service
    from nexus.uploads.rule_drafts import RuleDraftService,DraftConflict
    drafts=RuleDraftService(store);app.extensions['rule_draft_service']=drafts
    app.config['RUN_RULE_DRAFTS']=True

    def bound_draft(identity,draft_id):
        service.get(identity,actor_id=session['actor_id'])
        row=drafts.get(draft_id,actor_id=session['actor_id'])
        if row['upload_id']!=identity:raise LookupError('草案不存在')
        return row

    @app.get('/api/uploads/repair/<identity>/rule-drafts')
    def rule_draft_list(identity):
        try:return jsonify(jobs=drafts.list(identity,actor_id=session['actor_id']))
        except LookupError:return jsonify(error='上传或草案不存在'),404
        except (ValueError,OSError):return jsonify(error='草案原件或绑定已变化',code='DRAFT_EVIDENCE_CHANGED'),409

    @app.post('/api/uploads/repair/<identity>/rule-drafts')
    def rule_draft_create(identity):
        try:
            body=request.get_json()
            if (type(body) is not dict or set(body)-{'expected_version','function','request_key','consent','allowed_paths'} or
                    not {'expected_version','function','request_key','consent'}<=set(body)):
                raise ValueError('请确认函数、版本、范围及生成发送许可')
            uploaded=service.get(identity,actor_id=session['actor_id'])
            if not uploaded['goal']:
                return jsonify(error='请填写预期行为后再生成测试用例',code='DRAFT_INPUT_INVALID'),400
            if drafts.provider_factory is None:
                from nexus.demo.rule_draft_provider import RuleDraftProvider
                if not RuleDraftProvider.available():return jsonify(error='模型草案配置未就绪',code='DRAFT_MODEL_UNAVAILABLE'),503
            job=drafts.create(identity,actor_id=session['actor_id'],**body)
        except LookupError:return jsonify(error='上传或草案不存在'),404
        except DraftConflict as exc:return jsonify(error=str(exc),code='DRAFT_CONFLICT'),409
        except (ValueError,TypeError,KeyError):return jsonify(error='草案输入、版本或生成发送许可无效',code='DRAFT_INPUT_INVALID'),400
        if app.config['RUN_RULE_DRAFTS'] and job['call_state']=='CREATED':
            threading.Thread(target=drafts.run,args=(job['id'],),daemon=True).start()
        return jsonify(job),202

    @app.get('/api/uploads/repair/<identity>/rule-drafts/<draft_id>')
    def rule_draft_get(identity,draft_id):
        try:return jsonify(bound_draft(identity,draft_id))
        except LookupError:return jsonify(error='上传或草案不存在'),404
        except (ValueError,OSError):return jsonify(error='草案原件或绑定已变化',code='DRAFT_EVIDENCE_CHANGED'),409

    @app.post('/api/uploads/repair/<identity>/rule-drafts/<draft_id>/apply-preview')
    def rule_draft_apply(identity,draft_id):
        try:
            bound_draft(identity,draft_id)
            body=request.get_json()
            if type(body) is not dict or set(body)-{'expected_version','function','allowed_paths','examples_only'} or not {'expected_version','function'}<=set(body):raise ValueError('应用输入无效')
            return jsonify(drafts.apply_preview(draft_id,actor_id=session['actor_id'],**body))
        except LookupError:return jsonify(error='上传或草案不存在'),404
        except DraftConflict as exc:return jsonify(error=str(exc),code='DRAFT_CONFLICT'),409
        except (ValueError,TypeError,KeyError,OSError):return jsonify(error='草案不可应用或绑定已变化',code='DRAFT_INPUT_INVALID'),400


    @app.get('/api/uploads/repair')
    def upload_list():return jsonify(uploads=service.list(actor_id=session['actor_id']))

    @app.get('/api/uploads/repair/<identity>')
    def upload_get(identity):return jsonify(service.get(identity,actor_id=session['actor_id']))

    @app.post('/api/uploads/repair/<identity>/goal')
    def upload_bind_goal(identity):
        try:
            body=request.get_json()
            if type(body) is not dict or set(body)!={'goal','expected_version'}:
                raise ValueError('请提供预期行为和上传版本')
            return jsonify(service.bind_goal(identity,actor_id=session['actor_id'],**body))
        except LookupError:return jsonify(error='上传不存在'),404
        except UploadGoalConflict as exc:return jsonify(error=str(exc),code='UPLOAD_GOAL_CONFLICT'),409
        except ValueError as exc:return jsonify(error=str(exc),code='UPLOAD_INPUT_INVALID'),400

    @app.post('/api/uploads/repair')
    def upload_prepare():
        try:
            if set(request.files)!={'file'} or len(request.files.getlist('file'))!=1 or set(request.form) not in ({'request_key'},{'goal','request_key'}):
                raise ValueError('请选择单个 .cj 文件')
            file=request.files['file']
            value=service.prepare(file.filename,file.stream.read(MAX_SOURCE+1),request.form.get('goal',''),
                actor_id=session['actor_id'],request_key=request.form['request_key'])
            return jsonify(value),201
        except ValueError as exc:return jsonify(error=str(exc),code='UPLOAD_INPUT_INVALID'),400

    @app.post('/api/uploads/repair/<identity>/confirm')
    def upload_confirm(identity):
        try:
            body=request.get_json()
            if (not isinstance(body,dict) or set(body)-{'expected_version','function','examples_json','consent','oracle_json','allowed_paths','rule_draft_ref','properties_json','relations_json','sequences_json'} or
                    not {'expected_version','function','examples_json','consent'}<=set(body)):
                raise ValueError('请确认函数、示例版本与发送许可')
            return jsonify(service.confirm(identity,actor_id=session['actor_id'],**body))
        except ValueError as exc:return jsonify(error=str(exc),code='UPLOAD_INPUT_INVALID'),400

    @app.post('/api/uploads/repair/project')
    def project_prepare():
        try:
            if set(request.files)=={'file'} and set(request.form) in ({'request_key'},{'goal','request_key'}) and len(request.files.getlist('file'))==1:
                file=request.files['file']
                if not file.filename.lower().endswith('.zip'):raise ValueError('工程归档请选择.zip')
                value=service.prepare_project(file.filename,file.stream.read(MAX_ARCHIVE+1),request.form.get('goal',''),actor_id=session['actor_id'],request_key=request.form['request_key'])
            elif set(request.files)=={'files'} and set(request.form) in ({'request_key','paths_json'},{'goal','request_key','paths_json'}):
                raw=request.form['paths_json']
                if len(raw.encode())>32768:raise ValueError('工程路径清单超限')
                try:paths=json.loads(raw)
                except (ValueError,RecursionError):raise ValueError('工程路径清单JSON无效') from None
                uploaded=request.files.getlist('files')
                if not isinstance(paths,list) or not 1<=len(paths)<=MAX_FILES or len(paths)!=len(uploaded) or any(not isinstance(p,str) for p in paths) or len(set(paths))!=len(paths):raise ValueError('工程文件与路径清单不匹配')
                entries={};total=0
                for path,file in zip(paths,uploaded):
                    data=file.stream.read(MAX_FILE+1);total+=len(data)
                    if len(data)>MAX_FILE or total>MAX_TOTAL:raise ValueError('工程文件或总大小超限')
                    entries[path]=data
                value=service.prepare_project('目录工程',None,request.form.get('goal',''),actor_id=session['actor_id'],request_key=request.form['request_key'],entries=entries)
            else:raise ValueError('请选择单个ZIP或一份工程目录')
            return jsonify(value),201
        except ValueError as exc:return jsonify(error=str(exc),code='UPLOAD_INPUT_INVALID'),400
