'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function page(callgraph,native=false,{omitPointOnResult=false,cacheHit=false}={}){
 const nodes=new Map();
 const element=()=>({children:[],textContent:'',value:'',hidden:false,disabled:false,dataset:{},style:{},showModal(){},classList:{toggle(){}},setAttribute(){},append(...xs){this.children.push(...xs);},replaceChildren(...xs){this.children=xs;},querySelectorAll(){return[];},querySelector(){return null;}});
 const get=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);};
 const source={filename:'f.cj',code:'func f(): Int64 {\n let x = 2\n return x\n}\n',line_count:4,source_sha256:'hash'};
 const requests=[],report={id:'saved',status:callgraph?'PARTIAL':'COMPLETE',callgraph,source,slice_criterion:{line:3,direction:'Bwd',method:'SymPas'},observations:[{tool:'sympas_slice',status:'VALID',data:{slices:{x:[2,3]}}}]};
 if(native){report.slice_scope='VARIABLE_TABLE';report.observations=[{tool:'sympas_slice_table',status:'VALID',data:{scope:'VARIABLE_TABLE',slices:{x:[2,3],a:[1]}}}];}
 if(native==='point'){report.point_slice_url='/api/analysis/saved/point-slice';report.point_graph={status:'VALID',source_sha256:'hash',raw_sha256:'raw',graph:{graph_type:'Pdg',nodes:[{id:'one',label:'[L2]: x = 2',line:2},{id:'two',label:'[L3]: return x',line:3}],edges:[{from:'one',to:'two'}]}};}
 const ctx={document:{getElementById:get,createElement:element,createElementNS:element},crypto:require('node:crypto').webcrypto,TextDecoder,FormData,csrf:'csrf',location:{origin:'http://localhost'},toast(){},setTimeout:()=>0,clearTimeout(){},fetch:async(url,options={})=>{
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
 for(const file of ['analysis-core.js','analysis.js'])vm.runInContext(fs.readFileSync('nexus/demo/static/'+file,'utf8'),ctx);
 return{get,requests,show:()=>vm.runInContext('AnalysisUI.show()',ctx),openBound:(line)=>{ctx.boundReport={...report,display_origin:'REGISTERED_BOUND'};ctx.boundLine=line;return vm.runInContext('AnalysisUI.openBound(boundReport,{line:boundLine})',ctx);}};
}
test('bound localization opens the requested baseline statement rather than the default criterion',()=>{
 const p=page(null,'point');assert.equal(p.openBound(2),true);assert.equal(p.get('analysis-target-line').value,'2');assert.equal(p.get('analysis-slice-mode').value,'point');
 assert.equal(p.openBound(999),false);assert.equal(p.get('analysis-target-line').value,'2');
});
test('selected source line becomes actual request criterion and old results stay labelled',async()=>{
 const {get,requests,show}=page();await show();
 get('analysis-source').children[1].onclick();
 assert.equal(get('analysis-target-line').value,'2');
 assert.match(get('analysis-target-note').textContent,/L3/);assert.match(get('analysis-target-note').textContent,/L2/);
 assert.equal(requests.filter(r=>r.method==='POST').length,0);
 await get('analysis-run').onclick();
 assert.equal(JSON.parse(requests.find(r=>r.method==='POST').body).slice_line,2);
 assert.doesNotMatch(get('analysis-target-note').textContent,/显示.*L3/);
});
test('saved native SVG is accessible for partial results and cleared on source switch',async()=>{
 const {get,show}=page({status:'SAVED',source_sha256:'hash',view_url:'/api/analysis/saved/callgraph.svg',download_url:'/api/analysis/saved/callgraph.svg?download=1'});
 await show();assert.equal(get('analysis-callgraph-open').hidden,true);
 await get('analysis-history').onchange({target:{value:'saved'}});
 assert.equal(get('analysis-callgraph-open').hidden,false);
 assert.equal(get('analysis-callgraph-open').href,'/api/analysis/saved/callgraph.svg');
 assert.equal(get('analysis-callgraph-download').href,'/api/analysis/saved/callgraph.svg?download=1');
 await get('analysis-samples').children[0].onclick();
 assert.equal(get('analysis-callgraph-open').hidden,true);
 assert.equal(get('analysis-callgraph-open').href,'');
});
test('restoring analysis restores its recorded target and rejects invalid edits',async()=>{
 const {get,show}=page();await show();get('analysis-target-line').value='2';get('analysis-target-line').onchange({target:get('analysis-target-line')});
 await get('analysis-history').onchange({target:{value:'saved'}});
 assert.equal(get('analysis-target-line').value,'3');
 get('analysis-target-line').value='999';get('analysis-target-line').onchange({target:get('analysis-target-line')});
 assert.equal(get('analysis-target-line').value,'3');
});

test('native table switches highlight rows by variable and the target control remains a navigation anchor',async()=>{
 const {get,show,requests}=page(undefined,true);await show();
 assert.equal(get('analysis-slice-count').textContent,2);
 assert.match(get('analysis-target-note').textContent,/变量切片表/);
 assert.match(get('analysis-source').children[1].className,/is-slice/);
 assert.doesNotMatch(get('analysis-source').children[0].className,/is-slice/);
 get('analysis-variable').onchange({target:{value:'a'}});
 assert.match(get('analysis-source').children[0].className,/is-slice/);
 assert.doesNotMatch(get('analysis-source').children[1].className,/is-slice/);
 get('analysis-source').children[1].onclick();
 assert.match(get('analysis-target-note').textContent,/定位 L2/);
 assert.equal(requests.filter(r=>r.method==='POST').length,0);
});

test('point mode updates source highlights and download target immediately without a new MCP request',async()=>{
 const {get,show,requests}=page(undefined,'point');await show();
 get('analysis-slice-mode').onchange({target:{value:'point'}});
 assert.equal(get('analysis-slice-mode').value,'point');
 assert.equal(get('analysis-variable').hidden,true);
 get('analysis-source').children[1].onclick();
 assert.equal(get('analysis-slice-count').textContent,1);
 assert.match(get('analysis-source').children[1].className,/is-slice/);
 assert.doesNotMatch(get('analysis-source').children[2].className,/is-slice/);
 assert.match(get('analysis-point-download').href,/line=2&download=1/);
 get('analysis-source').children[3].onclick();
 assert.equal(get('analysis-point-download').hidden,true);
 assert.ok(get('analysis-source').children.every(n=>!n.className.includes('is-slice')));
 assert.equal(requests.filter(r=>r.method==='POST').length,0);
 get('analysis-slice-mode').onchange({target:{value:'table'}});
 assert.equal(get('analysis-slice-count').textContent,2);
 assert.equal(get('analysis-variable').disabled,false);
});

test('typing a valid point target recomputes immediately without waiting for blur',async()=>{
 const {get,show}=page(undefined,'point');await show();
 get('analysis-slice-mode').onchange({target:{value:'point'}});
 get('analysis-target-line').oninput({target:{value:'2'}});
 assert.match(get('analysis-target-note').textContent,/L2/);
 assert.match(get('analysis-point-download').href,/line=2&download=1/);
 assert.doesNotMatch(get('analysis-source').children[2].className,/is-slice/);
});

test('new PDG availability does not change the selected DDG mode',async()=>{
 const {get,show}=page(undefined,'point');await show();
 assert.equal(get('analysis-slice-mode').value,'table');
 assert.equal(get('analysis-graph-title').textContent,'数据依赖 DDG');
 await get('analysis-run').onclick();
 assert.equal(get('analysis-slice-mode').value,'table');
 assert.equal(get('analysis-graph-title').textContent,'数据依赖 DDG');
});

test('explicit point selection survives reanalysis and does not fallback when PDG is missing',async()=>{
 const {get,show}=page(undefined,'point',{omitPointOnResult:true});await show();
 get('analysis-slice-mode').onchange({target:{value:'point'}});
 const pending=get('analysis-run').onclick();
 assert.equal(get('analysis-slice-mode').value,'point');
 assert.equal(get('analysis-graph-title').textContent,'程序依赖 PDG');
 await pending;
 assert.equal(get('analysis-slice-mode').value,'point');
 assert.equal(get('analysis-graph-title').textContent,'程序依赖 PDG');
 assert.equal(get('analysis-node-count').textContent,'—');
 assert.match(get('analysis-slice-note').textContent,/PDG/);
});

test('first upload requests reuse and reanalysis forces tools while showing original cache provenance',async()=>{
 const {get,show,requests}=page(undefined,true,{cacheHit:true});await show();
 const bytes=new TextEncoder().encode('func f(): Int64 { return 1 }\n');
 const file=new Blob([bytes]);file.name='f.cj';
 get('analysis-file').onchange({target:{files:[file],value:'file'}});
 for(let i=0;i<100&&get('analysis-filename').textContent!=='f.cj';i++)await new Promise(resolve=>setImmediate(resolve));
 get('analysis-consent').checked=true;
 await get('analysis-run').onclick();
 const first=requests.filter(r=>r.method==='POST')[0];
 assert.equal(first.body.get('reuse_cache'),'true');
 assert.match(get('analysis-origin').textContent,/缓存复用/);
 get('analysis-evidence-open').onclick();
 assert.ok(JSON.stringify(get('analysis-evidence-content').children).includes('2026'));
 await get('analysis-run').onclick();
 assert.equal(requests.filter(r=>r.method==='POST')[1].body.get('reuse_cache'),'false');
});
