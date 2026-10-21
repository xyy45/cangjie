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
