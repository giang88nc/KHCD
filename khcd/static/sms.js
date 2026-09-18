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
    const picks = [...document.querySelectorAll('[data-pick-msg]')], all = document.querySelector('[data-all-msg]'), btns = [...bulk.querySelectorAll('[data-bulk]')], count = bulk.querySelector('[data-bulk-count]');
    const sync = () => { const n = picks.filter(p => p.checked).length; if (count) count.textContent = n; btns.forEach(b => { b.disabled = !n; }); if (all) { all.checked = !!n && n === picks.length; all.indeterminate = n > 0 && n < picks.length; } };
    picks.forEach(p => p.addEventListener('change', sync));
    if (all) all.addEventListener('change', () => { picks.forEach(p => { p.checked = all.checked; }); sync(); });
    sync();
    // Hủy / XÓA nhóm: hỏi lại bằng hộp thoại chung rồi mới gửi đúng nút đã bấm (giữ formaction).
    bulk.querySelectorAll('[data-confirm-btn]').forEach(b => b.addEventListener('click', async e => {
      if (b.dataset.ok) { delete b.dataset.ok; return; }
      e.preventDefault();
      const ok = window.KHDialog ? await KHDialog.confirm({ title: b.dataset.confirmBtn, danger: true }) : confirm(b.dataset.confirmBtn);
      if (ok) { b.dataset.ok = '1'; bulk.requestSubmit ? bulk.requestSubmit(b) : b.click(); }
    }));
    bulk.addEventListener('submit', e => { const sub = e.submitter; if (sub && !sub.hasAttribute('formaction') && !bulk.querySelector('[name=gio]').value) e.preventDefault(); });
  }
  document.querySelectorAll('[data-auto-submit]').forEach(el => el.addEventListener('change', () => el.form.submit()));
  // XEM: dựng đúng nội dung tin ZNS (mẫu 635511) từ 6 biến đã chụp của dòng — chỉ gán textContent, không innerHTML.
  const xem = document.getElementById('sm-xem');
  if (xem) {
    const dat = (k, v) => xem.querySelectorAll('[data-x="' + k + '"]').forEach(el => { el.textContent = v || '…'; });
    document.addEventListener('click', e => {
      const b = e.target.closest('[data-xem-tin]'); if (!b) return;
      const d = b.dataset; dat('anh_chi', d.anhChi); dat('ten', d.ten); dat('ma', d.ma); dat('ngay', d.ngay); dat('days', d.days); dat('notes', d.notes);
      dat('rule', d.rule); dat('gio', d.gio ? 'Hẹn gửi ' + d.gio : '');
      xem.showModal();
    });
    xem.addEventListener('click', e => { if (e.target === xem || e.target.closest('[data-close-xem]')) xem.close(); });
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
