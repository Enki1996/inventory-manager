/* IMS V4.27 · Dedicated, read-only Warehouse Statements print designer.
 * Always fetches the complete current report through authenticated endpoints.
 * No inventory or audit records are modified by printing.
 */
(()=>{'use strict';
const $=(s,r=document)=>r.querySelector(s), $$=(s,r=document)=>[...r.querySelectorAll(s)];
const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const params=new URLSearchParams(location.search);
const allowedModes=['missing','scarce','surplus','near_expiry'];
const mode=allowedModes.includes(params.get('mode'))?params.get('mode'):'near_expiry';
const userLang=params.get('lang')||(()=>{try{return localStorage.getItem('hospital-warehouse-language')}catch(_){return null}})();
let lang=userLang==='en'?'en':'ar';
const BRANCH={medication:{ar:'الأدوية',en:'Medication'},medical_supplies:{ar:'المستلزمات الطبية',en:'Medical Supplies'},surgical_instruments:{ar:'الأدوات الجراحية',en:'Surgical Instruments'}};
const MODE={
 missing:{ar:'موقف المواد المفقودة',en:'Missing-stock statement'},
 scarce:{ar:'موقف المواد الشحيحة',en:'Scarce-materials statement'},
 surplus:{ar:'موقف المواد الفائضة',en:'Surplus-materials statement'},
 near_expiry:{ar:'موقف المواد قريبة النفاذ',en:'Near-expiry materials statement'}
};
const WORDS={
 ar:{subhead:'نظام إدارة المخزون · مركز إعداد التقارير',back:'العودة إلى المواقف',configuration:'إعداد التقرير',designerTitle:'تصميم وطباعة المواقف',designerDesc:'اختر الحقول وترتيب العرض ثم راجع نسخة A4 قبل الطباعة أو الحفظ PDF.',reportSource:'الموقف المحدد',documentSettings:'إعدادات الصفحة',titleLabel:'عنوان التقرير',subtitleLabel:'عنوان فرعي (اختياري)',paperOrientation:'اتجاه ورقة A4',landscape:'أفقي',portrait:'عمودي',lotPresentation:'طريقة عرض الوجبات',eachLot:'كل وجبة بسطر مستقل',eachLotHint:'الصلاحية والكمية والسعر لكل وجبة',oneItem:'سطر واحد لكل مادة',oneItemHint:'الكمية الإجمالية المشمولة في الموقف',columns:'أعمدة التقرير',columnHint:'اختر فقط الحقول التي تريد ظهورها في النسخة المطبوعة.',selectAll:'تحديد الكل',defaults:'الافتراضي',compact:'مختصر',finalTouches:'تفاصيل الطباعة',showLogo:'إظهار شعار المذخر IMS',showFilters:'إظهار الفلاتر المستخدمة',signature:'إظهار خانة التوقيع',liveData:'تستخدم الطباعة بيانات النظام الحالية للقراءة فقط، ولا تُغيّر أي مخزون أو سجل.',print:'طباعة / حفظ PDF',reset:'استعادة الإعدادات',livePreview:'معاينة مباشرة',previewTitle:'نسخة التقرير الجاهزة للطباعة',preparing:'جارٍ تجهيز البيانات...',refresh:'تحديث المعاينة ↻',loading:'جارٍ تحميل بيانات الموقف...',loadingHint:'قد يستغرق التقرير الكبير بضع لحظات',page:'صفحة',of:'من',items:'مواد',rows:'سطور',dataDate:'بيانات حتى',printed:'تاريخ الإعداد',by:'أعدّه',filter:'الفلاتر',allBranches:'جميع الفروع',allBooks:'جميع السجلات',customDate:'الصلاحية قبل',threshold:'حد النسبة',search:'بحث',paper:'A4',signatureTitle:'توقيع مسؤول المذخر',missing:'لا توجد مواد مطابقة لهذه الفلاتر.',manyColumns:'عدد الأعمدة كبير؛ يُفضّل اختيار A4 أفقي أو إخفاء الأعمدة غير الضرورية حتى تبقى الطباعة مقروءة.',ready:'التقرير جاهز',error:'تعذر تحميل التقرير. تحقق من تسجيل الدخول والاتصال.',printTitle:'تقرير مخزني حسب البيانات الحالية',noValue:'—',groupInfo:'معلومات المادة',groupStock:'المخزون والصلاحيات',groupPrices:'الأسعار والاحتياجات',yes:'نعم',multiple:'متعددة',reportScope:'المواد المطابقة للتقرير'},
 en:{subhead:'Inventory Management System · Report studio',back:'Back to statements',configuration:'REPORT SETUP',designerTitle:'Print Report Designer',designerDesc:'Choose the fields and paper layout, then review the A4 preview before printing or saving a PDF.',reportSource:'Selected statement',documentSettings:'Page setup',titleLabel:'Report title',subtitleLabel:'Subtitle (optional)',paperOrientation:'A4 orientation',landscape:'Landscape',portrait:'Portrait',lotPresentation:'Lot display',eachLot:'One row per lot',eachLotHint:'Expiry, quantity and price per lot',oneItem:'One row per item',oneItemHint:'Total matching stock quantity',columns:'Printed columns',columnHint:'Select only the information you want on the printed report.',selectAll:'Select all',defaults:'Defaults',compact:'Compact',finalTouches:'Print details',showLogo:'Include the IMS logo',showFilters:'Include applied filters',signature:'Include signature area',liveData:'This read-only report uses current inventory data and never modifies stock or audit records.',print:'Print / Save PDF',reset:'Reset settings',livePreview:'LIVE PREVIEW',previewTitle:'A4 report preview',preparing:'Preparing data…',refresh:'Refresh preview ↻',loading:'Loading statement data…',loadingHint:'Large statements may take a moment',page:'Page',of:'of',items:'items',rows:'rows',dataDate:'Data as of',printed:'Created',by:'Prepared by',filter:'Filters',allBranches:'All branches',allBooks:'All registers',customDate:'Expiry before',threshold:'Threshold',search:'Search',paper:'A4',signatureTitle:'Warehouse officer signature',missing:'No matching inventory records for these filters.',manyColumns:'Many columns selected. Landscape A4 or fewer columns is recommended for readability.',ready:'Report ready',error:'Unable to load the report. Check your login and connection.',printTitle:'Warehouse stock report using current data',noValue:'—',groupInfo:'Item information',groupStock:'Stock and expiry',groupPrices:'Prices and requirements',yes:'Yes',multiple:'Multiple',reportScope:'Matching report items'}
};
const columns=[
 {id:'seq',ar:'ت',en:'#',group:'groupInfo'},
 {id:'name',ar:'اسم المادة',en:'Item name',group:'groupInfo'},
 {id:'scientific',ar:'الاسم العلمي',en:'Scientific name',group:'groupInfo'},
 {id:'branch',ar:'فرع المخزن',en:'Warehouse branch',group:'groupInfo'},
 {id:'book',ar:'السجل المعتمد',en:'Register / book',group:'groupInfo'},
 {id:'unit',ar:'الوحدة',en:'Unit',group:'groupInfo'},
 {id:'sku',ar:'رمز المادة',en:'Item code',group:'groupInfo'},
 {id:'manufacturer',ar:'الشركة المصنعة',en:'Manufacturer',group:'groupInfo'},
 {id:'aliases',ar:'معلومات / أسماء بديلة',en:'Alternate names / notes',group:'groupInfo'},
 {id:'qty',ar:'الكمية المشمولة',en:'Matching quantity',group:'groupStock'},
 {id:'physical',ar:'الرصيد الفعلي',en:'Physical balance',group:'groupStock'},
 {id:'usable',ar:'الرصيد الصالح',en:'Usable balance',group:'groupStock'},
 {id:'batch',ar:'رقم الوجبة',en:'Batch number',group:'groupStock'},
 {id:'mfg',ar:'تاريخ الإنتاج',en:'Manufacture date',group:'groupStock'},
 {id:'expiry',ar:'تاريخ الصلاحية',en:'Expiry date',group:'groupStock'},
 {id:'dinar',ar:'السعر — دينار',en:'Price — dinar',group:'groupPrices'},
 {id:'fils',ar:'السعر — فلس',en:'Price — fils',group:'groupPrices'},
 {id:'annual',ar:'الاحتياج السنوي',en:'Annual requirement',group:'groupPrices'},
 {id:'monthly',ar:'الاحتياج الشهري',en:'Monthly requirement',group:'groupPrices'},
 {id:'percent',ar:'نسبة الرصيد من الشهري',en:'% of monthly need',group:'groupPrices'}
];
const minimal=['seq','name','unit','qty','expiry'];
const defaultColumns=mode==='near_expiry'?['seq','name','branch','unit','batch','expiry','qty']:
 mode==='missing'?['seq','name','branch','book','unit','qty','annual']:
 ['seq','name','branch','book','unit','qty','monthly','percent'];
const state={data:null,items:[],batches:[],me:null,selected:new Set(defaultColumns),orientation:'landscape',lotMode:mode==='near_expiry'?'lots':'summary',showBrand:true,showFilters:true,showSignature:true,title:MODE[mode][lang],subtitle:WORDS[lang].printTitle,rows:[],pages:[],matched:[],loaded:false};
const fmt=n=>Number(n||0).toLocaleString('en-US',{maximumFractionDigits:3});
const money=v=>v==null?['—','—']:[fmt(Math.floor(Number(v)/1000)),String(Math.abs(Number(v)%1000)).padStart(3,'0')];
const normalized=s=>String(s??'').toLowerCase().normalize('NFKC').replace(/[أإآ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه').replace(/[ًٌٍَُِّْـ]/g,'').replace(/\s+/g,' ').trim();
const dateTime=()=>new Intl.DateTimeFormat(lang==='ar'?'ar-IQ':'en-GB',{timeZone:'Asia/Baghdad',dateStyle:'medium',timeStyle:'short',numberingSystem:'latn'}).format(new Date());
const priceForRow=(item,lot)=>lot?.unit_price_fils??(lot?null:item?.price_fils);
function text(k){return WORDS[lang][k]||k}
function tMode(){return MODE[mode][lang]}
function safeDate(s){return s?escape(s):'—'}
function getQuery(){return {branch:params.get('branch')||'',book:params.get('book')||'',search:params.get('search')||'',sort:params.get('sort')||'name'}}
function unit(u){const map={ar:{tablet:'حب',capsule:'كبسول',bottle:'بطل',ampoule:'امبول',vial:'فيال',tube:'انبوب',suppository:'تحاميل',drops:'قطرات',piece:'قطعة',bag:'كيس',pack:'باكة',roll:'رولة',packet:'باكيت',dozen:'درزن'},en:{}};return map[lang][u]||u||'—'}
function getField(row,key){const {item,lot,seq,stat,qty,percent}=row;
 switch(key){
 case 'seq':return String(seq);case 'name':return item.trade_name||item.name||'—';
 case 'scientific':return item.branch==='medication'?item.name||'—':'—';
 case 'branch':return BRANCH[item.branch]?.[lang]||'—';case 'book':return item.category||'—';
 case 'unit':return unit(item.unit);case 'sku':return item.sku||'—';
 case 'manufacturer':return item.manufacturer||'—';case 'aliases':return item.information||'—';
 case 'qty':return fmt(qty);case 'physical':return fmt(stat.physical);case 'usable':return fmt(stat.usable);
 case 'batch':return lot?.batch_no||((stat.lots.length>1&&state.lotMode==='summary')?text('multiple'):'—');
 case 'mfg':return safeDate(lot?.manufacture_date||(!lot?item.manufacture_date:null));
 case 'expiry':return safeDate(lot?.expiry_date||(!lot?stat.nearest:null));
 case 'dinar':return money(priceForRow(item,lot))[0];case 'fils':return money(priceForRow(item,lot))[1];
 case 'annual':return item.annual_need==null?'—':fmt(item.annual_need);
 case 'monthly':return item.annual_need==null?'—':fmt(Number(item.annual_need)/12);
 case 'percent':return percent==null?'—':fmt(percent)+'%';default:return '—';
 }
}
function stats(item){const lots=state.batches.filter(l=>Number(l.item_id)===Number(item.id));const now=state.data?.as_of||new Date().toISOString().slice(0,10);let physical=0,usable=0,nearest=null;for(const l of lots){const q=Number(l.on_hand)||0;physical+=q;if(l.expiry_date&&l.expiry_date>=now){usable+=q;if(q>0&&(!nearest||l.expiry_date<nearest))nearest=l.expiry_date}}return {lots,physical,usable,nearest}}
function matchedLots(item,recordRows){const lots=state.batches.filter(l=>Number(l.item_id)===Number(item.id));const today=state.data?.as_of||'';
 if(mode==='near_expiry'){const ids=new Set(recordRows.map(r=>Number(r.lot_id)));return lots.filter(l=>ids.has(Number(l.id))&&Number(l.on_hand)>0).sort((a,b)=>(a.expiry_date||'9999').localeCompare(b.expiry_date||'9999')||Number(a.id)-Number(b.id))}
 if(mode==='missing')return [];
 return lots.filter(l=>Number(l.on_hand)>0&&l.expiry_date&&l.expiry_date>=today).sort((a,b)=>(a.expiry_date||'9999').localeCompare(b.expiry_date||'9999')||Number(a.id)-Number(b.id));
}
function buildRows(){
 if(!state.loaded)return [];
 const byId=new Map(state.items.map(it=>[Number(it.id),it])),records=state.data[mode]||[];
 const ids=[...new Set(records.map(r=>Number(r.item_id)))],recordsByItem=new Map();for(const r of records){const key=Number(r.item_id);if(!recordsByItem.has(key))recordsByItem.set(key,[]);recordsByItem.get(key).push(r)}
 const q=getQuery(),needle=normalized(q.search),terms=needle.split(' ').filter(Boolean);
 let items=ids.map(id=>byId.get(id)).filter(Boolean).filter(item=>{
  if(q.branch&&item.branch!==q.branch)return false;
  if(q.book&&item.category!==q.book)return false;
  if(!terms.length)return true;
  const lots=state.batches.filter(l=>Number(l.item_id)===Number(item.id));
  const haystack=normalized([item.name,item.trade_name,item.generic_name,item.information,item.sku,item.category,item.manufacturer,...lots.flatMap(l=>[l.batch_no,l.expiry_date])].join(' '));
  return terms.every(t=>haystack.includes(t));
 });
 items.sort((a,b)=>{const x=stats(a),y=stats(b);if(q.sort==='stock_desc')return y.physical-x.physical;if(q.sort==='stock_asc')return x.physical-y.physical;if(q.sort==='expiry')return (x.nearest||'9999').localeCompare(y.nearest||'9999');return String(a.trade_name||a.name).localeCompare(String(b.trade_name||b.name),lang==='ar'?'ar':'en')});
 state.matched=items;const output=[];let seq=0;
 for(const item of items){const records=recordsByItem.get(Number(item.id))||[],stat=stats(item),lots=matchedLots(item,records),percent=records.find(r=>r.percent_of_monthly_need!=null)?.percent_of_monthly_need??null;
  const allQty=mode==='near_expiry'?records.reduce((v,r)=>v+Number(r.stock||0),0):mode==='missing'?0:Number(records[0]?.stock??stat.usable);
  if(state.lotMode==='lots'&&lots.length){for(const lot of lots){seq++;output.push({item,lot,seq,stat,qty:Number(lot.on_hand)||0,percent});}}
  else{seq++;output.push({item,lot:null,seq,stat,qty:allQty,percent});}
 }
 state.rows=output;return output;
}
function setLanguage(next){if(!['en','ar'].includes(next))return;const prior=state.title===MODE[mode][lang],oldSub=state.subtitle===WORDS[lang].printTitle;lang=next;document.documentElement.lang=next;document.documentElement.dir=next==='ar'?'rtl':'ltr';$$('[data-locale]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.locale===lang)));$$('[data-ui]').forEach(el=>el.textContent=text(el.dataset.ui));if(prior)state.title=tMode();if(oldSub)state.subtitle=text('printTitle');$('#customTitle').value=state.title;$('#customSubtitle').value=state.subtitle;$('#reportSource').textContent=tMode();renderColumnChoices();renderPreview();}
function renderColumnChoices(){const holder=$('#columnChoices');if(!holder)return;let html='';for(const group of ['groupInfo','groupStock','groupPrices']){const list=columns.filter(c=>c.group===group);html+=`<div class="column-group"><h3>${escape(text(group))}</h3><div class="column-choices-grid">${list.map(c=>`<label class="column-choice"><input type="checkbox" data-print-column="${c.id}" ${state.selected.has(c.id)?'checked':''} ${c.id==='seq'?'disabled':''}><span>${escape(c[lang])}</span></label>`).join('')}</div></div>`}holder.innerHTML=html;updateCount()}
function updateCount(){$('#selectedCount').textContent=state.selected.size+'/'+columns.length}
async function loadJSON(url){const res=await fetch(url,{credentials:'same-origin',cache:'no-store'});if(res.status===401){location.href='/login.html';throw Error('Unauthorized')}if(!res.ok)throw Error('HTTP '+res.status);return res.json()}
async function loadData(){const q=new URLSearchParams();for(const key of ['expiry_before','scarce_pct','surplus_pct']){const val=params.get(key);if(val)q.set(key,val)}const urls=['/api/positions'+(q.toString()?'?'+q.toString():''),'/api/items','/api/batches','/api/me'];const data=await Promise.all(urls.map(loadJSON));[state.data,state.items,state.batches,state.me]=data;state.loaded=true;renderPreview()}
function metadata(){const parts=[],q=getQuery();if(q.branch)parts.push((lang==='ar'?'الفرع: ':'Branch: ')+(BRANCH[q.branch]?.[lang]||q.branch));else parts.push(text('allBranches'));if(q.book)parts.push((lang==='ar'?'السجل: ':'Book: ')+q.book);if(q.search)parts.push(text('search')+': '+q.search);if(mode==='near_expiry')parts.push(text('customDate')+': '+(state.data?.expiry_before||'—'));if(mode==='scarce'||mode==='surplus')parts.push(text('threshold')+': '+(mode==='scarce'?(state.data?.scarce_pct||params.get('scarce_pct')):(state.data?.surplus_pct||params.get('surplus_pct')))+'%');return parts.join(' · ')}
function sheetHeader(page,pageCount){const brand=state.showBrand?`<img src="/static/ims-icon.png" alt="" />`:'';const actualName=state.me?.full_name||state.me?.username||'—';return `<div class="sheet-head"><div class="sheet-head-brand">${brand}<div><strong>${lang==='ar'?'المذخر':'IMS Warehouse'}</strong><span>Inventory Management System</span></div></div><div class="sheet-head-title"><h3>${escape(state.title||tMode())}</h3>${state.subtitle?`<p>${escape(state.subtitle)}</p>`:''}</div><div class="sheet-head-code">IMS · ${escape(mode.toUpperCase())}</div></div><div class="sheet-meta"><span>${escape(text('dataDate'))}: <strong>${escape(state.data?.as_of||'—')}</strong></span><span class="meta-end">${escape(text('printed'))}: <strong>${escape(dateTime())}</strong></span>${state.showFilters?`<span class="sheet-filterline">${escape(text('filter'))}: ${escape(metadata())}</span>`:''}</div>`}
function sheetFooter(page,pageCount){return `<div class="sheet-footer"><div class="signature">${state.showSignature?`<label>${escape(text('signatureTitle'))}</label><div class="signature-line"></div>`:''}</div><div class="page-id">${escape(text('page'))} ${page} ${escape(text('of'))} ${pageCount}</div><div class="generated">${escape(text('by'))}: ${escape(state.me?.full_name||state.me?.username||'—')}</div></div>`}
function rowMarkup(row,ids){return `<tr>${ids.map(id=>`<td class="${id==='name'?'itemname':id==='dinar'||id==='fils'?'price':''}">${escape(getField(row,id))}</td>`).join('')}</tr>`}
function tableMarkup(rows,ids){const headers=`<thead><tr>${ids.map(id=>`<th>${escape(columns.find(c=>c.id===id)?.[lang]||id)}</th>`).join('')}</tr></thead>`;return `<table class="sheet-table">${headers}<tbody>${rows.length?rows.map(row=>rowMarkup(row,ids)).join(''):`<tr><td colspan="${ids.length}" class="sheet-empty">${escape(text('missing'))}</td></tr>`}</tbody></table>`}
function sheetMarkup(rows,index,total,ids){return `<article class="report-sheet ${ids.length>10?'dense':''}">${sheetHeader(index,total)}<div class="sheet-content">${tableMarkup(rows,ids)}</div>${sheetFooter(index,total)}</article>`}
function paperSlot(rows,index,total,ids){return `<div class="paper-slot">${sheetMarkup(rows,index,total,ids)}</div>`}
function getHeights(rows,ids){const temp=document.createElement('div');temp.className='paper-slot measure-slot';temp.style.cssText='position:absolute;top:-100000px;visibility:hidden;pointer-events:none;';temp.innerHTML=sheetMarkup(rows,1,1,ids);$('#paperPages').append(temp);const sheet=$('.report-sheet',temp),content=$('.sheet-content',temp),head=$('.sheet-table thead',temp);const maxH=content.clientHeight-head.offsetHeight-6;const tr=$$('.sheet-table tbody tr',temp).map(el=>el.offsetHeight);temp.remove();return {maxH,heights:tr}}
function chunkRows(rows,ids){if(!rows.length)return [[]];const {maxH,heights}=getHeights(rows,ids);const pages=[];let bucket=[],used=0;for(let i=0;i<rows.length;i++){const h=Math.max(22,heights[i]||26);if(bucket.length&&used+h>maxH){pages.push(bucket);bucket=[];used=0}bucket.push(rows[i]);used+=h;}if(bucket.length)pages.push(bucket);return pages}
function scalePages(){const wrap=$('#paperPages');if(!wrap||!wrap.children.length)return;const space=$('.preview-area').clientWidth-42;const paper=$('.report-sheet',wrap);if(!paper)return;const scale=Math.max(.2,Math.min(.96,space/paper.offsetWidth));$$('.paper-slot',wrap).forEach(slot=>{slot.style.setProperty('--scale',String(scale));slot.style.setProperty('--sheet-screen-w',paper.offsetWidth+'px');slot.style.setProperty('--sheet-screen-h',paper.offsetHeight+'px');slot.style.width=Math.ceil(paper.offsetWidth*scale)+'px';slot.style.height=Math.ceil(paper.offsetHeight*scale)+'px'})}
function renderPreview(){if(!state.loaded)return;const paper=$('#paperPages'),loading=$('#loadingCard');loading.hidden=true;document.documentElement.style.setProperty('--paper-w',state.orientation==='landscape'?'297mm':'210mm');document.documentElement.style.setProperty('--paper-h',state.orientation==='landscape'?'210mm':'297mm');$('#dynamicPageStyle').textContent=`@page{size:A4 ${state.orientation};margin:0}`;
 const ids=columns.filter(c=>state.selected.has(c.id)).map(c=>c.id);if(!ids.includes('seq'))ids.unshift('seq');
 const rows=buildRows();paper.innerHTML='';const chunks=chunkRows(rows,ids);state.pages=chunks;paper.innerHTML=chunks.map((chunk,i)=>paperSlot(chunk,i+1,chunks.length,ids)).join('');
 requestAnimationFrame(scalePages);const count=state.matched.length;$('#sourceCounter').textContent=`${fmt(count)} ${text('items')} · ${fmt(rows.length)} ${text('rows')}`;$('#pageCounter').textContent=`${chunks.length} ${text('page')}`;$('#previewStatus').textContent=`${text('ready')} · ${fmt(rows.length)} ${text('rows')}`;
 const warning=$('#printWarning');warning.hidden=ids.length<=10;warning.textContent=text('manyColumns');document.title=`${state.title} — IMS`;updateCount();}
function resetSettings(){state.selected=new Set(defaultColumns);state.orientation='landscape';state.lotMode=mode==='near_expiry'?'lots':'summary';state.showBrand=state.showFilters=state.showSignature=true;state.title=tMode();state.subtitle=text('printTitle');$('#customTitle').value=state.title;$('#customSubtitle').value=state.subtitle;$$('input[name="orientation"]').forEach(e=>e.checked=e.value===state.orientation);$$('input[name="lotMode"]').forEach(e=>e.checked=e.value===state.lotMode);for(const [id,value] of [['showBrand',true],['showFilters',true],['showSignature',true]])$('#'+id).checked=value;renderColumnChoices();renderPreview()}
function initEvents(){
 $$('[data-locale]').forEach(b=>b.addEventListener('click',()=>setLanguage(b.dataset.locale)));
 $('#columnChoices').addEventListener('change',e=>{const c=e.target.closest('[data-print-column]');if(!c)return;if(c.checked)state.selected.add(c.dataset.printColumn);else state.selected.delete(c.dataset.printColumn);if(!state.selected.has('seq'))state.selected.add('seq');renderPreview()});
 $('#allColumns').addEventListener('click',()=>{state.selected=new Set(columns.map(c=>c.id));renderColumnChoices();renderPreview()});
 $('#defaultColumns').addEventListener('click',()=>{state.selected=new Set(defaultColumns);renderColumnChoices();renderPreview()});
 $('#minimalColumns').addEventListener('click',()=>{state.selected=new Set(minimal);renderColumnChoices();renderPreview()});
 $$('input[name="orientation"]').forEach(e=>e.addEventListener('change',()=>{state.orientation=e.value;renderPreview()}));
 $$('input[name="lotMode"]').forEach(e=>e.addEventListener('change',()=>{state.lotMode=e.value;renderPreview()}));
 ['showBrand','showFilters','showSignature'].forEach(id=>$('#'+id).addEventListener('change',e=>{state[id]=e.target.checked;renderPreview()}));
 $('#customTitle').addEventListener('input',e=>{state.title=e.target.value;renderPreview()});
 $('#customSubtitle').addEventListener('input',e=>{state.subtitle=e.target.value;renderPreview()});
 $('#resetButton').addEventListener('click',resetSettings);
 $('#refreshButton').addEventListener('click',()=>{state.loaded=false;$('#loadingCard').hidden=false;$('#paperPages').innerHTML='';loadData().catch(displayError)});
 $('#printButton').addEventListener('click',()=>{if(!state.loaded)return;document.title=state.title||tMode();window.print()});
 window.addEventListener('resize',()=>requestAnimationFrame(scalePages));
}
function displayError(e){console.error('Print report error',e);$('#loadingCard').hidden=false;$('#loadingCard').innerHTML=`<strong>${escape(text('error'))}</strong><span>${escape(e.message||'')}</span>`;$('#previewStatus').textContent=text('error')}
async function main(){document.documentElement.lang=lang;document.documentElement.dir=lang==='ar'?'rtl':'ltr';initEvents();setLanguage(lang);$$('input[name="lotMode"]').forEach(el=>el.checked=el.value===state.lotMode);try{await loadData()}catch(e){displayError(e)}}
window.addEventListener('DOMContentLoaded',main);
})();
