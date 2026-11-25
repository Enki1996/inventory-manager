/* Live V4.10 bilingual warehouse prototype: all changes go through the server and SQLite database. */
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
let user=null, csrf='', view='', cache={items:[],departments:[],batches:[],movements:[],users:[],dashboard:null,books:{},units:{},staff:[]}, toastTimer;
let inlineNewItem=null; // Pending shipment line; kept intact while the item modal is open.
const headers={overview:'Warehouse Overview',inventory:'Inventory',receiving:'Receive Shipments',distribution:'Prepare outgoing shipment',returns:'Stock Adjustments',movements:'Movement History',batches:'Batches & Expiry',departments:'Departments',reports:'Reports',users:'Users & Permissions',backup:'Backup & Restore',settings:'Settings'};
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
  const endpoints=['items','departments','batches','movements','dashboard','books','units','staff-directory'];
  const rows=await Promise.all(endpoints.map(path=>api('/api/'+path)));
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
 const q=$('#itemFilter')?.value||'';
 const branch=$('#itemBranchFilter')?.value||'';
 const book=$('#itemBookFilter')?.value||'';
 const matched=filteredItems(q).filter(it=>(!branch||it.branch===branch)&&(!book||it.category===book));
 const results=$('#itemResults');if(results)results.innerHTML=table(inventoryColumns,itemRows(matched));
}
const inventoryColumns=['Item / scientific name / SKU','Generic / other names','Manufacturer / made on','Unit price (IQD)','Warehouse branch','Book / register category','Reference expiry','Warehouse stock','Batches','Status','Actions'];
function itemRows(items){return items.map(it=>`<tr>
 <td><strong>${E(it.trade_name||it.name)}</strong>${it.trade_name?`<div class="tiny">${E(it.name)}</div>`:""}<div class="tiny">${E(it.sku)}</div></td>
 <td><strong>${E(it.generic_name||'—')}</strong>${it.information?`<div class="tiny item-alias" title="${E(it.information)}">${E(it.information)}</div>`:''}</td>
 <td>${E(it.manufacturer||'—')}${it.manufacture_date?`<div class="tiny">${E(it.manufacture_date)}</div>`:''}</td>
 <td><strong>${priceLabel(it.price_fils)}</strong><div class="tiny">${E(it.unit)}</div></td>
 <td>${badge(branchName(it.branch),it.branch?'blue':'warning')}</td>
 <td>${E(it.category)}<div class="tiny">${E(it.unit)}</div></td>
 <td>${E(it.expiry_date||'—')}</td>
 <td><strong>${N(it.stock)}</strong> ${E(it.unit)}</td>
 <td>${N(it.batch_count)}</td>
 <td>${Number(it.min_stock)>0&&Number(it.stock)<Number(it.min_stock)?badge('Low stock','warning'):badge(it.active?'Active':'Inactive',it.active?'':'danger')}</td>
 <td>${canEditBranch(it.branch)?`<div class="db-small-actions"><button data-edit-item="${it.id}">Edit</button></div>`:'—'}</td>
 </tr>`)}
