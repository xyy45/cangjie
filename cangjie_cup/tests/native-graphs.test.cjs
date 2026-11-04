'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ui=require('../nexus/demo/static/native-graphs.js');
const source={source_sha256:'source'};
const graph=(kind)=>({status:'SAVED',graph_type:kind,source_sha256:'source',aspect_ratio:2,
 view_url:'/api/analysis/run/graphs/'+kind+'.svg',download_url:'/api/analysis/run/graphs/'+kind+'.svg?download=1'});
const report={id:'run',status:'COMPLETE',source,native_graphs:{schema_version:1,graphs:Object.fromEntries(
 ['Cfg','Cg','Cdg','Ddg','Pdg','Sdg','Dfg'].map(k=>[k,graph(k)]))}};
test('seven independent graph types retain original same-origin assets',()=>{
 assert.equal(ui.TYPES.length,7);
 for(const kind of ui.TYPES)assert.equal(ui.asset(report,kind).view_url,graph(kind).view_url);
 const bad=structuredClone(report);bad.native_graphs.graphs.Sdg.source_sha256='other';
 assert.equal(ui.asset(bad,'Sdg').ready,false);assert.equal(ui.asset(bad,'Ddg').ready,true);
});
test('unavailable kind never falls back to another graph; old CG is available explicitly',()=>{
 const old={source,status:'PARTIAL',callgraph:{...graph('Cg'),view_url:'/api/analysis/run/callgraph.svg',download_url:'/api/analysis/run/callgraph.svg?download=1'}};
 assert.equal(ui.asset(old,'Cg').ready,true);assert.equal(ui.asset(old,'Sdg').ready,false);
 assert.equal(ui.asset({...report,status:'RUNNING'},'Ddg').ready,false);
});
test('foreign, active, non-graph and protocol-relative URLs are rejected',()=>{
 for(const url of ['https://evil.invalid/g.svg','//evil.invalid/g.svg','javascript:alert(1)','data:image/svg+xml,x','/api/tasks']){
  const bad=structuredClone(report);bad.native_graphs.graphs.Ddg.view_url=url;
  assert.equal(ui.asset(bad,'Ddg').ready,false,url);
 }
});
test('fit contains portrait and wide graphs in a full-width viewport, zoom and pan stay bounded',()=>{
 for(const ratio of [.2,2,20]){
  const size=ui.fitSize(1200,ratio);assert.equal(size.width,1200);assert.ok(size.height>=260&&size.height<=900);
 }
 const v=new ui.Viewport();v.zoomBy(20);assert.equal(v.zoom,8);v.panBy(1e9,-1e9,1000,500);
 assert.ok(v.x<=3500&&v.y>=-1750);v.fit();assert.deepEqual([v.zoom,v.x,v.y],[1,0,0]);
});
test('source switch clears original image and stale load cannot change the new graph status',()=>{
 const nodes=new Map();const el=()=>({children:[],style:{},dataset:{},classList:{toggle(){}},clientWidth:1000,
  setAttribute(){},append(...xs){this.children.push(...xs);},replaceChildren(...xs){this.children=xs;}});
 const get=id=>{if(!nodes.has(id))nodes.set(id,el());return nodes.get(id);};
 const ctx={document:{getElementById:get,createElement:el},location:{origin:'http://localhost'},URL};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/native-graphs.js','utf8'),ctx);
 const viewer=ctx.NativeGraphUI.mount({onSelect(){}});viewer.render(report,'Ddg');
 const image=get('analysis-graph').children[0];assert.equal(image.src,graph('Ddg').view_url);
 viewer.render({...report,id:'other',source:{source_sha256:'new'}},'Sdg');
 const status=get('analysis-node-detail').textContent;image.onload();
 assert.equal(get('analysis-node-detail').textContent,status);
 assert.notEqual(get('analysis-graph').children[0],image);
});
test('native viewer is loaded before analysis and exposes graph selection and fullscreen',()=>{
 const html=fs.readFileSync('nexus/demo/templates/demo.html','utf8');
 assert.ok(html.indexOf("filename='native-graphs.js'")<html.indexOf("filename='analysis.js'"));
 assert.match(html,/id="analysis-graph-types"/);assert.match(html,/id="analysis-fullscreen"/);
});

test('fullscreen uses a modal gallery even when browser fullscreen is a no-op',()=>{
 const nodes=new Map();const el=()=>({children:[],style:{},dataset:{},classList:{toggle(){}},clientWidth:1000,
  setAttribute(){},append(...xs){this.children.push(...xs);},insertBefore(){},replaceChildren(...xs){this.children=xs;}});
 const get=id=>{if(!nodes.has(id))nodes.set(id,el());return nodes.get(id);};
 get('analysis-graph-panel').parentNode=el();get('analysis-graph-panel').nextSibling=null;
 get('analysis-graph-panel').requestFullscreen=()=>Promise.resolve();
 const dialog=get('analysis-graph-dialog');dialog.showModal=()=>{dialog.open=true;};dialog.close=()=>{dialog.open=false;dialog.onclose();};
 const ctx={document:{getElementById:get,createElement:el},location:{origin:'http://localhost'},URL};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/native-graphs.js','utf8'),ctx);
 const viewer=ctx.NativeGraphUI.mount({onSelect(){}});viewer.render(report,'Sdg');viewer.fullscreen();
 assert.equal(dialog.open,true);assert.equal(get('analysis-fullscreen').textContent,'退出全屏');
 viewer.fullscreen();assert.equal(dialog.open,false);assert.equal(get('analysis-fullscreen').textContent,'全屏');
});

test('polling a completed missing graph replaces the earlier waiting state without changing graph kind',()=>{
 const nodes=new Map();const el=()=>({children:[],style:{},dataset:{},classList:{toggle(){}},clientWidth:1000,
  setAttribute(){},append(...xs){this.children.push(...xs);},replaceChildren(...xs){this.children=xs;}});
 const get=id=>{if(!nodes.has(id))nodes.set(id,el());return nodes.get(id);};
 const ctx={document:{getElementById:get,createElement:el},location:{origin:'http://localhost'},URL};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/native-graphs.js','utf8'),ctx);
 const viewer=ctx.NativeGraphUI.mount({onSelect(){}});
 viewer.render({...report,status:'RUNNING'},'Ddg');assert.match(get('analysis-node-detail').textContent,/等待/);
 const finished=structuredClone(report);finished.status='PARTIAL';finished.native_graphs.graphs.Ddg={status:'UNAVAILABLE',reason:'MCP下载超时'};
 viewer.render(finished,'Ddg');assert.equal(get('analysis-node-detail').textContent,'MCP下载超时');
 assert.equal(get('analysis-graph').children[0].textContent,'MCP下载超时');
});
