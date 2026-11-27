/* Live V4.21 bilingual warehouse application: all stock, including opening balances, is audited. */
const $ = (s, root=document)=>root.querySelector(s);
const $$ = (s, root=document)=>[...root.querySelectorAll(s)];
const I = name=>`<svg class="i" aria-hidden="true"><use href="#ico-${name}"/></svg>`;
const E = value=>String(value??'').replace(/[&<>"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
const N = v=>Number(v||0).toLocaleString('en-US');
const priceLabel=v=>{if(v==null)return '—';const d=N(Math.floor(Number(v)/1000)),f=String(Number(v)%1000).padStart(3,'0');return window.HWLang?.get()==='en'?`${d} IQD · ${f} fils`:`${d} دينار · ${f} فلس`;};
const todayBaghdad=()=>{const p=Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:'Asia/Baghdad',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date()).map(x=>[x.type,x.value]));return `${p.year}-${p.month}-${p.day}`};
const fmtDate = str=>new Date(str).toLocaleString(window.HWLang?.get()==='ar'?'ar-IQ':'en-GB',{timeZone:'Asia/Baghdad',dateStyle:'medium',timeStyle:'short'});
const D = str=>str?`<time class="localized-time" datetime="${E(str)}">${E(fmtDate(str))}</time>`:'—';
const badge = (label,kind='neutral')=>`<span class="pill ${kind}">${E(label)}</span>`;
const msg = (title,sub='')=>`<div class="empty-state">${I('package')}<strong>${E(title)}</strong><span class="muted-hint">${E(sub)}</span></div>`;
let user=null, csrf='', view='', cache={items:[],departments:[],batches:[],movements:[],users:[],dashboard:null,positions:null,books:{},units:{},staff:[]}, toastTimer;
let inlineNewItem=null; // Pending shipment line; kept intact while the item modal is open.
const DEFAULT_SCARCE_PERCENT='20', DEFAULT_SURPLUS_PERCENT='120';
let statementExpiryBefore='', statementScarcePct=DEFAULT_SCARCE_PERCENT, statementSurplusPct=DEFAULT_SURPLUS_PERCENT;
// V4.13: filters and selected table columns are presentation-only. Data is unchanged.
const expandedItems=new Set();
const expandedFullInfo=new Set(); // second-level details are collapsed by default
let inventoryState='available', inventorySort='name', inventoryInactive=false;
let statementBook='', statementSort='name';
const COLS=[
 ['name','Item / Product'],['branch','Warehouse branch'],['book','Registered book'],
 ['unit','Unit'],['physical','Physical balance'],['usable','Usable balance'],
 ['expired','Expired balance'],['unknown','Unknown expiry'],['lots','Stored lots'],
 ['next','Nearest usable expiry'],['price','Registered price'],['annual','Annual requirement'],['monthly','Monthly requirement'],
 ['manufacturer','Manufacturer'],['mfg','Manufacture date'],['generic','Generic name'],
 ['aliases','Alternative names'],['reference','Reference batch / expiry'],
 ['status','Item status'],['percent','% monthly need'],['matched','Matching expiry lots'],['actions','Edit']
];
const DEFAULT_INV_COLS=['name','branch','book','physical','usable','lots','next','price','annual','actions'];
const DEFAULT_STMT_COLS=['name','branch','book','physical','usable','lots','next','price','annual','monthly','matched','percent'];
const storedColumnState=(section,defaults)=>{
 try{const raw=JSON.parse(localStorage.getItem('hw_columns_'+section));if(Array.isArray(raw)&&raw.length)return raw.filter(k=>COLS.some(c=>c[0]===k));}catch(_e){}
 return [...defaults];
};
const columnShown={inventory:storedColumnState('inventory',DEFAULT_INV_COLS),statements:storedColumnState('statements',DEFAULT_STMT_COLS)};
// V4.14: the old narrow dropdown is replaced by an accessible centered dialog.
// Changes apply to the display only after Save; the database is never changed.
const columnGroups=[
 ['Basic item information',['name','branch','book','unit','generic','manufacturer','mfg','aliases','reference','status']],
 ['Stock and expiry',['physical','usable','expired','unknown','lots','next']],
 ['Pricing and requirements',['price','annual','percent','matched']],
 ['Actions',['actions']]
];
const allowedColumns=section=>COLS.filter(([key])=>section==='statements'?key!=='actions':key!=='matched'&&key!=='percent').map(([key])=>key);
let columnDialogSection='',columnDialogFocus=null;
const columnPicker=section=>`<button type="button" class="db-btn secondary column-picker-launch" data-open-column-manager="${section}" aria-haspopup="dialog">Show / hide columns ⚙</button>`;
function openColumnManager(section){
 if(!['inventory','statements'].includes(section))return;
 const root=$('#columnManager');if(!root)return;
 columnDialogSection=section;columnDialogFocus=document.activeElement;
 const allowed=allowedColumns(section),saved=columnShown[section];
 const groups=columnGroups.map(([name,keys])=>{
  const fields=keys.filter(k=>allowed.includes(k));
  if(!fields.length)return '';
  return `<section class="column-group"><h3>${E(name)}</h3><div class="column-options">${fields.map(k=>`<label class="column-option" data-column-label="${E(headerFor(k).toLowerCase())}"><input type="checkbox" data-column-choice="${k}" ${k==='name'?'disabled':''} ${k==='name'||saved.includes(k)?'checked':''}><span>${E(headerFor(k))}</span>${k==='name'?'<small>Always shown</small>':''}</label>`).join('')}</div></section>`;
 }).join('');
 root.innerHTML=`<div class="column-dialog" role="dialog" aria-modal="true" aria-labelledby="columnManagerTitle" aria-describedby="columnManagerHelp" tabindex="-1"><div class="column-dialog-header"><div><h2 id="columnManagerTitle">Show / hide columns</h2><p id="columnManagerHelp">Choose which details appear in the table. Item names stay visible.</p></div><button type="button" class="column-dialog-x" data-close-column-manager aria-label="Close">×</button></div><div class="column-dialog-top"><input type="search" class="db-input" id="columnManagerSearch" placeholder="Search columns..." aria-label="Search columns"><span class="muted-hint">${allowed.length} available</span></div><div class="column-dialog-scroll">${groups}</div><div class="column-dialog-footer"><div class="column-dialog-bulk"><button class="db-btn secondary small" type="button" data-column-all>Select all</button><button class="db-btn secondary small" type="button" data-column-none>Hide optional</button><button class="db-btn secondary small" type="button" data-column-default>Restore defaults</button></div><div class="column-dialog-actions"><button class="db-btn secondary" type="button" data-close-column-manager>Cancel</button><button class="db-btn" type="button" data-save-column-manager>Apply columns</button></div></div></div>`;
 root.classList.add('open');root.setAttribute('aria-hidden','false');document.body.classList.add('column-dialog-open');
 window.HWLang?.apply();$('#columnManagerSearch')?.focus();
}
function closeColumnManager(){
 const root=$('#columnManager');if(!root||!root.classList.contains('open'))return;
 root.classList.remove('open');root.setAttribute('aria-hidden','true');root.innerHTML='';document.body.classList.remove('column-dialog-open');
 columnDialogFocus?.focus?.();columnDialogFocus=null;columnDialogSection='';
}
function columnChoices(){return $$('[data-column-choice]',$('#columnManager'));}
function columnChangeAll(mode){
 const section=columnDialogSection;if(!section)return;
 const defaults=section==='inventory'?DEFAULT_INV_COLS:DEFAULT_STMT_COLS;
 columnChoices().forEach(el=>{if(!el.disabled)el.checked=mode==='all'||mode==='default'&&defaults.includes(el.dataset.columnChoice)});
}
function saveColumnManager(){
 const section=columnDialogSection;if(!section)return;
 const selected=columnChoices().filter(el=>el.checked).map(el=>el.dataset.columnChoice);
 columnShown[section]=allowedColumns(section).filter(k=>selected.includes(k)||k==='name');
 try{localStorage.setItem('hw_columns_'+section,JSON.stringify(columnShown[section]));}catch(_e){}
 closeColumnManager();
 if(section==='inventory')filterInventory();else filterStatement();
}
function searchColumnOptions(q){
 const needle=normalizeItemSearch(q); const panel=$('#columnManager');if(!panel)return;
 $$('.column-group',panel).forEach(group=>{
  let count=0;
  $$('.column-option',group).forEach(label=>{
   const name=normalizeItemSearch(label.innerText+' '+(label.dataset.columnLabel||''));
   label.hidden=!!needle&&!name.includes(needle);if(!label.hidden)count++;
  });
  group.hidden=count===0;
 });
}
const lotForItem=it=>cache.batches.filter(b=>Number(b.item_id)===Number(it.id));
const lotStats=(it)=>{
 const lots=lotForItem(it),today=todayBaghdad();
 let physical=0,usable=0,expired=0,unknown=0;
 let next='';
 for(const b of lots){const q=Number(b.on_hand)||0;if(q<0)continue;physical+=q;
  if(!b.expiry_date)unknown+=q;
  else if(b.expiry_date<today)expired+=q;
  else{usable+=q;if(q>0&&(!next||b.expiry_date<next))next=b.expiry_date;}
 }
 return {lots,physical,usable,expired,unknown,next};
};
const lotStatus=b=>b.expiry_date&&b.expiry_date<todayBaghdad()?'Expired':!b.expiry_date?'Expiry unknown':b.on_hand>0?'Available':'Empty';
const rowSearchText=(it)=>normalizeItemSearch([itemSearchText(it),...lotForItem(it).flatMap(b=>[b.batch_no,b.expiry_date,String(b.unit_price_fils??'')])].join(' '));
const itemById=id=>cache.items.find(i=>Number(i.id)===Number(id));
const headerFor=k=>COLS.find(c=>c[0]===k)?.[1]||k;
function itemColumn(it,stat,key,context){
 const pct=context?.percent_of_need;
 switch(key){
  case 'name':return `${stat.lots.length>1?`<strong>${E(it.trade_name||it.name)}</strong>`:`<button type="button" class="item-name-open" data-expand-item="${it.id}" aria-expanded="${expandedItems.has(it.id)}" aria-label="View item details">${E(it.trade_name||it.name)}</button>`}${it.trade_name?`<div class="tiny">${E(it.name)}</div>`:''}<div class="tiny">${E(it.sku)}</div>`;
  case 'branch':return badge(branchName(it.branch),it.branch?'blue':'warning');
  case 'book':return E(it.category||'—');
  case 'unit':return E(it.unit||'—');
  case 'physical':return `<strong>${N(stat.physical)}</strong> ${E(it.unit)}`;
  case 'usable':return `<strong>${N(stat.usable)}</strong> ${E(it.unit)}`;
  case 'expired':return stat.expired?badge(`${N(stat.expired)} ${it.unit}`,'danger'):`${N(0)}`;
  case 'unknown':return stat.unknown?badge(`${N(stat.unknown)} ${it.unit}`,'warning'):'0';
  case 'lots':return `<div class="lots-cell"><strong>${N(stat.lots.length)}</strong><span class="tiny">lots</span></div>`;
  case 'next':return E(stat.next||'—');
  case 'price':return priceLabel(it.price_fils);
  case 'annual':return it.annual_need==null?'—':`${N(it.annual_need)} ${E(it.unit)}`;
  case 'monthly':return it.annual_need==null?'—':`${(Number(it.annual_need)/12).toLocaleString('en-US',{maximumFractionDigits:2})} ${E(it.unit)}`;
  case 'manufacturer':return E(it.manufacturer||'—');
  case 'mfg':return E(it.manufacture_date||'—');
  case 'generic':return E(it.generic_name||'—');
  case 'aliases':return E(it.information||'—');
  case 'reference':return `${E(it.initial_batch_no||'—')}<div class="tiny">${E(it.expiry_date||'—')}</div>`;
  case 'status':return badge(it.active?'Active':'Inactive',it.active?'blue':'danger');
  case 'percent':return pct==null?'—':`${N(pct)}%`;
  case 'matched':return context?.matches==null?'—':`${N(context.matches)} lots`;
  case 'actions':return canEditBranch(it.branch)?`<button type="button" class="mini-edit" data-edit-item="${it.id}">Edit</button>`:'—';
  default:return '—';
 }
}
function fullItemPanel(it,stat){
 const fieldValues=[['Item name',it.name],['Trade name',it.trade_name],['Generic name',it.generic_name],
  ['SKU / internal ID',it.sku],['Branch',branchName(it.branch)],['Register book',it.category],
  ['Unit',it.unit],['Manufacturer',it.manufacturer],['Manufacture date',it.manufacture_date],
  ['Reference batch',it.initial_batch_no],['Reference expiry',it.expiry_date],
  ['Registered price',priceLabel(it.price_fils)],['Annual requirement',it.annual_need==null?'—':`${N(it.annual_need)} ${it.unit}`],
  ['Monthly requirement',it.annual_need==null?'—':`${(Number(it.annual_need)/12).toLocaleString('en-US',{maximumFractionDigits:2})} ${it.unit}`],
  ['Other names / information',it.information],['Record created',it.created_at],['Record status',it.active?'Active':'Inactive'],
  ['Total stock',`${N(stat.physical)} ${it.unit}`],['Usable / unexpired',`${N(stat.usable)} ${it.unit}`],
  ['Expired stock',`${N(stat.expired)} ${it.unit}`],['No expiry recorded',`${N(stat.unknown)} ${it.unit}`]];
 const lots=[...stat.lots].sort((a,b)=>(a.expiry_date||'9999-12-31').localeCompare(b.expiry_date||'9999-12-31')||a.id-b.id);
 const lotRows=lots.map((b,i)=>`<tr><td><span class="lot-row-index">${N(i+1)}</span></td><td><strong>${E(b.batch_no)}</strong><div class="tiny">Lot ID ${N(b.id)}</div></td><td>${E(b.manufacture_date||'—')}</td><td>${E(b.expiry_date||'—')}</td><td><strong>${N(b.on_hand)}</strong> ${E(it.unit)}</td><td>${priceLabel(b.unit_price_fils)}</td><td>${badge(lotStatus(b),lotStatus(b)==='Expired'?'danger':lotStatus(b)==='Expiry unknown'?'warning':'blue')}</td></tr>`);
 return `<div class="expanded-item-panel"><div class="expanded-header"><h3>All stored lots — ${E(it.trade_name||it.name)}</h3><span class="lot-summary-count">${N(lots.length)} stored lot(s)</span></div>
 <p class="lot-table-intro">Every lot is listed separately with its own expiry date, remaining quantity and stored unit price—even when batch numbers repeat.</p>
 ${lots.length?table(['#','Batch number','Manufacture date','Expiry date','Remaining quantity','Stored lot price','Status'],lotRows):msg('No lots registered','This product has not been received yet.')}
 <button type="button" class="expanded-secondary-toggle" data-toggle-item-extra="${it.id}" aria-controls="item-extra-${it.id}" aria-expanded="${expandedFullInfo.has(it.id)}">
   <span>Full item information &amp; movement history</span><span class="expanded-extra-chevron" aria-hidden="true">${expandedFullInfo.has(it.id)?'▴':'▾'}</span>
 </button>
 <div class="expanded-secondary" id="item-extra-${it.id}" data-item-extra="${it.id}" ${expandedFullInfo.has(it.id)?'':'hidden'}>
   <h3>Full item information</h3>
   <div class="full-item-fields">${fieldValues.map(([label,v])=>`<div class="full-field"><span>${E(label)}</span><strong>${E(v??'—')}</strong></div>`).join('')}</div>
   <div class="item-ledger-heading"><h3>Complete recorded movement history</h3><span class="muted-hint">Fetched from the database in pages, including older movements.</span></div>
   <div data-item-history="${it.id}"><button type="button" class="db-btn secondary small" data-load-item-history="${it.id}" data-history-offset="0">Load movement history</button></div>
 </div></div>`;
}
function detailsTable(items,section,contexts={}){
 const chosen=allowedColumns(section).filter(k=>k==='name'||columnShown[section].includes(k));
 const columns=['#',''].concat(chosen.map(headerFor));
 const rows=[];
 for(const [i,it] of items.entries()){
  const stat=lotStats(it),id=it.id,open=expandedItems.has(id),ctx=contexts[id]||{};
  const arrow=stat.lots.length>1?`<button type="button" class="expand-row-btn" data-expand-item="${id}" aria-expanded="${open}" aria-label="Expand stored lots" title="Expand stored lots">${open?'▴':'▾'}</button>`:'';
  rows.push(`<tr class="product-summary"><td><span class="item-row-number">${N(i+1)}</span></td><td class="item-expand-cell">${arrow}</td>${chosen.map(k=>`<td>${itemColumn(it,stat,k,ctx)}</td>`).join('')}</tr>`);
  rows.push(`<tr class="product-detail-row" data-detail-row="${id}" ${open?'':'hidden'}><td colspan="${columns.length}">${open?fullItemPanel(it,stat):''}</td></tr>`);
 }
 return rows.length?table(columns,rows):msg('No matching items','Try changing the stock status or filters.');
}
async function loadItemHistory(itemId,offset=0){
 const holder=document.querySelector(`[data-item-history="${itemId}"]`);if(!holder)return;
 const btn=holder.querySelector('[data-load-item-history]');if(btn){btn.disabled=true;btn.textContent='Loading…';}
 try{
  const result=await api(`/api/items/${itemId}/history?limit=50&offset=${offset}`);
  const rows=result.rows.map(m=>`<tr><td>${D(m.created_at)}</td><td><strong>${E(m.code)}</strong><div class="tiny">${E(m.route==='opening_balance'?'Opening balance':m.kind)} · ${E(routeNames[m.route]||m.route)}</div></td><td>${E(m.paper_ref||'—')}${m.dispatch_ref?`<div class="tiny">${E(m.dispatch_ref)}</div>`:''}</td><td>${E(m.batch_no)}</td><td>${E(m.expiry_date||'—')}</td><td>${m.direction>0?'+':'−'}${N(m.qty)}</td><td>${priceLabel(m.unit_price_fils)}</td><td>${E(m.operator)}</td></tr>`);
  if(offset===0){holder.innerHTML=`<p class="muted-hint">${N(result.total)} recorded line(s)</p><div class="db-table-wrap"><table class="db-table history-table"><thead><tr>${['Date','Movement','Document','Batch','Expiry','Quantity','Price','By'].map(x=>`<th>${E(x)}</th>`).join('')}</tr></thead><tbody data-history-body>${rows.join('')}</tbody></table></div>`;}
  else holder.querySelector('[data-history-body]')?.insertAdjacentHTML('beforeend',rows.join(''));
  if(result.total===0){holder.innerHTML=msg('No movements yet','Creating an item does not add warehouse stock.');return;}
  const next=offset+rows.length;
  if(next<result.total)holder.insertAdjacentHTML('beforeend',`<button type="button" class="db-btn secondary small history-more" data-load-item-history="${itemId}" data-history-offset="${next}">Load more (${N(result.total-next)} remaining)</button>`);
  window.HWLang?.apply();
 }catch(e){toast(e.message,'error');if(btn){btn.disabled=false;btn.textContent='Retry history';}}
}

