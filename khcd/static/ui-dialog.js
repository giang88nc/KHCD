(() => {
  const dialog=document.createElement('dialog');dialog.className='khcd-message-dialog';
  dialog.innerHTML='<div class="message-symbol" aria-hidden="true">?</div><h2 id="shared-message-title"></h2><p id="shared-message-body" hidden></p><div class="message-buttons"><button type="button" class="message-no">Không</button><button type="button" class="message-yes">Có</button></div>';
  dialog.setAttribute('aria-labelledby','shared-message-title');document.body.append(dialog);
  const title=dialog.querySelector('h2'),body=dialog.querySelector('p'),no=dialog.querySelector('.message-no'),yes=dialog.querySelector('.message-yes');
  let resolveActive=null,queue=Promise.resolve();
  const finish=value=>{if(!resolveActive)return;const resolve=resolveActive;resolveActive=null;dialog.close();resolve(value);};
  no.addEventListener('click',()=>finish(false));yes.addEventListener('click',()=>finish(true));
  dialog.addEventListener('cancel',event=>{event.preventDefault();finish(false);});
  dialog.addEventListener('close',()=>{if(resolveActive){const resolve=resolveActive;resolveActive=null;resolve(false);}});
  const open=(options,notice)=>{const task=queue.then(()=>new Promise(resolve=>{
    resolveActive=resolve;title.textContent=options.title||(notice?'Thông báo':'Xác nhận');body.textContent=options.message||'';body.hidden=!options.message;
    if(options.message)dialog.setAttribute('aria-describedby','shared-message-body');else dialog.removeAttribute('aria-describedby');
    no.hidden=notice;yes.textContent=notice?'Đóng':'Có';dialog.querySelector('.message-symbol').textContent=notice?'i':'?';dialog.classList.toggle('is-danger',!!options.danger);dialog.showModal();(notice?yes:no).focus();
  }));queue=task.catch(()=>{});return task;};
  window.KHDialog={confirm:options=>open(options||{},false),notify:options=>open(options||{},true)};
})();
