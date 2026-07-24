const API_BASE = 'http://127.0.0.1:8765';
const HISTORY_KEY = 'phishRadarWebHistory';
const AUTH_API_HOST = location.hostname === 'localhost' ? 'localhost' : '127.0.0.1';
const AUTH_API_BASE = globalThis.PhishRadarRuntime?.apiBase || `http://${AUTH_API_HOST}:8765`;
const FEEDBACK_KEY = 'phishRadarWebFeedbackCount';
const PRIVACY_KEY = 'phishRadarPrivacyMode';
const PRIVATE_FEEDBACK_KEY = 'phishRadarPrivateFeedback';

const state = {
  current: null,
  user: null,
  history: [],
  feedbackCount: Number(localStorage.getItem(FEEDBACK_KEY) || 0),
  privacyMode: localStorage.getItem(PRIVACY_KEY) === '1',
  qrStream: null,
  qrTimer: null
};

const $ = selector => document.querySelector(selector);
const $$ = selector => Array.from(document.querySelectorAll(selector));
const els = {
  backendStatus: $('#backendStatus'), privacyMode: $('#privacyMode'), scanForm: $('#scanForm'), urlInput: $('#urlInput'), scanButton: $('#scanButton'), formMessage: $('#formMessage'),
  emptyResult: $('#emptyResult'), resultContent: $('#resultContent'), riskLabel: $('#riskLabel'), resultTitle: $('#resultTitle'), scoreRing: $('#scoreRing'),
  finalScore: $('#finalScore'), ruleScore: $('#ruleScore'), mlScore: $('#mlScore'), combinedScore: $('#combinedScore'), reasonList: $('#reasonList'), threatTypes: $('#threatTypes'),
  insightState: $('#insightState'), insightList: $('#insightList'), llmState: $('#llmState'), llmRiskType: $('#llmRiskType'), llmExplanation: $('#llmExplanation'), llmAdvice: $('#llmAdvice'), feedbackStatus: $('#feedbackStatus'),
  previewBadge: $('#previewBadge'), previewHost: $('#previewHost'), previewProtocol: $('#previewProtocol'), previewUrl: $('#previewUrl'), openTarget: $('#openTarget'), copyReport: $('#copyReport'),
  metricTotal: $('#metricTotal'), metricHigh: $('#metricHigh'), metricAverage: $('#metricAverage'), metricFeedback: $('#metricFeedback'), healthBackend: $('#healthBackend'), healthModel: $('#healthModel'), healthLlm: $('#healthLlm'), healthFeedback: $('#healthFeedback'), historyRows: $('#historyRows'),
  exportCsv: $('#exportCsv'), exportJson: $('#exportJson'), copyDashboard: $('#copyDashboard'), reportStatus: $('#reportStatus'), reportState: $('#reportState'),
  qrVideo: $('#qrVideo'), qrCanvas: $('#qrCanvas'), qrPlaceholder: $('#qrPlaceholder'), qrStatus: $('#qrStatus'), startCamera: $('#startCamera'), stopCamera: $('#stopCamera'), qrFile: $('#qrFile'),
  accountSummary: $('#accountSummary'), accountAvatar: $('#accountAvatar'), accountName: $('#accountName'), accountRole: $('#accountRole'), logoutButton: $('#logoutButton')
};

