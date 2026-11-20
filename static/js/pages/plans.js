import { api } from '../api.js';

export async function renderPlans(view, setMsg) {
  const j = await api('/api/plans');
  view.innerHTML = `
    <section class="card">
      <h2>压实计划</h2>
      <div class="row">
        <label>编号<input id="code" value="CP-NEW-1" /></label>
        <label>标题<input id="title" value="新压实计划" /></label>
        <label>目标表<input id="table" value="dw_payments" /></label>
        <button class="primary" id="create" type="button">创建计划</button>
      </div>
    </section>
    <section class="wall" style="margin-top:1rem">
      ${(j.items || []).map(p => {
        const hasGhost = Number(p.ghost_count || 0) > 0;
        const chip = hasGhost
          ? '<span class="tag bad">项残留</span>'
          : '<span class="tag ok">已剔幽灵</span>';
        const ghostLine = hasGhost ? `<p class="err">幽灵挂载 ${p.ghost_count} 项，须先清理才能合并</p>` : '';
        return `<article class="card">
        <h3>${p.plan_code}</h3>
        <span class="tag">${p.status}</span> ${chip}
        <p>${p.title}</p>
        <p class="muted">${p.target_table} · ${p.item_count} 文件 · ${p.plan_bytes} 有效字节（已剔幽灵）</p>
        ${ghostLine}
        <div class="row">
          <button data-attach="${p.id}" type="button">挂入碎文件</button>
          <button data-pub="${p.id}" class="primary" type="button">发布</button>
          <button data-detail="${p.id}" type="button">详情</button><span class="tag" data-thick="void_ghost">${hasGhost ? '项残留' : '已剔幽灵'}</span>
        </div>
        <pre class="muted" id="d${p.id}"></pre>
      </article>`;
      }).join('') || '<p class="muted">暂无计划</p>'}
    </section>`;
  document.getElementById('create').onclick = async () => {
    try {
      await api('/api/plans', { method:'POST', body: JSON.stringify({
        plan_code: document.getElementById('code').value,
        title: document.getElementById('title').value,
        target_table: document.getElementById('table').value,
      })});
      setMsg('计划已创建');
      await renderPlans(view, setMsg);
    } catch (e) { setMsg(e.message, true); }
  };
  view.querySelectorAll('[data-attach]').forEach(btn => {
    btn.onclick = async () => {
      try {
        const r = await api('/api/plans/' + btn.dataset.attach + '/attach', { method:'POST', body:'{}' });
        setMsg('挂入 ' + r.attached + ' 个碎文件');
        await renderPlans(view, setMsg);
      } catch (e) { setMsg(e.message, true); }
    };
  });
  view.querySelectorAll('[data-pub]').forEach(btn => {
    btn.onclick = async () => {
      try {
        await api('/api/plans/' + btn.dataset.pub + '/publish', { method:'POST', body:'{}' });
        setMsg('已发布');
        await renderPlans(view, setMsg);
      } catch (e) { setMsg(e.message, true); }
    };
  });
  view.querySelectorAll('[data-detail]').forEach(btn => {
    btn.onclick = async () => {
      try {
        const r = await api('/api/plans/' + btn.dataset.detail);
        const lines = [
          '芯片：' + r.plan_chip + '（幽灵 ' + r.ghost_count + ' 项）',
          '有效字节：' + r.clean_bytes,
          '',
          ...r.items.map(x => `#${x.id} [${x.status}] ${x.path} · ${x.size_bytes} 字节`),
        ];
        if (r.ghost_items && r.ghost_items.length) {
          lines.push('', '幽灵项：');
          r.ghost_items.forEach(g => lines.push(`  幽灵 #${g.id} ${g.path}`));
        }
        document.getElementById('d' + btn.dataset.detail).textContent = lines.join('\n');
      } catch (e) { setMsg(e.message, true); }
    };
  });
}
