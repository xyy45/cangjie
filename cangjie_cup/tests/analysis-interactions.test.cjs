'use strict';
const test=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const vm=require('node:vm');const path=require('node:path');
const root=path.resolve(__dirname,'..');
function setup(){
 const elements=new Map();
 const element=()=>({textContent:'',hidden:true,checked:false,disabled:false,value:'',dataset:{},style:{},classList:{toggle(){}},setAttribute(){},append(){},replaceChildren(){},querySelectorAll(){return[];},querySelector(){return null;}});
 const get=id=>{if(!elements.has(id))elements.set(id,element());return elements.get(id);};
 let resolveCatalog;const calls=[];
 const response=data=>({ok:true,json:async()=>data});
 const ctx={document:{getElementById:get,createElement:element,createElementNS:element},crypto:require('node:crypto').webcrypto,TextDecoder,FormData,csrf:'test',location:{origin:'http://localhost'},toast(){},setTimeout,clearTimeout,fetch:async url=>{
  calls.push(url);if(url==='/analysis/samples')return new Promise(resolve=>{resolveCatalog=data=>resolve(response(data));});
  if(url==='/analysis/samples/sum3')return response({source:{filename:'sample.cj',code:'func sample(): Int64 { return 1 }\n',line_count:1,source_sha256:'sample'},snapshot:null});
  if(url==='/api/analysis')return response({jobs:[]});throw Error(url);
 }};
 vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(root,'nexus/demo/static/analysis-core.js'),'utf8'),ctx);vm.runInContext(fs.readFileSync(path.join(root,'nexus/demo/static/analysis.js'),'utf8'),ctx);
 return {ctx,get,calls,resolve(data){resolveCatalog(data);},show(){return vm.runInContext('AnalysisUI.show()',ctx);}};
}

test('a late initial sample catalog never replaces the source the user already uploaded',async()=>{
 const {get,show,resolve,calls}=setup();const showing=show();const bytes=Buffer.from('func uploaded(): Int64 { return 42 }\n');
 get('analysis-file').onchange({target:{files:[{name:'user.cj',size:bytes.length,arrayBuffer:async()=>bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength)}],value:'upload'}});
 for(let n=0;n<10&&get('analysis-filename').textContent!=='user.cj';n++)await new Promise(setImmediate);
 assert.equal(get('analysis-filename').textContent,'user.cj');
 resolve({samples:[{id:'sum3',title:'sample'}]});await showing;
 assert.equal(get('analysis-filename').textContent,'user.cj');assert.equal(calls.includes('/analysis/samples/sum3'),false);
});
