'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function page(callgraph,native=false,{omitPointOnResult=false,cacheHit=false,sourceOverride=null,reportOverrides={}}={}){
 const nodes=new Map();
 const element=()=>({children:[],textContent:'',value:'',hidden:false,disabled:false,dataset:{},style:{},showModal(){},classList:{toggle(){}},setAttribute(){},append(...xs){this.children.push(...xs);},replaceChildren(...xs){this.children=xs;},querySelectorAll(){return[];},querySelector(){return null;}});
 const get=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);};
 const source=sourceOverride||{filename:'f.cj',code:'func f(): Int64 {\n let x = 2\n return x\n}\n',line_count:4,source_sha256:'hash'};
 const requests=[],report={id:'saved',status:callgraph?'PARTIAL':'COMPLETE',callgraph,source,slice_criterion:{line:3,direction:'Bwd',method:'SymPas'},observations:[{tool:'sympas_slice',status:'VALID',data:{slices:{x:[2,3]}}}]};
 if(native){report.slice_scope='VARIABLE_TABLE';report.observations=[{tool:'sympas_slice_table',status:'VALID',data:{scope:'VARIABLE_TABLE',slices:{x:[2,3],a:[1]}}}];}
 if(native==='point'){report.point_slice_url='/api/analysis/saved/point-slice';report.point_graph={status:'VALID',source_sha256:'hash',raw_sha256:'raw',graph:{graph_type:'Pdg',nodes:[{id:'one',label:'[L2]: x = 2',line:2},{id:'two',label:'[L3]: return x',line:3}],edges:[{from:'one',to:'two'}]}};}
 if(native==='mcp'){report.analysis_profile=8;report.slice_scope='MCP_NATIVE';report.observations=[{tool:'sympas_slice',status:'VALID',data:{slices:{x:[2,3],a:[1]}}}];}
 Object.assign(report,reportOverrides);
 const ctx={document:{getElementById:get,createElement:element,createElementNS:element},crypto:require('node:crypto').webcrypto,TextDecoder,FormData,csrf:'csrf',URL,location:{origin:'http://localhost'},toast(){},setTimeout:()=>0,clearTimeout(){},fetch:async(url,options={})=>{
  requests.push({url,...options});let data;
  if(url==='/analysis/samples')data={samples:[{id:'s',title:'sample'}]};
  else if(url==='/analysis/samples/s')data={source,snapshot:{...report,callgraph:undefined,display_origin:'SAMPLE_SNAPSHOT'}};
  else if(url==='/api/analysis'&&options.method==='POST')data=cacheHit?{id:'job',cache_hit:true,cached_at:'2026-10-24T00:00:00+00:00'}:{id:'job'};
  else if(url==='/api/analysis/job'){data={...report,id:'job',slice_criterion:{line:2,direction:'Bwd',method:'SymPas'}};if(omitPointOnResult)delete data.point_graph;}
  else if(url==='/api/analysis/saved')data=report;
  else if(url==='/api/analysis')data={jobs:[]};else throw Error(url);
  return{ok:true,json:async()=>data};
 }};
 vm.createContext(ctx);
 for(const file of ['analysis-core.js','native-graphs.js','analysis.js'])vm.runInContext(fs.readFileSync('nexus/demo/static/'+file,'utf8'),ctx);
 return{get,requests,show:()=>vm.runInContext('AnalysisUI.show()',ctx),openBound:(line)=>{ctx.boundReport={...report,display_origin:'REGISTERED_BOUND'};ctx.boundLine=line;return vm.runInContext('AnalysisUI.openBound(boundReport,{line:boundLine})',ctx);}};
}

