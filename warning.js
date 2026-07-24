const params = new URLSearchParams(location.search);
const target = params.get('target') || '';
let privacyMode = params.get('privacy_mode') === '1';
let llmEnabled = false;
let result;
try {
  const reasons = JSON.parse(params.get('reasons') || '[]');
  const score = Number(params.get('score'));
  result = Number.isFinite(score) && score > 0
    ? { ...PhishRadarAnalyzer.analyzeUrl(target), score, reasons: reasons.length ? reasons : PhishRadarAnalyzer.analyzeUrl(target).reasons }
    : PhishRadarAnalyzer.analyzeUrl(target);
} catch (_) {
  result = PhishRadarAnalyzer.analyzeUrl(target);
}

const $ = id => document.getElementById(id);

function clampRiskScore(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return null;
  return Math.max(0, Math.min(100, Math.round(number)));
}

function scoreTone(score) {
  if (!Number.isFinite(score)) return 'muted';
  if (score >= 81) return 'critical';
  if (score >= 61) return 'danger';
  if (score >= 31) return 'warn';
  return 'safe';
}

function finalRiskLevel(score, decisionThreshold) {
  const highCut = Number.isFinite(decisionThreshold) ? Math.max(5, Math.min(95, decisionThreshold)) : 61;
  if (score >= Math.min(100, highCut + 20)) return 'critical';
  if (score >= highCut) return 'high';
  if (score >= Math.max(5, Math.round(highCut * 0.6))) return 'medium';
  return 'low';
}

function setSourceRow(source, score, meta, options = {}) {
  const row = $('source' + source + 'Row');
  const value = $('source' + source + 'Value');
  const fill = $('source' + source + 'Fill');
  const metaEl = $('source' + source + 'Meta');
  if (!row || !value || !fill || !metaEl) return;

  const percent = Number.isFinite(options.percent) ? Math.max(0, Math.min(100, options.percent)) : (Number.isFinite(score) ? score : 0);
  row.dataset.tone = options.tone || scoreTone(score);
  value.textContent = options.valueText || (Number.isFinite(score) ? score + '/100' : 'ไม่พร้อม');
  metaEl.textContent = meta;
  fill.style.width = percent + '%';
}

function llmBreakdownState(response) {
  if (!response) {
    return {
      valueText: 'รอผล',
      percent: 28,
      tone: 'info',
      meta: 'กำลังขอคำอธิบายจาก LLM ผ่าน backend'
    };
  }
  if (response.ok && (response.provider === 'openai' || response.provider === 'ollama')) {
    return {
      valueText: 'พร้อม',
      percent: 100,
      tone: 'safe',
      meta: response.cached ? 'ใช้คำอธิบาย LLM ที่เคยวิเคราะห์ไว้แล้ว' : 'เชื่อมต่อ LLM สำเร็จ และสร้างคำอธิบายจากข้อมูลความเสี่ยง'
    };
  }
  if (response.status === 'privacy_mode' || response.provider === 'local-only' || response.privacy_mode) {
    return {
      valueText: 'Local only',
      percent: 100,
      tone: 'safe',
      meta: 'Privacy Mode ปิดการส่ง URL ไป backend/LLM และใช้คำแนะนำสำรองใน browser'
    };
  }
  if (response.status === 'llm_disabled') {
    return {
      valueText: 'ปิด',
      percent: 12,
      tone: 'muted',
      meta: 'ปิด LLM จาก Popup จึงไม่ส่งคำขอไป Qwen/Ollama'
    };
  }
  if (response.status === 'missing_api_key') {
    return {
      valueText: 'ปิดอยู่',
      percent: 18,
      tone: 'muted',
      meta: 'ยังไม่ได้ตั้งค่า OPENAI_API_KEY จึงไม่เรียกใช้ token'
    };
  }
  return {
    valueText: 'สำรอง',
    percent: 55,
    tone: 'warn',
    meta: 'ใช้คำอธิบายสำรอง เพราะ backend หรือ LLM ยังไม่พร้อม'
  };
}

