const API = '';
let currentPage = 1;
let cachedData = null;
const charts = {};

const labelMap = { positive: '正面', negative: '负面', neutral: '中性' };
const docTypeMap = { news: '新闻', announcement: '公告', comment: '评论', sample: '样本' };
const colors = { positive: '#18805d', negative: '#b33a3a', neutral: '#1d5f9f' };

setInterval(() => {
  document.getElementById('clock').textContent = new Date().toLocaleTimeString('zh-CN');
}, 1000);

function showPage(name, el, updateHash = true) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  el.classList.add('active');
  const titles = { dashboard: '舆情总览', sentiment: '情感分析', topics: '主题模型', news: '舆情明细', control: '采集控制' };
  document.getElementById('page-title').textContent = titles[name] || name;
  if (updateHash && location.hash.slice(1) !== name) location.hash = name;
  setTimeout(resizeCharts, 50);
  if (name === 'news') { loadSources(); loadNews(currentPage); }
  if (name === 'control') { renderSourcePie(); loadCrawlLogs(); }
  if (name === 'sentiment') { loadModelEval(); }
}

function activatePageFromHash() {
  const page = location.hash.slice(1) || 'dashboard';
  const nav = document.querySelector(`.nav-item[data-page="${page}"]`);
  showPage(nav ? page : 'dashboard', nav || document.querySelector('.nav-item[data-page="dashboard"]'), false);
}

function chart(id) {
  if (!charts[id]) charts[id] = echarts.init(document.getElementById(id));
  return charts[id];
}

function resizeCharts() {
  Object.values(charts).forEach(c => c.resize());
}
window.addEventListener('resize', resizeCharts);

function sentimentTag(s) {
  return `<span class="tag tag-${s || 'neutral'}">${labelMap[s] || '中性'}</span>`;
}

function docPill(t) {
  return `<span class="doc-pill">${docTypeMap[t] || t || '新闻'}</span>`;
}

function themeOption() {
  return {
    backgroundColor: 'transparent',
    textStyle: { color: '#4b5563', fontFamily: 'Microsoft YaHei' },
    tooltip: { backgroundColor: '#101820', borderColor: '#101820', textStyle: { color: '#fff' } },
    legend: { textStyle: { color: '#6b7785' } }
  };
}

async function loadStats() {
  const r = await fetch(API + '/api/stats').then(r => r.json());
  document.getElementById('s-total').textContent = r.total_news.toLocaleString();
  document.getElementById('s-analyzed').textContent = r.analyzed.toLocaleString();
  document.getElementById('s-announcements').textContent = r.announcements.toLocaleString();
  document.getElementById('s-comments').textContent = r.comments.toLocaleString();
  document.getElementById('last-crawl').textContent = `最近采集：${r.last_crawl || '--'}`;
}

async function loadCharts() {
  cachedData = await fetch(API + '/api/sentiment').then(r => r.json());
  renderTrendChart(cachedData.trend_data || {});
  renderPieChart(cachedData.sentiment_dist || {});
  renderSourceBar(cachedData.source_sentiment || {});
  renderLatestNews(cachedData.latest_news || []);
  renderHistChart(cachedData.latest_news || []);
  renderDocTypeChart(cachedData.doc_type_stats || []);
  renderBarSource(cachedData.source_sentiment || {});
  renderSentimentIndex(cachedData.trend_data || {});
  renderTopicBar(cachedData.topic_dist || []);
  renderTopicPie(cachedData.topic_dist || []);
  renderTopicSentiment(cachedData.topic_sentiment || {});
}

async function loadWordCloud() {
  const words = await fetch(API + '/api/wordcloud').then(r => r.json());
  renderWordCloud(words || []);
}

