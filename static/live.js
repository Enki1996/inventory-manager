/* Live V4.1 bilingual warehouse prototype: all changes go through the server and SQLite database. */
const $ = (s, root=document)=>root.querySelector(s);
const $$ = (s, root=document)=>[...root.querySelectorAll(s)];
const I = name=>`<svg class="i" aria-hidden="true"><use href="#ico-${name}"/></svg>`;
const E = value=>String(value??'').replace(/[&<>"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
const N = v=>Number(v||0).toLocaleString('en-US');
const fmtDate = str=>new Date(str).toLocaleString(window.HWLang?.get()==='ar'?'ar-IQ':'en-GB',{timeZone:'Asia/Baghdad',dateStyle:'medium',timeStyle:'short'});
const D = str=>str?`<time class="localized-time" datetime="${E(str)}">${E(fmtDate(str))}</time>`:'—';
const badge = (label,kind='neutral')=>`<span class="pill ${kind}">${E(label)}</span>`;
const msg = (title,sub='')=>`<div class="empty-state">${I('package')}<strong>${E(title)}</strong><span class="muted-hint">${E(sub)}</span></div>`;
let user=null, csrf='', view='', cache={items:[],departments:[],batches:[],movements:[],users:[],dashboard:null}, toastTimer;
const headers={overview:'Warehouse Overview',inventory:'Inventory',receiving:'Receive Shipments',distribution:'Distribute to Departments',returns:'Returns & Adjustments',movements:'Movement History',batches:'Batches & Expiry',departments:'Departments',reports:'Reports',users:'Users & Permissions',backup:'Backup & Restore',settings:'Settings'};
const can=p=>!!user?.permissions.includes(p);
const typeLabel = {IN:'Received',OUT:'Distributed',RETURN:'Returned',ADJUST_PLUS:'Added adjustment',ADJUST_MINUS:'Removed adjustment'};
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
  const endpoints=['items','departments','batches','movements','dashboard'];
  const rows=await Promise.all(endpoints.map(path=>api('/api/'+path)));
  for(let i=0;i<endpoints.length;i++)cache[endpoints[i]]=rows[i];
  if(can('users'))cache.users=await api('/api/users');
}
const selectOptions = (items,selected='',placeholder='Select one')=>`<option value="">${E(placeholder)}</option>`+items.map(o=>`<option value="${E(o.value)}" ${String(o.value)===String(selected)?'selected':''}>${E(o.label)}</option>`).join('');
const itemOptions = ()=>selectOptions(cache.items.filter(x=>x.active).map(x=>({value:x.id,label:`${x.sku} · ${x.name}${x.generic_name?' / '+x.generic_name:''} (${x.unit})`})),'','Select product');
const deptOptions = ()=>selectOptions(cache.departments.filter(x=>x.active).map(x=>({value:x.id,label:`${x.code} · ${x.name}`})),'','Choose department');
const batchOptions = (includeExpired=false)=>selectOptions(cache.batches.filter(x=>x.item_active&&x.on_hand>0&&(includeExpired||!x.expiry_date||x.expiry_date>=new Date().toISOString().slice(0,10))).map(x=>({value:x.id,label:`${x.item_name} · Batch ${x.batch_no} · ${N(x.on_hand)} ${x.unit} · Exp ${x.expiry_date||'N/A'}`})),'','Select batch');
const field=(label,input,help='')=>`<label class="db-field"><span>${E(label)}</span>${input}${help?`<small>${E(help)}</small>`:''}</label>`;
const inp=(name,placeholder='',type='text',other='')=>`<input class="db-input" name="${name}" placeholder="${E(placeholder)}" type="${type}" ${other}>`;
const head=(title,desc,actions='')=>`<div class="db-head"><div><span class="eyebrow">Central Warehouse / Live Workspace</span><h1>${E(title)}</h1><p>${E(desc)}</p></div>${actions?`<div class="db-actions">${actions}</div>`:''}</div>`;
const panel=(title,content,icon='package')=>`<section class="db-panel"><h2>${I(icon)} ${E(title)}</h2>${content}</section>`;
const table=(cols,rows)=>rows.length?`<div class="db-table-wrap"><table class="db-table"><thead><tr>${cols.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`:msg('No records yet','Add your first record using the action button above.');
// Item catalog lookup: official, generic, company and colloquial/alternate names.
const normalizeItemSearch = value=>String(value??'').toLocaleLowerCase().normalize('NFKC')
 .replace(/[\u064b-\u065f\u0670\u0640]/g,'').replace(/[إأآٱ]/g,'ا').replace(/ى/g,'ي').trim();
const itemSearchText = it=>normalizeItemSearch([it.sku,it.name,it.generic_name,it.manufacturer,it.information,it.category].join(' '));
const filteredItems = query=>{
 const terms=normalizeItemSearch(query).split(/\s+/).filter(Boolean);
 return cache.items.filter(it=>terms.every(term=>itemSearchText(it).includes(term)));
};
const inventoryColumns=['Scientific name / SKU','Generic / other names','Manufacturer / made on','Category','Reference expiry','Warehouse stock','Batches','Status','Actions'];
function itemRows(items){return items.map(it=>`<tr>
 <td><strong>${E(it.name)}</strong><div class="tiny">${E(it.sku)}</div></td>
 <td><strong>${E(it.generic_name||'—')}</strong>${it.information?`<div class="tiny item-alias" title="${E(it.information)}">${E(it.information)}</div>`:''}</td>
 <td>${E(it.manufacturer||'—')}${it.manufacture_date?`<div class="tiny">${E(it.manufacture_date)}</div>`:''}</td>
 <td>${E(it.category)}<div class="tiny">${E(it.unit)}</div></td>
 <td>${E(it.expiry_date||'—')}</td>
 <td><strong>${N(it.stock)}</strong> ${E(it.unit)}</td>
 <td>${N(it.batch_count)}</td>
 <td>${Number(it.min_stock)>0&&Number(it.stock)<Number(it.min_stock)?badge('Low stock','warning'):badge(it.active?'Active':'Inactive',it.active?'':'danger')}</td>
 <td>${can('item_write')?`<div class="db-small-actions"><button data-edit-item="${it.id}">Edit</button></div>`:'—'}</td>
 </tr>`)}
function departmentRows(depts){return depts.map(it=>`<tr><td><strong>${E(it.code)}</strong></td><td>${E(it.name)}</td><td>${badge(it.active?'Active':'Inactive',it.active?'':'danger')}</td><td>${can('department_write')?`<div class="db-small-actions"><button data-edit-dept="${it.id}">Edit</button></div>`:'—'}</td></tr>`)}
function movementRows(movements){return movements.map(m=>`<tr><td><strong>${E(m.code)}</strong><div class="tiny">${D(m.created_at)}</div></td><td>${badge(typeLabel[m.kind]||m.kind,m.kind==='OUT'?'blue':'neutral')}</td><td><strong>${E(m.paper_ref||'—')}</strong></td><td>${E(m.department_name||m.source||'—')}</td><td>${m.lines.map(l=>`${E(l.item_name)} · ${E(l.batch_no)} · ${N(l.qty)} ${E(l.unit)}`).join('<div style="height:5px"></div>')}</td><td>${E(m.creator)}</td></tr>`)}
function batchRows(rows){return rows.map(b=>`<tr><td><strong>${E(b.item_name)}</strong><div class="tiny">${E(b.sku)}</div></td><td>${E(b.batch_no)}</td><td>${E(b.expiry_date||'Not applicable')}</td><td><strong>${N(b.on_hand)}</strong> ${E(b.unit)}</td><td>${b.expiry_date&&b.expiry_date<new Date().toISOString().slice(0,10)?badge('Expired','danger'):b.on_hand===0?badge('Empty'):badge('Available','blue')}</td></tr>`)}
function overview(){
 const s=cache.dashboard;
 const metrics=[['Registered items',s.items,'Products in catalog','package'],['Warehouse units',s.stock,'Total stock across all batches','packages'],['Active departments',s.departments,'Distribution destinations','building'],['Recorded movements',s.movements,'Permanent transaction log','history']];
 const kpis=`<div class="db-kpis">${metrics.map(([label,num,desc,icon])=>`<div class="db-kpi"><span class="name">${I(icon)} ${E(label)}</span><span class="num">${N(num)}</span><span class="desc">${E(desc)}</span></div>`).join('')}</div>`;
 const alerts=cache.items.filter(i=>i.active&&i.min_stock>0&&i.stock<i.min_stock);
 const exp=cache.batches.filter(b=>b.on_hand>0&&b.expiry_date&&b.expiry_date>=new Date().toISOString().slice(0,10)&&b.expiry_date<=new Date(Date.now()+60*864e5).toISOString().slice(0,10));
 return `<div class="db-decor">${head('Welcome back, '+user.full_name,'Your central warehouse is connected to the local database. Inventory and movements below update after every saved transaction.')}
 <div class="db-actions">${can('item_write')?`<button class="db-btn" data-new="item">${I('package')} Add item</button>`:''}${can('department_write')?`<button class="db-btn secondary" data-new="dept">${I('building')} Add department</button>`:''}${can('movement_write')?`<button class="db-btn secondary" data-go="receiving">${I('incoming')} Receive shipment</button><button class="db-btn secondary" data-go="distribution">${I('outgoing')} Distribute stock</button>`:''}</div></div>
 ${user.must_change_password?`<div class="db-alert"><strong>Change your temporary password.</strong> This account was created with a temporary login. Use Settings → Change Password before entering important data.</div>`:''}
 ${kpis}<div class="db-layout"><div>${panel('Recent warehouse movements',table(['Movement','Type','Paper reference','From / To','Lines','By'],movementRows(cache.movements.slice(0,6))),'history')}</div><div>${panel('Attention needed',`<div class="db-help">${I('warning')} ${alerts.length} item(s) under the reorder threshold · ${exp.length} batch(es) expiring in the next 60 days.</div><div style="margin-top:15px">${alerts.slice(0,5).map(i=>`<div style="display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid #eaf1f4;font-size:11px"><span>${E(i.name)}</span><strong>${N(i.stock)} / ${N(i.min_stock)}</strong></div>`).join('')||'<p class="muted-hint">No low-stock alerts at the moment.</p>'}</div>`,'warning')}
 ${panel('Quick navigation',`<div class="db-actions"><button class="db-btn secondary" data-go="inventory">Inventory</button><button class="db-btn secondary" data-go="departments">Departments</button><button class="db-btn secondary" data-go="movements">Movement history</button></div>`,'dashboard')}</div></div>`
}
function inventory(){return `${head('Item inventory','Create products independently of stock receipts. Stock is then added to its matching batch through Receive Shipments.',can('item_write')?`<button class="db-btn" data-new="item">${I('package')} New item</button>`:'')}${panel('Product catalog',`<div class="db-toolbar">${inp('filter','Search scientific, generic, common name, company or code...','search','id="itemFilter"')}<span class="muted-hint">${cache.items.length} registered items</span></div><div id="itemResults">${table(inventoryColumns,itemRows(cache.items))}</div>`,'package')}`}
function departments(){return `${head('Hospital departments','These are shipment destinations. This version does not manage their internal stock.',can('department_write')?`<button class="db-btn" data-new="dept">${I('building')} Add department</button>`:'')}${panel('Saved departments',table(['Code','Department','Status','Actions'],departmentRows(cache.departments)),'building')}`}
function batches(){return `${head('Batches and expiration','Stock quantity is recorded separately for every batch. Never issue expired lots.')}${panel('Batch register',table(['Product','Batch number','Expiration','Warehouse balance','Status'],batchRows(cache.batches)),'calendar')}`}
function movements(){return `${head('Movement history','Every receipt, issue, return and adjustment has a permanent movement ID plus the original document reference.')}${panel('Transaction register',`<div class="db-toolbar">${inp('movement_filter','Search requisition, item or user...','search','id="movementFilter"')}<select class="db-select" id="movementType" style="max-width:180px"><option value="">All types</option><option value="IN">Incoming</option><option value="OUT">Distributions</option><option value="RETURN">Returns</option><option value="ADJUST_PLUS">Adjustment (+)</option><option value="ADJUST_MINUS">Adjustment (−)</option></select></div><div id="movementResults">${table(['Movement ID','Type','Paper reference','Source / destination','Item lines','Operator'],movementRows(cache.movements))}</div>`,'history')}`}
const receiveLine=()=>`<div class="ship-line" data-receive-line>${field('Product',`<select class="db-select" data-key="item_id" required>${itemOptions()}</select>`)}${field('Batch number',`<input class="db-input" data-key="batch_no" placeholder="e.g. LOT-24A" required maxlength="90">`)}${field('Expiry (optional)',`<input class="db-input" type="date" data-key="expiry_date">`)}${field('Quantity',`<input class="db-input" type="number" data-key="qty" min="1" step="1" required placeholder="0">`)}<button class="db-btn danger small" type="button" data-remove-line title="Remove line">×</button></div>`;
const issueLine=includeExpired=>`<div class="ship-line issue" data-issue-line>${field('Select product batch',`<select class="db-select" data-key="batch_id" required>${batchOptions(includeExpired)}</select>`)}${field('Quantity',`<input class="db-input" type="number" data-key="qty" min="1" step="1" required placeholder="0">`)}<button class="db-btn danger small" type="button" data-remove-line>×</button></div>`;
function receiving(){return `${head('Receive incoming shipment','Add one or more product batches to warehouse stock. Reference the original receipt or delivery document.')}${panel('New incoming receipt',`<form id="receiveForm" class="db-form"><div class="db-grid">${field('Paper receipt / delivery reference',inp('paper_ref','e.g. GRN-2026-0042','text','required'))}${field('Received from / supplier',inp('source','e.g. Central medical supply','text','required'))}${field('Notes (optional)',`<textarea name="notes" class="db-textarea" placeholder="Delivery or document notes"></textarea>`)}</div><h3 style="font-size:13px;margin:4px 0">Received product batches</h3><div id="receiptLines">${receiveLine()}</div><div class="db-actions"><button type="button" class="db-btn secondary" data-add="receive">+ Add another item</button><button type="submit" class="db-btn">${I('incoming')} Save receipt and update stock</button></div></form>`,'incoming')}`}
function distribution(){return `${head('Distribute to department','Choose batch-specific stock and enter the requisition serial printed on the requesting paper. Issued stock leaves this warehouse.')}${panel('New distribution record',`<form id="issueForm" class="db-form"><div class="db-grid">${field('Paper requisition serial number',inp('paper_ref','e.g. REQ-2026-0185','text','required'))}${field('Receiving hospital department',`<select name="department_id" class="db-select" required>${deptOptions()}</select>`)}${field('Notes (optional)',`<textarea name="notes" class="db-textarea" placeholder="Employee / delivery notes"></textarea>`)}</div><h3 style="font-size:13px;margin:4px 0">Products and batches</h3><div id="issueLines">${issueLine(false)}</div><div class="db-actions"><button type="button" class="db-btn secondary" data-add="issue">+ Add another batch</button><button type="submit" class="db-btn">${I('outgoing')} Save distribution</button></div></form><div class="db-note warn" style="margin-top:14px">Expiring and out-of-stock batches are blocked by the server. The entire distribution is cancelled if any selected line cannot be issued.</div>`,'outgoing')}`}
function returns(){return `${head('Returns and stock adjustments','Return unused items to the central warehouse or perform manager-authorized balance corrections with an audit record.')}${panel('Record department return',`<form id="returnForm" class="db-form"><div class="db-grid">${field('Return paper reference',inp('paper_ref','e.g. RET-2026-0034','text','required'))}${field('Returning department',`<select class="db-select" name="department_id" required>${deptOptions()}</select>`)}${field('Original requisition number (notes)',inp('notes','e.g. REQ-2026-0185','text'))}</div><div id="returnLines">${issueLine(true)}</div><div class="db-actions"><button class="db-btn secondary" type="button" data-add="return">+ Add item</button><button class="db-btn" type="submit">${I('return')} Record return</button></div></form>`,'return')}${can('adjust')?panel('Manager-only stock correction',`<form id="adjustForm" class="db-form"><div class="db-grid">${field('Correction type',`<select class="db-select" name="kind"><option value="ADJUST_PLUS">Increase available stock</option><option value="ADJUST_MINUS">Decrease available stock</option></select>`)}${field('Reference / reason code',inp('paper_ref','e.g. COUNT-2026-003','text','required'))}${field('Detailed reason',`<textarea class="db-textarea" name="notes" required placeholder="Why was this correction needed?"></textarea>`)}</div><div id="adjustLines">${issueLine(true)}</div><div class="db-actions"><button class="db-btn" type="submit">Record correction with audit trail</button></div></form>`,'warning'):''}`}
function users(){if(!can('users'))return msg('Access denied','Only administrators manage staff accounts.');const rows=cache.users.map(x=>`<tr><td><strong>${E(x.username)}</strong><div class="tiny">${E(x.full_name)}</div></td><td>${badge(x.role,x.role==='admin'?'blue':'neutral')}</td><td>${badge(x.is_active?'Active':'Disabled',x.is_active?'':'danger')}</td><td>${x.must_change_password?'Temporary':'Updated'}</td><td>${x.id!==user.id?`<div class="db-small-actions"><button data-edit-user="${x.id}">Role / status</button><button data-reset-user="${x.id}">Reset password</button></div>`:'Current account'}</td></tr>`);
return `${head('Users and permissions','Only administrators can create staff accounts. Rights are checked by the backend on every action.',`<button class="db-btn" data-new="user">${I('users')} Create account</button>`)}<div class="db-note">Roles: <b>Administrator</b> full access and backups; <b>Manager</b> products, departments, shipments and stock corrections; <b>Operator</b> receives/issues stock; <b>Viewer</b> read only. No public registration.</div>${panel('Warehouse accounts',table(['Username / name','Role','Status','Password','Actions'],rows),'users')}`}
function backup(){return `${head('Database backup and restore','Administrators can download a portable complete snapshot or upload a previously exported file. Account password hashes are included, but active login sessions are excluded.')}
<div class="db-layout">${panel('Download full backup',`<p class="muted-hint" style="margin-bottom:16px">Includes users, departments, items, batches, requisition references, all movements and audit records. Creates a ZIP with a database snapshot and SHA-256 manifest.</p><button type="button" class="db-btn" id="downloadBackup">${I('download')} Download full database backup</button>`,'backup')}${panel('Restore previously exported backup',`<p class="muted-hint" style="margin-bottom:15px">This replaces ALL current records with the uploaded snapshot. A safety copy is automatically saved to the server first.</p><form id="restoreForm" class="db-form">${field('Upload warehouse backup ZIP',`<input name="backup" type="file" class="db-input" accept=".zip" required>`)}${field('Type RESTORE to confirm',inp('confirmation','RESTORE','text','required autocomplete="off"'))}<button class="db-btn danger" type="submit">${I('upload')} Validate and restore backup</button></form>`,'backup')}</div><div class="db-note warn">Important: restoration can remove transactions created after the selected backup. It also signs out all staff. Download and store backups securely; this testing build has manual backup only.</div>`}
function reports(){const low=cache.items.filter(x=>x.active&&x.min_stock>0&&x.stock<x.min_stock);const dist=cache.movements.filter(x=>x.kind==='OUT');const total=dist.length;
return `${head('Warehouse reports','Basic live summaries derived from your saved records. Spreadsheet and PDF reports can be added after we finalize the workflow.')}
<div class="db-kpis"><div class="db-kpi"><span class="name">${I('package')} Products</span><span class="num">${N(cache.items.length)}</span></div><div class="db-kpi"><span class="name">${I('warning')} Low stock</span><span class="num">${N(low.length)}</span></div><div class="db-kpi"><span class="name">${I('outgoing')} Distribution slips</span><span class="num">${N(total)}</span></div><div class="db-kpi"><span class="name">${I('history')} Total transactions</span><span class="num">${N(cache.movements.length)}</span></div></div>
${panel('Low-stock products',table(['SKU','Item','Current units','Minimum threshold'],low.map(x=>`<tr><td>${E(x.sku)}</td><td>${E(x.name)}</td><td>${N(x.stock)} ${E(x.unit)}</td><td>${N(x.min_stock)}</td></tr>`)),'warning')}`}
function settings(){return `${head('Settings and account security','Update your own password. Management can also review a separate audit trail.')}
${panel('Change your password',`<form id="passwordForm" class="db-form" style="max-width:530px"><div class="db-grid">${field('Current password',inp('current_password','','password','required autocomplete="current-password"'))}${field('New password (8+ characters)',inp('new_password','','password','required minlength="8" autocomplete="new-password"'))}</div><button type="submit" class="db-btn" style="justify-self:start">Update password</button></form>`,'lock')}
${can('item_write')?panel('Operations audit trail',`<div id="auditLog">Loading events...</div>`,'history'):''}`}
const pages={overview,inventory,departments,batches,movements,receiving,distribution,returns,users,backup,reports,settings};
function showPage(next){
 if(!pages[next])next='overview';if((next==='users'&&!can('users'))||(next==='backup'&&!can('backup')))next='overview';
 view=next;$$('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===next);b.setAttribute('aria-current',b.dataset.view===next?'page':'false')});
 $('#topTitle').textContent=headers[next];$('#dashboardView').innerHTML=pages[next]();window.HWLang?.apply();closeMenu();
 if(next==='settings'&&can('item_write'))loadAudit();
 window.scrollTo({top:0,behavior:'instant'});
}
function route(next){location.hash=next;showPage(next)}
function closeMenu(){$('#sidebar').classList.remove('open');$('#dimOverlay').classList.remove('show')}
function modalOpen(title,description,fields,formType,button='Save changes'){
 const modal=$('#entityModal');modal.innerHTML=`<div class="modal-body ${formType.startsWith('item:')?'item-dialog':''}" role="dialog" aria-modal="true" aria-label="${E(title)}"><div class="db-actions" style="justify-content:space-between;align-items:center"><h2>${E(title)}</h2><button class="db-btn secondary small" type="button" data-close-modal>Close ×</button></div><p>${E(description)}</p><form id="entityForm" data-entity="${formType}" class="db-form"><div class="db-grid">${fields}</div><div class="modal-footer"><button class="db-btn secondary" type="button" data-close-modal>Cancel</button><button class="db-btn" type="submit">${E(button)}</button></div></form></div>`;
 modal.classList.add('open');modal.setAttribute('aria-hidden','false');window.HWLang?.apply();$('.db-input',modal)?.focus();
}
function modalClose(){const el=$('#entityModal');el.classList.remove('open');el.innerHTML='';el.setAttribute('aria-hidden','true')}
function editItem(it=null){
 const f=[
  field('Product code / SKU',`<input name="sku" class="db-input" required maxlength="50" value="${E(it?.sku||'')}" placeholder="MED-0001">`),
  field('Scientific item name',`<input name="name" class="db-input" required maxlength="160" value="${E(it?.name||'')}" placeholder="e.g. Ceftriaxone 1 g">`),
  field('Generic name',`<input name="generic_name" class="db-input" maxlength="160" value="${E(it?.generic_name||'')}" placeholder="Generic / alternative official name">`),
  field('Manufacturer company',`<input name="manufacturer" class="db-input" maxlength="160" value="${E(it?.manufacturer||'')}" placeholder="Company name">`),
  field('Category',`<input name="category" class="db-input" required maxlength="80" value="${E(it?.category||'')}" placeholder="Medications / Supplies">`),
  field('Stock unit',`<input name="unit" class="db-input" required maxlength="30" value="${E(it?.unit||'')}" placeholder="Vial, box, piece, bag">`),
  field('Manufacture date (optional)',`<input name="manufacture_date" class="db-input" type="date" value="${E(it?.manufacture_date||'')}">`),
  field('Expiration date (optional)',`<input name="expiry_date" class="db-input" type="date" value="${E(it?.expiry_date||'')}">`),
  field('Information / alternate names',`<textarea name="information" class="db-textarea" maxlength="2000" rows="4" placeholder="Slang, common names, local terms, abbreviations, spellings... separate with commas or new lines">${E(it?.information||'')}</textarea>`,
   'Add as many alternative names or notes as you need. All text here is included in item search.').replace('class="db-field"','class="db-field wide"')
 ];
 if(it)f.push(field('Active status',`<select class="db-select" name="active"><option value="1" ${it.active?'selected':''}>Active</option><option value="0" ${!it.active?'selected':''}>Inactive</option></select>`));
 modalOpen(it?'Edit item':'Register item','Dates here describe the catalog item only. Enter the actual expiry for each batch when receiving stock.',f.join(''),`item:${it?.id||'new'}`);
}
function editDept(it=null){modalOpen(it?'Edit department':'Add department','Departments are distribution destinations, not separate inventory locations.',
 field('Department code',`<input name="code" class="db-input" required maxlength="30" value="${E(it?.code||'')}" placeholder="ER">`)+field('Department name',`<input name="name" class="db-input" required value="${E(it?.name||'')}" placeholder="Emergency Department">`)+(it?field('Status',`<select class="db-select" name="active"><option value="1" ${it.active?'selected':''}>Active</option><option value="0" ${!it.active?'selected':''}>Inactive</option></select>`):''),
 `department:${it?.id||'new'}`)}
function createUser(){modalOpen('Create staff account','A new employee can sign in immediately using the username and temporary password you set.',
 field('Username',inp('username','e.g. warehouse01','text','required minlength="3" pattern="[a-zA-Z0-9_.-]+"'))+
 field('Full name',inp('full_name','Employee full name','text','required'))+
 field('Temporary password (8+ characters)',inp('password','At least 8 characters','password','required minlength="8"'))+
 field('Role',`<select class="db-select" name="role"><option value="viewer">Viewer — Read only</option><option value="operator">Operator — Stock movements</option><option value="manager">Manager — Inventory management</option><option value="admin">Administrator — Full access</option></select>`),
 'user:new','Create user')}
function editUser(it){modalOpen('Edit account: '+it.username,'Change role or disable this account. Disabled staff are immediately signed out.',
 field('Role',`<select name="role" class="db-select">${['admin','manager','operator','viewer'].map(x=>`<option value="${x}" ${it.role===x?'selected':''}>${x}</option>`).join('')}</select>`)+
 field('Account status',`<select name="is_active" class="db-select"><option value="1" ${it.is_active?'selected':''}>Active</option><option value="0" ${!it.is_active?'selected':''}>Disabled</option></select>`),`user:${it.id}`,'Update account')}
function resetUser(it){modalOpen('Reset password: '+it.username,'This resets the password and signs out the employee from any active session.',
 field('New temporary password (8+ characters)',inp('password','','password','required minlength="8"')),
 `reset:${it.id}`,'Reset password')}
function extractLines(container,type){return $$(`[data-${type}-line]`,container).map(el=>{
  let line={};$$('[data-key]',el).forEach(n=>line[n.dataset.key]=n.value.trim());return line;
})}
async function submitEntity(form){const type=form.dataset.entity, [entity,id]=type.split(':');const d=Object.fromEntries(new FormData(form).entries());
 if(entity==='item'){if(id!=='new')d.active=d.active==='1';await api(id==='new'?'/api/items':'/api/items/'+id,{method:id==='new'?'POST':'PATCH',data:d})}
 else if(entity==='department'){if(id!=='new')d.active=d.active==='1';await api(id==='new'?'/api/departments':'/api/departments/'+id,{method:id==='new'?'POST':'PATCH',data:d})}
 else if(entity==='user'){if(id!=='new')d.is_active=d.is_active==='1';await api(id==='new'?'/api/users':'/api/users/'+id,{method:id==='new'?'POST':'PATCH',data:d})}
 else if(entity==='reset'){await api('/api/users/'+id+'/reset-password',{method:'POST',data:d})}
 modalClose();await refreshData();showPage(view);toast('Saved successfully in the database');
}
async function postShipment(kind,form,lines){
 const obj=Object.fromEntries(new FormData(form).entries());
 const payload={kind,paper_ref:obj.paper_ref||'',source:obj.source||'',notes:obj.notes||'',lines};
 if(kind==='RETURN'||kind==='OUT')payload.department_id=Number(obj.department_id);
 const r=await api('/api/movements',{method:'POST',data:payload});
 await refreshData();route('movements');toast(`Saved ${r.code}. Warehouse balance updated.`);
}
async function loadAudit(){try{const a=await api('/api/audit');if(view!=='settings')return;$('#auditLog').innerHTML=table(['Date / time','Action','Operator','Detail'],a.map(x=>`<tr><td>${D(x.created_at)}</td><td>${E(x.action)}</td><td>${E(x.username||'System')}</td><td><span class="tiny">${E(x.detail).slice(0,220)}</span></td></tr>`))}catch(e){if($('#auditLog'))$('#auditLog').textContent=e.message}}
async function downloadBackup(){try{
 const r=await api('/api/backup/export');const blob=await r.blob();const a=document.createElement('a');a.href=URL.createObjectURL(blob);
 a.download=r.headers.get('content-disposition')?.match(/filename="([^"]+)"/)?.[1]||'warehouse_backup.zip';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),4000);toast('Backup downloaded. Store it in a secure location.');
}catch(e){toast(e.message,'error')}}
document.addEventListener('click',async e=>{
 const v=e.target.closest('[data-view],[data-go]');if(v){route(v.dataset.view||v.dataset.go);return}
 const n=e.target.closest('[data-new]');if(n){if(n.dataset.new==='item')editItem();if(n.dataset.new==='dept')editDept();if(n.dataset.new==='user')createUser();return}
 const item=e.target.closest('[data-edit-item]');if(item){editItem(cache.items.find(x=>x.id===Number(item.dataset.editItem)));return}
 const dep=e.target.closest('[data-edit-dept]');if(dep){editDept(cache.departments.find(x=>x.id===Number(dep.dataset.editDept)));return}
 const uu=e.target.closest('[data-edit-user]');if(uu){editUser(cache.users.find(x=>x.id===Number(uu.dataset.editUser)));return}
 const reset=e.target.closest('[data-reset-user]');if(reset){resetUser(cache.users.find(x=>x.id===Number(reset.dataset.resetUser)));return}
 if(e.target.closest('[data-close-modal]')){modalClose();return}
 if(e.target.closest('[data-remove-line]')){const line=e.target.closest('.ship-line');const parent=line.parentElement;if(parent.children.length>1)line.remove();else toast('At least one line is required','error');return}
 const add=e.target.closest('[data-add]');if(add){const type=add.dataset.add;if(type==='receive')$('#receiptLines').insertAdjacentHTML('beforeend',receiveLine());else $(`#${type==='issue'?'issueLines':type==='return'?'returnLines':'adjustLines'}`).insertAdjacentHTML('beforeend',issueLine(type!=='issue'));return}
 if(e.target.closest('#downloadBackup')){downloadBackup();return}
});
document.addEventListener('submit',async e=>{
 const form=e.target;if(!['entityForm','receiveForm','issueForm','returnForm','adjustForm','passwordForm','restoreForm'].includes(form.id))return;
 e.preventDefault();const button=form.querySelector('[type=submit]');button.disabled=true;
 try{
  if(form.id==='entityForm')await submitEntity(form);
  if(form.id==='receiveForm')await postShipment('IN',form,extractLines($('#receiptLines'),'receive'));
  if(form.id==='issueForm')await postShipment('OUT',form,extractLines($('#issueLines'),'issue'));
  if(form.id==='returnForm')await postShipment('RETURN',form,extractLines($('#returnLines'),'issue'));
  if(form.id==='adjustForm')await postShipment(new FormData(form).get('kind'),form,extractLines($('#adjustLines'),'issue'));
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
document.addEventListener('input',e=>{if(e.target.id==='itemFilter'){const items=filteredItems(e.target.value);$('#itemResults').innerHTML=table(inventoryColumns,itemRows(items))}
 if(e.target.id==='movementFilter')filterMovements()});
document.addEventListener('change',e=>{if(e.target.id==='movementType')filterMovements()});
function filterMovements(){const q=($('#movementFilter')?.value||'').toLowerCase(),t=$('#movementType')?.value||'';
 const results=cache.movements.filter(x=>(!t||x.kind===t)&&JSON.stringify(x).toLowerCase().includes(q));$('#movementResults').innerHTML=table(['Movement ID','Type','Paper reference','Source / destination','Item lines','Operator'],movementRows(results));}
$('#menuButton').addEventListener('click',()=>{$('#sidebar').classList.toggle('open');$('#dimOverlay').classList.toggle('show')});
$('#dimOverlay').addEventListener('click',closeMenu);
$('#accountButton').addEventListener('click',()=>{$('#accountMenu').classList.toggle('open');$('#accountButton').setAttribute('aria-expanded',$('#accountMenu').classList.contains('open'))});
$('#notifBtn').addEventListener('click',()=>toast(`${cache.dashboard?.low_stock||0} low-stock items · ${cache.dashboard?.expiry_soon||0} expiring batches`));
$('#logoutButton').addEventListener('click',async()=>{try{await api('/api/logout',{method:'POST'});location.href='/login.html'}catch(e){toast(e.message,'error')}});
$('#globalSearch').addEventListener('keydown',e=>{if(e.key==='Enter'){route('inventory');$('#itemFilter').value=e.target.value;$('#itemFilter').dispatchEvent(new Event('input',{bubbles:true}))}});
$('#entityModal').addEventListener('click',e=>{if(e.target.id==='entityModal')modalClose()});
window.addEventListener('hashchange',()=>{if(user)showPage(location.hash.slice(1))});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){modalClose();closeMenu();$('#accountMenu').classList.remove('open')}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('#globalSearch').focus()}});
(async function boot(){try{
 user=await api('/api/me');csrf=user.csrf;
 $('#userName').textContent=user.full_name;$('#userRole').textContent=user.role[0].toUpperCase()+user.role.slice(1);
 if(!can('users'))$$('[data-view="users"]').forEach(x=>x.style.display='none');
 if(!can('backup'))$$('[data-view="backup"]').forEach(x=>x.style.display='none');
 if(!can('item_write'))$$('[data-view="settings"]').forEach(x=>x.style.display='');
 await refreshData();showPage(location.hash.slice(1)||'overview');
}catch(e){$('#dashboardView').innerHTML=msg('Database unavailable',e.message);toast(e.message,'error')}})();

window.addEventListener('warehouse:languagechange',()=>document.querySelectorAll('time.localized-time[datetime]').forEach(el=>{el.textContent=fmtDate(el.getAttribute('datetime'))}));