function loadJson(key, fallback) {
  try { const value = JSON.parse(localStorage.getItem(key) || ''); return Array.isArray(value) ? value : fallback; }
  catch (_) { return fallback; }
}
function userHistoryKey() { return `${HISTORY_KEY}:${state.user?.user_id || 'anonymous'}`; }
function safeHistoryUrl(url, privacy = false) {
  if (privacy) return redactUrl(url);
  try {
    const parsed = new URL(url);
    parsed.username = '';
    parsed.password = '';
    parsed.search = '';
    parsed.hash = '';
    return parsed.href;
  } catch (_) {
    return '[invalid-url]';
  }
}
function safeHistoryItem(item) {
  const url = safeHistoryUrl(item?.displayUrl || item?.url, !!item?.privacy);
  return { ...item, url, displayUrl: url };
}
function saveHistory() { localStorage.setItem(userHistoryKey(), JSON.stringify(state.history.slice(0, 50).map(safeHistoryItem))); }
function normalizeInputUrl(value) { const raw = String(value || '').trim(); if (!raw) return ''; return /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(raw) ? raw : `https://${raw}`; }
function flattenReason(reason) { if (!reason) return ''; if (typeof reason === 'string') return reason; return reason.detail ? `${reason.label}: ${reason.detail}` : reason.label; }
function riskLevel(score, decisionThreshold = 61) { const highCut = Number.isFinite(decisionThreshold) ? Math.max(5, Math.min(95, decisionThreshold)) : 61; const criticalCut = Math.min(100, highCut + 20); const mediumCut = Math.max(5, Math.round(highCut * 0.6)); if (score >= criticalCut) return { key: 'critical', label: 'อันตรายมาก', tone: 'risk-text-critical' }; if (score >= highCut) return { key: 'high', label: 'เสี่ยงสูง', tone: 'risk-text-high' }; if (score >= mediumCut) return { key: 'medium', label: 'น่าสงสัย', tone: 'risk-text-medium' }; return { key: 'low', label: 'ค่อนข้างปลอดภัย', tone: 'risk-text-low' }; }
function setMessage(text, isError = false) { els.formMessage.textContent = text || ''; els.formMessage.classList.toggle('error', isError); }
function setBackendStatus(online, text) { els.backendStatus.textContent = text; els.backendStatus.classList.toggle('online', online === true); els.backendStatus.classList.toggle('offline', online === false); els.backendStatus.classList.toggle('checking', online === null); }
function setAnimatedNumber(element, value, options) {
  if (Number.isFinite(Number(value)) && window.PhishRadarMotion?.animateNumber) window.PhishRadarMotion.animateNumber(element, Number(value), options);
  else element.textContent = value;
}
function sameOrSubdomain(host, domain) { host = String(host || '').replace(/^www\./, '').toLowerCase(); domain = String(domain || '').replace(/^www\./, '').toLowerCase(); return host === domain || host.endsWith(`.${domain}`); }
function redactUrl(url) { try { const parsed = new URL(url); return `${parsed.protocol}//${parsed.hostname}/[path-hidden]`; } catch (_) { return '[url-hidden]'; } }
function setPrivacyMode(enabled) { state.privacyMode = !!enabled; localStorage.setItem(PRIVACY_KEY, enabled ? '1' : '0'); document.body.classList.toggle('privacy-active', enabled); if (els.privacyMode) els.privacyMode.checked = enabled; }
function savePrivateFeedback(label) {
  const list = loadJson(PRIVATE_FEEDBACK_KEY, []);
  list.unshift({
    url: redactUrl(state.current?.url),
    user_label: label,
    rule_score: state.current?.ruleScore ?? null,
    ml_score: Number.isFinite(state.current?.mlScore) ? state.current.mlScore : null,
    final_score: state.current?.finalScore ?? null,
    source: 'web-app-privacy-local',
    privacy_mode: true,
    saved_at: new Date().toISOString()
  });
  localStorage.setItem(PRIVATE_FEEDBACK_KEY, JSON.stringify(list.slice(0, 200)));
}