function renderTrendChart(trendData) {
  const dates = Object.keys(trendData).sort();
  chart('chart-trend').setOption({
    ...themeOption(),
    grid: { left: 48, right: 18, top: 32, bottom: 36 },
    tooltip: { ...themeOption().tooltip, trigger: 'axis' },
    legend: { top: 0, data: ['正面', '负面', '中性'] },
    xAxis: { type: 'category', data: dates, axisLabel: { color: '#6b7785' }, axisLine: { lineStyle: { color: '#dde3ea' } } },
    yAxis: { type: 'value', axisLabel: { color: '#6b7785' }, splitLine: { lineStyle: { color: '#edf1f5' } } },
    series: [
      { name: '正面', type: 'bar', stack: 'total', data: dates.map(d => trendData[d].positive || 0), itemStyle: { color: colors.positive } },
      { name: '负面', type: 'bar', stack: 'total', data: dates.map(d => trendData[d].negative || 0), itemStyle: { color: colors.negative } },
      { name: '中性', type: 'bar', stack: 'total', data: dates.map(d => trendData[d].neutral || 0), itemStyle: { color: colors.neutral } }
    ]
  });
}

function renderPieChart(dist) {
  chart('chart-pie').setOption({
    ...themeOption(),
    tooltip: { ...themeOption().tooltip, trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius: ['48%', '72%'],
      center: ['50%', '45%'],
      data: Object.entries(dist).map(([k, v]) => ({ name: labelMap[k] || k, value: v, itemStyle: { color: colors[k] } })),
      label: { color: '#4b5563' }
    }]
  });
}

function renderSourceBar(sourceSentiment) {
  const sources = Object.keys(sourceSentiment);
  chart('chart-source').setOption({
    ...themeOption(),
    grid: { left: 92, right: 18, top: 32, bottom: 28 },
    tooltip: { ...themeOption().tooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 0 },
    xAxis: { type: 'value', axisLabel: { color: '#6b7785' }, splitLine: { lineStyle: { color: '#edf1f5' } } },
    yAxis: { type: 'category', data: sources, axisLabel: { color: '#6b7785' }, axisLine: { lineStyle: { color: '#dde3ea' } } },
    series: [
      { name: '正面', type: 'bar', stack: 'total', data: sources.map(s => sourceSentiment[s].positive || 0), itemStyle: { color: colors.positive } },
      { name: '负面', type: 'bar', stack: 'total', data: sources.map(s => sourceSentiment[s].negative || 0), itemStyle: { color: colors.negative } },
      { name: '中性', type: 'bar', stack: 'total', data: sources.map(s => sourceSentiment[s].neutral || 0), itemStyle: { color: colors.neutral } }
    ]
  });
}

function renderWordCloud(words) {
  chart('chart-wordcloud').setOption({
    backgroundColor: 'transparent',
    series: [{
      type: 'wordCloud',
      shape: 'circle',
      width: '96%',
      height: '96%',
      sizeRange: [12, 42],
      rotationRange: [-20, 20],
      gridSize: 9,
      textStyle: {
        fontFamily: 'Microsoft YaHei',
        fontWeight: 700,
        color: () => ['#1d5f9f', '#18805d', '#b7832f', '#1282a2', '#b33a3a'][Math.floor(Math.random() * 5)]
      },
      data: words.slice(0, 70)
    }]
  });
}

function renderLatestNews(newsList) {
  document.getElementById('latest-news-list').innerHTML = newsList.slice(0, 20).map(n => `
    <div class="news-mini-item">
      <span class="muted">${n.source || ''}</span>
      ${docPill(n.doc_type)}
      <span class="news-mini-title" title="${escapeHtml(n.title)}">${escapeHtml(n.title)}</span>
      ${sentimentTag(n.sentiment)}
      <span class="muted">${n.publish_time || ''}</span>
    </div>
  `).join('');
}