function renderScoreBreakdown(llmResponse = null) {
  const ruleScore = clampRiskScore(getNumericWarningParam('rule_score') ?? result.ruleScore ?? result.score);
  const mlScore = clampRiskScore(getNumericWarningParam('ml_score') ?? result.mlScore);
  const finalScore = clampRiskScore(getNumericWarningParam('final_score') ?? result.finalScore ?? result.score);
  const alpha = getNumericWarningParam('alpha');
  const decisionThreshold = getNumericWarningParam('decision_threshold');
  const ruleWeight = Number.isFinite(alpha) ? Math.round(alpha * 100) : 60;
  const mlWeight = 100 - ruleWeight;

  setSourceRow('Rule', ruleScore, 'ตรวจจากกฎ เช่น ความยาว URL, subdomain, IP host, คำเสี่ยง, redirect และ encoded URL');
  if (privacyMode) {
    setSourceRow('Ml', null, 'ปิดการเรียก ML backend เพื่อไม่ส่ง URL ออกนอก browser', { valueText: 'ปิด', percent: 12, tone: 'muted' });
  } else {
    setSourceRow('Ml', mlScore, Number.isFinite(mlScore) ? `โมเดลทำนายจาก feature ของ URL แล้วนำมาถ่วงน้ำหนัก ${mlWeight}%` : 'ยังไม่ได้รับคะแนน ML จาก backend; คะแนนรวมจึงอิง Rule-base เป็นหลัก', { tone: Number.isFinite(mlScore) ? scoreTone(mlScore) : 'muted' });
  }

  const llmState = llmBreakdownState(llmResponse);
  setSourceRow('Llm', null, llmState.meta, llmState);

  const badge = $('scoreFormulaBadge');
  const blend = $('scoreBlendText');
  if (badge) {
    badge.textContent = privacyMode
      ? 'Privacy Mode • Local analysis'
      : Number.isFinite(mlScore) ? `Final = Rule ${ruleWeight}% + ML ${mlWeight}%` : 'Rule active • ML offline';
  }
  if (blend) {
    blend.textContent = privacyMode
      ? 'คะแนนรวม ' + finalScore + '/100 มาจาก Rule-base และหลักฐานบนหน้าเว็บเท่านั้น รอบนี้ไม่ส่ง URL ไป ML backend หรือ LLM'
      : Number.isFinite(mlScore)
        ? 'คะแนนรวม ' + finalScore + '/100 = Rule-base ' + ruleScore + '/100 × ' + ruleWeight + '% + ML ' + mlScore + '/100 × ' + mlWeight + '%; เกณฑ์ phishing ที่โมเดลเลือกคือ ' + (Number.isFinite(decisionThreshold) ? decisionThreshold : 61) + '/100 และ LLM ไม่ได้นำมาบวกคะแนนโดยตรง'
        : 'คะแนนรวม ' + finalScore + '/100 ใช้ Rule-base เป็นหลักในรอบนี้ และ LLM ใช้อธิบายเหตุผลเมื่อ backend พร้อม';
  }
}
$('target').textContent = target;
$('score').textContent = result.score;
$('meterFill').style.width = `${result.score}%`;
const level = finalRiskLevel(result.score, getNumericWarningParam('decision_threshold'));
const levelText = level === 'critical' ? 'อันตรายมาก' : level === 'high' ? 'เสี่ยงสูง' : level === 'medium' ? 'น่าสงสัย' : 'ปลอดภัย';
$('status').textContent = `${levelText} (${result.score}/100)`;
renderScoreBreakdown();

document.body.dataset.level = level;
const headlineText = level === 'critical'
  ? 'หยุดก่อน! ลิงก์นี้อันตรายมาก'
  : level === 'high'
    ? 'หยุดก่อน! เว็บไซต์นี้มีความเสี่ยงสูง'
    : level === 'medium'
      ? 'ระวัง! เว็บไซต์นี้น่าสงสัย'
      : 'เว็บไซต์นี้ดูปลอดภัย';
$('headline').textContent = headlineText;
$('lead').textContent = level === 'medium'
  ? 'ระบบพบสัญญาณบางอย่าง เช่น phishing, scam, malware, redirect หรือ SEO spam ควรตรวจสอบก่อนเปิดต่อ'
  : level === 'low'
    ? 'ระบบยังไม่พบสัญญาณเสี่ยงสำคัญจากกฎที่ตรวจในขณะนี้ แต่ยังควรระวังก่อนกรอกข้อมูลสำคัญ'
    : 'ระบบป้องกันก่อนเข้าถึงตรวจพบสัญญาณที่เข้าข่าย Phishing หรือเนื้อหาเสี่ยง จึงพาคุณมาหน้านี้แทนที่จะเปิดเว็บปลายทางทันที';

const threatBox = $('threatTypes');
if (threatBox) {
  threatBox.innerHTML = '';
  for (const t of (result.threatTypes || [])) {
    const span = document.createElement('span');
    span.textContent = t;
    threatBox.appendChild(span);
  }
}

