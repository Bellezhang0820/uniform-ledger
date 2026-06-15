const app = document.querySelector('#app');
const tabs = document.querySelectorAll('.tab-btn');
const dialog = document.querySelector('#entryDialog');
const entryText = document.querySelector('#entryText');
const entryFile = document.querySelector('#entryFile');
const draftItemsEl = document.querySelector('#draftItems');
const parseErrors = document.querySelector('#parseErrors');
let activeTab = 'home';
let draftItems = [];
let currentSource = 'manual';
let charts = [];

const api = async (url, options = {}) => {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || res.statusText);
  const type = res.headers.get('content-type') || '';
  return type.includes('json') ? res.json() : res.text();
};
const money = n => `¥${Number(n || 0).toFixed(2)}`;
const today = () => new Date().toISOString().slice(0, 10);

function icon(name) { return `<span class="material-symbols-outlined text-[20px]">${name}</span>`; }
function shell(title, body) {
  app.innerHTML = `<section class="p-4 space-y-4"><header class="pt-2"><h1 class="text-2xl font-extrabold tracking-normal">${title}</h1></header>${body}</section>`;
}
function rowItem(item, editable = false, idx = 0) {
  return `<div class="card p-3 grid grid-cols-[1fr_auto] gap-2 text-sm">
    <div><div class="font-bold">${item.category_name || `${item.school_level}${item.fabric_type}${item.item_type}`}</div><div class="text-[#46464a] mono">${item.size || '无尺码'} x ${item.qty}${item.unit || ''}</div>${item.note ? `<div class="text-xs text-[#46464a]">${item.note}</div>` : ''}</div>
    ${editable ? `<button class="material-symbols-outlined" data-del-draft="${idx}">delete</button>` : `<div class="mono font-bold">${money((item.qty || 0) * (item.unit_price || 0))}</div>`}
  </div>`;
}

