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
