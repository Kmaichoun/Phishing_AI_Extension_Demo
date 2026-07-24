importScripts('analyzer.js');
importScripts('app-trust.js');
try {
  importScripts('ml-feedback-client.js');
} catch (error) {
  console.warn('Phish Radar ML client is not available:', error);
}

const DEFAULT_SETTINGS = {
  threshold: 61,
  warnMedium: true,
  highlightLinks: true,
  protectForms: true,
  showStatusPanel: true,
  pageScanningEnabled: true,
  privacyMode: false,
  llmEnabled: false,
  searchProtection: true,
  clipboardProtection: true,
  pauseDirectNavigationCheck: false
};

const APP_TRUST = globalThis.PhishRadarAppTrust;

async function getSettings() {
  const data = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  return { ...DEFAULT_SETTINGS, ...data };
}

function warningUrl(target, source = 'navigation', extra = {}) {
  const ruleScore = extra.ruleScore ?? extra.rule_score ?? extra.score ?? '';
  const mlScore = extra.mlScore ?? extra.ml_score ?? extra.ml?.ml_score ?? '';
  const finalScore = extra.finalScore ?? extra.final_score ?? extra.score ?? '';
  const alpha = extra.alpha ?? extra.ml?.alpha ?? '';
  const decisionThreshold = extra.decisionThreshold ?? extra.decision_threshold ?? extra.ml?.decision_threshold ?? '';
  const params = new URLSearchParams({
    target,
    source,
    score: String(finalScore),
    rule_score: String(ruleScore),
    ml_score: mlScore === null || mlScore === undefined ? '' : String(mlScore),
    final_score: String(finalScore),
    alpha: alpha === null || alpha === undefined ? '' : String(alpha),
    decision_threshold: decisionThreshold === null || decisionThreshold === undefined ? '' : String(decisionThreshold),
    privacy_mode: extra.privacyMode || extra.privacy_mode ? '1' : '',
    reasons: JSON.stringify(extra.reasons ?? [])
  });
  return chrome.runtime.getURL('warning.html?' + params.toString());
}

function localOnlyMlResult(ruleScore) {
  return {
    ok: false,
    model_status: 'privacy-mode',
    ml_score: null,
    final_score: ruleScore,
    privacy_mode: true
  };
}

function effectiveRiskThreshold(settings, result) {
  const userThreshold = Number(settings?.threshold || 61);
  const modelThreshold = Number(result?.decisionThreshold ?? result?.decision_threshold ?? result?.ml?.decision_threshold);
  return Number.isFinite(modelThreshold) ? modelThreshold : userThreshold;
}

function privacyLlmFallback() {
  return {
    ok: false,
    provider: 'local-only',
    status: 'privacy_mode',
    privacy_mode: true,
    llm: {
      risk_type: 'Privacy Mode เปิดอยู่',
      simple_explanation: 'ระบบวิเคราะห์จาก Rule-based และหลักฐานบนหน้าเว็บภายใน browser เท่านั้น จึงไม่ส่ง URL ไป backend หรือ LLM',
      user_advice: 'ตรวจสอบโดเมนให้แน่ใจก่อนกรอกข้อมูลสำคัญ หากต้องการคำอธิบายจาก LLM ให้ปิด Privacy Mode ชั่วคราว',
      confidence_note: 'โหมดนี้เน้นความเป็นส่วนตัว จึงปิด Machine Learning backend และ AI explanation ในรอบนี้'
    }
  };
}

// v2.8 independent LLM token control
function llmDisabledFallback() {
  return {
    ok: false,
    provider: 'local-only',
    status: 'llm_disabled',
    llm: {
      risk_type: 'ปิดคำอธิบายจาก LLM',
      simple_explanation: 'ระบบยังใช้ Rule-based และ Machine Learning ตรวจจับความเสี่ยงตามปกติ แต่รอบนี้ไม่ส่งคำขอไป AI provider',
      user_advice: 'ตรวจสอบโดเมนและเหตุผลจากระบบก่อนกรอกข้อมูลสำคัญ เปิด LLM เฉพาะเมื่อต้องการคำอธิบายเพิ่มเติม',
      confidence_note: 'LLM ถูกปิดจาก Popup จึงไม่มีการส่งคำขอไป Qwen/Ollama'
    }
  };
}

function redactUrlForPrivacy(value) {
  try {
    const url = new URL(String(value || ''));
    return `${url.protocol}//${url.hostname}/[redacted]`;
  } catch (_) {
    return '[redacted]';
  }
}

