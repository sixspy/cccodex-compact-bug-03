import { api } from '../api.js';

export async function renderSettings(view, setMsg) {
  const j = await api('/api/settings');
  view.innerHTML = `
    <section class="card">
      <h2>台参数</h2>
      <p class="muted">压实阈值与对账模式；保存后立即写库。</p>
      <div class="wall">
        ${(j.items || []).map(s => `<article class="card">
          <h3>${s.label}</h3>
          <p class="muted">${s.key}</p>
          <input data-key="${s.key}" value="${s.value}" />
          <button data-save="${s.key}" class="primary" type="button">保存</button>
        </article>`).join('')}
      </div>
    </section>`;
  view.querySelectorAll('[data-save]').forEach(btn => {
    btn.onclick = async () => {
      try {
        const key = btn.dataset.save;
        const input = view.querySelector('input[data-key="'+key+'"]');
        await api('/api/settings', { method:'POST', body: JSON.stringify({ key, value: input.value }) });
        setMsg('已保存 ' + key);
        await renderSettings(view, setMsg);
      } catch (e) { setMsg(e.message, true); }
    };
  });

  try {
    const dash = await api('/api/void_ghost/dash');
    const chipClass = dash.chip === '已剔幽灵' ? 'ok' : 'bad';
    const truthClass = dash.truth === '已剔幽灵' ? 'ok' : 'bad';
    const voucherLines = (dash.vouchers || []).map(v =>
      `凭证#${v.id} 文件#${v.file_id} ${v.path} · ${v.size_bytes}字节 · 作废${v.voided_at}` +
      (v.revoked_at ? ` · 已清理${v.revoked_at}` : ' · 待清理')
    ).join('\n') || '暂无作废凭证';
    const mountLines = (dash.mounts || []).map(m =>
      `计划#${m.plan_id} ${m.plan_code} 挂着作废文件#${m.file_id} ${m.path}`
    ).join('\n') || '无幽灵挂载';
    view.innerHTML += `<section class="card" style="margin-top:1rem">
      <h3>作废幽灵清理（账册）</h3>
      <p>页面芯片 <span class="tag ${chipClass}">${dash.chip}</span>
         库内真相 <span class="tag ${truthClass}">${dash.truth}</span>
         <span class="muted">对齐：${dash.aligned} · 假绿：${dash.fake_green}</span></p>
      <p class="muted">残留幽灵 ${dash.ghost_count} 项；清理在服务端同一事务写凭证并删挂载行。</p>
      <div class="row">
        <button id="note_void_ghost" type="button">记一笔</button>
        <button id="purge_void_ghost" class="primary" type="button" ${dash.ghost_count === 0 ? 'disabled' : ''}>清理全部幽灵</button>
      </div>
      <h4 style="margin:.8rem 0 .3rem">作废凭证（库内可查）</h4>
      <pre class="muted" style="white-space:pre-wrap">${voucherLines}</pre>
      <h4 style="margin:.8rem 0 .3rem">幽灵挂载</h4>
      <pre class="muted" style="white-space:pre-wrap">${mountLines}</pre>
    </section>`;
    document.getElementById('note_void_ghost').onclick = async () => {
      try {
        await api('/api/void_ghost/note', { method:'POST', body: JSON.stringify({plan_id:1, note:'作废幽灵'}) });
        setMsg('已记账册');
        await renderSettings(view, setMsg);
      } catch (e) { setMsg(e.message, true); }
    };
    document.getElementById('purge_void_ghost').onclick = async () => {
      try {
        const r = await api('/api/void_ghost/purge', { method:'POST', body:'{}' });
        setMsg('清理完成：剔 ' + r.purge.removed + ' 项，剩余 ' + r.purge.remaining_ghosts);
        await renderSettings(view, setMsg);
      } catch (e) { setMsg(e.message, true); }
    };
  } catch (e) { /* surface optional */ }

}
