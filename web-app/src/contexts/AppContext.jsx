import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState
} from 'react';
import { api } from '../services/api';
import {
  analyzer,
  brandVisualInsights,
  flattenReason,
  normalizeInputUrl,
  redactUrl,
  safeHistoryUrl
} from '../services/risk';
import { useAuth } from './AuthContext';

const HISTORY_KEY = 'phishRadarWebHistory';
const FEEDBACK_KEY = 'phishRadarWebFeedbackCount';
const PRIVACY_KEY = 'phishRadarPrivacyMode';
const PRIVATE_FEEDBACK_KEY = 'phishRadarPrivateFeedback';

const AppContext = createContext(null);

function loadArray(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(value) ? value : [];
  } catch {
    return [];
  }
}

function safeHistoryItem(item) {
  const url = safeHistoryUrl(item?.displayUrl || item?.url, Boolean(item?.privacy));
  return { ...item, url, displayUrl: url };
}

function mapServerHistory(item) {
  const layers = item.layer_results || {};
  const fusion = layers.learned_fusion || {};
  return {
    historyId: item.history_id,
    url: item.url,
    displayUrl: item.url,
    ruleScore: item.rule_score,
    riskProbability: item.risk_probability,
    riskScore: item.risk_score ?? item.final_score,
    decision: item.decision,
    warningThreshold: item.warning_threshold ?? item.decision_threshold,
    blockingThreshold: item.blocking_threshold,
    modelVersion: item.model_version,
    policyVersion: item.policy_version,
    featureSchemaVersion: item.feature_schema_version,
    layerResults: layers,
    fuzzyScore: layers.fuzzy_rule_evidence?.score ?? null,
    randomForestScore: item.ml_score,
    fusionMethod: fusion.method || null,
    fusionApplied: fusion.status === 'ready',
    mlScore: item.ml_score,
    finalScore: item.risk_score ?? item.final_score,
    ruleWeight: item.alpha ?? null,
    mlWeight: item.alpha == null ? null : 1 - item.alpha,
    riskFormula: fusion.method
      ? 'FinalScore = 100 × LearnedFusion(FuzzyScore, RandomForestScore)'
      : null,
    decisionThreshold: item.warning_threshold ?? item.decision_threshold,
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

function privateExplanation() {
  return {
    state: 'Privacy Mode',
    riskType: 'Privacy-first local check',
    explanation: 'โหมดนี้ใช้ Rule-based และ Brand/Visual clues ในเครื่องเท่านั้น ไม่ส่ง URL ไป Backend หรือ LLM',
    advice: 'ถ้าต้องการคะแนน ML และคำอธิบาย Qwen ให้ปิด Privacy Mode แล้วตรวจใหม่'
  };
}

function fallbackExplanation() {
  return {
    state: 'ใช้คำอธิบายสำรอง',
    riskType: '-',
    explanation: 'ยังไม่สามารถดึงคำอธิบายจาก LLM ได้',
    advice: 'ตรวจสอบโดเมนให้ชัดเจนก่อนกรอกข้อมูลสำคัญ'
  };
}

function mapLlm(response) {
  const llm = response?.llm;
  if (!llm) return fallbackExplanation();
  return {
    state: response.ok && ['openai', 'ollama'].includes(response.provider)
      ? 'LLM พร้อมใช้งาน'
      : 'คำอธิบายสำรอง',
    riskType: llm.risk_type || '-',
    explanation: llm.simple_explanation || '-',
    advice: llm.user_advice || '-'
  };
}

export function AppProvider({ children }) {
  const { user } = useAuth();
  const [current, setCurrent] = useState(null);
  const [analysisPhase, setAnalysisPhase] = useState('idle');
  const [history, setHistory] = useState([]);
  const [feedbackCount, setFeedbackCount] = useState(
    () => Number(localStorage.getItem(FEEDBACK_KEY) || 0)
  );
  const [privacyMode, setPrivacyModeState] = useState(
    () => localStorage.getItem(PRIVACY_KEY) === '1'
  );
  const [backendStatus, setBackendStatus] = useState({
    online: null,
    label: 'กำลังเช็คระบบ'
  });
  const [health, setHealth] = useState(null);
  const [formMessage, setFormMessage] = useState('');
  const [formError, setFormError] = useState(false);
  const [reportStatus, setReportStatus] = useState('');
  const [reportState, setReportState] = useState('Account history');

  const userHistoryKey = useCallback(
    () => `${HISTORY_KEY}:${user?.user_id || 'anonymous'}`,
    [user?.user_id]
  );

  const persistHistory = useCallback(items => {
    localStorage.setItem(
      userHistoryKey(),
      JSON.stringify(items.slice(0, 50).map(safeHistoryItem))
    );
  }, [userHistoryKey]);

  const updateHistory = useCallback(updater => {
    setHistory(previous => {
      const next = typeof updater === 'function' ? updater(previous) : updater;
      persistHistory(next);
      return next;
    });
  }, [persistHistory]);

  const checkHealth = useCallback(async () => {
    if (privacyMode) {
      const localHealth = {
        privacy: true,
        backendText: 'Local rule-based mode',
        modelText: 'ข้าม ML เพื่อไม่ส่ง URL',
        llmText: 'ข้าม LLM',
        feedbackText: 'เก็บ feedback ใน browser เท่านั้น'
      };
      setHealth(localHealth);
      setBackendStatus({ online: true, label: 'Privacy Mode เปิดอยู่' });
      return localHealth;
    }

    setBackendStatus({ online: null, label: 'กำลังเช็คระบบ' });
    try {
      const response = await api.health();
      const databaseReady = response.database?.connected && response.database?.auth_schema_ready;
      const policy = response.model_policy;
      const llmModel = response.llm?.provider === 'ollama'
        ? response.llm.ollama_model
        : response.llm?.openai_model;
      const mapped = {
        ...response,
        backendText: response.ok
          ? `Online · Database ${databaseReady ? 'พร้อม' : 'ยังไม่พร้อม'}`
          : 'ไม่พร้อม',
        modelText: response.model_ready
          ? `${policy?.model_version || 'Risk Model'} · Fuzzy + Random Forest + learned fusion · warn ${policy?.warning_threshold ?? '-'} · block ${policy?.blocking_threshold ?? '-'}`
          : 'ยังไม่พบ model.pkl',
        llmText: response.llm?.llm_ready
          ? `พร้อมใช้ ${llmModel || 'LLM'}`
          : `ยังไม่พร้อม · ${llmModel || 'ตรวจสอบ Qwen/Ollama'}`,
        feedbackText: response.feedback_path || '-'
      };
      setHealth(mapped);
      setBackendStatus({ online: true, label: 'Backend พร้อมใช้งาน' });
      return mapped;
    } catch {
      setHealth({
        backendText: 'Offline',
        modelText: '-',
        llmText: '-',
        feedbackText: '-'
      });
      setBackendStatus({ online: false, label: 'Backend ยังไม่เปิด' });
      return null;
    }
  }, [privacyMode]);

  const loadHistory = useCallback(async () => {
    if (!user) return;
    const localItems = loadArray(userHistoryKey()).map(safeHistoryItem);
    const localPrivate = localItems.filter(item => item.privacy);

    if (privacyMode) {
      setHistory(localPrivate);
      setReportState('Privacy local history');
      setReportStatus('Privacy Mode: แสดงเฉพาะประวัติที่ปิดบังและเก็บใน browser');
      persistHistory(localPrivate);
      return;
    }

    try {
      const data = await api.history(50);
      const serverItems = (data.items || []).map(mapServerHistory);
      const items = [...localPrivate, ...serverItems]
        .sort((left, right) => new Date(right.time) - new Date(left.time))
        .slice(0, 50);
      setHistory(items);
      persistHistory(items);
      setReportState('Account history');
      setReportStatus(`โหลดประวัติจากบัญชี ${serverItems.length} รายการ`);
    } catch {
      setHistory(localItems);
      setReportState('Local fallback');
      setReportStatus('ยังโหลดประวัติจากฐานข้อมูลไม่ได้ จึงใช้ข้อมูลใน browser ชั่วคราว');
    }
  }, [persistHistory, privacyMode, user, userHistoryKey]);

  useEffect(() => {
    document.body.classList.toggle('privacy-active', privacyMode);
    localStorage.setItem(PRIVACY_KEY, privacyMode ? '1' : '0');
    if (user) {
      loadHistory();
      checkHealth();
    }
  }, [checkHealth, loadHistory, privacyMode, user]);

  const setPrivacyMode = useCallback(enabled => {
    setPrivacyModeState(Boolean(enabled));
  }, []);

  const analyzeUrl = useCallback(async rawValue => {
    const normalized = normalizeInputUrl(rawValue);
    if (!normalized) {
      setFormMessage('กรุณาใส่ URL ที่ต้องการตรวจสอบ');
      setFormError(true);
      return null;
    }

    let parsed;
    try {
      parsed = new URL(normalized);
    } catch {
      setFormMessage('รูปแบบ URL ยังไม่ถูกต้อง');
      setFormError(true);
      return null;
    }

    const url = parsed.href;
    const ruleResult = analyzer.analyzeUrl(url);
    const insights = brandVisualInsights(url, ruleResult);
    setFormMessage('กำลังวิเคราะห์ URL นี้');
    setFormError(false);
    setAnalysisPhase('analyzing');
    setCurrent({
      url,
      displayUrl: privacyMode ? redactUrl(url) : url,
      ruleScore: ruleResult.score,
      riskScore: ruleResult.score,
      finalScore: ruleResult.score,
      warningThreshold: 61,
      blockingThreshold: 81,
      reasons: ruleResult.reasons,
      threatTypes: ruleResult.threatTypes,
      insights,
      privacy: privacyMode,
      llm: privacyMode ? privateExplanation() : {
        state: 'กำลังวิเคราะห์',
        riskType: '-',
        explanation: 'กำลังขอคำอธิบายจาก Backend',
        advice: '-'
      },
      time: new Date().toISOString()
    });

    let prediction = {
      ok: false,
      risk_score: ruleResult.score,
      ml_score: null,
      model_status: privacyMode ? 'privacy_local_only' : 'offline'
    };

    if (!privacyMode) {
      try {
        prediction = await api.predict({ url, rule_score: ruleResult.score });
        checkHealth();
      } catch {
        setBackendStatus({ online: false, label: 'Backend ยังไม่เปิด' });
      }
    }

    const result = {
      url,
      displayUrl: privacyMode ? redactUrl(url) : url,
      ruleScore: ruleResult.score,
      riskProbability: Number.isFinite(prediction.risk_probability)
        ? prediction.risk_probability
        : null,
      riskScore: Number.isFinite(prediction.risk_score)
        ? prediction.risk_score
        : ruleResult.score,
      decision: prediction.decision || null,
      warningThreshold: Number.isFinite(prediction.warning_threshold)
        ? prediction.warning_threshold
        : 61,
      blockingThreshold: Number.isFinite(prediction.blocking_threshold)
        ? prediction.blocking_threshold
        : 81,
      modelVersion: prediction.model_version || null,
      policyVersion: prediction.policy_version || null,
      featureSchemaVersion: prediction.feature_schema_version || null,
      layerResults: prediction.layer_results || {},
      fuzzyScore: Number.isFinite(prediction.fuzzy_score) ? prediction.fuzzy_score : null,
      randomForestScore: Number.isFinite(prediction.random_forest_score)
        ? prediction.random_forest_score
        : Number.isFinite(prediction.ml_score) ? prediction.ml_score : null,
      fusionMethod: prediction.fusion_method || null,
      fusionApplied: Boolean(prediction.fusion_applied),
      mlScore: Number.isFinite(prediction.ml_score) && prediction.model_status === 'ready'
        ? prediction.ml_score
        : null,
      finalScore: Number.isFinite(prediction.risk_score)
        ? prediction.risk_score
        : ruleResult.score,
      ruleWeight: Number.isFinite(prediction.rule_weight) ? prediction.rule_weight : null,
      mlWeight: Number.isFinite(prediction.ml_weight) ? prediction.ml_weight : null,
      riskFormula: prediction.risk_formula || 'FinalScore = 100 × LearnedFusion(FuzzyScore, RandomForestScore)',
      decisionThreshold: Number.isFinite(prediction.warning_threshold)
        ? prediction.warning_threshold
        : null,
      detectionLabel: prediction.label || null,
      modelStatus: prediction.model_status || null,
      source: 'web-app-react',
      reasons: ruleResult.reasons,
      threatTypes: ruleResult.threatTypes,
      insights,
      privacy: privacyMode,
      llm: privacyMode ? privateExplanation() : {
        state: 'กำลังวิเคราะห์',
        riskType: '-',
        explanation: 'กำลังขอคำอธิบายจาก Backend',
        advice: '-'
      },
      time: new Date().toISOString()
    };

    setCurrent(result);
    updateHistory(previous => [safeHistoryItem(result), ...previous].slice(0, 50));

    if (!privacyMode) {
      try {
        await api.createHistory({
          url: result.url,
          rule_score: result.ruleScore,
          risk_probability: result.riskProbability,
          risk_score: result.riskScore,
          decision: result.decision,
          warning_threshold: result.warningThreshold,
          blocking_threshold: result.blockingThreshold,
          model_version: result.modelVersion,
          policy_version: result.policyVersion,
          feature_schema_version: result.featureSchemaVersion,
          layer_results: result.layerResults,
          ml_score: Number.isFinite(result.mlScore) ? result.mlScore : null,
          final_score: result.finalScore,
          alpha: result.ruleWeight,
          decision_threshold: result.warningThreshold,
          detection_label: result.detectionLabel,
          model_status: result.modelStatus,
          source: result.source
        });
        setReportState('Account history');
      } catch {
        setReportStatus('ผลตรวจแสดงได้ แต่ยังบันทึกประวัติลงฐานข้อมูลไม่ได้');
      }
    }

    let llm = privateExplanation();
    if (!privacyMode) {
      try {
        const response = await api.explain({
          url,
          rule_score: result.ruleScore,
          fuzzy_score: result.fuzzyScore,
          random_forest_score: result.randomForestScore,
          fusion_method: result.fusionMethod,
          ml_score: result.mlScore,
          final_score: result.finalScore,
          alpha: result.ruleWeight,
          risk_probability: result.riskProbability,
          risk_score: result.riskScore,
          decision: result.decision,
          warning_threshold: result.warningThreshold,
          blocking_threshold: result.blockingThreshold,
          model_version: result.modelVersion,
          policy_version: result.policyVersion,
          layer_results: result.layerResults,
          reasons: (ruleResult.reasons || []).slice(0, 7).map(flattenReason).filter(Boolean),
          threat_types: ruleResult.threatTypes || [],
          language: 'th'
        });
        llm = mapLlm(response);
      } catch {
        llm = fallbackExplanation();
      }
    }

    const completed = { ...result, llm };
    setCurrent(completed);
    setAnalysisPhase('done');
    setFormMessage('วิเคราะห์เสร็จแล้ว');
    return completed;
  }, [checkHealth, privacyMode, updateHistory]);

  const submitFeedback = useCallback(async label => {
    if (!current) return;
    if (current.privacy) {
      const entries = loadArray(PRIVATE_FEEDBACK_KEY);
      entries.unshift({
        url: redactUrl(current.url),
        user_label: label,
        rule_score: current.ruleScore ?? null,
        ml_score: Number.isFinite(current.mlScore) ? current.mlScore : null,
        final_score: current.finalScore ?? null,
        source: 'web-app-react-privacy-local',
        privacy_mode: true,
        saved_at: new Date().toISOString()
      });
      localStorage.setItem(PRIVATE_FEEDBACK_KEY, JSON.stringify(entries.slice(0, 200)));
      const nextCount = feedbackCount + 1;
      setFeedbackCount(nextCount);
      localStorage.setItem(FEEDBACK_KEY, String(nextCount));
      return 'Privacy Mode: บันทึก feedback ไว้ในเครื่องแล้ว ไม่ส่งไป server';
    }

    try {
      await api.feedback({
        url: current.url,
        user_label: label,
        rule_score: current.ruleScore,
        ml_score: Number.isFinite(current.mlScore) ? current.mlScore : null,
        final_score: current.finalScore,
        source: 'web-app-react'
      });
      const nextCount = feedbackCount + 1;
      setFeedbackCount(nextCount);
      localStorage.setItem(FEEDBACK_KEY, String(nextCount));
      return 'บันทึก feedback แล้ว';
    } catch {
      return 'ยังบันทึกไม่ได้ ตรวจสอบว่า Backend เปิดอยู่หรือไม่';
    }
  }, [current, feedbackCount]);

  const clearHistory = useCallback(async () => {
    if (privacyMode) {
      updateHistory(previous => previous.filter(item => !item.privacy));
      setReportStatus('Privacy Mode: ล้างเฉพาะประวัติ local แล้ว โดยไม่เรียก Backend');
      return;
    }
    try {
      if (history.some(item => !item.privacy)) await api.clearHistory();
      updateHistory([]);
      setReportStatus('ล้างประวัติของบัญชีนี้แล้ว');
    } catch {
      setReportStatus('ยังล้างประวัติจากฐานข้อมูลไม่ได้ กรุณาตรวจสอบ Backend');
    }
  }, [history, privacyMode, updateHistory]);

  const value = useMemo(() => ({
    current,
    analysisPhase,
    history,
    feedbackCount,
    privacyMode,
    setPrivacyMode,
    backendStatus,
    health,
    checkHealth,
    formMessage,
    formError,
    reportStatus,
    reportState,
    setReportStatus,
    analyzeUrl,
    submitFeedback,
    clearHistory,
    reloadHistory: loadHistory
  }), [
    current,
    analysisPhase,
    history,
    feedbackCount,
    privacyMode,
    setPrivacyMode,
    backendStatus,
    health,
    checkHealth,
    formMessage,
    formError,
    reportStatus,
    reportState,
    analyzeUrl,
    submitFeedback,
    clearHistory,
    loadHistory
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp() {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used inside AppProvider.');
  return context;
}
