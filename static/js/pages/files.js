import { api } from '../api.js';

export async function renderFiles(view, setMsg) {
  const j = await api('/api/files');
  view.innerHTML = `
    <section class="card">
      <h2>小文件清单</h2>
      <p class="muted">登记湖区碎文件；作废后生成凭证并从计划挂载中清理，清理前不得进入合并。</p>
      <div class="row">
        <label>路径<input id="path" placeholder="lake/dw_x/part-9.parquet" /></label>
        <label>表名<input id="table" value="dw_orders" /></label>
        <label>字节<input id="size" type="number" value="250000" /></label>
        <button class="primary" id="reg" type="button">登记碎文件</button>
      </div>
    </section>
    <section class="wall" style="margin-top:1rem">
      ${(j.stats || []).map(s => `<article class="card"><h3>${s.table_name}</h3>
        <p>文件 ${s.file_count} · 碎文件 ${s.loose_count}</p>
        <p class="muted">${s.total_bytes} 字节</p></article>`).join('')}
    </section>
    <section class="wall" style="margin-top:1rem">
      ${(j.items || []).map(f => {
        const isVoid = f.status === '作废';
        const ghost = isVoid && f.ghost_mount;
        const chip = !isVoid
          ? '<span class="tag ok">已剔幽灵</span>'
          : ghost
            ? '<span class="tag bad">项残留</span>'
            : '<span class="tag ok">已剔幽灵</span>';
        return `<article class="card">
        <h3>${f.path}</h3>
        <span class="tag ${isVoid ? 'void' : ''}">${f.status}</span> ${chip}
        <p class="muted">${f.table_name} · ${f.size_bytes} 字节 · 挂载 ${f.mount_count || 0} 个计划</p>
        <div class="row">
          <button data-void="${f.id}" type="button" ${f.status==='已合并'?'disabled':''}>作废</button>
          ${ghost ? `<button class="primary" data-purge="${f.id}" type="button">清理幽灵</button>` : ''}
        </div>
      </article>`;
      }).join('') || '<p class="muted">暂无文件</p>'}
    </section>`;
  document.getElementById('reg').onclick = async () => {
    try {
      await api('/api/files', { method:'POST', body: JSON.stringify({
        path: document.getElementById('path').value,
        table_name: document.getElementById('table').value,
        size_bytes: Number(document.getElementById('size').value),
      })});
      setMsg('已登记碎文件');
      await renderFiles(view, setMsg);
    } catch (e) { setMsg(e.message, true); }
  };
  view.querySelectorAll('[data-void]').forEach(btn => {
    btn.onclick = async () => {
      try {
        await api('/api/files/' + btn.dataset.void + '/void', { method:'POST', body:'{}' });
        setMsg('已作废并生成作废凭证');
        await renderFiles(view, setMsg);
      } catch (e) { setMsg(e.message, true); }
    };
  });
  view.querySelectorAll('[data-purge]').forEach(btn => {
    btn.onclick = async () => {
      try {
        const r = await api('/api/void_ghost/purge', {
          method: 'POST',
          body: JSON.stringify({ file_id: Number(btn.dataset.purge) }),
        });
        setMsg('已清理幽灵 ' + r.purge.removed + ' 项，剩余 ' + r.purge.remaining_ghosts);
        await renderFiles(view, setMsg);
      } catch (e) { setMsg(e.message, true); }
    };
  });
}