async function checkHealth() {
  if (state.privacyMode) {
    setBackendStatus(true, 'Privacy Mode เปิดอยู่');
    els.healthBackend.textContent = 'Local rule-based mode'; els.healthModel.textContent = 'ข้าม ML เพื่อไม่ส่ง URL'; els.healthLlm.textContent = 'ข้าม LLM'; els.healthFeedback.textContent = 'เก็บ feedback ใน browser เท่านั้น';
    return null;
  }
  setBackendStatus(null, 'กำลังเช็คระบบ');
  try {
    const response = await fetch(`${AUTH_API_BASE}/health`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const health = await response.json();
    setBackendStatus(true, 'Backend พร้อมใช้งาน');
    const databaseReady = health.database?.connected && health.database?.auth_schema_ready;
    els.healthBackend.textContent = health.ok ? `Online · Database ${databaseReady ? 'พร้อม' : 'ยังไม่พร้อม'}` : 'ไม่พร้อม';
    const policy = health.model_policy;
    els.healthModel.textContent = health.model_ready
      ? `พร้อมใช้ model.pkl${Number.isFinite(policy?.alpha) ? ` · alpha ${policy.alpha} · threshold ${policy.decision_threshold}` : ''}`
      : 'ยังไม่พบ model.pkl';
    const llmModel = health.llm?.provider === 'ollama' ? health.llm.ollama_model : health.llm?.openai_model;
    els.healthLlm.textContent = health.llm?.llm_ready ? `พร้อมใช้ ${llmModel || 'LLM'}` : `ยังไม่พร้อม · ${llmModel || 'ตรวจสอบ Qwen/Ollama'}`;
    els.healthFeedback.textContent = health.feedback_path || '-';
    return health;
  } catch (_) {
    setBackendStatus(false, 'Backend ยังไม่เปิด');
    els.healthBackend.textContent = 'Offline'; els.healthModel.textContent = '-'; els.healthLlm.textContent = '-'; els.healthFeedback.textContent = '-';
    return null;
  }
}
async function predictWithMl(url, ruleScore) { const response = await fetch(`${AUTH_API_BASE}/predict`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, rule_score: ruleScore }) }); if (!response.ok) throw new Error(`ML API ${response.status}`); return response.json(); }
async function explainWithLlm(payload) { const response = await fetch(`${AUTH_API_BASE}/explain`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); if (!response.ok) throw new Error(`LLM API ${response.status}`); return response.json(); }
async function sendFeedback(payload) { const response = await fetch(`${AUTH_API_BASE}/feedback`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); if (!response.ok) throw new Error(`Feedback API ${response.status}`); return response.json(); }
async function historyRequest(path = '', options = {}) {
  const response = await fetch(`${AUTH_API_BASE}/history${path}`, {
    credentials: 'include',
    ...options,
    headers: { 'X-Phish-Radar-Client': 'web-app', ...(options.headers || {}) }
  });
  if (!response.ok) throw new Error(`History API ${response.status}`);
  return response.status === 204 ? null : response.json();
}
function mapServerHistory(item) {
  return {
    historyId: item.history_id,
    url: item.url,
    displayUrl: item.url,
    ruleScore: item.rule_score,
    mlScore: item.ml_score,
    finalScore: item.final_score,
    alpha: item.alpha,
    decisionThreshold: item.decision_threshold,
    detectionLabel: item.detection_label,
    modelStatus: item.model_status,
    reasons: [],
    threatTypes: [],
    insights: [],
    privacy: false,
    source: item.source,
    deviceName: item.device_name,
    time: item.created_at
  };
}
async function loadSearchHistory() {
  const localItems = loadJson(userHistoryKey(), []).map(safeHistoryItem);
  const localPrivate = localItems.filter(item => item.privacy);
  if (state.privacyMode) {
    state.history = localPrivate;
    els.reportState.textContent = 'Privacy local history';
    els.reportStatus.textContent = 'Privacy Mode: แสดงเฉพาะประวัติที่ปิดบังและเก็บใน browser';
    saveHistory();
    renderDashboard();
    return;
  }
  try {
    const data = await historyRequest('?limit=50');
    const serverItems = (data.items || []).map(mapServerHistory);
    state.history = [...localPrivate, ...serverItems]
      .sort((left, right) => new Date(right.time) - new Date(left.time))
      .slice(0, 50);
    els.reportState.textContent = 'Account history';
    els.reportStatus.textContent = `โหลดประวัติจากบัญชี ${serverItems.length} รายการ`;
  } catch (_) {
    state.history = localItems;
    els.reportState.textContent = 'Local fallback';
    els.reportStatus.textContent = 'ยังโหลดประวัติจากฐานข้อมูลไม่ได้ จึงใช้ข้อมูลใน browser ชั่วคราว';
  }
  saveHistory();
  renderDashboard();
}
async function storeSearchHistory(result) {
  const saved = await historyRequest('', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      url: result.url,
      rule_score: result.ruleScore,
      ml_score: Number.isFinite(result.mlScore) ? result.mlScore : null,
      final_score: result.finalScore,
      alpha: result.alpha,
      decision_threshold: result.decisionThreshold,
      detection_label: result.detectionLabel,
      model_status: result.modelStatus,
      source: result.source || 'web-app'
    })
  });
  return saved;
}
async function clearSearchHistory() {
  if (state.privacyMode) {
    state.history = state.history.filter(item => !item.privacy);
    saveHistory();
    renderDashboard();
    els.reportStatus.textContent = 'Privacy Mode: ล้างเฉพาะประวัติ local แล้ว โดยไม่เรียก Backend';
    return;
  }
  const hadServerItems = state.history.some(item => !item.privacy);
  try {
    if (hadServerItems) await historyRequest('', { method: 'DELETE' });
    state.history = [];
    saveHistory();
    renderDashboard();
    els.reportStatus.textContent = 'ล้างประวัติของบัญชีนี้แล้ว';
  } catch (_) {
    els.reportStatus.textContent = 'ยังล้างประวัติจากฐานข้อมูลไม่ได้ กรุณาตรวจสอบ Backend';
  }
}

