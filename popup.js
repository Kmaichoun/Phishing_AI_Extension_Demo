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
  clipboardProtection: true
};

const $ = id => document.getElementById(id);
let activeTab = null;
let currentResult = null;
let popupTheme = 'dark';

function applyPopupTheme() {
  const dark = popupTheme === 'dark';
  document.documentElement.classList.toggle('phish-radar-theme-dark', dark);
  document.documentElement.classList.toggle('phish-radar-theme-light', !dark);
  document.body.classList.toggle('phish-radar-theme-dark', dark);
  document.body.classList.toggle('phish-radar-theme-light', !dark);
  document.body.dataset.phishRadarTheme = popupTheme;

  const button = $('popupThemeToggle');
  if (button) {
    button.title = dark ? 'เปลี่ยนเป็นโหมดสว่าง' : 'เปลี่ยนเป็นโหมดมืด';
    button.setAttribute('aria-label', button.title);
    button.setAttribute('aria-pressed', String(!dark));
  }
}

async function loadPopupTheme() {
  try {
    const data = await chrome.storage.sync.get({ phishRadarTheme: 'dark' });
    popupTheme = data.phishRadarTheme === 'light' ? 'light' : 'dark';
  } catch (_) {
    popupTheme = 'dark';
  }
  applyPopupTheme();
}

async function togglePopupTheme() {
  popupTheme = popupTheme === 'dark' ? 'light' : 'dark';
  try {
    await chrome.storage.sync.set({ phishRadarTheme: popupTheme });
  } catch (_) {}

  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (document.startViewTransition && !reduceMotion) {
    document.startViewTransition(() => applyPopupTheme());
  } else {
    applyPopupTheme();
  }

  try {
    if (activeTab?.id) {
      chrome.tabs.sendMessage(
        activeTab.id,
        { type: 'SET_UI_THEME', theme: popupTheme },
        () => void chrome.runtime.lastError,
      );
    }
  } catch (_) {}
}

try {
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'sync' || !changes.phishRadarTheme) return;
    popupTheme = changes.phishRadarTheme.newValue === 'light' ? 'light' : 'dark';
    applyPopupTheme();
  });
} catch (_) {}

$('popupThemeToggle')?.addEventListener('click', togglePopupTheme);

function sendMessage(message) {
  return new Promise(resolve => chrome.runtime.sendMessage(message, response => resolve(response || { ok: false })));
}

async function sendToTab(tabId, message) {
  return new Promise(resolve => {
    chrome.tabs.sendMessage(tabId, message, response => {
      if (chrome.runtime.lastError) return resolve({ ok: false, error: chrome.runtime.lastError.message });
      resolve(response || { ok: false });
    });
  });
}

async function ensureContentScript(tabId) {
  if (!tabId) return false;
  const ping = await sendToTab(tabId, { type: 'GET_LAST_SCAN' });
  if (ping?.ok) return true;

  // When the extension is loaded while a tab is already open, Chrome may not
  // inject declared content scripts into that existing page until refresh.
  // This fallback injects the same files from the popup so the demo works
  // immediately on the currently open Google/search page.
  try {
    await chrome.scripting.insertCSS({ target: { tabId }, files: ['content.css'] });
  } catch (_) {}
  try {
    await chrome.scripting.executeScript({ target: { tabId }, files: ['analyzer.js', 'content.js'] });
    await new Promise(resolve => setTimeout(resolve, 350));
    const check = await sendToTab(tabId, { type: 'GET_LAST_SCAN' });
    return !!check?.ok;
  } catch (error) {
    console.warn('Phish Radar injection failed:', error);
    return false;
  }
}

function colorClass(score) {
  if (score >= 61) return 'bad';
  if (score >= 31) return 'warn';
  return 'good';
}

function reasonText(r) {
  return `${r.label}${r.detail ? ': ' + r.detail : ''}`;
}

function setToast(message) {
  const toast = $('toast');
  if (!toast) return;
  toast.textContent = message || '';
}

function setVerdictState(state) {
  const icon = $('verdictIcon');
  if (icon) icon.dataset.state = state;
}