const statementApiPath=()=>{
 const p=new URLSearchParams();
 if(statementExpiryBefore)p.set('expiry_before',statementExpiryBefore);
 if(statementScarcePct)p.set('scarce_pct',statementScarcePct);
 if(statementSurplusPct)p.set('surplus_pct',statementSurplusPct);
 const q=p.toString();return '/api/positions'+(q?'?'+q:'');
};
async function reloadPositions(){
 const search=$('#statementSearch')?.value||'',branch=$('#statementBranch')?.value||'',book=$('#statementBook')?.value||'';
 cache.positions=await api(statementApiPath());
 if(view==='positions'){
  $('#dashboardView').innerHTML=warehouseStatements();
  if($('#statementSearch'))$('#statementSearch').value=search;
  if($('#statementBranch'))$('#statementBranch').value=branch;
  if($('#statementBook'))$('#statementBook').value=book;
  filterStatement();window.HWLang?.apply();
 }
}

const headers={overview:'Warehouse Overview',inventory:'Inventory',item_movement:'Item movements',profile:'My account',receiving:'Receive Shipments',distribution:'Prepare outgoing shipment',returns:'Stock Adjustments',movements:'Movement History',batches:'Batches & Expiry',departments:'Departments',positions:'Warehouse Statements',reports:'Reports',users:'Users & Permissions',backup:'Backup & Restore',settings:'Audit logs'};
const can=p=>!!user?.permissions.includes(p);
const BRANCHES=[['medication','Medication'],['medical_supplies','Medical Supplies'],['surgical_instruments','Surgical Instruments']];
const branchName=b=>BRANCHES.find(x=>x[0]===b)?.[1]||'Unassigned — admin classification needed';
const canEditBranch=b=>can('item_write')&&(user?.role==='admin'||(!!user?.branch&&user.branch===b));
const inMyBranch=b=>user?.role==='admin'||(!!user?.branch&&user.branch===b);
const branchList=selected=>`<option value="">Select a branch</option>`+BRANCHES.map(([code,label])=>`<option value="${code}" ${code===selected?'selected':''}>${E(label)}</option>`).join('');
const branchField=(name,selected='',allowSwitch=true)=>allowSwitch
 ? `<select class="db-select branch-select" name="${name}" required>${branchList(selected)}</select>`
 : `<select class="db-select branch-select" disabled aria-label="Assigned branch">${branchList(selected)}</select><input type="hidden" name="${name}" value="${E(selected)}">`;
// Book names come from the server's official branch-to-register catalog.
const booksFor = branch => cache.books?.[branch]||[];
const unitsFor = branch => cache.units?.[branch]||[];
const unitOptions = (branch, selected='', allowLegacy=false) => {
 let options='<option value="">Select stock unit</option>';
 options+=unitsFor(branch).map(x=>`<option value="${E(x)}" ${x===selected?'selected':''}>${E(x)}</option>`).join('');
 if(allowLegacy && selected && !unitsFor(branch).includes(selected))options+=`<option selected value="${E(selected)}">${E(selected)} (Legacy unit — unchanged)</option>`;
 return options;
};
const approvedBook = (branch, category) => booksFor(branch).includes(category);
const legacyBooksFor = branch => [...new Set(cache.items.filter(i=>i.category && (!branch||i.branch===branch) && !approvedBook(i.branch,i.category)).map(i=>i.category))].sort((a,b)=>a.localeCompare(b));
const optionsForBooks = (branch,selected='') => {
 let html='<option value="">Select a book / register</option>';
 if(!branch || !booksFor(branch).length) return html;
 html += booksFor(branch).map(name=>`<option value="${E(name)}" ${name===selected?'selected':''}>${E(name)}</option>`).join('');
 return html;
};
const filterBookOptions = (branch='', selected='') => {
 const show=branch?[branch]:BRANCHES.map(b=>b[0]);
 let html='<option value="">All books / registers</option>';
 for(const b of show){
  const names=booksFor(b);
  if(!names.length)continue;
  const options=names.map(n=>`<option value="${E(n)}" ${n===selected?'selected':''}>${E(n)}</option>`).join('');
  html+=`<optgroup label="${E(branchName(b))}">${options}</optgroup>`;
 }
 const legacy=legacyBooksFor(branch).filter(n=>!show.some(b=>approvedBook(b,n)));
 if(legacy.length)html+=`<optgroup label="Legacy / needs review">${legacy.map(n=>`<option value="${E(n)}" ${n===selected?'selected':''}>${E(n)}</option>`).join('')}</optgroup>`;
 return html;
};

const typeLabel = {IN:'Warehouse intake',OUT:'Warehouse dispatch',RETURN:'Internal return',ADJUST_PLUS:'Stock increase',ADJUST_MINUS:'Stock decrease'};
const movementLabel=m=>m.route==='opening_balance'?'Opening balance':(typeLabel[m.kind]||m.kind);
const movementBadgeType={IN:'intake',OUT:'dispatch',RETURN:'return-type',ADJUST_PLUS:'adjustment',ADJUST_MINUS:'adjustment'};
async function api(path,{method='GET',data,headers={},body}={}){
  let h={...headers}; if(method!=='GET')h['X-CSRF-Token']=csrf;
  if(data!==undefined){h['Content-Type']='application/json';body=JSON.stringify(data)}
  const r=await fetch(path,{method,headers:h,body,credentials:'same-origin'});
  if(r.status===401){location.href='/login.html';throw Error('Sign in again')}
  if(!r.ok){const d=await r.json().catch(()=>({}));throw Error(typeof d.detail==='string'?d.detail:`Request failed (${r.status})`)}
  if(r.headers.get('content-type')?.includes('application/json'))return r.json();
  return r;
}
function toast(text,kind='ok'){
  const el=$('#toast');el.textContent=window.HWLang?.t(text)||text;el.classList.add('show');el.style.background=kind==='error'?'#bd5651':'#0a858e';
  clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.remove('show'),5000)
}
async function refreshData(){
  const endpoints=['items','departments','batches','movements','dashboard','positions','books','units','staff-directory'];
  const rows=await Promise.all(endpoints.map(path=>api(path==='positions'?statementApiPath():'/api/'+path)));
  for(let i=0;i<endpoints.length;i++)cache[endpoints[i]==='staff-directory'?'staff':endpoints[i]]=rows[i];
  if(can('users'))cache.users=await api('/api/users');
}
const selectOptions = (items,selected='',placeholder='Select one')=>`<option value="">${E(placeholder)}</option>`+items.map(o=>`<option value="${E(o.value)}" ${String(o.value)===String(selected)?'selected':''}>${E(o.label)}</option>`).join('');
const itemOptions = ()=>selectOptions(cache.items.filter(x=>x.active&&inMyBranch(x.branch)).map(x=>({value:x.id,label:`${x.sku} · ${x.trade_name?x.trade_name+' / ':''}${x.name} (${x.unit})`})),'','Select product');
// Searchable dropdown with the search box INSIDE the expanded department menu.
// The submitted value is always a real department ID; typed text alone cannot select a department.
let deptPickerCounter=0;
const departmentPicker=(label='Receiving hospital department')=>{
 const uid=`department-list-${++deptPickerCounter}`;
 const active=cache.departments.filter(x=>x.active);
 return `<div class="db-field"><span>${E(label)}</span><div class="dept-picker" data-dept-picker>
  <button type="button" class="db-select dept-trigger" data-dept-trigger aria-expanded="false" aria-haspopup="listbox" aria-controls="${uid}"><span data-dept-caption>Choose department</span><span class="dept-chevron" aria-hidden="true">▾</span></button>
  <input type="hidden" name="department_id" data-dept-value value="">
  <div class="dept-popup" data-dept-popup hidden>
   <input class="db-input dept-search" data-dept-search type="search" placeholder="Search departments..." aria-label="Search departments" autocomplete="off">
   <div id="${uid}" class="dept-option-list" data-dept-options role="listbox" aria-label="${E(label)}">${active.map(d=>`<button type="button" role="option" aria-selected="false" class="dept-option" data-dept-option="${d.id}" data-dept-name="${E(d.name)}">${E(d.name)}</button>`).join('')}</div>
   <p class="dept-no-results" data-dept-empty hidden>No matching departments</p>
  </div>
 </div></div>`;
};
function closeDepartmentPicker(picker){if(!picker)return;const pop=picker.querySelector('[data-dept-popup]');if(pop)pop.hidden=true;picker.querySelector('[data-dept-trigger]')?.setAttribute('aria-expanded','false');}
function openDepartmentPicker(picker){
 document.querySelectorAll('[data-dept-picker]').forEach(other=>{if(other!==picker)closeDepartmentPicker(other)});
 const pop=picker.querySelector('[data-dept-popup]');if(!pop)return;pop.hidden=false;
 picker.querySelector('[data-dept-trigger]')?.setAttribute('aria-expanded','true');
 const search=picker.querySelector('[data-dept-search]');search.value='';filterDeptPicker(picker);search.focus();
}
function filterDeptPicker(picker){
 const q=normalizeItemSearch(picker.querySelector('[data-dept-search]')?.value||'');let visible=0;
 picker.querySelectorAll('[data-dept-option]').forEach(btn=>{const yes=normalizeItemSearch(btn.dataset.deptName).includes(q);btn.hidden=!yes;if(yes)visible++});
 picker.querySelector('[data-dept-empty]').hidden=visible!==0;
}
function selectDepartment(picker,option){
 picker.querySelector('[data-dept-value]').value=option.dataset.deptOption;
 picker.querySelector('[data-dept-caption]').textContent=option.dataset.deptName;
 picker.querySelectorAll('[data-dept-option]').forEach(btn=>btn.setAttribute('aria-selected',String(btn===option)));
 closeDepartmentPicker(picker);picker.querySelector('[data-dept-trigger]')?.focus();
}

const batchOptions = (includeExpired=false)=>selectOptions(cache.batches.filter(x=>inMyBranch(x.branch)&&x.item_active&&x.on_hand>0&&(includeExpired||!x.expiry_date||x.expiry_date>=todayBaghdad())).map(x=>({value:x.id,label:`${x.item_name} · Batch ${x.batch_no} · ${N(x.on_hand)} ${x.unit} · Exp ${x.expiry_date||'N/A'} · ${priceLabel(x.unit_price_fils)}`})),'','Select batch');
const field=(label,input,help='')=>`<label class="db-field"><span>${E(label)}</span>${input}${help?`<small>${E(help)}</small>`:''}</label>`;
const inp=(name,placeholder='',type='text',other='')=>`<input class="db-input" name="${name}" placeholder="${E(placeholder)}" type="${type}" ${other}>`;
const head=(title,desc,actions='')=>`<div class="db-head"><div><span class="eyebrow">Central Warehouse / Live Workspace</span><h1>${E(title)}</h1><p>${E(desc)}</p></div>${actions?`<div class="db-actions">${actions}</div>`:''}</div>`;
const panel=(title,content,icon='package')=>`<section class="db-panel"><h2>${I(icon)} ${E(title)}</h2>${content}</section>`;
const table=(cols,rows)=>rows.length?`<div class="db-table-wrap"><table class="db-table"><thead><tr>${cols.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`:msg('No records yet','Add your first record using the action button above.');
// Item catalog lookup: official, generic, company and colloquial/alternate names.
const normalizeItemSearch = value=>String(value??'').toLocaleLowerCase().normalize('NFKC')
 .replace(/[\u064b-\u065f\u0670\u0640]/g,'').replace(/[إأآٱ]/g,'ا').replace(/ى/g,'ي').trim();
const itemSearchText = it=>normalizeItemSearch([it.sku,it.name,it.trade_name,it.generic_name,it.manufacturer,it.information,it.category,it.initial_batch_no,branchName(it.branch)].join(' '));
const filteredItems = query=>{
 const terms=normalizeItemSearch(query).split(/\s+/).filter(Boolean);
 return cache.items.filter(it=>terms.every(term=>itemSearchText(it).includes(term)));
};
function filterInventory(){
 const q=normalizeItemSearch($('#itemFilter')?.value||'');
 const branch=$('#itemBranchFilter')?.value||'';
 const book=$('#itemBookFilter')?.value||'';
 const status=$('#itemStockStatus')?.value||inventoryState;
 const sort=$('#itemSort')?.value||inventorySort;
 const showInactive=$('#itemIncludeInactive')?.checked??inventoryInactive;
 inventoryState=status;inventorySort=sort;inventoryInactive=showInactive;
 let matched=cache.items.filter(it=>{
  if(!showInactive&&!it.active)return false;
  if(branch&&it.branch!==branch)return false;
  if(book&&it.category!==book)return false;
  if(q&&!q.split(/\s+/).filter(Boolean).every(term=>rowSearchText(it).includes(term)))return false;
  const st=lotStats(it);
  if(status==='available')return st.usable>0;
  if(status==='empty')return st.physical===0;
  if(status==='expired')return st.expired>0;
  if(status==='unknown')return st.unknown>0;
  return true;
 });
 const compare=(a,b)=>{
  const x=lotStats(a),y=lotStats(b);
  if(sort==='expiry')return (x.next||'9999').localeCompare(y.next||'9999')||a.name.localeCompare(b.name);
  if(sort==='stock_desc')return y.physical-x.physical||a.name.localeCompare(b.name);
  if(sort==='stock_asc')return x.physical-y.physical||a.name.localeCompare(b.name);
  return (a.trade_name||a.name).localeCompare(b.trade_name||b.name);
 };
 matched.sort(compare);
 const results=$('#itemResults');if(results)results.innerHTML=detailsTable(matched,'inventory');
 const count=$('#inventoryShown');if(count)count.textContent=`${N(matched.length)} of ${N(cache.items.length)} items`;
 window.HWLang?.apply();
}
function departmentRows(depts){return depts.map(it=>`<tr><td><strong>${E(it.name)}</strong></td><td>${it.last_shipment_at?D(it.last_shipment_at):'<span class="muted-hint">No shipments yet</span>'}</td><td>${N(it.shipment_count)} </td><td>${badge(it.active?'Active':'Inactive',it.active?'':'danger')}</td><td><div class="db-small-actions"><button type="button" data-open-dept-shipments="${it.id}">Shipment history</button>${can('department_write')?`<button type="button" data-edit-dept="${it.id}">Edit</button>`:''}</div></td></tr>`)}
const routeNames={opening_balance:'Opening balance',department_issue:'Hospital departments',external_transfer_out:'External transfer',pharmacy_transfer_out:'Transfer to Pharmacy Department',pharmacy_receipt:'Pharmacy Department',purchase_receipt:'Purchases',external_transfer_in:'External transfer received',internal_return:'Internal department return'};
function movementRows(movements){return movements.map(m=>{
 const pending=m.paperwork_pending===1;
 const action=pending&&can('movement_write')?`<div class="db-small-actions" style="margin-top:8px"><button type="button" data-complete-paperwork="${m.id}">Complete missing papers</button></div>`:'';
 const docs=`<strong>${E(m.paper_ref||'—')}</strong>${m.dispatch_ref?`<div class="tiny">Dispatch/receipt: ${E(m.dispatch_ref)}</div>`:''}${pending?`<div>${badge('Emergency · papers pending','warning')}</div>`:''}${m.paperwork_completed_at?`<div class="tiny">Papers completed: ${D(m.paperwork_completed_at)}</div>`:''}${action}`;
 const recipient=m.department_name||m.external_destination||m.source||'—';
 const lines=Array.isArray(m.lines)?m.lines:[],first=lines[0];
 const preview=first?`<div class="movement-line-summary"><strong>${E(first.item_name)}</strong><span class="tiny">${E(first.batch_no)} · ${N(first.qty)} ${E(first.unit)}</span></div>`:'<span class="muted-hint">No lines recorded</span>';
 const countLabel=lines.length===1?(window.HWLang?.get()==='ar'?'مادة واحدة':'1 item'):(window.HWLang?.get()==='ar'?`${N(lines.length)} مواد`:`${N(lines.length)} items`);
 return `<tr class="movement-master-row" data-movement-master="${m.id}"><td><strong>${E(m.code)}</strong><div class="tiny">${D(m.created_at)}</div></td><td>${badge(movementLabel(m),m.route==='opening_balance'?'adjustment':(movementBadgeType[m.kind]||'neutral'))}<div class="tiny">${E(routeNames[m.route]||'Legacy movement')}</div></td><td>${docs}</td><td>${E(recipient)}${m.trusted_pharmacist_name||m.trusted_pharmacist_username?`<div class="tiny">Trusted pharmacist: ${E(m.trusted_pharmacist_name||m.trusted_pharmacist_username)}</div>`:''}${m.authorization_ref?`<div class="tiny">Authorization letter no.: ${E(m.authorization_ref)}</div>`:''}</td><td><div class="movement-lines-cell">${preview}<button type="button" class="movement-expand-btn" data-expand-movement="${m.id}" aria-expanded="false" aria-label="${E(window.HWLang?.get()==='ar'?'عرض جميع مواد المستند':'Show all receipt items')}" title="${E(window.HWLang?.get()==='ar'?'عرض تفاصيل المستند':'Full receipt details')}"><span class="movement-count-pill">${E(countLabel)}</span><span class="movement-chevron" aria-hidden="true">▾</span></button></div></td><td>${E(m.creator)}</td></tr>`;
 });}