function brandVisualInsights(url, ruleResult) {
  const insights = [];
  let parsed = null;
  try { parsed = new URL(url); } catch (_) { return ['อ่าน URL ไม่ได้ จึงตรวจ brand/visual clue ไม่ครบ']; }
  const hostname = parsed.hostname.toLowerCase();
  const decoded = decodeURIComponent(url).toLowerCase();
  const profiles = PhishRadarAnalyzer.BRAND_PROFILES || [];
  const official = profiles.filter(profile => (profile.officialDomains || []).some(domain => sameOrSubdomain(hostname, domain)));
  if (official.length) insights.push(`โดเมนตรงกับรายการทางการของ ${official.map(p => p.brand).slice(0, 2).join(', ')} จึงลดความเสี่ยงด้านการเลียนแบบแบรนด์`);

  for (const profile of profiles) {
    const tokens = [profile.brand, ...(profile.aliases || [])].filter(Boolean).map(v => String(v).toLowerCase());
    const mentionsBrand = tokens.some(token => decoded.includes(token));
    const isOfficial = (profile.officialDomains || []).some(domain => sameOrSubdomain(hostname, domain));
    if (mentionsBrand && !isOfficial) {
      insights.push(`พบคำ/แบรนด์ "${profile.brand}" แต่โดเมนไม่ใช่โดเมนทางการ อาจเป็นหน้าเลียนแบบแบรนด์`);
      break;
    }
  }

  if (/xn--/i.test(hostname)) insights.push('โดเมนใช้ Punycode/IDN ซึ่งอาจใช้ตัวอักษรหลอกตาให้คล้ายแบรนด์จริง');
  if (/(login|verify|secure|account|password|otp|wallet|bank|signin)/i.test(decoded) && ruleResult.score >= 31) insights.push('URL มีบริบท login/verify/account ร่วมกับคะแนนเสี่ยง จึงควรระวังหน้าเก็บรหัสผ่าน');
  if ((ruleResult.reasons || []).some(r => ['brand', 'homograph', 'credential', 'form'].includes(r.category))) insights.push('Rule-based พบสัญญาณที่เกี่ยวกับแบรนด์ ตัวอักษรหลอกตา หรือข้อมูลลับ');
  if (!insights.length) insights.push('ยังไม่พบสัญญาณเลียนแบบแบรนด์จาก URL และชื่อโดเมนในรอบนี้');
  return insights.slice(0, 5);
}

