/* sms.js — trang GỬI SMS: chọn tất cả, đếm tin, xác nhận hủy. CSP: không inline. */
(() => {
  const chon = document.getElementById('sm-chon');
  if (chon) {
    // Ô tick nằm trong bảng, NGOÀI thẻ form (gắn bằng thuộc tính form="sm-chon") → tìm trên cả trang.
    const picks = [...document.querySelectorAll('[data-pick]')], all = document.querySelector('[data-all]'), btn = chon.querySelector('[data-submit]'), count = chon.querySelector('[data-count]');
    const sync = () => { const n = picks.filter(p => p.checked).length; if (count) count.textContent = n; if (btn) btn.disabled = !n; if (all) all.checked = n && n === picks.length; };
    picks.forEach(p => p.addEventListener('change', sync));
    if (all) all.addEventListener('change', () => { picks.forEach(p => { p.checked = all.checked; }); sync(); });
    sync();
    chon.addEventListener('submit', e => { if (!picks.some(p => p.checked)) e.preventDefault(); });
  }
  const bulk = document.getElementById('sm-bulk');
  if (bulk) {
    const picks = [...document.querySelectorAll('[data-pick-msg]')], all = bulk.querySelector('[data-all-msg]'), btn = bulk.querySelector('[data-bulk]'), count = bulk.querySelector('[data-bulk-count]');
    const sync = () => { const n = picks.filter(p => p.checked).length; if (count) count.textContent = n; if (btn) btn.disabled = !n; if (all) all.checked = n && n === picks.length; };
    picks.forEach(p => p.addEventListener('change', sync));
    if (all) all.addEventListener('change', () => { picks.forEach(p => { p.checked = all.checked; }); sync(); });
    sync();
  }
  const rules = document.getElementById('sm-rules');
  if (rules) {
    document.querySelectorAll('[data-open-rules]').forEach(b => b.addEventListener('click', () => rules.showModal()));
    rules.querySelectorAll('[data-close-rules]').forEach(b => b.addEventListener('click', () => rules.close()));
  }
  document.querySelectorAll('form[data-confirm]').forEach(f => f.addEventListener('submit', async e => {
    if (f.dataset.ok) return; e.preventDefault();
    const ok = window.KHDialog ? await KHDialog.confirm({ title: f.dataset.confirm, danger: true }) : confirm(f.dataset.confirm);
    if (ok) { f.dataset.ok = '1'; f.requestSubmit ? f.requestSubmit() : f.submit(); }
  }));
})();