async function savePrivateFeedback(payload = {}) {
  const feedback = {
    ...payload,
    url: redactUrlForPrivacy(payload.url),
    privacy_mode: true,
    stored_locally: true,
    saved_at: new Date().toISOString()
  };
  const data = await chrome.storage.local.get({ privacyFeedback: [] });
  const list = [...data.privacyFeedback, feedback].slice(-200);
  await chrome.storage.local.set({ privacyFeedback: list });
  return { ok: true, local: true, privacy_mode: true, saved_count: list.length };
}

function hashString(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h += (h << 1) + (h << 4) + (h << 7) + (h << 8) + (h << 24);
  }
  return 'allow_' + (h >>> 0).toString(16);
}

async function isAllowedOnce(url) {
  const key = hashString(url);
  const data = await chrome.storage.session.get(key);
  const ts = data[key];
  if (!ts) return false;
  await chrome.storage.session.remove(key);
  return Date.now() - ts < 60_000;
}

async function setAllowedOnce(url) {
  const key = hashString(String(url || ''));
  const payload = {};
  payload[key] = Date.now();
  await chrome.storage.session.set(payload);
}

async function isWhitelisted(hostname) {
  const { whitelist = [] } = await chrome.storage.sync.get({ whitelist: [] });
  return whitelist.some(item => hostname === item || hostname.endsWith('.' + item));
}

async function analyzeUrlWithMl(url, options = {}) {
  if (APP_TRUST?.isTrustedWebAppUrl(url)) {
    return APP_TRUST.createTrustedResult(url);
  }
  const ruleResult = PhishRadarAnalyzer.analyzeUrl(url, options);
  const settings = await getSettings();

  if (settings.privacyMode) {
    return {
      ...ruleResult,
      ruleScore: ruleResult.score,
      mlScore: null,
      finalScore: ruleResult.score,
      score: ruleResult.score,
      privacyMode: true,
      ml: localOnlyMlResult(ruleResult.score)
    };
  }

  if (typeof phishRadarPredictWithMl !== 'function') {
    return {
      ...ruleResult,
      ruleScore: ruleResult.score,
      mlScore: null,
      finalScore: ruleResult.score,
      score: ruleResult.score,
      ml: { ok: false, model_status: 'client-missing' }
    };
  }

  const ml = await phishRadarPredictWithMl(url, ruleResult.score);
  if (typeof phishRadarCombineMlResult === 'function') {
    return phishRadarCombineMlResult(ruleResult, ml);
  }

  const finalScore = ml?.final_score ?? ruleResult.score;
  return {
    ...ruleResult,
    ruleScore: ruleResult.score,
    mlScore: ml?.ml_score ?? null,
    finalScore,
    alpha: Number.isFinite(ml?.alpha) ? ml.alpha : null,
    decisionThreshold: Number.isFinite(ml?.decision_threshold) ? ml.decision_threshold : null,
    score: finalScore,
    ml
  };
}

const SAFE_PREVIEW_TTL_MS = 15 * 60 * 1000;

function safePreviewKey(tabId) {
  return 'safe_preview_' + tabId;
}

async function setSafePreview(tabId, target) {
  if (!tabId || !target) return;
  const key = safePreviewKey(tabId);
  const payload = {};
  payload[key] = { target, startedAt: Date.now() };
  await chrome.storage.session.set(payload);
}

async function getSafePreview(tabId) {
  if (!tabId) return null;
  const key = safePreviewKey(tabId);
  const data = await chrome.storage.session.get(key);
  const preview = data[key];
  if (!preview) return null;
  if (Date.now() - Number(preview.startedAt || 0) > SAFE_PREVIEW_TTL_MS) {
    await chrome.storage.session.remove(key);
    return null;
  }
  return preview;
}

async function clearSafePreview(tabId) {
  if (!tabId) return;
  await chrome.storage.session.remove(safePreviewKey(tabId));
}

async function applySafePreviewIfNeeded(tabId, url) {
  if (!tabId || !url || !/^https?:/.test(url)) return;
  const preview = await getSafePreview(tabId);
  if (!preview) return;
  try {
    await chrome.scripting.insertCSS({ target: { tabId }, files: ['safe-preview.css'] });
  } catch (error) {
    console.warn('Safe Preview CSS injection failed:', error);
  }
  try {
    await chrome.scripting.executeScript({ target: { tabId }, files: ['safe-preview.js'] });
  } catch (error) {
    console.warn('Safe Preview script injection failed:', error);
  }
}

