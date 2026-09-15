document.querySelectorAll('[data-dialog]').forEach(button => button.addEventListener('click', () => document.getElementById(button.dataset.dialog).showModal()));
document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.getElementById('print-button')?.addEventListener('click', () => window.print());
document.getElementById('back-button')?.addEventListener('click', () => history.back());
if (['#renew-dialog','#redeem-dialog'].includes(location.hash)) {
  const action=document.querySelector('[data-dialog="'+location.hash.slice(1)+'"]');
  if(action && !action.disabled)document.getElementById(action.dataset.dialog)?.showModal();
}
const clockTime=document.querySelector('[data-clock-time]');
const clockDate=document.querySelector('[data-clock-date]');
function updateClock(){
  const now=new Date();
  if(clockTime) clockTime.textContent=new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(now);
  if(clockDate) clockDate.textContent=new Intl.DateTimeFormat('vi-VN',{timeZone:'Asia/Ho_Chi_Minh',weekday:'short',day:'2-digit',month:'2-digit',year:'numeric'}).format(now);
}
updateClock();
setInterval(updateClock,1000);
document.querySelectorAll('form[method="post"]:not([data-async])').forEach(form=>form.addEventListener('submit',()=>{
  form.querySelectorAll('button:not([type="button"])').forEach(button=>{
    button.disabled=true;button.setAttribute('aria-busy','true');
  });
}));