function departmentRows(depts){return depts.map(it=>`<tr><td><strong>${E(it.name)}</strong></td><td>${badge(it.active?'Active':'Inactive',it.active?'':'danger')}</td><td>${can('department_write')?`<div class="db-small-actions"><button data-edit-dept="${it.id}">Edit</button></div>`:'—'}</td></tr>`)}
const routeNames={department_issue:'Hospital departments',external_transfer_out:'External transfer',pharmacy_transfer_out:'Transfer to Pharmacy Department',pharmacy_receipt:'Pharmacy Department',purchase_receipt:'Purchases',external_transfer_in:'External transfer received',internal_return:'Internal department return'};
function movementRows(movements){return movements.map(m=>{
 const pending=m.paperwork_pending===1;
 const action=pending&&can('movement_write')?`<div class="db-small-actions" style="margin-top:8px"><button type="button" data-complete-paperwork="${m.id}">Complete missing papers</button></div>`:'';
 const docs=`<strong>${E(m.paper_ref||'—')}</strong>${m.dispatch_ref?`<div class="tiny">Dispatch/receipt: ${E(m.dispatch_ref)}</div>`:''}${pending?`<div>${badge('Emergency · papers pending','warning')}</div>`:''}${m.paperwork_completed_at?`<div class="tiny">Papers completed: ${D(m.paperwork_completed_at)}</div>`:''}${action}`;
 const recipient=m.department_name||m.external_destination||m.source||'—';
 return `<tr><td><strong>${E(m.code)}</strong><div class="tiny">${D(m.created_at)}</div></td><td>${badge(typeLabel[m.kind]||m.kind,m.kind==='OUT'?'blue':'neutral')}<div class="tiny">${E(routeNames[m.route]||'Legacy movement')}</div></td><td>${docs}</td><td>${E(recipient)}${m.trusted_pharmacist_name||m.trusted_pharmacist_username?`<div class="tiny">Trusted pharmacist: ${E(m.trusted_pharmacist_name||m.trusted_pharmacist_username)}</div>`:''}${m.authorization_ref?`<div class="tiny">Authorization letter no.: ${E(m.authorization_ref)}</div>`:''}</td><td>${m.lines.map(l=>`<div><strong>${E(l.item_name)}</strong> · ${E(l.batch_no)} · ${N(l.qty)} ${E(l.unit)}<div class="tiny">Exp: ${E(l.expiry_date||'—')} · ${priceLabel(l.unit_price_fils)}</div></div>`).join('<div style="height:5px"></div>')}</td><td>${E(m.creator)}</td></tr>`;
})}

