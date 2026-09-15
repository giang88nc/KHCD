(function () {
  'use strict';
  var frame, opener, closing;
  function close() {
    if (frame) frame.remove(); frame = null;
    document.body.classList.remove('customer-popup-open');
    document.querySelector('.khcd-shell').inert = false;
    if (opener) opener.focus();
  }
  document.addEventListener('click', function (event) {
    var button = event.target.closest('[data-customer-popup]');
    if (!button) return;
    event.preventDefault(); if (frame) return;
    opener = button;
    frame = document.createElement('iframe');
    frame.className = 'customer-popup-frame'; frame.title = button.dataset.custId ? 'Sửa khách hàng' : 'Thêm khách hàng';
    frame.allow = 'camera self';
    frame.src = '/camdo/khach-hang/popup/frame' + (button.dataset.custId ? '?cust_id=' + encodeURIComponent(button.dataset.custId) : '');
    document.body.appendChild(frame); document.body.classList.add('customer-popup-open');
    document.querySelector('.khcd-shell').inert = true;
    frame.focus();
  });
  window.addEventListener('message', function (event) {
    if (!frame || event.source !== frame.contentWindow || event.origin !== window.location.origin ||
        !event.data || event.data.source !== 'khcd-customer-popup') return;
    if (event.data.type === 'close') {
      // KHBL emits close before khachSaved; allow the success message to arrive.
      closing = window.setTimeout(close, 60);
    } else if (event.data.type === 'saved') {
      window.clearTimeout(closing);
      if (document.getElementById('pawn-create')) {
        var detail=event.data.detail || {};
        close(); document.dispatchEvent(new CustomEvent('pawn:customer-saved',{detail:detail})); return;
      }
      sessionStorage.setItem('khcd-customer-saved', JSON.stringify(event.data.detail || {}));
      close(); window.location.reload();
    }
  });
  var saved = sessionStorage.getItem('khcd-customer-saved');
  if (saved) {
    sessionStorage.removeItem('khcd-customer-saved');
    try {
      var detail = JSON.parse(saved), notice = document.createElement('div');
      notice.className = 'flash success'; notice.setAttribute('role','status');
      notice.textContent = [detail.message || 'Đã lưu khách vào KK'].concat(detail.warnings || []).join(' · ');
      document.querySelector('.khcd-page').prepend(notice);
    } catch (_) { /* A stale local notification does not affect the customer list. */ }
  }
})();
