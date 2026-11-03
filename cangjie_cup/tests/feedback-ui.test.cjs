'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Node {
 constructor(){this.children=[];this.textContent='';this.hidden=false;}
 append(...nodes){this.children.push(...nodes);}
 replaceChildren(...nodes){this.children=nodes;}
}
function page(){
 const context={document:{createElement:()=>new Node()}};
 vm.createContext(context);vm.runInContext(fs.readFileSync('nexus/demo/static/feedback.js','utf8')+'\nglobalThis.ui=FeedbackUI;',context);
 return {box:new Node(),ui:context.ui};
}
const text=n=>n.textContent+' '+n.children.map(text).join(' ');
const candidate={id:'candidate',tree_hash:'hash'};
const feedback={previous_candidate_id:'candidate',tree_hash:'hash',failure_cases:[{test_id:'PriceTests.upper',input:'validPrice(1000000)',
 expected:'true',actual:'false',requirement_refs:['REQ-PRICE'],mapping_basis:'TEST_SUITE',source:{log_ref:'records/real.log',start_char:10,end_char:80}}]};
test('feedback renders real values and suite mapping without interpreting source as HTML',()=>{
 const {box,ui}=page();ui.render(box,feedback,candidate);const visible=text(box);
 assert.match(visible,/validPrice\(1000000\)/);assert.match(visible,/true/);assert.match(visible,/false/);assert.match(visible,/REQ-PRICE/);
 assert.match(visible,/套件/);assert.match(visible,/records\/real.log/);assert.equal(box.hidden,false);
 assert.equal(box.children.some(n=>n.innerHTML!==undefined),false);
});
test('missing fields stay unavailable and switching candidate clears stale feedback',()=>{
 const {box,ui}=page();ui.render(box,{...feedback,failure_cases:[{test_id:'case',input:null,expected:null,actual:null,requirement_refs:[]}]},candidate);
 assert.match(text(box),/未提供/);
 ui.render(box,feedback,{id:'other',tree_hash:'hash'});assert.equal(box.hidden,true);assert.equal(box.children.length,0);
 ui.render(box,feedback,{id:'candidate',tree_hash:'changed'});assert.equal(box.hidden,true);
});
test('pending candidate without feedback safely keeps the panel empty',()=>{
 const {box,ui}=page();ui.render(box,undefined,{});
 assert.equal(box.hidden,true);assert.equal(box.children.length,0);
});
test('business property feedback displays typed actual returns and asserted property',()=>{
 const {box,ui}=page();ui.render(box,{...feedback,failure_cases:[{kind:'business_property',property_id:'PROP-RANGE',property_text:'退款不超实付',test_id:'Observed.case0',args:[1000,900,200],actual_return:1100,assertion_value:false,expected_property:true,mapping_basis:'USER_CONFIRMED_PROPERTY',requirement_refs:['REQ-UPLOAD']}]},candidate);
 assert.match(text(box),/PROP-RANGE/);assert.match(text(box),/\[1000,900,200\]/);assert.match(text(box),/实际返回.*1100/);assert.match(text(box),/断言.*false/);
 assert.doesNotMatch(text(box),/预期结果.*未提供|实际结果.*未提供/);
});
test('property feedback uses canonical primitive text for large integers',()=>{
 const {box,ui}=page();ui.render(box,{...feedback,failure_cases:[{kind:'business_property',test_id:'case',property_id:'PROP-SAME',args:[9223372036854775806],actual_return:9223372036854775807,args_text:'[9223372036854775806]',actual_return_text:'9223372036854775807'}]},candidate);
 assert.match(text(box),/9223372036854775806/);assert.match(text(box),/9223372036854775807/);assert.doesNotMatch(text(box),/9223372036854776000/);
});
test('paired feedback shows two exact calls and their relation without fabricated expected returns',()=>{
 const {box,ui}=page();ui.render(box,{...feedback,failure_cases:[{kind:'business_relation',pair_id:'PAIR-one',relation_id:'REL-SAME',relation_text:'相同输入返回一致',left_test_id:'Observed.case0',right_test_id:'Observed.case1',left_args:[9223372036854775806],right_args:[9223372036854775807],left_actual_return:9223372036854775806,right_actual_return:9223372036854775807,left_args_text:'[9223372036854775806]',right_args_text:'[9223372036854775807]',left_actual_return_text:'9223372036854775806',right_actual_return_text:'9223372036854775807',assertion_value:false,expected_relation:true}]},candidate);
 const visible=text(box);assert.match(visible,/REL-SAME/);assert.match(visible,/左.*实际返回.*9223372036854775806/);assert.match(visible,/右.*实际返回.*9223372036854775807/);assert.doesNotMatch(visible,/9223372036854776000|预期结果.*未提供/);
});