function renderHistChart(news) {
  const scores = news.map(n => n.score).filter(s => typeof s === 'number');
  const bins = Array(10).fill(0);
  scores.forEach(s => { bins[Math.min(9, Math.floor(s * 10))]++; });
  chart('chart-hist').setOption({
    ...themeOption(),
    grid: { left: 44, right: 16, top: 24, bottom: 40 },
    tooltip: { ...themeOption().tooltip, trigger: 'axis' },
    xAxis: { type: 'category', data: ['0-.1','.1-.2','.2-.3','.3-.4','.4-.5','.5-.6','.6-.7','.7-.8','.8-.9','.9-1'], axisLabel: { color: '#6b7785' } },
    yAxis: { type: 'value', axisLabel: { color: '#6b7785' }, splitLine: { lineStyle: { color: '#edf1f5' } } },
    series: [{ type: 'bar', data: bins, barMaxWidth: 34, itemStyle: { color: '#1d5f9f' } }]
  });
}

function renderDocTypeChart(rows) {
  chart('chart-doc-type').setOption({
    ...themeOption(),
    grid: { left: 50, right: 16, top: 26, bottom: 36 },
    tooltip: { ...themeOption().tooltip, trigger: 'axis' },
    xAxis: { type: 'category', data: rows.map(r => docTypeMap[r.doc_type] || r.doc_type), axisLabel: { color: '#6b7785' } },
    yAxis: { type: 'value', min: 0, max: 1, axisLabel: { color: '#6b7785' }, splitLine: { lineStyle: { color: '#edf1f5' } } },
    series: [{ type: 'bar', data: rows.map(r => r.avg_score), itemStyle: { color: '#1282a2' }, barMaxWidth: 42 }]
  });
}

