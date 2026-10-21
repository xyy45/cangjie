const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../nexus/web/static/operator.js'),'utf8');

function page() {
  const elements=new Map();let request,resolve,reloaded=0;
  function element(id) {
    if (!elements.has(id)) elements.set(id,{value:'',textContent:'',disabled:false,addEventListener(name,handler){this[name]=handler;}});
    return elements.get(id);
  }
  vm.runInNewContext(source,{
    document:{getElementById:element,querySelector:()=>({content:'synthetic-csrf'})},
    location:{origin:'http://127.0.0.1:8765',reload(){reloaded++;}},
    localStorage:{setItem(){throw new Error('Credential must not persist in browser storage');}},
    fetch(url,options){request={url,options};return new Promise(r=>resolve=r);}
  });
  return {element,submit:()=>element('operator-form').submit({preventDefault(){}}),
    request:()=>request,reply:ok=>resolve({ok}),reloaded:()=>reloaded};
}

test('operator credential is cleared immediately and sent only to explicit authorization route',async()=>{
  const p=page();p.element('operator-key').value='synthetic-operator-secret';
  const pending=p.submit();
  assert.equal(p.element('operator-key').value,'');
  assert.equal(p.element('authorize').disabled,true);
  assert.equal(p.request().url,'/api/operator/authorize');
  assert.equal(p.request().options.headers['X-CSRF-Token'],'synthetic-csrf');
  assert.deepEqual(JSON.parse(p.request().options.body),{key:'synthetic-operator-secret'});
  p.reply(true);await pending;
  assert.equal(p.reloaded(),1);
});

test('failed pairing neither reloads nor retains or echoes credential',async()=>{
  const p=page();p.element('operator-key').value='synthetic-operator-secret';
  const pending=p.submit();p.reply(false);await pending;
  assert.equal(p.reloaded(),0);
  assert.equal(p.element('operator-key').value,'');
  assert.equal(p.element('authorize').disabled,false);
  assert.ok(!p.element('authorization-message').textContent.includes('synthetic-operator-secret'));
});
