'use strict';
const UploadUI=(()=>{
 let draft=null,busy=false,generation=0,key=null,projectChecks=[];
 const draftEnabled=!!$('upload-draft-generate');
 let draftJob=null,draftRef=null,draftEpoch=0,draftTimer=null,draftBusy=false,draftUnresolved=false,draftError='',replacementArmed=false;
 const mode=()=>['project','directory'].includes($('upload-mode').value)?$('upload-mode').value:'single';
 const readEpoch={goal:0,examples:0,oracle:0,properties:0,relations:0,sequences:0},reading={goal:false,examples:false,oracle:false,properties:false,relations:false,sequences:false};
 function invalidateImports(kind){for(const name of kind?[kind]:['goal','examples','oracle','properties','relations','sequences']){readEpoch[name]++;reading[name]=false;}}
 function importing(){return reading.goal||reading.examples||reading.oracle||reading.properties||reading.relations||reading.sequences;}
 const make=(tag,text,value)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(value!==undefined)n.value=value;return n;};
 async function send(path,body){
  const options=body===undefined?{}:{method:'POST',headers:{'Origin':location.origin,'X-CSRF-Token':csrf},body};
  if(body!==undefined&&!(body instanceof FormData)){options.headers['Content-Type']='application/json';options.body=JSON.stringify(body);}
  const response=await fetch(path,options),data=await response.json();if(!response.ok){const error=new Error(data.error||'上传操作失败');error.status=response.status;error.code=data.code;throw error;}return data;
 }
 function resetRuleDraft(keepSource=false){
  const uncertain=draftUnresolved||draftBusy||['CREATED','STARTED','IN_DOUBT'].includes(draftJob?.call_state);
  draftEpoch++;if(draftTimer!==null){clearTimeout(draftTimer);draftTimer=null;}
  draftJob=null;draftBusy=false;draftError='';replacementArmed=false;draftUnresolved=keepSource?uncertain:false;if(!keepSource)draftRef=null;
  if(draftEnabled)$('upload-draft-consent').checked=false;
 }
 function selectedPaths(){return draft?.kind==='PROJECT'?projectChecks.filter(input=>input.checked).map(input=>input.value).sort():null;}
 function draftContext(){return{generation,epoch:draftEpoch,id:draft?.id,function:$('upload-function').value,paths:selectedPaths()};}
 function currentDraftContext(ctx){return ctx.generation===generation&&ctx.epoch===draftEpoch&&draft?.id===ctx.id&&ctx.function===$('upload-function').value&&JSON.stringify(ctx.paths)===JSON.stringify(selectedPaths())&&$('upload-dialog').open;}
 function matchingDraft(job){return job?.binding?.upload_id===draft?.id&&job.binding.upload_version===draft.version&&job.binding.source_sha256===draft.source_sha256&&job.binding.signature?.name===$('upload-function').value&&JSON.stringify(job.binding.allowed_paths)===JSON.stringify(selectedPaths()||['src/uploaded.cj']);}
 function renderRuleDraft(){
  if(!draftEnabled)return;
  const disabled=busy||importing()||!draft||draft.status==='CONFIRMED',result=draftJob?.result;
  $('upload-draft-consent').disabled=disabled||draftBusy;
  $('upload-draft-generate').disabled=disabled||draftBusy||draftUnresolved||draftJob?.call_state==='IN_DOUBT';
  $('upload-draft-query').disabled=disabled||draftBusy;
  $('upload-draft-apply').disabled=disabled||draftBusy||result?.status!=='DRAFT_READY';
  $('upload-draft-apply').textContent=replacementArmed?'确认替换并填入':'应用草案';
  $('upload-draft-preview').hidden=!result;
  $('upload-draft-summary').textContent=(draftJob?.model_id?draftJob.model_id+' · '+(draftJob.origin==='LIVE'?'模型请求':'测试夹具')+'：':'')+(result?.suggestion?.summary||'');
  $('upload-draft-assumptions').textContent=(result?.suggestion?.assumptions||[]).join('；');
  $('upload-draft-questions').textContent=(result?.suggestion?.questions||[]).join('；');
  $('upload-draft-examples-preview').value=result?.examples_json||'';$('upload-draft-oracle-preview').value=result?.oracle_json||'';
  $('upload-draft-status').textContent=(replacementArmed?'再次点击“确认替换并填入”将替换现有测试与规则，之后仍需核对并确认修复。':'')||draftError||(draftUnresolved||draftJob?.call_state==='IN_DOUBT'?'请求结果待核实，请查询原记录；不会自动重发。':draftBusy?'正在生成草案，关闭窗口不撤回已发送请求。':draftJob?.call_state==='FAILED'?'草案生成未成功：'+(draftJob.error_code||'请检查配置和原件'):result?.status==='DRAFT_READY'?'模型草案 · 结构校验完成，请核对业务含义后再应用。':result?.status==='NEEDS_CLARIFICATION'?'草案需要澄清，请补全预期行为后重新准备上传。':result?'草案校验未通过：'+(result.reason||'请检查规则'):'读取函数后可生成草案，或查询本会话已有记录。');
 }
 async function pollRuleDraft(ctx,id){
  try{
   const value=await send('/api/uploads/repair/'+ctx.id+'/rule-drafts/'+id);
   if(!currentDraftContext(ctx))return;
   if(!matchingDraft(value))throw Error('草案与当前源码、函数或范围不符');
   draftJob=value;draftUnresolved=value.call_state==='IN_DOUBT';draftBusy=['CREATED','STARTED'].includes(value.call_state);render();
   if(draftBusy)draftTimer=setTimeout(()=>pollRuleDraft(ctx,id),700);
  }catch(error){if(currentDraftContext(ctx)){draftBusy=false;draftUnresolved=true;draftError=error.message+'；请查询原记录，不自动重发。';render();}}
 }
 async function generateRuleDraft(){
  if(!draftEnabled||busy||importing()||draftBusy||!draft||draft.status==='CONFIRMED'||draftUnresolved||draftJob?.call_state==='IN_DOUBT')return;
  if(!$('upload-draft-consent').checked){$('upload-draft-status').textContent='请先同意现在发送所选源码和需求以生成草案。';return;}
  const paths=selectedPaths();if(paths&&(paths.length<1||paths.length>3)){$('upload-draft-status').textContent='请选择1至3个生产文件';return;}
  resetRuleDraft(true);draftUnresolved=false;const ctx=draftContext();draftBusy=true;$('upload-consent').checked=false;render();
  try{
   const body={expected_version:draft.version,function:ctx.function,request_key:crypto.randomUUID(),consent:true};if(paths)body.allowed_paths=paths;
   const value=await send('/api/uploads/repair/'+ctx.id+'/rule-drafts',body);
   if(!currentDraftContext(ctx))return;draftJob=value;await pollRuleDraft(ctx,value.id);
  }catch(error){if(currentDraftContext(ctx)){draftBusy=false;draftUnresolved=!error.status||error.status===409;draftError=error.message;render();}}
 }
 async function queryRuleDraft(){
  if(!draftEnabled||busy||draftBusy||!draft||draft.status==='CONFIRMED')return;
  const ctx=draftContext();draftBusy=true;draftError='';render();
  try{
   const data=await send('/api/uploads/repair/'+ctx.id+'/rule-drafts');if(!currentDraftContext(ctx))return;
   const found=(data.jobs||[]).find(matchingDraft);
   if(found)await pollRuleDraft(ctx,found.id);else{draftBusy=false;draftError=draftUnresolved?'尚未找到已登记请求，当前未知请求不会重发。':'当前函数和范围暂无已登记草案。';render();}
  }catch(error){if(currentDraftContext(ctx)){draftBusy=false;draftError=error.message;render();}}
 }
 async function applyRuleDraft(){
  if(!draftEnabled||busy||importing()||draftBusy||!draft||draft.status==='CONFIRMED'||draftJob?.result?.status!=='DRAFT_READY')return;
  if(($('upload-examples').value.trim()||$('upload-oracle').value.trim())&&!replacementArmed){replacementArmed=true;render();return;}
  replacementArmed=false;
  const ctx=draftContext();draftBusy=true;render();
  try{
   const body={expected_version:draft.version,function:ctx.function};if(ctx.paths)body.allowed_paths=ctx.paths;
   const result=await send('/api/uploads/repair/'+ctx.id+'/rule-drafts/'+draftJob.id+'/apply-preview',body);
   if(!currentDraftContext(ctx))return;
   invalidateImports('examples');invalidateImports('oracle');$('upload-examples').value=result.examples_json;$('upload-oracle').value=result.oracle_json;
   draftRef=result.rule_draft_ref;$('upload-consent').checked=false;draftBusy=false;$('upload-status').textContent='草案已填入，可编辑；请核对预期行为后确认。';render();
  }catch(error){if(currentDraftContext(ctx)){draftBusy=false;draftError=error.message;render();}}
 }
 async function importFile(kind,input){
  const file=input.files?.[0];input.value='';
  if(!file||busy||!$('upload-dialog').open||kind==='goal'&&draft||kind!=='goal'&&(!draft||draft.status==='CONFIRMED'))return;
  if(kind!=='goal')resetRuleDraft(true);
  const stamp=++readEpoch[kind],version=generation;reading[kind]=true;render();
  const current=()=>stamp===readEpoch[kind]&&version===generation&&$('upload-dialog').open&&!busy;
  try{
   const goal=kind==='goal',limit=goal||kind==='properties'||kind==='relations'||kind==='sequences'?16384:8192;
   if(!(goal?/\.(txt|md)$/i:/\.json$/i).test(file.name))throw Error(goal?'请选择.txt或.md预期行为文件':'请选择.json测试用例文件');
   if(file.size<=0||file.size>limit)throw Error(goal||kind==='properties'||kind==='relations'||kind==='sequences'?'文件为空或超过16KiB':'测试JSON文件为空或超过8KiB');
   const bytes=await file.arrayBuffer();
   if(!current())return;
   if(bytes.byteLength===0||bytes.byteLength>limit)throw Error('文件大小不符合限制');
   let text;try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{throw Error('文件必须使用UTF-8编码');}
   if(!text.trim()||text.includes('\0'))throw Error('文件内容为空或含空字节');
   if(goal){if(Array.from(text.trim()).length>4000)throw Error('预期行为最多4000字');}
   else{
    let parsed;try{parsed=JSON.parse(text);}catch{throw Error('测试文件不是有效JSON，请检查格式');}
    if(kind==='examples'&&(!Array.isArray(parsed)||!parsed.length))throw Error('测试JSON应为非空用例数组');
    if(kind==='oracle'&&(!parsed||typeof parsed!=='object'||Array.isArray(parsed)))throw Error('独立规则应为JSON对象');
    if(kind==='properties'&&(!parsed||typeof parsed!=='object'||Array.isArray(parsed)))throw Error('业务属性应为JSON对象');
    if(kind==='relations'&&(!parsed||typeof parsed!=='object'||Array.isArray(parsed)))throw Error('业务关系应为JSON对象');
    if(kind==='sequences'&&(!parsed||typeof parsed!=='object'||Array.isArray(parsed)))throw Error('状态序列应为JSON对象');
   }
   $('upload-'+kind).value=text;
   if(goal)key=null;
   $('upload-consent').checked=false;
   $('upload-status').textContent='已导入 '+file.name+'，可继续检查和编辑。';
  }catch(error){if(current())$('upload-status').textContent=error.message||'文件读取失败';}
  finally{if(stamp===readEpoch[kind]){reading[kind]=false;render();}}
 }
 function render(){
  $('upload-open').disabled=starting||reviewBusy||flow.running;
  $('upload-prepare').disabled=busy||importing()||draft?.status==='CONFIRMED';
  $('upload-confirm').disabled=busy||importing()||draftBusy||!draft;
  const frozen=draft?.status==='CONFIRMED';
  $('upload-oracle').disabled=busy||!draft||frozen;
  $('upload-properties').disabled=busy||!draft||frozen;
  $('upload-relations').disabled=busy||!draft||frozen;
  $('upload-sequences').disabled=busy||!draft||frozen;
  const signature=draft?.functions.find(f=>f.name===$('upload-function').value);
  $('upload-properties-aliases').textContent=signature?[...signature.params.map((p,i)=>'arg'+i+' = '+p.name+' ('+p.type+')'),'result = 实际返回 ('+signature.return_type+')'].join('；'):'';
  $('upload-relations-aliases').textContent=signature?[...['left','right'].flatMap(side=>signature.params.map((p,i)=>side+'_arg'+i+' = '+p.name+' ('+p.type+')')),'left_result / right_result = 左右实际返回 ('+signature.return_type+')'].join('；'):'';
  $('upload-sequences-aliases').textContent=signature?[...signature.params.map((p,i)=>'arg'+i+' = '+p.name+' ('+p.type+')'),'initial_state = 初态；before_state = 当前前态；expected_state = 模型参考状态；state_param指定状态参数，context_params按参数位置使用ctx别名'].join('；'):'';
  $('upload-function').disabled=busy||!draft||frozen;$('upload-examples').disabled=busy||!draft||frozen;
  $('upload-file').disabled=busy;$('upload-goal').disabled=busy||!!draft;$('upload-recent').disabled=busy;
  $('upload-mode').disabled=busy;$('upload-directory').disabled=busy;
  $('upload-file').hidden=mode()==='directory';$('upload-directory').hidden=mode()!=='directory';
  $('upload-file').accept=mode()==='project'?'.zip':'.cj';
  $('upload-source-help').textContent=mode()==='single'?'单个.cj，最多64KiB／1000行。支持只读具名struct/class及Int64／Bool／String／Array<Int64>函数（String最多256 UTF-8字节；.size为字节数，.toRuneArray().size为码点数）、只读Int64数组最多16项，支持字面量、下标读取、size、for遍历；局部变量、条件、while和同文件调用；无package时补固定包声明。':
   '工程ZIP／目录最多2MiB、100文件、16个包；使用单一cjpm构建根和固定1.0.5 SDK，支持冻结的工程内跨包导入、只读struct/class、纯实例方法及Int64／Bool／String／Array<Int64>函数。String最多256 UTF-8字节，数组最多16项；测试支持标准@Test／@TestCase中的字面量@Expect及返回对象的字段投影。';
  for(const input of projectChecks){input.disabled=busy||frozen;if(input.scopeLabel)input.scopeLabel.textContent=input.checked?'允许修改正文':'只读依赖';}
  renderPackages();
  for(const [kind,disabled] of [['goal',busy||!!draft],['examples',busy||!draft||frozen],['oracle',busy||!draft||frozen],['properties',busy||!draft||frozen],['relations',busy||!draft||frozen],['sequences',busy||!draft||frozen]]){
   $('upload-'+kind+'-import').disabled=disabled;$('upload-'+kind+'-file').disabled=disabled;
   $('upload-'+kind+'-import').textContent=reading[kind]?'重新选择文件':'导入文件';
  }
  $('upload-confirm').textContent=frozen?'进入工作台':'确认测试并进入工作台';renderRuleDraft();
 }
 function renderPackages(){
  const section=$('upload-packages');if(!section)return;
  const index=draft?.kind==='PROJECT'&&draft.project_index?.version===2?draft.project_index:null;
  section.hidden=!index;
  $('upload-package-graph').replaceChildren();$('upload-package-imports').replaceChildren();
  $('upload-package-origin').textContent='';$('upload-package-hash').textContent='';
  if(!index)return;
  $('upload-package-origin').textContent='源码声明依赖 · 导入与配置冻结';
  $('upload-package-hash').textContent=index.graph_hash;
  const graph=index.dependency_graph;
  for(const [label,edges] of [['生产依赖',graph.production_edges],['测试依赖',graph.test_edges]]){
   for(const [from,to] of edges){const row=make('div');row.className='upload-package-edge';row.append(make('span',label),make('code',from+' → '+to));$('upload-package-graph').append(row);}
  }
  if(!graph.production_edges.length&&!graph.test_edges.length)$('upload-package-graph').append(make('p','无跨包导入边'));
  for(const item of graph.imports){
   const row=make('div');row.className='upload-package-import';
   row.append(make('code',item.path+':'+item.line),make('span',item.specifier+(item.alias?' as '+item.alias:'')+' · '+(item.origin==='WORKSPACE'?'工程内导入':'固定 SDK 导入')));
   $('upload-package-imports').append(row);
  }
 }
 function scaffold(){
  invalidateImports('properties');invalidateImports('relations');invalidateImports('sequences');$('upload-properties').value='';$('upload-relations').value='';$('upload-sequences').value='';
  resetRuleDraft();  invalidateImports('examples');invalidateImports('oracle');$('upload-oracle').value='';$('upload-consent').checked=false;
  const f=draft?.functions.find(f=>f.name===$('upload-function').value);if(!f)return;
  const types=f.types||draft?.types||draft?.project_index?.types||{};
  const seed=kind=>kind==='Array<Int64>'?[]:kind==='Bool'?false:kind==='String'?'':kind==='Int64'?0:Object.prototype.hasOwnProperty.call(types,kind)?{$type:kind,fields:Object.fromEntries(types[kind].fields.map(field=>[field.name,seed(field.type)]))}:null;
  $('upload-examples').value=JSON.stringify(['target','regression'].map(suite=>({args:f.params.map(p=>seed(p.type)),expected:null,suite})),null,2);
 }
 function load(value){
  resetRuleDraft();  invalidateImports();draft=value;$('upload-mode').value=value.kind==='PROJECT'?'project':'single';
  $('upload-goal').value=value.goal;$('upload-function').replaceChildren(...value.functions.map(f=>make('option',f.name+'('+f.params.map(p=>p.name+': '+p.type).join(', ')+'): '+f.return_type+(f.path?' · '+f.path:''),f.name)));
  $('upload-function').value=value.function||value.functions[0].name;
  $('upload-consent').checked=value.status==='CONFIRMED';
  $('upload-identity').textContent=value.filename+' · '+value.source_sha256;
  if(value.examples_json)$('upload-examples').value=value.examples_json;else scaffold();
  $('upload-oracle').value=value.oracle_json||'';
  $('upload-properties').value=value.properties_json||'';
  $('upload-relations').value=value.relations_json||'';
  $('upload-sequences').value=value.sequences_json||'';
  projectChecks=[];$('upload-project-tree').replaceChildren();$('upload-project').hidden=value.kind!=='PROJECT';
  if(value.kind==='PROJECT'){
   $('upload-project-summary').textContent='构建根 / · '+value.production_paths.length+' 个生产文件 · '+value.original_tests.length+' 个原测试';
   const selected=value.allowed_paths||value.production_paths.slice(0,3);
   for(const path of Object.keys(value.original_manifest).sort()){
    const row=make('label');row.className='upload-project-row';
    if(value.production_paths.includes(path)){
     const input=make('input');input.type='checkbox';input.value=path;input.checked=selected.includes(path);
     input.onchange=()=>{resetRuleDraft();invalidateImports('properties');invalidateImports('relations');invalidateImports('sequences');$('upload-consent').checked=false;render();};projectChecks.push(input);row.append(input);
    }
    const label=make('span',value.production_paths.includes(path)?'生产源码':path.endsWith('_test.cj')?'原测试':'配置／文档');
    if(value.project_index?.version===2&&value.production_paths.includes(path))projectChecks.at(-1).scopeLabel=label;
    row.append(make('code',path),label);$('upload-project-tree').append(row);
   }
  }
  $('upload-status').textContent=value.status==='CONFIRMED'?'示例已冻结，进入工作台后点击“开始”。':
   '函数已读取。请填写真实输入及预期值（null必须替换），每种分组至少一项。';render();
 }
 function clear(){
  $('upload-properties').value='';$('upload-relations').value='';$('upload-sequences').value='';
  resetRuleDraft();  invalidateImports();draft=null;key=null;projectChecks=[];$('upload-project').hidden=true;$('upload-project-tree').replaceChildren();
  $('upload-mode').value='single';$('upload-directory').value='';$('upload-goal').value='';$('upload-file').value='';$('upload-function').replaceChildren();$('upload-examples').value='';$('upload-oracle').value='';
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
  if(busy||importing())return;const selectedMode=mode(),file=$('upload-file').files[0],directory=Array.from($('upload-directory').files||[]),goal=$('upload-goal').value.trim();
  if(!(selectedMode==='directory'?directory.length:file)||!goal){$('upload-status').textContent='请选择源码文件／工程并填写预期行为';return;}
  busy=true;render();const version=generation;key=key||crypto.randomUUID();
  const body=new FormData();
  if(selectedMode==='directory'){
   body.append('paths_json',JSON.stringify(directory.map(f=>f.webkitRelativePath||f.name)));
   for(const selected of directory)body.append('files',selected);
  }else body.append('file',file);
  body.append('goal',goal);body.append('request_key',key);
  $('upload-status').textContent='检查受限语法并读取函数…';
  try{const result=await send(selectedMode==='single'?'/api/uploads/repair':'/api/uploads/repair/project',body);if(version===generation&&$('upload-dialog').open)load(result);}
  catch(error){if(version===generation)$('upload-status').textContent=error.message;}
  finally{if(version===generation){busy=false;render();}}
 }
 async function confirm(){
  if(busy||importing()||draftBusy||!draft)return;
  if(!$('upload-consent').checked){$('upload-status').textContent='请确认测试预期，并同意开始修复时向MCP和DeepSeek发送源码及公开示例';return;}
  busy=true;render();const version=generation;
  try{
   if(draft.status!=='CONFIRMED'){
    const body={expected_version:draft.version,function:$('upload-function').value,examples_json:$('upload-examples').value,consent:true};
    if(draft.kind==='PROJECT'){
     body.allowed_paths=projectChecks.filter(input=>input.checked).map(input=>input.value);
     if(body.allowed_paths.length<1||body.allowed_paths.length>3)throw Error('请选择1至3个允许修改的生产文件');
    }
    if(draftRef)body.rule_draft_ref=draftRef;
    if($('upload-oracle').value.trim())body.oracle_json=$('upload-oracle').value;
    if($('upload-properties').value.trim())body.properties_json=$('upload-properties').value;
    if($('upload-relations').value.trim())body.relations_json=$('upload-relations').value;
    if($('upload-sequences').value.trim())body.sequences_json=$('upload-sequences').value;
    const result=await send('/api/uploads/repair/'+draft.id+'/confirm',body);
    if(version!==generation||!$('upload-dialog').open)return;draft=result;
   }
   const result=await selectCase(draft.id);if(version===generation&&result)$('upload-dialog').close();
  }catch(error){if(version===generation)$('upload-status').textContent=error.message;}
  finally{if(version===generation){busy=false;render();}}
 }
 $('upload-dialog').onclose=()=>{resetRuleDraft();invalidateImports();generation++;busy=false;draft=null;render();};
 $('upload-open').onclick=open;$('upload-prepare').onclick=prepare;$('upload-confirm').onclick=confirm;
 $('upload-function').onchange=()=>{scaffold();render();};
 for(const kind of ['goal','examples','oracle','properties','relations','sequences']){
  $('upload-'+kind+'-import').onclick=()=>{if(!$('upload-'+kind+'-file').disabled)$('upload-'+kind+'-file').click();};
  $('upload-'+kind+'-file').onchange=event=>importFile(kind,event.target);
 }
 const sourceChanged=()=>{
  $('upload-properties').value='';$('upload-relations').value='';$('upload-sequences').value='';
  resetRuleDraft();  $('upload-oracle').value='';invalidateImports();generation++;busy=false;draft=null;key=null;projectChecks=[];
  $('upload-project').hidden=true;$('upload-project-tree').replaceChildren();$('upload-function').replaceChildren();$('upload-examples').value='';
  $('upload-goal').disabled=false;$('upload-confirm').disabled=true;$('upload-identity').textContent='';$('upload-consent').checked=false;render();
 };
 $('upload-file').onchange=sourceChanged;$('upload-directory').onchange=sourceChanged;
 $('upload-mode').onchange=()=>{$('upload-file').value='';$('upload-directory').value='';sourceChanged();};
 $('upload-goal').oninput=()=>{invalidateImports('goal');key=null;render();};
 for(const kind of ['examples','oracle','properties','relations','sequences'])$('upload-'+kind).oninput=()=>{resetRuleDraft(true);invalidateImports(kind);$('upload-consent').checked=false;render();};
 $('upload-recent').onchange=async()=>{
  const id=$('upload-recent').value;if(!id||busy)return;
  resetRuleDraft();invalidateImports();const version=++generation;busy=true;render();
  try{const value=await send('/api/uploads/repair/'+id);if(version===generation&&$('upload-dialog').open)load(value);}
  catch(error){if(version===generation)$('upload-status').textContent=error.message;}
  finally{if(version===generation){busy=false;render();}}
 };
 if(draftEnabled){$('upload-draft-generate').onclick=generateRuleDraft;$('upload-draft-query').onclick=queryRuleDraft;$('upload-draft-apply').onclick=applyRuleDraft;}
 return{render};
})();
