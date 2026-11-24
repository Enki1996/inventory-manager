const form = document.getElementById('loginForm');
const notice = document.querySelector('.demo-note');
notice.innerHTML = '<b>Connected test database.</b> Sign in using an administrator-created account. This early build is intended for testing, not live medical operations.';
notice.setAttribute('role','status');
queueMicrotask(()=>window.HWLang?.apply());
document.getElementById('eyeToggle').addEventListener('click',()=>{
  const pass=document.getElementById('password');const visible=pass.type==='text';pass.type=visible?'password':'text';
  document.getElementById('eyeSymbol').setAttribute('href',visible?'#ico-eye':'#ico-eyeoff');
  document.getElementById('eyeToggle').setAttribute('aria-label',visible?'Show password':'Hide password');
});
form.addEventListener('submit',async e=>{
 e.preventDefault(); if(!form.reportValidity()) return;
 const button=form.querySelector('[type=submit]');button.disabled=true;const old=button.innerHTML;button.textContent='Signing in...';
 try{
   const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},credentials:'same-origin',body:JSON.stringify({username:document.getElementById('email').value.trim(),password:document.getElementById('password').value})});
   const data=await r.json();if(!r.ok)throw Error(data.detail||'Sign in failed');
   window.location.href='/dashboard.html';
 }catch(err){notice.textContent=window.HWLang?.t(err.message)||err.message;notice.style.color='#b34e4e'}
 finally{button.disabled=false;button.innerHTML=old}
});
document.getElementById('forgot').addEventListener('click',e=>{e.preventDefault();notice.textContent='Contact the warehouse administrator to reset your password.';notice.style.color='#356e80'});