function renderScanningPaused() {
  currentResult = null;
  const scoreCard = $('scoreCard');
  scoreCard.classList.remove('good', 'warn', 'bad', 'is-analyzing');
  $('host').textContent = 'หยุดการสแกนชั่วคราว';
  $('score').textContent = '--';
  $('meterFill').style.width = '0%';
  setVerdictState('paused');
  $('status').textContent = 'การสแกนหน้าเว็บปิดอยู่';
  $('verdictText').textContent = 'เปิดสวิตช์เพื่อกลับมาตรวจการนำทาง ลิงก์ ฟอร์ม และ Clipboard';
  $('reasons').innerHTML = '<li>ไม่มีการวิเคราะห์หน้าเว็บขณะที่สวิตช์ปิดอยู่</li>';
  renderStats({ scanned: 0, risky: 0, high: 0, shown: 0 });
}

function renderPageScanning(enabled) {
  const card = $('pageScanCard');
  const badge = $('pageScanBadge');
  const input = $('pageScanningEnabled');
  const scanButton = $('scanLinks');
  if (input) input.checked = !!enabled;
  if (card) card.classList.toggle('is-enabled', !!enabled);
  if (badge) badge.textContent = enabled ? 'เปิดอยู่' : 'ปิดอยู่';
  if (scanButton) {
    scanButton.disabled = !enabled;
    scanButton.textContent = enabled ? 'ตรวจหน้านี้' : 'เปิดสแกนก่อน';
  }
  if (!enabled) renderScanningPaused();
}

// v2.8 independent LLM token control
function renderCloudModes(privacyEnabled, llmEnabled) {
  const privacyCard = $('privacyCard');
  const privacyBadge = $('privacyBadge');
  const llmCard = $('llmCard');
  const llmBadge = $('llmBadge');
  const llmInput = $('llmEnabled');
  const llmDescription = $('llmDescription');
  const footer = $('modeFooter');

  if (privacyCard) privacyCard.classList.toggle('is-private', !!privacyEnabled);
  if (privacyBadge) privacyBadge.textContent = privacyEnabled ? 'Local only' : 'Cloud assist';

  if (llmInput) llmInput.disabled = !!privacyEnabled;
  if (llmCard) {
    llmCard.classList.toggle('is-enabled', !!llmEnabled && !privacyEnabled);
    llmCard.classList.toggle('is-locked', !!privacyEnabled);
  }
  if (llmBadge) {
    llmBadge.textContent = privacyEnabled ? 'Privacy Mode' : llmEnabled ? 'Qwen' : 'Qwen ปิด';
  }
  if (llmDescription) {
    llmDescription.textContent = privacyEnabled
      ? 'Privacy Mode ปิดการส่งข้อมูลไป LLM ชั่วคราว'
      : llmEnabled
        ? 'ใช้ Qwen ผ่าน Ollama เมื่อหน้า Warning ขอคำอธิบาย'
        : 'ปิดอยู่ ระบบใช้ Rule-base + ML โดยไม่เรียก Qwen';
  }
  if (footer) {
    footer.textContent = privacyEnabled
      ? 'Privacy Mode: Rule-base + visual checks only'
      : llmEnabled
        ? 'Rule-base + ML + Qwen explanation + Feedback'
        : 'Rule-base + ML + Feedback • Qwen ปิด';
  }
}

function renderPrivacyMode(enabled) {
  renderCloudModes(enabled, !!$('llmEnabled')?.checked);
}

function renderStats(scan = {}) {
  $('scanned').textContent = scan.scanned ?? 0;
  $('risky').textContent = scan.risky ?? 0;
  $('high').textContent = scan.high ?? 0;
  const shown = $('shown');
  if (shown) shown.textContent = scan.shown ?? 0;
}

