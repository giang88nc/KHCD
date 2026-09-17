/* gcd-print.js — chot chan truoc khi in len GIAY IN SAN, va DUONG IN PHIA MAY CHU.

   HAI VIEC, TACH BACH:

   A. CHOT CHAN (luon chay): kiem CSS bo cuc (/camdo/bien-nhan/mau-in.css) da that su ap dung chua.
      Neu chua (phien het han tra HTML dang nhap, sai MIME, trinh duyet bo stylesheet khong bao gi)
      thi TAT nut in va hien dai do — vi khi do 17 khoi se xep chong len goc tren-trai to giay.
      KHONG BAO GIO tu goi window.print() o buoc nay: to giay in san la vat tu that, moi lan in phai
      do nguoi bam.

   B. NUT IN PHIA MAY CHU (chi khi co #gcd-nut-in): server da xac nhan cau hinh co may in, may chu
      co Edge + cong cu day ban in, va ten may in con trong Get-Printer. Bam IN thi:
         dem luot in -> POST data-may-url -> {ok:true} bao "Da gui toi <may in>"
                                          -> {ok:false} hoac het 30s thi ROI VE window.print()
      kem MOT dong giai thich mau XAM. Roi ve KHONG PHAI LOI: nguoi dung van in duoc, chi khac la
      phai tu chon may in trong hop thoai.

   HOM NAY may chu KHONG co may in vat ly va KHONG co cong cu day ban in => server luon dung
   id=tracked-print-button (receipt-print.js xu ly: dem luot roi window.print() NGAY, khong doi mot
   nhip nao). Toan bo nhanh B ben duoi nam im cho toi khi GD cai may in that. Do la CO Y: duong roi
   ve la duong chay that hang ngay nen no phai muot, khong duoc doi mot vong goi may chu. */
(() => {
  'use strict';
  const to = document.getElementById('gcd-to');
  if (!to) return;
  const nut = document.getElementById('tracked-print-button') || document.getElementById('gcd-nut-in');
  const bao = document.getElementById('gcd-bao-bocuc');
  const baoMay = document.getElementById('gcd-bao-may');

  // ---- A. CHOT CHAN --------------------------------------------------------------------------
  function kiem() {
    const khoi = to.querySelector('[data-gcd]');
    if (!khoi) return false;
    const k = getComputedStyle(khoi), t = getComputedStyle(to);
    // Bo cuc da ap dung => moi khoi phai la absolute, va to giay phai co be rong that (210mm).
    return k.position === 'absolute' && t.position === 'relative' && to.getBoundingClientRect().width > 100;
  }

  function ap() {
    const ok = kiem();
    if (bao) bao.hidden = ok;
    if (nut) {
      nut.disabled = !ok;
      nut.title = ok ? '' : 'Chua nap duoc bo cuc in — khong cho in de khoi hong to giay in san.';
    }
    return ok;
  }

  ap();
  window.addEventListener('load', ap);
  // Nguoi dung mo lai tab sau khi dang nhap lai o tab khac: kiem lai cho chac.
  window.addEventListener('focus', ap);

  // ---- B. IN PHIA MAY CHU --------------------------------------------------------------------
  const nutMay = document.getElementById('gcd-nut-in');
  if (!nutMay) return;
  const GIO_CHO = 30000;   // ngat som hon tong gio cho ben server (~43s) de nguoi dung khong ngoi doi

  function noi(chu, loai) {
    if (!baoMay) return;
    baoMay.textContent = chu;
    baoMay.className = 'gcd-bao no-print ' + (loai === 'ok' ? 'gcd-bao-xanh' : 'gcd-bao-xam');
    baoMay.hidden = false;
  }

  function bieuMau() {
    const d = new FormData();
    d.set('csrf_token', nutMay.dataset.csrf);
    return d;
  }

  async function demLuot() {
    // Dem luot in nhu duong cu (receipt-print.js): bam IN la tinh mot luot, du sau do co huy hop
    // thoai hay khong — giu DUNG MOT cach dem cho ca hai duong.
    const r = await fetch(nutMay.dataset.url, {method: 'POST', body: bieuMau(), headers: {Accept: 'application/json'}});
    if (!r.ok) throw new Error('Khong ghi duoc luot in.');
    const j = await r.json();
    if (j && j.count_print != null) nutMay.textContent = 'IN PHIẾU (' + j.count_print + ')';
  }

  function roiVe(lyDo) {
    noi('Không in được từ máy chủ (' + lyDo + ') — mở hộp thoại in của trình duyệt để chọn máy in.', 'xam');
    window.print();
  }

  nutMay.addEventListener('click', async () => {
    if (nutMay.disabled) return;
    nutMay.disabled = true;
    try {
      try { await demLuot(); } catch (e) { /* dem hut khong duoc phep chan viec in */ }
      let het = null;
      const dieu = ('AbortController' in window) ? new AbortController() : null;
      if (dieu) het = setTimeout(() => dieu.abort(), GIO_CHO);
      let ket;
      try {
        const r = await fetch(nutMay.dataset.mayUrl, {
          method: 'POST', body: bieuMau(), headers: {Accept: 'application/json'},
          signal: dieu ? dieu.signal : undefined});
        ket = await r.json();
      } finally { if (het) clearTimeout(het); }
      if (ket && ket.ok) noi(ket.thong_diep || 'Đã gửi tới máy in.', 'ok');
      else if (ket && ket.khoa) noi(ket.ly_do, 'xam');   // phieu khong duoc in: KHONG roi ve hop thoai
      else roiVe((ket && ket.ly_do) || 'máy chủ không trả lời rõ');
    } catch (e) {
      roiVe(e && e.name === 'AbortError' ? 'máy chủ không phản hồi kịp' : 'không gọi được máy chủ');
    } finally {
      nutMay.disabled = false;
    }
  });
})();