// Expand a document without another database call. The existing /api/movements
// response already contains every line for each returned receipt/issue.
function movementDetailsRow(m){
 const lines=Array.isArray(m.lines)?m.lines:[];
 const route=routeNames[m.route]||'Recorded movement',recipient=m.department_name||m.external_destination||m.source||'—';
 const headers=['#','Item / المادة','Batch / الوجبة','Manufacture date / الإنتاج','Expiry / الصلاحية','Qty / الكمية','Price / السعر'];
 const body=lines.map((l,i)=>`<tr><td><span class="item-row-number">${N(i+1)}</span></td><td><strong>${E(l.item_name)}</strong><div class="tiny">${E(l.sku||'')}</div></td><td>${E(l.batch_no||'—')}</td><td>${E(l.manufacture_date||'—')}</td><td>${E(l.expiry_date||'—')}</td><td><strong>${N(l.qty)}</strong> ${E(l.unit)}</td><td>${priceLabel(l.unit_price_fils)}</td></tr>`).join('');
 const docs=[m.paper_ref?`<span><strong>Order / المستند:</strong> ${E(m.paper_ref)}</span>`:'',m.dispatch_ref?`<span><strong>Dispatch / التجهيز:</strong> ${E(m.dispatch_ref)}</span>`:'',m.authorization_ref?`<span><strong>Authorization / التخويل:</strong> ${E(m.authorization_ref)}</span>`:''].filter(Boolean).join('');
 return `<tr class="movement-details-row" data-expanded-movement="${m.id}"><td colspan="6"><div class="movement-details-panel" role="region" aria-label="${E('Details for '+m.code)}"><div class="movement-details-header"><div><strong>${E(m.code)} · ${E(route)}</strong><span>${E(recipient)} · ${D(m.created_at)} · ${E(m.creator||'')}</span></div><span class="movement-detail-count">${N(lines.length)} ${window.HWLang?.get()==='ar'?'سطر مواد':'item lines'}</span></div>${docs?`<div class="movement-document-refs">${docs}</div>`:''}<div class="db-table-wrap"><table class="db-table movement-lines-table"><thead><tr>${headers.map(h=>`<th>${E(h)}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>${!lines.length?'<p class="muted-hint">No item lines found.</p>':''}</div></td></tr>`;
}
function toggleMovementDetails(button){
 const row=button.closest('tr[data-movement-master]');if(!row)return;
 const id=Number(button.dataset.expandMovement),expanded=row.nextElementSibling;
 if(expanded?.matches(`[data-expanded-movement="${id}"]`)){
  expanded.remove();button.setAttribute('aria-expanded','false');button.querySelector('.movement-chevron').textContent='▾';return;
 }
 const movement=cache.movements.find(m=>m.id===id);if(!movement)return;
 row.insertAdjacentHTML('afterend',movementDetailsRow(movement));
 button.setAttribute('aria-expanded','true');button.querySelector('.movement-chevron').textContent='▴';
 window.HWLang?.apply();
}

function batchRows(rows){return rows.map((b,i)=>`<tr><td><span class="item-row-number">${N(i+1)}</span></td><td><strong>${E(b.item_name)}</strong><div class="tiny">${E(b.sku)}</div></td><td>${E(branchName(b.branch))}</td><td>${E(b.batch_no)}</td><td>${E(b.expiry_date||'Not applicable')}</td><td>${priceLabel(b.unit_price_fils)}</td><td><strong>${N(b.on_hand)}</strong> ${E(b.unit)}</td><td>${b.expiry_date&&b.expiry_date<todayBaghdad()?badge('Expired','danger'):b.on_hand===0?badge('Empty'):badge('Available','blue')}</td></tr>`)}
function overview(){
 const s=cache.dashboard;
 const metrics=[['Registered items',s.items,'Products in catalog','package'],['Warehouse units',s.stock,'Total stock across all batches','packages'],['Active departments',s.departments,'Distribution destinations','building'],['Recorded movements',s.movements,'Permanent transaction log','history']];
 const kpis=`<div class="db-kpis">${metrics.map(([label,num,desc,icon])=>`<div class="db-kpi"><span class="name">${I(icon)} ${E(label)}</span><span class="num">${N(num)}</span><span class="desc">${E(desc)}</span></div>`).join('')}</div>`;
 const alerts=cache.items.filter(i=>i.active&&i.min_stock>0&&i.stock<i.min_stock);
 const exp=cache.batches.filter(b=>b.on_hand>0&&b.expiry_date&&b.expiry_date>=todayBaghdad()&&b.expiry_date<=new Date(Date.now()+60*864e5).toISOString().slice(0,10));
 return `<div class="db-decor">${head('Welcome back, '+user.full_name,'Your central warehouse is connected to the local database. Inventory and movements below update after every saved transaction.')}
 <div class="db-actions">${can('item_write')&&(user.role==='admin'||user.branch)?`<button class="db-btn" data-new="item">${I('package')} Add item</button>`:''}${can('department_write')?`<button class="db-btn secondary" data-new="dept">${I('building')} Add department</button>`:''}${can('movement_write')?`<button class="db-btn secondary" data-go="receiving">${I('incoming')} Receive shipment</button><button class="db-btn secondary" data-go="distribution">${I('outgoing')} Distribute stock</button>`:''}</div></div>
 ${user.role!=='admin'&&!user.branch?'<div class="db-alert"><strong>Warehouse branch not assigned.</strong> Ask your administrator to assign your account to one branch before managing stock.</div>':''}
 ${user.must_change_password?`<div class="db-alert"><strong>Change your temporary password.</strong> Open My account → Change password to secure your login.</div>`:''}
 ${kpis}<div class="db-layout"><div>${panel('Recent warehouse movements',table(['Movement','Type','Paper reference','From / To','Lines','By'],movementRows(cache.movements.slice(0,6))),'history')}</div><div>${panel('Attention needed',`<div class="db-help">${I('warning')} ${alerts.length} item(s) under the reorder threshold · ${exp.length} batch(es) expiring in the next 60 days.</div><div style="margin-top:15px">${alerts.slice(0,5).map(i=>`<div style="display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid #eaf1f4;font-size:11px"><span>${E(i.name)}</span><strong>${N(i.stock)} / ${N(i.min_stock)}</strong></div>`).join('')||'<p class="muted-hint">No low-stock alerts at the moment.</p>'}</div>`,'warning')}
 ${panel('Quick navigation',`<div class="db-actions"><button class="db-btn secondary" data-go="inventory">Inventory</button><button class="db-btn secondary" data-go="departments">Departments</button><button class="db-btn secondary" data-go="movements">Movement history</button></div>`,'dashboard')}</div></div>`
}
function inventory(){return `${head('Item inventory','All product details and stored batch versions in one place. Expand an item to see its different batch numbers, expiry dates, lot prices and movement history.',can('item_write')&&(user.role==='admin'||user.branch)?`<button class="db-btn" data-new="item">${I('package')} New item</button>`:'')}
 ${panel('Product catalog',`<div class="db-note"><span>By default only items with positive unexpired, dated stock are shown.</span><span>Switch the stock filter to inspect zero-stock items, expired lots, unknown expiry or all records. Quantity and prices are recorded per lot.</span></div>
 <div class="db-toolbar inventory-filters">
 ${inp('filter','Search product, scientific name, batch or alias...','search','id="itemFilter"')}
 <select class="db-select" id="itemBranchFilter"><option value="">All branches</option>${branchList('').replace('<option value="">Select a branch</option>','')}</select>
 <select class="db-select" id="itemBookFilter">${filterBookOptions()}</select>
 <select class="db-select" id="itemStockStatus"><option value="available" ${inventoryState==='available'?'selected':''}>Available / usable</option><option value="empty" ${inventoryState==='empty'?'selected':''}>Out of stock (zero)</option><option value="expired" ${inventoryState==='expired'?'selected':''}>Has expired stock</option><option value="unknown" ${inventoryState==='unknown'?'selected':''}>No recorded expiry</option><option value="all" ${inventoryState==='all'?'selected':''}>All stock statuses</option></select>
 <select class="db-select" id="itemSort"><option value="name" ${inventorySort==='name'?'selected':''}>Sort: name</option><option value="expiry" ${inventorySort==='expiry'?'selected':''}>Sort: earliest expiry</option><option value="stock_desc" ${inventorySort==='stock_desc'?'selected':''}>Sort: most stock</option><option value="stock_asc" ${inventorySort==='stock_asc'?'selected':''}>Sort: least stock</option></select>
 <label class="include-inactive"><input id="itemIncludeInactive" type="checkbox" ${inventoryInactive?'checked':''}> Include inactive products</label>
 ${columnPicker('inventory')}<span class="muted-hint" id="inventoryShown"></span>
 </div><div id="itemResults"></div>`,'package')}`}
function departments(){return `${head('Hospital departments','The approved departments are preloaded once. You can add more, rename them or deactivate them without changing movement history.',can('department_write')?`<button class="db-btn" data-new="dept">${I('building')} Add department</button>`:'')}${panel('Saved departments',`<div class="db-toolbar">${inp('dept_filter','Search departments...','search','id="departmentFilter"')}<span class="muted-hint">${cache.departments.filter(d=>d.active).length} active departments</span></div><div id="departmentResults">${table(['Department','Last shipment','Shipments','Status','Actions'],departmentRows(cache.departments))}</div>`,'building')}`}
function filterDepartmentTable(){const input=$('#departmentFilter'),results=$('#departmentResults');if(!input||!results)return;const q=normalizeItemSearch(input.value);results.innerHTML=table(['Department','Last shipment','Shipments','Status','Actions'],departmentRows(cache.departments.filter(d=>normalizeItemSearch(d.name).includes(q))));}

// V4.18: dedicated item and department shipment timelines.
function itemMovements(){
 const rows=cache.items.map((it,i)=>{
  const stat=lotStats(it);
  return `<tr data-item-movement-row><td><span class="item-row-number">${N(i+1)}</span></td><td><strong>${E(it.trade_name||it.name)}</strong><div class="tiny">${E(it.name)} · ${E(it.sku)}</div></td><td>${E(branchName(it.branch))}</td><td>${E(it.category)}</td><td>${N(stat.physical)} ${E(it.unit)}</td><td>${N(stat.lots.length)}</td><td><button type="button" class="db-btn secondary small" data-open-item-shipments="${it.id}">Track movements</button></td></tr>`;
 });
 return `${head('حركة المواد — Item movements','Choose any registered item to inspect every incoming, outgoing, opening-balance, return and adjustment document it appeared in.')}
 ${panel('All registered items',`<div class="db-toolbar">${inp('item-movement-search','Search item, scientific name, batch or alias...','search','id="itemMovementSearch"')}</div><div id="itemMovementResults">${table(['#','Product','Branch','Register book','Stock','Lots','Movement history'],rows)}</div>`,'history')}`;
}
function filterItemMovements(){
 const q=normalizeItemSearch($('#itemMovementSearch')?.value||'');
 const rows=cache.items.filter(it=>!q||rowSearchText(it).includes(q)).map((it,i)=>{
  const stat=lotStats(it);
  return `<tr><td><span class="item-row-number">${N(i+1)}</span></td><td><strong>${E(it.trade_name||it.name)}</strong><div class="tiny">${E(it.name)} · ${E(it.sku)}</div></td><td>${E(branchName(it.branch))}</td><td>${E(it.category)}</td><td>${N(stat.physical)} ${E(it.unit)}</td><td>${N(stat.lots.length)}</td><td><button class="db-btn secondary small" data-open-item-shipments="${it.id}">Track movements</button></td></tr>`;
 });
 const root=$('#itemMovementResults');if(root)root.innerHTML=table(['#','Product','Branch','Register book','Stock','Lots','Movement history'],rows);
 window.HWLang?.apply();
}
let shipmentHistoryScope=null;
function closeShipmentHistory(){const el=$('#movementDetailModal');if(!el)return;el.classList.remove('open');el.setAttribute('aria-hidden','true');el.innerHTML='';shipmentHistoryScope=null;}
async function openShipmentHistory(type,id){
 const obj=type==='item'?cache.items.find(x=>x.id===id):cache.departments.find(x=>x.id===id);
 if(!obj)return;
 const name=type==='item'?(obj.trade_name||obj.name):obj.name;
 shipmentHistoryScope={type,id};
 const modal=$('#movementDetailModal');
 modal.innerHTML=`<section class="shipment-history-dialog" role="dialog" aria-modal="true" aria-label="Recorded shipment history" tabindex="-1"><header class="shipment-history-header"><div><small>${type==='item'?'حركة المواد':'حركات القسم'}</small><h2>${E(name)}</h2><p>All recorded shipments, newest first. Every shipment includes document references and its full stock-line details.</p></div><button type="button" class="db-btn secondary small" data-close-shipment-history>إغلاق ×</button></header><div class="shipment-history-scroll" id="shipmentHistoryContent">${msg('Loading shipment history...')}</div><footer class="shipment-history-footer"><span>Read-only records — stock quantities are not changed here.</span></footer></section>`;
 modal.classList.add('open');modal.setAttribute('aria-hidden','false');window.HWLang?.apply();
 modal.querySelector('[data-close-shipment-history]')?.focus();
 await loadShipmentHistory(0);
}
function shipmentCard(m,scope){
 const route=routeNames[m.route]||m.route||'—';
 const direction=m.kind==='IN'||m.kind==='ADJUST_PLUS'||m.kind==='RETURN';
 const color=m.route==='opening_balance'?'adjustment':direction?'intake':'dispatch';
 const recipient=m.department_name||m.external_destination||m.source||'—';
 const documents=[['رقم الطلبية / Order',m.paper_ref],['ورقة التجهيز / Dispatch',m.dispatch_ref],['المصدر / الوجهة',recipient],['Route',route],['Employee',m.operator],['Trusted pharmacist',m.trusted_pharmacist_name],['رقم كتاب التخويل',m.authorization_ref]].filter(([,v])=>!!v);
 const lines=(m.lines||[]).map((l,i)=>`<tr class="${scope.type==='item'&&l.item_id===scope.id?'selected-shipment-line':''}"><td><span class="item-row-number">${N(i+1)}</span></td><td>${E(l.trade_name||l.item_name)}<div class="tiny">${E(l.sku)}</div></td><td>${E(l.batch_no)}<div class="tiny">Lot ${N(l.lot_id)}</div></td><td>${E(l.manufacture_date||'—')}</td><td>${E(l.expiry_date||'—')}</td><td>${l.direction>0?'+':'−'}${N(l.qty)} ${E(l.unit)}</td><td>${priceLabel(l.unit_price_fils)}</td></tr>`);
 return `<article class="shipment-history-card"><div class="shipment-history-title"><div><strong>${E(m.code)}</strong><span class="tiny">${D(m.created_at)}</span></div>${badge(m.route==='opening_balance'?'رصيد افتتاحي':direction?'إدخال مخزني':'إخراج مخزني',color)}</div><div class="shipment-meta">${documents.map(([k,v])=>`<div><span>${E(k)}</span><strong>${E(v)}</strong></div>`).join('')}${m.paperwork_pending?'<div class="pending-paperwork">Emergency documents pending</div>':''}</div><div class="db-table-wrap">${table(['#','Product','Lot','Manufacture','Expiry','Quantity','Unit price'],lines)}</div>${m.notes?`<p class="shipment-notes">${E(m.notes)}</p>`:''}</article>`;
}
async function loadShipmentHistory(offset=0){
 const state=shipmentHistoryScope,el=$('#shipmentHistoryContent');if(!state||!el)return;
 const btn=el.querySelector('[data-more-shipments]');if(btn){btn.disabled=true;btn.textContent='Loading…';}
 try{
  const path=state.type==='item'?`/api/items/${state.id}/shipments`:`/api/departments/${state.id}/shipments`;
  const data=await api(`${path}?limit=25&offset=${offset}`);
  if(!shipmentHistoryScope||shipmentHistoryScope.id!==state.id||shipmentHistoryScope.type!==state.type)return;
  if(offset===0)el.innerHTML=`<div class="shipment-counter">${N(data.total)} recorded shipment(s)</div><div id="shipmentCards"></div>`;
  el.querySelector('[data-more-shipments]')?.remove();
  const cards=el.querySelector('#shipmentCards');
  cards?.insertAdjacentHTML('beforeend',data.shipments.map(m=>shipmentCard(m,state)).join(''));
  if(!data.total)el.innerHTML=msg('No shipments yet','This item or department has no recorded stock movements.');
  const next=offset+data.shipments.length;
  if(next<data.total)el.insertAdjacentHTML('beforeend',`<button type="button" class="db-btn secondary" data-more-shipments="${next}">Show more (${N(data.total-next)} remaining)</button>`);
  window.HWLang?.apply();
 }catch(err){toast(err.message,'error');if(btn){btn.disabled=false;btn.textContent='Retry'}}
}
function profilePage(){
 return `${head('My account — الملف الشخصي','Maintain your own employee contact information. Role, login name and assigned branch remain administrator-controlled.')}
 ${panel('Personal information',`<div id="profileContents">${msg('Loading your account...')}</div>`,'user')}`;
}
async function loadProfile(){
 try{
  const p=await api('/api/profile');if(view!=='profile')return;
  $('#profileContents').innerHTML=`<div class="profile-summary"><div><span>Username</span><strong>${E(p.username)}</strong></div><div><span>Role</span><strong>${E(p.role)}</strong></div><div><span>Assigned branch</span><strong>${E(p.role==='admin'?'All branches':branchName(p.branch))}</strong></div></div>
  <form id="profileForm" class="db-form"><div class="db-grid">
   ${field('Full name',`<input name="full_name" class="db-input" maxlength="100" required value="${E(p.full_name)}">`)}
   ${field('Email',`<input name="email" type="email" maxlength="200" class="db-input" value="${E(p.email)}" placeholder="name@example.com">`)}
   ${field('Phone number',`<input name="phone" type="tel" maxlength="35" class="db-input" value="${E(p.phone)}" placeholder="+964 ...">`)}
   ${field('Age',`<input name="age" type="number" min="0" max="120" step="1" class="db-input" value="${p.age==null?'':E(p.age)}">`)}
   ${field('Job title',`<input name="job_title" class="db-input" maxlength="100" value="${E(p.job_title)}" placeholder="Pharmacist / Warehouse employee">`)}
   </div><button type="submit" class="db-btn">Save my information</button></form>
  <div class="profile-password"><h3>تغيير كلمة المرور — Change password</h3><form id="passwordForm" class="db-form"><div class="db-grid">
  ${field('Current password',inp('current_password','','password','required autocomplete="current-password"'))}
  ${field('New password (8+ characters)',inp('new_password','','password','required minlength="8" autocomplete="new-password"'))}
  </div><button type="submit" class="db-btn">Update my password</button></form></div>
  <p class="muted-hint profile-help">Your role, warehouse branch, and username remain administrator-controlled.</p>`;
  window.HWLang?.apply();
 }catch(err){toast(err.message,'error')}
}
// Old links to #batches redirect to the combined Inventory screen.
function batches(){return inventory()}
function movements(){return `${head('Movement history','Every receipt, issue, return and adjustment has a permanent movement ID plus the original document reference.')}${panel('Transaction register',`<div class="db-toolbar">${inp('movement_filter','Search requisition, item or user...','search','id="movementFilter"')}<select class="db-select" id="movementType" style="max-width:180px"><option value="">All types</option><option value="IN">Warehouse intake</option><option value="OUT">Warehouse dispatch</option><option value="RETURN">Returns</option><option value="ADJUST_PLUS">Adjustment (+)</option><option value="ADJUST_MINUS">Adjustment (−)</option></select></div><div id="movementResults">${table(['Movement ID','Type','Paper refs','Source / destination','Item lines','Operator'],movementRows(cache.movements))}</div>`,'history')}`}
// In shipment menus, an authorized item editor can create a missing catalog item without leaving the draft.
const inlineItemButton = mode => can('item_write') && (user.role==='admin'||user.branch)
 ? `<button type="button" class="db-btn secondary small inline-item-button" data-inline-item="${mode}">+ Register item not in list</button>` : '';
const receiveLine=()=>`<div class="ship-line receive-priced" data-receive-line>
${field('Product',`<select class="db-select" data-key="item_id" required>${itemOptions()}</select>${inlineItemButton('receive')}`)}
${field('Batch number',`<input class="db-input" data-key="batch_no" placeholder="e.g. LOT-24A" required maxlength="90">`)}
${field('Expiry date',`<input class="db-input" type="date" data-key="expiry_date">`)}
${field('Quantity',`<input class="db-input" type="number" data-key="qty" min="1" step="1" required placeholder="0">`)}
${field('Price — دينار',`<input class="db-input" data-key="price_dinars" type="number" min="0" max="999999999" step="1" required placeholder="0">`)}
${field('Price — فلس',`<input class="db-input" data-key="price_fils_component" type="number" min="0" max="999" step="1" required placeholder="0">`)}
<button class="db-btn danger small" type="button" data-remove-line title="Remove line">×</button></div>`;
function prefillReceiptPrice(line){
 const id=Number(line?.querySelector('[data-key="item_id"]')?.value);
 const item=cache.items.find(x=>x.id===id);
 const price=item?.price_fils;
 if(!line||price==null)return;
 const d=line.querySelector('[data-key="price_dinars"]'),f=line.querySelector('[data-key="price_fils_component"]');
 if(d)d.value=String(Math.floor(price/1000));
 if(f)f.value=String(price%1000);
}
// Outgoing issues: select a product THEN an exact received lot. The lot supplies
// the authoritative batch number and expiry; the issue's dinar/fils snapshot may
// be edited without mutating the original receipt lot price.
const issueLine=(includeExpired=false)=>includeExpired
 ? `<div class="ship-line issue legacy-issue" data-issue-line data-allow-expired="1">${field('Select product batch',`<select class="db-select" data-key="batch_id" required>${batchOptions(true)}</select>`)}${field('Quantity',`<input class="db-input" type="number" data-key="qty" min="1" step="1" required placeholder="0">`)}<button class="db-btn danger small" type="button" data-remove-line>×</button></div>`
 : `<div class="ship-line issue-detailed" data-issue-line data-allow-expired="0">
 ${field('Product',`<select class="db-select" data-key="item_id" data-issue-product required>${itemOptions()}</select>${inlineItemButton('issue')}`)}
 ${field('Expiration date — تاريخ الصلاحية',`<select class="db-select" data-issue-expiry-picker required><option value="">اختر الصنف أولاً</option></select>`)}
 ${field('Batch / lot — الوجبة',`<input type="hidden" data-key="batch_id" data-issue-batch required><input class="db-input" data-issue-batch-display readonly aria-label="Selected batch number"><select class="db-select" data-issue-same-date-lot hidden aria-label="Choose lot for shared expiry date"></select>`)}
 ${field('Quantity',`<input type="number" class="db-input" data-key="qty" data-issue-qty min="1" step="1" required placeholder="0">`)}
 ${field('Price — دينار',`<input type="number" class="db-input" data-key="price_dinars" min="0" max="999999999" step="1" required placeholder="0">`)}
 ${field('Price — فلس',`<input type="number" class="db-input" data-key="price_fils_component" min="0" max="999" step="1" required placeholder="0">`)}
 <button class="db-btn danger small" type="button" data-remove-line aria-label="Remove product">×</button>
 <div class="fefo-line-notice" data-fefo-notice role="status" aria-live="polite" hidden></div><div class="issue-quantity-warning" data-qty-warning role="alert" hidden></div></div>`;
// FEFO: first expiring, first out. Expired lots are not issueable.
const fefoSort=(a,b)=>{
 const ad=a.expiry_date||'9999-12-31',bd=b.expiry_date||'9999-12-31';
 return ad.localeCompare(bd)||a.id-b.id;
};
const fefoAr=()=>window.HWLang?.get()!=='en';
const fefoDateDays=(expiry)=>{
 if(!expiry)return null;
 const iso=t=>Date.UTC(...t.split('-').map(Number).map((v,i)=>i===1?v-1:v));
 return Math.round((iso(expiry)-iso(todayBaghdad()))/86400000);
};
const eligibleLots=(itemId)=>cache.batches.filter(b=>b.item_id===itemId&&b.item_active&&inMyBranch(b.branch)&&b.on_hand>0&&(!b.expiry_date||b.expiry_date>=todayBaghdad())).sort(fefoSort);
function fefoWarningDetails(form){
 const lines=$$('[data-issue-line].issue-detailed',form),planned=new Map(),itemMap=new Map(),warnings=[];
 for(const line of lines){
  const lot=cache.batches.find(b=>b.id===Number(line.querySelector('[data-issue-batch]')?.value));
  const qty=Number(line.querySelector('[data-issue-qty]')?.value||0);
  if(lot&&qty>0){planned.set(lot.id,(planned.get(lot.id)||0)+qty);itemMap.set(lot.item_id,true);}
 }
 for(const id of itemMap.keys()){
  const lots=eligibleLots(id);
  for(const lot of lots){
   if(!(planned.get(lot.id)>0))continue;
   const earlier=lots.find(other=>(other.expiry_date||'9999-12-31')<(lot.expiry_date||'9999-12-31')&&other.on_hand>(planned.get(other.id)||0));
   if(earlier)warnings.push({lot,earlier,remaining:earlier.on_hand-(planned.get(earlier.id)||0)});
  }
 }
 return warnings;
}
function updateFefoNotices(form=$('#issueForm')){
 if(!form)return;
 const ar=fefoAr(),warnings=fefoWarningDetails(form);
 const selectionWarnings=new Map(warnings.map(w=>[w.lot.id,w]));
 for(const line of $$('[data-issue-line].issue-detailed',form)){
  const iid=Number(line.querySelector('[data-issue-product]')?.value||0),lot=cache.batches.find(b=>b.id===Number(line.querySelector('[data-issue-batch]')?.value));
  const message=line.querySelector('[data-fefo-notice]');if(!message)continue;
  validateIssueQuantity(line);
  if(!iid){message.hidden=true;continue;}
  const lots=eligibleLots(iid),best=lots[0],warning=lot&&selectionWarnings.get(lot.id);
  message.hidden=false;message.className='fefo-line-notice';
  if(!best){message.classList.add('danger');message.textContent=ar?'لا توجد وجبات متاحة للصرف لهذا الصنف.':'No available lot can be issued for this product.';continue;}
  const shown=lot||best,days=fefoDateDays(shown.expiry_date);
  const closest=ar?`الوجبة ${shown.batch_no} · الصلاحية ${shown.expiry_date||'غير مسجلة'} · الرصيد ${N(shown.on_hand)}`:
   `Lot ${shown.batch_no} · expiry ${shown.expiry_date||'not recorded'} · available ${N(shown.on_hand)}`;
  if(warning){
   message.classList.add('danger');
   message.innerHTML=`<strong>${ar?'تنبيه FEFO: توجد وجبة أقدم صلاحية لم تُصرف بالكامل.':'FEFO warning: an earlier-expiring lot still has stock.'}</strong> ${E(ar?'الأولوية: ':'Use first: ')}${E(warning.earlier.batch_no)} · ${E(warning.earlier.expiry_date||'—')} · ${N(warning.remaining)} ${E(ar?'متبقية':'remaining')}. <button type="button" class="fefo-pick" data-fefo-pick="${warning.earlier.id}">${ar?'اختيار الوجبة الأسبق':'Select earlier lot'}</button>`;
  }else if(lot&&lot.id!==best.id&&(lot.expiry_date||'9999-12-31')>(best.expiry_date||'9999-12-31')&&!Number(line.querySelector('[data-issue-qty]')?.value||0)){
   message.classList.add('warning');
   message.innerHTML=`${E(ar?'تم اختيار وجبة أحدث صلاحية. يُنصح باختيار الأقرب انتهاءً أولاً: ':'A later-expiring lot is selected. Recommended first: ')}${E(best.batch_no)} · ${E(best.expiry_date||'—')} <button type="button" class="fefo-pick" data-fefo-pick="${best.id}">${ar?'اختيار الأقرب':'Select earliest'}</button>`;
  }else if(!lot){message.classList.add('warning');message.textContent=(ar?'الأقرب انتهاءً أولاً (FEFO): ':'Earliest expiry first (FEFO): ')+closest;}
  else if(days===null){message.classList.add('warning');message.textContent=ar?'تاريخ انتهاء هذه الوجبة غير مسجّل. تحقق من الصلاحية قبل الصرف.':'This lot has no recorded expiry. Verify the date before issue.';}
  else if(days<=60){message.classList.add('warning');message.textContent=(ar?'★ ⚠ أقرب وجبة للصرف؛ متبقي ':'★ ⚠ Earliest lot to issue; ')+N(days)+(ar?' يوم. ':' days left. ')+closest;}
  else{message.classList.add('success');message.textContent=(ar?'★ ✓ صرف حسب أقرب تاريخ صلاحية: ':'★ ✓ FEFO priority: ')+closest;}
 }
 const wrap=form.querySelector('[data-fefo-override-wrap]');
 if(wrap){wrap.hidden=!warnings.length;const reason=wrap.querySelector('[name="fefo_override_reason"]');if(reason)reason.required=!!warnings.length;}
 const top=form.querySelector('[data-fefo-summary]');
 if(top){const urgent=cache.batches.filter(b=>b.on_hand>0&&b.item_active&&inMyBranch(b.branch)&&b.expiry_date&&b.expiry_date>=todayBaghdad()&&fefoDateDays(b.expiry_date)<=60);
  top.textContent=ar?`قاعدة الصرف: الأقرب انتهاءً أولاً (FEFO). توجد ${urgent.length} وجبة صالحة تنتهي خلال ٦٠ يوماً في المخزن.`:
  `Issue earliest-expiring usable lots first (FEFO). ${urgent.length} usable lot(s) expire within 60 days.`;
 }
}
// V4.18: expiry-first selection, with exact lot IDs retained for movements.
// Two or more lots can share an expiry date but differ in batch and price;
// the extra lot selector appears only when necessary to prevent ambiguity.
function syncIssueProduct(line, preferredBatch=null){
 if(!line?.matches('.issue-detailed'))return;
 const iid=Number(line.querySelector('[data-issue-product]')?.value||0),lots=eligibleLots(iid);
 const expirySelect=line.querySelector('[data-issue-expiry-picker]');
 const former=cache.batches.find(b=>b.id===Number(preferredBatch??line.querySelector('[data-issue-batch]')?.value));
 const dates=[...new Set(lots.map(b=>b.expiry_date||''))];
 expirySelect.innerHTML=selectOptions(dates.map((date,i)=>({value:date||'unknown',label:i===0?`★ ${date||'تاريخ الصلاحية غير مسجل'} · ${fefoAr()?'الموصى بها':'Recommended'}`:date||'تاريخ الصلاحية غير مسجل'})),'','اختر تاريخ الصلاحية');
 expirySelect.classList.toggle('fefo-recommended-select',!!dates.length);
 expirySelect.title=dates.length?(fefoAr()?'★ أقرب تاريخ صلاحية صالح للصرف':'★ Earliest usable expiration date recommended'):'';
 expirySelect.value=dates.includes(former?.expiry_date||null)?former.expiry_date||'unknown':dates.length?(dates[0]||'unknown'):'';
 syncIssueExpiry(line,preferredBatch);
 window.HWLang?.apply();
}
function syncIssueExpiry(line,preferredBatch=null){
 if(!line?.matches('.issue-detailed'))return;
 const iid=Number(line.querySelector('[data-issue-product]')?.value||0),exp=line.querySelector('[data-issue-expiry-picker]')?.value;
 const lots=eligibleLots(iid).filter(b=>(b.expiry_date||'unknown')===exp);
 const exact=line.querySelector('[data-issue-batch]'),same=line.querySelector('[data-issue-same-date-lot]');
 const chosen=lots.find(b=>b.id===Number(preferredBatch??exact.value))||lots[0];
 same.hidden=lots.length<=1;
 same.innerHTML=lots.map(b=>`<option value="${b.id}">${E(b.batch_no)} · ${N(b.on_hand)} ${E(b.unit)} · ${priceLabel(b.unit_price_fils)}</option>`).join('');
 if(chosen){same.value=String(chosen.id);exact.value=String(chosen.id)}else{exact.value=''}
 syncIssueBatch(line);
}
function syncIssueBatch(line){
 if(!line?.matches('.issue-detailed'))return;
 const batch=cache.batches.find(b=>b.id===Number(line.querySelector('[data-issue-batch]')?.value));
 const display=line.querySelector('[data-issue-batch-display]');if(display)display.value=batch?.batch_no||'';
 const qty=line.querySelector('[data-issue-qty]');if(qty){qty.max=batch?.on_hand??'';}
 const price=batch?.unit_price_fils;
 const d=line.querySelector('[data-key="price_dinars"]'),f=line.querySelector('[data-key="price_fils_component"]');
 if(d)d.value=price==null?'':String(Math.floor(price/1000));
 if(f)f.value=price==null?'':String(price%1000);
 updateFefoNotices();
}
function validateIssueQuantity(line){
 const lot=cache.batches.find(b=>b.id===Number(line?.querySelector('[data-issue-batch]')?.value));
 const qty=Number(line?.querySelector('[data-issue-qty]')?.value||0);
 const note=line?.querySelector('[data-qty-warning]');if(!note)return;
 const tooMuch=!!lot&&qty>lot.on_hand;
 note.hidden=!tooMuch;
 if(tooMuch){note.textContent=(fefoAr()?'⚠ الكمية المطلوبة أكبر من الرصيد المتوفر لهذه الوجبة. المتوفر: ':'⚠ Requested quantity exceeds this lot’s available stock: ')+N(lot.on_hand);}
 if(!tooMuch&&lot&&qty>0){const used=$$('[data-issue-line].issue-detailed',line.closest('form')).filter(l=>l.querySelector('[data-issue-batch]')?.value===String(lot.id)).reduce((a,l)=>a+Number(l.querySelector('[data-issue-qty]')?.value||0),0);
 if(used>lot.on_hand){note.hidden=false;note.textContent=fefoAr()?`⚠ مجموع الكميات المختارة من هذه الوجبة (${N(used)}) يتجاوز الرصيد (${N(lot.on_hand)}).`:`⚠ Total requested from this lot (${N(used)}) exceeds available stock (${N(lot.on_hand)}).`;}}
}
// V4.7 — explicit 4-in / 3-out shipment route selectors.
function shipmentChoice(name,value,title,desc,checked=false){return `<label class="dest-choice-option"><input type="radio" name="${name}" value="${value}" ${checked?'checked':''}><span><strong>${E(title)}</strong><small>${E(desc)}</small></span></label>`;}
const routeField=(selector,content)=>`<div class="dest-fields" data-${selector}>${content}</div>`;
function receiving(){return `${head('Receive incoming shipment','Choose one of four documented routes into the central warehouse. Returning department stock is recorded as an actual RETURN movement.')}
${panel('Incoming shipments · استلام مواد',`<form id="receiveForm" class="db-form">
<div class="dest-choice four-routes" role="group" aria-label="Incoming route">
${shipmentChoice('route','pharmacy_receipt','Pharmacy Department','Received from Pharmacy Department',true)}
${shipmentChoice('route','purchase_receipt','Purchases','Drugstore and distributor receipts')}
${shipmentChoice('route','external_transfer_in','External transfer','Received from another hospital or sector')}
${shipmentChoice('route','internal_return','Internal department return','Materials returned by a hospital department')}
</div><div class="db-grid">
${routeField('in-pharmacy',field('Received from',`<input class="db-input" value="قسم الصيدلة" readonly>`))}
${routeField('in-purchase',field('Drugstore / distributor name',inp('source','Supplier or distributor','text','maxlength="180"')))}
${routeField('in-external',field('Sending hospital / external sector',inp('source','Hospital / organization name','text','maxlength="180"')))}
${routeField('in-return',departmentPicker('Returning hospital department'))}
${routeField('in-ref',field('Receipt / order paper number',inp('paper_ref','Paper reference','text','maxlength="80" required')))}
${routeField('in-dispatch',field('Warehouse return receipt number',inp('dispatch_ref','Our return receipt number','text','maxlength="80"')))}
${routeField('in-pharmacist',field('Trusted pharmacist name',inp('trusted_pharmacist_name','Full name of authorized pharmacist','text','maxlength="160"')))}
${routeField('in-authorization',field('Authorization letter number — رقم كتاب التخويل',inp('authorization_ref','Authorization letter / decree number','text','maxlength="90"')))}
${field('Notes (optional)',`<textarea name="notes" class="db-textarea" placeholder="Receipt or delivery details"></textarea>`)}
</div><h3 class="shipment-lines-title">Received product batches</h3>
<div id="receiptLines">${receiveLine()}</div>
<div class="db-actions"><button type="button" class="db-btn secondary" data-add="receive">+ Add another item</button><button type="submit" class="db-btn">${I('incoming')} Save receipt and update stock</button></div>
</form>`,'incoming')}`}
function syncIncomingRoute(form){
 if(!form)return;
 const route=form.querySelector('input[name="route"]:checked')?.value||'pharmacy_receipt';
 const active={ 'in-pharmacy':route==='pharmacy_receipt','in-purchase':route==='purchase_receipt','in-external':route==='external_transfer_in',
 'in-return':route==='internal_return','in-ref':true,'in-dispatch':route==='internal_return','in-pharmacist':route==='external_transfer_in','in-authorization':route==='external_transfer_in'};
 for(const [key,yes] of Object.entries(active)){
  const wrapper=form.querySelector(`[data-${key}]`);if(!wrapper)continue;
  wrapper.hidden=!yes;
  wrapper.querySelectorAll('input,select,textarea').forEach(el=>{if(!el.readOnly){el.disabled=!yes;el.required=yes&&el.name!=='notes'} });
 }
 const refLabel=form.querySelector('[data-in-ref] .db-field>span');
 if(refLabel)refLabel.textContent=({pharmacy_receipt:'Receipt / order paper number',purchase_receipt:'Purchase receipt number',external_transfer_in:'External transfer order number',internal_return:'Original department order number'})[route];
 const container=form.querySelector('#receiptLines');const wasReturn=container?.dataset.returnMode==='1';const isReturn=route==='internal_return';
 if(container&&wasReturn!==isReturn){container.innerHTML=isReturn?issueLine(true):receiveLine();container.dataset.returnMode=isReturn?'1':'0';}
 const title=form.querySelector('.shipment-lines-title');if(title)title.textContent=isReturn?'Returned product batches':'Received product batches';
 window.HWLang?.apply();
}
function distribution(){const pending=cache.movements.filter(m=>m.route==='department_issue'&&m.paperwork_pending===1);
 return `${head('Prepare outgoing shipment','Select the receiving destination: hospital departments, another hospital / organization, or the Pharmacy Department.')}
${panel('تجهيز طلبية · Outgoing shipment',`<form id="issueForm" class="db-form">
<div class="dest-choice three-routes" role="group" aria-label="Outgoing route">
${shipmentChoice('route','department_issue','Hospital departments','Issue items to our departments',true)}
${shipmentChoice('route','external_transfer_out','External transfers','Send stock to another hospital or sector')}
${shipmentChoice('route','pharmacy_transfer_out','Transfer to Pharmacy Department','Fixed destination: Pharmacy Department')}
</div><div class="db-grid">
${routeField('out-department',departmentPicker('Receiving hospital department'))}
${routeField('out-external',field('Transfer destination name',inp('external_destination','Hospital / organization name','text','maxlength="180"')))}
${routeField('out-pharmacy',field('Transfer destination',`<input class="db-input" value="قسم الصيدلة" readonly>`))}
${routeField('out-pharmacist',field('Trusted pharmacist name',inp('trusted_pharmacist_name','Full name of authorized pharmacist','text','maxlength="160"')))}
${routeField('out-authorization',field('Authorization letter number — رقم كتاب التخويل',inp('authorization_ref','Authorization letter / decree number','text','maxlength="90"')))}
${routeField('out-ref',field('Order paper number',inp('paper_ref','Order / transfer number','text','maxlength="80" required')))}
${routeField('out-dispatch',field('Our dispatch paper number',inp('dispatch_ref','Dispatch paper number','text','maxlength="80" required')))}
${routeField('out-emergency',`<label class="emergency-check"><input type="checkbox" name="emergency_pending" value="1"><span><strong>Emergency issue — paperwork will be completed later</strong><small>تجهيز طارئ بدون أرقام أوراق حالياً؛ يجب إكمال رقم الطلبية ورقم ورقة التجهيز لاحقاً</small></span></label>`)}
${field('Notes (optional)',`<textarea name="notes" class="db-textarea" placeholder="Transfer / emergency details"></textarea>`)}
</div><h3 class="shipment-lines-title">Products and available batches</h3>
<div class="db-help" data-fefo-summary role="status">FEFO: Earliest expiring usable lot is recommended first.</div>
<div id="issueLines">${issueLine(false)}</div>
<div class="fefo-override" data-fefo-override-wrap hidden>${field('FEFO exception reason (required when issuing a later-expiring lot)',`<textarea class="db-textarea" name="fefo_override_reason" maxlength="250" placeholder="Explain why earlier-expiring available stock is not being issued"></textarea>`)}</div>
<p class="db-help">Lots are sorted by earliest usable expiry. A later-expiring lot requires a recorded exception reason if an earlier-expiring lot still has stock. Expired lots cannot be issued.</p>
<div class="db-actions"><button type="button" class="db-btn secondary" data-add="issue">+ Add another batch</button><button type="submit" class="db-btn">${I('outgoing')} Save outgoing shipment</button></div></form>
<div class="db-note warn" style="margin-top:14px">Emergency paperwork is restricted to department distributions. It does not bypass stock, branch, batch, or expiry checks.</div>`,'outgoing')}
${pending.length?panel('Emergency shipments awaiting documents',table(['Movement','Type','Paper refs','Source / destination','Item lines','Operator'],movementRows(pending)),'history'):''}`}
function syncOutgoingDestination(form){
 if(!form)return;
 const route=form.querySelector('input[name="route"]:checked')?.value||'department_issue';
 const department=route==='department_issue', external=route==='external_transfer_out',pharmacy=route==='pharmacy_transfer_out';
 const show={'out-department':department,'out-external':external,'out-pharmacy':pharmacy,'out-pharmacist':!department,'out-authorization':!department,
            'out-ref':true,'out-dispatch':department,'out-emergency':department};
 for(const [key,yes] of Object.entries(show)){
  const el=form.querySelector(`[data-${key}]`);if(!el)continue;el.hidden=!yes;
  el.querySelectorAll('input,select,textarea').forEach(field=>{if(!field.readOnly)field.disabled=!yes});
 }
 const emergency=form.querySelector('[name="emergency_pending"]');
 if(emergency&&!department)emergency.checked=false;
 const pending=department&&!!emergency?.checked;
 const ref=form.querySelector('[name="paper_ref"]'),dispatch=form.querySelector('[name="dispatch_ref"]');
 if(ref)ref.required=!pending;if(dispatch)dispatch.required=department&&!pending;
 const refLabel=form.querySelector('[data-out-ref] .db-field>span');
 if(refLabel)refLabel.textContent=department?'Order paper number':'Transfer order number';
 const dept=form.querySelector('[name="department_id"]'),dest=form.querySelector('[name="external_destination"]'),pharm=form.querySelector('[name="trusted_pharmacist_name"]'),auth=form.querySelector('[name="authorization_ref"]');
 if(dept)dept.required=department;
 if(dest)dest.required=external;
 if(pharm)pharm.required=!department;
 if(auth)auth.required=!department;
 window.HWLang?.apply();
}

function returns(){return `${head('Stock adjustments','Department returns are recorded only under Receive Shipments → Internal department return. This tab is for audited stocktaking corrections.')}
${can('adjust')?panel('Manager-only stock correction',`<form id="adjustForm" class="db-form"><div class="db-grid">${field('Correction type',`<select class="db-select" name="kind"><option value="ADJUST_PLUS">Increase available stock</option><option value="ADJUST_MINUS">Decrease available stock</option></select>`)}${field('Reference / reason code',inp('paper_ref','e.g. COUNT-2026-003','text','required'))}${field('Detailed reason',`<textarea class="db-textarea" name="notes" required placeholder="Why was this correction needed?"></textarea>`)}</div><div id="adjustLines">${issueLine(true)}</div><div class="db-actions"><button class="db-btn" type="submit">Record correction with audit trail</button></div></form>`,'warning'):msg('Read-only','Only managers and administrators with branch permissions can adjust stock.')}`}
function users(){if(!can('users'))return msg('Access denied','Only administrators manage staff accounts.');const rows=cache.users.map(x=>`<tr><td><strong>${E(x.username)}</strong><div class="tiny">${E(x.full_name)}</div></td><td>${badge(x.role,x.role==='admin'?'blue':'neutral')}</td><td>${E(x.role==='admin'?'All branches':branchName(x.branch))}</td><td>${badge(x.is_active?'Active':'Disabled',x.is_active?'':'danger')}</td><td><button type="button" class="db-btn secondary small" data-user-details="${x.id}">عرض البيانات · Details</button></td><td>${x.id!==user.id?`<div class="db-small-actions"><button data-edit-user="${x.id}">Role / status</button><button data-reset-user="${x.id}">Reset password</button></div>`:'Current account'}</td></tr>`);
return `${head('Users and permissions','Only administrators can create staff accounts. Rights are checked by the backend on every action.',`<button class="db-btn" data-new="user">${I('users')} Create account</button>`)}<div class="db-note">Administrators manage all branches. Managers can edit items and correct stock only in their assigned branch. Operators can receive and distribute stock only in their branch. Viewers are read-only. Each non-admin account must have one assigned branch.</div>${panel('Warehouse accounts',table(['Username / name','Role','Assigned branch','Status','Profile details','Actions'],rows),'users')}`}
function backup(){return `${head('Database backup and restore','Administrators can export and restore the database, and manage encrypted Google Drive backups.')}
<div class="db-layout">${panel('Download full backup',`<p class="muted-hint" style="margin-bottom:16px">Includes users, departments, items, batches, requisition references, all movements and audit records. Creates a restorable ZIP with a SQLite snapshot and SHA-256 manifest.</p><button type="button" class="db-btn" id="downloadBackup">${I('download')} Download full database backup</button>`,'backup')}${panel('Restore previously exported backup',`<p class="muted-hint" style="margin-bottom:15px">This replaces ALL current records with the uploaded snapshot. A local safety copy is saved first.</p><form id="restoreForm" class="db-form">${field('Upload warehouse backup ZIP',`<input name="backup" type="file" class="db-input" accept=".zip" required>`)}${field('Type RESTORE to confirm',inp('confirmation','RESTORE','text','required autocomplete="off"'))}<button class="db-btn danger" type="submit">${I('upload')} Validate and restore backup</button></form>`,'backup')}</div>
${panel('Google Drive — automatic encrypted backups',`<div class="gdrive-backup" id="googleDriveStatus" aria-live="polite"><span class="muted-hint">Checking Google Drive connection…</span></div><div class="gdrive-backup-actions"><button type="button" class="db-btn" id="gdriveConnect">${I('backup')} Connect Google Drive</button><button type="button" class="db-btn secondary" id="gdriveRunNow" disabled>${I('upload')} Back up now</button><button type="button" class="db-btn secondary" id="gdriveRefresh">Refresh status</button><button type="button" class="db-btn secondary" id="gdriveBrowse">Browse Drive backups</button><button type="button" class="db-btn secondary" id="gdriveDisconnect" disabled>Disconnect</button></div><div id="gdriveBackups"></div><div class="db-note">Automatic: 10:00 AM and 2:00 PM Baghdad time, once the Railway Cron service is configured. Google Drive files are encrypted; the decryption key must be stored securely outside Railway too. Restore is manual and administrator-only.</div>`,'backup')}
<div class="db-note warn">Before restoring, download and verify a recent backup. Never paste OAuth tokens or the encryption key into the website, chat, or GitHub. Google Drive backups are independent of the Railway volume.</div>`}

function reports(){const low=cache.items.filter(x=>x.active&&x.min_stock>0&&x.stock<x.min_stock);const dist=cache.movements.filter(x=>x.kind==='OUT');const total=dist.length;
return `${head('Warehouse reports','Basic live summaries derived from your saved records. Spreadsheet and PDF reports can be added after we finalize the workflow.')}
<div class="db-kpis"><div class="db-kpi"><span class="name">${I('package')} Products</span><span class="num">${N(cache.items.length)}</span></div><div class="db-kpi"><span class="name">${I('warning')} Low stock</span><span class="num">${N(low.length)}</span></div><div class="db-kpi"><span class="name">${I('outgoing')} Distribution slips</span><span class="num">${N(total)}</span></div><div class="db-kpi"><span class="name">${I('history')} Total transactions</span><span class="num">${N(cache.movements.length)}</span></div></div>
${panel('Low-stock products',table(['SKU','Item','Current units','Minimum threshold'],low.map(x=>`<tr><td>${E(x.sku)}</td><td>${E(x.name)}</td><td>${N(x.stock)} ${E(x.unit)}</td><td>${N(x.min_stock)}</td></tr>`)),'warning')}`}
// V4.12 — read-only warehouse statements with editable thresholds and expiry cutoff.
let statementMode='missing';
function warehouseStatements(){
 const info=cache.positions||{missing:[],near_expiry:[],scarce:[],surplus:[],expired_lot_count:0,as_of:'',expiry_last_included:''};
 const ar=window.HWLang?.get()!=='en';
 const isMissing=statementMode==='missing',isExpiry=statementMode==='near_expiry',isPercent=!isMissing&&!isExpiry;
 const threshold=statementMode==='scarce'?statementScarcePct:statementSurplusPct;
 const options=[
 {key:'scarce',name:'Scarce materials',icon:'warning',desc:`${N(info.scarce?.length||0)} items below ${statementScarcePct}% of monthly need`},
 {key:'missing',name:'Missing materials',icon:'package',desc:`${N(info.missing.length)} items with no stock`},
 {key:'surplus',name:'Surplus materials',icon:'packages',desc:`${N(info.surplus?.length||0)} items above ${statementSurplusPct}% of monthly need`},
 {key:'near_expiry',name:'Materials nearing expiry',icon:'calendar',desc:`${N(info.near_expiry.length)} expiring lots before ${info.expiry_before||'—'}`}
 ];
 const cards=options.map(o=>`<button type="button" class="statement-card ${o.key===statementMode?'chosen':''}" data-statement="${o.key}"><span class="statement-card-icon">${I(o.icon)}</span><strong>${E(o.name)}</strong><span>${E(o.desc)}</span><small class="statement-open">View statement</small></button>`).join('');
 const heading={scarce:'Scarce materials',surplus:'Surplus materials',missing:'Missing materials',near_expiry:'Materials nearing expiry'}[statementMode];
 const explanation=isMissing?'Registered items without any warehouse stock, including those never received.':isExpiry?
 `Available lots expiring from ${info.as_of||'—'} through ${info.expiry_last_included||'—'}. Expand items to inspect all other lots.`:
 'Monthly requirement = annual requirement ÷ 12. Only usable, dated, unexpired lots count toward the stock percentage.';
 const expiryControl=isExpiry?`<div class="statement-param-row"><label class="db-field statement-control"><span>Expiry before (exclusive)</span><input class="db-input" type="date" id="statementExpiryBefore" value="${E(info.expiry_before||'')}" min="1900-01-01" max="2200-12-31" required></label><button type="button" class="db-btn secondary small" data-reset-statement-expiry>Use default expiry period</button><span class="muted-hint">The selected cutoff date is excluded.</span></div>`:'';
 const percentControl=isPercent?`<div class="statement-param-row"><label class="db-field statement-control"><span>Monthly requirement threshold (%)</span><input id="statementPercentInput" class="db-input" inputmode="decimal" type="number" min="0.01" max="1000" step="0.01" placeholder="Enter custom percentage" value="${E(threshold)}"></label><button type="button" class="db-btn small" data-apply-statement-percent>Calculate statement</button><button type="button" class="db-btn secondary small" data-reset-statement-percent>Use default percentage</button><span class="muted-hint">Monthly need = annual need ÷ 12. Scarce: below ${E(statementMode==='scarce'?threshold:DEFAULT_SCARCE_PERCENT)}%. Surplus: above ${E(statementMode==='surplus'?threshold:DEFAULT_SURPLUS_PERCENT)}%.</span></div>`:'';
 const records=info[statementMode]||[],unique=new Set(records.map(r=>r.item_id)).size;
 return `${head('Warehouse Statements','Detailed reports with configurable columns; expand any item for all its batches, expiry dates, prices and movements.')}
 <div class="statement-grid">${cards}</div><div class="db-panel statement-results">
 <div class="statement-result-head"><div><h2>${I(isMissing?'package':isExpiry?'calendar':'warning')} ${E(heading)}</h2><p class="muted-hint">${E(explanation)}</p></div><span class="statement-count">${N(unique)}</span></div>
 ${expiryControl}${percentControl}
 ${isPercent?`<div class="db-note ${info.annual_need_unset_count>0?'warn':''}">${N(info.annual_need_unset_count||0)} items have no positive annual requirement; excluded from this report.</div>`:''}
 ${isExpiry&&info.expired_lot_count>0?`<div class="db-note warn">${N(info.expired_lot_count)} expired lots excluded from the near-expiry calculation (still visible when item is expanded).</div>`:''}
 <div class="db-toolbar statement-tools"><input class="db-input" type="search" id="statementSearch" placeholder="Search item, batch, book, alternate names..." aria-label="Search statement">
 <select class="db-select" id="statementBranch"><option value="">All branches</option>${BRANCHES.map(([id,name])=>`<option value="${E(id)}">${E(name)}</option>`).join('')}</select>
 <select class="db-select" id="statementBook">${filterBookOptions()}</select>
 <select class="db-select" id="statementSort"><option value="name" ${statementSort==='name'?'selected':''}>Sort: name</option><option value="expiry" ${statementSort==='expiry'?'selected':''}>Sort: earliest expiry</option><option value="stock_desc" ${statementSort==='stock_desc'?'selected':''}>Sort: most stock</option><option value="stock_asc" ${statementSort==='stock_asc'?'selected':''}>Sort: least stock</option></select>
 ${columnPicker('statements')}<span class="muted-hint" id="statementShown"></span></div>
 <div id="statementTable" aria-live="polite"></div></div>`;
}
function filterStatement(){
 const el=$('#statementTable');if(!el)return;
 const info=cache.positions||{missing:[],near_expiry:[],scarce:[],surplus:[]};
 const threshold=statementMode==='scarce'?statementScarcePct:statementSurplusPct;
 const data=info[statementMode]||[],q=normalizeItemSearch($('#statementSearch')?.value||'');
 const branch=$('#statementBranch')?.value||'',book=$('#statementBook')?.value||'';
 const sort=$('#statementSort')?.value||statementSort;statementSort=sort;
 const contexts={},matched=[];
 for(const row of data){const id=Number(row.item_id);if(!contexts[id])contexts[id]={matches:0,percent_of_need:null};
  if(statementMode==='near_expiry')contexts[id].matches++;
  if(row.percent_of_monthly_need!=null)contexts[id].percent_of_need=row.percent_of_monthly_need;
  if(!matched.includes(id))matched.push(id);
 }
 let rows=matched.map(itemById).filter(Boolean).filter(it=>
 (!branch||it.branch===branch)&&(!book||it.category===book)&&(!q||q.split(/\s+/).filter(Boolean).every(t=>rowSearchText(it).includes(t))));
 rows.sort((a,b)=>{const x=lotStats(a),y=lotStats(b);
  if(sort==='stock_desc')return y.physical-x.physical;
  if(sort==='stock_asc')return x.physical-y.physical;
  if(sort==='expiry')return (x.next||'9999').localeCompare(y.next||'9999');
  return (a.trade_name||a.name).localeCompare(b.trade_name||b.name);
 });
 el.innerHTML=detailsTable(rows,'statements',contexts);
 const count=$('#statementShown');if(count)count.textContent=`${N(rows.length)} of ${N(matched.length)} items · ${N(data.length)} matching records`;
 window.HWLang?.apply();
}
function settings(){if(user?.role!=='admin')return msg('Access denied','Only administrators can view audit logs.');return `${head('سجل التدقيق — Audit logs','Administrator-only log of application activity, account changes and stock operations.')}
${panel('سجل التدقيق — Operations audit trail',`<div id="auditLog">Loading events...</div>`,'history')}`}
const pages={overview,inventory,item_movement:itemMovements,profile:profilePage,warehouseStatements:warehouseStatements,positions:warehouseStatements,departments,batches,movements,receiving,distribution,returns,users,backup,reports,settings};
function showPage(next){
 if(next==='batches')next='inventory';
 if(!pages[next])next='overview';if((next==='users'&&!can('users'))||(next==='backup'&&!can('backup'))||(next==='settings'&&user.role!=='admin'))next='overview';
 closeColumnManager();view=next;$$('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===next);b.setAttribute('aria-current',b.dataset.view===next?'page':'false')});
 $('#topTitle').textContent=headers[next];$('#dashboardView').innerHTML=pages[next]();if(next==='positions')filterStatement();if(next==='inventory')filterInventory();if(next==='distribution'){syncOutgoingDestination($('#issueForm'));updateFefoNotices();}if(next==='receiving'){const f=$('#receiveForm');const lines=f?.querySelector('#receiptLines');if(lines)lines.dataset.returnMode='0';syncIncomingRoute(f)}window.HWLang?.apply();closeMenu();
 if(next==='settings'&&user?.role==='admin')loadAudit();if(next==='profile')loadProfile();if(next==='backup')loadGoogleDriveStatus();
 window.scrollTo({top:0,behavior:'instant'});
}
function route(next){location.hash=next;showPage(next)}
function closeMenu(){$('#sidebar').classList.remove('open');$('#dimOverlay').classList.remove('show')}
function modalOpen(title,description,fields,formType,button='Save changes'){
 const modal=$('#entityModal');modal.innerHTML=`<div class="modal-body ${formType.startsWith('item:')?'item-dialog':''}" role="dialog" aria-modal="true" aria-label="${E(title)}"><div class="db-actions" style="justify-content:space-between;align-items:center"><h2>${E(title)}</h2><button class="db-btn secondary small" type="button" data-close-modal>Close ×</button></div><p>${E(description)}</p><form id="entityForm" data-entity="${formType}" class="db-form"><div class="db-grid">${fields}</div><div class="modal-footer"><button class="db-btn secondary" type="button" data-close-modal>Cancel</button><button class="db-btn" type="submit">${E(button)}</button></div></form></div>`;
 modal.classList.add('open');modal.setAttribute('aria-hidden','false');syncUserBranchField($('#entityForm'));window.HWLang?.apply();$('.db-input',modal)?.focus();
}
function modalClose(){const el=$('#entityModal');el.classList.remove('open');el.innerHTML='';el.setAttribute('aria-hidden','true')}
function openingLotRow(index){
 return `<div class="opening-lot-row" data-opening-lot><div class="opening-lot-header"><strong>الوجبة ${N(index+1)} · Opening lot</strong><button class="db-btn secondary small" type="button" data-remove-opening-lot title="Remove this lot" ${index===0?'disabled':''}>Remove</button></div><div class="db-grid opening-balance-grid">
 ${field('Batch / lot number',`<input data-opening-key="batch_no" class="db-input" maxlength="90" placeholder="e.g. LOT-001" required>`)}
 ${field('Manufacture date (optional)',`<input data-opening-key="manufacture_date" class="db-input" type="date">`)}
 ${field('Expiration date',`<input data-opening-key="expiry_date" class="db-input" type="date" required>`)}
 ${field('Opening quantity',`<input data-opening-key="opening_qty" class="db-input" type="number" min="1" max="100000000" step="1" inputmode="numeric" required>`)}
 ${field('Price — دينار',`<input data-opening-key="price_dinars" class="db-input" type="number" min="0" max="999999999" step="1" required>`)}
 ${field('Price — فلس',`<input data-opening-key="price_fils_component" class="db-input" type="number" min="0" max="999" step="1" required>`)}
 </div></div>`;
}
function refreshOpeningLotNumbers(form){
 const rows=$$('[data-opening-lot]',form);
 rows.forEach((row,i)=>{row.querySelector('.opening-lot-header strong').textContent=`الوجبة ${N(i+1)} · Opening lot`;row.querySelector('[data-remove-opening-lot]').disabled=rows.length===1;});
}
function editItem(it=null){
 const b=it?.branch||user.branch||'';
 const legacyWarn=it?.category&&!approvedBook(it.branch,it.category)?`<small class="legacy-book-warning">Existing category: ${E(it.category)} — please choose an approved book for this branch.</small>`:'';
 const wide=s=>s.replace('class="db-field"','class="db-field wide"');
 const f=[
  wide(field('Warehouse branch',branchField('branch',b,user.role==='admin'), 'Choose your assigned warehouse branch first.')),
  field('Trade name',`<input name="trade_name" class="db-input" maxlength="160" value="${E(it?.trade_name||'')}" placeholder="Commercial or brand name">`).replace('class="db-field"','class="db-field" data-med-trade'),
  field('Scientific name',`<input name="name" class="db-input" maxlength="160" value="${E(it?.name||'')}" placeholder="Scientific / active ingredient name">`).replace('class="db-field"','class="db-field" data-med-scientific'),
  wide(field('Item name',`<input name="name" class="db-input" maxlength="160" value="${E(it?.name||'')}" placeholder="Name of the supply / instrument">`)).replace('class="db-field wide"','class="db-field wide" data-other-name'),
  field('Stock unit',`<select name="unit" class="db-select" data-item-unit required>${unitOptions(b,it?.unit||'')}</select>`),
  field('Book / register category',`<select name="category" class="db-select" data-item-book required>${optionsForBooks(b,it?.category||'')}</select>${legacyWarn}`),
  ...(it?[field('Manufacture date (reference)',`<input name="manufacture_date" class="db-input" type="date" value="${E(it?.manufacture_date||'')}">`)]:[]),
  field('Manufacturer company',`<input name="manufacturer" class="db-input" maxlength="160" value="${E(it?.manufacturer||'')}" placeholder="Company name">`),
  wide(field('Annual requirement quantity',`<input name="annual_need" class="db-input" type="number" min="0" max="1000000000" step="1" inputmode="numeric" value="${it?.annual_need==null?'':E(it.annual_need)}" placeholder="${window.HWLang?.get()==='ar'?'الاحتياج خلال سنة كاملة':'Yearly quantity in stock units'}">`, 'Optional. Used for scarce and surplus reports.')),
  wide(field('Information / alternate names',`<textarea name="information" class="db-textarea" maxlength="2000" rows="4" placeholder="Common names, Iraqi slang, abbreviations, alternate spellings...">${E(it?.information||'')}</textarea>`, 'All alternate names are searchable.'))
 ];
 if(it){
  // These are historical catalog reference values only. Editing them never
  // changes stock or price on saved lots. Opening stock is create-only.
  f.push(field('Reference batch (optional)',`<input name="batch_no" class="db-input" maxlength="90" value="${E(it.initial_batch_no||it.display_batch_no||'')}">`));
  f.push(field('Reference expiry (optional)',`<input name="expiry_date" class="db-input" type="date" value="${E(it.expiry_date||'')}">`));
  f.push(field('Reference price — دينار',`<input name="price_dinars" class="db-input" type="number" min="0" max="999999999" step="1" value="${it.price_fils==null?'':Math.floor(it.price_fils/1000)}">`));
  f.push(field('Reference price — فلس',`<input name="price_fils_component" class="db-input" type="number" min="0" max="999" step="1" value="${it.price_fils==null?'':it.price_fils%1000}">`));
  f.push(wide(field('Active status',`<select class="db-select" name="active"><option value="1" ${it.active?'selected':''}>Active</option><option value="0" ${!it.active?'selected':''}>Inactive</option></select>`)));
 }else{
  f.push(`<div class="db-field wide opening-balance-choice"><label class="opening-balance-label"><input type="checkbox" name="opening_balance" value="1" data-opening-balance><span>Opening balance</span></label><small>Tick only for stock already physically in the warehouse. The opening quantity will be recorded once in movement history.</small></div>`);
  f.push(`<div class="opening-balance-fields wide" data-opening-fields hidden>
    <div class="opening-balance-heading">Opening stock — multiple batches</div>
    <div id="openingLotRows">${openingLotRow(0)}</div>
    <button type="button" class="db-btn secondary small" data-add-opening-lot>+ Add another batch</button>
    <small class="opening-balance-hint">Enter each stored lot separately. The opening balance is recorded as one audited transaction; individual batch numbers, manufacturing dates, expiry dates, quantities and prices remain separate.</small>
   </div>`);
 }
 modalOpen(it?'Edit item':'Register item',it?'Edit the registered details without changing historical received or opening quantities.':'Register an item without stock, or tick رصيد افتتاحي to record existing physical stock in one step.',f.join(''),`item:${it?.id||'new'}`);
 const form=$('#entityForm');form.classList.add('item-form-grid');
 form.dataset.originalBranch=it?.branch||'';form.dataset.originalUnit=it?.unit||'';
 const dlg=form.closest('.modal-body');
 dlg.querySelector('h2')?.insertAdjacentHTML('beforeend',' <span class="form-version" translate="no">V4.18</span>');
 syncItemBranchFields(form,it?.category||'',it?.unit||'');
 syncOpeningBalanceFields(form);
 window.HWLang?.apply();
}
function syncOpeningBalanceFields(form){
 if(!form?.dataset.entity || form.dataset.entity!=='item:new')return;
 const checkbox=form.querySelector('[data-opening-balance]'),wrap=form.querySelector('[data-opening-fields]');
 if(!checkbox||!wrap)return;
 const on=checkbox.checked;
 wrap.hidden=!on;
 wrap.querySelectorAll('input').forEach(el=>{el.disabled=!on;el.required=on && el.dataset.openingKey!=='manufacture_date';});
}
function syncItemBranchFields(form, previousBook='', previousUnit=''){
 if(!form?.dataset.entity?.startsWith('item:'))return;
 const branch=form.querySelector('select[name="branch"]')?.value || form.querySelector('input[name="branch"]')?.value || '';
 const book=form.querySelector('[data-item-book]');
 if(book){const choice=previousBook||book.value;book.innerHTML=optionsForBooks(branch,choice);book.value=approvedBook(branch,choice)?choice:'';book.disabled=!branch;}
 const units=form.querySelector('[data-item-unit]');
 if(units){const previous=previousUnit||units.value;
  const allowLegacy=!!(form.dataset.originalBranch===branch && form.dataset.originalUnit===previous && previous);
  units.innerHTML=unitOptions(branch,previous,allowLegacy);
  units.value=(unitsFor(branch).includes(previous)||allowLegacy)?previous:'';units.disabled=!branch;}
 const medication=branch==='medication';
 for(const [selector,visible] of [['[data-med-trade]',medication],['[data-med-scientific]',medication],['[data-other-name]',!!branch&&!medication]]){
  const container=form.querySelector(selector);if(!container)continue;
  container.hidden=!visible;
  const input=container.querySelector('input');if(input){input.disabled=!visible;input.required=visible;}
 }
 // Editing a form never changes saved stock, batches, or movement history.
 // Keep disabled inputs out of the submitted JSON to avoid duplicate names.
 form.dataset.branch=branch;
 window.HWLang?.apply();
}
function reloadShipmentDropdowns(){
 $$('[data-receive-line] select[data-key="item_id"]').forEach(sel=>{const saved=sel.value;sel.innerHTML=itemOptions();sel.value=saved;});
 $$('[data-issue-line]').forEach(line=>{
  const item= line.querySelector('[data-issue-product]');
  if(item){const selected=item.value;item.innerHTML=itemOptions();item.value=selected;syncIssueProduct(line);}
  else{const sel=line.querySelector('[data-key="batch_id"]');const saved=sel.value;sel.innerHTML=batchOptions(true);sel.value=saved;}
 });
 window.HWLang?.apply();
}
function quickReceiptForNewItem(itemId, ctx){
 const item=cache.items.find(i=>i.id===itemId);
 if(!item){toast('New item not found. Please reload.','error');return}
 modalOpen('Register stock before shipment',
 'This new item has zero stock. If the warehouse has physically received it, enter its incoming receipt details now. Otherwise cancel and receive it later.',
 field('New registered item',`<input class="db-input" value="${E(item.trade_name||item.name)}" disabled>`)+
 field('Batch number',`<input class="db-input" name="batch_no" value="${E(item.initial_batch_no)}" required>`)+
 field('Expiration date',`<input class="db-input" name="expiry_date" type="date" value="${E(item.expiry_date||'')}" required>`)+
 field('Received quantity',`<input class="db-input" name="qty" type="number" min="1" step="1" required>`)+
 field('Price — دينار',`<input class="db-input" name="price_dinars" type="number" min="0" max="999999999" step="1" required value="${item.price_fils==null?'':Math.floor(item.price_fils/1000)}">`)+
 field('Price — فلس',`<input class="db-input" name="price_fils_component" type="number" min="0" max="999" step="1" required value="${item.price_fils==null?'':item.price_fils%1000}">`)+
 field('Incoming receipt paper number',`<input class="db-input" name="paper_ref" maxlength="80" required>`)+
 field('Received from / supplier',`<input class="db-input" name="source" maxlength="140" required>`),
 `quickreceipt:${itemId}`,'Record receipt & select batch');
 inlineNewItem=ctx;
}
function editDept(it=null){modalOpen(it?'Edit department':'Add department','Departments are distribution destinations, not separate inventory locations.',
 field('Department name',`<input name="name" class="db-input" required value="${E(it?.name||'')}" placeholder="Emergency Department">`)+(it?field('Status',`<select class="db-select" name="active"><option value="1" ${it.active?'selected':''}>Active</option><option value="0" ${!it.active?'selected':''}>Inactive</option></select>`):''),
 `department:${it?.id||'new'}`)}
function createUser(){modalOpen('Create staff account','Choose exactly one warehouse branch per employee. Administrators are the exception and can access all branches.',
 field('Username',inp('username','e.g. warehouse01','text','required minlength="3" pattern="[a-zA-Z0-9_.-]+"'))+
 field('Full name',inp('full_name','Employee full name','text','required'))+
 field('Temporary password (8+ characters)',inp('password','At least 8 characters','password','required minlength="8"'))+
 field('Role',`<select class="db-select" name="role" data-user-role><option value="viewer">Viewer — Read only</option><option value="operator">Operator — Stock movements</option><option value="manager">Manager — Inventory management</option><option value="admin">Administrator — Full access</option></select>`)+
 field('Assigned branch',`<select class="db-select" name="branch" data-user-branch required>${branchList('')}</select>`, 'Required for staff accounts. Administrators automatically have access to all branches.'),
 'user:new','Create user')}
function editUser(it){modalOpen('Edit account: '+it.username,'Change the role, branch or status. Changing a branch signs the employee out immediately.',
 field('Role',`<select name="role" class="db-select" data-user-role>${['admin','manager','operator','viewer'].map(x=>`<option value="${x}" ${it.role===x?'selected':''}>${x}</option>`).join('')}</select>`)+
 field('Assigned branch',`<select name="branch" class="db-select" data-user-branch>${branchList(it.branch||'')}</select>`, 'One branch per staff account. Administrators have access to all branches.')+
 field('Account status',`<select name="is_active" class="db-select"><option value="1" ${it.is_active?'selected':''}>Active</option><option value="0" ${!it.is_active?'selected':''}>Disabled</option></select>`),`user:${it.id}`,'Update account')}
function resetUser(it){modalOpen('Reset password: '+it.username,'This resets the password and signs out the employee from any active session.',
 field('New temporary password (8+ characters)',inp('password','','password','required minlength="8"')),
 `reset:${it.id}`,'Reset password')}
function extractLines(container,type){return $$(`[data-${type}-line]`,container).map(el=>{
  let line={};$$('[data-key]',el).forEach(n=>line[n.dataset.key]=n.value.trim());return line;
})}
async function submitEntity(form){const type=form.dataset.entity, [entity,id]=type.split(':');const d=Object.fromEntries(new FormData(form).entries());
 if(entity==='paperwork'){
  const r=await api('/api/movements/'+id+'/paperwork',{method:'PATCH',data:{paper_ref:d.paper_ref,dispatch_ref:d.dispatch_ref}});
  modalClose();await refreshData();showPage(view);toast('Emergency paperwork completed for '+r.code);return;
 }
 if(entity==='quickreceipt'){
  const ctx=inlineNewItem;
  const r=await api('/api/movements',{method:'POST',data:{kind:'IN',route:'purchase_receipt',paper_ref:d.paper_ref,source:d.source,lines:[{item_id:Number(id),batch_no:d.batch_no,expiry_date:d.expiry_date,qty:d.qty,price_dinars:d.price_dinars,price_fils_component:d.price_fils_component}]}});
  modalClose();await refreshData();reloadShipmentDropdowns();
  if(ctx?.line?.isConnected){
   const b=cache.batches.find(x=>x.item_id===Number(id)&&x.batch_no===d.batch_no&&x.expiry_date===d.expiry_date&&x.unit_price_fils===Number(d.price_dinars)*1000+Number(d.price_fils_component)&&x.on_hand>0);
   if(b){const product=ctx.line.querySelector('[data-issue-product]');if(product){product.value=String(id);syncIssueProduct(ctx.line,b.id)}else{const select=ctx.line.querySelector('select[data-key="batch_id"]');if(select)select.value=String(b.id)}}
  }
  inlineNewItem=null;
  toast(`Incoming receipt ${r.code} saved. New batch selected for distribution.`);
  return;
 }
 let createdItem=null;
 if(entity==='item' && id==='new' && form.querySelector('[data-opening-balance]')?.checked){
  d.opening_lots=$$('[data-opening-lot]',form).map(row=>{
   const lot={};$$('[data-opening-key]',row).forEach(input=>lot[input.dataset.openingKey]=input.value.trim());return lot;
  });
 }
 if(entity==='item'){if(id!=='new')d.active=d.active==='1';createdItem=await api(id==='new'?'/api/items':'/api/items/'+id,{method:id==='new'?'POST':'PATCH',data:d})}
 else if(entity==='department'){if(id!=='new')d.active=d.active==='1';await api(id==='new'?'/api/departments':'/api/departments/'+id,{method:id==='new'?'POST':'PATCH',data:d})}
 else if(entity==='user'){if(id!=='new')d.is_active=d.is_active==='1';await api(id==='new'?'/api/users':'/api/users/'+id,{method:id==='new'?'POST':'PATCH',data:d})}
 else if(entity==='reset'){await api('/api/users/'+id+'/reset-password',{method:'POST',data:d})}
 const ctx=entity==='item'&&id==='new'?inlineNewItem:null;
 modalClose();await refreshData();
 if(ctx?.line?.isConnected){
  reloadShipmentDropdowns();
  if(ctx.mode==='receive'){
   const sel=ctx.line.querySelector('select[data-key="item_id"]');if(sel)sel.value=String(createdItem.id);
   const batch=ctx.line.querySelector('[data-key="batch_no"]');if(batch&&d.batch_no)batch.value=d.batch_no;
   const expiry=ctx.line.querySelector('[data-key="expiry_date"]');if(expiry&&d.expiry_date)expiry.value=d.expiry_date;
   prefillReceiptPrice(ctx.line);
   inlineNewItem=null;toast('Item registered. Add its received quantity to the shipment.');
  }else if(ctx.mode==='issue'){
   const product=ctx.line.querySelector('[data-issue-product]');
   if(product){product.value=String(createdItem.id);syncIssueProduct(ctx.line,createdItem.opening_batch_id||undefined);}
   if(createdItem.opening_batch_id){inlineNewItem=null;toast('Opening balance recorded. The new batch is available for shipment.');}
   else{quickReceiptForNewItem(createdItem.id,ctx);toast('Item registered with zero stock. Record an incoming receipt to issue it.');}
  }
 }else{inlineNewItem=null;showPage(view);toast('Saved successfully in the database')}
}
async function postShipment(kind,form,lines){
 const obj=Object.fromEntries(new FormData(form).entries());
 const route=obj.route||(kind==='RETURN'?'internal_return':null);
 const resolved=kind==='IN'&&route==='internal_return'?'RETURN':kind;
 const payload={kind:resolved,route,paper_ref:obj.paper_ref||'',dispatch_ref:obj.dispatch_ref||'',
  source:obj.source||'',notes:obj.notes||'',lines};
 if(resolved==='RETURN'){payload.department_id=Number(obj.department_id);if(!payload.department_id)throw Error('Choose a department from the list.')}
 if(resolved==='OUT'){
  payload.fefo_override_reason=obj.fefo_override_reason||'';
  payload.emergency_pending=obj.emergency_pending==='1';
  if(route==='department_issue'){payload.department_id=Number(obj.department_id);if(!payload.department_id)throw Error('Choose a department from the list.')}
  if(route==='external_transfer_out')payload.external_destination=obj.external_destination||'';
  if(route!=='department_issue'){payload.trusted_pharmacist_name=obj.trusted_pharmacist_name||'';payload.authorization_ref=obj.authorization_ref||'';}
 }
 if(resolved==='IN'&&route==='external_transfer_in'){payload.trusted_pharmacist_name=obj.trusted_pharmacist_name||'';payload.authorization_ref=obj.authorization_ref||'';}
 const r=await api('/api/movements',{method:'POST',data:payload});
 await refreshData();routeToMovements();toast(`Saved ${r.code}. Warehouse balance updated.${r.paperwork_pending?' Paperwork is pending.':''}`);
}
function routeToMovements(){route('movements')}

async function loadAudit(){try{const a=await api('/api/audit');if(view!=='settings')return;$('#auditLog').innerHTML=table(['Date / time','Action','Operator','Detail'],a.map(x=>`<tr><td>${D(x.created_at)}</td><td>${E(x.action)}</td><td>${E(x.username||'System')}</td><td><span class="tiny">${E(x.detail).slice(0,220)}</span></td></tr>`))}catch(e){if($('#auditLog'))$('#auditLog').textContent=e.message}}
// Google Drive account, schedule, and backup history are admin-only. No keys or
// refresh tokens are ever sent to the browser.
async function loadGoogleDriveStatus(){
 const el=$('#googleDriveStatus'),list=$('#gdriveBackups');if(!el||view!=='backup')return;
 try{
  const d=await api('/api/gdrive/status');
  const status=d.connected?'متصل بـ Google Drive · Connected':d.configured?'غير متصل · Not connected':'Requires Railway credentials';
  el.innerHTML=`<div class="gdrive-status-head"><strong>${E(status)}</strong><span class="gdrive-state ${d.connected?'connected':'disconnected'}">${d.connected?'● Connected':'○ Not connected'}</span></div>
  <div class="gdrive-summary"><span>جدول النسخ: <strong>${E(d.schedule||'10:00 and 14:00 Asia/Baghdad')}</strong></span><span>آخر نسخة ناجحة: <strong>${E(d.last_success_utc?fmtDate(d.last_success_utc):'—')}</strong></span><span>آخر ملف: <strong>${E(d.last_file_name||'—')}</strong></span><span>نسخ اليوم: <strong>${E((d.completed_today||[]).join(', ')||'—')}</strong></span></div>
  ${d.last_error?`<p class="gdrive-error">آخر خطأ: ${E(d.last_error)}</p>`:''}
  ${d.root_folder_id?`<a href="https://drive.google.com/drive/u/0/folders/${encodeURIComponent(d.root_folder_id)}" target="_blank" rel="noopener noreferrer">Open IMS_SECURE_BACKUPS folder in Google Drive</a>`:''}`;
  $('#gdriveConnect').disabled=!d.configured;
  $('#gdriveRunNow').disabled=!d.connected;
  $('#gdriveDisconnect').disabled=!d.connected;
  list.innerHTML=`<h3>Recent Google Drive backups</h3>${(d.recent||[]).length?`<div class="gdrive-files">${d.recent.map(f=>`<div class="gdrive-file"><span>${E(f.name)}<small>${E(f.created_utc||'')}</small></span><a class="db-btn secondary small" href="/api/gdrive/download/${encodeURIComponent(f.id)}">Download restorable ZIP</a></div>`).join('')}</div>`:'<p class="muted-hint">No Google Drive backups created by this app yet.</p>'}`;
  window.HWLang?.apply();
 }catch(e){el.innerHTML=`<p class="gdrive-error">${E(e.message)}</p>`}
}
async function browseGoogleDriveBackups(){
 const listing=$('#gdriveBackups');if(!listing)return;
 listing.innerHTML='<p class="muted-hint">Loading Drive backups…</p>';
 try{
  const files=await api('/api/gdrive/files');
  listing.innerHTML=`<h3>Google Drive backups (${N(files.length)})</h3>${files.length?`<div class="gdrive-files">${files.map(f=>`<div class="gdrive-file"><span>${E(f.name)}<small>${E(f.created_utc||'')}</small></span><a class="db-btn secondary small" href="/api/gdrive/download/${encodeURIComponent(f.id)}">Download restorable ZIP</a></div>`).join('')}</div>`:'<p class="muted-hint">No IMS backups found in this connected Google Drive account.</p>'}`;
  window.HWLang?.apply();
 }catch(err){listing.innerHTML=`<p class="gdrive-error">${E(err.message)}</p>`}
}
async function beginGDriveConnection(){
 const r=await api('/api/gdrive/connect',{method:'POST'});
 if(!r.url||!r.url.startsWith('https://accounts.google.com/'))throw Error('Invalid Google authorization URL');
 location.assign(r.url);
}
async function runGDriveNow(){
 if(!window.confirm('Create an encrypted Google Drive backup now?'))return;
 const b=$('#gdriveRunNow');b.disabled=true;
 try{const result=await api('/api/gdrive/backup-now',{method:'POST'});
  toast(result.ok?'Encrypted backup uploaded to Google Drive':'Google Drive backup was not completed');await loadGoogleDriveStatus();
 }finally{if(document.body.contains(b))b.disabled=false}
}
async function disconnectGDrive(){
 if(!window.confirm('Disconnect Google Drive? Already uploaded encrypted backups will remain there.'))return;
 await api('/api/gdrive/disconnect',{method:'POST',data:{confirmation:'DISCONNECT'}});
 toast('Google Drive disconnected');await loadGoogleDriveStatus();
}
async function downloadBackup(){try{
 const r=await api('/api/backup/export');const blob=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(blob);
 a.download=r.headers.get('content-disposition')?.match(/filename="([^"]+)"/)?.[1]||'warehouse_backup.zip';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),4000);toast('Backup downloaded. Store it in a secure location.');
}catch(e){toast(e.message,'error')}}
function completeMovementPapers(m){
 if(!m||!m.paperwork_pending)return;
 modalOpen('Complete emergency issue paperwork','The stock was deducted when this emergency shipment was issued. Enter both paper numbers to finish its documents; the original shipment is never deleted or reissued.',
  field('Order paper number',`<input class="db-input" name="paper_ref" maxlength="80" required value="${E(m.paper_ref||'')}">`)+
  field('Our dispatch paper number',`<input class="db-input" name="dispatch_ref" maxlength="80" required value="${E(m.dispatch_ref||'')}">`),
  `paperwork:${m.id}`,'Complete paperwork');
}
document.addEventListener('click',async e=>{
 const movementToggle=e.target.closest('[data-expand-movement]');if(movementToggle){toggleMovementDetails(movementToggle);return;}
 const v=e.target.closest('[data-view],[data-go]');if(v){route(v.dataset.view||v.dataset.go);return}
 const expand=e.target.closest('[data-expand-item]');if(expand){
  const id=Number(expand.dataset.expandItem),detail=document.querySelector(`[data-detail-row="${id}"]`);
  if(detail){
   const opening=detail.hidden;
   detail.hidden=!opening;
   if(opening){
    expandedItems.add(id);expandedFullInfo.delete(id);
    const it=itemById(id);
    if(it)detail.querySelector('td').innerHTML=fullItemPanel(it,lotStats(it));
   }else{expandedItems.delete(id);expandedFullInfo.delete(id);}
   $$(`[data-expand-item="${id}"]`).forEach(btn=>{btn.setAttribute('aria-expanded',String(opening));if(btn.classList.contains('expand-row-btn'))btn.textContent=opening?'▴':'▾';});
  }return;
 }
 const extra=e.target.closest('[data-toggle-item-extra]');if(extra){
  const id=Number(extra.dataset.toggleItemExtra),panel=document.getElementById(`item-extra-${id}`);
  if(panel){const opening=panel.hidden;panel.hidden=!opening;if(opening)expandedFullInfo.add(id);else expandedFullInfo.delete(id);extra.setAttribute('aria-expanded',String(opening));const arrow=extra.querySelector('.expanded-extra-chevron');if(arrow)arrow.textContent=opening?'▴':'▾';}return;
 }
 const colOpen=e.target.closest('[data-open-column-manager]');if(colOpen){openColumnManager(colOpen.dataset.openColumnManager);return;}
 if(e.target.closest('[data-close-column-manager]')){closeColumnManager();return;}
 if(e.target.closest('[data-column-all]')){columnChangeAll('all');return;}
 if(e.target.closest('[data-column-none]')){columnChangeAll('none');return;}
 if(e.target.closest('[data-column-default]')){columnChangeAll('default');return;}
 if(e.target.closest('[data-save-column-manager]')){saveColumnManager();return;}
 if(e.target.id==='columnManager'){closeColumnManager();return;}
 if(e.target.closest('[data-close-shipment-history]')||e.target.id==='movementDetailModal'){closeShipmentHistory();return;}
 const inspectItem=e.target.closest('[data-open-item-shipments]');if(inspectItem){await openShipmentHistory('item',Number(inspectItem.dataset.openItemShipments));return;}
 const inspectDept=e.target.closest('[data-open-dept-shipments]');if(inspectDept){await openShipmentHistory('department',Number(inspectDept.dataset.openDeptShipments));return;}
 const moreShipments=e.target.closest('[data-more-shipments]');if(moreShipments){await loadShipmentHistory(Number(moreShipments.dataset.moreShipments));return;}
 const history=e.target.closest('[data-load-item-history]');if(history){await loadItemHistory(Number(history.dataset.loadItemHistory),Number(history.dataset.historyOffset)||0);return;}
 const statement=e.target.closest('[data-statement]');if(statement){statementMode=statement.dataset.statement;showPage('positions');return}
 if(e.target.closest('[data-reset-statement-expiry]')){statementExpiryBefore='';try{await reloadPositions()}catch(err){toast(err.message,'error')}return;}
 if(e.target.closest('[data-apply-statement-percent]')){try{await applyStatementPercent()}catch(err){toast(err.message,'error')}return;}
 if(e.target.closest('[data-reset-statement-percent]')){const scarce=statementMode==='scarce';const old=scarce?statementScarcePct:statementSurplusPct;if(scarce)statementScarcePct=DEFAULT_SCARCE_PERCENT;else statementSurplusPct=DEFAULT_SURPLUS_PERCENT;try{await reloadPositions()}catch(err){if(scarce)statementScarcePct=old;else statementSurplusPct=old;toast(err.message,'error')}return;}
 const trigger=e.target.closest('[data-dept-trigger]');if(trigger){const picker=trigger.closest('[data-dept-picker]');if(picker.querySelector('[data-dept-popup]').hidden)openDepartmentPicker(picker);else closeDepartmentPicker(picker);return}
 const option=e.target.closest('[data-dept-option]');if(option){selectDepartment(option.closest('[data-dept-picker]'),option);return}
 if(!e.target.closest('[data-dept-picker]'))document.querySelectorAll('[data-dept-picker]').forEach(closeDepartmentPicker);
 const pending=e.target.closest('[data-complete-paperwork]');if(pending){completeMovementPapers(cache.movements.find(m=>m.id===Number(pending.dataset.completePaperwork)));return}
 const inline=e.target.closest('[data-inline-item]');
 if(inline){inlineNewItem={mode:inline.dataset.inlineItem,line:inline.closest('.ship-line')};editItem();return}
 const addOpening=e.target.closest('[data-add-opening-lot]');if(addOpening){
  const form=addOpening.closest('#entityForm'),rows=form?.querySelector('#openingLotRows');if(!rows)return;
  if(rows.children.length>=40){toast('Maximum 40 opening lots per registration','error');return;}
  rows.insertAdjacentHTML('beforeend',openingLotRow(rows.children.length));refreshOpeningLotNumbers(form);window.HWLang?.apply();return;
 }
 const removeOpening=e.target.closest('[data-remove-opening-lot]');if(removeOpening){
  const row=removeOpening.closest('[data-opening-lot]'),form=removeOpening.closest('#entityForm');
  if($$('[data-opening-lot]',form).length>1){row.remove();refreshOpeningLotNumbers(form)}return;
 }
 const n=e.target.closest('[data-new]');if(n){inlineNewItem=null;if(n.dataset.new==='item')editItem();if(n.dataset.new==='dept')editDept();if(n.dataset.new==='user')createUser();return}
 const item=e.target.closest('[data-edit-item]');if(item){editItem(cache.items.find(x=>x.id===Number(item.dataset.editItem)));return}
 const dep=e.target.closest('[data-edit-dept]');if(dep){editDept(cache.departments.find(x=>x.id===Number(dep.dataset.editDept)));return}
 const uu=e.target.closest('[data-edit-user]');if(uu){editUser(cache.users.find(x=>x.id===Number(uu.dataset.editUser)));return}
 const detail=e.target.closest('[data-user-details]');if(detail){try{const u=await api('/api/users/'+Number(detail.dataset.userDetails)+'/profile');modalOpen('بيانات الموظف — Staff profile','Read-only information supplied by this employee.',
 `<div class="staff-profile-details">${[['Username',u.username],['Full name',u.full_name],['Branch',u.branch||'All branches'],['Role',u.role],['Email',u.email],['Phone',u.phone],['Age',u.age],['Job title',u.job_title]].map(([name,value])=>`<div><span>${E(name)}</span><strong>${E(value??'—')}</strong></div>`).join('')}</div>`,'staff-readonly','Close');const readOnly=$('#entityForm');if(readOnly){readOnly.id='staffReadOnlyProfile';readOnly.querySelector('[type=submit]')?.remove();}}catch(err){toast(err.message,'error')}return;}
 const reset=e.target.closest('[data-reset-user]');if(reset){resetUser(cache.users.find(x=>x.id===Number(reset.dataset.resetUser)));return}
 if(e.target.closest('[data-close-notifications]')||e.target.id==='notificationModal'){closeNotifications();return;}
 const notifGo=e.target.closest('[data-notif-go]');if(notifGo){closeNotifications();route(notifGo.dataset.notifGo);return;}
 if(e.target.closest('[data-close-modal]')){if($('#entityForm')?.dataset.entity?.startsWith('quickreceipt:'))toast('Item saved, but it cannot be issued until incoming stock is recorded.','error');modalClose();inlineNewItem=null;return}
 const priority=e.target.closest('[data-fefo-pick]');if(priority){const line=priority.closest('[data-issue-line]');const select=line?.querySelector('[data-issue-batch]');if(select){const preferred=Number(priority.dataset.fefoPick);const lot=cache.batches.find(b=>b.id===preferred);const expiry=line.querySelector('[data-issue-expiry-picker]');if(expiry)expiry.value=lot?.expiry_date||'unknown';syncIssueExpiry(line,preferred);}return;}
 if(e.target.closest('[data-remove-line]')){const line=e.target.closest('.ship-line');const parent=line.parentElement;if(parent.children.length>1)line.remove();else toast('At least one line is required','error');updateFefoNotices();return}
 const add=e.target.closest('[data-add]');if(add){const type=add.dataset.add;if(type==='receive'){$('#receiptLines').insertAdjacentHTML('beforeend',$('#receiptLines').dataset.returnMode==='1'?issueLine(true):receiveLine());}else $(`#${type==='issue'?'issueLines':'adjustLines'}`).insertAdjacentHTML('beforeend',issueLine(type!=='issue'));return}
 if(e.target.closest('#downloadBackup')){downloadBackup();return}
 if(e.target.closest('#gdriveConnect')){try{await beginGDriveConnection()}catch(err){toast(err.message,'error')}return}
 if(e.target.closest('#gdriveRunNow')){try{await runGDriveNow()}catch(err){toast(err.message,'error')}return}
 if(e.target.closest('#gdriveRefresh')){await loadGoogleDriveStatus();return}
 if(e.target.closest('#gdriveBrowse')){await browseGoogleDriveBackups();return}
 if(e.target.closest('#gdriveDisconnect')){try{await disconnectGDrive()}catch(err){toast(err.message,'error')}return}
});
document.addEventListener('submit',async e=>{
 const form=e.target;if(!['entityForm','receiveForm','issueForm','adjustForm','passwordForm','profileForm','restoreForm'].includes(form.id))return;
 e.preventDefault();const button=form.querySelector('[type=submit]');button.disabled=true;
 try{
  if(form.id==='entityForm')await submitEntity(form);
  if(form.id==='receiveForm')await postShipment('IN',form,extractLines($('#receiptLines'),$('#receiptLines').dataset.returnMode==='1'?'issue':'receive'));
  if(form.id==='issueForm')await postShipment('OUT',form,extractLines($('#issueLines'),'issue'));
  if(form.id==='adjustForm')await postShipment(new FormData(form).get('kind'),form,extractLines($('#adjustLines'),'issue'));
  if(form.id==='profileForm'){
   const p=await api('/api/profile',{method:'PATCH',data:Object.fromEntries(new FormData(form).entries())});
   user.full_name=p.full_name;$('#userName').textContent=p.full_name;toast('Your profile was saved.');
  }
  if(form.id==='passwordForm'){await api('/api/change-password',{method:'POST',data:Object.fromEntries(new FormData(form).entries())});user.must_change_password=false;form.reset();toast('Password updated and other sessions revoked')}
  if(form.id==='restoreForm'){
   const fd=new FormData(form);const confirmation=String(fd.get('confirmation')||'');fd.delete('confirmation');
   if(confirmation!=='RESTORE')throw Error('Type RESTORE in capital letters to confirm');
   if(!window.confirm(window.HWLang?.t('RESTORE the database? All newer items, accounts and movements will be replaced. All staff will be signed out.')||'RESTORE the database? All newer items, accounts and movements will be replaced. All staff will be signed out.'))return;
   const r=await api('/api/backup/restore',{method:'POST',body:fd,headers:{'X-Restore-Confirmation':'RESTORE'}});
   alert(window.HWLang?.t(r.message)||r.message);location.href='/login.html';return;
  }
 }catch(err){toast(err.message,'error')}
 finally{if(document.body.contains(button))button.disabled=false}
});
async function applyStatementPercent(){
 const inp=$('#statementPercentInput');if(!inp)return;
 if(!inp.value.trim() || !inp.checkValidity())throw Error('Percentage must be above zero and at most 1000, with up to two decimals.');
 const next=inp.value.trim();
 const old=statementMode==='scarce'?statementScarcePct:statementSurplusPct;
 if(statementMode==='scarce')statementScarcePct=next;else statementSurplusPct=next;
 try{await reloadPositions()}catch(e){if(statementMode==='scarce')statementScarcePct=old;else statementSurplusPct=old;throw e}
}
document.addEventListener('input',e=>{if(e.target.id==='itemFilter')filterInventory();
 if(e.target.id==='statementSearch')filterStatement();
 if(e.target.id==='columnManagerSearch')searchColumnOptions(e.target.value);
 if(e.target.id==='movementFilter')filterMovements();
 if(e.target.id==='departmentFilter')filterDepartmentTable();
 if(e.target.id==='itemMovementSearch')filterItemMovements();
 if(e.target.matches('#issueForm [data-issue-qty]'))updateFefoNotices();
 if(e.target.matches('[data-dept-search]'))filterDeptPicker(e.target.closest('[data-dept-picker]'));});
