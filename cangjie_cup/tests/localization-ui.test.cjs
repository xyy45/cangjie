'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element{constructor(){this.children=[];this.hidden=false;this.disabled=false;this.textContent='';this.open=false;}append(...xs){this.children.push(...xs);}replaceChildren(...xs){this.children=xs;}showModal(){this.open=true;}close(){this.open=false;this.onclose?.();}}
const report={status:'PARTIAL',binding:{task_id:'t',baseline_id:'base',baseline_hash:'basehash',subject_id:'base',subject_tree_hash:'basehash',spec_hash:'spec',for_round:1},limitations:['基线坐标不代表候选执行'],targets:[{test_id:'Tests.one',mapping:'CONFIRMED_CASE',function:'total',args:[2],args_text:'[2]',actual:'104',expected:'102',requirement_refs:['REQ'],locations:[{function:'total',path:'src/order.cj',coordinate_subject_id:'base',start_line:2,end_line:4,source_sha256:'filehash',call_origin:'CONFIRMED_CASE',source_lines:[{line:3,text:'return x + 1'}],anchors:[{line:3,basis:'RETURN_STATEMENT',slice:{status:'VALID',analysis_id:'analysis',raw_sha256:'raw',lines:[2,3]}}]}]}]};
const event={type:'LOCALIZATION_CONTEXT',context_hash:'focus',localization:report};
const task={id:'t',baseline_id:'base',spec_hash:'spec',candidates:[{id:'c1',attempt:1,tree_hash:'c1hash'},{id:'c2',attempt:2,tree_hash:'c2hash'}],events:[event]};
function page(withGlobal=true){
 const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};let api=async()=>({task_id:'t',round:1,context_hash:'focus',report});const calls=[],opened=[];
 const ctx={document:{getElementById:get,createElement:()=>new Element()},api:async path=>{calls.push(path);return api(path);},toast(){},AnalysisUI:{openBound:(r,o)=>{opened.push([r,o]);return true;}},showView(){}};
 if(withGlobal)ctx.$=get;
 assert.ok(fs.existsSync('nexus/demo/static/localization.js'),'localization component missing');vm.createContext(ctx);vm.runInContext(fs.readFileSync('nexus/demo/static/localization.js','utf8')+'\nglobalThis.ui=LocalizationUI;',ctx);
 return {get,calls,opened,ui:ctx.ui,setApi(fn){api=fn;}};
}
function text(n){return n.textContent+' '+n.children.map(text).join(' ');}
function buttons(n){return[n,...n.children.flatMap(buttons)].filter(e=>e.onclick);}
test('component can initialize before the workbench globals are defined',()=>{
 const p=page(false);p.ui.render(task,task.candidates[0],'real');assert.equal(p.get('focus-open').disabled,false);
});
test('selected round only offers its own evidence and clears stale state on another task or replay',()=>{
 const p=page();p.ui.render(task,task.candidates[0],'real');assert.equal(p.get('focus-open').disabled,false);assert.match(p.get('focus-summary').textContent,/第 1 轮/);
 p.ui.render(task,task.candidates[1],'real');assert.equal(p.get('focus-open').disabled,true);
 p.ui.render({...task,id:'other'},null,'real');assert.equal(p.get('repair-focus').hidden,true);
 p.ui.render(task,task.candidates[0],'replay');assert.equal(p.get('repair-focus').hidden,true);
});
test('opening rechecks server originals then displays baseline coordinates and literal failure facts',async()=>{
 const p=page();p.ui.render(task,task.candidates[0],'real');await p.get('focus-open').onclick();
 assert.deepEqual(p.calls,['/api/demo/tasks/t/localization?round=1']);
 const contents=text(p.get('focus-content'));assert.match(contents,/基线/);assert.match(contents,/104/);assert.match(contents,/102/);assert.match(contents,/src\/order.cj/);assert.match(contents,/L2/);
 const button=buttons(p.get('focus-content')).find(b=>b.textContent.includes('依赖图'));assert.ok(button);
 p.setApi(async()=>({source:{source_sha256:'filehash'},point_graph:{status:'VALID'}}));await button.onclick();
 assert.equal(p.opened[0][1].line,3);assert.equal(p.opened[0][0].source.source_sha256,'filehash');
});
test('late fetch cannot render another round and forged response bindings are rejected',async()=>{
 const p=page();p.ui.render(task,task.candidates[0],'real');let resolve;p.setApi(()=>new Promise(r=>resolve=r));const pending=p.get('focus-open').onclick();
 p.ui.render(task,task.candidates[1],'real');resolve({task_id:'t',round:1,context_hash:'focus',report});await pending;assert.doesNotMatch(text(p.get('focus-content')),/104/);
 p.ui.render(task,task.candidates[0],'real');p.setApi(async()=>({task_id:'other',round:1,context_hash:'focus',report}));await p.get('focus-open').onclick();assert.match(text(p.get('focus-content')),/核对失败/);
});
test('missing PDG stays unavailable and does not expose a graph action',async()=>{
 const p=page();p.ui.render(task,task.candidates[0],'real');const missing=JSON.parse(JSON.stringify(report));missing.targets[0].locations[0].anchors[0].slice={status:'UNAVAILABLE',reason:'无图'};
 p.setApi(async()=>({task_id:'t',round:1,context_hash:'focus',report:missing}));await p.get('focus-open').onclick();
 assert.match(text(p.get('focus-content')),/无图/);assert.equal(buttons(p.get('focus-content')).length,0);
});
test('property localization shows observed return and violation instead of a missing numeric answer',async()=>{
 const p=page();p.ui.render(task,task.candidates[0],'real');const property=JSON.parse(JSON.stringify(report));
 Object.assign(property.targets[0],{property_id:'PROP-RANGE',property_text:'退款不超实付',actual:null,expected:null,actual_return:9223372036854775807,actual_return_text:'9223372036854775807',assertion_value:false,expected_property:true});
 p.setApi(async()=>({task_id:'t',round:1,context_hash:'focus',report:property}));await p.get('focus-open').onclick();
 assert.match(text(p.get('focus-content')),/实际返回.*9223372036854775807/);assert.match(text(p.get('focus-content')),/PROP-RANGE/);
 assert.doesNotMatch(text(p.get('focus-content')),/预期.*未提取/);
});
test('relation localization names the actual side and displays its exact return without numeric expected',async()=>{
 const p=page();p.ui.render(task,task.candidates[0],'real');const paired=JSON.parse(JSON.stringify(report));
 Object.assign(paired.targets[0],{pair_id:'PAIR-one',relation_role:'left',relation_id:'REL-MONOTONE',relation_text:'增加数量不降低金额',actual:null,expected:null,actual_return:9223372036854775807,actual_return_text:'9223372036854775807',assertion_value:false,expected_relation:true});
 p.setApi(async()=>({task_id:'t',round:1,context_hash:'focus',report:paired}));await p.get('focus-open').onclick();
 const visible=text(p.get('focus-content'));assert.match(visible,/REL-MONOTONE/);assert.match(visible,/左/);assert.match(visible,/实际返回.*9223372036854775807/);assert.doesNotMatch(visible,/预期.*未提取/);
});
test('sequence localization separates SDK case from step and displays exact state context',async()=>{
 const p=page();p.ui.render(task,task.candidates[0],'real');const sequence=JSON.parse(JSON.stringify(report));
 Object.assign(sequence.targets[0],{call_id:'SEQUENCE-one.step1',sequence_id:'SEQUENCE-one',step_index:1,sequence_role:'failure',operation_id:'OP-REFUND',operation_text:'退款',initial_state:0,initial_state_text:'0',before_state:9223372036854775806,before_state_text:'9223372036854775806',actual_return:9223372036854775807,actual_return_text:'9223372036854775807',expected_state:9223372036854775806,expected_state_text:'9223372036854775806',context:[9223372036854775807],context_text:'[9223372036854775807]',failure_ids:['MODEL-OP-REFUND']});
 p.setApi(async()=>({task_id:'t',round:1,context_hash:'focus',report:sequence}));await p.get('focus-open').onclick();const visible=text(p.get('focus-content'));
 assert.match(visible,/Tests.one/);assert.match(visible,/SEQUENCE-one.step1/);assert.match(visible,/前态.*9223372036854775806/);assert.match(visible,/参考状态.*9223372036854775806/);assert.match(visible,/上下文.*9223372036854775807/);assert.doesNotMatch(visible,/9223372036854776000/);
});
test('missing canonical sequence context never silently rounds an unsafe integer',async()=>{
 const p=page();p.ui.render(task,task.candidates[0],'real');const sequence=JSON.parse(JSON.stringify(report));
 Object.assign(sequence.targets[0],{call_id:'SEQUENCE-one.step1',sequence_id:'SEQUENCE-one',step_index:1,sequence_role:'failure',operation_id:'OP-REFUND',operation_text:'退款',initial_state:0,before_state:0,actual_return:1,expected_state:0,context:[9223372036854775807],failure_ids:['MODEL-OP-REFUND']});
 p.setApi(async()=>({task_id:'t',round:1,context_hash:'focus',report:sequence}));await p.get('focus-open').onclick();const visible=text(p.get('focus-content'));
 assert.match(visible,/精确.*待核对/);assert.doesNotMatch(visible,/9223372036854776000/);
});
