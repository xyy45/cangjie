'use strict';
const AnalysisUI=(()=>{
  const el=id=>document.getElementById(id),{AnalysisSession,sliceLines,sliceView,pointSlice}=AnalysisCore,session=new AnalysisSession();
  const labels={COMPLETE:'结果已返回',PARTIAL:'部分结果',FAILED:'分析失败',IN_DOUBT:'待核实',RUNNING:'分析中',READY:'待分析',VALID:'有效结构',EMPTY:'空结果',INVALID:'结果无效',UNAVAILABLE:'不可用'};
  const toolLabels={sympas_slice:'静态切片',sympas_slice_table:'静态切片表',sympas_dep_graph:'数据依赖',ast_symbol_extractor:'符号结构'};
  let initialized=false,samples=[],selectedSample=null,restoredId=null,source=null,upload=null,variable='',focusedLine=null,focusedNode=null,nativeKind='Ddg',pollTimer=null,loadBusy=false,targetLine=null,sliceMode='table',cacheReuse=null;
  const make=(tag,className,text)=>{const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;};
  const gallery=typeof NativeGraphUI==='undefined'?null:NativeGraphUI.mount({onSelect(kind){nativeKind=kind;render();}});
  async function request(path,body){
    const options=body===undefined?{}:{method:'POST',headers:{Origin:location.origin,'X-CSRF-Token':csrf},body};
    if(body&&!(body instanceof FormData)){options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
    const response=await fetch(path,options);let data;try{data=await response.json();}catch{throw Error('响应不可用，请核对状态');}
    if(!response.ok){const error=Error(data.error||'分析请求失败');error.code=data.code;throw error;}return data;
  }
  function allowedSelection(){if(session.busy||loadBusy){toast('请等待当前分析');return false;}return true;}
  function reportLine(report){return report?.slice_criterion?.line||Math.min(3,report?.source?.line_count||source?.line_count||1);}
  function chooseTarget(value){
    if(session.busy||loadBusy||session.report?.display_origin==='REGISTERED_BOUND'&&sliceMode!=='point')return;
    const line=Number(value);if(Number.isInteger(line)&&source&&line>=1&&line<=source.line_count){targetLine=line;focusedLine=line;focusedNode=null;}else toast('请选择源码范围内的整数行号');
    render();
  }
  function currentPoint(){return pointSlice(session.report,targetLine);}
  function includedLines(){return sliceMode==='point'?new Set(currentPoint().lines):sliceLines(session.report,variable);}
  function clearSelection(){variable='';focusedLine=null;focusedNode=null;}
  async function selectSample(id){
    if(!allowedSelection())return;const token=session.select();cacheReuse=null;selectedSample=id;restoredId=null;upload=null;source=null;targetLine=null;clearSelection();render();
    try{const data=await request('/analysis/samples/'+id);if(token!==session.epoch)return;source=data.source;targetLine=reportLine(data.snapshot||{source});session.apply(token,data.snapshot||{status:'PREVIEW',source,observations:[],origin:'SAMPLE'});render();}
    catch(error){if(token===session.epoch){session.fail(token);toast(error.message);render();}}
  }
  async function chooseUpload(file){
    if(!file||!allowedSelection())return;const token=session.select();cacheReuse=null;selectedSample=null;restoredId=null;source=null;upload=null;targetLine=null;clearSelection();render();
    try{
      if(!file.name.endsWith('.cj')||file.size>65536||file.size===0)throw Error('请选择不超过64KiB的 .cj 文件');
      const bytes=await file.arrayBuffer(),code=new TextDecoder('utf-8',{fatal:true}).decode(bytes);
      const lines=code.split(/\r\n|\n|\r/);if(!code.trim()||code.includes('\0')||lines.length-(lines.at(-1)===''?1:0)>1000)throw Error('源码为空或超过1000行');
      const hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join('');
      if(token!==session.epoch)return;source={filename:file.name,code,line_count:lines.length-(lines.at(-1)===''?1:0),source_sha256:hash};upload=file;targetLine=Math.min(3,source.line_count);el('analysis-consent').checked=false;render();
    }catch(error){if(token===session.epoch){toast(error instanceof TypeError?'源码必须为 UTF-8':error.message);render();}}
  }
  async function run(){
    if(session.busy||loadBusy||!source||session.report?.display_origin==='REGISTERED_BOUND')return;
    if(upload&&!el('analysis-consent').checked){toast('请确认发送至课题组 MCP');return;}
    const reuseCache=!session.report?.observations?.length;
    const token=session.start();if(token===null)return;cacheReuse=null;clearSelection();render();
    try{
      const requestKey=crypto.randomUUID();let body;
      if(upload){body=new FormData();body.append('file',upload);body.append('request_key',requestKey);body.append('consent','true');body.append('slice_line',String(targetLine));body.append('reuse_cache',String(reuseCache));}
      else body=selectedSample?{sample_id:selectedSample,request_key:requestKey,slice_line:targetLine,reuse_cache:reuseCache}:{analysis_id:restoredId,request_key:requestKey,slice_line:targetLine,reuse_cache:reuseCache};
      const job=await request('/api/analysis',body);if(token!==session.epoch)return;
      cacheReuse=job.cache_hit?{cache_hit:true,cached_at:job.cached_at}:null;
      session.apply(token,{id:job.id,status:'READY',origin:upload?'UPLOAD':'SAMPLE',source,observations:[],slice_scope:'VARIABLE_TABLE',slice_criterion:{line:targetLine,direction:'Bwd',method:'SymPas'}});
      await poll(job.id,token);
    }catch(error){if(token===session.epoch){session.fail(token);session.report={status:'IN_DOUBT',source,observations:[],error:error.message};render();toast(error.message);await refreshHistory();}}
  }
  async function poll(identity,token){
    clearTimeout(pollTimer);
    try{
      const report=await request('/api/analysis/'+identity);if(token!==session.epoch)return;
      if(!session.apply(token,cacheReuse?{...report,...cacheReuse}:report))return;source=report.source;targetLine=reportLine(report);render();
      if(session.busy)pollTimer=setTimeout(()=>poll(identity,token),700);else await refreshHistory();
    }catch(error){if(token===session.epoch){session.fail(token);session.report={...session.report,status:'IN_DOUBT',error:error.message};render();toast(error.message);}}
  }
  async function refreshHistory(){
    try{const data=await request('/api/analysis');el('analysis-history').replaceChildren(make('option','', '最近分析'),...data.jobs.map(job=>{const o=make('option','',job.filename+(job.slice_scope==='VARIABLE_TABLE'?' · 变量切片表 · 定位 L':' · L')+(job.slice_criterion?.line||'?')+' · '+(labels[job.status]||job.status));o.value=job.id;return o;}));el('analysis-history').options[0].value='';}
    catch{/* History may be unavailable; public samples remain usable. */}
  }
  async function restore(identity){
    if(!identity||!allowedSelection())return;const token=session.select();cacheReuse=null;clearSelection();upload=null;selectedSample=null;restoredId=identity;source=null;targetLine=null;loadBusy=true;render();
    try{const report=await request('/api/analysis/'+identity);if(!session.apply(token,report))return;source=report.source;targetLine=reportLine(report);render();if(session.busy)pollTimer=setTimeout(()=>poll(identity,token),700);}
    catch(error){if(token===session.epoch)toast(error.message);}finally{if(token===session.epoch){loadBusy=false;render();}}
  }
  function observation(tool){return session.report?.observations?.find(o=>o.tool===tool);}
  function render(){
    const report=session.report,busy=session.busy||loadBusy,snapshot=report?.display_origin==='SAMPLE_SNAPSHOT';
    const bound=report?.display_origin==='REGISTERED_BOUND',pointMode=sliceMode==='point',point=currentPoint();
    el('analysis-slice-mode').value=sliceMode;el('analysis-slice-mode').disabled=busy||!source;
    el('analysis-run').disabled=busy||!source||bound;el('analysis-run').textContent=bound?'修复依据 · 只读':busy?'分析中':report?.observations?.length?'重新分析':'分析';el('analysis-upload-open').disabled=busy;el('analysis-file').disabled=busy;el('analysis-history').disabled=busy;
    el('analysis-filename').textContent=report?.bound_path||source?.filename||'选择样例或上传 .cj';el('analysis-origin').textContent=report?.cache_hit?'缓存复用 · '+new Date(report.cached_at).toLocaleString('zh-CN'):bound?(report.bound_label||'修复基线'):snapshot?'样例快照':upload||report?.origin==='UPLOAD'?'上传':'本地样例';
    el('analysis-target-line').value=source?String(targetLine||Math.min(3,source.line_count)):'';
    el('analysis-target-line').max=String(source?.line_count||1);el('analysis-target-line').disabled=busy||!source||(bound&&!pointMode);
    const resultLine=report?.observations?.length?reportLine(report):null;
    const tableMode=report?.slice_scope==='VARIABLE_TABLE'||!!observation('sympas_slice_table')||!report?.observations?.length;
    el('analysis-target-label').textContent=pointMode?'切片目标行':tableMode?'源码定位行':'切片目标行';
    el('analysis-target-line').setAttribute('aria-label',pointMode?'切片目标行':tableMode?'源码定位行':'切片目标行');
    el('analysis-target-note').textContent=pointMode?'目标 L'+targetLine+' · PDG 后向依赖 · 语句级':tableMode&&source?'变量切片表 · 后向 Bwd · 定位 L'+targetLine+(bound?' · 当前版本只读':''):!source?'点击源码行选择目标':bound?'已记录 L'+targetLine+' · 后向切片 · 当前版本只读':resultLine&&resultLine!==targetLine?'当前显示 L'+resultLine+' 的结果；点击分析后请求 L'+targetLine+'。':'目标 L'+targetLine+' · 后向切片 · 点击分析发送请求';
    el('analysis-consent-label').hidden=!upload;el('analysis-consent').disabled=busy;
    el('analysis-samples').querySelectorAll('button').forEach(button=>{button.disabled=busy;button.classList.toggle('selected',button.dataset.sample===selectedSample);});
    el('analysis-status').textContent=busy?(toolLabels[report?.active_tool]?'分析中':'准备中'):(labels[report?.status]||'就绪');
    el('analysis-status').className='status '+(report?.status==='COMPLETE'?'good':report?.status==='PARTIAL'?'pending':['FAILED','IN_DOUBT'].includes(report?.status)?'bad':'neutral');
    el('analysis-active-tool').textContent=busy?(toolLabels[report?.active_tool]||''):report?.error?'请查看证据':'';
    if(el('analysis-view').hidden===false){el('source-badge').textContent=report?.cache_hit?'MCP · 缓存复用':snapshot?'样例快照':'课题组 MCP';el('source-badge').dataset.origin=report?.cache_hit?'ANALYSIS_CACHE':snapshot?'ANALYSIS_SNAPSHOT':'ANALYSIS_LIVE';}
    const graph=observation('sympas_dep_graph'),symbols=observation('ast_symbol_extractor');
    const view=sliceView(report),sliceData=view.slices,graphData=nativeKind==='Pdg'?(report?.point_graph?.status==='VALID'?report.point_graph.graph:null):nativeKind==='Ddg'&&graph?.status==='VALID'?graph.data.graphs[0]:null;
    el('analysis-graph-title').textContent=typeof NativeGraphUI==='undefined'?(pointMode?'程序依赖 PDG':'数据依赖 DDG'):NativeGraphUI.LABELS[nativeKind];
    el('analysis-graph').setAttribute('aria-label',pointMode?'程序依赖图':'数据依赖图');
    el('analysis-slice-metric-label').textContent=pointMode?'切片行数':'切片变量';
    el('analysis-slice-count').textContent=pointMode?(point.status==='VALID'?point.lines.length:'—'):Object.keys(sliceData).length?Object.keys(sliceData).length:'—';el('analysis-node-count').textContent=report?.native_graphs?.graphs?.[nativeKind]?.node_count??graphData?.nodes?.length??'—';el('analysis-edge-count').textContent=report?.native_graphs?.graphs?.[nativeKind]?.edge_count??graphData?.edges?.length??'—';el('analysis-duration').textContent=report?.elapsed_ms!==undefined&&report?.elapsed_ms!==null?(report.elapsed_ms/1000).toFixed(2)+'s':'—';
    const derived=report?.derived_slice;
    el('analysis-slice-note').hidden=pointMode?false:!derived;
    el('analysis-slice-note').classList.toggle('point-valid',pointMode&&point.status==='VALID');
    el('analysis-slice-note').textContent=pointMode?(point.status==='VALID'?'MCP PDG → 本地后向遍历 · '+point.lines.length+' 行':point.reason):view.recovered?'日志解析恢复 · 原引擎检查未通过。已核对文件及行号，仅作辅助展示。':derived?'日志解析被拒绝 · '+derived.reason:'';
    if(!Object.hasOwn(sliceData,variable))variable=Object.keys(sliceData)[0]||'';
    el('analysis-variable').replaceChildren(...(variable?Object.keys(sliceData).map(name=>{const o=make('option','',name);o.value=name;return o;}):[make('option','','无有效切片')]));el('analysis-variable').hidden=pointMode;el('analysis-variable').disabled=pointMode||!variable;
    el('analysis-point-target').hidden=!pointMode;el('analysis-point-target').textContent='目标 L'+targetLine;el('analysis-variable').value=variable;
    el('analysis-line-count').textContent=source?source.line_count+' 行':'—';el('analysis-source-hash').textContent=source?.source_sha256?.slice(0,16)||'—';renderSource();renderGraph(graphData);renderGraphNodes(graphData);
    el('analysis-tools').replaceChildren(...(observation('sympas_slice_table')||tableMode?['sympas_slice_table','sympas_dep_graph','ast_symbol_extractor']:['sympas_slice','sympas_dep_graph','ast_symbol_extractor']).map(tool=>{const o=observation(tool),recovered=tool==='sympas_slice'&&view.recovered,card=make('div','analysis-tool');card.append(make('span','',toolLabels[tool]),make('span','status '+(recovered?'pending':o?.status==='VALID'?'good':o?.status==='FAILED'?'bad':'neutral'),recovered?'日志解析恢复':labels[o?.status]||'未运行'));return card;}));
    const symbolData=symbols?.status==='VALID'?symbols.data.symbols:[];el('analysis-symbol-count').textContent=String(symbolData.length);el('analysis-symbols').replaceChildren(...symbolData.map(item=>{const row=make('div','analysis-symbol');row.append(make('code','',item.symbol),make('span','',item.appears_in.join(' · ')));return row;}));if(!symbolData.length)el('analysis-symbols').append(make('div','analysis-empty','暂无有效结构'));
    const downloadable=report?.id&&!['READY','RUNNING'].includes(report.status)&&report.observations?.length;
    el('analysis-download').hidden=!downloadable;
    if(downloadable)el('analysis-download').href=report.evidence_url||(snapshot?'/analysis/samples/'+selectedSample+'/evidence':'/api/analysis/'+report.id+'/evidence');
    const pointDownload=pointMode&&!busy&&point.status==='VALID'&&report?.point_slice_url;
    el('analysis-point-download').hidden=!pointDownload;el('analysis-point-download').href=pointDownload?report.point_slice_url+'?line='+targetLine+'&download=1':'';

  }
  function renderSource(){
    const lines=source?.code?.split(/\r\n|\n|\r/)||[],included=includedLines(),recovered=sliceMode!=='point'&&sliceView(session.report).recovered;if(lines.at(-1)==='')lines.pop();
    el('analysis-source').replaceChildren(...lines.map((text,index)=>{const line=index+1,row=make('button','analysis-source-line'+(included.has(line)?' is-slice'+(recovered?' is-recovered':''):'')+(focusedLine===line?' is-focused':'')+(targetLine===line?' is-target-line':''));row.type='button';row.dataset.line=String(line);row.setAttribute('aria-label','源码第'+line+'行');const content=make('code');if(typeof highlightCode==='function')highlightCode(content,text||' ');else content.textContent=text||' ';row.append(make('span','analysis-line-number',String(line)),content);row.onclick=()=>{if(session.report?.display_origin!=='REGISTERED_BOUND'||sliceMode==='point')chooseTarget(line);focusedLine=line;focusedNode=null;renderSource();updateGraphSelection();el('analysis-node-detail').textContent='L'+line+' · '+text;};return row;}));
  }
  function renderGraph(){if(gallery)gallery.render(session.report,nativeKind);else el('analysis-graph').replaceChildren();}
  function renderGraphNodes(graph){
    const details=el('analysis-graph-node-details'),list=el('analysis-graph-nodes');details.hidden=!graph?.nodes?.length;list.replaceChildren();
    for(const node of graph?.nodes||[]){const button=make('button','analysis-node-link',node.line?'L'+node.line+' · '+node.label:node.label);button.type='button';button.dataset.nodeId=node.id;button.dataset.line=node.line||'';button.title=node.label;
      button.onclick=()=>{if(sliceMode==='point'&&node.line!==null)chooseTarget(node.line);focusedNode=node.id;focusedLine=node.line;renderSource();updateGraphSelection();el('analysis-node-detail').textContent=node.label;el('analysis-source').querySelector(`[data-line="${node.line}"]`)?.scrollIntoView?.({block:'nearest'});};list.append(button);}
    updateGraphSelection();
  }
  function updateGraphSelection(){const pointNodes=new Set(currentPoint().node_ids),lines=includedLines();el('analysis-graph-nodes').querySelectorAll('button').forEach(node=>{node.classList.toggle('selected',focusedNode?node.dataset.nodeId===focusedNode:focusedLine!==null&&Number(node.dataset.line)===focusedLine);node.classList.toggle('in-slice',sliceMode==='point'?pointNodes.has(node.dataset.nodeId):lines.has(Number(node.dataset.line)));});}
  function evidence(){
    const report=session.report,box=el('analysis-evidence-content');box.replaceChildren();
    if(!report){box.textContent='尚未生成分析结果';}else{
      const info=make('dl','analysis-evidence-info');for(const [label,text] of [['来源',report.cache_hit?'同会话已验证 MCP 缓存 · 原分析时间 '+new Date(report.cached_at).toLocaleString('zh-CN'):report.display_origin==='SAMPLE_SNAPSHOT'?'已记录样例快照':report.display_origin==='REGISTERED_BOUND'?(report.bound_label||'修复基线'):report.origin==='UPLOAD'?'上传文件 · 本次请求':'本地样例 · 本次请求'],['文件',source?.filename],['切片范围',sliceMode==='point'?'语句级 · L'+targetLine+' · 本地PDG后向遍历':report.slice_scope==='VARIABLE_TABLE'?'变量切片表 · 后向 Bwd · 定位 L'+reportLine(report):'L'+reportLine(report)+' · 后向 Bwd'],['SHA-256',source?.source_sha256],['分析标识',report.id||'—'],['生成时间',report.created_at?new Date(report.created_at).toLocaleString('zh-CN'):'—']])info.append(make('dt','',label),make('dd','',text||'—'));box.append(info);
      for(const o of report.observations||[]){const section=make('section','analysis-evidence-tool');section.append(make('strong','',o.tool+' · '+(labels[o.status]||o.status)),make('p','',o.reason),make('code','',o.raw_sha256));box.append(section);}
      if(sliceMode==='point'){const p=currentPoint(),section=make('section','analysis-evidence-tool');section.append(make('strong','','按行切片 · '+(labels[p.status]||p.status)),make('p','',p.reason),make('p','','目标 L'+targetLine+'；种子节点 '+p.seed_nodes.join(', ')+'；源码行 '+p.lines.join(', ')),make('code','',p.algorithm+' · PDG SHA-256 '+(p.graph_sha256||'—')),make('p','','语句级依赖遍历；未声明完整跨函数分析。'));box.append(section);}
      const cg=report.callgraph;
      if(cg){const section=make('section','analysis-evidence-tool');section.append(make('strong','','函数调用图 Cg · '+(cg.status==='SAVED'?'MCP 原生 SVG':'不可用')),
        make('p','',cg.status==='SAVED'?'已绑定本次源码、分析标识与图工具原始响应。':cg.reason),make('code','',cg.sha256||'—'));box.append(section);}
      const derived=report.derived_slice;
      if(derived){const section=make('section','analysis-evidence-tool recovery-evidence');section.append(make('strong','',derived.status==='RECOVERED'?'本地派生 · 日志解析恢复':'本地派生 · 解析拒绝'),
        make('p','',derived.notice),make('p','',derived.reason),make('code','',derived.parser_version+' · 原始响应 SHA-256 '+derived.raw_sha256));
        if(derived.log_line_range)section.append(make('p','', '原始 raw_output 第 '+derived.log_line_range.join('–')+' 行；变量 '+Object.keys(derived.slices).length+' 个'));
        box.append(section);}
    }el('analysis-evidence-dialog').showModal();
  }
  async function show(){
    if(!initialized){initialized=true;const openingEpoch=session.epoch;try{samples=(await request('/analysis/samples')).samples;el('analysis-samples').replaceChildren(...samples.map(sample=>{const button=make('button','analysis-sample-button',sample.title);button.dataset.sample=sample.id;button.onclick=()=>selectSample(sample.id);return button;}));if(!source&&session.epoch===openingEpoch&&samples.length)await selectSample(samples[0].id);}catch(error){initialized=false;toast(error.message);}}
    render();refreshHistory();
  }
  el('analysis-slice-mode').onchange=event=>{if(session.busy||loadBusy)return;sliceMode=event.target.value==='point'?'point':'table';nativeKind=sliceMode==='point'?'Pdg':'Ddg';focusedNode=null;render();};
  el('analysis-target-line').oninput=event=>{const n=Number(event.target.value);if(Number.isInteger(n)&&source&&n>=1&&n<=source.line_count)chooseTarget(n);};
  el('analysis-target-line').onchange=event=>chooseTarget(event.target.value);
  el('analysis-upload-open').onclick=()=>el('analysis-file').click();el('analysis-file').onchange=event=>{chooseUpload(event.target.files[0]);event.target.value='';};el('analysis-run').onclick=run;
  el('analysis-variable').onchange=event=>{variable=event.target.value;renderSource();updateGraphSelection();};el('analysis-history').onchange=event=>restore(event.target.value);
  el('analysis-zoom-in').onclick=()=>gallery?.zoom(.5);el('analysis-zoom-out').onclick=()=>gallery?.zoom(-.5);el('analysis-fit').onclick=()=>gallery?.fit();el('analysis-fullscreen').onclick=()=>gallery?.fullscreen();el('analysis-evidence-open').onclick=evidence;

  function openBound(report,{line=null}={}){
    if(!allowedSelection())return false;
    if(line!==null&&(!Number.isInteger(line)||line<1||line>report?.source?.line_count)){toast('定位行号不属于此源码');return false;}
    const token=session.select();cacheReuse=null;clearSelection();selectedSample=null;restoredId=null;upload=null;
    source=report.source;targetLine=line??reportLine(report);focusedLine=line;if(line!==null){sliceMode='point';nativeKind='Pdg';}session.apply(token,report);render();return true;
  }
  return {show,openBound};
})();