function batchRows(rows){return rows.map(b=>`<tr><td><strong>${E(b.item_name)}</strong><div class="tiny">${E(b.sku)}</div></td><td>${E(branchName(b.branch))}</td><td>${E(b.batch_no)}</td><td>${E(b.expiry_date||'Not applicable')}</td><td>${priceLabel(b.unit_price_fils)}</td><td><strong>${N(b.on_hand)}</strong> ${E(b.unit)}</td><td>${b.expiry_date&&b.expiry_date<todayBaghdad()?badge('Expired','danger'):b.on_hand===0?badge('Empty'):badge('Available','blue')}</td></tr>`)}
function overview(){
 const s=cache.dashboard;
 const metrics=[['Registered items',s.items,'Products in catalog','package'],['Warehouse units',s.stock,'Total stock across all batches','packages'],['Active departments',s.departments,'Distribution destinations','building'],['Recorded movements',s.movements,'Permanent transaction log','history']];
 const kpis=`<div class="db-kpis">${metrics.map(([label,num,desc,icon])=>`<div class="db-kpi"><span class="name">${I(icon)} ${E(label)}</span><span class="num">${N(num)}</span><span class="desc">${E(desc)}</span></div>`).join('')}</div>`;
 const alerts=cache.items.filter(i=>i.active&&i.min_stock>0&&i.stock<i.min_stock);
 const exp=cache.batches.filter(b=>b.on_hand>0&&b.expiry_date&&b.expiry_date>=todayBaghdad()&&b.expiry_date<=new Date(Date.now()+60*864e5).toISOString().slice(0,10));
 return `<div class="db-decor">${head('Welcome back, '+user.full_name,'Your central warehouse is connected to the local database. Inventory and movements below update after every saved transaction.')}
 <div class="db-actions">${can('item_write')&&(user.role==='admin'||user.branch)?`<button class="db-btn" data-new="item">${I('package')} Add item</button>`:''}${can('department_write')?`<button class="db-btn secondary" data-new="dept">${I('building')} Add department</button>`:''}${can('movement_write')?`<button class="db-btn secondary" data-go="receiving">${I('incoming')} Receive shipment</button><button class="db-btn secondary" data-go="distribution">${I('outgoing')} Distribute stock</button>`:''}</div></div>
 ${user.role!=='admin'&&!user.branch?'<div class="db-alert"><strong>Warehouse branch not assigned.</strong> Ask your administrator to assign your account to one branch before managing stock.</div>':''}
 ${user.must_change_password?`<div class="db-alert"><strong>Change your temporary password.</strong> This account was created with a temporary login. Use Settings → Change Password before entering important data.</div>`:''}
 ${kpis}<div class="db-layout"><div>${panel('Recent warehouse movements',table(['Movement','Type','Paper reference','From / To','Lines','By'],movementRows(cache.movements.slice(0,6))),'history')}</div><div>${panel('Attention needed',`<div class="db-help">${I('warning')} ${alerts.length} item(s) under the reorder threshold · ${exp.length} batch(es) expiring in the next 60 days.</div><div style="margin-top:15px">${alerts.slice(0,5).map(i=>`<div style="display:flex;justify-content:space-between;padding:10px;border-bottom:1px solid #eaf1f4;font-size:11px"><span>${E(i.name)}</span><strong>${N(i.stock)} / ${N(i.min_stock)}</strong></div>`).join('')||'<p class="muted-hint">No low-stock alerts at the moment.</p>'}</div>`,'warning')}
 ${panel('Quick navigation',`<div class="db-actions"><button class="db-btn secondary" data-go="inventory">Inventory</button><button class="db-btn secondary" data-go="departments">Departments</button><button class="db-btn secondary" data-go="movements">Movement history</button></div>`,'dashboard')}</div></div>`
}
function inventory(){return `${head('Item inventory','Create products independently of stock receipts. Stock is then added to its matching batch through Receive Shipments.',can('item_write')&&(user.role==='admin'||user.branch)?`<button class="db-btn" data-new="item">${I('package')} New item</button>`:'')}${panel('Product catalog',`<div class="db-note"><span>Three fixed branches · Medication, Medical Supplies, Surgical Instruments.</span> <span>Books are predefined for each branch; select the matching register.</span> ${user.role==='admin'?'<span>Administrators can classify unassigned legacy items.</span>':`<span>Your assigned branch:</span> <strong>${E(branchName(user.branch))}</strong>`}</div><div class="db-toolbar">${inp('filter','Search scientific, generic, common name, company or code...','search','id="itemFilter"')}<select class="db-select" id="itemBranchFilter"><option value="">All branches</option>${branchList('').replace('<option value="">Select a branch</option>','')}</select><select class="db-select" id="itemBookFilter">${filterBookOptions()}</select><span class="muted-hint">${cache.items.length} registered items</span></div><div id="itemResults">${table(inventoryColumns,itemRows(cache.items))}</div>`,'package')}`}
function departments(){return `${head('Hospital departments','The approved departments are preloaded once. You can add more, rename them or deactivate them without changing movement history.',can('department_write')?`<button class="db-btn" data-new="dept">${I('building')} Add department</button>`:'')}${panel('Saved departments',`<div class="db-toolbar">${inp('dept_filter','Search departments...','search','id="departmentFilter"')}<span class="muted-hint">${cache.departments.filter(d=>d.active).length} active departments</span></div><div id="departmentResults">${table(['Department','Status','Actions'],departmentRows(cache.departments))}</div>`,'building')}`}
function filterDepartmentTable(){const input=$('#departmentFilter'),results=$('#departmentResults');if(!input||!results)return;const q=normalizeItemSearch(input.value);results.innerHTML=table(['Department','Status','Actions'],departmentRows(cache.departments.filter(d=>normalizeItemSearch(d.name).includes(q))));}
function batches(){return `${head('Batches and expiration','Stock quantity is recorded separately for every batch. Never issue expired lots.')}${panel('Batch register',table(['Product','Warehouse branch','Batch number','Expiration','Unit price (IQD)','Warehouse balance','Status'],batchRows(cache.batches)),'calendar')}`}
function movements(){return `${head('Movement history','Every receipt, issue, return and adjustment has a permanent movement ID plus the original document reference.')}${panel('Transaction register',`<div class="db-toolbar">${inp('movement_filter','Search requisition, item or user...','search','id="movementFilter"')}<select class="db-select" id="movementType" style="max-width:180px"><option value="">All types</option><option value="IN">Incoming</option><option value="OUT">Distributions</option><option value="RETURN">Returns</option><option value="ADJUST_PLUS">Adjustment (+)</option><option value="ADJUST_MINUS">Adjustment (−)</option></select></div><div id="movementResults">${table(['Movement ID','Type','Paper refs','Source / destination','Item lines','Operator'],movementRows(cache.movements))}</div>`,'history')}`}
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
 ${field('Batch number / lot',`<select class="db-select" data-key="batch_id" data-issue-batch required><option value="">Choose product first</option></select>`)}
 ${field('Expiry date',`<input type="date" class="db-input" data-issue-expiry readonly aria-label="Expiry date of selected lot">`)}
 ${field('Quantity',`<input type="number" class="db-input" data-key="qty" data-issue-qty min="1" step="1" required placeholder="0">`)}
 ${field('Price — دينار',`<input type="number" class="db-input" data-key="price_dinars" min="0" max="999999999" step="1" required placeholder="0">`)}
 ${field('Price — فلس',`<input type="number" class="db-input" data-key="price_fils_component" min="0" max="999" step="1" required placeholder="0">`)}
 <button class="db-btn danger small" type="button" data-remove-line aria-label="Remove product">×</button>
 <div class="fefo-line-notice" data-fefo-notice role="status" aria-live="polite" hidden></div></div>`;
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
  else if(days<=60){message.classList.add('warning');message.textContent=(ar?'⚠ أقرب وجبة للصرف؛ متبقي ':'⚠ Earliest lot to issue; ')+N(days)+(ar?' يوم. ':' days left. ')+closest;}
  else{message.classList.add('success');message.textContent=(ar?'✓ صرف حسب أقرب تاريخ صلاحية: ':'✓ FEFO priority: ')+closest;}
 }
 const wrap=form.querySelector('[data-fefo-override-wrap]');
 if(wrap){wrap.hidden=!warnings.length;const reason=wrap.querySelector('[name="fefo_override_reason"]');if(reason)reason.required=!!warnings.length;}
 const top=form.querySelector('[data-fefo-summary]');
 if(top){const urgent=cache.batches.filter(b=>b.on_hand>0&&b.item_active&&inMyBranch(b.branch)&&b.expiry_date&&b.expiry_date>=todayBaghdad()&&fefoDateDays(b.expiry_date)<=60);
  top.textContent=ar?`قاعدة الصرف: الأقرب انتهاءً أولاً (FEFO). توجد ${urgent.length} وجبة صالحة تنتهي خلال ٦٠ يوماً في المخزن.`:
  `Issue earliest-expiring usable lots first (FEFO). ${urgent.length} usable lot(s) expire within 60 days.`;
 }
}
function syncIssueProduct(line, preferredBatch=null){
 if(!line||!line.matches('.issue-detailed'))return;
 const iid=Number(line.querySelector('[data-issue-product]')?.value||0);
 const opts=eligibleLots(iid);
 const sel=line.querySelector('[data-issue-batch]'),old=preferredBatch==null?Number(sel.value):Number(preferredBatch);
 sel.innerHTML=selectOptions(opts.map((b,i)=>{const days=fefoDateDays(b.expiry_date);
  const mark=i===0?'★ FEFO · ':'';
  const near=days!==null&&days<=60?'⚠ ':'';
  return {value:b.id,label:`${mark}${near}${b.batch_no} · Exp ${b.expiry_date||'unknown'} · ${N(b.on_hand)} ${b.unit} · ${priceLabel(b.unit_price_fils)}`};
 }),'','Select received lot');
 sel.value=opts.some(b=>b.id===old)?String(old):opts.length?String(opts[0].id):'';
 syncIssueBatch(line);window.HWLang?.apply();
}
function syncIssueBatch(line){
 if(!line||!line.matches('.issue-detailed'))return;
 const batch=cache.batches.find(b=>b.id===Number(line.querySelector('[data-issue-batch]')?.value));
 const expiry=line.querySelector('[data-issue-expiry]');if(expiry)expiry.value=batch?.expiry_date||'';
 const qty=line.querySelector('[data-issue-qty]');if(qty){qty.max=batch?.on_hand||'';if(batch&&Number(qty.value)>batch.on_hand)qty.value=String(batch.on_hand);}
 const price=batch?.unit_price_fils;
 const d=line.querySelector('[data-key="price_dinars"]'),f=line.querySelector('[data-key="price_fils_component"]');
 if(d)d.value=price==null?'':String(Math.floor(price/1000));
 if(f)f.value=price==null?'':String(price%1000);
 updateFefoNotices();
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
</form><p class="db-help">Internal department returns add the selected batch quantity back to the warehouse; other incoming routes register incoming batches.</p>`,'incoming')}`}
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
function users(){if(!can('users'))return msg('Access denied','Only administrators manage staff accounts.');const rows=cache.users.map(x=>`<tr><td><strong>${E(x.username)}</strong><div class="tiny">${E(x.full_name)}</div></td><td>${badge(x.role,x.role==='admin'?'blue':'neutral')}</td><td>${E(x.role==='admin'?'All branches':branchName(x.branch))}</td><td>${badge(x.is_active?'Active':'Disabled',x.is_active?'':'danger')}</td><td>${x.must_change_password?'Temporary':'Updated'}</td><td>${x.id!==user.id?`<div class="db-small-actions"><button data-edit-user="${x.id}">Role / status</button><button data-reset-user="${x.id}">Reset password</button></div>`:'Current account'}</td></tr>`);
return `${head('Users and permissions','Only administrators can create staff accounts. Rights are checked by the backend on every action.',`<button class="db-btn" data-new="user">${I('users')} Create account</button>`)}<div class="db-note">Administrators manage all branches. Managers can edit items and correct stock only in their assigned branch. Operators can receive and distribute stock only in their branch. Viewers are read-only. Each non-admin account must have one assigned branch.</div>${panel('Warehouse accounts',table(['Username / name','Role','Assigned branch','Status','Password','Actions'],rows),'users')}`}
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
 $('#topTitle').textContent=headers[next];$('#dashboardView').innerHTML=pages[next]();if(next==='distribution'){syncOutgoingDestination($('#issueForm'));updateFefoNotices();}if(next==='receiving'){const f=$('#receiveForm');const lines=f?.querySelector('#receiptLines');if(lines)lines.dataset.returnMode='0';syncIncomingRoute(f)}window.HWLang?.apply();closeMenu();
 if(next==='settings'&&can('item_write'))loadAudit();
 window.scrollTo({top:0,behavior:'instant'});
}
function route(next){location.hash=next;showPage(next)}
function closeMenu(){$('#sidebar').classList.remove('open');$('#dimOverlay').classList.remove('show')}
function modalOpen(title,description,fields,formType,button='Save changes'){
 const modal=$('#entityModal');modal.innerHTML=`<div class="modal-body ${formType.startsWith('item:')?'item-dialog':''}" role="dialog" aria-modal="true" aria-label="${E(title)}"><div class="db-actions" style="justify-content:space-between;align-items:center"><h2>${E(title)}</h2><button class="db-btn secondary small" type="button" data-close-modal>Close ×</button></div><p>${E(description)}</p><form id="entityForm" data-entity="${formType}" class="db-form"><div class="db-grid">${fields}</div><div class="modal-footer"><button class="db-btn secondary" type="button" data-close-modal>Cancel</button><button class="db-btn" type="submit">${E(button)}</button></div></form></div>`;
 modal.classList.add('open');modal.setAttribute('aria-hidden','false');syncUserBranchField($('#entityForm'));window.HWLang?.apply();$('.db-input',modal)?.focus();
}
function modalClose(){const el=$('#entityModal');el.classList.remove('open');el.innerHTML='';el.setAttribute('aria-hidden','true')}
function editItem(it=null){
 const b=it?.branch||user.branch||'';
 const legacyWarn=it?.category&&!approvedBook(it.branch,it.category)?`<small class="legacy-book-warning">Existing category: ${E(it.category)} — please choose an approved book for this branch.</small>`:'';
 // Fields are in the EXACT reading/tab order agreed with the warehouse team.
 // RTL layout places the first member of each pair on the right.
 const wide=s=>s.replace('class="db-field"','class="db-field wide"');
 const f=[
  wide(field('Warehouse branch',branchField('branch',b,user.role==='admin'), 'Choose your assigned warehouse branch first.')),
  field('Trade name',`<input name="trade_name" class="db-input" maxlength="160" value="${E(it?.trade_name||'')}" placeholder="Commercial or brand name">`).replace('class="db-field"','class="db-field" data-med-trade'),
  field('Scientific name',`<input name="name" class="db-input" maxlength="160" value="${E(it?.name||'')}" placeholder="Scientific / active ingredient name">`).replace('class="db-field"','class="db-field" data-med-scientific'),
  wide(field('Item name',`<input name="name" class="db-input" maxlength="160" value="${E(it?.name||'')}" placeholder="Name of the supply / instrument">`)).replace('class="db-field wide"','class="db-field wide" data-other-name'),
  field('Stock unit',`<select name="unit" class="db-select" data-item-unit required>${unitOptions(b,it?.unit||'')}</select>`),
  field('Book / register category',`<select name="category" class="db-select" data-item-book required>${optionsForBooks(b,it?.category||'')}</select>${legacyWarn}`),
  field('Batch number',`<input name="batch_no" class="db-input" maxlength="90" required value="${E(it?.initial_batch_no||it?.display_batch_no||'')}" placeholder="Batch / lot number">`),
  field('Expiration date',`<input name="expiry_date" class="db-input" type="date" required value="${E(it?.expiry_date||'')}">`, 'Required for every new item.'),
  field('Manufacture date (optional)',`<input name="manufacture_date" class="db-input" type="date" value="${E(it?.manufacture_date||'')}">`),
  field('Manufacturer company',`<input name="manufacturer" class="db-input" maxlength="160" value="${E(it?.manufacturer||'')}" placeholder="Company name">`),
  field('Price — دينار',`<input name="price_dinars" class="db-input" type="number" min="0" max="999999999" step="1" required value="${it?.price_fils==null?'':Math.floor(it.price_fils/1000)}" placeholder="0">`, 'IQD per stock unit.'),
  field('Price — فلس',`<input name="price_fils_component" class="db-input" type="number" min="0" max="999" step="1" required value="${it?.price_fils==null?'':it.price_fils%1000}" placeholder="0 to 999">`, '1000 fils = 1 dinar.'),
  wide(field('Information / alternate names',`<textarea name="information" class="db-textarea" maxlength="2000" rows="4" placeholder="Common names, Iraqi slang, abbreviations, alternate spellings...">${E(it?.information||'')}</textarea>`, 'All alternate names are searchable.'))
 ];
 if(it)f.push(wide(field('Active status',`<select class="db-select" name="active"><option value="1" ${it.active?'selected':''}>Active</option><option value="0" ${!it.active?'selected':''}>Inactive</option></select>`)));
 modalOpen(it?'Edit item':'Register item','Select the warehouse branch first. Only the relevant names, approved units and official books will appear. New items start with zero stock.',f.join(''),`item:${it?.id||'new'}`);
 const form=$('#entityForm');form.classList.add('item-form-grid');
 form.dataset.originalBranch=it?.branch||'';form.dataset.originalUnit=it?.unit||'';
 const dlg=form.closest('.modal-body');
 dlg.querySelector('h2')?.insertAdjacentHTML('beforeend',' <span class="form-version" translate="no">V4.9</span>');
 syncItemBranchFields(form,it?.category||'',it?.unit||'');
 window.HWLang?.apply();
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
   const batch=ctx.line.querySelector('[data-key="batch_no"]');if(batch)batch.value=d.batch_no;
   const expiry=ctx.line.querySelector('[data-key="expiry_date"]');if(expiry)expiry.value=d.expiry_date;
   prefillReceiptPrice(ctx.line);
   inlineNewItem=null;toast('Item registered. Add its received quantity to the shipment.');
  }else if(ctx.mode==='issue'){
   const product=ctx.line.querySelector('[data-issue-product]');if(product){product.value=String(createdItem.id);syncIssueProduct(ctx.line);}
   quickReceiptForNewItem(createdItem.id,ctx);
   toast('Item registered with zero stock. Record an incoming receipt to issue it.');
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
 const v=e.target.closest('[data-view],[data-go]');if(v){route(v.dataset.view||v.dataset.go);return}
 const trigger=e.target.closest('[data-dept-trigger]');if(trigger){const picker=trigger.closest('[data-dept-picker]');if(picker.querySelector('[data-dept-popup]').hidden)openDepartmentPicker(picker);else closeDepartmentPicker(picker);return}
 const option=e.target.closest('[data-dept-option]');if(option){selectDepartment(option.closest('[data-dept-picker]'),option);return}
 if(!e.target.closest('[data-dept-picker]'))document.querySelectorAll('[data-dept-picker]').forEach(closeDepartmentPicker);
 const pending=e.target.closest('[data-complete-paperwork]');if(pending){completeMovementPapers(cache.movements.find(m=>m.id===Number(pending.dataset.completePaperwork)));return}
 const inline=e.target.closest('[data-inline-item]');
 if(inline){inlineNewItem={mode:inline.dataset.inlineItem,line:inline.closest('.ship-line')};editItem();return}
 const n=e.target.closest('[data-new]');if(n){inlineNewItem=null;if(n.dataset.new==='item')editItem();if(n.dataset.new==='dept')editDept();if(n.dataset.new==='user')createUser();return}
 const item=e.target.closest('[data-edit-item]');if(item){editItem(cache.items.find(x=>x.id===Number(item.dataset.editItem)));return}
 const dep=e.target.closest('[data-edit-dept]');if(dep){editDept(cache.departments.find(x=>x.id===Number(dep.dataset.editDept)));return}
 const uu=e.target.closest('[data-edit-user]');if(uu){editUser(cache.users.find(x=>x.id===Number(uu.dataset.editUser)));return}
 const reset=e.target.closest('[data-reset-user]');if(reset){resetUser(cache.users.find(x=>x.id===Number(reset.dataset.resetUser)));return}
 if(e.target.closest('[data-close-modal]')){if($('#entityForm')?.dataset.entity?.startsWith('quickreceipt:'))toast('Item saved, but it cannot be issued until incoming stock is recorded.','error');modalClose();inlineNewItem=null;return}
 const priority=e.target.closest('[data-fefo-pick]');if(priority){const line=priority.closest('[data-issue-line]');const select=line?.querySelector('[data-issue-batch]');if(select){select.value=priority.dataset.fefoPick;syncIssueBatch(line);}return;}
 if(e.target.closest('[data-remove-line]')){const line=e.target.closest('.ship-line');const parent=line.parentElement;if(parent.children.length>1)line.remove();else toast('At least one line is required','error');updateFefoNotices();return}
 const add=e.target.closest('[data-add]');if(add){const type=add.dataset.add;if(type==='receive'){$('#receiptLines').insertAdjacentHTML('beforeend',$('#receiptLines').dataset.returnMode==='1'?issueLine(true):receiveLine());}else $(`#${type==='issue'?'issueLines':'adjustLines'}`).insertAdjacentHTML('beforeend',issueLine(type!=='issue'));return}
 if(e.target.closest('#downloadBackup')){downloadBackup();return}
});
document.addEventListener('submit',async e=>{
 const form=e.target;if(!['entityForm','receiveForm','issueForm','adjustForm','passwordForm','restoreForm'].includes(form.id))return;
 e.preventDefault();const button=form.querySelector('[type=submit]');button.disabled=true;
 try{
  if(form.id==='entityForm')await submitEntity(form);
  if(form.id==='receiveForm')await postShipment('IN',form,extractLines($('#receiptLines'),$('#receiptLines').dataset.returnMode==='1'?'issue':'receive'));
  if(form.id==='issueForm')await postShipment('OUT',form,extractLines($('#issueLines'),'issue'));
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
document.addEventListener('input',e=>{if(e.target.id==='itemFilter')filterInventory();
 if(e.target.id==='movementFilter')filterMovements();
 if(e.target.id==='departmentFilter')filterDepartmentTable();
 if(e.target.matches('#issueForm [data-issue-qty]'))updateFefoNotices();
 if(e.target.matches('[data-dept-search]'))filterDeptPicker(e.target.closest('[data-dept-picker]'));});
document.addEventListener('change',e=>{
 if(e.target.matches('[data-issue-product]'))syncIssueProduct(e.target.closest('[data-issue-line]'));
 if(e.target.matches('[data-issue-batch]'))syncIssueBatch(e.target.closest('[data-issue-line]'));
 if(e.target.id==='movementType')filterMovements();
 if(e.target.id==='itemBranchFilter') { const filter=$('#itemBookFilter');if(filter){filter.innerHTML=filterBookOptions(e.target.value);filter.value=''}filterInventory(); }
 if(e.target.id==='itemBookFilter')filterInventory();
 if(e.target.matches('#issueForm input[name="route"]')||e.target.matches('#issueForm input[name="emergency_pending"]'))syncOutgoingDestination(e.target.closest('form'));
 if(e.target.matches('#receiveForm input[name="route"]'))syncIncomingRoute(e.target.closest('form'));
 if(e.target.matches('[data-receive-line] select[data-key="item_id"]'))prefillReceiptPrice(e.target.closest('[data-receive-line]'));
 if(e.target.matches('#entityForm select[name="branch"]'))syncItemBranchFields(e.target.closest('#entityForm'));
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
$('#menuButton').addEventListener('click',()=>{$('#sidebar').classList.toggle('open');$('#dimOverlay').classList.toggle('show')});
$('#dimOverlay').addEventListener('click',closeMenu);
$('#accountButton').addEventListener('click',()=>{$('#accountMenu').classList.toggle('open');$('#accountButton').setAttribute('aria-expanded',$('#accountMenu').classList.contains('open'))});
$('#notifBtn').addEventListener('click',()=>toast(`${cache.dashboard?.low_stock||0} low-stock items · ${cache.dashboard?.expiry_soon||0} expiring batches`));
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
 if(e.key==='Escape'){modalClose();inlineNewItem=null;closeMenu();$('#accountMenu').classList.remove('open')}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('#globalSearch').focus()}});
(async function boot(){try{
 user=await api('/api/me');csrf=user.csrf;
 $('#userName').textContent=user.full_name;$('#userRole').textContent=user.role[0].toUpperCase()+user.role.slice(1);
 if(!can('users'))$$('[data-view="users"]').forEach(x=>x.style.display='none');
 if(!can('backup'))$$('[data-view="backup"]').forEach(x=>x.style.display='none');
 if(!can('item_write'))$$('[data-view="settings"]').forEach(x=>x.style.display='');
 await refreshData();showPage(location.hash.slice(1)||'overview');
}catch(e){$('#dashboardView').innerHTML=msg('Database unavailable',e.message);toast(e.message,'error')}})();

window.addEventListener('warehouse:languagechange',()=>{document.querySelectorAll('time.localized-time[datetime]').forEach(el=>{el.textContent=fmtDate(el.getAttribute('datetime'))});if(view==='inventory')filterInventory();if(view==='distribution')updateFefoNotices()});
