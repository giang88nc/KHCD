/* Transport/lifecycle only. All form, QR, phone and image behavior is KHBL's JS. */
(function () {
  'use strict';
  function notify(type, detail) {
    window.parent.postMessage({source:'khcd-customer-popup', type:type, detail:detail || {}}, window.location.origin);
  }
  var close = window.closeKhblModal;
  // The shared QR client reads this field, while HTMX reads the body header.
  document.querySelectorAll('[name="csrfmiddlewaretoken"]').forEach(function (field) {
    field.value = document.body.dataset.popupCsrf;
  });
  window.closeKhblModal = function () { close(); notify('close'); };
  document.addEventListener('khachSaved', function (event) {
    var d = event.detail || {};
    notify('saved', {custId:d.custId, message:d.message, warnings:d.warnings || []});
  });
  document.addEventListener('htmx:configRequest', function (event) {
    event.detail.headers['X-CSRFToken'] = document.body.dataset.popupCsrf;
  });
  function failed(event) {
    var form = document.getElementById('kh-form');
    if (!form) return;
    var box = document.getElementById('kh-luu-kq');
    var alert = document.createElement('div');
    alert.className = 'khbl-alert khbl-alert--do';
    alert.setAttribute('role','alert');
    alert.textContent = 'Chưa hoàn tất yêu cầu. Biểu mẫu vẫn được giữ lại. Nếu vừa lưu, kiểm tra kết quả trước khi gửi lại.';
    box.replaceChildren(alert);
    var token = form.querySelector('[name="save_token"]');
    if (token && event.detail && event.detail.elt && event.detail.elt.id === 'kh-form') {
      var link = document.createElement('a');
      link.href = '/camdo/khach-hang/ket-qua/' + encodeURIComponent(token.value);
      link.target = '_parent'; link.textContent = 'Kiểm tra kết quả lần lưu'; box.appendChild(link);
    }
  }
  ['htmx:responseError','htmx:sendError','htmx:timeout'].forEach(function (name) { document.addEventListener(name, failed); });
  notify('ready');
})();
