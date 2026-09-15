(() => {'use strict';
 const $=id=>document.getElementById(id), dialog=$('loan-batch'); if(!dialog)return;
 let rows=[],busy=false,stop=false,loaded=false,page=1,phase='',generation=0;
 const labels={pending:'Chưa đối soát',ready:'Đủ điều kiện',error:'Lỗi',existing:'Đã có bản chuyển',done:'Chuyển thành công',unknown:'Chưa xác định kết quả'};
 const money=value=>Number(value||0).toLocaleString('vi-VN')+' đ';
 const node=(tag,value)=>{const e=document.createElement(tag);e.textContent=value;return e;};
 function selected(){return rows.filter(r=>r.selected&&r.state==='ready');}
 function resetAck(){$('batch-ack').checked=false;}
 function filtered(){const q=$('batch-query').value.trim().toLocaleLowerCase('vi'),filter=$('batch-filter').value;return rows.filter(r=>(filter==='all'||r.state===filter||(filter==='error'&&r.state==='unknown'))&&[r.sku,r.phone,r.cust_id||''].join(' ').toLocaleLowerCase('vi').includes(q));}
 function controls(){
   const count=selected().length;
   for(const id of ['batch-reload','batch-review','batch-select','batch-clear','batch-ack','batch-close','batch-exceptions'])$(id).disabled=busy;
   $('batch-review').disabled=busy||!loaded||!rows.some(r=>!['existing','done'].includes(r.state));
   $('batch-stop').disabled=!busy||stop;
   $('batch-submit').disabled=busy||!loaded||!count||rows.some(r=>r.state==='unknown')||!$('batch-ack').checked||!!dialog.dataset.readonly;
   $('batch-submit').textContent='Xác nhận chuyển '+count+' phiếu';
 }
 function render(){
   const list=filtered(),pages=Math.max(1,Math.ceil(list.length/50));page=Math.min(page,pages);
   $('batch-page').textContent=`Trang ${page}/${pages} · ${list.length} phiếu theo bộ lọc`;
   $('batch-prev').disabled=page<=1;$('batch-next').disabled=page>=pages;
   const counts=rows.reduce((a,r)=>(a[r.state]=(a[r.state]||0)+1,a),{});
   $('batch-counts').textContent=`${rows.length} phiếu đang cầm · ${counts.ready||0} đủ điều kiện · ${(counts.error||0)+(counts.unknown||0)} lỗi/chưa xác định · ${counts.existing||0} đã có bản · ${counts.done||0} thành công đợt này · Đã chọn ${selected().length} phiếu trên toàn bộ danh sách.`;
   const body=$('batch-rows');body.replaceChildren();
   for(const r of list.slice((page-1)*50,page*50)){
     const tr=document.createElement('tr'),pick=document.createElement('td'),check=document.createElement('input');check.type='checkbox';check.checked=!!r.selected;check.disabled=busy||r.state!=='ready';check.setAttribute('aria-label','Chọn '+r.sku);check.addEventListener('change',()=>{r.selected=check.checked;resetAck();render();});pick.append(check);tr.append(pick);
     const code=node('td',r.sku);code.append(node('small',r.date1?new Date(r.date1).toLocaleDateString('vi-VN'):'Thiếu ngày'));tr.append(code);
     const customer=node('td',r.phone||'Thiếu SĐT');customer.append(node('small',r.cust_id||'Thiếu CustID'));tr.append(customer,node('td',money(r.value)));
     const status=node('td',labels[r.state]);status.className=r.state==='error'||r.state==='unknown'?'conversion-error':r.state==='ready'?'batch-ready':'';status.append(node('small',r.message||''));tr.append(status);
     const detail=document.createElement('td'),button=node('button','Đối soát / Chi tiết');button.type='button';button.className='btn btn-small';button.disabled=busy;button.addEventListener('click',()=>inspectOne(r));detail.append(button);tr.append(detail);body.append(tr);
   }
   if(!list.length){const tr=document.createElement('tr'),td=node('td',loaded?'Không có phiếu phù hợp.':'Đang tải danh sách…');td.colSpan=6;tr.append(td);body.append(tr);}
   controls();
 }
 async function json(url,options){
   const response=await fetch(url,options);let data;
   try{data=await response.json();}catch(_){throw Object.assign(Error('Máy chủ chưa trả kết quả xác định. Tải lại danh sách và đối soát trước khi tiếp tục.'),{uncertain:true});}
   if(!response.ok)throw Object.assign(Error(data.error||'Chưa hoàn tất yêu cầu.'),{uncertain:response.status!==409&&response.status!==400});return data;
 }
 function start(name){busy=true;stop=false;phase=name;resetAck();render();}
 function finish(){busy=false;phase='';render();}
 async function load(){
   if(busy)return;start('load');loaded=false;rows=[];page=1;$('batch-detail').open=false;let after=0,ceiling;const token=++generation;
   try{do{const params=new URLSearchParams({after});if(ceiling!==undefined)params.set('ceiling',ceiling);const data=await json(dialog.dataset.list+'?'+params);if(token!==generation)return;ceiling=data.ceiling;rows.push(...data.rows.map(r=>({...r,state:r.loan_id?'existing':'pending',message:r.loan_id?'cd_loans #'+r.loan_id+' · mở chi tiết để kiểm tra lại.':'',selected:false})));after=data.next_after;$('batch-progress').textContent=`Đã tải ${rows.length}/${data.total} phiếu đang cầm…`;render();}while(after!==null&&!stop);
     loaded=after===null;$('batch-progress').textContent=loaded?'Đã tải toàn bộ danh sách. Bấm Đối soát tất cả phiếu chưa chuyển trước khi xác nhận.':'Đã dừng tải. Tải lại đủ danh sách trước khi chuyển.';
   }catch(error){$('batch-progress').textContent=error.message;}finally{finish();}
 }
 function apply(r,data){
   r.plan=data;r.selected=false;
   if(data.converted){r.state='existing';r.loan_id=data.loan_id;r.message='Đã chuyển, đối soát nguồn và đích còn khớp.';}
   else if(data.can_convert&&data.loan_state==='ACTIVE'){r.state='ready';r.selected=true;r.message=(data.exception_policy?.accepted?.length||0)+' ngoại lệ đã duyệt · '+data.checks.filter(c=>c.state==='warning').length+' lưu ý; xem chi tiết trước khi xác nhận.';}
   else{r.state='error';r.message=data.checks.filter(c=>c.state==='error').map(c=>c.label+': '+c.detail).join(' · ')||'Phiếu không còn đang cầm hoặc chưa đủ điều kiện.';}
 }
 function details(r){
   $('batch-detail-title').textContent='Đối soát '+r.sku+' · '+labels[r.state];const body=$('batch-checks');body.replaceChildren();
   for(const c of [...(r.plan?.checks||[])].sort((a,b)=>({error:0,warning:1,ok:2})[a.state]-({error:0,warning:1,ok:2})[b.state])){const tr=document.createElement('tr');tr.className='conversion-'+c.state;for(const value of [c.label,c.source,c.target,({ok:'Đạt',warning:'Lưu ý',error:'LỖI'})[c.state]+' · '+c.detail])tr.append(node('td',value));body.append(tr);}
   if(!body.children.length){const tr=document.createElement('tr'),td=node('td',r.message||'Chưa có kết quả đối soát.');td.colSpan=4;tr.append(td);body.append(tr);}$('batch-detail').open=true;
 }
 function previewUrl(id){return dialog.dataset.preview+'?'+new URLSearchParams({pid:id,allow_exceptions:$('batch-exceptions').checked?'yes':'no'});}
 async function inspectOne(r){if(busy)return;start('review');$('batch-progress').textContent='Đang đối soát '+r.sku+'…';try{apply(r,await json(previewUrl(r.id)));$('batch-progress').textContent=r.sku+' · '+labels[r.state];}catch(e){r.state=r.state==='unknown'?'unknown':'error';r.message=e.message;r.selected=false;r.plan=null;}finally{details(r);finish();}}
 async function review(){
   if(busy||!loaded)return;start('review');const queue=rows.filter(r=>!['existing','done'].includes(r.state));let done=0;
   try{for(const r of queue){if(stop)break;try{apply(r,await json(previewUrl(r.id)));}catch(e){r.state=r.state==='unknown'?'unknown':'error';r.selected=false;r.message=e.message;r.plan=null;if(e.uncertain||e instanceof TypeError){stop=true;}}done++;$('batch-progress').textContent=`Đối soát ${done}/${queue.length} · ${r.sku}: ${labels[r.state]}`;render();}
     $('batch-progress').textContent=`${stop?'Đã dừng':'Hoàn tất'} đối soát ${done}/${queue.length} phiếu. Xem lỗi/lưu ý, điều chỉnh lựa chọn rồi xác nhận.`;
   }finally{finish();}
 }
 async function convert(event){
   event.preventDefault();if($('batch-submit').disabled)return;const queue=selected().slice();start('save');let done=0,failed=0,uncertain=false;
   try{for(const r of queue){if(stop)break;$('batch-progress').textContent=`Đang chuyển ${done+failed+1}/${queue.length}: ${r.sku}…`;
     const data=new FormData();data.set('csrf_token',$('batch-confirm').elements.csrf_token.value);data.set('pid',r.id);data.set('review_hash',r.plan.review_hash);data.set('confirmed','yes');
     if(r.plan.exception_policy?.enabled)data.set('allow_exceptions','yes');
     try{const result=await json(dialog.dataset.save,{method:'POST',body:data});r.state='done';r.loan_id=result.loan_id;r.message='cd_loans #'+result.loan_id+' · đã đọc kiểm, giữ nguyên nguồn.';done++;}
     catch(e){uncertain=!!e.uncertain||e instanceof TypeError;r.state=uncertain?'unknown':'error';r.message=e.message;r.plan=null;failed++;if(uncertain)stop=true;}
     r.selected=false;render();
   }$('batch-progress').textContent=`${stop?'Đã dừng':'Hoàn tất'}: ${done} phiếu thành công · ${failed} lỗi/chưa xác định · ${queue.length-done-failed} chưa xử lý.`+(uncertain?' Kết quả cuối chưa xác định: tải lại và đối soát trước khi tiếp tục.':' Phiếu hoàn tất đã được giữ lại.');}
   finally{finish();}
 }
 document.querySelectorAll('[data-convert-batch]').forEach(button=>button.addEventListener('click',()=>{dialog.showModal();if(!loaded&&!busy)load();else render();}));
 $('batch-close').addEventListener('click',()=>{if(!busy)dialog.close();});dialog.addEventListener('cancel',event=>{if(busy){event.preventDefault();stop=true;controls();$('batch-progress').textContent='Đang dừng sau phiếu hiện tại; chờ kết quả trước khi đóng.';}});
 window.addEventListener('beforeunload',event=>{if(busy&&phase==='save'){event.preventDefault();event.returnValue='';}});
 $('batch-reload').addEventListener('click',load);$('batch-review').addEventListener('click',review);$('batch-stop').addEventListener('click',()=>{stop=true;controls();});
 $('batch-exceptions').addEventListener('change',()=>{resetAck();for(const r of rows){r.selected=false;if(!['existing','done','unknown'].includes(r.state)){r.state='pending';r.plan=null;r.message='Điều kiện đã đổi; cần đối soát lại.';}}$('batch-detail').open=false;$('batch-progress').textContent='Đã đổi điều kiện. Bấm Đối soát tất cả phiếu chưa chuyển để kiểm tra lại.';render();});
 $('batch-select').addEventListener('click',()=>{rows.forEach(r=>r.selected=r.state==='ready');resetAck();render();});$('batch-clear').addEventListener('click',()=>{rows.forEach(r=>r.selected=false);resetAck();render();});
 for(const id of ['batch-query','batch-filter'])$(id).addEventListener('input',()=>{page=1;render();});
 $('batch-prev').addEventListener('click',()=>{page--;render();});$('batch-next').addEventListener('click',()=>{page++;render();});$('batch-ack').addEventListener('change',controls);$('batch-confirm').addEventListener('submit',convert);
})();
