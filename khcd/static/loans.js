(() => {
  const panel = document.querySelector('[data-reconcile-url]');
  if (!panel) return;
  const button = panel.querySelector('[data-reconcile]'), status = panel.querySelector('[data-reconcile-status]'), body = panel.querySelector('[data-reconcile-rows]');
  const issuesOnly = panel.querySelector('[data-issues-only]');
  issuesOnly.addEventListener('change', () => { for (const row of body.rows) row.hidden = issuesOnly.checked && row.dataset.state === 'ok'; });
  async function check() {
    button.disabled = true; status.textContent = 'Đang đối soát dữ liệu và ảnh…'; body.replaceChildren();
    try {
      const response = await fetch(panel.dataset.reconcileUrl, {headers: {'Accept': 'application/json'}, cache: 'no-store'});
      if (!response.ok || response.redirected || !response.headers.get('content-type')?.includes('application/json')) throw new Error('Chưa đọc được kết quả. Kiểm tra kết nối hoặc đăng nhập lại.');
      const result = await response.json();
      status.textContent = `${result.errors} lỗi · ${result.warnings} cảnh báo · ${result.checks.length} hạng mục. Chưa có dữ liệu nào bị sửa.`;
      const order = {error: 0, warning: 1, ok: 2};
      for (const item of result.checks.sort((a,b) => order[a.state]-order[b.state])) {
        const tr = document.createElement('tr'); tr.dataset.state=item.state; tr.hidden=issuesOnly.checked && item.state==='ok';
        for (const [index, value] of [({error:'Lỗi',warning:'Cảnh báo',ok:'Khớp'})[item.state] || item.state, item.label, item.source, item.target, item.detail].entries()) {
          const td = document.createElement('td'); td.textContent = value == null || value === '' ? '—' : String(value);
          if (index === 0) td.className = `loan-check-${item.state}`;
          if (index === 4) td.className = 'loan-check-detail';
          tr.append(td);
        }
        body.append(tr);
      }
    } catch (error) { status.textContent = error.message; }
    finally { button.disabled = false; }
  }
  button.addEventListener('click', check); check();
  for (const img of document.querySelectorAll('.loan-photo img')) img.addEventListener('error', () => { const card=img.closest('.loan-photo'); img.hidden=true; card.classList.add('error'); card.querySelector('p').textContent='Ảnh không còn đọc được. Hãy đối soát lại để kiểm tra nguồn.'; });
})();

document.querySelectorAll('[data-print]').forEach(b=>b.addEventListener('click',()=>window.print()));
