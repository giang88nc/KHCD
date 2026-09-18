/* Trang Biên nhận: nút Hôm nay + popup XEM (tải mảnh HTML /camdo/bien-nhan/<id>/xem vào <dialog>). CSP: không inline. */
(() => {
  const form = document.querySelector('.ll-filter');
  const todayBtn = form && form.querySelector('[data-today]');
  if (todayBtn) todayBtn.addEventListener('click', () => {
    const now = new Date(), iso = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    form.querySelector('[name=d1]').value = iso; form.querySelector('[name=d2]').value = iso;
    form.querySelector('[name=q]').value = ''; form.requestSubmit ? form.requestSubmit() : form.submit();
  });

  const dialog = document.getElementById('ll-modal');
  if (!dialog) return;
  const body = dialog.querySelector('[data-modal-body]');
  let opener = null, controller = null;

  const close = () => { if (dialog.open) dialog.close(); };
  dialog.addEventListener('close', () => { if (controller) controller.abort(); controller = null; if (opener) { opener.focus(); opener = null; } });
  dialog.addEventListener('click', event => {
    if (event.target.closest('[data-modal-close]')) return close();
    // Bấm ra vùng nền (backdrop) thì đóng; bấm trong nội dung thì giữ.
    const r = dialog.getBoundingClientRect();
    if (event.target === dialog && (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom)) close();
  });

  async function open(url, trigger) {
    opener = trigger || null;
    body.innerHTML = '<p class="ll-loading">Đang tải biên nhận…</p>';
    if (!dialog.open) dialog.showModal();
    if (controller) controller.abort();
    controller = new AbortController();
    try {
      const response = await fetch(url, { headers: { 'Accept': 'text/html' }, cache: 'no-store', signal: controller.signal });
      if (!response.ok || response.redirected) throw new Error(response.status === 404 ? 'Không tìm thấy biên nhận này.' : 'Chưa đọc được biên nhận. Kiểm tra kết nối hoặc đăng nhập lại.');
      body.innerHTML = await response.text();
      body.scrollTop = 0;
      const first = body.querySelector('.lm-close'); if (first) first.focus();
    } catch (error) {
      if (error.name === 'AbortError') return;
      body.innerHTML = '<p class="ll-error">' + error.message + '</p><p class="ll-loading"><button type="button" class="btn" data-modal-close>Đóng</button></p>';
    }
  }

  document.addEventListener('click', event => {
    const trigger = event.target.closest('[data-view]');
    if (!trigger) return;
    event.preventDefault();
    open(trigger.dataset.view, trigger);
  });

  // Mở thẳng popup khi URL có #xem=<id> (vd. quay về từ trang khác).
  const match = /^#xem=(\d+)$/.exec(location.hash);
  if (match) { const trigger = document.querySelector('tr[data-loan="' + match[1] + '"] [data-view]'); if (trigger) open(trigger.dataset.view, trigger); }
})();
