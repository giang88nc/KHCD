(()=>{'use strict';
 const $=id=>document.getElementById(id),dialog=$('desk-sessions');if(!dialog)return;
 const form=$('sessions-filter');let page=1,pages=1,version=0,controller=null,loading=false;let historyLoan='',historySku='';
 const money=value=>value===null?'Chưa ghi':new Intl.NumberFormat('vi-VN').format(BigInt(String(value||0).split('.')[0]))+' đ';
 const node=(tag,value)=>{const e=document.createElement(tag);e.textContent=value;return e;};
 function controls(){$('sessions-prev').disabled=loading||page<=1;$('sessions-next').disabled=loading||page>=pages;}
 function invalidate(){version++;controller?.abort();loading=false;$('sessions-result').hidden=true;$('sessions-totals').hidden=true;$('sessions-groups').replaceChildren($('sessions-status'));controls();}
 function render(data){
  page=data.page;pages=data.pages;const body=$('sessions-rows');body.replaceChildren();
  for(const row of data.rows){
   const tr=document.createElement('tr'),stamp=node('td',row.sku||'Thiếu biên nhận');stamp.append(node('small',row.happened_at));if(row.date_fallback)stamp.append(node('small','Thiếu ngày xử lý; dùng ngày bắt đầu.'));tr.append(stamp);
   const customer=node('td',row.customer_name||'Chưa có khách KK');customer.append(node('small',row.phone||'Thiếu SĐT'));tr.append(customer);
   const operation=document.createElement('td'),badge=node('span',row.operation);badge.className='session-operation';badge.dataset.operation=String(row.status_id ?? row.operation_id ?? 'unknown');operation.append(badge);if(row.note)operation.append(node('small',row.note));if(row.reverses_log_id)operation.append(node('small','Đảo phiên #'+row.reverses_log_id));tr.append(operation);
   const amounts=node('td',money(row.amount));amounts.append(node('small','Lãi: '+money(row.interest)));tr.append(amounts);
   const adjustments=node('td','Thêm: '+money(row.extra));adjustments.append(node('small','Giảm: '+money(row.discount)));tr.append(adjustments);
   const payment=node('td','TM: '+money(row.cash));payment.append(node('small','CK: '+money(row.bank)));tr.append(payment);
   const net=node('td',money(row.net));net.className=BigInt(row.net)>=0n?'sessions-in':'sessions-out';tr.append(net);
   const action=document.createElement('td'),open=node('button','MỞ');open.type='button';open.className='btn btn-primary';open.disabled=!row.can_open;open.setAttribute('aria-label','Mở phiếu '+(row.sku||row.pawn_id)+' từ phiên '+row.id);
   open.addEventListener('click',()=>{if($('pawn-create').inert)return;dialog.close();document.dispatchEvent(new CustomEvent('khcd:open-receipt',{detail:{sku:row.sku}}));});action.append(open);tr.append(action);body.append(tr);
  }
  if(!data.rows.length){const tr=document.createElement('tr'),td=node('td','Không có phiên giao dịch phù hợp.');td.colSpan=8;tr.append(td);body.append(tr);}
  $('sessions-page').textContent=`Trang ${page}/${pages} · ${data.total} phiên`;
  const totals=$('sessions-totals');totals.replaceChildren();
  for(const [label,value] of [['Số phiên',data.total],['Tổng thu',money(data.totals.received)],['Tổng chi',money(data.totals.paid)],['Lãi ghi nhận',money(data.totals.interest)],['Tiền mặt ròng',money(data.totals.cash)],['CK ròng',money(data.totals.bank)]]){const card=document.createElement('div');card.append(node('small',label),node('strong',value));totals.append(card);}
  $('sessions-groups').replaceChildren($('sessions-status'),...data.groups.map(g=>node('span',g.operation+': '+g.count+' phiên')));
  $('sessions-status').textContent=`${data.d1} → ${data.d2}`+(data.q?' · Từ khóa: '+data.q:'')+(data.warnings.length?' · '+data.warnings.join(' '):'');$('sessions-result').hidden=false;$('sessions-totals').hidden=false;controls();
 }
 async function load(nextPage=1){
  invalidate();const token=version;controller=new AbortController();loading=true;controls();$('sessions-status').classList.remove('is-error');$('sessions-status').textContent='Đang tải phiên giao dịch…';
  const params=historyLoan?new URLSearchParams({loan_id:historyLoan}):new URLSearchParams(new FormData(form));params.set('page',nextPage);
  try{const response=await fetch(dialog.dataset.url+'?'+params,{signal:controller.signal});let data;try{data=await response.json();}catch(_){throw Error('Chưa nhận được dữ liệu. Tải lại trang và kiểm tra phiên đăng nhập.');}if(token!==version||!dialog.open)return;if(!response.ok)throw Error(data.error||'Chưa tải được danh sách.');render(data);}
  catch(error){if(token!==version||error.name==='AbortError')return;$('sessions-status').classList.add('is-error');$('sessions-status').textContent=error.message||'Chưa tải được danh sách.';}
  finally{if(token===version){loading=false;controls();}}
 }
 $('open-desk-sessions').addEventListener('click',event=>{event.preventDefault();event.stopPropagation();if($('pawn-create').inert)return;historyLoan='';historySku='';form.hidden=false;$('desk-sessions-title').textContent='Danh sách phiên giao dịch';dialog.showModal();load();});
 $('open-receipt-history').addEventListener('click',()=>{const button=$('open-receipt-history');if(button.disabled||!button.dataset.loanId||$('pawn-create').inert)return;historyLoan=button.dataset.loanId;historySku=button.dataset.sku;form.hidden=true;$('desk-sessions-title').textContent='Nhật ký · '+historySku;dialog.showModal();load();});
 form.addEventListener('submit',event=>{event.preventDefault();load();});
 form.addEventListener('input',()=>{invalidate();$('sessions-status').textContent='Bộ lọc đã đổi. Bấm Tìm phiên để xem kết quả mới.';});
 $('sessions-today').addEventListener('click',()=>{form.elements.d1.value=dialog.dataset.today;form.elements.d2.value=dialog.dataset.today;form.elements.q.value='';load();});
 $('sessions-prev').addEventListener('click',()=>load(page-1));$('sessions-next').addEventListener('click',()=>load(page+1));dialog.addEventListener('close',invalidate);
})();
