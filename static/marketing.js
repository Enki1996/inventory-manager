/* The public website only. No access to stock, database or user sessions. */
(function(){
  'use strict';
  const nav=document.getElementById('siteNav');
  const button=document.querySelector('.menu-trigger');
  if(button && nav){
    function close(){nav.classList.remove('open');button.setAttribute('aria-expanded','false')}
    button.addEventListener('click',()=>{const active=nav.classList.toggle('open');button.setAttribute('aria-expanded',String(active))});
    nav.addEventListener('click',event=>{if(event.target.closest('a'))close()});
    document.addEventListener('keydown',event=>{if(event.key==='Escape')close()});
    document.addEventListener('click',event=>{if(!nav.contains(event.target)&&!button.contains(event.target))close()});
  }
  const tabs=Array.from(document.querySelectorAll('[data-preview]'));
  const panes=Array.from(document.querySelectorAll('[data-preview-panel]'));
  function activate(id){
    tabs.forEach(tab=>{const active=tab.dataset.preview===id;tab.classList.toggle('active',active);tab.setAttribute('aria-selected',String(active));tab.tabIndex=active?0:-1});
    panes.forEach(pane=>{pane.hidden=pane.dataset.previewPanel!==id});
  }
  tabs.forEach((tab,index)=>{
    tab.addEventListener('click',()=>activate(tab.dataset.preview));
    tab.addEventListener('keydown',event=>{
      if(event.key!=='ArrowRight'&&event.key!=='ArrowLeft')return;
      event.preventDefault();
      const next=(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
      tabs[next].focus();activate(tabs[next].dataset.preview);
    });
  });
  const links=Array.from(document.querySelectorAll('a[data-section]'));
  if('IntersectionObserver' in window&&links.length){
    const observer=new IntersectionObserver(entries=>{
      const visible=entries.filter(e=>e.isIntersecting).sort((a,b)=>b.intersectionRatio-a.intersectionRatio);
      if(!visible.length)return;
      links.forEach(a=>a.classList.toggle('active',a.dataset.section===visible[0].target.id));
    },{rootMargin:'-21% 0px -49% 0px',threshold:[0,.15,.3,.55]});
    document.querySelectorAll('.section-anchor').forEach(section=>observer.observe(section));
  }

  // V4.24: restrained pointer parallax on the illustrative warehouse network.
  // The effect is purely visual; no mouse tracking is stored or transmitted.
  const scene=document.querySelector('[data-hero-scene]');
  if(scene && window.matchMedia('(pointer:fine)').matches && !window.matchMedia('(prefers-reduced-motion:reduce)').matches){
    const target=scene.querySelector('[data-hero-tilt]');
    let frame=0, x=0, y=0;
    const paint=()=>{
      frame=0;
      scene.style.setProperty('--mx',(x*100).toFixed(1)+'%');
      scene.style.setProperty('--my',(y*100).toFixed(1)+'%');
      scene.style.setProperty('--tilt-x',((.5-y)*4.5).toFixed(2)+'deg');
      scene.style.setProperty('--tilt-y',((x-.5)*5.5).toFixed(2)+'deg');
    };
    scene.addEventListener('pointermove',event=>{
      if(event.pointerType!=='mouse' && event.pointerType!=='pen') return;
      const rect=target.getBoundingClientRect();
      x=Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width));
      y=Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height));
      if(!frame)frame=requestAnimationFrame(paint);
    },{passive:true});
    scene.addEventListener('pointerleave',()=>{
      if(frame){cancelAnimationFrame(frame);frame=0}
      scene.style.removeProperty('--mx');scene.style.removeProperty('--my');
      scene.style.removeProperty('--tilt-x');scene.style.removeProperty('--tilt-y');
    });
  }
})();