async function updateBadge(tabId, result) {
  if (!tabId || tabId < 0) return;
  const classification = typeof phishRadarClassifyPolicy === 'function'
    ? phishRadarClassifyPolicy(result.score, result.decisionThreshold)
    : { level: result.level || 'low', text: result.levelText || 'ไม่ทราบระดับ' };
  const text = classification.level === 'critical' ? '!!' : classification.level === 'high' ? 'HIGH' : classification.level === 'medium' ? 'WARN' : '✓';
  const color = classification.level === 'critical' ? '#991b1b' : classification.level === 'high' ? '#ef4444' : classification.level === 'medium' ? '#f59e0b' : '#22c55e';
  await chrome.action.setBadgeText({ tabId, text });
  await chrome.action.setBadgeBackgroundColor({ tabId, color });
  await chrome.action.setTitle({ tabId, title: 'Phish Radar AI: ' + classification.text + ' (' + result.score + '/100)' });
}

async function updateTrustedAppBadge(tabId) {
  if (!tabId || tabId < 0) return;
  await chrome.action.setBadgeText({ tabId, text: 'APP' });
  await chrome.action.setBadgeBackgroundColor({ tabId, color: '#d76d77' });
  await chrome.action.setTitle({ tabId, title: 'Phish Radar AI: Web App ของระบบที่เชื่อถือได้' });
}

async function clearScanBadge(tabId) {
  if (!tabId || tabId < 0) return;
  await chrome.action.setBadgeText({ tabId, text: '' });
  await chrome.action.setTitle({ tabId, title: 'Phish Radar AI: การสแกนหน้าเว็บปิดอยู่' });
}

async function syncPageScanningAcrossTabs(enabled) {
  const tabs = await chrome.tabs.query({});
  await Promise.all(tabs.map(async tab => {
    if (!tab.id) return;
    if (!enabled) await clearScanBadge(tab.id);
    else if (tab.url && APP_TRUST?.isTrustedWebAppUrl(tab.url)) await updateTrustedAppBadge(tab.id);
    else if (tab.url && /^https?:/.test(tab.url)) await updateBadge(tab.id, PhishRadarAnalyzer.analyzeUrl(tab.url));
    try {
      await chrome.tabs.sendMessage(tab.id, { type: 'SET_PAGE_SCANNING', enabled });
    } catch (_) {}
  }));
}

chrome.runtime.onInstalled.addListener(async () => {
  const existing = await chrome.storage.sync.get(DEFAULT_SETTINGS);
  await chrome.storage.sync.set({ ...DEFAULT_SETTINGS, ...existing });
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (!tab?.url || !/^https?:/.test(tab.url)) return;
  const settings = await getSettings();
  if (!settings.pageScanningEnabled) {
    await clearScanBadge(tabId);
    if (changeInfo.status === 'complete') await applySafePreviewIfNeeded(tabId, tab.url);
    return;
  }
  if (APP_TRUST?.isTrustedWebAppUrl(tab.url)) {
    await updateTrustedAppBadge(tabId);
    return;
  }
  if (changeInfo.status === 'loading' || changeInfo.status === 'complete') {
    const result = PhishRadarAnalyzer.analyzeUrl(tab.url);
    await updateBadge(tabId, result);
  }
  if (changeInfo.status === 'complete') {
    await applySafePreviewIfNeeded(tabId, tab.url);
  }
});

chrome.tabs.onActivated.addListener(async ({ tabId }) => {
  try {
    const tab = await chrome.tabs.get(tabId);
    if (!tab?.url || !/^https?:/.test(tab.url)) return;
    const settings = await getSettings();
    if (!settings.pageScanningEnabled) {
      await clearScanBadge(tabId);
      return;
    }
    if (APP_TRUST?.isTrustedWebAppUrl(tab.url)) {
      await updateTrustedAppBadge(tabId);
      return;
    }
    const result = PhishRadarAnalyzer.analyzeUrl(tab.url);
    await updateBadge(tabId, result);
  } catch (_) {}
});