async function renderHome() {
  const [st, ordersData] = await Promise.all([api('/api/stats?range=day'), api('/api/orders')]);
  const t = st.totals;
  shell('记账中枢', `
    <div class="card p-4 grid grid-cols-3 gap-2 text-center">
      <div><div class="text-xs text-[#46464a]">今日发货</div><div class="mono text-xl font-bold">${t.qty}</div></div>
      <div><div class="text-xs text-[#46464a]">销售额</div><div class="mono text-xl font-bold">${money(t.sales)}</div></div>
      <div><div class="text-xs text-[#46464a]">毛利</div><div class="mono text-xl font-bold">${money(t.profit)}</div></div>
    </div>
    <div class="grid grid-cols-1 gap-3">
      <button class="btn btn-primary h-16 text-lg" data-entry="voice">${icon('mic')}语音入账</button>
      <button class="btn btn-secondary h-14" data-entry="manual">${icon('edit_square')}速记入账</button>
      <button class="btn btn-secondary h-14" data-entry="ocr">${icon('photo_camera')}拍照入账</button>
    </div>
    <section class="space-y-2"><h2 class="font-bold">最近入账</h2>${ordersData.orders.map(orderCard).join('') || '<div class="text-sm text-[#46464a]">暂无记录</div>'}</section>
  `);
}
function orderCard(o) {
  return `<article class="card p-3 source-${o.source}">
    <div class="flex justify-between gap-2"><div class="font-bold">#${o.id} ${o.source}</div><button class="material-symbols-outlined" data-delete-order="${o.id}">delete</button></div>
    <div class="text-xs text-[#46464a]">${o.created_at}</div>
    <div class="mt-2 grid grid-cols-3 text-sm"><span>数量 <b class="mono">${o.total_qty}</b></span><span>销售 <b class="mono">${money(o.total_amount)}</b></span><span>毛利 <b class="mono">${money(o.gross_profit)}</b></span></div>
    <div class="mt-2 space-y-1">${o.items.slice(0, 3).map(i => `<div class="text-xs text-[#46464a]">${i.category_name} ${i.size} x ${i.qty}${i.unit}</div>`).join('')}</div>
  </article>`;
}
async function renderLedger() {
  const date = document.querySelector('#ledgerDate')?.value || today();
  const data = await api(`/api/orders?date=${date}`);
  const qty = data.orders.reduce((s, o) => s + o.total_qty, 0);
  const amt = data.orders.reduce((s, o) => s + o.total_amount, 0);
  shell('账本', `<input id="ledgerDate" type="date" class="input" value="${date}"><div class="card p-3 flex justify-between"><span>每日小计</span><b class="mono">${qty}件 / ${money(amt)}</b></div><div class="space-y-2">${data.orders.map(orderCard).join('') || '<div class="text-sm text-[#46464a]">该日无入账</div>'}</div>`);
  document.querySelector('#ledgerDate').addEventListener('change', renderLedger);
}
async function renderStats() {
  shell('统计', `<div class="grid grid-cols-3 gap-2"><button class="btn btn-primary" data-range="day">日</button><button class="btn btn-secondary" data-range="week">周</button><button class="btn btn-secondary" data-range="month">月</button></div><div id="statsSummary"></div><div class="card p-3"><canvas id="lineChart"></canvas></div><div class="card p-3"><canvas id="barChart"></canvas></div><div class="card p-3"><canvas id="pieChart"></canvas></div>`);
  await loadStats('day');
}
async function loadStats(range) {
  charts.forEach(c => c.destroy()); charts = [];
  const data = await api(`/api/stats?range=${range}`);
  document.querySelector('#statsSummary').innerHTML = `<div class="card p-4 grid grid-cols-3 text-center"><div><div class="text-xs">发货</div><b class="mono">${data.totals.qty}</b></div><div><div class="text-xs">销售</div><b class="mono">${money(data.totals.sales)}</b></div><div><div class="text-xs">毛利</div><b class="mono">${money(data.totals.profit)}</b></div></div>`;
  const labels = data.daily.map(d => d.day);
  charts.push(new Chart(document.querySelector('#lineChart'), {type:'line', data:{labels, datasets:[{label:'发货量', data:data.daily.map(d=>d.qty), borderColor:'#000'}]}}));
  charts.push(new Chart(document.querySelector('#barChart'), {type:'bar', data:{labels, datasets:[{label:'销售额', data:data.daily.map(d=>d.sales), backgroundColor:'#505f76'}]}}));
  charts.push(new Chart(document.querySelector('#pieChart'), {type:'pie', data:{labels:Object.keys(data.sku_distribution), datasets:[{data:Object.values(data.sku_distribution), backgroundColor:['#000','#505f76','#176b3a','#8a5a00','#ba1a1a','#77777b']}]}}));
}
async function renderReconcile() {
  const hist = await api('/api/reconciliations');
  shell('对账', `<div class="card p-3 space-y-2"><input id="ourDate" type="date" class="input" value="${today()}"><textarea id="theirText" class="input min-h-40" placeholder="粘贴对方清单"></textarea><button id="runRec" class="btn btn-primary w-full">${icon('rule')}执行对账</button></div><div id="recResult" class="space-y-2"></div><section class="space-y-2"><h2 class="font-bold">历史对账</h2>${hist.items.map(h => `<div class="card p-3 text-sm"><b>${h.name}</b><div class="text-xs text-[#46464a]">${h.date} ${h.status}</div></div>`).join('') || '<div class="text-sm text-[#46464a]">暂无历史</div>'}</section>`);
}
async function renderSettings() {
  const prices = await api('/api/price-list');
  shell('设置', `<button id="exportBtn" class="btn btn-primary w-full">${icon('download')}导出全部 CSV</button><div class="space-y-2">${prices.items.map(p => `<div class="card p-3 grid grid-cols-[1fr_72px_72px] gap-2 items-center text-sm"><b>${p.school_level}${p.fabric_type}${p.item_type}</b><input class="input mono py-1" data-sell="${p.id}" value="${p.sell_price}"><input class="input mono py-1" data-cost="${p.id}" value="${p.cost_price}"></div>`).join('')}</div>`);
}
function openEntry(source) {
  currentSource = source; draftItems = []; entryText.value = ''; parseErrors.textContent = ''; renderDraft();
  document.querySelector('#dialogTitle').textContent = source === 'voice' ? '语音入账' : source === 'ocr' ? '拍照入账' : '速记入账';
  dialog.showModal();
  if (source === 'ocr') entryFile.click();
  if (source === 'voice') startSpeech();
}
function startSpeech() {
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Rec) { parseErrors.textContent = '当前浏览器不支持 Web Speech API'; return; }
  const rec = new Rec(); rec.lang = 'zh-CN'; rec.interimResults = false;
  rec.onresult = e => { entryText.value = e.results[0][0].transcript; parseDraft(); };
  rec.start();
}
async function parseDraft() {
  const data = await api('/api/parse', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({text: entryText.value})});
  draftItems = data.items || []; parseErrors.textContent = (data.errors || []).join(' / '); renderDraft();
}
function renderDraft() { draftItemsEl.innerHTML = draftItems.map((i, idx) => rowItem(i, true, idx)).join('') || '<div class="text-sm text-[#46464a]">解析后在这里确认、删除，再入账</div>'; }
async function confirmOrder() {
  if (!draftItems.length) return;
  await api('/api/orders', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({source: currentSource, raw_text: entryText.value, items: draftItems})});
  dialog.close(); render();
}
async function handleUpload(file) {
  const fd = new FormData(); fd.append('file', file);
  const data = await api('/api/ocr', {method:'POST', body: fd});
  entryText.value = data.text || ''; draftItems = data.items || []; parseErrors.textContent = (data.errors || []).join(' / '); renderDraft();
}
async function render() {
  if (activeTab === 'home') return renderHome();
  if (activeTab === 'ledger') return renderLedger();
  if (activeTab === 'stats') return renderStats();
  if (activeTab === 'reconcile') return renderReconcile();
  return renderSettings();
}