function renderPreview(url, score = null) {
  let parsed = null;
  try { parsed = new URL(url); } catch (_) {}
  els.previewHost.textContent = parsed?.hostname || '-';
  els.previewProtocol.textContent = parsed?.protocol ? parsed.protocol.replace(':', '').toUpperCase() : '-';
  els.previewUrl.textContent = url || 'ยังไม่มีลิงก์';
  els.previewBadge.textContent = score === null ? 'รอการตรวจ' : riskLevel(score).label;
}
function renderReasons(result) {
  els.reasonList.innerHTML = '';
  const reasons = (result.reasons || []).slice(0, 7);
  if (!reasons.length) reasons.push('ยังไม่พบเหตุผลเสี่ยงสำคัญจากกฎที่ตรวจในขณะนี้');
  for (const reason of reasons) { const li = document.createElement('li'); li.textContent = flattenReason(reason); els.reasonList.appendChild(li); }
  els.threatTypes.textContent = (result.threatTypes || []).slice(0, 3).join(' / ') || 'URL pattern';
}
function renderInsights(insights, score) {
  els.insightList.innerHTML = '';
  for (const insight of insights || []) { const li = document.createElement('li'); li.textContent = insight; els.insightList.appendChild(li); }
  els.insightState.textContent = score >= 61 ? 'ควรตรวจสอบ' : 'ตรวจแล้ว';
}
function renderLoading(ruleResult, url) {
  els.emptyResult.hidden = true; els.resultContent.hidden = false;
  els.riskLabel.textContent = state.privacyMode ? 'Privacy Mode: ตรวจในเครื่องเป็นหลัก' : 'กำลังรวมผล Rule-based + ML + LLM'; els.riskLabel.className = '';
  els.resultTitle.textContent = ruleResult.summary; els.scoreRing.style.setProperty('--score', ruleResult.score); els.scoreRing.className = `score-ring risk-${riskLevel(ruleResult.score).key}`;
  setAnimatedNumber(els.finalScore, ruleResult.score); setAnimatedNumber(els.ruleScore, ruleResult.score); els.mlScore.textContent = state.privacyMode ? 'local' : '...'; setAnimatedNumber(els.combinedScore, ruleResult.score);
  els.llmState.textContent = state.privacyMode ? 'ข้าม LLM' : 'กำลังวิเคราะห์'; els.llmRiskType.textContent = '-'; els.llmExplanation.textContent = state.privacyMode ? 'เปิด Privacy Mode จึงไม่ส่ง URL เต็มไปให้ LLM วิเคราะห์' : 'กำลังขอคำอธิบายจาก backend'; els.llmAdvice.textContent = '-'; els.feedbackStatus.textContent = '';
  els.openTarget.href = url; renderReasons(ruleResult); renderInsights(brandVisualInsights(url, ruleResult), ruleResult.score); renderPreview(url, ruleResult.score);
}
function renderFinal(result) {
  const level = riskLevel(result.finalScore, result.decisionThreshold);
  const policyText = Number.isFinite(result.decisionThreshold) ? ` · เกณฑ์ phishing ${result.decisionThreshold}` : '';
  els.riskLabel.textContent = `ระดับความเสี่ยง: ${level.label}${policyText}`; els.riskLabel.className = level.tone;
  els.resultTitle.textContent = result.url; els.scoreRing.style.setProperty('--score', result.finalScore); els.scoreRing.className = `score-ring risk-${level.key}`;
  setAnimatedNumber(els.finalScore, result.finalScore); setAnimatedNumber(els.ruleScore, result.ruleScore); Number.isFinite(result.mlScore) ? setAnimatedNumber(els.mlScore, result.mlScore) : (els.mlScore.textContent = result.privacy ? 'local' : 'offline'); setAnimatedNumber(els.combinedScore, result.finalScore); els.openTarget.href = result.url;
  renderInsights(result.insights, result.finalScore); renderPreview(result.url, result.finalScore);
}
function renderLlm(response) {
  const llm = response?.llm;
  if (!llm) { els.llmState.textContent = 'ใช้คำอธิบายสำรอง'; els.llmRiskType.textContent = '-'; els.llmExplanation.textContent = 'ยังไม่สามารถดึงคำอธิบายจาก LLM ได้'; els.llmAdvice.textContent = 'ตรวจสอบโดเมนให้ชัดเจนก่อนกรอกข้อมูลสำคัญ'; return; }
  els.llmState.textContent = response.ok && ['openai', 'ollama'].includes(response.provider) ? 'LLM พร้อมใช้งาน' : 'คำอธิบายสำรอง';
  els.llmRiskType.textContent = llm.risk_type || '-'; els.llmExplanation.textContent = llm.simple_explanation || '-'; els.llmAdvice.textContent = llm.user_advice || '-';
}
function renderPrivacyLlm() { renderLlm({ llm: { risk_type: 'Privacy-first local check', simple_explanation: 'โหมดนี้ใช้ Rule-based และ Brand/Visual clues ในเครื่องเท่านั้น ไม่ส่ง URL ไป backend หรือ LLM', user_advice: 'ถ้าต้องการคะแนน ML และคำอธิบาย LLM ให้ปิด Privacy Mode แล้วตรวจใหม่' } }); els.llmState.textContent = 'Privacy Mode'; }
function addToHistory(entry) { state.history = [entry, ...state.history].slice(0, 50); saveHistory(); renderDashboard(); }
function exceedsPolicyThreshold(item) { return item.finalScore >= (Number.isFinite(item.decisionThreshold) ? item.decisionThreshold : 61); }
function renderDashboard() {
  const total = state.history.length, high = state.history.filter(exceedsPolicyThreshold).length;
  const average = total ? Math.round(state.history.reduce((sum, item) => sum + item.finalScore, 0) / total) : 0;
  setAnimatedNumber(els.metricTotal, total); setAnimatedNumber(els.metricHigh, high); setAnimatedNumber(els.metricAverage, average); setAnimatedNumber(els.metricFeedback, state.feedbackCount);
  els.historyRows.innerHTML = '';
  if (!state.history.length) { const row = document.createElement('tr'), cell = document.createElement('td'); cell.colSpan = 5; cell.textContent = 'ยังไม่มีประวัติการตรวจ'; row.appendChild(cell); els.historyRows.appendChild(row); return; }
  for (const item of state.history) { const row = document.createElement('tr'); const time = new Date(item.time).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' }); [time, item.url, item.ruleScore, Number.isFinite(item.mlScore) ? item.mlScore : (item.privacy ? 'local' : '-'), item.finalScore].forEach(value => { const cell = document.createElement('td'); cell.textContent = value; row.appendChild(cell); }); els.historyRows.appendChild(row); }
}

async function analyzeUrl(rawValue) {
  const url = normalizeInputUrl(rawValue);
  if (!url) { setMessage('กรุณาใส่ URL ที่ต้องการตรวจสอบ', true); return; }
  let parsed; try { parsed = new URL(url); } catch (_) { setMessage('รูปแบบ URL ยังไม่ถูกต้อง', true); return; }
  setMessage('กำลังวิเคราะห์ URL นี้'); els.urlInput.value = parsed.href; els.scanButton.disabled = true;
  const ruleResult = PhishRadarAnalyzer.analyzeUrl(parsed.href); renderLoading(ruleResult, parsed.href);
  const insights = brandVisualInsights(parsed.href, ruleResult);
  let ml = { ok: false, ml_score: null, final_score: ruleResult.score, model_status: state.privacyMode ? 'privacy_local_only' : 'offline' };

  if (!state.privacyMode) {
    try { ml = await predictWithMl(parsed.href, ruleResult.score); await checkHealth(); }
    catch (_) { setBackendStatus(false, 'Backend ยังไม่เปิด'); }
  } else {
    await checkHealth();
  }

  const result = { url: parsed.href, displayUrl: state.privacyMode ? redactUrl(parsed.href) : parsed.href, ruleScore: ruleResult.score, mlScore: ml.ml_score, finalScore: Number.isFinite(ml.final_score) ? ml.final_score : ruleResult.score, alpha: Number.isFinite(ml.alpha) ? ml.alpha : null, decisionThreshold: Number.isFinite(ml.decision_threshold) ? ml.decision_threshold : null, detectionLabel: ml.label || null, modelStatus: ml.model_status || null, source: 'web-app', reasons: ruleResult.reasons, threatTypes: ruleResult.threatTypes, insights, privacy: state.privacyMode, time: new Date().toISOString() };
  const historyEntry = safeHistoryItem(result);
  state.current = result; renderFinal(result); addToHistory(historyEntry);

  if (!state.privacyMode) {
    try {
      const saved = await storeSearchHistory(result);
      historyEntry.historyId = saved.history_id;
      historyEntry.deviceName = saved.device_name;
      historyEntry.url = saved.url;
      historyEntry.displayUrl = saved.url;
      saveHistory();
      els.reportState.textContent = 'Account history';
    }
    catch (_) { els.reportStatus.textContent = 'ผลตรวจแสดงได้ แต่ยังบันทึกประวัติลงฐานข้อมูลไม่ได้'; }
  }

  if (state.privacyMode) {
    renderPrivacyLlm();
  } else {
    try { renderLlm(await explainWithLlm({ url: parsed.href, rule_score: result.ruleScore, ml_score: result.mlScore, final_score: result.finalScore, alpha: result.alpha, decision_threshold: result.decisionThreshold, reasons: (ruleResult.reasons || []).slice(0, 7).map(flattenReason).filter(Boolean), threat_types: ruleResult.threatTypes || [], language: 'th' })); }
    catch (_) { renderLlm(null); }
  }
  setMessage('วิเคราะห์เสร็จแล้ว'); els.scanButton.disabled = false;
}

async function handleFeedback(label) {
  if (!state.current) return;
  els.feedbackStatus.textContent = 'กำลังบันทึก feedback...';
  if (state.current.privacy) {
    savePrivateFeedback(label);
    state.feedbackCount += 1;
    localStorage.setItem(FEEDBACK_KEY, String(state.feedbackCount));
    renderDashboard();
    els.feedbackStatus.textContent = 'Privacy Mode: บันทึก feedback ไว้ในเครื่องแล้ว ไม่ส่งไป server';
    return;
  }
  try {
    await sendFeedback({ url: state.current.url, user_label: label, rule_score: state.current.ruleScore, ml_score: Number.isFinite(state.current.mlScore) ? state.current.mlScore : null, final_score: state.current.finalScore, source: 'web-app' });
    state.feedbackCount += 1; localStorage.setItem(FEEDBACK_KEY, String(state.feedbackCount)); renderDashboard(); els.feedbackStatus.textContent = 'บันทึก feedback แล้ว';
  } catch (_) { els.feedbackStatus.textContent = 'ยังบันทึกไม่ได้ ตรวจสอบว่า backend เปิดอยู่หรือไม่'; }
}
function reportText(item = state.current) {
  if (!item) return '';
  return ['Phish Radar AI Report', `URL: ${item.privacy ? item.displayUrl : item.url}`, `Rule-based: ${item.ruleScore}/100`, `ML: ${Number.isFinite(item.mlScore) ? item.mlScore : (item.privacy ? 'local-only' : 'offline')}`, `Final: ${item.finalScore}/100`, `Alpha: ${Number.isFinite(item.alpha) ? item.alpha : '-'}`, `Decision threshold: ${Number.isFinite(item.decisionThreshold) ? item.decisionThreshold : '-'}`, `Detection: ${item.detectionLabel || '-'}`, `Privacy mode: ${item.privacy ? 'on' : 'off'}`, `Reasons: ${(item.reasons || []).slice(0, 5).map(flattenReason).join(' | ')}`, `Brand/Visual clues: ${(item.insights || []).join(' | ')}`].join('\n');
}
function copyCurrentReport() { if (!state.current) return; navigator.clipboard?.writeText(reportText(state.current)); setMessage('คัดลอกสรุปแล้ว'); }
function csvEscape(value) { return `"${String(value ?? '').replace(/"/g, '""')}"`; }
function exportHistory(format) {
  if (!state.history.length) { els.reportStatus.textContent = 'ยังไม่มีข้อมูลให้ส่งออก'; return; }
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
  let blob; let name;
  if (format === 'json') {
    blob = new Blob([JSON.stringify(state.history, null, 2)], { type: 'application/json;charset=utf-8' }); name = `phish-radar-history-${stamp}.json`;
  } else {
    const header = ['time', 'url', 'privacy', 'rule_score', 'ml_score', 'final_score', 'alpha', 'decision_threshold', 'detection_label', 'threat_types', 'insights'];
    const rows = state.history.map(item => [item.time, item.privacy ? item.displayUrl : item.url, item.privacy ? 'on' : 'off', item.ruleScore, Number.isFinite(item.mlScore) ? item.mlScore : '', item.finalScore, Number.isFinite(item.alpha) ? item.alpha : '', Number.isFinite(item.decisionThreshold) ? item.decisionThreshold : '', item.detectionLabel || '', (item.threatTypes || []).join(' | '), (item.insights || []).join(' | ')].map(csvEscape).join(','));
    blob = new Blob([[header.join(','), ...rows].join('\n')], { type: 'text/csv;charset=utf-8' }); name = `phish-radar-history-${stamp}.csv`;
  }
  const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = name; link.click(); setTimeout(() => URL.revokeObjectURL(link.href), 1000); els.reportStatus.textContent = `ส่งออก ${name} แล้ว`;
}
function copyDashboardSummary() {
  const total = state.history.length, high = state.history.filter(exceedsPolicyThreshold).length;
  const average = total ? Math.round(state.history.reduce((sum, item) => sum + item.finalScore, 0) / total) : 0;
  const text = `Phish Radar AI Dashboard\nตรวจทั้งหมด: ${total}\nเสี่ยงสูง: ${high}\nคะแนนเฉลี่ย: ${average}\nFeedback: ${state.feedbackCount}`;
  navigator.clipboard?.writeText(text); els.reportStatus.textContent = 'คัดลอกสรุป dashboard แล้ว';
}
function activateTab(tabName) {
  const tabs = ['scan', 'qr', 'dashboard'];
  const target = tabs.includes(tabName) ? tabName : 'scan';
  document.querySelector('.tabs')?.style.setProperty('--active-tab', String(tabs.indexOf(target)));
  $$('[data-tab]').forEach(link => link.classList.toggle('active', link.dataset.tab === target));
  $$('.page').forEach(page => page.classList.toggle('active', page.id === target));
}
function qrReaderAvailable() {
  return ('BarcodeDetector' in window) || typeof window.jsQR === 'function';
}
function qrReaderName() {
  if ('BarcodeDetector' in window) return 'BarcodeDetector';
  if (typeof window.jsQR === 'function') return 'jsQR fallback';
  return 'not-ready';
}
async function readQrFromSource(source) {
  if ('BarcodeDetector' in window) {
    try {
      const detector = new BarcodeDetector({ formats: ['qr_code'] });
      const codes = await detector.detect(source);
      if (codes[0]?.rawValue) return codes[0].rawValue;
    } catch (_) {}
  }
  if (typeof window.jsQR !== 'function') return '';
  const width = source.videoWidth || source.naturalWidth || source.width || 0;
  const height = source.videoHeight || source.naturalHeight || source.height || 0;
  if (!width || !height) return '';
  const canvas = els.qrCanvas;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  canvas.width = width;
  canvas.height = height;
  ctx.drawImage(source, 0, 0, width, height);
  const imageData = ctx.getImageData(0, 0, width, height);
  const code = window.jsQR(imageData.data, width, height, { inversionAttempts: 'attemptBoth' });
  return code?.data || '';
}
async function decodeImageFile(file) {
  if (!qrReaderAvailable()) {
    els.qrStatus.textContent = 'ยังโหลดตัวอ่าน QR ไม่สำเร็จ ถ้าใช้ fallback ต้องเชื่อมอินเทอร์เน็ต หรือใช้ Chrome/Brave ที่รองรับ BarcodeDetector';
    return;
  }
  els.qrStatus.textContent = `กำลังอ่าน QR จากรูปด้วย ${qrReaderName()}`;
  try {
    const image = await createImageBitmap(file);
    const value = await readQrFromSource(image);
    image.close?.();
    if (value) {
      els.qrStatus.textContent = 'อ่าน QR สำเร็จ กำลังตรวจลิงก์';
      location.hash = '#scan';
      activateTab('scan');
      analyzeUrl(value);
    } else {
      els.qrStatus.textContent = 'ยังไม่พบ QR ในรูปนี้ ลองครอปรูปให้เห็น QR ชัดขึ้น';
    }
  } catch (_) {
    els.qrStatus.textContent = 'อ่านไฟล์รูปไม่ได้ ลองใช้ภาพ PNG/JPG ที่เห็น QR ชัดเจน';
  }
}
async function startQrCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    els.qrStatus.textContent = 'เบราว์เซอร์นี้ยังเปิดกล้องจากหน้าเว็บไม่ได้';
    return;
  }
  if (!qrReaderAvailable()) {
    els.qrStatus.textContent = 'ยังไม่มีตัวอ่าน QR พร้อมใช้งาน ลองเชื่อมอินเทอร์เน็ตเพื่อโหลด jsQR หรือใช้ Chrome/Brave เวอร์ชันใหม่';
    return;
  }
  try {
    state.qrStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
    els.qrVideo.srcObject = state.qrStream;
    await els.qrVideo.play();
    els.qrVideo.hidden = false;
    els.qrPlaceholder.hidden = true;
    els.startCamera.disabled = true;
    els.stopCamera.disabled = false;
    els.qrStatus.textContent = `กำลังสแกน QR ด้วย ${qrReaderName()}`;
    const scan = async () => {
      if (!state.qrStream) return;
      try {
        const value = await readQrFromSource(els.qrVideo);
        if (value) {
          stopQrCamera();
          els.qrStatus.textContent = 'อ่าน QR สำเร็จ กำลังตรวจลิงก์';
          location.hash = '#scan';
          activateTab('scan');
          analyzeUrl(value);
          return;
        }
        els.qrStatus.textContent = `กำลังสแกน QR ด้วย ${qrReaderName()}`;
      } catch (_) {
        els.qrStatus.textContent = 'ยังอ่าน QR ไม่ได้ ลองขยับกล้องให้ภาพชัดขึ้น';
      }
      state.qrTimer = window.setTimeout(scan, 360);
    };
    scan();
  } catch (_) {
    els.qrStatus.textContent = 'เปิดกล้องไม่ได้ ตรวจสอบสิทธิ์การใช้กล้อง';
  }
}
function stopQrCamera() { if (state.qrTimer) window.clearTimeout(state.qrTimer); state.qrTimer = null; if (state.qrStream) state.qrStream.getTracks().forEach(track => track.stop()); state.qrStream = null; els.qrVideo.hidden = true; els.qrPlaceholder.hidden = false; els.startCamera.disabled = false; els.stopCamera.disabled = true; }