function renderBarSource(sourceSentiment) {
  const sources = Object.keys(sourceSentiment);
  const ratio = (s, label) => {
    const row = sourceSentiment[s];
    const total = (row.positive || 0) + (row.negative || 0) + (row.neutral || 0);
    return total ? +((row[label] || 0) / total * 100).toFixed(1) : 0;
  };
  chart('chart-bar-source').setOption({
    ...themeOption(),
    grid: { left: 92, right: 18, top: 32, bottom: 28 },
    tooltip: { ...themeOption().tooltip, trigger: 'axis' },
    legend: { top: 0 },
    xAxis: { type: 'value', max: 100, axisLabel: { color: '#6b7785', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#edf1f5' } } },
    yAxis: { type: 'category', data: sources, axisLabel: { color: '#6b7785' } },
    series: [
      { name: '正面占比', type: 'bar', data: sources.map(s => ratio(s, 'positive')), itemStyle: { color: colors.positive } },
      { name: '负面占比', type: 'bar', data: sources.map(s => ratio(s, 'negative')), itemStyle: { color: colors.negative } }
    ]
  });
}

function renderSentimentIndex(trendData) {
  const dates = Object.keys(trendData).sort();
  const idx = dates.map(d => {
    const row = trendData[d];
    const total = (row.positive || 0) + (row.negative || 0) + (row.neutral || 0);
    return total ? +(((row.positive || 0) - (row.negative || 0)) / total * 100).toFixed(2) : 0;
  });
  chart('chart-sentiment-index').setOption({
    ...themeOption(),
    grid: { left: 52, right: 18, top: 24, bottom: 36 },
    tooltip: { ...themeOption().tooltip, trigger: 'axis', formatter: p => `情感指数：${p[0].value}%` },
    xAxis: { type: 'category', data: dates, axisLabel: { color: '#6b7785' } },
    yAxis: { type: 'value', axisLabel: { color: '#6b7785', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#edf1f5' } } },
    series: [{ type: 'line', data: idx, smooth: true, symbolSize: 6, lineStyle: { width: 3, color: '#b7832f' }, itemStyle: { color: '#b7832f' }, markLine: { silent: true, data: [{ yAxis: 0 }] } }]
  });
}

function renderTopicBar(topicDist) {
  chart('chart-topic-bar').setOption({
    ...themeOption(),
    grid: { left: 148, right: 20, top: 20, bottom: 28 },
    tooltip: { ...themeOption().tooltip, trigger: 'axis' },
    xAxis: { type: 'value', axisLabel: { color: '#6b7785' }, splitLine: { lineStyle: { color: '#edf1f5' } } },
    yAxis: { type: 'category', data: topicDist.map(t => t[0]), axisLabel: { color: '#6b7785', width: 138, overflow: 'truncate' } },
    series: [{ type: 'bar', data: topicDist.map(t => t[1]), itemStyle: { color: '#1d5f9f' }, barMaxWidth: 28 }]
  });
}

function renderTopicPie(topicDist) {
  const palette = ['#1d5f9f', '#18805d', '#b7832f', '#1282a2', '#b33a3a', '#5f6f86', '#7a5c28', '#2f6f73'];
  chart('chart-topic-pie').setOption({
    ...themeOption(),
    tooltip: { ...themeOption().tooltip, trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [{
      type: 'pie',
      radius: ['42%', '68%'],
      center: ['50%', '44%'],
      label: { show: false },
      data: topicDist.map(([name, value], i) => ({ name, value, itemStyle: { color: palette[i % palette.length] } }))
    }]
  });
}

function renderTopicSentiment(topicSentiment) {
  const topics = Object.keys(topicSentiment).slice(0, 10);
  chart('chart-topic-sentiment').setOption({
    ...themeOption(),
    grid: { left: 150, right: 20, top: 34, bottom: 28 },
    tooltip: { ...themeOption().tooltip, trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 0 },
    xAxis: { type: 'value', axisLabel: { color: '#6b7785' }, splitLine: { lineStyle: { color: '#edf1f5' } } },
    yAxis: { type: 'category', data: topics, axisLabel: { color: '#6b7785', width: 140, overflow: 'truncate' } },
    series: [
      { name: '正面', type: 'bar', stack: 'total', data: topics.map(t => topicSentiment[t].positive || 0), itemStyle: { color: colors.positive } },
      { name: '负面', type: 'bar', stack: 'total', data: topics.map(t => topicSentiment[t].negative || 0), itemStyle: { color: colors.negative } },
      { name: '中性', type: 'bar', stack: 'total', data: topics.map(t => topicSentiment[t].neutral || 0), itemStyle: { color: colors.neutral } }
    ]
  });
}

async function renderSourcePie() {
  const data = cachedData || await fetch(API + '/api/sentiment').then(r => r.json());
  const totals = {};
  (data.latest_news || []).forEach(n => { totals[n.source] = (totals[n.source] || 0) + 1; });
  chart('chart-source-pie').setOption({
    ...themeOption(),
    tooltip: { ...themeOption().tooltip, trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0 },
    series: [{ type: 'pie', radius: ['42%', '68%'], center: ['50%', '44%'], data: Object.entries(totals).map(([name, value]) => ({ name, value })) }]
  });
}

async function loadModelEval() {
  const data = await fetch(API + '/api/model-eval').then(r => r.json());
  document.getElementById('model-eval').innerHTML = [
    ['样本文本', data.total_docs || 0],
    ['平均置信度', data.avg_confidence || 0],
    ['平均主题概率', data.avg_topic_probability || 0],
    ['情感熵', data.sentiment_entropy || 0]
  ].map(([k, v]) => `<div class="eval-item"><span>${k}</span><strong>${v}</strong></div>`).join('');
}

async function loadSources() {
  const sources = await fetch(API + '/api/sources').then(r => r.json());
  document.getElementById('source-select').innerHTML = '<option value="">全部来源</option>' + sources.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join('');
}

async function loadNews(page) {
  currentPage = page;
  const params = new URLSearchParams({
    page,
    size: 20,
    keyword: document.getElementById('kw-input').value,
    source: document.getElementById('source-select').value,
    sentiment: document.getElementById('sentiment-select').value,
    doc_type: document.getElementById('doc-type-select').value
  });
  const data = await fetch(`${API}/api/news?${params}`).then(r => r.json());
  document.getElementById('news-tbody').innerHTML = data.list.map(n => `
    <tr>
      <td class="td-title"><a href="${escapeHtml(n.url)}" target="_blank" title="${escapeHtml(n.title)}">${escapeHtml(n.title)}</a></td>
      <td>${escapeHtml(n.source)}</td>
      <td>${docPill(n.doc_type)}</td>
      <td>${sentimentTag(n.sentiment)}</td>
      <td style="color:${n.score > .6 ? colors.positive : n.score < .4 ? colors.negative : colors.neutral};font-weight:700">${n.score.toFixed(3)}</td>
      <td class="muted">${escapeHtml(n.topic)}</td>
      <td class="muted">${n.publish_time}</td>
    </tr>
  `).join('');
  const totalPages = Math.ceil(data.total / data.size);
  const pages = [];
  if (page > 1) pages.push(`<button class="page-btn" onclick="loadNews(${page - 1})">上页</button>`);
  for (let i = Math.max(1, page - 2); i <= Math.min(totalPages, page + 2); i++) {
    pages.push(`<button class="page-btn${i === page ? ' active' : ''}" onclick="loadNews(${i})">${i}</button>`);
  }
  if (page < totalPages) pages.push(`<button class="page-btn" onclick="loadNews(${page + 1})">下页</button>`);
  document.getElementById('pagination').innerHTML = `<span>共 ${data.total} 条</span>` + pages.join('');
}

async function doCrawl() {
  const btn = document.getElementById('crawl-btn');
  const res = document.getElementById('crawl-result');
  btn.disabled = true; btn.textContent = '采集中...'; res.textContent = '正在连接数据源并写入 MySQL。';
  try {
    const pages = parseInt(document.getElementById('crawl-pages').value, 10) || 2;
    const data = await fetch(API + '/api/crawl', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ pages }) }).then(r => r.json());
    res.textContent = data.success ? `采集完成，新增 ${data.count} 条记录。` : `采集失败：${data.error}`;
    if (data.success) await refreshAll();
  } catch (e) {
    res.textContent = `请求失败：${e.message}`;
  }
  btn.disabled = false; btn.textContent = '开始采集';
}

async function doAnalyze() {
  const btn = document.getElementById('analyze-btn');
  const res = document.getElementById('analyze-result');
  btn.disabled = true; btn.textContent = '分析中...'; res.textContent = '正在执行情感分析与主题建模。';
  try {
    const data = await fetch(API + '/api/analyze', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' }).then(r => r.json());
    res.textContent = data.success ? `分析完成，新增情感分析 ${data.sentiment_analyzed} 条，LDA 主题已更新。` : `分析失败：${data.error}`;
    if (data.success) await refreshAll();
  } catch (e) {
    res.textContent = `请求失败：${e.message}`;
  }
  btn.disabled = false; btn.textContent = '开始分析';
}

async function loadCrawlLogs() {
  const logs = await fetch(API + '/api/crawl-logs').then(r => r.json());
  document.getElementById('crawl-logs').innerHTML = logs.map(l => `
    <div class="log-item"><strong>${escapeHtml(l.source)}</strong>${escapeHtml(l.status)}，新增 ${l.records} 条<br>${escapeHtml(l.finished_at)} · ${escapeHtml(l.message || '')}</div>
  `).join('') || '<div class="log-item">暂无采集日志</div>';
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, s => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[s]));
}

async function refreshAll() {
  await loadStats();
  await loadCharts();
  await loadWordCloud();
  await loadModelEval();
  await loadCrawlLogs();
  setTimeout(resizeCharts, 60);
}

window.addEventListener('hashchange', activatePageFromHash);

(async () => {
  await refreshAll();
  activatePageFromHash();
})();