document.addEventListener('change',async e=>{
 if(e.target.id==='statementBranch'){
  const book=$('#statementBook');if(book){book.innerHTML=filterBookOptions(e.target.value);book.value='';}filterStatement();}
 if(e.target.id==='statementBook'||e.target.id==='statementSort')filterStatement();
 if(e.target.id==='itemStockStatus'||e.target.id==='itemSort'||e.target.id==='itemIncludeInactive')filterInventory();
 if(e.target.id==='statementExpiryBefore'){
  const old=statementExpiryBefore;
  statementExpiryBefore=e.target.value;
  try{await reloadPositions()}catch(err){statementExpiryBefore=old;toast(err.message,'error')}
 }
 if(e.target.id==='statementPercentInput'){try{await applyStatementPercent()}catch(err){toast(err.message,'error')}}
 if(e.target.matches('[data-issue-product]'))syncIssueProduct(e.target.closest('[data-issue-line]'));
 if(e.target.matches('[data-issue-expiry-picker]'))syncIssueExpiry(e.target.closest('[data-issue-line]'));
 if(e.target.matches('[data-issue-same-date-lot]')){const line=e.target.closest('[data-issue-line]');line.querySelector('[data-issue-batch]').value=e.target.value;syncIssueBatch(line);}
 if(e.target.id==='movementType')filterMovements();
 if(e.target.id==='itemBranchFilter') { const filter=$('#itemBookFilter');if(filter){filter.innerHTML=filterBookOptions(e.target.value);filter.value=''}filterInventory(); }
 if(e.target.id==='itemBookFilter')filterInventory();
 if(e.target.matches('#issueForm input[name="route"]')||e.target.matches('#issueForm input[name="emergency_pending"]'))syncOutgoingDestination(e.target.closest('form'));
 if(e.target.matches('#receiveForm input[name="route"]'))syncIncomingRoute(e.target.closest('form'));
 if(e.target.matches('[data-receive-line] select[data-key="item_id"]'))prefillReceiptPrice(e.target.closest('[data-receive-line]'));
 if(e.target.matches('#entityForm select[name="branch"]'))syncItemBranchFields(e.target.closest('#entityForm'));
 if(e.target.matches('#entityForm [data-opening-balance]'))syncOpeningBalanceFields(e.target.closest('#entityForm'));
 if(e.target.matches('[data-user-role]'))syncUserBranchField(e.target.closest('#entityForm'));
});
function syncUserBranchField(form){
 const role=form?.querySelector('[data-user-role]')?.value;
 const branch=form?.querySelector('[data-user-branch]');if(!branch)return;
 const admin=role==='admin';branch.disabled=admin;branch.required=!admin;
 if(admin)branch.value='';
}