const reasons = $('reasons');
reasons.innerHTML = '';
for (const r of result.reasons.slice(0, 6)) {
  const li = document.createElement('li');
  li.textContent = r.detail ? `${r.label}: ${r.detail}` : r.label;
  reasons.appendChild(li);
}
if (!result.reasons.length) {
  const li = document.createElement('li');
  li.textContent = 'คะแนนสูงจากรูปแบบ URL ที่ผิดปกติ';
  reasons.appendChild(li);
}

function flattenReason(reason) {
  if (!reason) return '';
  if (typeof reason === 'string') return reason;
  return reason.detail ? `${reason.label}: ${reason.detail}` : reason.label;
}

function renderLlmExplanation(response) {
  const status = $('llmStatus');
  const explanation = response?.llm;
  if (!explanation) {
    status.textContent = 'ยังโหลดคำอธิบายจาก LLM ไม่ได้';
    return;
  }

  $('llmRiskType').textContent = explanation.risk_type || '-';
  $('llmExplanation').textContent = explanation.simple_explanation || '-';
  $('llmAdvice').textContent = explanation.user_advice || '-';
  $('llmConfidence').textContent = explanation.confidence_note || '-';

  if (response.ok && (response.provider === 'openai' || response.provider === 'ollama')) {
    status.textContent = response.cached
      ? `ใช้คำอธิบายจาก LLM ที่เคยวิเคราะห์ไว้ (${response.model})`
      : `วิเคราะห์ด้วย LLM สำเร็จ (${response.model})`;
  } else if (response.status === 'privacy_mode' || response.provider === 'local-only' || response.privacy_mode) {
    status.textContent = 'Privacy Mode เปิดอยู่ จึงไม่เรียก AI explanation หรือ backend';
  } else if (response.status === 'llm_disabled') {
    status.textContent = 'LLM ปิดอยู่ ระบบไม่ได้ส่งคำขอไป Qwen/Ollama';
  } else if (response.status === 'missing_api_key') {
    status.textContent = 'ยังไม่ได้ตั้งค่า OPENAI_API_KEY จึงแสดงคำอธิบายสำรอง';
  } else if (response.status === 'openai_package_missing') {
    status.textContent = 'ยังไม่ได้ติดตั้งแพ็กเกจ openai ใน backend จึงแสดงคำอธิบายสำรอง';
  } else if (response.status === 'ollama_unavailable') {
    status.textContent = 'ยังเชื่อมต่อ Ollama ไม่ได้ กรุณาเปิด Ollama และติดตั้ง qwen3:4b';
  } else if (response.status === 'ollama_error') {
    status.textContent = 'Qwen/Ollama ตอบกลับไม่สำเร็จ จึงใช้คำอธิบายสำรอง';
  } else {
    status.textContent = 'ใช้คำอธิบายสำรอง เพราะ backend หรือ LLM ยังไม่พร้อม';
  }
}

function privacyModeLlmResponse() {
  return {
    ok: false,
    provider: 'local-only',
    status: 'privacy_mode',
    privacy_mode: true,
    llm: {
      risk_type: 'Privacy Mode เปิดอยู่',
      simple_explanation: 'ระบบใช้ Rule-based และหลักฐานบนหน้าเว็บที่ตรวจภายใน browser เท่านั้น จึงไม่ส่ง URL ไป backend หรือ LLM ในรอบนี้',
      user_advice: 'ถ้าจะกรอกรหัสผ่าน, OTP, seed phrase หรือข้อมูลบัตร ให้ตรวจโดเมนให้แน่ใจก่อน และควรใช้ Safe Preview เมื่อไม่มั่นใจ',
      confidence_note: 'โหมดนี้เน้นความเป็นส่วนตัว จึงปิด ML backend และคำอธิบายจาก AI ชั่วคราว'
    }
  };
}

// v2.8 independent LLM token control
function llmDisabledResponse() {
  return {
    ok: false,
    provider: 'local-only',
    status: 'llm_disabled',
    llm: {
      risk_type: 'ปิดคำอธิบายจาก LLM',
      simple_explanation: 'ระบบยังใช้ Rule-based และ Machine Learning ตรวจจับความเสี่ยง แต่ไม่ได้ส่งคำขอไป AI provider ในรอบนี้',
      user_advice: 'ตรวจสอบโดเมนและเหตุผลที่ระบบแสดงก่อนกรอกข้อมูลสำคัญ',
      confidence_note: 'LLM ถูกปิดจาก Popup จึงไม่มีการส่งคำขอไป Qwen/Ollama'
    }
  };
}

function renderPrivacyMode() {
  document.body.classList.toggle('privacy-mode', !!privacyMode);
  const panel = $('privacyPanel');
  if (panel) panel.hidden = !privacyMode;
}

