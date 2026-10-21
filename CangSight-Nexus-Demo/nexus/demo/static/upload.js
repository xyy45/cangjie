'use strict';
const UploadUI=(()=>{
 let draft=null,busy=false,generation=0,key=null;
 const make=(tag,text,value)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(value!==undefined)n.value=value;return n;};
 async function send(path,body){
  const options=body===undefined?{}:{method:'POST',headers:{'Origin':location.origin,'X-CSRF-Token':csrf},body};
  if(body!==undefined&&!(body instanceof FormData)){options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
  const response=await fetch(path,options),data=await response.json();if(!response.ok)throw new Error(data.error||'上传操作失败');return data;
 }
 function render(){
  $('upload-open').disabled=starting||reviewBusy||flow.running;
  $('upload-prepare').disabled=busy||draft?.status==='CONFIRMED';
  $('upload-confirm').disabled=busy||!draft;
  const frozen=draft?.status==='CONFIRMED';
  $('upload-function').disabled=busy||!draft||frozen;$('upload-examples').disabled=busy||!draft||frozen;
  $('upload-file').disabled=busy;$('upload-goal').disabled=busy||!!draft;$('upload-recent').disabled=busy;
  $('upload-confirm').textContent=frozen?'进入工作台':'确认测试并进入工作台';
 }
 function scaffold(){
  const f=draft?.functions.find(f=>f.name===$('upload-function').value);if(!f)return;
  $('upload-examples').value=JSON.stringify(['target','regression'].map(suite=>({args:f.params.map(p=>p.type==='Bool'?false:0),expected:null,suite})),null,2);
 }
 function load(value){
  draft=value;$('upload-goal').value=value.goal;$('upload-function').replaceChildren(...value.functions.map(f=>make('option',f.name+'('+f.params.map(p=>p.name+': '+p.type).join(', ')+'): '+f.return_type,f.name)));
  $('upload-function').value=value.function||value.functions[0].name;
  $('upload-consent').checked=value.status==='CONFIRMED';
  $('upload-identity').textContent=value.filename+' · '+value.source_sha256;
  if(value.examples_json)$('upload-examples').value=value.examples_json;else scaffold();
  $('upload-status').textContent=value.status==='CONFIRMED'?'示例已冻结，进入工作台后点击“开始”。':
   '函数已读取。请填写真实输入及预期值（null必须替换），每种分组至少一项。';render();
 }
 function clear(){
  draft=null;key=null;$('upload-goal').value='';$('upload-file').value='';$('upload-function').replaceChildren();$('upload-examples').value='';
  $('upload-identity').textContent='';$('upload-consent').checked=false;$('upload-status').textContent='选择文件并填写预期行为，再读取函数。';render();
 }
 async function open(){
  if(starting||reviewBusy||flow.running)return;
  const version=++generation;busy=false;clear();$('upload-dialog').showModal();
  try{
   const data=await send('/api/uploads/repair');if(version!==generation||!$('upload-dialog').open)return;
   $('upload-recent').replaceChildren(make('option','选择本会话已上传记录',''),...data.uploads.map(u=>make('option',u.filename+' · '+(u.status==='CONFIRMED'?'已确认':'待确认')+' · '+u.id.slice(-6),u.id)));
  }catch(error){if(version===generation)$('upload-status').textContent=error.message;}
 }
 async function prepare(){
  if(busy)return;const file=$('upload-file').files[0],goal=$('upload-goal').value.trim();
  if(!file||!goal){$('upload-status').textContent='请选择.cj并填写预期行为';return;}
  busy=true;render();const version=generation;key=key||crypto.randomUUID();
  const body=new FormData();body.append('file',file);body.append('goal',goal);body.append('request_key',key);
  $('upload-status').textContent='检查受限语法并读取函数…';
  try{const result=await send('/api/uploads/repair',body);if(version===generation&&$('upload-dialog').open)load(result);}
  catch(error){if(version===generation)$('upload-status').textContent=error.message;}
  finally{if(version===generation){busy=false;render();}}
 }
 async function confirm(){
  if(busy||!draft)return;
  if(!$('upload-consent').checked){$('upload-status').textContent='请确认测试预期，并同意开始修复时向MCP和DeepSeek发送源码及公开示例';return;}
  busy=true;render();const version=generation;
  try{
   if(draft.status!=='CONFIRMED'){
    const result=await send('/api/uploads/repair/'+draft.id+'/confirm',{expected_version:draft.version,function:$('upload-function').value,examples_json:$('upload-examples').value,consent:true});
    if(version!==generation||!$('upload-dialog').open)return;draft=result;
   }
   const result=await selectCase(draft.id);if(version===generation&&result)$('upload-dialog').close();
  }catch(error){if(version===generation)$('upload-status').textContent=error.message;}
  finally{if(version===generation){busy=false;render();}}
 }
 $('upload-dialog').onclose=()=>{generation++;busy=false;draft=null;render();};
 $('upload-open').onclick=open;$('upload-prepare').onclick=prepare;$('upload-confirm').onclick=confirm;
 $('upload-function').onchange=scaffold;
 $('upload-file').onchange=()=>{generation++;busy=false;draft=null;key=null;$('upload-goal').disabled=false;$('upload-confirm').disabled=true;$('upload-identity').textContent='';$('upload-consent').checked=false;render();};
 $('upload-goal').oninput=()=>{key=null;};
 $('upload-recent').onchange=async()=>{
  const id=$('upload-recent').value;if(!id||busy)return;
  const version=++generation;busy=true;render();
  try{const value=await send('/api/uploads/repair/'+id);if(version===generation&&$('upload-dialog').open)load(value);}
  catch(error){if(version===generation)$('upload-status').textContent=error.message;}
  finally{if(version===generation){busy=false;render();}}
 };
 return{render};
})();
