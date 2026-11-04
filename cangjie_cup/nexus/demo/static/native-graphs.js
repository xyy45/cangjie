(function(root,factory){const api=factory(root);if(typeof module==='object'&&module.exports)module.exports=api;else root.NativeGraphUI=api;})(typeof globalThis!=='undefined'?globalThis:this,function(root){
'use strict';
const TYPES=['Ddg','Pdg','Sdg','Cfg','Cdg','Cg','Dfg'];
const LABELS={Ddg:'数据依赖 DDG',Pdg:'程序依赖 PDG',Sdg:'系统依赖 SDG',Cfg:'控制流 CFG',Cdg:'控制依赖 CDG',Cg:'函数调用 CG',Dfg:'数据流 DFG'};
function safeURL(value,kind,origin){
 if(typeof value!=='string'||!value.startsWith('/')||value.startsWith('//'))return false;
 try{const u=new URL(value,origin);return u.origin===origin&&!u.username&&!u.password&&!u.hash&&
  /^\/(?:api\/analysis\/|api\/demo\/(?:tasks|candidates)\/|analysis\/samples\/)/.test(u.pathname)&&
  (u.pathname.endsWith('/graphs/'+kind+'.svg')||kind==='Cg'&&u.pathname.endsWith('/callgraph.svg'))&&
  [...u.searchParams].every(([key,v])=>key==='download'&&v==='1');}catch{return false;}
}
function asset(report,kind,origin=root.location?.origin||'http://localhost'){
 const unavailable=reason=>({ready:false,reason});
 if(!TYPES.includes(kind))return unavailable('未知图类型');
 if(!report||['READY','RUNNING'].includes(report.status))return unavailable('等待本次分析结果');
 const bundle=report.native_graphs;
 if(bundle&&bundle.schema_version!==1)return unavailable('图像记录版本不可用');
 const entry=bundle?bundle.graphs?.[kind]:kind==='Cg'?report.callgraph:null;
 if(!entry)return unavailable('此记录尚未保存'+LABELS[kind]+'原图，请重新分析');
 if(entry.status!=='SAVED')return unavailable(entry.reason||'MCP未返回此类图');
 if(entry.source_sha256!==report.source?.source_sha256||entry.graph_type&&entry.graph_type!==kind)
  return unavailable('图像与当前源码或图类型不匹配');
 if(!safeURL(entry.view_url,kind,origin)||!safeURL(entry.download_url,kind,origin))return unavailable('图像地址无效');
 return {...entry,ready:true};
}
function fitSize(width,aspect){
 const w=Number.isFinite(width)&&width>0?width:900,r=Number.isFinite(aspect)&&aspect>0?aspect:1.6;
 return {width:w,height:Math.max(260,Math.min(900,w/r))};
}
class Viewport{
 constructor(){this.fit();}
 fit(){this.zoom=1;this.x=0;this.y=0;}
 zoomBy(delta){this.zoom=Math.max(1,Math.min(8,this.zoom+delta));if(this.zoom===1)this.fit();}
 panBy(x,y,width,height){const mx=width*(this.zoom-1)/2,my=height*(this.zoom-1)/2;this.x=Math.max(-mx,Math.min(mx,this.x+x));this.y=Math.max(-my,Math.min(my,this.y+y));}
}
function mount({onSelect}){
 const get=id=>root.document.getElementById(id),canvas=get('analysis-graph'),panel=get('analysis-graph-panel'),tabs=get('analysis-graph-types'),detail=get('analysis-node-detail'),download=get('analysis-graph-download');
 const pose=new Viewport(),dialog=get('analysis-graph-dialog');let key='',revision=0,image=null,aspect=1.6,drag=null,home=null,nextSibling=null;
 const make=(tag,cls,text)=>{const n=root.document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
 const buttons=TYPES.map(kind=>{const b=make('button','native-graph-tab',LABELS[kind]);b.type='button';b.dataset.kind=kind;b.onclick=()=>onSelect(kind);tabs.append(b);return b;});
 function resize(){const size=fitSize(canvas.clientWidth||900,aspect);canvas.style.height=size.height+'px';apply();}
 function apply(){if(image)image.style.transform=`translate(${pose.x}px, ${pose.y}px) scale(${pose.zoom})`;canvas.style.touchAction=pose.zoom>1?'none':'pan-y';canvas.style.cursor=image&&pose.zoom>1?'grab':'default';}
 function render(report,kind){
  get('analysis-graph-title').textContent=LABELS[kind];canvas.setAttribute('aria-label',LABELS[kind]);
  for(const b of buttons){const current=asset(report,b.dataset.kind);b.classList.toggle('selected',b.dataset.kind===kind);b.setAttribute('aria-pressed',String(b.dataset.kind===kind));b.title=current.ready?LABELS[b.dataset.kind]:current.reason;b.disabled=['READY','RUNNING'].includes(report?.status);}
  const selected=asset(report,kind),next=[report?.id,report?.source?.source_sha256,report?.status,kind,selected.view_url,selected.sha256,selected.ready,selected.reason].join('|');
  if(next===key)return;
  key=next;revision++;const token=revision;image=null;drag=null;pose.fit();canvas.replaceChildren();download.hidden=true;download.href='';
  if(!selected.ready){canvas.append(make('div','analysis-empty',selected.reason));detail.textContent=selected.reason;aspect=1.6;resize();return;}
  image=make('img','native-graph-image');image.alt=LABELS[kind];image.draggable=false;
  aspect=selected.aspect_ratio||1.6;const current=image;
  current.onload=()=>{if(token!==revision||image!==current)return;if(!selected.aspect_ratio&&current.naturalWidth&&current.naturalHeight){aspect=current.naturalWidth/current.naturalHeight;resize();}detail.textContent=LABELS[kind]+' · 100% · 放大后可拖拽查看';};
  current.onerror=()=>{if(token!==revision||image!==current)return;detail.textContent='原图读取失败，请核对证据或重新分析';download.hidden=true;};
  current.src=selected.view_url;canvas.append(current);download.href=selected.download_url;download.hidden=false;download.setAttribute('download','');detail.textContent=LABELS[kind]+' · 加载原图…';resize();
 }
 function zoom(delta){if(!image)return;pose.zoomBy(delta);pose.panBy(0,0,canvas.clientWidth||900,parseFloat(canvas.style.height)||500);apply();detail.textContent=Math.round(pose.zoom*100)+'% · '+(pose.zoom>1?'拖拽查看，适应全图可复位':'完整图');}
 function fit(){pose.fit();apply();if(image)detail.textContent='100% · 完整图';}
 function fullscreen(){
  if(dialog.open){dialog.close();return;}
  home=panel.parentNode;nextSibling=panel.nextSibling;dialog.append(panel);dialog.showModal();
  get('analysis-fullscreen').textContent='退出全屏';
  resize();
 }
 dialog.onclose=()=>{if(home)home.insertBefore(panel,nextSibling);home=null;get('analysis-fullscreen').textContent='全屏';resize();};
 canvas.onpointerdown=event=>{if(!image||pose.zoom<=1||event.button!==undefined&&event.button!==0)return;drag={x:event.clientX,y:event.clientY,id:event.pointerId};canvas.setPointerCapture?.(event.pointerId);event.preventDefault?.();};
 canvas.onpointermove=event=>{if(!drag||drag.id!==event.pointerId)return;pose.panBy(event.clientX-drag.x,event.clientY-drag.y,canvas.clientWidth||900,parseFloat(canvas.style.height)||500);drag={...drag,x:event.clientX,y:event.clientY};apply();};
 canvas.onpointerup=canvas.onpointercancel=()=>{drag=null;};
 if(root.ResizeObserver)new root.ResizeObserver(resize).observe(canvas);
 return {render,zoom,fit,fullscreen};
}
return {TYPES,LABELS,asset,fitSize,Viewport,mount};
});
