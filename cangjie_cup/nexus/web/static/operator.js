const form=document.getElementById('operator-form');
form.addEventListener('submit',async event=>{
  event.preventDefault();
  const input=document.getElementById('operator-key'),button=document.getElementById('authorize');
  const key=input.value;input.value='';button.disabled=true;
  try {
    const response=await fetch('/api/operator/authorize',{method:'POST',headers:{
      'Content-Type':'application/json','Origin':location.origin,
      'X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content},body:JSON.stringify({key})});
    if (!response.ok) throw new Error();
    location.reload();
  } catch {
    document.getElementById('authorization-message').textContent='授权未完成，请核对本机凭据；工作台只允许已确认的操作者使用。';
  } finally {button.disabled=false;}
});
