"""Preparing and confirming uploads does not invoke tools or a model."""
from flask import request,session,jsonify
from nexus.analysis.normalize import MAX_SOURCE
from nexus.uploads.service import UploadService


def register_uploads(app,store):
    service=UploadService(store);app.extensions['upload_service']=service

    @app.get('/api/uploads/repair')
    def upload_list():return jsonify(uploads=service.list(actor_id=session['actor_id']))

    @app.get('/api/uploads/repair/<identity>')
    def upload_get(identity):return jsonify(service.get(identity,actor_id=session['actor_id']))

    @app.post('/api/uploads/repair')
    def upload_prepare():
        try:
            if set(request.files)!={'file'} or len(request.files.getlist('file'))!=1 or set(request.form)!={'goal','request_key'}:
                raise ValueError('请选择单个.cj并填写预期行为')
            file=request.files['file']
            value=service.prepare(file.filename,file.stream.read(MAX_SOURCE+1),request.form['goal'],
                actor_id=session['actor_id'],request_key=request.form['request_key'])
            return jsonify(value),201
        except ValueError as exc:return jsonify(error=str(exc),code='UPLOAD_INPUT_INVALID'),400

    @app.post('/api/uploads/repair/<identity>/confirm')
    def upload_confirm(identity):
        try:
            body=request.get_json()
            if not isinstance(body,dict) or set(body)!={'expected_version','function','examples_json','consent'}:
                raise ValueError('请确认函数、示例版本与发送许可')
            return jsonify(service.confirm(identity,actor_id=session['actor_id'],**body))
        except ValueError as exc:return jsonify(error=str(exc),code='UPLOAD_INPUT_INVALID'),400
