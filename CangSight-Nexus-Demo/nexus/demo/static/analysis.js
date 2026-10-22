'use strict';
const AnalysisUI=(()=>{
  const el=id=>document.getElementById(id),{AnalysisSession,layoutGraph,sliceLines,sliceView,pointSlice}=AnalysisCore,session=new AnalysisSession();
  const labels={COMPLETE:'结果已返回',PARTIAL:'部分结果',FAILED:'分析失败',IN_DOUBT:'待核实',RUNNING:'分析中',READY:'待分析',VALID:'有效结构',EMPTY:'空结果',INVALID:'结果无效',UNAVAILABLE:'不可用'};
  const toolLabels={sympas_slice:'静态切片',sympas_slice_table:'静态切片表',sympas_dep_graph:'数据依赖',ast_symbol_extractor:'符号结构'};
  let initialized=false,samples=[],selectedSample=null,restoredId=null,source=null,upload=null,variable='',focusedLine=null,focusedNode=null,zoom=1,graphLayout=null,pollTimer=null,loadBusy=false,targetLine=null,sliceMode='table';
  const make=(tag,className,text)=>{const node=document.createElement(tag);if(className)node.className=className;if(text!==undefined)node.textContent=text;return node;};
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
  function adoptMode(report){sliceMode=report?.point_graph?.status==='VALID'?'point':'table';}
  function currentPoint(){return pointSlice(session.report,targetLine);}
  function includedLines(){return sliceMode==='point'?new Set(currentPoint().lines):sliceLines(session.report,variable);}
  function clearSelection(){sliceMode='table';variable='';focusedLine=null;focusedNode=null;zoom=1;graphLayout=null;}
  async function selectSample(id){
    if(!allowedSelection())return;const token=session.select();selectedSample=id;restoredId=null;upload=null;source=null;targetLine=null;clearSelection();render();
    try{const data=await request('/analysis/samples/'+id);if(token!==session.epoch)return;source=data.source;targetLine=reportLine(data.snapshot||{source});session.apply(token,data.snapshot||{status:'PREVIEW',source,observations:[],origin:'SAMPLE'});adoptMode(data.snapshot);render();}
    catch(error){if(token===session.epoch){session.fail(token);toast(error.message);render();}}
  }
  async function chooseUpload(file){
    if(!file||!allowedSelection())return;const token=session.select();selectedSample=null;restoredId=null;source=null;upload=null;targetLine=null;clearSelection();render();
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
    const token=session.start();if(token===null)return;clearSelection();render();
    try{
      const requestKey=crypto.randomUUID();let body;
      if(upload){body=new FormData();body.append('file',upload);body.append('request_key',requestKey);body.append('consent','true');body.append('slice_line',String(targetLine));}
      else body=selectedSample?{sample_id:selectedSample,request_key:requestKey,slice_line:targetLine}:{analysis_id:restoredId,request_key:requestKey,slice_line:targetLine};
      const job=await request('/api/analysis',body);if(token!==session.epoch)return;
      session.apply(token,{id:job.id,status:'READY',origin:upload?'UPLOAD':'SAMPLE',source,observations:[],slice_scope:'VARIABLE_TABLE',slice_criterion:{line:targetLine,direction:'Bwd',method:'SymPas'}});
      await poll(job.id,token);
    }catch(error){if(token===session.epoch){session.fail(token);session.report={status:'IN_DOUBT',source,observations:[],error:error.message};render();toast(error.message);await refreshHistory();}}
  }
  async function poll(identity,token){
    clearTimeout(pollTimer);
    try{
      const report=await request('/api/analysis/'+identity);if(token!==session.epoch)return;
      if(!session.apply(token,report))return;source=report.source;targetLine=reportLine(report);adoptMode(report);render();
      if(session.busy)pollTimer=setTimeout(()=>poll(identity,token),700);else await refreshHistory();
    }catch(error){if(token===session.epoch){session.fail(token);session.report={...session.report,status:'IN_DOUBT',error:error.message};render();toast(error.message);}}
  }
  async function refreshHistory(){
    try{const data=await request('/api/analysis');el('analysis-history').replaceChildren(make('option','', '最近分析'),...data.jobs.map(job=>{const o=make('option','',job.filename+(job.slice_scope==='VARIABLE_TABLE'?' · 变量切片表 · 定位 L':' · L')+(job.slice_criterion?.line||'?')+' · '+(labels[job.status]||job.status));o.value=job.id;return o;}));el('analysis-history').options[0].value='';}
    catch{/* History may be unavailable; public samples remain usable. */}
  }
  async function restore(identity){
    if(!identity||!allowedSelection())return;const token=session.select();clearSelection();upload=null;selectedSample=null;restoredId=identity;source=null;targetLine=null;loadBusy=true;render();
    try{const report=await request('/api/analysis/'+identity);if(!session.apply(token,report))return;source=report.source;targetLine=reportLine(report);adoptMode(report);render();if(session.busy)pollTimer=setTimeout(()=>poll(identity,token),700);}
    catch(error){if(token===session.epoch)toast(error.message);}finally{if(token===session.epoch){loadBusy=false;render();}}
  }
  function observation(tool){return session.report?.observations?.find(o=>o.tool===tool);}
  function render(){
    const report=session.report,busy=session.busy||loadBusy,snapshot=report?.display_origin==='SAMPLE_SNAPSHOT';
    const bound=report?.display_origin==='REGISTERED_BOUND',pointMode=sliceMode==='point',point=currentPoint();
    el('analysis-slice-mode').value=sliceMode;el('analysis-slice-mode').disabled=busy||!source;
    el('analysis-run').disabled=busy||!source||bound;el('analysis-run').textContent=bound?'修复依据 · 只读':busy?'分析中':report?.observations?.length?'重新分析':'分析';el('analysis-upload-open').disabled=busy;el('analysis-file').disabled=busy;el('analysis-history').disabled=busy;
    el('analysis-filename').textContent=report?.bound_path||source?.filename||'选择样例或上传 .cj';el('analysis-origin').textContent=bound?(report.bound_label||'修复基线'):snapshot?'样例快照':upload||report?.origin==='UPLOAD'?'上传':'本地样例';
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
    if(el('analysis-view').hidden===false){el('source-badge').textContent=snapshot?'样例快照':'课题组 MCP';el('source-badge').dataset.origin=snapshot?'ANALYSIS_SNAPSHOT':'ANALYSIS_LIVE';}
    const graph=observation('sympas_dep_graph'),symbols=observation('ast_symbol_extractor');
    const view=sliceView(report),sliceData=view.slices,graphData=pointMode?(report?.point_graph?.status==='VALID'?report.point_graph.graph:null):graph?.status==='VALID'?graph.data.graphs[0]:null;
    el('analysis-graph-title').textContent=pointMode?'程序依赖 PDG':'数据依赖 DDG';
    el('analysis-graph').setAttribute('aria-label',pointMode?'程序依赖图':'数据依赖图');
    el('analysis-slice-metric-label').textContent=pointMode?'切片行数':'切片变量';
    el('analysis-slice-count').textContent=pointMode?(point.status==='VALID'?point.lines.length:'—'):Object.keys(sliceData).length?Object.keys(sliceData).length:'—';el('analysis-node-count').textContent=graphData?.nodes?.length??'—';el('analysis-edge-count').textContent=graphData?.edges?.length??'—';el('analysis-duration').textContent=report?.elapsed_ms!==undefined&&report?.elapsed_ms!==null?(report.elapsed_ms/1000).toFixed(2)+'s':'—';
    const derived=report?.derived_slice;
    el('analysis-slice-note').hidden=pointMode?false:!derived;
    el('analysis-slice-note').classList.toggle('point-valid',pointMode&&point.status==='VALID');
    el('analysis-slice-note').textContent=pointMode?(point.status==='VALID'?'MCP PDG → 本地后向遍历 · '+point.lines.length+' 行':point.reason):view.recovered?'日志解析恢复 · 原引擎检查未通过。已核对文件及行号，仅作辅助展示。':derived?'日志解析被拒绝 · '+derived.reason:'';
    if(!Object.hasOwn(sliceData,variable))variable=Object.keys(sliceData)[0]||'';
    el('analysis-variable').replaceChildren(...(variable?Object.keys(sliceData).map(name=>{const o=make('option','',name);o.value=name;return o;}):[make('option','','无有效切片')]));el('analysis-variable').hidden=pointMode;el('analysis-variable').disabled=pointMode||!variable;
    el('analysis-point-target').hidden=!pointMode;el('analysis-point-target').textContent='目标 L'+targetLine;el('analysis-variable').value=variable;
    el('analysis-line-count').textContent=source?source.line_count+' 行':'—';el('analysis-source-hash').textContent=source?.source_sha256?.slice(0,16)||'—';renderSource();renderGraph(graphData);
    el('analysis-tools').replaceChildren(...(observation('sympas_slice_table')||tableMode?['sympas_slice_table','sympas_dep_graph','ast_symbol_extractor']:['sympas_slice','sympas_dep_graph','ast_symbol_extractor']).map(tool=>{const o=observation(tool),recovered=tool==='sympas_slice'&&view.recovered,card=make('div','analysis-tool');card.append(make('span','',toolLabels[tool]),make('span','status '+(recovered?'pending':o?.status==='VALID'?'good':o?.status==='FAILED'?'bad':'neutral'),recovered?'日志解析恢复':labels[o?.status]||'未运行'));return card;}));
    const symbolData=symbols?.status==='VALID'?symbols.data.symbols:[];el('analysis-symbol-count').textContent=String(symbolData.length);el('analysis-symbols').replaceChildren(...symbolData.map(item=>{const row=make('div','analysis-symbol');row.append(make('code','',item.symbol),make('span','',item.appears_in.join(' · ')));return row;}));if(!symbolData.length)el('analysis-symbols').append(make('div','analysis-empty','暂无有效结构'));
    const downloadable=report?.id&&!['READY','RUNNING'].includes(report.status)&&report.observations?.length;
    el('analysis-download').hidden=!downloadable;
    if(downloadable)el('analysis-download').href=report.evidence_url||(snapshot?'/analysis/samples/'+selectedSample+'/evidence':'/api/analysis/'+report.id+'/evidence');
    const pointDownload=pointMode&&!busy&&point.status==='VALID'&&report?.point_slice_url;
    el('analysis-point-download').hidden=!pointDownload;el('analysis-point-download').href=pointDownload?report.point_slice_url+'?line='+targetLine+'&download=1':'';
    const cg=report?.callgraph,cgReady=!busy&&cg?.status==='SAVED'&&cg.source_sha256===source?.source_sha256&&cg.view_url&&cg.download_url;
    el('analysis-callgraph-status').textContent=cgReady?'MCP 原生 · 已保存':busy?'等待本次分析':snapshot?'快照未包含 SVG · 重新分析获取':cg?.reason||'尚未取得调用图 SVG';
    for(const [id,url] of [['analysis-callgraph-open',cg?.view_url],['analysis-callgraph-download',cg?.download_url]]){
      el(id).hidden=!cgReady;el(id).href=cgReady?url:'';
    }
  }
  function renderSource(){
    const lines=source?.code?.split(/\r\n|\n|\r/)||[],included=includedLines(),recovered=sliceMode!=='point'&&sliceView(session.report).recovered;if(lines.at(-1)==='')lines.pop();
    el('analysis-source').replaceChildren(...lines.map((text,index)=>{const line=index+1,row=make('button','analysis-source-line'+(included.has(line)?' is-slice'+(recovered?' is-recovered':''):'')+(focusedLine===line?' is-focused':'')+(targetLine===line?' is-target-line':''));row.type='button';row.dataset.line=String(line);row.setAttribute('aria-label','源码第'+line+'行');const content=make('code');if(typeof highlightCode==='function')highlightCode(content,text||' ');else content.textContent=text||' ';row.append(make('span','analysis-line-number',String(line)),content);row.onclick=()=>{if(session.report?.display_origin!=='REGISTERED_BOUND'||sliceMode==='point')chooseTarget(line);focusedLine=line;focusedNode=null;renderSource();updateGraphSelection();el('analysis-node-detail').textContent='L'+line+' · '+text;};return row;}));
  }
  function svgElement(tag,attributes={},text){const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [key,value] of Object.entries(attributes))node.setAttribute(key,String(value));if(text!==undefined)node.textContent=text;return node;}
  function renderGraph(graph){
    const container=el('analysis-graph');container.replaceChildren();
    if(!graph){graphLayout=null;container.append(make('div','analysis-empty',sliceMode==='point'?currentPoint().reason:observation('sympas_dep_graph')?.reason||'等待依赖结构'));el('analysis-node-detail').textContent='选择节点';return;}
    graphLayout=layoutGraph(graph);const positions=new Map(graphLayout.nodes.map(n=>[n.id,n]));const svg=svgElement('svg',{viewBox:`0 0 ${graphLayout.width} ${graphLayout.height}`,role:'group','aria-label':sliceMode==='point'?'仓颉程序依赖图':'仓颉数据依赖图'});
    const defs=svgElement('defs'),marker=svgElement('marker',{id:'analysis-arrow',viewBox:'0 0 10 10',refX:8,refY:5,markerWidth:5,markerHeight:5,orient:'auto-start-reverse'});marker.append(svgElement('path',{d:'M 0 0 L 10 5 L 0 10 z',fill:'currentColor'}));defs.append(marker);svg.append(defs);
    for(const edge of graphLayout.edges){const from=positions.get(edge.from),to=positions.get(edge.to),x1=from.x+from.width,y1=from.y+26,x2=to.x,y2=to.y+26,curve=Math.max(40,Math.abs(x2-x1)/2);svg.append(svgElement('path',{d:`M${x1},${y1} C${x1+curve},${y1} ${x2-curve},${y2} ${x2},${y2}`,class:'analysis-edge','data-from':edge.from,'data-to':edge.to,'marker-end':'url(#analysis-arrow)'}));}
    for(const node of graphLayout.nodes){const group=svgElement('g',{class:'analysis-node'+(node.line?' source-node':''),transform:`translate(${node.x} ${node.y})`,tabindex:0,role:'button','aria-label':node.label,'data-node-id':node.id,'data-line':node.line||''});group.append(svgElement('rect',{width:node.width,height:node.height,rx:8}));group.append(svgElement('title',{},node.label));group.append(svgElement('text',{x:12,y:19,class:'analysis-node-meta'},node.line?'L'+node.line:node.id));let label=node.label.replace(/^\[L\d+\]:\s*/,'');if(label.length>28)label=label.slice(0,27)+'…';group.append(svgElement('text',{x:12,y:38},label));const choose=()=>{if(sliceMode==='point'&&node.line!==null)chooseTarget(node.line);focusedNode=node.id;focusedLine=node.line;renderSource();updateGraphSelection();el('analysis-node-detail').textContent=node.label;const row=el('analysis-source').querySelector(`[data-line="${node.line}"]`);row?.scrollIntoView({block:'nearest',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});};group.onclick=choose;group.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();choose();}};svg.append(group);}
    container.append(svg);sizeGraph();updateGraphSelection();
  }
  function sizeGraph(){const svg=el('analysis-graph').querySelector('svg');if(!svg||!graphLayout)return;svg.style.width=Math.max(el('analysis-graph').clientWidth-24,graphLayout.width*.72*zoom)+'px';svg.style.height=Math.max(350,graphLayout.height*.85*zoom)+'px';}
  function updateGraphSelection(){
    const point=currentPoint(),pointNodes=new Set(point.node_ids),included=includedLines(),recovered=sliceMode!=='point'&&sliceView(session.report).recovered;el('analysis-graph').querySelectorAll('.analysis-node').forEach(node=>{node.classList.toggle('selected',focusedNode?node.dataset.nodeId===focusedNode:focusedLine!==null&&Number(node.dataset.line)===focusedLine);node.classList.toggle('in-slice',sliceMode==='point'?pointNodes.has(node.dataset.nodeId):included.has(Number(node.dataset.line)));node.classList.toggle('log-recovered',recovered);});
    el('analysis-graph').querySelectorAll('.analysis-edge').forEach(edge=>edge.classList.toggle('selected',sliceMode==='point'?pointNodes.has(edge.dataset.from)&&pointNodes.has(edge.dataset.to):!!focusedNode&&(edge.dataset.from===focusedNode||edge.dataset.to===focusedNode)));
  }
  function evidence(){
    const report=session.report,box=el('analysis-evidence-content');box.replaceChildren();
    if(!report){box.textContent='尚未生成分析结果';}else{
      const info=make('dl','analysis-evidence-info');for(const [label,text] of [['来源',report.display_origin==='SAMPLE_SNAPSHOT'?'已记录样例快照':report.display_origin==='REGISTERED_BOUND'?(report.bound_label||'修复基线'):report.origin==='UPLOAD'?'上传文件 · 本次请求':'本地样例 · 本次请求'],['文件',source?.filename],['切片范围',sliceMode==='point'?'语句级 · L'+targetLine+' · 本地PDG后向遍历':report.slice_scope==='VARIABLE_TABLE'?'变量切片表 · 后向 Bwd · 定位 L'+reportLine(report):'L'+reportLine(report)+' · 后向 Bwd'],['SHA-256',source?.source_sha256],['分析标识',report.id||'—'],['生成时间',report.created_at?new Date(report.created_at).toLocaleString('zh-CN'):'—']])info.append(make('dt','',label),make('dd','',text||'—'));box.append(info);
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
  el('analysis-slice-mode').onchange=event=>{if(session.busy||loadBusy)return;sliceMode=event.target.value==='point'?'point':'table';focusedNode=null;render();};
  el('analysis-target-line').oninput=event=>{const n=Number(event.target.value);if(Number.isInteger(n)&&source&&n>=1&&n<=source.line_count)chooseTarget(n);};
  el('analysis-target-line').onchange=event=>chooseTarget(event.target.value);
  el('analysis-upload-open').onclick=()=>el('analysis-file').click();el('analysis-file').onchange=event=>{chooseUpload(event.target.files[0]);event.target.value='';};el('analysis-run').onclick=run;
  el('analysis-variable').onchange=event=>{variable=event.target.value;renderSource();updateGraphSelection();};el('analysis-history').onchange=event=>restore(event.target.value);
  el('analysis-zoom-in').onclick=()=>{zoom=Math.min(2.5,zoom+.2);sizeGraph();};el('analysis-zoom-out').onclick=()=>{zoom=Math.max(.35,zoom-.2);sizeGraph();};el('analysis-fit').onclick=()=>{zoom=.6;sizeGraph();el('analysis-graph').scrollTo(0,0);};el('analysis-evidence-open').onclick=evidence;
  function openBound(report){
    if(!allowedSelection())return false;
    const token=session.select();clearSelection();selectedSample=null;restoredId=null;upload=null;
    source=report.source;targetLine=reportLine(report);session.apply(token,report);adoptMode(report);render();return true;
  }
  return {show,openBound};
})();
