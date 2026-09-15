/* Nút IN PHIẾU — đếm lượt in rồi mở hộp thoại in của trình duyệt.

   ⚠ LUẬT BẤT DI BẤT DỊCH: BẤM IN THÌ PHẢI RA HỘP THOẠI IN.
   Bản cũ gộp hai việc vào chung một try: mạng chập, máy chủ bận, hay phiên đăng nhập hết hạn
   là ném lỗi TRƯỚC khi kịp gọi window.print() — người bán bấm IN, hiện một hộp báo lỗi, và
   KHÔNG có tờ phiếu nào. Đây là đường in dùng hằng ngày nên mất hộp thoại là mất việc.

   Nay tách hẳn: ĐẾM LƯỢT là việc phụ, hỏng thì thôi (chỉ ghi console); IN là việc chính,
   LUÔN chạy ở cuối. Số đếm trên nút chỉ đổi khi máy chủ trả về thật.
*/
(() => {
  const button = document.getElementById('tracked-print-button');
  if (!button) return;

  button.addEventListener('click', async () => {
    if (button.disabled) return;
    button.disabled = true;
    try {
      // ---- việc PHỤ: đếm lượt in. Hỏng cũng KHÔNG được chặn việc in ----
      try {
        const data = new FormData();
        data.set('csrf_token', button.dataset.csrf);
        const response = await fetch(button.dataset.url, {
          method: 'POST', body: data, headers: { Accept: 'application/json' },
        });
        if (response.ok) {
          const result = await response.json();
          if (result && result.count_print !== undefined) {
            button.textContent = 'IN PHIẾU (' + result.count_print + ')';
          }
        } else {
          console.warn('Không ghi được lượt in (HTTP ' + response.status + ') — vẫn in bình thường.');
        }
      } catch (loi) {
        console.warn('Không ghi được lượt in — vẫn in bình thường.', loi);
      }
      // ---- việc CHÍNH: luôn mở hộp thoại in ----
      window.print();
    } finally {
      button.disabled = false;
    }
  });
})();