function filterMovements(){const q=($('#movementFilter')?.value||'').toLowerCase(),t=$('#movementType')?.value||'';
 const results=cache.movements.filter(x=>(!t||x.kind===t)&&JSON.stringify(x).toLowerCase().includes(q));$('#movementResults').innerHTML=table(['Movement ID','Type','Paper refs','Source / destination','Item lines','Operator'],movementRows(results));}

function openNotifications(){
 const root=$('#notificationModal');if(!root)return;
 const today=todayBaghdad();const lots=cache.batches.filter(b=>b.on_hand>0&&b.item_active&&b.expiry_date);
 const expired=lots.filter(b=>b.expiry_date<today).sort(fefoSort);
 const near=lots.filter(b=>b.expiry_date>=today&&fefoDateDays(b.expiry_date)<=60).sort(fefoSort);
 const pending=cache.movements.filter(m=>m.paperwork_pending);
 const empty=cache.items.filter(it=>it.active&&lotStats(it).physical<=0);
 const card=(name,arr,action,limit=5)=>`<section class="notification-section"><header><strong>${E(name)}</strong><span class="notification-count">${N(arr.length)}</span></header><div class="notification-list">${arr.length?arr.slice(0,limit).map(action).join(''):'<p class="muted-hint">لا توجد تنبيهات حالياً · None</p>'}</div></section>`;
 root.innerHTML=`<div class="notification-dialog" role="dialog" aria-modal="true" aria-labelledby="notificationTitle"><div class="notification-header"><div><h2 id="notificationTitle">التنبيهات الرئيسية · Notifications</h2><p class="muted-hint">ملخص مهمات المخزن — key warehouse alerts</p></div><button class="db-btn secondary small" type="button" data-close-notifications>إغلاق ×</button></div><div class="notification-grid">
 ${card('مواد منتهية الصلاحية · Expired lots',expired,b=>`<div>${E(b.item_name)} · ${E(b.expiry_date)} · ${N(b.on_hand)}</div>`)}
 ${card('مواد قريبة النفاذ · Expiring in 60 days',near,b=>`<div>${E(b.item_name)} · ${E(b.expiry_date)} · ${N(b.on_hand)}</div>`)}
 ${card('مواد مفقودة · No stock',empty,it=>`<div>${E(it.trade_name||it.name)} · ${E(branchName(it.branch))}</div>`)}
 ${card('أوراق طلبية ناقصة · Pending paperwork',pending,m=>`<div>${E(m.code)} · ${E(m.paper_ref||'—')}</div>`)}
 </div><div class="notification-footer"><button class="db-btn secondary" type="button" data-notif-go="positions">عرض المواقف</button><button class="db-btn secondary" type="button" data-notif-go="movements">سجل الحركات</button></div></div>`;
 root.classList.add('open');root.setAttribute('aria-hidden','false');root.querySelector('[data-close-notifications]')?.focus();window.HWLang?.apply();
}
function closeNotifications(){const root=$('#notificationModal');if(!root)return;root.classList.remove('open');root.setAttribute('aria-hidden','true');root.innerHTML=''}