test('bound focus opens a source location without deriving a new local slice',()=>{
 const p=page(null,'mcp');assert.equal(p.openBound(2),true);assert.equal(p.get('analysis-target-line').value,'2');
 assert.equal(p.get('analysis-variable').value,'x');assert.equal(p.get('analysis-slice-count').textContent,2);
 assert.equal(p.openBound(999),false);assert.equal(p.get('analysis-target-line').value,'2');
});
test('changing request line preserves tool rows until an actual analysis request',async()=>{
 const {get,requests,show}=page(null,'mcp');await show();get('analysis-source').children[1].onclick();
 assert.match(get('analysis-target-note').textContent,/请求行号为 L3/);
 assert.match(get('analysis-source').children[2].className,/is-slice/);
 assert.equal(requests.filter(r=>r.method==='POST').length,0);
 await get('analysis-run').onclick();
 assert.equal(JSON.parse(requests.find(r=>r.method==='POST').body).slice_line,2);
});
test('original CG links remain available explicitly and clear on a source switch',async()=>{
 const cg={status:'SAVED',source_sha256:'hash',sha256:'svg',view_url:'/api/analysis/saved/callgraph.svg',download_url:'/api/analysis/saved/callgraph.svg?download=1'};
 const {get,show}=page(cg,'mcp');await show();await get('analysis-history').onchange({target:{value:'saved'}});
 get('analysis-graph-types').children.find(b=>b.dataset.kind==='Cg').onclick();
 assert.equal(get('analysis-graph').children[0].src,'/api/analysis/saved/callgraph.svg');
 assert.equal(get('analysis-graph-download').href,'/api/analysis/saved/callgraph.svg?download=1');
 await get('analysis-samples').children[0].onclick();assert.equal(get('analysis-graph-download').hidden,true);
});
test('restoring a record keeps its request criterion and rejects invalid edits',async()=>{
 const {get,show}=page(null,'mcp');await show();get('analysis-target-line').onchange({target:{value:'2'}});
 await get('analysis-history').onchange({target:{value:'saved'}});assert.equal(get('analysis-target-line').value,'3');
 get('analysis-target-line').onchange({target:{value:'999'}});assert.equal(get('analysis-target-line').value,'3');
});
test('MCP variable rows alone drive highlights, including rows after the request line',async()=>{
 const {get,show,requests}=page(null,'mcp');await show();
 assert.equal(get('analysis-slice-count').textContent,2);assert.match(get('analysis-source').children[2].className,/is-slice/);
 get('analysis-target-line').oninput({target:{value:'2'}});assert.match(get('analysis-source').children[2].className,/is-slice/);
 get('analysis-variable').onchange({target:{value:'a'}});
 assert.match(get('analysis-source').children[0].className,/is-slice/);assert.doesNotMatch(get('analysis-source').children[2].className,/is-slice/);
 assert.equal(requests.filter(r=>r.method==='POST').length,0);
});
test('SDG remains default and all six other-than-DDG original choices remain independently selectable',async()=>{
 const {get,show}=page(null,'mcp');await show();
 assert.equal(get('analysis-graph-title').textContent,'系统依赖 SDG');
 assert.deepEqual(get('analysis-graph-types').children.map(b=>b.dataset.kind),['Sdg','Pdg','Cfg','Cg','Cdg','Dfg']);
 get('analysis-graph-types').children.find(b=>b.dataset.kind==='Cg').onclick();
 get('analysis-target-line').oninput({target:{value:'2'}});assert.equal(get('analysis-graph-title').textContent,'函数调用 CG');
});
test('first upload may reuse a verified cache, while explicit reanalysis requests fresh tools',async()=>{
 const {get,show,requests}=page(null,'mcp',{cacheHit:true});await show();
 const file=new Blob([new TextEncoder().encode('public func f(): Int64 {\n return 1\n}\n')]);file.name='cache-upload.cj';
 get('analysis-file').onchange({target:{files:[file],value:'file'}});
 for(let i=0;i<100&&get('analysis-filename').textContent!=='cache-upload.cj';i++)await new Promise(resolve=>setImmediate(resolve));
 get('analysis-consent').checked=true;await get('analysis-run').onclick();
 assert.equal(requests.filter(r=>r.method==='POST')[0].body.get('reuse_cache'),'true');assert.match(get('analysis-origin').textContent,/缓存复用/);
 await get('analysis-run').onclick();assert.equal(requests.filter(r=>r.method==='POST')[1].body.get('reuse_cache'),'false');
});
test('PDG JSON node navigation changes focus without recomputing the selected MCP slice',async()=>{
 const pg={status:'VALID',source_sha256:'hash',graph:{nodes:[{id:'n',line:2,label:'[L2]: x = 2'}],edges:[]}};
 const {get,show,requests}=page(null,'mcp',{reportOverrides:{point_graph:pg}});await show();
 get('analysis-graph-types').children.find(b=>b.dataset.kind==='Pdg').onclick();get('analysis-graph-nodes').children[0].onclick();
 assert.equal(get('analysis-target-line').value,'2');assert.match(get('analysis-source').children[2].className,/is-slice/);
 assert.equal(requests.filter(r=>r.method==='POST').length,0);
});
test('new upload clears stale rows and remains pending until MCP is requested',async()=>{
 const {get,show}=page(null,'mcp');await show();
 const file=new Blob([new TextEncoder().encode('public func f(): Int64 {\n return 1\n}\n')]);file.name='fresh.cj';
 get('analysis-file').onchange({target:{files:[file],value:'file'}});
 for(let i=0;i<100&&get('analysis-filename').textContent!=='fresh.cj';i++)await new Promise(resolve=>setImmediate(resolve));
 assert.equal(get('analysis-target-line').value,'2');assert.equal(get('analysis-slice-count').textContent,'—');
 assert.ok(get('analysis-source').children.every(n=>!n.className.includes('is-slice')));
 assert.ok(get('analysis-tools').children.some(c=>c.children.map(n=>n.textContent).join(' ')==='MCP原生切片 未运行'));
});
test('failed native result cannot be replaced by old table, local PDG or log recovery',async()=>{
 const {get,show}=page(null,'mcp',{reportOverrides:{status:'PARTIAL',observations:[{tool:'sympas_slice',status:'FAILED',reason:'工具失败',data:{}},{tool:'sympas_slice_table',status:'VALID',data:{scope:'VARIABLE_TABLE',slices:{x:[2,3]}}}],derived_slice:{status:'RECOVERED',slices:{x:[2,3]}}}});
 await show();assert.equal(get('analysis-slice-count').textContent,'—');assert.match(get('analysis-slice-note').textContent,/工具失败/);
 assert.ok(get('analysis-source').children.every(n=>!n.className.includes('is-slice')));
});
test('legacy table reports remain identifiable and require explicit reanalysis to change their results',async()=>{
 const {get,show,requests}=page(null,true);await show();
 assert.match(get('analysis-slice-note').textContent,/历史切片表/);assert.equal(get('analysis-slice-count').textContent,2);
 assert.equal(requests.filter(r=>r.method==='POST').length,0);
});
