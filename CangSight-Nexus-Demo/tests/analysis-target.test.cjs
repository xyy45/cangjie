'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function page(callgraph){
 const nodes=new Map();
 const element=()=>({children:[],textContent:'',value:'',hidden:false,disabled:false,dataset:{},style:{},classList:{toggle(){}},setAttribute(){},append(...xs){this.children.push(...xs);},replaceChildren(...xs){this.children=xs;},querySelectorAll(){return[];},querySelector(){return null;}});
 const get=id=>{if(!nodes.has(id))nodes.set(id,element());return nodes.get(id);};
 const source={filename:'f.cj',code:'func f(): Int64 {\n let x = 2\n return x\n}\n',line_count:4,source_sha256:'hash'};
 const requests=[],report={id:'saved',status:callgraph?'PARTIAL':'COMPLETE',callgraph,source,slice_criterion:{line:3,direction:'Bwd',method:'SymPas'},observations:[{tool:'sympas_slice',status:'VALID',data:{slices:{x:[2,3]}}}]};
 const ctx={document:{getElementById:get,createElement:element,createElementNS:element},crypto:require('node:crypto').webcrypto,TextDecoder,FormData,csrf:'csrf',location:{origin:'http://localhost'},toast(){},setTimeout:()=>0,clearTimeout(){},fetch:async(url,options={})=>{
  requests.push({url,...options});let data;
  if(url==='/analysis/samples')data={samples:[{id:'s',title:'sample'}]};
  else if(url==='/analysis/samples/s')data={source,snapshot:{...report,callgraph:undefined,display_origin:'SAMPLE_SNAPSHOT'}};
  else if(url==='/api/analysis'&&options.method==='POST')data={id:'job'};
  else if(url==='/api/analysis/job')data={...report,id:'job',slice_criterion:{line:2,direction:'Bwd',method:'SymPas'}};
  else if(url==='/api/analysis/saved')data=report;
  else if(url==='/api/analysis')data={jobs:[]};else throw Error(url);
  return{ok:true,json:async()=>data};
 }};
 vm.createContext(ctx);
 for(const file of ['analysis-core.js','analysis.js'])vm.runInContext(fs.readFileSync('nexus/demo/static/'+file,'utf8'),ctx);
 return{get,requests,show:()=>vm.runInContext('AnalysisUI.show()',ctx)};
}
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
