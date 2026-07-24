const PHISH_RADAR_ML_API = 'http://127.0.0.1:8765';

async function phishRadarPredictWithMl(url, ruleScore) {
  try {
    const response = await fetch(`${PHISH_RADAR_ML_API}/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, rule_score: ruleScore })
    });
    if (!response.ok) throw new Error(`ML API ${response.status}`);
    return await response.json();
  } catch (error) {
    return {
      ok: false,
      error: error.message,
      ml_score: null,
      final_score: ruleScore,
      model_status: 'offline'
    };
  }
}

async function phishRadarExplainWithLlm(payload) {
  try {
    const response = await fetch(`${PHISH_RADAR_ML_API}/explain`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`LLM API ${response.status}`);
    return await response.json();
  } catch (error) {
    return {
      ok: false,
      provider: 'offline',
      status: 'backend_offline',
      error: error.message,
      llm: {
        risk_type: 'ยังไม่ได้เชื่อมต่อคำอธิบาย LLM',
        simple_explanation: 'ระบบยังใช้คะแนน Rule-based และ Machine Learning ได้ แต่คำอธิบายจาก Qwen ต้องเปิด backend และ Ollama ก่อน',
        user_advice: 'ตรวจสอบ URL ให้แน่ใจก่อนกรอกข้อมูลสำคัญ และหลีกเลี่ยงการดาวน์โหลดไฟล์จากเว็บที่ไม่แน่ใจ',
        confidence_note: 'คำอธิบายนี้เป็นข้อความสำรอง เพราะ backend หรือ LLM ยังไม่พร้อมใช้งาน'
      }
    };
  }
}

async function phishRadarSendFeedback(payload) {
  try {
    const response = await fetch(`${PHISH_RADAR_ML_API}/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(`Feedback API ${response.status}`);
    return await response.json();
  } catch (error) {
    return { ok: false, error: error.message };
  }
}

function phishRadarClassifyPolicy(score, decisionThreshold) {
  const highCut = Number.isFinite(decisionThreshold) ? Math.max(5, Math.min(95, decisionThreshold)) : 61;
  if (score >= Math.min(100, highCut + 20)) return { level: 'critical', text: 'อันตรายมาก' };
  if (score >= highCut) return { level: 'high', text: 'เสี่ยงสูง' };
  if (score >= Math.max(5, Math.round(highCut * 0.6))) return { level: 'medium', text: 'น่าสงสัย' };
  return { level: 'low', text: 'ปลอดภัย' };
}

function phishRadarCombineMlResult(ruleResult, ml) {
  const finalScore = ml && Number.isFinite(ml.final_score) ? ml.final_score : ruleResult.score;
  const decisionThreshold = ml && Number.isFinite(ml.decision_threshold) ? ml.decision_threshold : null;
  const classification = phishRadarClassifyPolicy(finalScore, decisionThreshold);
  return {
    ...ruleResult,
    ruleScore: ruleResult.score,
    mlScore: ml ? ml.ml_score : null,
    finalScore,
    alpha: ml && Number.isFinite(ml.alpha) ? ml.alpha : null,
    decisionThreshold,
    score: finalScore,
    level: classification.level,
    levelText: classification.text,
    safe: classification.level === 'low',
    summary: `${classification.text} (${finalScore}/100)`,
    ml
  };
}
