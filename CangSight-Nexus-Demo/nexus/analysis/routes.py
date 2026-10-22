"""Local session-scoped analysis routes; public views contain only registered samples."""
import threading
import io
import re
from flask import jsonify,request,session,send_file
from nexus.analysis import samples
from nexus.analysis.point import point_slice,point_archive
from nexus.analysis.normalize import MAX_SOURCE,validate_source
from nexus.analysis.service import AnalysisService,AnalysisConflict


def svg_links(result,base):
    result['point_slice_url']=base+'/point-slice'
    if result.get('callgraph',{}).get('status')=='SAVED':
        result['callgraph']=dict(result['callgraph'],view_url=base+'/callgraph.svg',download_url=base+'/callgraph.svg?download=1')
    return result


def svg_response(raw,identity):
    response=send_file(io.BytesIO(raw),mimetype='image/svg+xml',as_attachment=request.args.get('download')=='1',
        download_name=f'CangSight-callgraph-{identity}.svg')
    response.headers.update({'Content-Security-Policy':"sandbox; default-src 'none'; style-src 'unsafe-inline'",
        'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','Cache-Control':'private, no-store'})
    return response



def point_response(result,archive):
    if (set(request.args)-{'line','download'} or len(request.args.getlist('line'))!=1 or
            not re.fullmatch(r'[1-9][0-9]{0,3}',request.args['line']) or
            len(request.args.getlist('download'))>1 or request.args.get('download','0') not in ('0','1')):
        return jsonify(error='请提供有效的切片目标行'),400
    try:derived=point_slice(result,int(request.args['line']))
    except ValueError as exc:return jsonify(error=str(exc)),400
    if request.args.get('download')!='1':return jsonify(derived)
    if derived['status']!='VALID':return jsonify(error=derived['reason']),409
    stream=point_archive(archive(),result,derived['line'])
    return send_file(stream,mimetype='application/zip',as_attachment=True,
        download_name='CangSight-point-slice-L'+str(derived['line'])+'.zip')


def register_analysis(app,store):
    service=AnalysisService(store.root);app.extensions['analysis_service']=service
    app.config['RUN_ANALYSES']=True

    @app.get('/analysis/samples')
    def analysis_samples():return jsonify(samples=samples.catalog())

    @app.get('/analysis/samples/<identity>')
    def analysis_sample(identity):
        try:
            result=samples.snapshot(identity)
            return jsonify(**samples.sample(identity),snapshot=svg_links(result,request.path) if result else None)
        except ValueError:return jsonify(error='样例不可用'),404

    @app.get('/analysis/samples/<identity>/evidence')
    def analysis_sample_evidence(identity):
        try:return send_file(samples.snapshot_archive(identity),mimetype='application/zip',as_attachment=True,download_name=f'CangSight-analysis-sample-{identity}.zip')
        except (ValueError,LookupError):return jsonify(error='样例证据不可用'),404

    @app.get('/analysis/samples/<identity>/callgraph.svg')
    def analysis_sample_svg(identity):
        try:return svg_response(samples.callgraph_bytes(identity),identity)
        except (ValueError,LookupError,OSError):return jsonify(error='样例调用图不可用'),404

    @app.get('/analysis/samples/<identity>/point-slice')
    def analysis_sample_point(identity):
        try:
            result=samples.snapshot(identity)
            if not result:raise LookupError('暂无样例快照')
            return point_response(result,lambda:samples.snapshot_archive(identity))
        except (ValueError,LookupError):return jsonify(error='样例切片不可用'),404

    @app.post('/api/analysis')
    def analysis_start():
        try:
            if request.is_json:
                body=request.get_json()
                if not isinstance(body,dict):raise ValueError('请选择分析来源')
                line=body.get('slice_line')
                if 'slice_line' in body and type(line) is not int:raise ValueError('目标行必须是整数')
                fields=set(body)-{'slice_line'}
                if fields=={'sample_id','request_key'}:
                    source=samples.sample(body['sample_id'])['source'];origin='SAMPLE'
                elif fields=={'analysis_id','request_key'}:
                    previous=service.get(body['analysis_id'],actor_id=session['actor_id'])
                    source=previous['source'];origin=previous['origin']
                    if 'slice_line' not in body:line=previous['slice_criterion']['line']
                else:raise ValueError('请选择分析来源')
                key=body['request_key']
            else:
                if set(request.form)-{'slice_line'}!={'request_key','consent'} or request.form['consent']!='true' or set(request.files)!={'file'} or len(request.files.getlist('file'))!=1:
                    raise ValueError('请选择单个.cj并确认发送至课题组MCP')
                file=request.files['file'];source=validate_source(file.filename,file.stream.read(MAX_SOURCE+1));origin='UPLOAD';key=request.form['request_key']
                line=None
                if 'slice_line' in request.form:
                    if not re.fullmatch(r'[1-9][0-9]{0,3}',request.form['slice_line']):raise ValueError('目标行必须是整数')
                    line=int(request.form['slice_line'])
            job=service.create(source,actor_id=session['actor_id'],request_key=key,origin=origin,slice_line=line)
        except LookupError:return jsonify(error='分析记录不存在'),404
        except AnalysisConflict as exc:return jsonify(error=str(exc),code='ANALYSIS_BUSY'),409
        except (ValueError,TypeError,KeyError):return jsonify(error='请选择UTF-8 .cj（最多64KiB、1000行），并确认分析来源',code='ANALYSIS_INPUT_INVALID'),400
        if app.config['RUN_ANALYSES']:
            threading.Thread(target=service.run,args=(job['id'],),daemon=True).start()
        return jsonify(job),202

    @app.get('/api/analysis')
    def analysis_history():return jsonify(jobs=service.list(session['actor_id']))

    @app.get('/api/analysis/<identity>')
    def analysis_detail(identity):
        try:return jsonify(svg_links(service.get(identity,actor_id=session['actor_id']),request.path))
        except LookupError:return jsonify(error='分析记录不存在'),404
        except ValueError:return jsonify(error='源码或分析证据摘要变化',code='ANALYSIS_EVIDENCE_CHANGED'),409

    @app.get('/api/analysis/<identity>/point-slice')
    def analysis_point(identity):
        try:
            result=service.get(identity,actor_id=session['actor_id'])
            return point_response(result,lambda:service.export(identity,actor_id=session['actor_id']))
        except LookupError:return jsonify(error='分析记录不存在'),404
        except ValueError:return jsonify(error='源码或PDG证据变化'),409

    @app.get('/api/analysis/<identity>/callgraph.svg')
    def analysis_svg(identity):
        try:return svg_response(service.callgraph_bytes(identity,actor_id=session['actor_id']),identity)
        except LookupError:return jsonify(error='调用图 SVG 不可用'),404
        except (ValueError,OSError):return jsonify(error='调用图证据已变化',code='ANALYSIS_EVIDENCE_CHANGED'),409

    @app.get('/api/analysis/<identity>/evidence')
    def analysis_evidence(identity):
        try:return send_file(service.export(identity,actor_id=session['actor_id']),mimetype='application/zip',as_attachment=True,download_name=f'CangSight-analysis-{identity}.zip')
        except LookupError:return jsonify(error='分析记录不存在'),404
        except ValueError:return jsonify(error='分析未结束或证据已变化',code='ANALYSIS_EVIDENCE_CHANGED'),409

    @app.errorhandler(413)
    def analysis_too_large(error):return jsonify(error='请求超过本机限制；上传源码最多64KiB',code='SOURCE_TOO_LARGE'),413