$('#menuButton').addEventListener('click',()=>{$('#sidebar').classList.toggle('open');$('#dimOverlay').classList.toggle('show')});
$('#dimOverlay').addEventListener('click',closeMenu);
$('#accountButton').addEventListener('click',()=>{$('#accountMenu').classList.toggle('open');$('#accountButton').setAttribute('aria-expanded',$('#accountMenu').classList.contains('open'))});
$('#notifBtn').addEventListener('click',()=>openNotifications());
$('#logoutButton').addEventListener('click',async()=>{try{await api('/api/logout',{method:'POST'});location.href='/login.html'}catch(e){toast(e.message,'error')}});
$('#globalSearch').addEventListener('keydown',e=>{if(e.key==='Enter'){route('inventory');$('#itemFilter').value=e.target.value;$('#itemFilter').dispatchEvent(new Event('input',{bubbles:true}))}});
$('#entityModal').addEventListener('click',e=>{if(e.target.id==='entityModal')modalClose()});
window.addEventListener('hashchange',()=>{if(user)showPage(location.hash.slice(1))});
document.addEventListener('keydown',e=>{
 const search=e.target.closest('[data-dept-search]');
 if(search){const picker=search.closest('[data-dept-picker]');
  if(e.key==='Escape'){closeDepartmentPicker(picker);picker.querySelector('[data-dept-trigger]').focus();e.preventDefault();return;}
  if(e.key==='ArrowDown'){const first=[...picker.querySelectorAll('[data-dept-option]')].find(el=>!el.hidden);if(first){first.focus();e.preventDefault();return;}}
  if(e.key==='Enter'){const matches=[...picker.querySelectorAll('[data-dept-option]')].filter(el=>!el.hidden);if(matches.length===1){selectDepartment(picker,matches[0]);e.preventDefault();return;}e.preventDefault();}
 }
 const option=e.target.closest('[data-dept-option]');if(option){const picker=option.closest('[data-dept-picker]');
  if(e.key==='Escape'){closeDepartmentPicker(picker);picker.querySelector('[data-dept-trigger]').focus();e.preventDefault();return;}
  if(e.key==='Enter'||e.key===' '){selectDepartment(picker,option);e.preventDefault();return;}
  if(e.key==='ArrowDown'||e.key==='ArrowUp'){const matches=[...picker.querySelectorAll('[data-dept-option]')].filter(el=>!el.hidden);const i=matches.indexOf(option);matches[Math.max(0,Math.min(matches.length-1,i+(e.key==='ArrowDown'?1:-1)))]?.focus();e.preventDefault();return;}
 }
 if(e.key==='Escape'){closeNotifications();closeShipmentHistory();modalClose();inlineNewItem=null;closeMenu();$('#accountMenu').classList.remove('open')}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('#globalSearch').focus()}});