document.addEventListener('click', async e => {
  const tab = e.target.closest('.tab-btn');
  if (tab) { activeTab = tab.dataset.tab; tabs.forEach(t => t.classList.toggle('active', t === tab)); render(); }
  const entry = e.target.closest('[data-entry]'); if (entry) openEntry(entry.dataset.entry);
  const delDraft = e.target.closest('[data-del-draft]'); if (delDraft) { draftItems.splice(Number(delDraft.dataset.delDraft), 1); renderDraft(); }
  const delOrder = e.target.closest('[data-delete-order]'); if (delOrder) { await api(`/api/orders/${delOrder.dataset.deleteOrder}`, {method:'DELETE'}); render(); }
  if (e.target.closest('[data-range]')) loadStats(e.target.closest('[data-range]').dataset.range);
  if (e.target.id === 'runRec') {
    const result = await api('/api/reconcile', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({our_date: document.querySelector('#ourDate').value, their_text: document.querySelector('#theirText').value, save:true, name:'手工对账'})});
    document.querySelector('#recResult').innerHTML = `<div class="card p-3 mono">一致 ${result.summary.matched} / 异常 ${result.summary.mismatched} / 差额 ${money(result.summary.diff_amount)}</div>${result.rows.map(r => `<div class="card p-3 text-sm"><b>${r.mark} ${r.category_name} ${r.size}</b><div class="mono">我方 ${r.our_qty} / 对方 ${r.their_qty} / 差 ${r.diff_qty} / ${money(r.diff_amount)}</div></div>`).join('')}`;
  }
  if (e.target.id === 'exportBtn') {
    const text = await api('/api/export', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const url = URL.createObjectURL(new Blob(['\ufeff' + text], {type:'text/csv;charset=utf-8'}));
    const a = Object.assign(document.createElement('a'), {href:url, download:'ledger.csv'}); a.click(); URL.revokeObjectURL(url);
  }
});
document.querySelector('#parseBtn').addEventListener('click', parseDraft);
document.querySelector('#confirmBtn').addEventListener('click', confirmOrder);
entryFile.addEventListener('change', e => e.target.files[0] && handleUpload(e.target.files[0]));
document.addEventListener('change', async e => {
  const sell = e.target.dataset.sell, cost = e.target.dataset.cost;
  if (sell || cost) {
    const id = sell || cost;
    const sellVal = document.querySelector(`[data-sell="${id}"]`).value;
    const costVal = document.querySelector(`[data-cost="${id}"]`).value;
    await api(`/api/price-list/${id}`, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({sell_price:sellVal, cost_price:costVal})});
  }
});
render();
