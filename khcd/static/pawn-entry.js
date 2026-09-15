/* Receipt editor. The server independently validates and recomputes every amount. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id), form=$('pawn-create');
  if(!form)return;
  const digits=v=>String(v).replace(/\D/g,''), amount=v=>BigInt(digits(v)||'0');
  const serverAmount=v=>BigInt(String(v||'0').split('.')[0]);
  const fmt=v=>new Intl.NumberFormat('vi-VN').format(v), money=v=>fmt(v)+' đ';
  const round=(n,d)=>(n+d/2n)/d;
  const scaled=v=>{const s=String(v).replace(',','.');return /^\d+(\.\d{1,4})?$/.test(s)?BigInt(s.split('.')[0]+(s.split('.')[1]||'').padEnd(4,'0')):null;};
  const weight=v=>{const s=v.toString().padStart(5,'0');return s.slice(0,-4)+'.'+s.slice(-4);};
  const weight2=v=>{if(scaled(v)===null)return String(v);const s=round(scaled(v),100n).toString().padStart(3,'0');return s.slice(0,-2)+'.'+s.slice(-2);};
  let loaded=null,totalValuation=0n,lookupVersion=0,qrVersion=0,pendingReceipt=null,bankRows=[],operationVersion=0;
  let rows=[], dirty=false, busy=false, searchVersion=0, selectVersion=0, searchTimer, selected=null, results=[], active=-1;
  const photos=new Map(), frames=[$('pawn-front'),$('pawn-back'),$('pawn-photos')].filter(Boolean);
  const initialDisabled=new Map(Array.from(form.querySelectorAll('input,select,textarea,button')).map(e=>[e,e.disabled]));
  try{rows=JSON.parse($('items-json').value);}catch(_){rows=[];}
  function node(tag,text,cls){const n=document.createElement(tag);n.textContent=text;if(cls)n.className=cls;return n;}
  function error(message){$('desk-error').hidden=!message;$('desk-error').textContent=message;if(message)$('desk-error').scrollIntoView({block:'center',behavior:'smooth'});}
  function words(value){
    const names=['không','một','hai','ba','bốn','năm','sáu','bảy','tám','chín'];
    function group(n,full){let a=[];const h=Math.floor(n/100),t=Math.floor(n%100/10),u=n%10;
      if(h||full)a.push(names[h],'trăm');
      if(t>1)a.push(names[t],'mươi');else if(t===1)a.push('mười');else if(u&&(h||full))a.push('lẻ');
      if(u)a.push(u===1&&t>1?'mốt':u===5&&t>0?'lăm':names[u]);return a.join(' ');}
    if(!value)return 'Không đồng';if(value>999999999999n)return 'Số tiền vượt giới hạn';
    const parts=[],units=['','nghìn','triệu','tỷ'];let n=value,index=0;
    while(n){const g=Number(n%1000n);if(g)parts.unshift(group(g,n>=1000n)+' '+units[index]);n/=1000n;index++;}
    const out=parts.join(' ').trim()+' đồng';return out[0].toUpperCase()+out.slice(1);
  }
  function previewItem(){
    const option=$('item-gold').selectedOptions[0],gross=scaled($('item-gross').value),stone=scaled($('item-stone').value||'0');
    $('item-unit').textContent=option?.dataset.unit||'chỉ';
    const net=gross!==null&&stone!==null&&gross>stone?gross-stone:null;
    $('item-net').value=net===null?'':weight(net);$('item-subtotal').value=net===null?'':fmt(round(net*amount($('item-price').value),10000n));
  }
  function resetEditor(){['item-desc','item-gross','item-net','item-subtotal'].forEach(id=>$(id).value='');$('item-stone').value='0';}
  function render(){
    const body=$('item-rows');body.replaceChildren();let total=0n;
    rows.forEach((row,index)=>{
      const tr=document.createElement('tr'),first=document.createElement('td');first.append(node('b','['+row.gold.toUpperCase()+']'),document.createTextNode(row.description),node('small',row.unit));tr.append(first);
      for(const v of [row.gross,row.net,row.stone,fmt(BigInt(row.price)),money(BigInt(row.subtotal))])tr.append(node('td',v));
      const cell=document.createElement('td'),remove=node('button','×');remove.type='button';remove.title='Bỏ món '+(index+1);remove.setAttribute('aria-label',remove.title);
      remove.disabled=!!loaded;remove.addEventListener('click',()=>{if(loaded)return;rows.splice(index,1);dirty=true;render();});cell.append(remove);tr.append(cell);body.append(tr);total+=BigInt(row.subtotal);
    });
    if(!rows.length){const tr=document.createElement('tr'),td=node('td','Thêm món vàng đầu tiên vào biên nhận','empty-items');td.colSpan=7;tr.append(td);body.append(tr);}
    $('item-count').textContent=rows.length+' MÓN';$('items-json').value=JSON.stringify(rows);
    $('item-summary').value=rows.map(r=>'['+r.gold.toUpperCase()+'] '+r.description+' '+weight2(r.net)+(r.unit==='chỉ'?'c':'g')).join(' + ');
    totalValuation=total;$('valuation-total').textContent=loaded&&!loaded.valuation_known?'Chưa lưu định giá':money(total);warnValuation();
  }
  $('item-add').addEventListener('click',()=>{
    if(loaded)return;
    const option=$('item-gold').selectedOptions[0],gross=scaled($('item-gross').value),stone=scaled($('item-stone').value||'0'),price=amount($('item-price').value),description=$('item-desc').value.trim();
    let message='';
    if(!option.value||!description)message='Chọn loại vàng và nhập mô tả món hàng.';
    else if(gross===null||stone===null||gross<=stone||gross>999990000n)message='Kiểm tra trọng lượng: tổng lớn hơn hột, tối đa 4 số thập phân.';
    else if(!$('item-price').value||price>999999999999n)message='Nhập giá định giá hợp lệ, tối đa 999.999.999.999 đ.';
    else if(rows.length>=30)message='Một phiếu tối đa 30 dòng món hàng.';
    $('item-error').textContent=message||'Đã thêm món. Có thể tiếp tục nhập món tiếp theo.';$('item-error').classList.toggle('desk-error-field',!!message);if(message)return;
    rows.push({gold:option.value,name:option.textContent,unit:option.dataset.unit,description,gross:weight(gross),stone:weight(stone),net:weight(gross-stone),price:price.toString(),subtotal:round((gross-stone)*price,10000n).toString()});
    dirty=true;render();resetEditor();$('item-desc').focus();
  });
  form.querySelector('.item-editor').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('item-add').click();}});
  $('item-gold').addEventListener('change',()=>{$('item-price').value=fmt(serverAmount($('item-gold').selectedOptions[0].dataset.price));previewItem();});
  for(const id of ['item-gross','item-stone','item-price'])$(id).addEventListener('input',previewItem);
  function warnValuation(){const over=rows.length>0&&(!loaded||loaded.valuation_known)&&amount($('principal').value)>totalValuation;$('principal-panel').classList.toggle('principal-over',over);$('valuation-warning').hidden=!over;}
  function update(resetAmounts=false){
    const principal=amount($('principal').value),bankOn=$('pay-bank').checked;
    $('principal-readable').textContent=words(principal);$('bank-fields').hidden=!bankOn;
    for(const name of ['bank_name','bank_account','bank_holder'])form.elements.namedItem(name).required=bankOn;
    $('bank-amount').readOnly=!bankOn;$('cash-input').readOnly=!bankOn;
    if(!loaded&&(resetAmounts||!bankOn)){$('bank-amount').value=fmt(bankOn?principal:0n);$('cash-input').value=fmt(bankOn?0n:principal);}
    const term=Number($('term').value),valid=Number.isInteger(term)&&term>=1&&term<=365;
    $('estimated-interest').textContent=valid?money(round(principal*BigInt(Math.round(Number($('monthly-rate').value)*10))*BigInt(term),30000n)):'—';
    const date=new Date($('entry-date').value+'T00:00:00Z');
    if(loaded)$('entry-due').value=loaded.due;
    else if(valid&&Number.isFinite(date.getTime())){date.setUTCDate(date.getUTCDate()+term);$('entry-due').value=date.toISOString().slice(0,10);}else $('entry-due').value='';
    warnValuation();
  }
  for(const id of ['principal','bank-amount','cash-input','item-price'])$(id).addEventListener('input',()=>{
    const field=$(id),value=digits(field.value);field.value=value?fmt(BigInt(value)):'';
    if(['bank-amount','cash-input'].includes(id)){
      const principal=amount($('principal').value),entered=amount(field.value),other=id==='cash-input'?'bank-amount':'cash-input';
      $(other).value=fmt(entered<=principal?principal-entered:0n);$('bank-status').textContent=entered>principal?'Số tiền vượt tiền cầm.':'';
    }
    update(id==='principal');if(id==='item-price')previewItem();
  });
  for(const id of ['pay-cash','pay-bank'])$(id).addEventListener('change',()=>update(true));
  for(const id of ['monthly-rate','term','entry-date'])$(id).addEventListener('change',()=>update());
  form.addEventListener('input',e=>{if(!loaded&&e.target.id!=='receipt-query')dirty=true;});form.addEventListener('change',e=>{if(!loaded&&e.target.id!=='receipt-query')dirty=true;});
  function post(type,detail={}){frames.forEach(frame=>frame.contentWindow?.postMessage({source:'khcd-pawn-parent',type,detail},location.origin));}
  function closeResults(){$('customer-results').hidden=true;$('customer-query').setAttribute('aria-expanded','false');$('customer-query').removeAttribute('aria-activedescendant');active=-1;}
  function clearCustomer(){selected=null;selectVersion++;qrVersion++;$('entry-customer').value='';$('customer-facts').hidden=true;$('edit-customer').disabled=true;delete $('edit-customer').dataset.custId;for(const name of ['bank_name','bank_account','bank_holder'])form.elements.namedItem(name).value='';$('bank-qr-input').value='';$('bank-status').textContent='';post('customer',{id:'',photos:{}});}
  $('clear-customer').addEventListener('click',()=>{if(loaded)return;clearCustomer();$('customer-query').value='';closeResults();$('customer-search-status').textContent='Tìm và chọn khách KK.';$('customer-query').focus();});
  async function get(url){const response=await fetch(url,{headers:{Accept:'application/json'}});const data=await response.json();if(!response.ok||data.error)throw new Error(data.error||'Không đọc được dữ liệu.');return data;}
  async function choose(id){
    if(loaded)return;
    const sameCustomer=selected?.id===String(id);
    if(!sameCustomer)clearCustomer();
    const version=++selectVersion;searchVersion++;clearTimeout(searchTimer);closeResults();$('customer-search-status').textContent='Đang đọc hồ sơ…';
    try{const data=await get(form.dataset.search+'?id='+encodeURIComponent(id));if(version!==selectVersion)return;
      const c=data.customer;selected={id:String(c.id),photos:data.photos||{}};$('entry-customer').value=c.id;$('customer-query').value=c.name;
      for(const name of ['name','phone','cccd','addr'])$('customer-'+name).textContent=c[name]||'—';
      $('customer-facts').hidden=false;$('edit-customer').disabled=false;$('edit-customer').dataset.custId=c.id;
      $('customer-search-status').textContent='Đã chọn hồ sơ KK · '+c.id;post('customer',selected);dirty=true;
    }catch(e){if(version===selectVersion){if(!sameCustomer)clearCustomer();$('customer-search-status').textContent=e.message;}}
  }
  async function search(){
    const q=$('customer-query').value.trim(),version=++searchVersion;if(q.length<2){closeResults();$('customer-search-status').textContent='Nhập ít nhất 2 ký tự để tìm khách.';return;}
    $('customer-search-status').textContent='Đang tìm khách…';
    try{const data=await get(form.dataset.search+'?q='+encodeURIComponent(q));if(version!==searchVersion)return;
      results=data.customers||[];const box=$('customer-results');box.replaceChildren();active=-1;
      results.forEach((c,index)=>{const b=node('button','');b.type='button';b.id='customer-option-'+index;b.setAttribute('role','option');b.setAttribute('aria-selected','false');b.append(node('b',c.name||'Chưa có tên'),node('small',[c.phone,c.cccd,c.id].filter(Boolean).join(' · ')));b.addEventListener('click',()=>choose(c.id));box.append(b);});
      box.hidden=!results.length;$('customer-query').setAttribute('aria-expanded',String(!!results.length));$('customer-search-status').textContent=results.length?'Chọn một hồ sơ trong danh sách.':'Không tìm thấy. Dùng nút Thêm khách để tạo hồ sơ.';
    }catch(e){if(version===searchVersion){closeResults();$('customer-search-status').textContent=e.message;}}
  }
  $('customer-query').addEventListener('input',()=>{clearCustomer();searchVersion++;closeResults();clearTimeout(searchTimer);searchTimer=setTimeout(search,280);});
  $('customer-query').addEventListener('keydown',event=>{
    if(event.key==='Escape'){closeResults();return;}
    if(event.key==='Enter'){event.preventDefault();if(active>=0&&!$('customer-results').hidden)choose(results[active].id);else search();return;}
    if(['ArrowDown','ArrowUp'].includes(event.key)&&!$('customer-results').hidden){event.preventDefault();active=(active+(event.key==='ArrowDown'?1:-1)+results.length)%results.length;Array.from($('customer-results').children).forEach((b,i)=>b.setAttribute('aria-selected',String(i===active)));const b=$('customer-option-'+active);$('customer-query').setAttribute('aria-activedescendant',b.id);b.scrollIntoView({block:'nearest'});}
  });
  document.addEventListener('click',e=>{if(!e.target.closest('.customer-lookup'))closeResults();});
  document.addEventListener('pawn:customer-saved',e=>{if(e.detail.custId)choose(e.detail.custId);});
  window.addEventListener('message',e=>{
    const frame=frames.find(f=>e.source===f.contentWindow);
    if(e.origin!==location.origin||!frame||e.data?.source!=='khcd-pawn-photos')return;
    const {type,detail={}}=e.data;
    if(type==='ready'){if(loaded)post('lock',{locked:true,id:loaded.customer.id,photos:loaded.photos});else if(selected)post('customer',selected);}
    if(type==='expand'){frame.classList.toggle('is-expanded',!!detail.open);frame.closest('.desk-section,.desk-right').classList.toggle('photo-owner-expanded',!!detail.open);document.body.classList.toggle('pawn-photo-expanded',frames.some(f=>f.classList.contains('is-expanded')));}
    if(type==='file'&&!loaded&&['anh_truoc','anh_sau','anh_sp1','anh_sp2','anh_qr'].includes(detail.name)){
      if(detail.file)photos.set(detail.name,detail.file);else photos.delete(detail.name);if(detail.user)dirty=true;
      if(detail.name==='anh_qr'){if(!detail.file)qrVersion++;else if(detail.user&&!detail.parsed)readQr('bank','',detail.file);}
    }
    if(type==='scan'&&!loaded&&photos.get('anh_qr'))readQr('bank','',photos.get('anh_qr'));
  });
  function clearDraft(){loaded=null;lookupVersion++;qrVersion++;searchVersion++;clearTimeout(searchTimer);closeResults();lockForm(false);form.reset();$('loaded-pawn-id').value='';$('receipt-state').textContent='PHIẾU MỚI';$('customer-search-status').textContent='Tìm và chọn khách KK.';$('item-error').textContent='Trọng lượng theo đơn vị loại vàng.';$('desk-save-status').textContent='Kiểm tra thông tin trước khi lưu phiếu.';$('receipt-status').textContent='';$('receipt-query').value='';rows=[];photos.clear();clearCustomer();$('customer-query').value='';post('reset');resetEditor();render();update(true);error('');dirty=false;}
  $('clear-draft').addEventListener('click',()=>{if(busy)return;if(dirty)$('clear-draft-dialog').showModal();else clearDraft();});
  $('confirm-clear-draft').addEventListener('click',()=>{clearDraft();$('clear-draft-dialog').close();});
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(busy||loaded)return;
    if(!$('entry-customer').value){error('Tìm và chọn hồ sơ khách trước khi lưu.');$('customer-query').focus();return;}
    if(!rows.length){error('Thêm ít nhất một món vàng vào biên nhận.');return;}
    if($('item-desc').value.trim()||$('item-gross').value){error('Món đang nhập chưa được thêm. Bấm THÊM hoặc xóa nội dung món đang nhập.');return;}
    const principal=amount($('principal').value),bank=$('pay-bank').checked?amount($('bank-amount').value):0n;
    if(principal<=0n||principal>999999999999n){error('Tiền cầm phải từ 1 đến 999.999.999.999 đồng.');return;}
    if((!$('pay-cash').checked&&!$('pay-bank').checked)||bank>principal||($('pay-bank').checked&&bank<=0n)){error('Kiểm tra phương thức và số tiền chi cho khách.');return;}
    const cash=amount($('cash-input').value);if(cash+bank!==principal){error('Tiền mặt + chuyển khoản phải bằng số tiền cầm.');return;}
    const fd=new FormData(form);fd.set('cash_amount',cash.toString());fd.set('value',principal.toString());fd.set('bank_amount',bank.toString());fd.set('items_json',JSON.stringify(rows));photos.forEach((file,name)=>fd.append(name,file,file.name||name+'.jpg'));
    busy=true;form.inert=true;frames.forEach(f=>f.inert=true);error('');$('save-pawn').disabled=true;$('save-pawn').setAttribute('aria-busy','true');$('desk-save-status').textContent='Đang kiểm tra và lưu phiếu…';
    try{const response=await fetch(form.action,{method:'POST',body:fd,headers:{Accept:'application/json'}});let data;try{data=await response.json();}catch(_){throw new Error('Chưa xác định được kết quả lưu. Giữ phiếu này và kiểm tra lịch sử trước khi thử lại.');}
      if(!response.ok||!data.url)throw new Error(data.error||'Chưa lưu được phiếu. Dữ liệu đang nhập được giữ lại.');dirty=false;location.assign(data.url);
    }catch(e){form.inert=false;frames.forEach(f=>f.inert=false);error(e.message);$('desk-save-status').textContent='Chưa hoàn tất · nội dung đang nhập được giữ lại.';busy=false;$('save-pawn').disabled=false;$('save-pawn').removeAttribute('aria-busy');}
  });
  function lockForm(on){
    form.classList.toggle('desk-locked',on);
    initialDisabled.forEach((disabled,field)=>{field.disabled=on?!['receipt-query','scan-receipt'].includes(field.id):disabled;});
    $('print-pawn').disabled=!on;
    document.querySelectorAll('[data-pawn-action]').forEach(b=>{b.disabled=b.dataset.pawnAction!=='1'&&(!on||!loaded?.active);b.title=b.disabled?'Quét phiếu đang cầm để mở nghiệp vụ':b.dataset.actionName;b.classList.toggle('is-active',b.dataset.pawnAction==='1'&&!on);});
    if(!on){form.querySelectorAll('option[data-loaded]').forEach(o=>o.remove());post('lock',{locked:false});}
  }
  function selectStored(select,value,label){let option=Array.from(select.options).find(o=>o.value===String(value));if(!option){option=new Option(label||value,String(value));option.dataset.loaded='1';select.add(option);}select.value=String(value);}
  function openReceipt(p){
    lookupVersion++;qrVersion++;selectVersion++;searchVersion++;clearTimeout(searchTimer);closeResults();loaded=p;dirty=false;photos.clear();rows=p.items;selected={id:p.customer.id,photos:p.photos};
    $('loaded-pawn-id').value=p.id;$('receipt-query').value=p.sku;$('receipt-state').textContent=p.status_name;
    $('receipt-status').textContent='Đang xem '+p.sku+' · Thông tin đã khóa. Chọn nghiệp vụ bên trái.';
    $('item-error').textContent='';$('desk-save-status').textContent='Phiếu đã lưu · chỉ xem và in.';
    $('entry-customer').value=p.customer.id;$('customer-query').value=p.customer.name;
    for(const key of ['name','phone','cccd','addr'])$('customer-'+key).textContent=p.customer[key]||'—';$('customer-facts').hidden=false;
    $('customer-search-status').textContent=p.customer_error||'';
    selectStored(form.elements.employee_id,p.employee_id||'legacy',p.employee_name);
    form.elements.safe.value=p.safe;$('entry-date').value=p.date1;$('principal').value=fmt(serverAmount(p.value));
    const rate=Array.from($('monthly-rate').options).find(o=>Number(o.value)===Number(p.monthly_rate));
    selectStored($('monthly-rate'),rate?.value||p.monthly_rate,p.monthly_rate+'% / tháng');
    const days=Math.round((new Date(p.due)-new Date(p.date1))/86400000);$('term').value=Number.isFinite(days)&&days>0?days:30;
    form.elements.note.value=p.note;
    for(const key of ['bank_name','bank_account','bank_holder','bank_reference'])form.elements.namedItem(key).value=p.payment[key]||'';
    $('bank-amount').value=fmt(serverAmount(p.payment.bank_amount));$('cash-input').value=fmt(serverAmount(p.payment.cash));
    $('pay-bank').checked=serverAmount(p.payment.bank_amount)>0n;$('pay-cash').checked=!$('pay-bank').checked;$('bank-status').textContent='';
    render();$('item-summary').value=p.content;update();lockForm(true);post('lock',{locked:true,id:p.customer.id,photos:p.photos});error('');
  }
  async function lookupReceipt(raw){
    const version=++lookupVersion;$('receipt-status').textContent='Đang tìm biên nhận…';
    try{const p=await get(form.dataset.lookup+'?q='+encodeURIComponent(raw));if(version!==lookupVersion)return;
      if(dirty&&!loaded){pendingReceipt=p;$('receipt-open-dialog').showModal();}else openReceipt(p);
    }catch(e){if(version===lookupVersion){$('receipt-status').textContent=e.message;if(loaded)$('receipt-query').value=loaded.sku;}}
  }
  $('confirm-open-receipt').addEventListener('click',()=>{if(pendingReceipt)openReceipt(pendingReceipt);pendingReceipt=null;$('receipt-open-dialog').close();});
  $('receipt-query').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();lookupReceipt(e.target.value);}});
  $('print-pawn').addEventListener('click',()=>{if(loaded)window.open(loaded.detail_url,'_blank','noopener');});
  document.querySelectorAll('[data-pawn-action]').forEach(button=>button.addEventListener('click',async()=>{
    const id=Number(button.dataset.pawnAction);if(id===1){if(dirty)$('clear-draft-dialog').showModal();else clearDraft();return;}
    if(!loaded)return;const version=++operationVersion;
    $('operation-title').textContent=button.dataset.actionName;$('operation-receipt').textContent=loaded.sku+' · '+loaded.customer.name;
    const incoming=[3,4,5].includes(id),outgoing=id===2;
    $('operation-direction').textContent=incoming?'THU TIỀN VÀO · tài khoản nhận của tiệm':outgoing?'CHI TIỀN RA · tài khoản nhận của khách':'';
    $('operation-bank-panel').hidden=!incoming&&!outgoing;$('operation-bank-choice').hidden=!incoming;
    for(const field of ['name','number','holder'])$('operation-bank-'+field).value='';
    $('operation-bank-status').textContent='';$('operation-dialog').showModal();
    if(outgoing){$('operation-bank-name').value=loaded.payment.bank_name||'';$('operation-bank-number').value=loaded.payment.bank_account||'';$('operation-bank-holder').value=loaded.payment.bank_holder||'';
      if(!loaded.payment.bank_account)$('operation-bank-status').textContent='Phiếu chưa lưu tài khoản khách. Bổ sung khi mở xử lý nghiệp vụ.';
    }
    if(incoming){$('operation-bank').replaceChildren(new Option('Chọn tài khoản nhận',''));$('operation-bank-status').textContent='Đang đọc danh mục tài khoản tiệm…';
      try{const data=await get(form.dataset.banks);if(version!==operationVersion||!$('operation-dialog').open)return;bankRows=data.rows;
        bankRows.forEach(b=>$('operation-bank').add(new Option([b.bank_name||b.bank_bin,b.bank_number,b.type].filter(Boolean).join(' · '),b.id)));
        $('operation-bank').value=data.default_id==null?'':String(data.default_id);showShopBank();
        $('operation-bank-status').textContent=data.default_id==null?'Chưa cấu hình tài khoản đang bật có type=pawn. Chọn tài khoản tiệm để xem.':'Tài khoản mặc định type=pawn · nguồn khj_bl.gold_bank';
      }catch(e){if(version===operationVersion&&$('operation-dialog').open)$('operation-bank-status').textContent=e.message;}
    }
  }));
  function showShopBank(){const bank=bankRows.find(b=>String(b.id)===$('operation-bank').value)||{};$('operation-bank-name').value=bank.bank_name||bank.bank_bin||'';$('operation-bank-number').value=bank.bank_number||'';$('operation-bank-holder').value=bank.bank_user||'';}
  $('operation-bank').addEventListener('change',showShopBank);
  let qrKind='receipt',cameraStream=null;
  function stopCamera(){cameraStream?.getTracks().forEach(t=>t.stop());cameraStream=null;$('desk-qr-video').srcObject=null;document.querySelector('.qr-camera').hidden=true;$('desk-qr-capture').hidden=true;}
  function showQr(kind){qrKind=kind;$('desk-qr-title').textContent=kind==='bank'?'Quét QR chuyển khoản khách':'Quét QR biên nhận';$('desk-qr-raw').value='';$('desk-qr-status').textContent='Dùng máy quét, chọn ảnh QR hoặc mở camera.';$('desk-qr-file').value='';$('desk-qr-dialog').showModal();$('desk-qr-raw').focus();}
  $('scan-receipt').addEventListener('click',()=>showQr('receipt'));$('scan-bank').addEventListener('click',()=>{if(!loaded)showQr('bank');});
  $('desk-qr-dialog').addEventListener('close',()=>{stopCamera();qrVersion++;});
  $('desk-qr-camera').addEventListener('click',async()=>{try{stopCamera();cameraStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'},audio:false});if(!$('desk-qr-dialog').open){stopCamera();return;}$('desk-qr-video').srcObject=cameraStream;document.querySelector('.qr-camera').hidden=false;$('desk-qr-capture').hidden=false;}catch(e){$('desk-qr-status').textContent='Chưa mở được camera. Có thể chọn ảnh hoặc dùng máy quét.';}});
  $('desk-qr-capture').addEventListener('click',()=>{const video=$('desk-qr-video');if(!video.videoWidth){$('desk-qr-status').textContent='Đợi camera hiển thị hình.';return;}const canvas=document.createElement('canvas'),scale=Math.min(1,1600/video.videoWidth);canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);canvas.toBlob(b=>{if(b)readQr(qrKind,'',new File([b],'qr-camera.jpg',{type:'image/jpeg'}));},'image/jpeg',.92);});
  $('desk-qr-file').addEventListener('change',e=>{if(e.target.files[0])readQr(qrKind,'',e.target.files[0]);});
  $('desk-qr-use').addEventListener('click',()=>readQr(qrKind,$('desk-qr-raw').value));
  $('desk-qr-raw').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();readQr(qrKind,e.target.value);}});
  $('bank-qr-input').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();readQr('bank',e.target.value);}});
  async function readQr(kind,text='',file=null){
    if(kind==='bank'&&loaded)return;const version=++qrVersion,box=$('desk-qr-dialog').open?$('desk-qr-status'):$('bank-status');box.textContent='Đang đọc mã QR…';
    try{if(file&&file.size>15*1024*1024)throw new Error('Ảnh QR tối đa 15 MB.');
      const fd=new FormData();fd.set('csrf_token',form.elements.csrf_token.value);fd.set('kind',kind);fd.set('text',text);if(file)fd.append('image',file);
      const response=await fetch(form.dataset.qr,{method:'POST',body:fd,headers:{Accept:'application/json'}});const data=await response.json();if(version!==qrVersion)return;if(!response.ok||data.error)throw new Error(data.error||'Không đọc được QR.');
      if(kind==='receipt'){if($('desk-qr-dialog').open)$('desk-qr-dialog').close();lookupReceipt(data.text);return;}
      const oldAccount=form.elements.bank_account.value;form.elements.bank_name.value=data.bank_name;form.elements.bank_account.value=data.bank_account;
      form.elements.bank_holder.value=data.bank_holder||(oldAccount===data.bank_account?form.elements.bank_holder.value:'');
      $('pay-bank').checked=true;update(true);$('bank-status').textContent=data.warning||'Đã đọc QR. Đối chiếu tài khoản và tên người nhận.';dirty=true;
      if(data.qr_image&&!file){const bytes=Uint8Array.from(atob(data.qr_image),c=>c.charCodeAt(0));post('qr',{file:new File([bytes],'qr-khach.png',{type:'image/png'})});}
      else if(file)post('qr',{file});
      if($('desk-qr-dialog').open)$('desk-qr-dialog').close();
    }catch(e){if(version===qrVersion)box.textContent=e.message||'Chưa đọc được mã QR.';}
  }
  window.addEventListener('beforeunload',event=>{stopCamera();if(dirty){event.preventDefault();event.returnValue='';}});
  render();update(true);previewItem();if($('entry-customer').value)choose($('entry-customer').value);
})();