function render(result) {
  currentResult = result;
  const scoreCard = $('scoreCard');
  scoreCard.classList.remove('good', 'warn', 'bad', 'trusted-app');
  const whitelistButton = $('whitelist');
  if (whitelistButton) {
    whitelistButton.disabled = false;
    whitelistButton.textContent = 'เชื่อถือเว็บนี้';
  }

  if (result.trustedWebApp) {
    scoreCard.classList.add('good', 'trusted-app');
    $('host').textContent = result.hostname || 'Phish Radar Web App';
    $('score').textContent = 'APP';
    $('meterFill').style.width = '100%';
    setVerdictState('good');
    $('status').textContent = 'Web App ของ Phish Radar AI';
    $('verdictText').textContent = 'ระบบรู้จัก Origin นี้แบบตรงตัวและจะไม่ส่งเข้าหน้าเตือน แต่ยังตรวจลิงก์ภายนอกที่เปิดจากหน้านี้ตามปกติ';
    $('reasons').innerHTML = '<li>ตรงกับรายการ Domain ของระบบ: protocol + hostname + port</li>';
    if (whitelistButton) {
      whitelistButton.disabled = true;
      whitelistButton.textContent = 'Domain ของระบบ';
    }
    return;
  }

  const cls = colorClass(result.score);
  scoreCard.classList.add(cls);
  $('host').textContent = result.hostname || result.domain || 'unknown';
  $('score').textContent = result.score;
  $('meterFill').style.width = `${result.score}%`;
  const verdictIcon = $('verdictIcon');
  const verdictText = $('verdictText');
  if (verdictIcon) setVerdictState(cls);
  $('status').textContent = `${result.levelText} (${result.score}/100)`;
  if (verdictText) {
    verdictText.textContent = cls === 'good'
      ? 'เว็บไซต์นี้ดูปลอดภัยจาก rule ที่ตรวจตอนนี้ แต่ยังควรระวังก่อนกรอกข้อมูลสำคัญ'
      : cls === 'warn'
        ? 'พบสัญญาณน่าสงสัย เช่น phishing, scam, malware หรือ SEO spam ควรตรวจสอบก่อนเปิดต่อ'
        : 'เสี่ยงสูง ระบบควรบล็อกหรือพาไปหน้า Warning ก่อนเข้าเว็บ';
  }

  const reasons = $('reasons');
  reasons.innerHTML = '';
  const items = result.reasons.length ? result.reasons : [{ points: 0, label: 'ไม่พบสัญญาณเสี่ยงชัดเจน', detail: 'ยังควรตรวจสอบชื่อเว็บก่อนกรอกข้อมูล' }];
  for (const r of items.slice(0, 2)) {
    const li = document.createElement('li');
    li.innerHTML = `${reasonText(r).replace(/&/g, '&amp;').replace(/</g, '&lt;')}`;
    reasons.appendChild(li);
  }
}

function renderManual(url) {
  const r = globalThis.PhishRadarAppTrust?.isTrustedWebAppUrl(url)
    ? globalThis.PhishRadarAppTrust.createTrustedResult(url)
    : PhishRadarAnalyzer.analyzeUrl(url);
  const resultCard = $('manualResult');
  const cls = colorClass(r.score);
  resultCard.classList.remove('good', 'warn', 'bad');
  resultCard.classList.add(cls);
  $('manualDomain').textContent = r.domain || r.hostname || '-';
  $('manualScore').textContent = r.trustedWebApp ? 'APP' : r.score;
  $('manualThreat').textContent = (r.threatTypes || []).join(' / ') || (r.safe ? 'ไม่พบหมวดความเสี่ยง' : r.levelText);
  $('manualSummary').textContent = r.summary || `${r.levelText} (${r.score}/100)`;
  const reasonList = $('manualReasons');
  reasonList.replaceChildren();
  const items = r.reasons?.length
    ? r.reasons.slice(0, 2)
    : [{ label: 'ไม่พบสัญญาณเสี่ยงชัดเจน', detail: 'ตรวจชื่อโดเมนก่อนกรอกข้อมูลสำคัญ' }];
  for (const reason of items) {
    const li = document.createElement('li');
    li.textContent = reasonText(reason);
    reasonList.appendChild(li);
  }
  return r;
}

