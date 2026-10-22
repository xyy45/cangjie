'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
function page(){
 class Element{constructor(){this.children=[];this.dataset={};this.style={};this.open=false;this.classList={toggle(){}};this.disabled=false;this.textContent='';}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}setAttribute(k,v){this[k]=v;}showModal(){this.open=true;}close(){this.open=false;}querySelector(){return null;}}
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
 let transport=async()=>({candidate_id:'one',status:'NOT_STARTED',files:[],tree_hash:'hash',attempt:1});const calls=[];
 const ctx={document:{createElement:()=>new Element(),createElementNS:()=>new Element()},$:get,api:async(path,body)=>{calls.push([path,body]);return transport(path,body);},toast(){},setTimeout:()=>0,clearTimeout(){},AnalysisCore:require('../nexus/demo/static/analysis-core.js')};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/impact.js','utf8')+'\nglobalThis.ui=ImpactUI;',ctx);
 return{get,calls,ui:ctx.ui,setApi(fn){transport=fn;}};
}
test('viewing and switching candidates do not request fresh tool analysis',async()=>{
 const {ui,get,calls}=page();ui.render({id:'task'}, {id:'one'},'real',false);
 await get('impact-open').onclick();
 assert.equal(calls.length,1);assert.equal(calls[0][1],undefined);
 ui.render({id:'task'}, {id:'two'},'real',false);
 assert.equal(calls.length,1);assert.equal(get('impact-dialog').open,false);
});
test('late impact response cannot fill the newly selected candidate dialog',async()=>{
 const {ui,get,setApi}=page();let resolve;
 setApi(()=>new Promise(r=>resolve=r));ui.render({id:'task'}, {id:'one'},'real',false);
 const pending=get('impact-open').onclick();ui.render({id:'task'}, {id:'two'},'real',false);
 resolve({candidate_id:'one',status:'COMPLETE',files:[],tree_hash:'old'});await pending;
 assert.equal(get('impact-dialog').open,false);
 assert.notEqual(get('impact-identity').textContent,'one');
});
test('explicit generation sends only one empty POST and cannot repeat a recorded run',async()=>{
 const {ui,get,setApi,calls}=page();let status='NOT_STARTED';
 setApi(async(path,body)=>{if(body!==undefined)status='COMPLETE';return {candidate_id:'one',status,files:[],tree_hash:'hash',attempt:1,report_ref:status==='COMPLETE'?'record':null};});
 ui.render({id:'task'}, {id:'one'},'real',false);await get('impact-open').onclick();
 const pending=get('impact-generate').onclick();const duplicate=get('impact-generate').onclick();await pending;await duplicate;
 assert.equal(calls.filter(c=>c[1]!==undefined).length,1);
 assert.deepEqual(JSON.parse(JSON.stringify(calls.find(c=>c[1]!==undefined)[1])),{});
 assert.equal(get('impact-generate').disabled,true);
});

function text(node){return [node.textContent,...node.children.map(text)].join(' ');}
function elements(node,predicate){return [...(predicate(node)?[node]:[]),...node.children.flatMap(n=>elements(n,predicate))];}
const changeFile=()=>({path:'src/quantity.cj',before_code:'func f() {\n value >= 0\n}',after_code:'func f() {\n value >= 1\n}',changes:{before_lines:[2],after_lines:[2],functions:[]},before:null,after:null});
const emptyEntry=()=>({analysis_id:'analysis',source_sha256:'a'.repeat(64),slice_scope:'VARIABLE_TABLE',slice_criterion:{line:2},status:'PARTIAL',tools:[{tool:'sympas_dep_graph',status:'EMPTY'}],graph:{status:'EMPTY',reason:'未返回非空DDG',nodes:[],edges:[],anchor_ids:[],total_nodes:0,total_edges:0}});

test('each missing side distinguishes active analysis, waiting, interruption and no result',async()=>{
 for(const [status,progress,want] of [['NOT_STARTED','',/尚未生成/],['RUNNING','src/quantity.cj · 修复后',/分析中/],['RUNNING','src/quantity.cj · 修复前',/等待/],['IN_DOUBT','',/中断/],['PARTIAL','',/未取得/]]){
  const {ui,get,setApi}=page(),file=changeFile();file.before=emptyEntry();
  setApi(async()=>({candidate_id:'one',status,progress,files:[file],tree_hash:'hash',attempt:1}));
  ui.render({id:'task'},{id:'one'},'real',false);await get('impact-open').onclick();
  const columns=elements(get('impact-files'),n=>n.className==='impact-side');
  assert.match(text(columns[1]),want,status+' should describe the actual side state');
  assert.doesNotMatch(text(columns[1]),/点击生成工具对比/);
  if(status==='RUNNING')assert.equal(get('impact-generate').textContent,'分析中');
 }
});

test('legacy display PDG is visibly typed without relabeling the empty DDG evidence',async()=>{
 const {ui,get,setApi}=page(),file=changeFile(),entry=emptyEntry();
 entry.display_graph={status:'VALID',graph_type:'Pdg',total_nodes:3,total_edges:2,graph_count:1,graph_index:0,
  nodes:[{id:'entry',line:null,label:'ENTER f'},{id:'changed',line:2,label:'[L2]: value >= 1'}],
  edges:[{from:'entry',to:'changed'}],anchor_ids:['changed']};file.after=entry;file.before=emptyEntry();
 setApi(async()=>({candidate_id:'one',status:'PARTIAL',files:[file],tree_hash:'hash',attempt:1}));
 ui.render({id:'task'},{id:'one'},'real',false);await get('impact-open').onclick();
 const columns=elements(get('impact-files'),n=>n.className==='impact-side');
 assert.match(text(columns[1]),/PDG/);assert.match(text(columns[1]),/DDG EMPTY/);
 const graphs=elements(columns[1],n=>n.role==='img');assert.equal(graphs.length,1);
 assert.match(graphs[0]['aria-label'],/PDG/);
 assert.match(text(columns[1]),/3 节点 \/ 2 边/);
 assert.match(text(columns[0]),/未返回非空DDG/);
});

test('dependency SVG keeps readable dimensions instead of inheriting 18px icon sizing',async()=>{
 const {ui,get,setApi}=page(),file=changeFile(),entry=emptyEntry();
 entry.graph={status:'VALID',graph_type:'Ddg',total_nodes:1,total_edges:0,graph_count:1,graph_index:0,
  nodes:[{id:'changed',line:2,label:'[L2]: value >= 1'}],edges:[],anchor_ids:['changed']};file.after=entry;
 setApi(async()=>({candidate_id:'one',status:'PARTIAL',files:[file],tree_hash:'hash',attempt:1}));
 ui.render({id:'task'},{id:'one'},'real',false);await get('impact-open').onclick();
 const [canvas]=elements(get('impact-files'),n=>n.role==='img');
 assert.ok(Number.parseFloat(canvas.style.width)>=340,'graph width must override global icon CSS');
 assert.ok(Number.parseFloat(canvas.style.height)>=180,'graph height must override global icon CSS');
});