function loadWarningSettings() {
  return new Promise(resolve => {
    try {
      chrome.runtime.sendMessage({ type: 'GET_SETTINGS' }, response => resolve(response?.settings || {}));
    } catch (_) {
      resolve({});
    }
  });
}

function requestLlmExplanation() {
  if (privacyMode) {
    const response = privacyModeLlmResponse();
    renderLlmExplanation(response);
    renderScoreBreakdown(response);
    return;
  }
  if (!llmEnabled) {
    const response = llmDisabledResponse();
    renderLlmExplanation(response);
    renderScoreBreakdown(response);
    return;
  }

  const payload = {
    url: target,
    rule_score: getNumericWarningParam('rule_score') ?? result.ruleScore ?? result.score,
    ml_score: getNumericWarningParam('ml_score') ?? result.mlScore ?? null,
    final_score: getNumericWarningParam('final_score') ?? result.finalScore ?? result.score,
    alpha: getNumericWarningParam('alpha'),
    decision_threshold: getNumericWarningParam('decision_threshold'),
    reasons: (result.reasons || []).slice(0, 6).map(flattenReason).filter(Boolean),
    threat_types: result.threatTypes || [],
    privacy_mode: privacyMode,
    language: 'th'
  };

  chrome.runtime.sendMessage({ type: 'EXPLAIN_WITH_LLM', payload }, response => {
    renderLlmExplanation(response);
    renderScoreBreakdown(response);
  });
}

$('goBack').addEventListener('click', () => {
  if (history.length > 1) history.back();
  else location.href = 'https://www.google.com/';
});

$('safePreview').addEventListener('click', () => {
  if (!target) return;
  const button = $('safePreview');
  button.disabled = true;
  button.textContent = 'กำลังเปิด Preview...';
  chrome.runtime.sendMessage({ type: 'OPEN_SAFE_PREVIEW', target }, response => {
    if (response?.ok) return;
    button.disabled = false;
    button.textContent = 'เปิด Safe Preview';
    const status = $('feedbackStatus');
    if (status) status.textContent = 'ยังเปิด Safe Preview ไม่ได้ ลอง Reload extension แล้วเปิดใหม่อีกครั้ง';
  });
});

$('continue').addEventListener('click', async () => {
  if (!target) return;
  await chrome.runtime.sendMessage({ type: 'ALLOW_ONCE', target });
  location.href = target;
});
function getWarningParam(name) {
  return new URLSearchParams(location.search).get(name);
}

function getNumericWarningParam(name) {
  const value = getWarningParam(name);
  if (value === null || value === '') return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function sendWarningFeedback(userLabel) {
  const target = getWarningParam('target') || '';
  const fallbackScore = getNumericWarningParam('score');
  const ruleScore = getNumericWarningParam('rule_score') ?? fallbackScore;
  const mlScore = getNumericWarningParam('ml_score');
  const finalScore = getNumericWarningParam('final_score') ?? fallbackScore;
  const status = document.getElementById('feedbackStatus');
  const payload = {
    url: target,
    user_label: userLabel,
    rule_score: ruleScore,
    ml_score: mlScore,
    final_score: finalScore,
    privacy_mode: privacyMode,
    source: 'warning-page'
  };

  if (status) status.textContent = 'กำลังบันทึก feedback...';

  chrome.runtime.sendMessage({ type: 'SEND_FEEDBACK', payload }, response => {
    if (!status) return;
    status.textContent = response?.local
      ? 'Privacy Mode: บันทึก feedback ไว้ในเครื่องแล้ว ไม่ส่ง URL ไป backend'
      : response?.ok
      ? 'บันทึก feedback แล้ว ขอบคุณครับ'
      : 'ยังบันทึกไม่ได้ ตรวจสอบว่า backend เปิดอยู่หรือไม่';
  });
}

document.getElementById('feedbackDangerous')?.addEventListener('click', () => sendWarningFeedback('dangerous'));
document.getElementById('feedbackSafe')?.addEventListener('click', () => sendWarningFeedback('safe'));
document.getElementById('feedbackUnsure')?.addEventListener('click', () => sendWarningFeedback('unsure'));

async function initWarningPage() {
  if (globalThis.PhishRadarAppTrust?.isTrustedWebAppUrl(target)) {
    location.replace(target);
    return;
  }
  const settings = await loadWarningSettings();
  privacyMode = privacyMode || !!settings.privacyMode;
  llmEnabled = !!settings.llmEnabled;
  renderPrivacyMode();
  requestLlmExplanation();
}

renderPrivacyMode();
initWarningPage();



