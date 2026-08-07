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
      risk_probability: null,
      risk_score: ruleScore,
      decision: null,
      warning_threshold: null,
      blocking_threshold: null,
      fuzzy_score: null,
      random_forest_score: null,
      fusion_method: null,
      fusion_applied: false,
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

function phishRadarClassifyPolicy(score, warningThreshold, blockingThreshold, decision) {
  const warnCut = Number.isFinite(warningThreshold) ? Math.max(1, Math.min(99, warningThreshold)) : 61;
  const blockCut = Number.isFinite(blockingThreshold) ? Math.max(warnCut, Math.min(100, blockingThreshold)) : Math.min(100, warnCut + 20);
  if (decision === 'block' || score >= blockCut) return { level: 'critical', decision: 'block', text: 'อันตรายมาก' };
  if (decision === 'warn' || score >= warnCut) return { level: 'high', decision: 'warn', text: 'เสี่ยงสูง' };
  if (score >= Math.max(5, Math.round(warnCut * 0.6))) return { level: 'medium', decision: 'allow', text: 'น่าสงสัย' };
  return { level: 'low', decision: 'allow', text: 'ปลอดภัย' };
}

function phishRadarCombineMlResult(ruleResult, ml) {
  const riskScore = ml && Number.isFinite(ml.risk_score) ? ml.risk_score : ruleResult.score;
  const mlScore = ml && Number.isFinite(ml.ml_score) ? ml.ml_score : null;
  const warningThreshold = ml && Number.isFinite(ml.warning_threshold) ? ml.warning_threshold : null;
  const blockingThreshold = ml && Number.isFinite(ml.blocking_threshold) ? ml.blocking_threshold : null;
  const classification = phishRadarClassifyPolicy(riskScore, warningThreshold, blockingThreshold, ml?.decision);
  return {
    ...ruleResult,
    ruleScore: ruleResult.score,
    riskProbability: Number.isFinite(ml?.risk_probability) ? ml.risk_probability : null,
    riskScore,
    decision: ml?.decision || classification.decision,
    warningThreshold,
    blockingThreshold,
    modelVersion: ml?.model_version || null,
    policyVersion: ml?.policy_version || null,
    featureSchemaVersion: ml?.feature_schema_version || null,
    layerResults: ml?.layer_results || {},
    fuzzyScore: Number.isFinite(ml?.fuzzy_score) ? ml.fuzzy_score : null,
    randomForestScore: Number.isFinite(ml?.random_forest_score) ? ml.random_forest_score : mlScore,
    fusionMethod: ml?.fusion_method || null,
    fusionApplied: Boolean(ml?.fusion_applied),
    mlScore: ml?.model_status === 'ready' ? mlScore : null,
    finalScore: riskScore,
    ruleWeight: Number.isFinite(ml?.rule_weight) ? ml.rule_weight : null,
    mlWeight: Number.isFinite(ml?.ml_weight) ? ml.ml_weight : null,
    riskFormula: ml?.risk_formula || 'FinalScore = 100 × LearnedFusion(FuzzyScore, RandomForestScore)',
    decisionThreshold: warningThreshold,
    score: riskScore,
    level: classification.level,
    levelText: classification.text,
    safe: classification.level === 'low',
    summary: `${classification.text} (${riskScore}/100)`,
    ml
  };
}
