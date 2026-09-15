/* Presentation/transport adapter; KHBL still owns capture and CCCD crop. */
(() => {
 'use strict';
 const form=document.getElementById('kh-form');if(!form)return;
 const inputs=Array.from(form.querySelectorAll('[data-photo-input]'));
 let customer='',sources={},locked=false;
 const send=(type,detail={})=>parent.postMessage({source:'khcd-pawn-photos',type,detail},location.origin);
 function controls(input){const card=input.closest('[data-photo]'),cccd=['anh_truoc','anh_sau'].includes(input.name),disabled=locked||(cccd&&!customer),has=!!input._capturedFile||!!input.files?.length||!!input._hasSaved;
  input.disabled=disabled;card.classList.toggle('photo-disabled',disabled);card.querySelectorAll('button').forEach(b=>b.disabled=disabled||(b.classList.contains('kh-anh__btn--cat')&&!has));
 }
 function restore(input){input.value='';input._capturedFile=null;input._hasSaved=false;const card=input.closest('[data-photo]'),box=card.querySelector('[data-xem]');if(box.dataset.url){URL.revokeObjectURL(box.dataset.url);delete box.dataset.url;}box.replaceChildren();card.querySelector('[data-cat-tt]').textContent='';
  if(sources[input.name]){const img=document.createElement('img');img.alt=card.dataset.label;img.src=sources[input.name];img.addEventListener('load',()=>{input._hasSaved=true;controls(input);});img.addEventListener('error',()=>{box.textContent='Chưa có ảnh';input._hasSaved=false;controls(input);});box.append(img);}else box.textContent='Chưa có ảnh';controls(input);send('file',{name:input.name,file:null,user:false});
 }
 function picked(e){const input=e.target;if(!input.matches('[data-photo-input]')||locked)return;const file=e.detail?.file||input._capturedFile||input.files?.[0];if(!file)return;
  if(file.size>15*1024*1024){restore(input);input.closest('[data-photo]').querySelector('[data-cat-tt]').textContent='Ảnh tối đa 15 MB.';return;}
  controls(input);send('file',{name:input.name,file,user:true,parsed:!!e.detail?.fromScan});input.closest('[data-photo]').querySelector('[data-cat-tt]').textContent='';
 }
 document.addEventListener('change',picked);document.addEventListener('khbl:anh-dat',picked);
 inputs.forEach(input=>{const button=document.createElement('button');button.type='button';button.className='photo-remove khbl-btn khbl-btn--outline';button.textContent='×';button.title='Bỏ ảnh vừa chọn';button.setAttribute('aria-label','Bỏ ảnh vừa chọn');button.addEventListener('click',()=>{restore(input);send('file',{name:input.name,file:null,user:true});});input.closest('[data-photo]').querySelector('.kh-anh__actions').append(button);controls(input);});
 window.closeKhblModal=()=>{window.__khblStopCamera?.();window.khblKhCatDong?.();};
 const camera=document.getElementById('kh-camera'),crop=document.getElementById('kh-cat-root');
 function expanded(){const open=!!camera?.open||!!crop?.innerHTML.trim();document.body.classList.toggle('photo-expanded',open);send('expand',{open});}
 if(camera)new MutationObserver(expanded).observe(camera,{attributes:true,attributeFilter:['open']});if(crop)new MutationObserver(expanded).observe(crop,{childList:true});
 window.addEventListener('message',e=>{if(e.origin!==location.origin||e.source!==parent||e.data?.source!=='khcd-pawn-parent')return;const {type,detail={}}=e.data;
  if(type==='customer'&&!locked){const changed=customer!==detail.id;customer=detail.id||'';sources=detail.photos||{};form.querySelector('[name=CustID]').value=customer;inputs.filter(i=>['anh_truoc','anh_sau','anh_qr'].includes(i.name)).forEach(i=>{if(changed||!customer||(!i.files?.length&&!i._capturedFile))restore(i);});}
  if(type==='lock'){locked=!!detail.locked;if(locked){customer=detail.id||'';sources=detail.photos||{};inputs.forEach(restore);window.closeKhblModal();}inputs.forEach(controls);}
  if(type==='reset'){locked=false;customer='';sources={};form.querySelector('[name=CustID]').value='';inputs.forEach(restore);window.closeKhblModal();}
  if(type==='qr'&&!locked){const input=inputs.find(i=>i.name==='anh_qr');if(input&&detail.file){input._capturedFile=detail.file;try{const dt=new DataTransfer();dt.items.add(detail.file);input.files=dt.files;}catch(_){}input.dispatchEvent(new CustomEvent('khbl:anh-dat',{bubbles:true,detail:{file:detail.file,fromScan:true}}));}}
 });
 form.addEventListener('submit',e=>e.preventDefault());window.addEventListener('beforeunload',()=>window.__khblStopCamera?.());send('ready');
})();