function extractPotentialUrl(text) {
  const value = String(text || '').trim();
  const match = value.match(/https?:\/\/[^\s<>"']+|(?:[a-z0-9-]+\.)+[a-z]{2,}(?:\/[^\s<>"']*)?/i);
  if (!match) return '';
  const raw = match[0].replace(/[),.;]+$/g, '');
  return /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
}

async function load() {
  await loadPopupTheme();
  const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
  activeTab = tabs[0];
  const settingsRes = await sendMessage({ type: 'GET_SETTINGS' });
  const settings = { ...DEFAULT_SETTINGS, ...(settingsRes.settings || {}) };
  $('threshold').value = settings.threshold;
  $('thresholdText').textContent = `${settings.threshold}`;
  $('highlightLinks').checked = !!settings.highlightLinks;
  $('protectForms').checked = !!settings.protectForms;
  $('showStatusPanel').checked = !!settings.showStatusPanel;
  $('pageScanningEnabled').checked = !!settings.pageScanningEnabled;
  $('searchProtection').checked = !!settings.searchProtection;
  $('clipboardProtection').checked = !!settings.clipboardProtection;
  $('privacyMode').checked = !!settings.privacyMode;
  $('llmEnabled').checked = !!settings.llmEnabled;
  renderPageScanning(settings.pageScanningEnabled);
  renderCloudModes(settings.privacyMode, settings.llmEnabled);

  if (!settings.pageScanningEnabled) {
    if (activeTab?.id && /^https?:/.test(activeTab.url || '')) {
      await ensureContentScript(activeTab.id);
      await sendToTab(activeTab.id, { type: 'SET_PAGE_SCANNING', enabled: false });
    }
    renderManual($('manualUrl').value);
    return;
  }

  if (!activeTab?.url || !/^https?:/.test(activeTab.url)) {
    render(PhishRadarAnalyzer.analyzeUrl('chrome://newtab'));
    $('host').textContent = 'เปิดเว็บ http/https ก่อน';
    renderStats({ scanned: 0, risky: 0, high: 0 });
    renderManual($('manualUrl').value);
    return;
  }

  const result = globalThis.PhishRadarAppTrust?.isTrustedWebAppUrl(activeTab.url)
    ? globalThis.PhishRadarAppTrust.createTrustedResult(activeTab.url)
    : PhishRadarAnalyzer.analyzeUrl(activeTab.url);
  render(result);
  await ensureContentScript(activeTab.id);
  const pageScan = await sendToTab(activeTab.id, { type: 'GET_PAGE_SCAN' });
  if (pageScan?.ok && pageScan.pageResult) render(pageScan.pageResult);
  if (pageScan?.ok && pageScan.linkScan) renderStats(pageScan.linkScan);
  if (!pageScan?.ok) {
    renderStats({ scanned: 0, risky: 0, high: 0, shown: 0 });
    $('status').textContent = `${result.levelText} (${result.score}/100) • กด Reload หน้าเว็บหรือกดสแกนอีกครั้ง`;
  }
  renderManual($('manualUrl').value);
}

$('scanLinks').addEventListener('click', async () => {
  if (!activeTab?.id) return;
  await ensureContentScript(activeTab.id);
  const res = await sendToTab(activeTab.id, { type: 'SCAN_LINKS_NOW' });
  if (!res.ok) return alert('สแกนหน้านี้ไม่ได้ อาจเป็นหน้า chrome:// หรือ extension page\nแนะนำให้ Reload หน้าเว็บ 1 ครั้ง แล้วลองใหม่');
  renderStats(res);
  alert(`สแกนแล้ว ${res.scanned} ลิงก์\nพบลิงก์น่าสงสัย ${res.risky} ลิงก์\nเสี่ยงสูง ${res.high} ลิงก์\nแสดงบนหน้า ${res.shown ?? 0} ลิงก์`);
});

$('openWebApp').addEventListener('click', async () => {
  const res = await sendMessage({ type: 'OPEN_WEB_APP' });
  setToast(res.ok ? 'เปิดหน้าเข้าสู่ระบบแล้ว' : 'เปิดหน้าเข้าสู่ระบบไม่สำเร็จ');
});
$('openQrScanner').addEventListener('click', () => sendMessage({ type: 'OPEN_QR_SCANNER' }));

$('whitelist').addEventListener('click', async () => {
  if (!activeTab?.url || !/^https?:/.test(activeTab.url)) return;
  if (globalThis.PhishRadarAppTrust?.isTrustedWebAppUrl(activeTab.url)) {
    setToast('หน้านี้เป็น Domain ของระบบอยู่แล้ว');
    return;
  }
  const res = await sendMessage({ type: 'ADD_WHITELIST', url: activeTab.url });
  if (res.ok) setToast('เพิ่มเว็บนี้เข้า whitelist แล้ว');
});

$('manualAnalyze').addEventListener('click', () => { renderManual($('manualUrl').value); setToast('วิเคราะห์ URL ตัวอย่างแล้ว'); });
$('manualUrl').addEventListener('keydown', e => { if (e.key === 'Enter') renderManual($('manualUrl').value); });

$('checkClipboard').addEventListener('click', async () => {
  try {
    const text = await navigator.clipboard.readText();
    const url = extractPotentialUrl(text);
    if (!url) {
      setToast('ไม่พบ URL ใน Clipboard');
      return;
    }
    $('manualUrl').value = url;
    const result = renderManual(url);
    if (result.score >= Number($('threshold').value || DEFAULT_SETTINGS.threshold)) {
      setToast('พบ URL เสี่ยงใน Clipboard กำลังเปิดหน้าเตือน');
      await sendMessage({ type: 'OPEN_WARNING', target: url, source: 'clipboard-popup', result, tabId: activeTab?.id });
    } else {
      setToast(`Clipboard ดูค่อนข้างปลอดภัย (${result.score}/100)`);
    }
  } catch (error) {
    setToast('อ่าน Clipboard ไม่ได้ ให้กดอนุญาตหรือวาง URL ในช่องทดสอบเอง');
  }
});

$('threshold').addEventListener('input', e => {
  $('thresholdText').textContent = e.target.value;
});

$('threshold').addEventListener('change', e => sendMessage({ type: 'SET_SETTINGS', settings: { threshold: Number(e.target.value) } }));
$('highlightLinks').addEventListener('change', e => sendMessage({ type: 'SET_SETTINGS', settings: { highlightLinks: e.target.checked } }));
$('protectForms').addEventListener('change', e => sendMessage({ type: 'SET_SETTINGS', settings: { protectForms: e.target.checked } }));
$('showStatusPanel').addEventListener('change', e => sendMessage({ type: 'SET_SETTINGS', settings: { showStatusPanel: e.target.checked } }));
$('pageScanningEnabled').addEventListener('change', async e => {
  const enabled = e.target.checked;
  renderPageScanning(enabled);
  const res = await sendMessage({ type: 'SET_SETTINGS', settings: { pageScanningEnabled: enabled } });
  if (!res.ok) {
    renderPageScanning(!enabled);
    setToast('ยังบันทึกสถานะการสแกนไม่ได้');
    return;
  }
  if (enabled && activeTab?.id && /^https?:/.test(activeTab.url || '')) {
    const result = PhishRadarAnalyzer.analyzeUrl(activeTab.url);
    render(result);
    await ensureContentScript(activeTab.id);
    const pageScan = await sendToTab(activeTab.id, { type: 'GET_PAGE_SCAN' });
    if (pageScan?.pageResult) render(pageScan.pageResult);
    if (pageScan?.linkScan) renderStats(pageScan.linkScan);
  }
  setToast(enabled
    ? 'เปิดการสแกนหน้าเว็บอัตโนมัติแล้ว'
    : 'ปิดการสแกนแล้ว และนำ badge/กล่องแจ้งเตือนออกจากหน้าเว็บ');
});
$('searchProtection').addEventListener('change', e => sendMessage({ type: 'SET_SETTINGS', settings: { searchProtection: e.target.checked } }));
$('clipboardProtection').addEventListener('change', e => sendMessage({ type: 'SET_SETTINGS', settings: { clipboardProtection: e.target.checked } }));
$('llmEnabled').addEventListener('change', async e => {
  const enabled = e.target.checked;
  renderCloudModes(!!$('privacyMode').checked, enabled);
  const res = await sendMessage({ type: 'SET_SETTINGS', settings: { llmEnabled: enabled } });
  if (!res.ok) {
    e.target.checked = !enabled;
    renderCloudModes(!!$('privacyMode').checked, !enabled);
    setToast('ยังบันทึกสถานะ LLM ไม่ได้');
    return;
  }
  setToast(enabled
    ? 'เปิด Qwen แล้ว: หน้า Warning จะขอคำอธิบายผ่าน Ollama'
    : 'ปิด Qwen แล้ว: ระบบจะใช้ Rule-base + ML เท่านั้น');
});

$('privacyMode').addEventListener('change', async e => {
  const enabled = e.target.checked;
  renderCloudModes(enabled, !!$('llmEnabled').checked);
  const res = await sendMessage({ type: 'SET_SETTINGS', settings: { privacyMode: enabled } });
  if (!res.ok) {
    e.target.checked = !enabled;
    renderCloudModes(!enabled, !!$('llmEnabled').checked);
    setToast('ยังบันทึก Privacy Mode ไม่ได้');
    return;
  }
  setToast(enabled
    ? 'เปิด Privacy Mode แล้ว: ไม่ส่ง URL ไป backend/LLM'
    : 'ปิด Privacy Mode แล้ว: ML กลับมาใช้งาน ส่วน LLM ทำตามสวิตช์');
});

load();