chrome.webNavigation.onBeforeNavigate.addListener(async details => {
  if (details.frameId !== 0 || !/^https?:/.test(details.url)) return;
  const settings = await getSettings();
  if (!settings.pageScanningEnabled) return;
  if (settings.pauseDirectNavigationCheck) return;
  if (await getSafePreview(details.tabId)) return;
  if (await isAllowedOnce(details.url)) return;
  if (APP_TRUST?.isTrustedWebAppUrl(details.url)) {
    await updateTrustedAppBadge(details.tabId);
    return;
  }

  const url = new URL(details.url);
  if (await isWhitelisted(url.hostname)) return;

  const result = await analyzeUrlWithMl(details.url);
  if (result.score >= effectiveRiskThreshold(settings, result)) {
    await updateBadge(details.tabId, result);
    try {
      await chrome.tabs.update(details.tabId, { url: warningUrl(details.url, 'direct-navigation', result) });
    } catch (_) {}
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    if (message?.type === 'ANALYZE_URL') {
      const result = await analyzeUrlWithMl(message.url, message.options || {});
      if (sender?.tab?.id) await updateBadge(sender.tab.id, result);
      sendResponse({ ok: true, result });
      return;
    }

    if (message?.type === 'OPEN_WARNING') {
      if (APP_TRUST?.isTrustedWebAppUrl(message.target)) {
        const tabId = sender?.tab?.id || message.tabId;
        if (tabId) await updateTrustedAppBadge(tabId);
        sendResponse({ ok: true, trustedWebApp: true });
        return;
      }
      const result = message.result?.ruleScore !== undefined
        ? message.result
        : await analyzeUrlWithMl(message.target);
      const tabId = sender?.tab?.id || message.tabId;
      if (tabId) {
        await updateBadge(tabId, result);
        await chrome.tabs.update(tabId, { url: warningUrl(message.target, message.source || 'click', result) });
      } else {
        await chrome.tabs.create({ url: warningUrl(message.target, message.source || 'manual', result) });
      }
      sendResponse({ ok: true });
      return;
    }

    if (message?.type === 'ALLOW_ONCE') {
      await setAllowedOnce(message.target);
      sendResponse({ ok: true });
      return;
    }

    if (message?.type === 'OPEN_SAFE_PREVIEW') {
      const tabId = sender?.tab?.id || message.tabId;
      const target = message.target;
      if (!tabId || !target || !/^https?:/i.test(target)) {
        sendResponse({ ok: false, error: 'Safe Preview needs an http/https target tab' });
        return;
      }
      await setSafePreview(tabId, target);
      await setAllowedOnce(target);
      await chrome.tabs.update(tabId, { url: target });
      sendResponse({ ok: true });
      return;
    }

    if (message?.type === 'END_SAFE_PREVIEW') {
      const tabId = sender?.tab?.id || message.tabId;
      await clearSafePreview(tabId);
      if (message.openFull && message.url) await setAllowedOnce(message.url);
      sendResponse({ ok: true });
      return;
    }

    if (message?.type === 'GET_SETTINGS') {
      sendResponse({ ok: true, settings: await getSettings() });
      return;
    }

    if (message?.type === 'SET_SETTINGS') {
      const nextSettings = message.settings || {};
      await chrome.storage.sync.set(nextSettings);
      if (Object.prototype.hasOwnProperty.call(nextSettings, 'pageScanningEnabled')) {
        await syncPageScanningAcrossTabs(!!nextSettings.pageScanningEnabled);
      }
      sendResponse({ ok: true, settings: await getSettings() });
      return;
    }

    if (message?.type === 'ADD_WHITELIST') {
      if (APP_TRUST?.isTrustedWebAppUrl(message.url)) {
        sendResponse({ ok: true, alreadyTrusted: true, whitelist: [] });
        return;
      }
      const host = new URL(message.url).hostname.replace(/^www\./, '');
      const data = await chrome.storage.sync.get({ whitelist: [] });
      const whitelist = Array.from(new Set([...data.whitelist, host]));
      await chrome.storage.sync.set({ whitelist });
      sendResponse({ ok: true, whitelist });
      return;
    }

    if (message?.type === 'SEND_FEEDBACK') {
      const settings = await getSettings();
      if (settings.privacyMode || message.payload?.privacy_mode) {
        sendResponse(await savePrivateFeedback(message.payload || {}));
        return;
      }
      if (typeof phishRadarSendFeedback !== 'function') {
        sendResponse({ ok: false, error: 'ML feedback client is not available' });
        return;
      }
      const saved = await phishRadarSendFeedback(message.payload || {});
      sendResponse(saved);
      return;
    }

    if (message?.type === 'EXPLAIN_WITH_LLM') {
      const settings = await getSettings();
      if (settings.privacyMode || message.payload?.privacy_mode) {
        sendResponse(privacyLlmFallback());
        return;
      }
      if (!settings.llmEnabled) {
        sendResponse(llmDisabledFallback());
        return;
      }
      if (typeof phishRadarExplainWithLlm !== 'function') {
        sendResponse({ ok: false, error: 'LLM client is not available' });
        return;
      }
      const explanation = await phishRadarExplainWithLlm(message.payload || {});
      sendResponse(explanation);
      return;
    }

    if (message?.type === 'OPEN_WEB_APP') {
      const url = APP_TRUST?.DEFAULT_WEB_APP_URL || 'http://127.0.0.1:5505/login.html';
      await chrome.tabs.create({ url });
      sendResponse({ ok: true, url });
      return;
    }

    if (message?.type === 'OPEN_QR_SCANNER') {
      await chrome.tabs.create({ url: chrome.runtime.getURL('qr-scanner.html') });
      sendResponse({ ok: true });
      return;
    }

    sendResponse({ ok: false, error: 'Unknown message type' });
  })();
  return true;
});

