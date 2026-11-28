(()=>{
 const root=document.getElementById('backupMonitor');if(!root)return;
 let status=null, received=0, unavailable=false;
 const el=id=>document.getElementById('backupMonitor'+id);
 const ar=()=>document.documentElement.lang==='ar';
 const t=(a,b)=>ar()?a:b;
 const date=v=>v?new Intl.DateTimeFormat(ar()?'ar-IQ':'en-GB',{timeZone:'Asia/Baghdad',dateStyle:'short',timeStyle:'short'}).format(new Date(v)):t('لم يُسجل بعد','Not recorded');
 function draw(){
  el('Title').textContent=t('النسخ التلقائي · Google Drive','Auto backup · Google Drive');
  if(!status||unavailable){root.dataset.state=unavailable?'unavailable':'loading';el('State').textContent=unavailable?t('تعذر قراءة الحالة','Status unavailable'):t('جارٍ قراءة الحالة','Loading status');el('Next').textContent='';el('Countdown').textContent='';el('Previous').textContent='';el('Last').textContent='';return;}
  root.dataset.state=status.state;
  const labels={connected:t('متصل · موعد مجدول','Connected · scheduled'),error:t('خطأ في النسخ الاحتياطي','Backup error'),missed:t('لم يكتمل النسخ المجدول','Scheduled backup missed'),disconnected:t('غير متصل','Disconnected'),unconfigured:t('النسخ التلقائي غير مهيأ','Auto backup not configured')};
  el('State').textContent=labels[status.state]||'—';
  const enabled=!['unconfigured','disconnected'].includes(status.state);
  let secs=Math.max(0,Math.ceil((Date.parse(status.next_utc)-Date.parse(status.server_utc)-(Date.now()-received))/1000));
  el('Next').textContent=enabled?t('الموعد المجدول التالي','Next scheduled time')+' · '+date(status.next_utc):'';
  el('Countdown').textContent=enabled?[Math.floor(secs/3600),Math.floor(secs/60)%60,secs%60].map(x=>String(x).padStart(2,'0')).join(':'):'';
  const previous={complete:t('مكتمل','Completed'),pending:t('بانتظار التأكيد','Awaiting confirmation'),missed:t('لم يكتمل','Not completed'),unknown:t('غير معروف','Unknown')};
  el('Previous').textContent=t('الموعد السابق: ','Previous slot: ')+(previous[status.previous_scheduled]||'—');
  el('Last').textContent=t('آخر نسخة ناجحة: ','Last success: ')+date(status.last_success_utc)+(status.state==='error'&&status.last_failure_utc?' · '+t('آخر خطأ: ','Last failure: ')+date(status.last_failure_utc):'');
 }
 async function refresh(){try{const r=await fetch('/api/backup-summary',{credentials:'same-origin',cache:'no-store'});if(!r.ok)throw Error();status=await r.json();received=Date.now();unavailable=false;}catch(e){unavailable=true;}draw();}
 refresh();setInterval(refresh,15000);setInterval(draw,1000);window.addEventListener('warehouse:languagechange',draw);
})();
