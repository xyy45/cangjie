'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const script=fs.readFileSync('nexus/demo/static/demo.js','utf8');
const html=fs.readFileSync('nexus/demo/templates/demo.html','utf8');

function page(){
 const views=['workspace','analysis','history','deliveries'];
 const nodes=Object.fromEntries([...views.map(v=>v+'-view'),'execution-modes'].map(id=>[id,{hidden:id!=='workspace-view'}]));
 const controls=[...html.matchAll(/<[^>]+data-view="([^"]+)"[^>]*>/g)].map(([tag,view])=>({
  dataset:{view},nav:/class="[^"]*\bnav-button\b/.test(tag),attributes:{},
  classList:{toggle(){}},setAttribute(k,v){this.attributes[k]=v;}
 }));
 const ctx={document:{querySelectorAll(selector){return selector.includes('.nav-button')?controls.filter(c=>c.nav):controls;},body:{classList:{toggle(){}}}},
  $:id=>nodes[id],current:null,renderHistory(){},AnalysisUI:{show(){}}};
 vm.createContext(ctx);
 vm.runInContext(script.match(/^function showView\(view\).*$/m)[0],ctx);
 vm.runInContext(script.match(/^document\.querySelectorAll\([^\n]+?;/m)[0],ctx);
 return {nodes,controls,show:view=>{ctx.requestedView=view;vm.runInContext('showView(requestedView)',ctx);}};
}

test('clicking selected code in any diff layout preserves the workspace',()=>{
 for(const layout of ['split','before','after']){
  const p=page(),code=p.controls.find(c=>!c.nav);
  assert.ok(code,'actual template must include the diff container');
  code.dataset.view=layout;
  // A code click bubbles to its containing diff element.
  code.onclick?.();
  assert.equal(p.nodes['workspace-view'].hidden,false,layout);
  assert.equal(code.attributes['aria-current'],undefined);
 }
});

test('unknown view names leave the currently visible page unchanged',()=>{
 const p=page();p.show('history');
 for(const invalid of ['split','before','after','',undefined]){
  p.show(invalid);
  assert.equal(p.nodes['history-view'].hidden,false);
  assert.equal(p.nodes['workspace-view'].hidden,true);
 }
});

test('sidebar navigation still opens each supported page',()=>{
 const p=page();
 for(const button of p.controls.filter(c=>c.nav)){
  button.onclick();
  for(const view of ['workspace','analysis','history','deliveries'])
   assert.equal(p.nodes[view+'-view'].hidden,view!==button.dataset.view);
 }
});
