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
  let cancelDeadline=0,cancelKey="",savedSku='',paymentDeadline=0,bankCode='',outgoingPreview=null,outgoingKey='';
  let loaded=null,totalValuation=0n,lookupVersion=0,qrVersion=0,pendingReceipt=null,bankRows=[],operationVersion=0;
  let rows=[], dirty=false, busy=false, searchVersion=0, selectVersion=0, searchTimer, selected=null, results=[], active=-1;
  const photos=new Map(), frames=[$('pawn-front'),$('pawn-back'),$('pawn-photos'),$('pawn-session-qr')].filter(Boolean);
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
    const other=option?.value==='KHAC';
    for(const id of ['item-gross','item-stone','item-net']){$(id).disabled=other;$(id).closest('label').hidden=other;}
    $('item-price').closest('label').hidden=!other;
    $('item-unit').textContent=other?'món (giá hiện tại)':option?.dataset.unit||'chỉ';
    const net=gross!==null&&stone!==null&&gross>stone?gross-stone:null;
    $('item-net').value=net===null?'':weight(net);$('item-subtotal').value=net===null?'':fmt(round(net*amount($('item-price').value),10000n));
  }
  function resetEditor(){['item-desc','item-gross','item-net','item-subtotal'].forEach(id=>$(id).value='');$('item-stone').value='0';$('item-gold').value='';$('item-price').value='';previewItem();}
  function render(){
    const body=$('item-rows');body.replaceChildren();let total=0n;
    rows.forEach((row,index)=>{
      const tr=document.createElement('tr'),first=document.createElement('td');tr.title=row.gold==='KHAC'?'Giá trị hiện tại: '+money(BigInt(row.subtotal)):row.net+' '+row.unit+' × '+money(BigInt(row.price))+' = '+money(BigInt(row.subtotal));first.append(node('b','['+row.gold.toUpperCase()+']'),document.createTextNode(row.description));tr.append(first);
      for(const v of [row.gross,row.net,row.stone,fmt(BigInt(row.price)),money(BigInt(row.subtotal))])tr.append(node('td',v));
      const cell=document.createElement('td'),remove=node('button','×');remove.type='button';remove.title='Bỏ món '+(index+1);remove.setAttribute('aria-label',remove.title);
      remove.disabled=!!loaded;remove.addEventListener('click',()=>{if(loaded)return;rows.splice(index,1);dirty=true;render();});cell.append(remove);tr.append(cell);body.append(tr);total+=BigInt(row.subtotal);
    });
    if(!rows.length){const tr=document.createElement('tr'),td=node('td','Thêm món vàng đầu tiên vào biên nhận','empty-items');td.colSpan=7;tr.append(td);body.append(tr);}
    $('item-count').textContent=rows.length+' MÓN';$('items-json').value=JSON.stringify(rows);
    $('item-summary').value=rows.map(r=>'['+r.gold.toUpperCase()+'] '+r.description+(r.gold==='KHAC'?'':' '+weight2(r.net)+(r.unit==='chỉ'?'c':'g'))).join(' + ');
    totalValuation=((total*70n+99999n)/100000n)*1000n;$('valuation-total').title=loaded&&!loaded.valuation_known?'ĐỊNH GIÁ: Chưa lưu':'ĐỊNH GIÁ: '+money(total);$('valuation-total').textContent=loaded&&!loaded.valuation_known?'Chưa lưu định giá':money(totalValuation);warnValuation();
  }
  $('item-add').addEventListener('click',()=>{
    if(loaded)return;
    const option=$('item-gold').selectedOptions[0],gross=scaled($('item-gross').value),stone=scaled($('item-stone').value||'0'),price=amount($('item-price').value),description=$('item-desc').value.trim();
    let message='';
    if(!option.value||!description)message='Chọn loại vàng và nhập mô tả món hàng.';
    else if(option.value!=='KHAC'&&(gross===null||stone===null||gross<=stone||gross>999990000n))message='Kiểm tra trọng lượng: tổng lớn hơn hột, tối đa 4 số thập phân.';
    else if(!$('item-price').value||price>999999999999n)message='Nhập giá định giá hợp lệ, tối đa 999.999.999.999 đ.';
    else if(rows.length>=30)message='Một phiếu tối đa 30 dòng món hàng.';
    $('item-error').textContent=message||'';$('item-error').classList.toggle('desk-error-field',!!message);if(message)return;
    if(option.value==='KHAC')rows.push({gold:'KHAC',name:'KHÁC',unit:'món',description,gross:'0',stone:'0',net:'0',price:price.toString(),subtotal:price.toString()});
    else rows.push({gold:option.value,name:option.textContent,unit:option.dataset.unit,description,gross:weight(gross),stone:weight(stone),net:weight(gross-stone),price:price.toString(),subtotal:round((gross-stone)*price,10000n).toString()});
    dirty=true;render();resetEditor();$('item-desc').focus();
  });
  form.querySelector('.item-editor').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();$('item-add').click();}});
  $('item-gold').addEventListener('change',()=>{$('item-price').value=fmt(serverAmount($('item-gold').selectedOptions[0].dataset.price));previewItem();});
  for(const id of ['item-gross','item-stone','item-price'])$(id).addEventListener('input',previewItem);
  function warnValuation(){const over=rows.length>0&&(!loaded||loaded.valuation_known)&&amount($('principal').value)>totalValuation;$('principal-panel').classList.toggle('principal-over',over);$('valuation-warning').hidden=!over;}
  function update(resetAmounts=false){
    const principal=amount($('principal').value),paymentTotal=loaded?serverAmount(loaded.checkout?.total):principal,bankOn=$('pay-bank').checked;
    $('principal-readable').textContent=words(principal);$('bank-fields').hidden=!bankOn;
    for(const name of ['bank_name','bank_account','bank_holder'])form.elements.namedItem(name).required=bankOn;
    $('bank-amount').readOnly=!bankOn;$('cash-input').readOnly=!bankOn;
    if((!loaded||canEditPayment())&&(resetAmounts||!bankOn)){$('bank-amount').value=fmt(bankOn?paymentTotal:0n);$('cash-input').value=fmt(bankOn?0n:paymentTotal);}
    const term=Number($('term').value),valid=Number.isInteger(term)&&term>=1&&term<=365;
    $('estimated-interest').textContent=valid?money(round(principal*BigInt(Math.round(Number($('monthly-rate').value)*10))*BigInt(term),30000n)):'—';
    const date=new Date($('entry-date').value+'T00:00:00Z');
    if(loaded)$('entry-due').value=loaded.due;
    else if(valid&&Number.isFinite(date.getTime())){date.setUTCDate(date.getUTCDate()+term);$('entry-due').value=date.toISOString().slice(0,10);}else $('entry-due').value='';
    const checkout=loaded?.checkout;
    $('checkout-receipt-code').textContent=loaded?.sku||'PHIẾU MỚI';
    $('checkout-due-label').textContent=loaded?'Ngày hẹn đã chốt':'Ngày hẹn dự kiến';
    $('checkout-note').hidden=!!loaded;
    document.querySelector('.session-qr-corner').hidden=!!loaded&&!loaded.photos?.anh_qr;
    $('checkout-last-session').hidden=!checkout?.at;
    $('checkout-last-session').textContent=checkout?[checkout.operation,checkout.at.slice(11,16),checkout.at.slice(0,10).split('-').reverse().join('/')].filter(Boolean).join(' · '):'';
    $('checkout-direction').textContent=checkout?checkout.direction+': '+money(serverAmount(checkout.total)):'CHI CHO KHÁCH';
    $('checkout-forecast').hidden=!!checkout?.closed;
    if(checkout)$('estimated-interest').textContent=checkout.forecast_interest===null?'Chưa xác định — kiểm tra mốc lãi':money(serverAmount(checkout.forecast_interest));
    warnValuation();refreshPaymentControls();
  }
  for(const id of ['principal','bank-amount','cash-input','item-price'])$(id).addEventListener('input',()=>{
    const field=$(id),value=digits(field.value);field.value=value?fmt(BigInt(value)):'';
    if(['bank-amount','cash-input'].includes(id)){
      const principal=loaded?serverAmount(loaded.checkout?.total):amount($('principal').value),entered=amount(field.value),other=id==='cash-input'?'bank-amount':'cash-input';
      $(other).value=fmt(entered<=principal?principal-entered:0n);$('bank-status').textContent=entered>principal?'Số tiền vượt tiền cầm.':'';
    }
    update(id==='principal');if(id==='item-price')previewItem();
  });
  for(const id of ['pay-cash','pay-bank'])$(id).addEventListener('change',()=>update(true));
  for(const id of ['monthly-rate','term','entry-date'])$(id).addEventListener('change',()=>update());
  form.addEventListener('input',e=>{if(!loaded&&!['receipt-query','customer-query'].includes(e.target.id))dirty=true;});form.addEventListener('change',e=>{if(!loaded&&!['receipt-query','customer-query'].includes(e.target.id))dirty=true;});
  function post(type,detail={}){frames.forEach(frame=>frame.contentWindow?.postMessage({source:'khcd-pawn-parent',type,detail},location.origin));}
  function closeResults(){$('customer-results').hidden=true;$('customer-query').setAttribute('aria-expanded','false');$('customer-query').removeAttribute('aria-activedescendant');active=-1;}
  function syncCustomerActions(){
    const has=!!selected?.id,readonly=$('create-customer').hasAttribute('data-readonly');
    $('create-customer').hidden=has;$('create-customer').disabled=!!loaded||readonly;
    $('edit-customer').hidden=!has;$('edit-customer').disabled=!has||!!loaded||readonly;
    $('clear-customer').hidden=!has;$('clear-customer').disabled=!!loaded;
    if(has)$('edit-customer').dataset.custId=selected.id;else delete $('edit-customer').dataset.custId;
    $('customer-query').closest('.customer-lookup').classList.toggle('has-customer',has);
  }
  function clearCustomer(){selected=null;selectVersion++;qrVersion++;$('entry-customer').value='';$('customer-facts').hidden=true;$('edit-customer').disabled=true;delete $('edit-customer').dataset.custId;for(const name of ['bank_name','bank_account','bank_holder'])form.elements.namedItem(name).value='';$('bank-qr-input').value='';$('bank-status').textContent='';post('customer',{id:'',photos:{}});syncCustomerActions();}
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
      $('customer-facts').hidden=false;syncCustomerActions();
      $('customer-search-status').textContent='Đã chọn hồ sơ KK · '+c.id;post('customer',selected);dirty=true;
    }catch(e){if(version===selectVersion){if(!sameCustomer)clearCustomer();$('customer-search-status').textContent=e.message;}}
  }
  async function search(){
    let q=$('customer-query').value.trim();const version=++searchVersion;
    if(q.includes('|')){
      const fields=q.split('|'),cccd=fields[0].trim();
      if(fields.length<7||!/^\d{12}$/.test(cccd)||!/^\d{8}$/.test(fields[fields.length-1].trim())){closeResults();$('customer-search-status').textContent='QR CCCD chưa đủ hoặc sai định dạng. Quét lại hoặc nhập số CCCD.';return;}
      q=cccd;$('customer-query').value=cccd;
    }
    if(q.length<2){closeResults();$('customer-search-status').textContent='Nhập ít nhất 2 ký tự để tìm khách.';return;}
    $('customer-search-status').textContent='Đang tìm khách…';
    try{const data=await get(form.dataset.search+'?q='+encodeURIComponent(q));if(version!==searchVersion)return;
      results=data.customers||[];const box=$('customer-results');box.replaceChildren();active=-1;
      results.forEach((c,index)=>{const b=node('button','');b.type='button';b.id='customer-option-'+index;b.setAttribute('role','option');b.setAttribute('aria-selected','false');b.append(node('b',c.name||'Chưa có tên'),node('small',[c.phone,c.cccd,c.id].filter(Boolean).join(' · ')));b.addEventListener('click',()=>choose(c.id));box.append(b);});
      box.hidden=!results.length;$('customer-query').setAttribute('aria-expanded',String(!!results.length));$('customer-search-status').textContent=results.length?'Chọn một hồ sơ trong danh sách.':'Không tìm thấy. Bấm nút + để thêm khách.';
    }catch(e){if(version===searchVersion){closeResults();$('customer-search-status').textContent=e.message;}}
  }
  $('customer-query').addEventListener('input',()=>{clearCustomer();searchVersion++;closeResults();clearTimeout(searchTimer);searchTimer=setTimeout(search,280);});
  $('customer-query').addEventListener('keydown',event=>{
    if(event.key==='Escape'){closeResults();return;}
    if(event.key==='Enter'){event.preventDefault();clearTimeout(searchTimer);if(active>=0&&!$('customer-results').hidden)choose(results[active].id);else search();return;}
    if(['ArrowDown','ArrowUp'].includes(event.key)&&!$('customer-results').hidden){event.preventDefault();active=(active+(event.key==='ArrowDown'?1:-1)+results.length)%results.length;Array.from($('customer-results').children).forEach((b,i)=>b.setAttribute('aria-selected',String(i===active)));const b=$('customer-option-'+active);$('customer-query').setAttribute('aria-activedescendant',b.id);b.scrollIntoView({block:'nearest'});}
  });
  document.addEventListener('click',e=>{if(!e.target.closest('.customer-lookup'))closeResults();});
  document.addEventListener('pawn:customer-saved',e=>{if(e.detail.custId)choose(e.detail.custId);});
  window.addEventListener('message',e=>{
    const frame=frames.find(f=>e.source===f.contentWindow);
    if(e.origin!==location.origin||!frame||e.data?.source!=='khcd-pawn-photos')return;
    const {type,detail={}}=e.data;
    if(type==='view'){openPhotoGallery(detail.name);return;}
    if(type==='ready'){if(loaded)post('lock',{locked:true,id:loaded.customer.id,photos:loaded.photos});else if(selected)post('customer',selected);}
    if(type==='expand'){frame.classList.toggle('is-expanded',!!detail.open);frame.closest('.desk-section,.desk-right').classList.toggle('photo-owner-expanded',!!detail.open);document.body.classList.toggle('pawn-photo-expanded',frames.some(f=>f.classList.contains('is-expanded')));}
    if(type==='file'&&!loaded&&['anh_truoc','anh_sau','anh_sp1','anh_sp2','anh_qr'].includes(detail.name)){
      if(detail.file)photos.set(detail.name,detail.file);else photos.delete(detail.name);if(detail.user)dirty=true;
      if(detail.name==='anh_qr'){if(!detail.file)qrVersion++;else if(detail.user&&!detail.parsed)readQr('bank','',detail.file);}
    }
    if(type==='scan'&&!loaded&&photos.get('anh_qr'))readQr('bank','',photos.get('anh_qr'));
  });
  function clearDraft(){loaded=null;savedSku='';lookupVersion++;qrVersion++;searchVersion++;clearTimeout(searchTimer);closeResults();lockForm(false);form.reset();form.elements.request_key.value=crypto.randomUUID();cancelDeadline=0;refreshCancellation();$('loaded-pawn-id').value='';$('receipt-state').textContent='PHIẾU MỚI';$('customer-search-status').textContent='Tìm và chọn khách KK.';$('item-error').textContent='';$('desk-save-status').textContent='Kiểm tra thông tin trước khi lưu phiếu.';$('receipt-status').textContent='';$('receipt-query').value='';rows=[];photos.clear();clearCustomer();$('customer-query').value='';post('reset');resetEditor();render();update(true);error('');dirty=false;}
  $('clear-draft').addEventListener('click',()=>{if(busy)return;if(loaded){if($('clear-draft').disabled)return;$('cancel-reason').value='';$('cancel-returned').checked=false;$('cancel-error').textContent='';$('cancel-amounts').textContent='Dòng tiền cần hoàn trả: tiền mặt '+money(serverAmount(loaded.cancellation.cash_return))+' · chuyển khoản '+money(serverAmount(loaded.cancellation.bank_return));$('cancel-session-dialog').showModal();return;}if(dirty)$('clear-draft-dialog').showModal();else clearDraft();});
  $('confirm-clear-draft').addEventListener('click',()=>{clearDraft();$('clear-draft-dialog').close();});
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(busy||loaded||savedSku)return;
    if(!$('entry-customer').value){error('Tìm và chọn hồ sơ khách trước khi lưu.');$('customer-query').focus();return;}
    if(!rows.length){error('Thêm ít nhất một món vàng vào biên nhận.');return;}
    if($('item-desc').value.trim()||$('item-gross').value){error('Món đang nhập chưa được thêm. Bấm THÊM hoặc xóa nội dung món đang nhập.');return;}
    const principal=amount($('principal').value),bank=$('pay-bank').checked?amount($('bank-amount').value):0n;
    if(principal<=0n||principal>999999999999n){error('Tiền cầm phải từ 1 đến 999.999.999.999 đồng.');return;}
    if((!$('pay-cash').checked&&!$('pay-bank').checked)||bank>principal||($('pay-bank').checked&&bank<=0n)){error('Kiểm tra phương thức và số tiền chi cho khách.');return;}
    const cash=amount($('cash-input').value);if(cash+bank!==principal){error('Tiền mặt + chuyển khoản phải bằng số tiền cầm.');return;}
    const fd=new FormData(form);fd.set('payment_method','cash');fd.set('cash_amount',cash.toString());fd.set('value',principal.toString());fd.set('bank_amount',bank.toString());fd.set('items_json',JSON.stringify(rows));photos.forEach((file,name)=>{if(name!=='anh_qr'||bank>0n)fd.append(name,file,file.name||name+'.jpg');});
    busy=true;form.inert=true;frames.forEach(f=>f.inert=true);error('');$('save-pawn').disabled=true;$('save-pawn').setAttribute('aria-busy','true');$('desk-save-status').textContent='Đang kiểm tra và lưu phiếu…';
    try{let response,data;
      try{response=await fetch(form.action,{method:'POST',body:fd,headers:{Accept:'application/json'}});data=await response.json();}
      catch(problem){
        if(form.dataset.saveStatus){try{const check=await fetch(form.dataset.saveStatus+'?request_key='+encodeURIComponent(fd.get('request_key')));const recovered=await check.json();if(check.ok&&recovered.url){response=check;data=recovered;}}catch(_){}}
        if(!data?.url)throw new Error('Chưa xác định được kết quả lưu. Giữ phiếu này và kiểm tra lịch sử trước khi thử lại.');
      }
      if(!response.ok||!data.url)throw new Error(data.error||'Chưa lưu được phiếu. Dữ liệu đang nhập được giữ lại.');savedSku=data.sku;dirty=false;$('receipt-query').value=data.sku;lockForm(true);await lookupReceipt(data.sku);if(!loaded){$('desk-save-status').textContent='Đã lưu '+data.sku+'. Nhập mã này để mở lại phiếu.';cancelDeadline=0;refreshCancellation();}
    }catch(e){form.inert=false;frames.forEach(f=>f.inert=false);error(savedSku?'Đã lưu '+savedSku+'; chưa hiển thị lại được phiếu. Nhập mã để mở lại.':e.message);$('desk-save-status').textContent=savedSku?'Đã lưu '+savedSku:'Chưa hoàn tất · nội dung đang nhập được giữ lại.';busy=false;$('save-pawn').disabled=!!savedSku;$('save-pawn').removeAttribute('aria-busy');}
    finally{form.inert=false;frames.forEach(f=>f.inert=false);busy=false;$('save-pawn').removeAttribute('aria-busy');refreshCancellation();}
  });
  function canEditPayment(){return !!loaded?.checkout?.payment_edit?.allowed&&performance.now()<paymentDeadline;}
  function refreshPaymentControls(){
    const editable=canEditPayment();
    for(const id of ['pay-cash','pay-bank','bank-amount','cash-input','bank-qr-input','scan-bank','make-outgoing-qr']){const field=$(id);if(field)field.disabled=!editable;}
    for(const key of ['bank_name','bank_account','bank_holder','bank_reference'])form.elements.namedItem(key).disabled=!editable;
    if($('make-outgoing-qr'))$('make-outgoing-qr').hidden=!editable||!$('pay-bank').checked;
    if(editable&&serverAmount(loaded.checkout.payment.bank_amount)>0n)$('pay-cash').disabled=true;
    if($('payment-window'))$('payment-window').textContent=editable?'Có thể chọn chuyển khoản trong '+Math.ceil((paymentDeadline-performance.now())/60000)+' phút.':loaded?'Thanh toán đã khóa hoặc phiên không phải CHI.':'Xác nhận phiếu trước để chọn chuyển khoản.';
  }
  function outgoingData(mode){const fd=new FormData();fd.set('csrf_token',form.elements.csrf_token.value);fd.set('mode',mode);fd.set('log_id',loaded.checkout.log_id);fd.set('payment_version',loaded.checkout.payment_edit.version);fd.set('request_key',outgoingKey);for(const key of ['bank_name','bank_account','bank_holder','bank_reference'])fd.set(key,form.elements.namedItem(key).value);fd.set('bank_code',bankCode);fd.set('bank_amount',digits($('bank-amount').value)||'0');return fd;}
  $('make-outgoing-qr').addEventListener('click',async()=>{
    if(!canEditPayment()||busy)return;outgoingKey=crypto.randomUUID();outgoingPreview=null;const receipt=loaded,fd=outgoingData('preview');$('outgoing-qr-status').textContent='Đang tạo QR…';$('save-outgoing-qr').disabled=true;$('outgoing-qr-image').removeAttribute('src');$('outgoing-qr-dialog').showModal();
    try{const response=await fetch(receipt.checkout.payment_edit.url,{method:'POST',body:fd,headers:{Accept:'application/json'}});const data=await response.json();if(!response.ok)throw Error(data.error||'Không tạo được QR.');if(loaded!==receipt)return;outgoingPreview={fd,data,receipt};$('outgoing-qr-image').src='data:'+data.qr_mime+';base64,'+data.qr_image;$('outgoing-qr-status').textContent=[data.bank_name,data.bank_account,data.bank_holder,'CHUYỂN '+money(serverAmount(data.bank_amount)),data.bank_reference].join(' · ');$('save-outgoing-qr').disabled=false;}catch(error){$('outgoing-qr-status').textContent=error.message;}
  });
  $('save-outgoing-qr').addEventListener('click',async()=>{
    if(!outgoingPreview||busy||loaded!==outgoingPreview.receipt)return;const {fd,receipt}=outgoingPreview;fd.set('mode','save');busy=true;$('save-outgoing-qr').disabled=true;
    try{const response=await fetch(receipt.checkout.payment_edit.url,{method:'POST',body:fd,headers:{Accept:'application/json'}});const data=await response.json();if(!response.ok)throw Error(data.error||'Chưa lưu được chuyển khoản.');$('outgoing-qr-dialog').close();await lookupReceipt(data.sku);$('bank-status').textContent='Đã lưu QR và phương thức chuyển khoản. Chưa xác nhận ngân hàng đã chuyển tiền.';}catch(error){$('outgoing-qr-status').textContent=error.message;$('save-outgoing-qr').disabled=false;}finally{busy=false;}
  });
  form.elements.bank_name.addEventListener('input',()=>{bankCode='';});
  function refreshCancellation(){
    refreshPaymentControls();
    const seconds=Math.max(0,Math.ceil((cancelDeadline-performance.now())/1000));
    const allowed=!!loaded?.cancellation?.allowed&&seconds>0&&!initialDisabled.get($('save-pawn'));
    $('clear-draft').disabled=busy||(!!loaded&&!allowed);
    $('cancel-window').textContent=loaded?(allowed?'Có thể hủy trong '+Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')+' · cần thu hồi tiền.':(loaded.cancellation?.allowed?'Đã hết thời hạn hủy 5 phút.':loaded.cancellation?.reason||'Phiếu chỉ xem.')):'';
    $('confirm-cancel-session').disabled=busy||!allowed;
  }
  setInterval(refreshCancellation,1000);
  $('confirm-cancel-session').addEventListener('click',async()=>{
    if(busy||!loaded)return;
    const reason=$('cancel-reason').value.trim();
    if(!reason||!$('cancel-returned').checked){$('cancel-error').textContent='Nhập lý do và xác nhận đã thu hồi đủ tiền.';return;}
    const fd=new FormData();fd.set('csrf_token',form.elements.csrf_token.value);fd.set('pid',loaded.id);fd.set('fingerprint',loaded.fingerprint);fd.set('request_key',cancelKey);fd.set('reason',reason);fd.set('returned_funds','yes');
    busy=true;refreshCancellation();$('cancel-error').textContent='Đang hủy phiên…';
    try{const response=await fetch(form.dataset.cancel,{method:'POST',body:fd,headers:{Accept:'application/json'}});const data=await response.json();if(!response.ok||data.error)throw new Error(data.error||'Chưa hủy được phiên.');
      const sku=loaded.sku;loaded.cancellation.allowed=false;cancelDeadline=0;$('cancel-session-dialog').close();await lookupReceipt(sku);$('desk-save-status').textContent=data.message;
    }catch(e){$('cancel-error').textContent=e.message||'Chưa xác định kết quả. Kiểm tra lịch sử trước khi tiếp tục.';}
    finally{busy=false;refreshCancellation();}
  });
  function lockForm(on){
    form.classList.toggle('desk-locked',on);
    initialDisabled.forEach((disabled,field)=>{field.disabled=on?!['receipt-query','scan-receipt','open-desk-sessions','new-receipt'].includes(field.id):disabled;});
    $('open-receipt-history').disabled=!(on&&loaded);
    $('open-receipt-history').dataset.loanId=on&&loaded?loaded.id:'';
    $('open-receipt-history').dataset.sku=on&&loaded?loaded.sku:'';
    $('open-receipt-history').title=on&&loaded?'Nhật ký giao dịch '+loaded.sku:'Mở phiếu để xem lịch sử giao dịch';
    $('print-pawn').disabled=!(on&&loaded);
    $('print-pawn').textContent='▤ IN PHIẾU'+(on&&loaded?.count_print?' ('+loaded.count_print+')':'');
    document.querySelectorAll('[data-pawn-action]').forEach(b=>{b.disabled=b.dataset.pawnAction!=='1'&&(!on||!loaded?.active);b.title=b.disabled?'Quét phiếu đang cầm để mở nghiệp vụ':b.dataset.actionName;b.classList.toggle('is-active',b.dataset.pawnAction==='1'&&!on);});
    refreshPaymentControls();
    if(!on){form.querySelectorAll('option[data-loaded]').forEach(o=>o.remove());post('lock',{locked:false});}
  }
  function selectStored(select,value,label){let option=Array.from(select.options).find(o=>o.value===String(value));if(!option){option=new Option(label||value,String(value));option.dataset.loaded='1';select.add(option);}select.value=String(value);}
  function openReceipt(p){
    lookupVersion++;qrVersion++;selectVersion++;searchVersion++;clearTimeout(searchTimer);closeResults();loaded=p;paymentDeadline=performance.now()+(p.checkout?.payment_edit?.remaining_seconds||0)*1000;bankCode=p.checkout?.payment?.bank_code||'';cancelKey=crypto.randomUUID();cancelDeadline=performance.now()+(p.cancellation?.remaining_seconds||0)*1000;dirty=false;photos.clear();rows=p.items;selected={id:p.customer.id,photos:p.photos};
    $('loaded-pawn-id').value=p.id;$('receipt-query').value=p.sku;$('receipt-state').textContent=p.status_name;
    $('receipt-status').textContent='Đang xem '+p.sku+' · Thông tin đã khóa. Chọn nghiệp vụ bên trái.';
    $('item-error').textContent='';$('desk-save-status').textContent='Phiếu đã lưu · chỉ xem và in.';
    $('entry-customer').value=p.customer.id;$('customer-query').value=p.customer.name;
    for(const key of ['name','phone','cccd','addr'])$('customer-'+key).textContent=p.customer[key]||'—';$('customer-facts').hidden=false;
    $('customer-search-status').textContent=p.customer_error||'';
    selectStored(form.elements.employee_id,p.employee_id||'legacy',p.employee_name);
    selectStored(form.elements.safe,p.safe||'',p.safe?'Tủ cũ · '+p.safe:'Chưa có tủ');$('entry-date').value=p.date1;$('principal').value=fmt(serverAmount(p.value));
    const rate=Array.from($('monthly-rate').options).find(o=>Number(o.value)===Number(p.monthly_rate));
    selectStored($('monthly-rate'),rate?.value||p.monthly_rate,p.monthly_rate+'% / tháng');
    const days=Math.round((new Date(p.due)-new Date(p.date1))/86400000);selectStored($('term'),Number.isFinite(days)&&days>0?days:30);
    form.elements.note.value=p.checkout?p.checkout.note:p.note;
    const displayedPayment=p.checkout?.payment||p.payment;
    for(const key of ['bank_name','bank_account','bank_holder','bank_reference'])form.elements.namedItem(key).value=displayedPayment[key]||'';
    $('bank-amount').value=fmt(serverAmount(displayedPayment.bank_amount));$('cash-input').value=fmt(serverAmount(displayedPayment.cash));
    form.elements.bank_reference.value=displayedPayment.bank_reference||p.sku;$('pay-bank').checked=serverAmount(displayedPayment.bank_amount)>0n;$('pay-cash').checked=!$('pay-bank').checked;$('bank-status').textContent='';
    render();$('item-summary').value=p.content;update();lockForm(true);syncCustomerActions();post('lock',{locked:true,id:p.customer.id,photos:p.photos});refreshCancellation();error('');
  }
  async function lookupReceipt(raw){
    const version=++lookupVersion;$('receipt-status').textContent='Đang tìm biên nhận…';
    try{const p=await get(form.dataset.lookup+'?q='+encodeURIComponent(raw));if(version!==lookupVersion)return;
      if(dirty&&!loaded){pendingReceipt=p;$('receipt-open-dialog').showModal();}else openReceipt(p);
    }catch(e){if(version===lookupVersion){$('receipt-status').textContent=e.message;if(loaded)$('receipt-query').value=loaded.sku;}}
  }
  $('confirm-open-receipt').addEventListener('click',()=>{if(pendingReceipt)openReceipt(pendingReceipt);pendingReceipt=null;$('receipt-open-dialog').close();});
  $('receipt-query').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();lookupReceipt(e.target.value);}});
  document.addEventListener('khcd:open-receipt',e=>{if(!busy&&e.detail?.sku)lookupReceipt(String(e.detail.sku));});
  $('print-pawn').addEventListener('click',()=>{if(loaded)window.open(loaded.detail_url,'_blank','noopener');});
  document.querySelectorAll('[data-pawn-action]').forEach(button=>button.addEventListener('click',async()=>{
    if(busy)return;const id=Number(button.dataset.pawnAction);if(id===1){if(dirty)$('clear-draft-dialog').showModal();else clearDraft();return;}
    if(!loaded)return;if(loaded.preview_url){showNativeOperation(id,button.dataset.actionName);return;}const version=++operationVersion;
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
  let nativeOp=0,nativeQuote=null,nativeKey='',nativeVersion=0,nativeQrUrl='',nativeTimer;
  const nf=$('native-operation-form');
  function nativeDate(date){return date.getFullYear()+'-'+String(date.getMonth()+1).padStart(2,'0')+'-'+String(date.getDate()).padStart(2,'0');}
  function nextNativeDue(){const value=nf.elements.transaction_date.value;if(!value)return;const date=new Date(value+'T12:00:00');date.setDate(date.getDate()+Number($('native-term').value));nf.elements.due.value=nativeDate(date);}
  function nativeChanged(event){nativeVersion++;$('native-payment-confirm').disabled=true;nativeQuote=null;$('native-confirm').disabled=true;$('native-total-amount').textContent='—';$('native-totals').textContent='Đang tính lại…';if(event?.target===nf.elements.transaction_date||event?.target===$('native-term'))nextNativeDue();else if(event?.target===nf.elements.due){const days=Math.round((new Date(nf.elements.due.value+'T12:00:00')-new Date(nf.elements.transaction_date.value+'T12:00:00'))/86400000);if(Number.isFinite(days)&&days>0){selectStored($('native-term'),days,days+' ngày');}}clearTimeout(nativeTimer);nativeTimer=setTimeout(()=>{if($('native-operation-dialog').open&&!busy)$('native-calculate').click();},350);}
  nf.addEventListener('input',nativeChanged);nf.addEventListener('change',nativeChanged);$('native-payment-dialog').addEventListener('input',nativeChanged);$('native-payment-dialog').addEventListener('change',nativeChanged);
  $('native-operation-dialog').addEventListener('close',()=>{clearTimeout(nativeTimer);nativeVersion++;});
  async function showNativeOperation(op,title){
    if(busy)return;nativeOp=op;nativeQuote=null;nativeKey=crypto.randomUUID();const v=++nativeVersion;nf.reset();clearNativeQr();
    $('native-session-qr').hidden=true;$('native-confirm').disabled=true;$('native-operation-title').textContent=title;$('native-receipt').textContent=loaded.sku+' · '+loaded.customer.name;
    $('native-amount-label').hidden=![2,3].includes(op);$('native-due-label').hidden=![2,3,4].includes(op);
    $('native-renewal-fields').hidden=![2,3,4].includes(op);$('native-date-label').hidden=false;$('native-principal-change').hidden=![2,3].includes(op);$('native-amount-caption').textContent=op===2?'Cầm thêm':'Trả bớt';$('native-new-principal').value=money(serverAmount(loaded.value));
    nf.elements.transaction_date.disabled=![2,3,4].includes(op);nf.elements.next_monthly_rate.disabled=![2,3,4].includes(op);
    $('native-next-title').textContent=[2,3,4].includes(op)?'Thông tin kỳ tiếp':'Thông tin phiên';
    $('native-principal').value=money(serverAmount(loaded.value));$('native-previous').value=loaded.checkout?.at||loaded.date1;
    selectStored($('native-current-rate'),Number(loaded.monthly_rate).toFixed(1),Number(loaded.monthly_rate).toFixed(1)+'% / tháng');$('native-current-rate').disabled=![2,3,4,5,6].includes(op);$('native-days').value='—';$('native-interest').value='—';$('native-cash').value='—';$('native-total-amount').textContent='—';
    $('native-total-label').textContent=op===2?'TỔNG CHI':'TỔNG THU';
    nf.elements.transaction_date.value=[2,3,4].includes(op)?[nativeDate(new Date()),loaded.checkout?.interest_from||''].sort().pop():nativeDate(new Date());nf.elements.transaction_date.min=loaded.checkout?.interest_from||loaded.date1;
    nf.elements.next_monthly_rate.value=String(Number(loaded.monthly_rate));
    const due=new Date();due.setDate(due.getDate()+30);nf.elements.due.value=due.getFullYear()+'-'+String(due.getMonth()+1).padStart(2,'0')+'-'+String(due.getDate()).padStart(2,'0');
    if([2,3,4].includes(op))nextNativeDue();
    $('native-bank-label').hidden=op===2;$('native-customer-bank').hidden=op!==2;$('native-lost-label').hidden=!loaded.receipt_lost||![5,6].includes(op);
    for(const key of ['bank_name','bank_account','bank_holder'])nf.elements.namedItem(key).value=loaded.payment[key]||'';
    $('native-policy').textContent=op===2?'Chốt lãi trên gốc cũ, bù trừ vào tiền cầm thêm. Kỳ tiếp tính trên gốc mới.':op===3?'Thu gốc trả bớt và toàn bộ lãi đến hôm nay; kỳ sau tính trên dư gốc còn lại.':op===7?'Ghi nhận báo mất; giữ nguyên mốc lãi và dư gốc.':op===4?'Thu lãi đến hôm nay, bắt đầu kỳ lãi tiếp theo và cập nhật ngày hẹn.':'Thu hết dư gốc và lãi đến hôm nay. Kiểm tra giấy tờ, tài sản trước khi chốt.';
    $('native-error').textContent='';$('native-totals').textContent='Nhập thông tin rồi bấm Tính và đối chiếu.';$('native-bank').replaceChildren(new Option('Chọn tài khoản nhận',''));$('native-operation-dialog').showModal();
    {try{const data=await get(form.dataset.banks);if(nativeOp!==op||!$('native-operation-dialog').open)return;data.rows.forEach(b=>$('native-bank').add(new Option([b.bank_name||b.bank_bin,b.bank_number,b.bank_user].filter(Boolean).join(' · '),b.id)));$('native-bank').value=data.default_id==null?'':String(data.default_id);}catch(e){$('native-error').textContent=e.message;}}
    if(nativeOp===op&&$('native-operation-dialog').open)$('native-calculate').click();
  }
  function nativeData(includeQr=false){const fd=new FormData(nf);if(!includeQr||amount(nf.elements.bank_amount.value)===0n||!nf.elements.anh_qr.files.length)fd.delete('anh_qr');for(const key of ['amount','bank_amount','extra','discount'])fd.set(key,digits(fd.get(key)||'0')||'0');fd.set('csrf_token',form.elements.csrf_token.value);fd.set('operation',nativeOp);fd.set('request_key',nativeKey);fd.set('bank_amount','0');fd.delete('anh_qr');return fd;}
  function clearNativeQr(){if(nativeQrUrl)URL.revokeObjectURL(nativeQrUrl);nativeQrUrl='';$('native-qr-file').value='';$('native-qr-preview').removeAttribute('src');$('native-qr-preview').hidden=true;$('native-qr-clear').hidden=true;}
  $('native-qr-clear').addEventListener('click',()=>{clearNativeQr();nativeQuote=null;$('native-confirm').disabled=true;});
  $('native-qr-file').addEventListener('change',()=>{const file=$('native-qr-file').files[0];if(nativeQrUrl)URL.revokeObjectURL(nativeQrUrl);if(!file){clearNativeQr();return;}if(file.size>15*1024*1024){clearNativeQr();$('native-error').textContent='Ảnh QR tối đa 15 MB.';return;}nativeQrUrl=URL.createObjectURL(file);$('native-qr-preview').src=nativeQrUrl;$('native-qr-preview').hidden=false;$('native-qr-clear').hidden=false;});
  nf.elements.bank_amount.addEventListener('input',()=>{$('native-session-qr').hidden=amount(nf.elements.bank_amount.value)===0n;});
  $('native-calculate').addEventListener('click',async()=>{
    if(busy||!loaded)return;const v=++nativeVersion;nativeQuote=null;$('native-confirm').disabled=true;clearTimeout(nativeTimer);
    try{const response=await fetch(loaded.preview_url,{method:'POST',body:nativeData(),headers:{Accept:'application/json'}});const q=await response.json();if(v!==nativeVersion)return;if(!response.ok||q.error)throw new Error(q.error||'Không tính được phiên.');
      const net=BigInt(q.net);const total=net<0n?-net:net,bank=amount(nf.elements.bank_amount.value);
      if(bank>total)throw new Error('Chuyển khoản vượt tổng tiền phiên.');nativeQuote=q;$('native-bank-label').hidden=net<=0n;$('native-customer-bank').hidden=net>=0n;
      $('native-total-amount').textContent=money(total);$('native-total-label').textContent=net<0n?'TỔNG CHI':'TỔNG THU';$('native-days').value=q.days+' ngày';$('native-interest').value=money(BigInt(q.interest));$('native-cash').value=money(total-bank);
      $('native-new-principal').value=money(BigInt(q.principal_after));$('native-payment-total').textContent=(net<0n?'TỔNG CHI: ':'TỔNG THU: ')+money(total);$('native-payment-error').textContent='';$('native-payment-confirm').disabled=false;$('native-totals').textContent=[2,3].includes(nativeOp)?'':'Dư gốc sau: '+money(BigInt(q.principal_after));
      $('native-error').textContent='';$('native-confirm').disabled=false;
    }catch(e){$('native-error').textContent=e.message;$('native-payment-error').textContent=e.message;}
  });
  nf.addEventListener('submit',async e=>{
    e.preventDefault();if(busy||!nativeQuote||!loaded)return;
    const fd=nativeData(true),net=BigInt(nativeQuote.net);fd.set('confirmed_total',(net<0n?-net:net).toString());fd.set('fingerprint',nativeQuote.fingerprint);
    busy=true;nf.inert=true;$('native-payment-dialog').inert=true;$('native-confirm').disabled=true;
    try{const response=await fetch(loaded.commit_url,{method:'POST',body:fd,headers:{Accept:'application/json'}});const data=await response.json();if(!response.ok||data.error)throw new Error(data.error||'Chưa xác định kết quả. Giữ phiên để kiểm tra.');
      $('native-payment-dialog').close();$('native-operation-dialog').close();await lookupReceipt(data.sku);$('desk-save-status').textContent=data.message;
    }catch(err){$('native-error').textContent=err.message;$('native-payment-error').textContent=err.message;$('native-confirm').disabled=false;}
    finally{busy=false;nf.inert=false;$('native-payment-dialog').inert=false;refreshCancellation();}
  });
  document.addEventListener('input',event=>{const input=event.target;if(!input.matches('input[inputmode="numeric"]')||!['value','cash_amount','bank_amount','amount','extra','discount'].includes(input.name)&&input.id!=='item-price')return;const before=input.value,at=input.selectionStart??before.length,count=digits(before.slice(0,at)).length;input.value=digits(before)?fmt(amount(before)):'';let position=0,seen=0;while(position<input.value.length&&seen<count){if(/\d/.test(input.value[position]))seen++;position++;}input.setSelectionRange(position,position);},true);
  function showShopBank(){const bank=bankRows.find(b=>String(b.id)===$('operation-bank').value)||{};$('operation-bank-name').value=bank.bank_name||bank.bank_bin||'';$('operation-bank-number').value=bank.bank_number||'';$('operation-bank-holder').value=bank.bank_user||'';}
  $('operation-bank').addEventListener('change',showShopBank);
  let qrKind='receipt',cameraStream=null;
  function stopCamera(){cameraStream?.getTracks().forEach(t=>t.stop());cameraStream=null;$('desk-qr-video').srcObject=null;document.querySelector('.qr-camera').hidden=true;$('desk-qr-capture').hidden=true;}
  function showQr(kind){qrKind=kind;$('desk-qr-title').textContent=kind==='bank'?'Quét QR chuyển khoản khách':'Quét QR biên nhận';$('desk-qr-raw').value='';$('desk-qr-status').textContent='Dùng máy quét, chọn ảnh QR hoặc mở camera.';$('desk-qr-file').value='';$('desk-qr-dialog').showModal();$('desk-qr-raw').focus();}
  $('scan-receipt').addEventListener('click',()=>showQr('receipt'));$('scan-bank').addEventListener('click',()=>{if(canEditPayment())showQr('bank');});
  $('desk-qr-dialog').addEventListener('close',()=>{stopCamera();qrVersion++;});
  $('desk-qr-camera').addEventListener('click',async()=>{try{stopCamera();cameraStream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'},audio:false});if(!$('desk-qr-dialog').open){stopCamera();return;}$('desk-qr-video').srcObject=cameraStream;document.querySelector('.qr-camera').hidden=false;$('desk-qr-capture').hidden=false;}catch(e){$('desk-qr-status').textContent='Chưa mở được camera. Có thể chọn ảnh hoặc dùng máy quét.';}});
  $('desk-qr-capture').addEventListener('click',()=>{const video=$('desk-qr-video');if(!video.videoWidth){$('desk-qr-status').textContent='Đợi camera hiển thị hình.';return;}const canvas=document.createElement('canvas'),scale=Math.min(1,1600/video.videoWidth);canvas.width=Math.round(video.videoWidth*scale);canvas.height=Math.round(video.videoHeight*scale);canvas.getContext('2d').drawImage(video,0,0,canvas.width,canvas.height);canvas.toBlob(b=>{if(b)readQr(qrKind,'',new File([b],'qr-camera.jpg',{type:'image/jpeg'}));},'image/jpeg',.92);});
  $('desk-qr-file').addEventListener('change',e=>{if(e.target.files[0])readQr(qrKind,'',e.target.files[0]);});
  $('desk-qr-use').addEventListener('click',()=>readQr(qrKind,$('desk-qr-raw').value));
  $('desk-qr-raw').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();readQr(qrKind,e.target.value);}});
  $('bank-qr-input').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();readQr('bank',e.target.value);}});
  async function readQr(kind,text='',file=null){
    if(kind==='bank'&&loaded&&!canEditPayment())return;const version=++qrVersion,box=$('desk-qr-dialog').open?$('desk-qr-status'):$('bank-status');box.textContent='Đang đọc mã QR…';
    try{if(file&&file.size>15*1024*1024)throw new Error('Ảnh QR tối đa 15 MB.');
      const fd=new FormData();fd.set('csrf_token',form.elements.csrf_token.value);fd.set('kind',kind);fd.set('text',text);if(file)fd.append('image',file);
      const response=await fetch(form.dataset.qr,{method:'POST',body:fd,headers:{Accept:'application/json'}});const data=await response.json();if(version!==qrVersion)return;if(!response.ok||data.error)throw new Error(data.error||'Không đọc được QR.');
      if(kind==='receipt'){if($('desk-qr-dialog').open)$('desk-qr-dialog').close();lookupReceipt(data.text);return;}
      bankCode=data.bank_code||data.bank_name;const oldAccount=form.elements.bank_account.value;form.elements.bank_name.value=data.bank_name;form.elements.bank_account.value=data.bank_account;
      form.elements.bank_holder.value=data.bank_holder||(oldAccount===data.bank_account?form.elements.bank_holder.value:'');
      $('pay-bank').checked=true;update(true);$('bank-status').textContent=data.warning||'Đã đọc QR. Đối chiếu tài khoản và tên người nhận.';if(!loaded)dirty=true;
      if(!loaded&&data.qr_image&&!file){const bytes=Uint8Array.from(atob(data.qr_image),c=>c.charCodeAt(0));post('qr',{file:new File([bytes],'qr-khach.png',{type:'image/png'})});}
      else if(!loaded&&file)post('qr',{file});
      if($('desk-qr-dialog').open)$('desk-qr-dialog').close();
    }catch(e){if(version===qrVersion)box.textContent=e.message||'Chưa đọc được mã QR.';}
  }
  window.addEventListener('beforeunload',event=>{stopCamera();if(dirty){event.preventDefault();event.returnValue='';}});
  render();update(true);previewItem();if($('entry-customer').value)choose($('entry-customer').value);const initialReceipt=new URLSearchParams(location.search).get('receipt');if(initialReceipt)lookupReceipt(initialReceipt);
  window.addEventListener('focus',async()=>{if(!loaded?.print_count_url)return;const current=loaded;try{const r=await fetch(current.print_count_url);if(r.ok&&loaded===current){const d=await r.json();current.count_print=d.count_print;$('print-pawn').textContent='▤ IN PHIẾU'+(d.count_print?' ('+d.count_print+')':'');}}catch(_){}});
  const gallery=$('desk-photo-gallery');let galleryPhotos=[],galleryIndex=0;
  function showGalleryPhoto(){const photo=galleryPhotos[galleryIndex];if(!photo)return;$('gallery-image').src=photo.src;$('gallery-image').alt=photo.label;$('gallery-title').textContent=photo.label;$('gallery-count').textContent=(galleryIndex+1)+' / '+galleryPhotos.length;$('gallery-prev').disabled=$('gallery-next').disabled=galleryPhotos.length<2;}
  function openPhotoGallery(name){
    galleryPhotos=[];
    for(const frame of frames){
      try{for(const card of frame.contentDocument.querySelectorAll('[data-photo]')){const img=card.querySelector('[data-xem] img'),input=card.querySelector('[data-photo-input]');if(img?.getAttribute('src')&&input)galleryPhotos.push({name:input.name,label:card.dataset.label||img.alt||'Ảnh hồ sơ',src:img.currentSrc||img.src});}}catch(_){/* A frame still loading can be skipped. */}
    }
    if(!galleryPhotos.length)return;
    galleryIndex=Math.max(0,galleryPhotos.findIndex(p=>p.name===name));showGalleryPhoto();if(!gallery.open)gallery.showModal();
  }
  function stepGallery(delta){galleryIndex=(galleryIndex+delta+galleryPhotos.length)%galleryPhotos.length;showGalleryPhoto();}
  $('gallery-prev').addEventListener('click',()=>stepGallery(-1));$('gallery-next').addEventListener('click',()=>stepGallery(1));
  $('gallery-close').addEventListener('click',()=>gallery.close());
  gallery.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();stepGallery(e.key==='ArrowLeft'?-1:1);}});
  gallery.addEventListener('click',e=>{if(e.target===gallery)gallery.close();});
  gallery.addEventListener('close',()=>{$('gallery-image').removeAttribute('src');galleryPhotos=[];});
})();