function redirectToLogin() {
  const next = `index.html${location.hash || ''}`;
  location.replace(`login.html?next=${encodeURIComponent(next)}`);
}

async function loadCurrentUser() {
  try {
    const response = await fetch(`${AUTH_API_BASE}/auth/me`, { credentials: 'include' });
    if (!response.ok) {
      redirectToLogin();
      return null;
    }
    const user = await response.json();
    state.user = user;
    els.accountName.textContent = user.username;
    els.accountAvatar.textContent = (user.username || 'U').slice(0, 1).toUpperCase();
    els.accountRole.textContent = user.role === 'admin' ? 'Admin' : 'User';
    els.accountRole.classList.toggle('admin', user.role === 'admin');
    els.accountSummary.hidden = false;
    document.body.classList.toggle('role-admin', user.role === 'admin');
    document.body.classList.remove('auth-pending');
    return user;
  } catch (_) {
    redirectToLogin();
    return null;
  }
}

async function logout() {
  els.logoutButton.disabled = true;
  els.logoutButton.textContent = 'กำลังออก…';
  try {
    const response = await fetch(`${AUTH_API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'X-Phish-Radar-Client': 'web-app' }
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    location.replace('login.html');
  } catch (_) {
    els.logoutButton.disabled = false;
    els.logoutButton.textContent = 'ลองออกอีกครั้ง';
  }
}

function bindEvents() {
  window.addEventListener('hashchange', () => activateTab(location.hash.replace('#', ''))); activateTab(location.hash.replace('#', '') || 'scan');
  $('[data-focus-url]')?.addEventListener('click', event => {
    event.preventDefault();
    els.scanForm.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'center' });
    els.urlInput.focus({ preventScroll: true });
  });
  els.scanForm.addEventListener('submit', event => { event.preventDefault(); analyzeUrl(els.urlInput.value); });
  els.privacyMode?.addEventListener('change', async event => { setPrivacyMode(event.target.checked); await loadSearchHistory(); checkHealth(); });
  $$('.feedback-actions button[data-feedback]').forEach(button => button.addEventListener('click', () => handleFeedback(button.dataset.feedback)));
  els.copyReport.addEventListener('click', copyCurrentReport); $('#refreshHealth').addEventListener('click', checkHealth); $('#clearHistory').addEventListener('click', clearSearchHistory);
  els.exportCsv?.addEventListener('click', () => exportHistory('csv')); els.exportJson?.addEventListener('click', () => exportHistory('json')); els.copyDashboard?.addEventListener('click', copyDashboardSummary);
  els.startCamera.addEventListener('click', startQrCamera); els.stopCamera.addEventListener('click', stopQrCamera); els.qrFile.addEventListener('change', event => { const file = event.target.files?.[0]; if (file) decodeImageFile(file); });
  els.logoutButton?.addEventListener('click', logout);
}

async function bootstrap() {
  const user = await loadCurrentUser();
  if (!user) return;
  state.history = loadJson(userHistoryKey(), []);
  setPrivacyMode(state.privacyMode);
  bindEvents();
  renderDashboard();
  await loadSearchHistory();
  renderPreview('');
  checkHealth();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js?v=20', { updateViaCache: 'none' }).catch(() => {});
}

bootstrap();

