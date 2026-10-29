const params = new URLSearchParams(location.search);
const target = params.get('target') || '';
let privacyMode = params.get('privacy_mode') === '1';
let llmEnabled = false;
let llmRequestPending = false;
let llmRequestSequence = 0;
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
  if (score >= 80) return 'critical';
  if (score >= 60) return 'danger';
  if (score >= 31) return 'warn';
  return 'safe';
}

function finalRiskLevel(score, warningThreshold, blockingThreshold, decision) {
  const warnCut = Number.isFinite(warningThreshold) ? Math.max(1, Math.min(99, warningThreshold)) : 60;
  const blockCut = Number.isFinite(blockingThreshold) ? Math.max(warnCut, Math.min(100, blockingThreshold)) : Math.min(100, warnCut + 20);
  if (decision === 'block') return 'critical';
  if (decision === 'warn') return 'high';
  if (decision !== 'allow' && score >= blockCut) return 'critical';
  if (decision !== 'allow' && score >= warnCut) return 'high';
  if (score >= Math.max(5, Math.round(warnCut * 0.6))) return 'medium';
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
  if (!response || response.status === 'pending') {
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
  if (response.status === 'privacy_mode' || response.privacy_mode) {
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

function warningModelReady() {
  const status = getWarningParam('model_status');
  const score = getNumericWarningParam('random_forest_score') ?? getNumericWarningParam('ml_score');
  // Older warning URLs did not transmit status. Their actual model outputs
  // remain readable; fusion_applied=false does not mean the RF is offline.
  return !privacyMode && (status === 'ready' || (!status && Number.isFinite(score) && Number.isFinite(getNumericWarningParam('risk_probability'))));
}

function mlWarningWithoutRuleEvidence() {
  const rule = getNumericWarningParam('rule_score') ?? result.ruleScore ?? 0;
  const positiveReasons = result.reasons.some(reason => Number(reason?.points) > 0);
  return warningModelReady() && getWarningParam('fusion_method') === 'ml_only' && rule === 0 && !positiveReasons;
}

function renderScoreBreakdown(llmResponse = null) {
  const modelVersion = getWarningParam('model_version') || '';
  const modelReady = warningModelReady();
  const mlOnly = getWarningParam('fusion_method') === 'ml_only';

  $('scoreLabel').textContent = modelReady && mlOnly ? 'Random Forest หลังปรับเทียบ' : modelReady ? 'คะแนนจากโมเดลของผลตรวจนี้' : 'คะแนนตรวจ URL ในเครื่อง';
  if (privacyMode) {
    setSourceRow('Ml', null, 'ปิด URL Risk Model เพื่อไม่ส่ง URL ออกนอก browser', { valueText: 'ปิด', percent: 12, tone: 'muted' });
  } else {
    setSourceRow('Ml', null, modelReady ? `${mlOnly ? 'Random Forest หลังปรับเทียบ' : 'โมเดลที่ใช้ในผลตรวจนี้'}${modelVersion ? ` (${modelVersion})` : ''}` : 'โมเดลไม่พร้อม รอบนี้จึงใช้หลักฐาน local เป็นคะแนนสำรอง', { valueText: modelReady ? 'พร้อม' : 'ไม่พร้อม', percent: modelReady ? 100 : 0, tone: modelReady ? 'info' : 'muted' });
  }

  const llmState = llmBreakdownState(llmResponse);
  setSourceRow('Llm', null, llmState.meta, llmState);

  const badge = $('scoreFormulaBadge');
  const blend = $('scoreBlendText');
  if (badge) {
    badge.textContent = privacyMode
      ? 'Privacy Mode • Local analysis'
      : modelReady && mlOnly ? 'Random Forest • Calibrated score'
      : modelReady ? 'URL Risk Model • Ready' : 'Local evidence • Risk Model offline';
  }
  if (blend) {
    blend.textContent = privacyMode
      ? 'คะแนนตรวจในเครื่องมาจากกฎ URL และหลักฐาน local รอบนี้ไม่ส่ง URL ไปโมเดลหรือ LLM'
      : modelReady && mlOnly
        ? 'คะแนนด้านบนมาจาก Random Forest หลังปรับเทียบเพียงชุดเดียว ข้อสังเกตจากกฎ URL แสดงเป็นเหตุผลประกอบ และ LLM ไม่เปลี่ยนคะแนน'
        : modelReady ? 'คะแนนด้านบนมาจากโมเดลที่ใช้ในผลตรวจนี้ อ่านข้อสังเกตจาก URL และคำอธิบายประกอบได้ด้านล่าง'
        : 'โมเดลไม่พร้อม คะแนนด้านบนจึงเป็นผลตรวจในเครื่องชั่วคราว ไม่ใช่คะแนนจาก Random Forest';
  }
}
$('target').textContent = target;
$('score').textContent = result.score;
$('meterFill').style.width = `${result.score}%`;
const level = finalRiskLevel(
  result.score,
  getNumericWarningParam('warning_threshold') ?? getNumericWarningParam('decision_threshold'),
  getNumericWarningParam('blocking_threshold'),
  getWarningParam('decision')
);
const modelOnlyWarning = mlWarningWithoutRuleEvidence();
const levelText = modelOnlyWarning && (level === 'high' || level === 'critical') ? 'โมเดลประเมินว่าควรระวัง' : level === 'critical' ? 'อันตรายมาก' : level === 'high' ? 'เสี่ยงสูง' : level === 'medium' ? 'น่าสงสัย' : 'ยังไม่พบความเสี่ยงชัดเจน';
$('status').textContent = `${levelText} (${result.score}/100)`;
renderScoreBreakdown();

document.body.dataset.level = level;
const headlineText = modelOnlyWarning && (level === 'high' || level === 'critical')
  ? 'โมเดลประเมินว่าลิงก์นี้ควรระวัง'
  : level === 'critical'
  ? 'หยุดก่อน! ลิงก์นี้อันตรายมาก'
  : level === 'high'
    ? 'หยุดก่อน! เว็บไซต์นี้มีความเสี่ยงสูง'
    : level === 'medium'
      ? 'ระวัง! เว็บไซต์นี้น่าสงสัย'
      : 'ยังไม่พบความเสี่ยงชัดเจนจาก URL';
$('headline').textContent = headlineText;
$('lead').textContent = modelOnlyWarning && (level === 'high' || level === 'critical')
  ? 'คะแนนโมเดลถึงเกณฑ์เตือน แต่ยังไม่พบหลักฐานเสี่ยงจากกฎ URL ที่ตรวจ ผลนี้ยังไม่ยืนยันว่าเว็บไซต์เป็น phishing ควรตรวจแหล่งที่มาก่อนกรอกข้อมูลสำคัญ'
  : level === 'medium'
  ? 'คะแนนอยู่ในช่วงที่ควรอ่านข้อสังเกตเพิ่มเติม ผลตรวจนี้ไม่ได้ยืนยันว่าเว็บไซต์เป็น phishing'
  : level === 'low'
    ? 'ระบบยังไม่พบสัญญาณเสี่ยงสำคัญจากกฎที่ตรวจในขณะนี้ แต่ยังควรระวังก่อนกรอกข้อมูลสำคัญ'
    : 'ผลตรวจ URL ถึงเกณฑ์เตือน จึงพาคุณมาหน้านี้เพื่ออ่านเหตุผลก่อนเปิดปลายทาง ผลนี้ไม่ได้ยืนยันเนื้อหาทั้งเว็บไซต์';

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
  li.textContent = modelOnlyWarning ? 'ยังไม่พบหลักฐานเสี่ยงจากกฎ URL; การเตือนครั้งนี้มาจากคะแนนโมเดล' : 'ยังไม่มีเหตุผลจากกฎ URL ให้แสดง';
  reasons.appendChild(li);
}

function flattenReason(reason) {
  if (!reason) return '';
  if (typeof reason === 'string') return reason;
  return reason.detail ? `${reason.label}: ${reason.detail}` : reason.label;
}

function renderExplanationReasons(id, items, emptyText) {
  const list = $(id);
  const empty = $(id + 'Empty');
  if (!list || !empty) return;
  const reasons = Array.isArray(items) ? items.filter(item => item && typeof item === 'object'
    && typeof item.title === 'string' && typeof item.explanation === 'string'
    && item.title.trim() && item.explanation.trim()).slice(0, 4) : [];
  list.innerHTML = '';
  list.hidden = !reasons.length;
  empty.hidden = Boolean(reasons.length);
  empty.textContent = emptyText;
  for (const item of reasons) {
    const li = document.createElement('li');
    const title = document.createElement('strong');
    const detail = document.createElement('p');
    title.textContent = item.title.trim().slice(0, 160);
    detail.textContent = item.explanation.trim().slice(0, 500);
    li.appendChild(title);
    li.appendChild(detail);
    list.appendChild(li);
  }
}

function renderLlmExplanation(response) {
  if (!response?.llm) response = buildLocalExplanation(response?.status || 'llm_unavailable');
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
  const hasDetailedReasons = Array.isArray(explanation.risk_reasons) || Array.isArray(explanation.reassuring_reasons);
  renderExplanationReasons('llmRiskReasons', explanation.risk_reasons,
    hasDetailedReasons ? 'ยังไม่พบข้อควรระวังจากข้อมูล URL ที่ตรวจในครั้งนี้'
      : 'คำอธิบายนี้ไม่มีเหตุผลแยกรายข้อ อ่านสรุปด้านบนหรือตรวจ URL ใหม่เพื่อรับรายละเอียดล่าสุด');
  renderExplanationReasons('llmReassuringReasons', explanation.reassuring_reasons,
    hasDetailedReasons ? 'ยังไม่พบข้อมูลที่ช่วยลดความกังวลจาก URL ที่ตรวจ ผลนี้ไม่ยืนยันว่าเว็บไซต์ปลอดภัยหรืออันตราย'
      : 'ไม่มีข้อมูลประกอบส่วนนี้ในคำอธิบาย ไม่ได้หมายความว่าเว็บไซต์ปลอดภัยหรืออันตราย');

  if (response.ok && (response.provider === 'openai' || response.provider === 'ollama')) {
    status.textContent = response.cached
      ? `ใช้คำอธิบายจาก LLM ที่เคยวิเคราะห์ไว้ (${response.model})`
      : `วิเคราะห์ด้วย LLM สำเร็จ (${response.model})`;
  } else if (response.status === 'pending') {
    status.textContent = 'แสดงเหตุผลจากผลตรวจไว้ก่อน กำลังขอคำสรุปจาก Ollama…';
  } else if (response.status === 'local_evidence') {
    status.textContent = 'ข้อสังเกตจากผลตรวจในเครื่อง ยังไม่ได้ใช้คำอธิบายจาก Ollama';
  } else if (response.status === 'privacy_mode' || response.privacy_mode) {
    status.textContent = 'Privacy Mode: แสดงเหตุผลในเครื่อง ไม่ส่ง URL ไปโมเดลหรือ Ollama';
  } else if (response.status === 'llm_disabled') {
    status.textContent = 'แสดงเหตุผลจากผลตรวจในเครื่อง; เปิด AI Explanation ใน Popup เพื่อขอคำสรุปจาก Ollama';
  } else if (response.status === 'llm_timeout') {
    status.textContent = 'Ollama ตอบกลับไม่ทัน แสดงเหตุผลจากผลตรวจไว้ก่อน สามารถกดขอคำอธิบายอีกครั้งได้';
  } else if (response.status === 'missing_api_key') {
    status.textContent = 'ยังไม่ได้ตั้งค่า OPENAI_API_KEY จึงแสดงคำอธิบายสำรอง';
  } else if (response.status === 'openai_package_missing') {
    status.textContent = 'ยังไม่ได้ติดตั้งแพ็กเกจ openai ใน backend จึงแสดงคำอธิบายสำรอง';
  } else if (response.status === 'ollama_unavailable') {
    status.textContent = 'ยังเชื่อมต่อ Ollama ไม่ได้ กรุณาเปิด Ollama และตรวจสอบโมเดลที่ตั้งค่าไว้';
  } else if (response.status === 'ollama_error') {
    status.textContent = 'Qwen/Ollama ตอบกลับไม่สำเร็จ จึงใช้คำอธิบายสำรอง';
  } else {
    status.textContent = 'ใช้คำอธิบายสำรอง เพราะ backend หรือ LLM ยังไม่พร้อม';
  }
}

function buildLocalExplanation(status = 'local_evidence') {
  const modelReady = warningModelReady();
  const warning = getNumericWarningParam('warning_threshold') ?? getNumericWarningParam('decision_threshold') ?? 60;
  const blocking = getNumericWarningParam('blocking_threshold') ?? Math.max(80, warning);
  const score = getNumericWarningParam('risk_score') ?? getNumericWarningParam('final_score') ?? result.score;
  const suppliedDecision = getWarningParam('decision');
  const decision = ['allow', 'warn', 'block'].includes(suppliedDecision) ? suppliedDecision
    : score >= blocking ? 'block' : score >= warning ? 'warn' : 'allow';
  const rawReasons = Array.isArray(result.reasons) ? result.reasons : [];
  const positive = rawReasons.filter(reason => reason && typeof reason === 'object' && Number(reason.points) > 0);
  const negative = rawReasons.filter(reason => reason && typeof reason === 'object' && Number(reason.points) < 0);
  const rule = getNumericWarningParam('rule_score') ?? result.ruleScore ?? PhishRadarAnalyzer.analyzeUrl(target).score;
  const modelOnly = modelReady && ['warn', 'block'].includes(decision) && !positive.length && rule === 0;
  const source = modelReady ? getWarningParam('fusion_method') === 'ml_only'
    ? 'Random Forest หลังปรับเทียบ' : 'โมเดลที่ใช้ในผลตรวจนี้' : 'กฎตรวจ URL ในเครื่อง';
  const relation = decision === 'block' ? `ผลตัดสินถึงเกณฑ์หยุดตรวจสอบ ${blocking}`
    : decision === 'warn' ? `ผลตัดสินถึงเกณฑ์เตือน ${warning}` : `ผลตัดสินยังไม่ถึงเกณฑ์เตือน ${warning}`;
  const riskReasons = [];
  const reassuringReasons = [];
  const append = (rows, title, detail) => {
    title = String(title || '').trim().slice(0, 120);
    detail = String(detail || '').trim().slice(0, 300);
    if (title && detail && !rows.some(item => item.title === title)) rows.push({ title, explanation: detail });
  };
  const meaning = reason => {
    const text = String(reason.title || reason.label || '').toLowerCase();
    if (/เลียนแบบ|แบรนด์|brand/.test(text)) return 'ชื่อที่อ้างแบรนด์ไม่ยืนยันว่าเป็นผู้ให้บริการจริง ควรตรวจโดเมนปลายทางก่อนกรอกข้อมูล';
    if (/ลิงก์ย่อ|redirect|ปลายทาง|ซ้อน|shorten/.test(text)) return 'ปลายทางอาจอ่านได้ไม่ชัดจากลิงก์นี้ ควรตรวจโดเมนที่จะไปถึงก่อนกรอกข้อมูลหรือดาวน์โหลด';
    if (/ข้อมูลลับ|รหัสผ่าน|otp|token|credential|ยืนยันตัวตน/.test(text)) return 'เกี่ยวข้องกับข้อมูลสำคัญ ควรตรวจเจ้าของปลายทางก่อนส่งข้อมูล การพบรูปแบบนี้ยังไม่ยืนยันว่ามีการขโมยข้อมูล';
    if (/ไม่ได้ใช้ https|ไม่มี https/.test(text)) return 'การเชื่อมต่อที่ไม่เข้ารหัสอาจเปิดเผยข้อมูลระหว่างทาง ควรหลีกเลี่ยงการส่งข้อมูลสำคัญก่อนตรวจสอบ';
    return 'เป็นข้อสังเกตที่ควรตรวจร่วมกับแหล่งที่มาของลิงก์ ไม่ใช่การยืนยันว่าเว็บไซต์เป็น phishing';
  };
  for (const reason of positive) {
    append(riskReasons, reason.title || reason.label || 'ข้อควรตรวจสอบจาก URL',
      [reason.detail, meaning(reason)].filter(Boolean).join(' '));
  }
  if (!riskReasons.length && rule > 0) {
    append(riskReasons, 'มีข้อควรตรวจสอบจากผลตรวจในเครื่อง', 'ผลตรวจระบุข้อควรระวัง แต่ไม่มีรายละเอียดรายข้อ จึงยังระบุสาเหตุเฉพาะไม่ได้');
  }
  if (modelOnly) {
    append(riskReasons, 'โมเดลประเมินว่าควรระวัง', 'ผลของโมเดลถึงเกณฑ์เตือน แต่ยังไม่มีหลักฐานเสี่ยงจากกฎ URL สนับสนุน ควรตรวจเพิ่มเติมและยังยืนยัน phishing ไม่ได้');
  }
  try {
    if (new URL(target).protocol === 'https:') {
      append(reassuringReasons, 'ใช้ HTTPS', 'การเชื่อมต่อเข้ารหัสช่วยป้องกันข้อมูลระหว่างทาง แต่เว็บไซต์หลอกก็ใช้ HTTPS ได้ จึงต้องตรวจชื่อโดเมนร่วมด้วย');
    }
  } catch (_) {}
  for (const reason of negative) {
    append(reassuringReasons, reason.title || reason.label, [reason.detail,
      'เป็นข้อมูลประกอบที่ช่วยลดความกังวลจากรูปแบบลิงก์ แต่ไม่รับรองความปลอดภัยของเนื้อหาหรือทุกหน้า'].filter(Boolean).join(' '));
  }
  if (!positive.length && rule === 0) {
    append(reassuringReasons, 'ยังไม่พบสัญญาณเสี่ยงชัดเจนจากกฎ URL', 'กฎที่ใช้ในการตรวจครั้งนี้ยังไม่มีข้อสังเกตเสี่ยงชัดเจน การไม่พบสัญญาณไม่ได้แปลว่าครอบคลุมทุกวิธีโจมตี');
  }
  const verdict = decision === 'block' ? 'ความเสี่ยงสูง: ควรหยุดตรวจสอบก่อน'
    : decision === 'warn' ? 'ควรระวัง: ตรวจแหล่งที่มาก่อนใช้งาน'
    : positive.length ? 'คะแนนยังไม่ถึงเกณฑ์เตือน แต่มีข้อควรตรวจสอบจาก URL' : 'ยังไม่พบความเสี่ยงชัดเจนจาก URL';
  return {
    ok: false, provider: 'local-only', status, privacy_mode: privacyMode,
    llm: {
      risk_type: verdict,
      simple_explanation: `คะแนน ${score}/100 มาจาก ${source}; ${relation}${modelOnly ? ' คะแนนสูงจากโมเดล แต่ยังไม่มีหลักฐานจากกฎ URL สนับสนุน จึงยังยืนยัน phishing ไม่ได้' : ''}`,
      user_advice: decision === 'allow' ? 'ตรวจชื่อโดเมนและแหล่งที่มาก่อนกรอกข้อมูลสำคัญ'
        : 'ตรวจผ่านช่องทางทางการก่อน อย่าเพิ่งกรอกรหัสผ่าน OTP หรือดาวน์โหลดไฟล์',
      confidence_note: privacyMode ? 'Privacy Mode ใช้ข้อสังเกตในเครื่อง ไม่ส่ง URL ไป backend หรือ Ollama และไม่รับรองเนื้อหาเว็บ'
        : 'ข้อสังเกตนี้ตรวจจากผลและรูปแบบ URL ไม่ใช่สาเหตุราย feature ของ Random Forest หรือการยืนยันเนื้อหาเว็บ',
      risk_reasons: riskReasons.slice(0, 4), reassuring_reasons: reassuringReasons.slice(0, 4)
    }
  };
}

function privacyModeLlmResponse() {
  return buildLocalExplanation('privacy_mode');
}

// v2.8 independent LLM token control
function llmDisabledResponse() {
  return buildLocalExplanation('llm_disabled');
}

function updateExplanationButton() {
  const button = $('retryExplanation');
  if (!button) return;
  button.hidden = privacyMode || !llmEnabled;
  button.disabled = llmRequestPending || privacyMode || !llmEnabled;
  button.textContent = llmRequestPending ? 'กำลังขอคำอธิบาย…' : 'ขอคำอธิบายจาก Ollama อีกครั้ง';
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
  if (llmRequestPending) return;
  if (privacyMode) {
    const response = privacyModeLlmResponse();
    renderLlmExplanation(response);
    renderScoreBreakdown(response);
    updateExplanationButton();
    return;
  }
  if (!llmEnabled) {
    const response = llmDisabledResponse();
    renderLlmExplanation(response);
    renderScoreBreakdown(response);
    updateExplanationButton();
    return;
  }

  const payload = {
    url: target,
    rule_score: getNumericWarningParam('rule_score') ?? result.ruleScore ?? result.score,
    fuzzy_score: getNumericWarningParam('fuzzy_score'),
    random_forest_score: getNumericWarningParam('random_forest_score') ?? getNumericWarningParam('ml_score'),
    fusion_method: getWarningParam('fusion_method') || null,
    ml_score: getNumericWarningParam('ml_score'),
    risk_probability: getNumericWarningParam('risk_probability'),
    risk_score: getNumericWarningParam('risk_score') ?? result.finalScore ?? result.score,
    decision: getWarningParam('decision') || null,
    warning_threshold: getNumericWarningParam('warning_threshold') ?? getNumericWarningParam('decision_threshold'),
    blocking_threshold: getNumericWarningParam('blocking_threshold'),
    model_version: getWarningParam('model_version') || null,
    policy_version: getWarningParam('policy_version') || null,
    feature_schema_version: getWarningParam('feature_schema_version') || null,
    reasons: (result.reasons || []).slice(0, 6).map(flattenReason).filter(Boolean),
    evidence_reasons: (result.reasons || [])
      .filter(reason => reason && typeof reason === 'object' && Number.isFinite(reason.points))
      .slice(0, 8)
      .map(reason => ({
        title: String(reason.title || reason.name || reason.label || ''),
        detail: String(reason.detail || ''),
        points: reason.points
      })),
    threat_types: result.threatTypes || [],
    privacy_mode: privacyMode,
    language: 'th'
  };

  llmRequestPending = true;
  const requestSequence = ++llmRequestSequence;
  const pending = buildLocalExplanation('pending');
  renderLlmExplanation(pending);
  renderScoreBreakdown(pending);
  updateExplanationButton();
  let timer;
  const finish = response => {
    if (requestSequence !== llmRequestSequence || !llmRequestPending) return;
    clearTimeout(timer);
    llmRequestPending = false;
    const display = response?.llm ? response : buildLocalExplanation(response?.status || 'llm_unavailable');
    renderLlmExplanation(display);
    renderScoreBreakdown(display);
    updateExplanationButton();
  };
  timer = setTimeout(() => finish(buildLocalExplanation('llm_timeout')), 120000);
  try {
    chrome.runtime.sendMessage({ type: 'EXPLAIN_WITH_LLM', payload }, response => {
      if (chrome.runtime.lastError) finish(buildLocalExplanation('llm_unavailable'));
      else finish(response);
    });
  } catch (_) {
    finish(buildLocalExplanation('llm_unavailable'));
  }
}

$('retryExplanation')?.addEventListener('click', requestLlmExplanation);

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

renderLlmExplanation(buildLocalExplanation());
updateExplanationButton();
renderPrivacyMode();
initWarningPage();



