/* Hospital Warehouse IMS: bilingual UI runtime.
 * Edit the Arabic wording in static/locales/ar.json (English source strings are the keys).
 * Interface locale only: this NEVER changes item/batch/department values in the database.
 */
(function(){
  'use strict';
  const KEY='hospital-warehouse-language';
  const supported=['ar','en'];
  let language='ar';
  try { const saved=localStorage.getItem(KEY);if(supported.includes(saved))language=saved; }catch(_e){}
  const originalTitle=document.title;
  let dict={};
  const originals=new WeakMap();
  const attrOriginals=new WeakMap();
  let observer, pending=false, ready=false;
  const normalize=s=>String(s||'').replace(/\s+/g,' ').trim();

  function translate(original){
    const s=normalize(original);
    if(!s||language==='en')return original;
    if(Object.prototype.hasOwnProperty.call(dict,s))return dict[s];
    let unitMatch=s.match(/^([\d,.]+) (tablet|capsule|bottle|ampoule|vial|tube|suppository|drops|piece|bag|pack|roll|packet|dozen)$/); if(unitMatch)return unitMatch[1]+' '+(dict[unitMatch[2]]||unitMatch[2]);
    let pages=s.match(/^Showing ([\d,]+)–([\d,]+) of ([\d,]+)$/);if(pages)return `عرض ${pages[1]}–${pages[2]} من أصل ${pages[3]}`;
    let dynamic=s.match(/^([\d,]+) items$/); if(dynamic)return dynamic[1]+' مواد';
    dynamic=s.match(/^([\d,]+) item lines$/); if(dynamic)return dynamic[1]+' سطر مواد';
    dynamic=s.match(/^Opening lot ([\d,]+)$/); if(dynamic)return 'الوجبة '+dynamic[1];
    dynamic=s.match(/^([\d,]+) IQD · ([\d,]+) fils$/); if(dynamic)return dynamic[1]+' دينار · '+dynamic[2]+' فلس';
    dynamic=s.match(/^★ Expiry date not recorded · Recommended$/); if(dynamic)return '★ تاريخ الصلاحية غير مسجل · الموصى بها';
    dynamic=s.match(/^★ (.+) · Recommended$/); if(dynamic)return '★ '+dynamic[1]+' · الموصى بها';
    dynamic=s.match(/^Dispatch\/receipt: (.+)$/); if(dynamic)return 'التجهيز / الاستلام: '+dynamic[1];
    dynamic=s.match(/^Google Drive backups \(([\d,]+)\)$/); if(dynamic)return 'نسخ Google Drive الاحتياطية ('+dynamic[1]+')';
    // Compose messages containing database values without translating user-entered data.
    let m=s.match(/^Undo recorded shipment · (.+)$/);
    if(m)return 'التراجع عن حركة مخزنية · '+m[1];
    m=s.match(/^Recovery saved as a new, permanent audit event\. (.+)$/);
    if(m)return 'تم حفظ التصحيح بسجل تدقيق دائم جديد · '+m[1];
    m=s.match(/^Welcome back, (.+)$/);
    if(m)return 'مرحباً بعودتك، '+m[1];
    m=s.match(/^Existing category: (.+) — please choose an approved book for this branch\.$/);
    if(m)return 'التصنيف السابق: '+m[1]+' — يرجى اختيار سجل معتمد لهذا الفرع.';
    m=s.match(/^Edit account: (.+)$/);
    if(m)return 'تعديل الحساب: '+m[1];
    m=s.match(/^Reset password: (.+)$/);
    if(m)return 'إعادة تعيين كلمة مرور: '+m[1];
    m=s.match(/^(\d+) registered items$/);
    if(m)return m[1]+' صنف مسجّل';
    m=s.match(/^([\d,]+) item\(s\) under the reorder threshold · ([\d,]+) batch\(es\) expiring in the next 60 days\.$/);
    if(m)return `${m[1]} صنف دون الحد الأدنى · ${m[2]} تشغيلة تنتهي خلال ٦٠ يوماً.`;
    m=s.match(/^([\d,]+) low-stock items · ([\d,]+) expiring batches$/);
    if(m)return `${m[1]} أصناف منخفضة المخزون · ${m[2]} تشغيلات تقترب صلاحيتها من الانتهاء`;
    m=s.match(/^Saved (.+)\. Warehouse balance updated\.$/);
    if(m)return `تم حفظ الحركة ${m[1]} وتحديث رصيد المخزن.`;
    m=s.match(/^(.+) · Batch ([^·]+) · (.+) · Exp (.+)$/);
    if(m)return `${m[1]} · تشغيلة ${m[2]} · ${m[3]} · الصلاحية ${m[4]}`;
    // V4.14 dynamically generated captions retain product names and IDs.
    m=s.match(/^All stored lots — (.+)$/);
    if(m)return 'جميع الوجبات المخزنة — '+m[1];
    m=s.match(/^Lot ID (\d+)$/);
    if(m)return 'معرّف الوجبة '+m[1];
    m=s.match(/^([\d,]+) available$/);
    if(m)return m[1]+' عمود متاح';
    m=s.match(/^View all ([\d,]+) stored lots$/);
    if(m)return 'عرض جميع الوجبات المخزنة ('+m[1]+')';
    // V4.13 count text on detailed Inventory / المواقف tables.
    m=s.match(/^([\d,]+) of ([\d,]+) items · ([\d,]+) matching records$/);
    if(m)return `${m[1]} من أصل ${m[2]} صنف · ${m[3]} سجل مطابق`;
    m=s.match(/^([\d,]+) of ([\d,]+) items$/);
    if(m)return `${m[1]} من أصل ${m[2]} صنف`;
    m=s.match(/^([\d,]+) recorded line\(s\)$/);
    if(m)return `${m[1]} حركة مسجلة`;
    m=s.match(/^([\d,]+) stored lot\(s\)$/);
    if(m)return `${m[1]} وجبة محفوظة`;
    m=s.match(/^([\d,]+) lots?$/);
    if(m)return `${m[1]} وجبة`;
    m=s.match(/^([\d,]+) expiring lots before ([0-9-]+)$/);
    if(m)return `${m[1]} وجبة قريبة النفاذ قبل ${m[2]}`;
    m=s.match(/^([\d,]+) items with no stock$/);
    if(m)return `${m[1]} صنف بدون رصيد`;
    m=s.match(/^([\d,]+) items (below|above) ([\d.]+)% of monthly need$/);
    if(m)return `${m[1]} صنف ${m[2]==='below'?'أقل من':'أكثر من'} ${m[3]}٪ من الاحتياج الشهري`;
    m=s.match(/^([\d,]+) items (below|above) ([\d.]+)%$/);
    if(m)return `${m[1]} صنف ${m[2]==='below'?'أقل من':'أكثر من'} ${m[3]}٪`;
    m=s.match(/^Monthly need = annual need ÷ 12\. Scarce: below ([\d.]+)%\. Surplus: above ([\d.]+)%\.$/);
    if(m)return `الاحتياج الشهري = الاحتياج السنوي ÷ 12. الشحيحة: أقل من ${m[1]}٪، والفائضة: أكثر من ${m[2]}٪.`;
    m=s.match(/^([0-9]+) item\(s\) under the reorder threshold/);
    if(m)return s.replace(' item(s) under the reorder threshold',' صنف دون حد التنبيه');
    return original;
  }
  function shouldSkip(node){
    let parent=node.parentElement;
    if(!parent)return true;
    return !!parent.closest('script,style,noscript,textarea,code,pre,[translate="no"],[data-i18n-skip],.no-translate,[contenteditable="true"]');
  }
  function applyNode(node){
    if(shouldSkip(node))return;
    const current=node.nodeValue;
    let data=originals.get(node);
    if(!data){data={raw:current,last:current};originals.set(node,data)}
    else if(current!==data.last){data.raw=current;data.last=current}
    const ws=data.raw.match(/^(\s*)([\s\S]*?)(\s*)$/);
    if(!ws||!ws[2])return;
    const next=ws[1]+(language==='ar'?translate(ws[2]):ws[2])+ws[3];
    if(current!==next)node.nodeValue=next;
    data.last=next;
  }
  function applyAttrs(el){
    if(el.matches('[translate="no"],[data-i18n-skip],.no-translate'))return;
    const allowed=['placeholder','aria-label','title',...(el.tagName==='OPTGROUP'?['label']:[])];
    let entries=attrOriginals.get(el);
    if(!entries){entries={};attrOriginals.set(el,entries)}
    for(const attr of allowed){
      if(!el.hasAttribute(attr))continue;
      const current=el.getAttribute(attr);
      if(!entries[attr]||current!==entries[attr].last)entries[attr]={raw:current,last:current};
      const next=language==='ar'?translate(entries[attr].raw):entries[attr].raw;
      if(current!==next)el.setAttribute(attr,next);
      entries[attr].last=next;
    }
  }
  function paintSwitches(){
    document.querySelectorAll('[data-lang-switcher] [data-language]').forEach(button=>{
      const selected=button.dataset.language===language;
      button.classList.toggle('selected',selected);
      button.setAttribute('aria-pressed',String(selected));
    });
  }
  function apply(){
    if(!document.body)return;
    if(observer)observer.disconnect();
    document.documentElement.lang=language;
    document.documentElement.dir=language==='ar'?'rtl':'ltr';
    document.title=language==='ar'?translate(originalTitle):originalTitle;
    document.querySelectorAll('[data-lang-switcher]').forEach(el=>{const label=language==='ar'?'لغة الواجهة':'Interface language';if(el.getAttribute('aria-label')!==label)el.setAttribute('aria-label',label)});
    const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
    while(walker.nextNode())applyNode(walker.currentNode);
    document.querySelectorAll('[placeholder],[aria-label],[title],optgroup[label]').forEach(applyAttrs);
    document.querySelectorAll('[data-localized-value]').forEach(el=>{el.value=translate(el.dataset.localizedValue)});
    paintSwitches();
    if(observer)observer.observe(document.body,{subtree:true,childList:true});
    document.documentElement.classList.remove('i18n-pending');
  }
  function schedule(){
    if(pending||!ready)return;
    pending=true;
    requestAnimationFrame(()=>{pending=false;apply()});
  }
  function setLanguage(next){
    if(!supported.includes(next))return;
    language=next;
    try{localStorage.setItem(KEY,next)}catch(_e){}
    apply();
    window.dispatchEvent(new CustomEvent('warehouse:languagechange',{detail:{language}}));
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('[data-language]');
    if(button&&button.closest('[data-lang-switcher]')){event.preventDefault();setLanguage(button.dataset.language)}
  });
  window.HWLang={get:()=>language,set:setLanguage,t:(s)=>language==='ar'?translate(s):s,apply,ready:()=>ready};
  async function init(){
    try{
      const response=await fetch('/static/locales/ar.json',{cache:'no-store'});
      if(!response.ok)throw Error('Arabic terminology file unavailable');
      dict=await response.json();
    }catch(error){console.warn('Arabic language file could not load:',error)}
    observer=new MutationObserver(schedule);
    ready=true;apply();
    window.dispatchEvent(new CustomEvent('warehouse:i18nready',{detail:{language}}));
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init,{once:true});
  else init();
})();