(async function boot(){try{
 user=await api('/api/me');csrf=user.csrf;
 $('#userName').textContent=user.full_name;$('#userRole').textContent=user.role[0].toUpperCase()+user.role.slice(1);
 if(!can('users'))$$('[data-view="users"]').forEach(x=>x.style.display='none');
 if(!can('backup'))$$('[data-view="backup"]').forEach(x=>x.style.display='none');
 if(user.role!=='admin')$$('[data-view="settings"]').forEach(x=>x.style.display='');
 await refreshData();showPage(location.hash.slice(1)||'overview');
 const gd=new URLSearchParams(location.search).get('gdrive');if(gd){toast(gd==='connected'?'Google Drive connected successfully':'Google authorization failed. Please try again.',gd==='connected'?'ok':'error');history.replaceState(null,'',location.pathname+location.hash);}
}catch(e){$('#dashboardView').innerHTML=msg('Database unavailable',e.message);toast(e.message,'error')}})();

window.addEventListener('warehouse:languagechange',()=>{document.querySelectorAll('time.localized-time[datetime]').forEach(el=>{el.textContent=fmtDate(el.getAttribute('datetime'))});if(view==='inventory')filterInventory();if(view==='distribution')updateFefoNotices()});

// Refresh language-dependent report counters without reloading or losing user filters.
window.addEventListener('warehouse:languagechange',()=>{
 if(view!=='positions')return;
 const search=$('#statementSearch')?.value||'',branch=$('#statementBranch')?.value||'',book=$('#statementBook')?.value||'';
 $('#dashboardView').innerHTML=warehouseStatements();
 if($('#statementSearch'))$('#statementSearch').value=search;
 if($('#statementBranch'))$('#statementBranch').value=branch;
 if($('#statementBook'))$('#statementBook').value=book;
 filterStatement();window.HWLang?.apply();
});

// V4.14 column dialog keyboard support, including focus containment and Escape.
document.addEventListener('keydown',e=>{
 const dlg=$('#columnManager');if(!dlg?.classList.contains('open'))return;
 if(e.key==='Escape'){e.preventDefault();closeColumnManager();return;}
 if(e.key==='Tab'){const focusables=$$('button:not([disabled]),input:not([disabled])',dlg).filter(x=>!x.closest('[hidden]'));if(!focusables.length)return;const first=focusables[0],last=focusables.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus()}}
});
