(() => {
  'use strict';

  let settings = { threshold: 61, warnMedium: true, highlightLinks: true, protectForms: true, showStatusPanel: true, pageScanningEnabled: true, privacyMode: false, searchProtection: true, clipboardProtection: true };
  let uiTheme = 'dark';
  let alreadyScanned = false;
  let detailsPinned = false;
  let detailsInteracting = false;
  let suppressDetailsClickUntil = 0;
  let detailCloseTimer = null;
  let lastScan = { scanned: 0, risky: 0, high: 0, medium: 0, shown: 0, mode: 'normal' };
  let linkTooltipEl = null;
  let linkTooltipHideTimer = null;
  let activeTooltipTrigger = null;
  let linkTooltipPinned = false;
  let linkTooltipDragging = false;
  let linkIdCounter = 0;
  let pageScanObserver = null;

  function isTrustedWebAppUrl(value) {
    return !!globalThis.PhishRadarAppTrust?.isTrustedWebAppUrl(value);
  }

  function trustedWebAppResult(value) {
    return globalThis.PhishRadarAppTrust?.createTrustedResult(value)
      || PhishRadarAnalyzer.analyzeUrl(value);
  }

  const SEARCH_HOST_PATTERNS = [
    /(^|\.)google\./i,
    /(^|\.)bing\.com$/i,
    /(^|\.)duckduckgo\.com$/i,
    /(^|\.)yahoo\./i,
    /(^|\.)yandex\./i,
    /(^|\.)baidu\.com$/i
  ];

  const SOCIAL_OR_FEED_HOST_PATTERNS = [
    /(^|\.)facebook\.com$/i,
    /(^|\.)x\.com$/i,
    /(^|\.)twitter\.com$/i,
    /(^|\.)youtube\.com$/i,
    /(^|\.)reddit\.com$/i,
    /(^|\.)tiktok\.com$/i
  ];

  function sendMessage(message) {
    return new Promise(resolve => {
      try {
        chrome.runtime.sendMessage(message, response => resolve(response || { ok: false }));
      } catch (_) {
        resolve({ ok: false });
      }
    });
  }

  async function loadSettings() {
    const res = await sendMessage({ type: 'GET_SETTINGS' });
    if (res?.ok) settings = { ...settings, ...res.settings };
    try {
      const themeData = await chrome.storage.sync.get({ phishRadarTheme: 'dark' });
      uiTheme = themeData.phishRadarTheme === 'dark' ? 'dark' : 'light';
    } catch (_) {
      uiTheme = 'dark';
    }
  }

  function applyUiTheme() {
    const dark = uiTheme === 'dark';
    const theme = dark ? 'dark' : 'light';
    const selector = [
      '#phish-radar-mini-panel',
      '#phish-radar-mini-panel .phish-radar-hover-details',
      '#phish-radar-overlay',
      '#phish-radar-link-tooltip',
      '#phish-radar-clipboard-overlay',
      '#phish-radar-evidence-layer',
      '#phish-radar-evidence-layer .phish-radar-evidence-panel',
      '.phish-radar-safe-preview',
      '.phish-radar-badge'
    ].join(', ');

    document.querySelectorAll(selector).forEach(el => {
      el.classList.toggle('phish-radar-theme-dark', dark);
      el.classList.toggle('phish-radar-theme-light', !dark);
      el.dataset.phishRadarTheme = theme;
    });
  }

  // v2.7 unified theme sync
  try {
    chrome.storage.onChanged.addListener((changes, area) => {
      if (area !== 'sync') return;
      if (changes.phishRadarTheme) {
        uiTheme = changes.phishRadarTheme.newValue === 'dark' ? 'dark' : 'light';
        applyUiTheme();
      }
      if (changes.pageScanningEnabled) {
        void setPageScanningEnabled(changes.pageScanningEnabled.newValue !== false);
      }
    });
  } catch (_) {}

  function shouldSkipUrl(url) {
    return !url || /^(javascript:|mailto:|tel:|#|data:|blob:|chrome:|chrome-extension:|about:)/i.test(url);
  }

  function escapeHtml(str) {
    return String(str || '').replace(/[&<>'"]/g, s => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[s]));
  }


  function compactUrl(value, max = 74) {
    try {
      const u = new URL(value);
      const path = u.pathname && u.pathname !== '/' ? u.pathname : '';
      const query = u.search ? '?…' : '';
      const short = `${u.hostname}${path}${query}`;
      return short.length > max ? short.slice(0, max - 1) + '…' : short;
    } catch (_) {
      const text = String(value || '');
      return text.length > max ? text.slice(0, max - 1) + '…' : text;
    }
  }

  function reasonLine(reason) {
    if (!reason) return '';
    const detail = reason.detail ? `: ${reason.detail}` : '';
    return `${reason.label}${detail}`;
  }

  function extractPotentialUrl(text) {
    const value = String(text || '').trim();
    const match = value.match(/https?:\/\/[^\s<>"']+|(?:[a-z0-9-]+\.)+[a-z]{2,}(?:\/[^\s<>"']*)?/i);
    if (!match) return '';
    const raw = match[0].replace(/[),.;]+$/g, '');
    return /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
  }

  function insertClipboardText(target, text) {
    if (!target) return;
    if ((target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement) && !target.readOnly && !target.disabled) {
      const start = Number.isFinite(target.selectionStart) ? target.selectionStart : target.value.length;
      const end = Number.isFinite(target.selectionEnd) ? target.selectionEnd : start;
      target.setRangeText(text, start, end, 'end');
      target.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste', data: text }));
      return;
    }
    if (target.isContentEditable) {
      target.focus();
      document.execCommand('insertText', false, text);
    }
  }

  function showClipboardProtectionOverlay(url, result, target, text) {
    document.getElementById('phish-radar-clipboard-overlay')?.remove();
    const div = document.createElement('div');
    div.id = 'phish-radar-clipboard-overlay';
    div.setAttribute('role', 'dialog');
    div.setAttribute('aria-modal', 'true');
    div.setAttribute('aria-labelledby', 'phish-radar-clipboard-title');
    div.tabIndex = -1;
    const reasons = (result.reasons || []).slice(0, 4).map(r => `<li>${escapeHtml(reasonLine(r))}</li>`).join('');
    div.innerHTML = `
      <h3 id="phish-radar-clipboard-title">Clipboard Protection</h3>
      <p><b>พบ URL เสี่ยงก่อนวางข้อความ</b></p>
      <code>${escapeHtml(compactUrl(url, 96))}</code>
      <p class="phish-radar-clipboard-score">Risk Score: ${escapeHtml(result.score)}/100 — ${escapeHtml(result.levelText)}</p>
      <ul>${reasons || '<li>URL มีรูปแบบน่าสงสัย</li>'}</ul>
      <div class="phish-radar-actions">
        <button type="button" class="primary" data-action="warning">เปิดหน้าเตือน</button>
        <button type="button" class="secondary" data-action="paste">วางต่อ</button>
        <button type="button" class="secondary" data-action="close">ยกเลิก</button>
      </div>`;
    document.documentElement.appendChild(div);
    applyUiTheme();
    requestAnimationFrame(() => div.focus?.({ preventScroll: true }));
    div.addEventListener('click', async event => {
      const action = event.target?.dataset?.action;
      if (!action) return;
      event.preventDefault();
      if (action === 'warning') {
        await sendMessage({ type: 'OPEN_WARNING', target: url, source: 'clipboard-protection', result });
        div.remove();
        return;
      }
      if (action === 'paste') {
        insertClipboardText(target, text);
        div.remove();
        return;
      }
      if (action === 'close') div.remove();
    });
  }

  function detailTopHtml(title) {
    return `
      <div class="phish-radar-detail-top">
        <div class="phish-radar-detail-head">${title}<span class="phish-radar-drag-cue">ลากเพื่อย้าย</span></div>
        <button type="button" class="phish-radar-detail-reset" data-action="details-reset" title="กลับตำแหน่งเดิม" aria-label="รีเซ็ตตำแหน่งหน้าต่างรายละเอียด">รีเซ็ต</button><button type="button" class="phish-radar-detail-close" data-action="details-close" aria-label="ปิดหน้าต่างรายละเอียด">ปิด</button>
      </div>`;
  }

  function detailWindowHtml(title, body) {
    return `
      ${detailTopHtml(title)}
      <div class="phish-radar-detail-scroll">${body}</div>
      <button type="button" class="phish-radar-window-resize" data-action="details-resize" title="ลากเพื่อขยายหรือย่อหน้าต่าง" aria-label="ปรับขนาดหน้าต่างรายละเอียด">↘</button>`;
  }

  function buildHoverDetails(scan) {
    const modeText = scan.mode === 'search'
      ? 'Search Mode: ตรวจปลายทางจริง + บริบทผลค้นหา เช่น phishing, malware, scam, SEO spam'
      : 'Normal Mode: ตรวจลิงก์และเนื้อหาเสี่ยงที่มองเห็นในหน้าเว็บ';
    const privacyText = settings.privacyMode ? ' • Privacy Mode: ไม่ส่ง URL ไป backend/LLM' : '';

    const isSearch = scan?.mode === 'search';
    const displayItems = isSearch
      ? (scan.items || []).filter(item => item.visuallyShown || item.score >= 61).slice(0, 5)
      : (scan.items || []).slice(0, 5);
    const hasVisibleRisk = isSearch ? displayItems.length > 0 : !!scan?.risky;

    if (!scan || !hasVisibleRisk) {
      return detailWindowHtml('รายละเอียดการตรวจ', `
        <div class="phish-radar-detail-row"><b>สถานะ:</b> ${isSearch ? 'ไม่พบลิงก์เสี่ยงสูงที่ควรเตือนบนหน้าค้นหา' : 'ไม่พบลิงก์เสี่ยงในหน้านี้'}</div>
        <div class="phish-radar-detail-row"><b>จำนวนที่สแกน:</b> ${escapeHtml(scan?.scanned ?? 0)} ลิงก์</div>
        ${isSearch && scan?.risky ? `<div class="phish-radar-detail-note">พบรายการเฝ้าระวัง ${escapeHtml(scan.risky)} รายการ แต่ยังไม่ถึงระดับที่ควรแสดงเตือนบนหน้า เพื่อไม่ให้รบกวนผู้ใช้หรือเกิด false positive</div>` : ''}
        <div class="phish-radar-detail-note">${escapeHtml(modeText + privacyText)}</div>
      `);
    }

    const list = displayItems.length ? displayItems.map((item, index) => {
      const reasons = (item.reasons || []).slice(0, 3).map(r => `<li>${escapeHtml(reasonLine(r))}</li>`).join('');
      const levelIcon = item.score >= 81 ? '🚫' : item.score >= 61 ? '⛔' : '⚠️';
      const actionButtons = item.linkId ? `
        <div class="phish-radar-detail-actions">
          <button type="button" data-action="scroll-link" data-target-id="${escapeHtml(item.linkId)}">ชี้ตำแหน่งบนหน้า</button>
          <button type="button" data-action="warning-link" data-url="${escapeHtml(item.url)}">เปิดหน้าเตือน</button>
          <button type="button" data-action="copy-url" data-url="${escapeHtml(item.url)}">คัดลอก URL</button>
        </div>` : '';
      return `
        <div class="phish-radar-detail-item" data-item-id="${escapeHtml(item.linkId || '')}">
          <div class="phish-radar-detail-url">${levelIcon} <b>${escapeHtml(item.score)}/100</b> ${escapeHtml(compactUrl(item.url, 68))}</div>
          <ul>${reasons || '<li>พบรูปแบบ URL ที่น่าสงสัย</li>'}</ul>
          ${actionButtons}
        </div>
      `;
    }).join('') : '<div class="phish-radar-detail-note">พบความเสี่ยง แต่ไม่มีรายการที่แสดงบนหน้าเว็บ</div>';

    return detailWindowHtml('รายละเอียดที่ตรวจพบ', `
      <div class="phish-radar-detail-row"><b>สรุป:</b> เสี่ยงสูง ${escapeHtml(scan.high)} รายการ • น่าสงสัย ${escapeHtml(scan.medium)} รายการ</div>
      <div class="phish-radar-detail-row"><b>สแกนแล้ว:</b> ${escapeHtml(scan.scanned)} ลิงก์ • แสดงบนหน้า ${escapeHtml(scan.shown)} รายการ</div>
      <div class="phish-radar-detail-note">${escapeHtml(modeText + privacyText)}</div>
      ${list}
    `);
  }

    function hostMatches(hostname, patterns) {
    return patterns.some(re => re.test(String(hostname || '')));
  }

  function currentPageMode() {
    const host = location.hostname || '';
    const path = location.pathname || '';
    const isSearch = hostMatches(host, SEARCH_HOST_PATTERNS) && (
      /\/search/i.test(path) || location.search.includes('q=') || location.search.includes('query=') || host.includes('duckduckgo')
    );
    if (isSearch) return 'search';
    if (hostMatches(host, SOCIAL_OR_FEED_HOST_PATTERNS)) return 'feed';
    return 'normal';
  }

  function sameOrSubdomain(host, parent) {
    host = String(host || '').replace(/^www\./, '').toLowerCase();
    parent = String(parent || '').replace(/^www\./, '').toLowerCase();
    return host === parent || host.endsWith('.' + parent);
  }

  function tryUrl(value, base = location.href) {
    try { return new URL(value, base); } catch (_) { return null; }
  }

  function nestedUrlFromParams(url) {
    const redirectKeys = [
      'url', 'u', 'q', 'r', 'redirect', 'redirect_uri', 'next', 'target', 'to',
      'continue', 'return', 'returnurl', 'dest', 'destination', 'adurl'
    ];
    for (const key of redirectKeys) {
      const value = url.searchParams.get(key);
      if (!value || !/^https?:\/\//i.test(value)) continue;
      const nested = tryUrl(value);
      if (nested && nested.hostname && nested.hostname !== url.hostname) return nested;
    }
    return null;
  }

  function resolveEffectiveUrl(rawHref) {
    const original = tryUrl(rawHref);
    if (!original) return null;

    // Google/Bing/search engines often wrap real links with long redirect URLs.
    // Analyze the real destination instead of the wrapper to avoid false positives
    // from tracking parameters such as ved/ei/usg/q.
    const nested = nestedUrlFromParams(original);
    if (nested) {
      return {
        originalUrl: original.href,
        effectiveUrl: nested.href,
        wasRedirectWrapper: true
      };
    }

    return {
      originalUrl: original.href,
      effectiveUrl: original.href,
      wasRedirectWrapper: false
    };
  }

  function isElementVisible(el) {
    if (!el || !el.getClientRects || el.getClientRects().length === 0) return false;
    const rect = el.getBoundingClientRect();
    if (rect.width < 6 || rect.height < 6) return false;
    const style = getComputedStyle(el);
    return style.visibility !== 'hidden' && style.display !== 'none' && Number(style.opacity || 1) > 0.05;
  }

  function trimmedOwnText(a, mode) {
    const raw = [a.innerText, a.textContent, a.title, a.getAttribute('aria-label')]
      .filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();

    // On search result pages, anchors can contain title + snippet + visible URL.
    // Passing the whole text to the phishing engine causes false positives.
    if (mode === 'search' || mode === 'feed') {
      return raw.length <= 120 ? raw : '';
    }
    return raw.slice(0, 400);
  }

  function searchResultContextText(a, mode) {
    if (mode !== 'search') return '';
    const selectors = [
      'div.MjjYud', 'div.g', '[data-sokoban-container]', '[data-hveid]', 'article', 'section'
    ];
    let box = null;
    for (const selector of selectors) {
      box = a.closest(selector);
      if (box && box !== document.body && box !== document.documentElement) break;
      box = null;
    }
    const text = [box?.innerText, a.innerText, a.title, a.getAttribute('aria-label')]
      .filter(Boolean)
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
    // Keep enough context for SEO-spam detection, but not the whole page.
    return text.slice(0, 900);
  }

  function linkOptions(a, resolved, mode) {
    const rel = (a.getAttribute('rel') || '').toLowerCase();
    return {
      linkText: trimmedOwnText(a, mode),
      searchContextText: searchResultContextText(a, mode),
      ignoreLinkText: mode === 'search',
      opensNewTabNoNoopener: a.target === '_blank' && !rel.includes('noopener'),
      wasRedirectWrapper: !!resolved?.wasRedirectWrapper,
      originalUrl: resolved?.originalUrl || ''
    };
  }

  function formIssuesForPage() {
    const issues = [];
    const currentHost = location.hostname;
    const forms = Array.from(document.forms || []).slice(0, 10);
    for (const form of forms) {
      const hasSecret = !!form.querySelector('input[type="password"], input[name*="otp" i], input[name*="token" i], input[name*="pin" i], input[name*="card" i], input[name*="cvv" i]');
      if (!hasSecret) continue;

      const rawAction = form.getAttribute('action') || '';
      let actionUrl = null;
      try { actionUrl = new URL(rawAction || location.href, location.href); } catch (_) {}

      if (!rawAction) {
        issues.push({ points: 4, label: 'ฟอร์มรับข้อมูลสำคัญไม่มี action ชัดเจน', detail: 'ใช้ปลายทางเดียวกับหน้าเว็บ' });
      }

      if (actionUrl) {
        if (actionUrl.protocol === 'http:') {
          issues.push({ points: 18, label: 'ฟอร์มส่งข้อมูลผ่าน HTTP', detail: actionUrl.href });
        }
        if (actionUrl.hostname && actionUrl.hostname !== currentHost && !actionUrl.hostname.endsWith('.' + currentHost)) {
          issues.push({ points: 22, label: 'ฟอร์มส่งข้อมูลไปคนละโดเมน', detail: `${currentHost} → ${actionUrl.hostname}` });
        }
      }

      const autocompleteOff = form.getAttribute('autocomplete') === 'off' || !!form.querySelector('[autocomplete="off"]');
      if (autocompleteOff) {
        issues.push({ points: 4, label: 'ฟอร์มปิด autocomplete', detail: 'ไม่ใช่หลักฐาน phishing โดยตรง แต่พบร่วมกับหน้า login ปลอมได้' });
      }

      const hiddenCount = form.querySelectorAll('input[type="hidden"]').length;
      if (hiddenCount >= 5) {
        issues.push({ points: 5, label: 'ฟอร์มมี hidden input จำนวนมาก', detail: `${hiddenCount} ช่อง` });
      }
    }
    return issues;
  }



  // v2.1: Visual phishing detection. This looks at visible brand cues on the
  // page, not only the URL: logos, headings, login buttons, placeholders, and
  // credential fields. It is intentionally local so it does not spend LLM tokens.
  function normalizeVisualText(value) {
    return String(value || '')
      .toLowerCase()
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9ก-๙@._ -]/gi, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function visualBrandNames(profile) {
    return [profile?.brand, ...(profile?.aliases || [])]
      .filter(Boolean)
      .map(name => String(name).toLowerCase())
      .filter(name => name.length >= 3 && !['line'].includes(name));
  }

  function visualTextMatchesBrand(text, profile) {
    const normalized = normalizeVisualText(text);
    if (!normalized) return null;
    return visualBrandNames(profile).find(name => normalized.includes(normalizeVisualText(name))) || null;
  }

  function visualElementText(el) {
    if (!el) return '';
    const src = el.getAttribute?.('src') || '';
    const href = el.getAttribute?.('href') || '';
    let srcHost = '';
    try { srcHost = src ? new URL(src, location.href).hostname : ''; } catch (_) {}
    return [
      el.innerText,
      el.textContent,
      el.value,
      el.alt,
      el.placeholder,
      el.getAttribute?.('aria-label'),
      el.getAttribute?.('title'),
      el.getAttribute?.('name'),
      el.getAttribute?.('id'),
      el.getAttribute?.('class'),
      src,
      srcHost,
      href
    ].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
  }

  function isOfficialBrandHost(profile, host = location.hostname) {
    return (profile?.officialDomains || []).some(domain => sameOrSubdomain(host, domain));
  }

  function findVisualBrandTargets(profile) {
    const targets = [];
    const selectors = [
      'img[alt]',
      'img[src]',
      'svg[aria-label]',
      '[class*="logo" i]',
      '[id*="logo" i]',
      '[class*="brand" i]',
      '[id*="brand" i]',
      'h1',
      'h2',
      '[role="heading"]',
      'button',
      'input[placeholder]',
      'label',
      'a[aria-label]',
      '[title]'
    ].join(', ');

    const nodes = Array.from(document.querySelectorAll(selectors))
      .filter(el => !isPhishRadarUiNode(el) && isElementVisible(el))
      .slice(0, 180);

    for (const el of nodes) {
      const raw = visualElementText(el);
      const matched = visualTextMatchesBrand(raw, profile);
      if (!matched) continue;
      const tag = (el.tagName || '').toLowerCase();
      const isLogoLike = tag === 'img' || tag === 'svg' || /logo|brand/i.test(el.className || '') || /logo|brand/i.test(el.id || '');
      const isHeadingLike = /^(h1|h2)$/i.test(tag) || el.getAttribute('role') === 'heading';
      const isActionLike = /button|submit|login|sign|verify|continue|เข้าสู่ระบบ|ลงชื่อ|ยืนยัน/i.test(raw);
      targets.push({ el, matched, raw: raw.slice(0, 160), isLogoLike, isHeadingLike, isActionLike });
    }

    return targets;
  }

  function visualLoginActionCount() {
    return Array.from(document.querySelectorAll(PAGE_EVIDENCE_ACTION_SELECTOR))
      .filter(el => !isPhishRadarUiNode(el) && isElementVisible(el))
      .filter(el => PAGE_EVIDENCE_ACTION_RE.test(evidenceTextForElement(el)))
      .slice(0, 8).length;
  }

  function collectVisualPhishingSignals() {
    const profiles = PhishRadarAnalyzer?.BRAND_PROFILES || [];
    const passwordCount = document.querySelectorAll('input[type="password"]').length;
    const secretCount = document.querySelectorAll(PAGE_EVIDENCE_SECRET_SELECTOR).length;
    const loginActionCount = visualLoginActionCount();
    const pageTitle = document.title || '';
    const findings = [];

    for (const profile of profiles) {
      if (isOfficialBrandHost(profile)) continue;
      const targets = findVisualBrandTargets(profile);
      const titleMatch = visualTextMatchesBrand(pageTitle, profile);
      if (!targets.length && !titleMatch) continue;

      const logoTarget = targets.find(item => item.isLogoLike);
      const headingTarget = targets.find(item => item.isHeadingLike);
      const actionTarget = targets.find(item => item.isActionLike);
      const hasCredentialSurface = secretCount > 0 || passwordCount > 0 || loginActionCount > 0;
      const hasStrongBrandCue = !!(logoTarget || headingTarget || titleMatch);
      if (!hasStrongBrandCue || !hasCredentialSurface) continue;

      const signals = [];
      if (logoTarget) signals.push('logo/brand asset');
      if (headingTarget || titleMatch) signals.push('brand heading/title');
      if (passwordCount) signals.push('password field');
      if (loginActionCount) signals.push('login/verify button');

      const points = Math.min(34, 16 + (logoTarget ? 8 : 0) + (headingTarget || titleMatch ? 5 : 0) + (passwordCount ? 7 : 0) + (loginActionCount ? 4 : 0));
      const target = logoTarget?.el || headingTarget?.el || actionTarget?.el || targets[0]?.el || null;
      findings.push({
        brand: profile.brand,
        points,
        confidence: points >= 30 ? 'high' : 'medium',
        signals,
        detail: 'พบสัญญาณหน้าตาเว็บคล้าย ' + profile.brand + ' แต่โดเมนคือ ' + location.hostname,
        target,
        sample: (logoTarget || headingTarget || actionTarget || targets[0])?.raw || pageTitle
      });
    }

    return findings.sort((a, b) => b.points - a.points).slice(0, 4);
  }

  function visualFindingForAnalyzer(finding) {
    return {
      brand: finding.brand,
      points: finding.points,
      confidence: finding.confidence,
      signals: finding.signals,
      detail: finding.detail,
      sample: finding.sample
    };
  }
  function pageRiskOptions(extra = {}) {
    const bodyText = document.body ? document.body.innerText : '';
    const passwordFieldCount = document.querySelectorAll('input[type="password"]').length;
    const otpFieldCount = document.querySelectorAll('input[name*="otp" i], input[name*="token" i], input[name*="pin" i], input[autocomplete="one-time-code"]').length;
    const visualFindings = collectVisualPhishingSignals();
    return {
      pageHasPasswordForm: passwordFieldCount > 0,
      passwordFieldCount,
      otpFieldCount,
      pageText: bodyText,
      documentTitle: document.title || '',
      formIssues: formIssuesForPage(),
      visualFindings: visualFindings.map(visualFindingForAnalyzer),
      ...extra
    };
  }



  // v2.0: Explainable Warning evidence layer. It turns analyzer reasons into
  // visible proof on the page, so users can see what the warning is based on.
  let evidenceLayerEl = null;
  let evidencePositionFrame = 0;
  let evidenceListenersReady = false;
  let pageEvidenceState = { items: [] };

  const PAGE_EVIDENCE_SECRET_SELECTOR = [
    'input[type="password"]',
    'input[name*="otp" i]',
    'input[name*="token" i]',
    'input[name*="pin" i]',
    'input[name*="card" i]',
    'input[name*="cvv" i]',
    'input[autocomplete="one-time-code"]',
    'textarea[name*="seed" i]',
    'textarea[name*="recovery" i]'
  ].join(', ');

  const PAGE_EVIDENCE_ACTION_SELECTOR = [
    'button',
    'input[type="submit"]',
    'input[type="button"]',
    'a[href]',
    '[role="button"]'
  ].join(', ');

  const PAGE_EVIDENCE_ACTION_RE = /(login|log in|signin|sign in|verify|verification|confirm|continue|submit|claim|reward|download|update|unlock|recover|reset|allow|connect|wallet|pay|payment|otp|password|เข้าสู่ระบบ|ลงชื่อ|ยืนยัน|ตรวจสอบ|ดำเนินการต่อ|รับสิทธิ์|ดาวน์โหลด|อัปเดต|กู้คืน|ปลดล็อก|เชื่อมต่อ|กระเป๋า|ชำระ|โอน|รหัสผ่าน|โอทีพี)/i;

  function evidenceTextForElement(el) {
    if (!el) return '';
    return [
      el.innerText,
      el.value,
      el.getAttribute?.('aria-label'),
      el.getAttribute?.('title'),
      el.getAttribute?.('placeholder'),
      el.getAttribute?.('name')
    ].filter(Boolean).join(' ').replace(/\s+/g, ' ').trim();
  }

  function evidenceFieldLabel(el) {
    const raw = [
      el?.type,
      el?.name,
      el?.id,
      el?.autocomplete,
      el?.placeholder
    ].filter(Boolean).join(' ').toLowerCase();
    if (/otp|token|pin|one-time/.test(raw)) return 'ช่องกรอก OTP/Token ตรงนี้เสี่ยง';
    if (/card|cvv|credit/.test(raw)) return 'ช่องกรอกข้อมูลบัตรตรงนี้เสี่ยง';
    if (/seed|recovery|private/.test(raw)) return 'ช่องกรอก seed phrase/recovery phrase ตรงนี้เสี่ยงมาก';
    return 'ช่องกรอกรหัสผ่านตรงนี้เสี่ยง';
  }

  function evidenceReason(result, categories, fallback) {
    const reason = (result?.reasons || []).find(r => categories.includes(r.category) && r.points > 0);
    return reason ? reasonLine(reason) : fallback;
  }

  function addEvidence(items, usedElements, item) {
    if (!item) return;
    if (item.target) {
      if (usedElements.has(item.target)) return;
      usedElements.add(item.target);
    }
    items.push({
      id: `pr-evidence-${items.length + 1}`,
      kind: item.kind || 'general',
      label: item.label || 'พบจุดเสี่ยงบนหน้าเว็บ',
      detail: item.detail || '',
      target: item.target || null
    });
  }

  function collectPageEvidence(result) {
    const items = [];
    const usedElements = new Set();
    const reasons = result?.reasons || [];
    const hasPositive = reasons.some(r => r.points > 0);
    if (!hasPositive && Number(result?.score || 0) < 31) return items;

    const domainReason = reasons.find(r => ['brand', 'homograph', 'domain', 'transport', 'combo'].includes(r.category) && r.points > 0);
    if (domainReason) {
      addEvidence(items, usedElements, {
        kind: 'domain',
        label: domainReason.category === 'brand'
          ? 'โดเมนนี้มีลักษณะเลียนแบบแบรนด์'
          : 'โดเมน/URL มีรูปแบบผิดปกติ',
        detail: reasonLine(domainReason) || location.hostname
      });
    }

    const visualFindings = collectVisualPhishingSignals();
    for (const finding of visualFindings.slice(0, 4)) {
      addEvidence(items, usedElements, {
        kind: 'visual',
        label: 'หน้าตาเว็บเลียนแบบ ' + finding.brand,
        detail: finding.detail + (finding.signals?.length ? ' (' + finding.signals.join(', ') + ')' : ''),
        target: finding.target
      });
    }

    const secretFields = Array.from(document.querySelectorAll(PAGE_EVIDENCE_SECRET_SELECTOR))
      .filter(el => !isPhishRadarUiNode(el) && isElementVisible(el))
      .slice(0, 5);
    for (const field of secretFields) {
      addEvidence(items, usedElements, {
        kind: /seed|recovery/i.test(evidenceTextForElement(field)) ? 'critical' : 'secret',
        label: evidenceFieldLabel(field),
        detail: evidenceReason(result, ['form', 'credential', 'combo'], 'หน้าเว็บนี้ขอข้อมูลสำคัญบนโดเมนที่มีสัญญาณผิดปกติ'),
        target: field
      });
    }

    const forms = Array.from(document.forms || []).filter(form => !isPhishRadarUiNode(form) && form.querySelector(PAGE_EVIDENCE_SECRET_SELECTOR));
    for (const form of forms.slice(0, 3)) {
      const rawAction = form.getAttribute('action') || '';
      let actionUrl = null;
      try { actionUrl = new URL(rawAction || location.href, location.href); } catch (_) {}
      if (actionUrl && actionUrl.hostname && actionUrl.hostname !== location.hostname && !actionUrl.hostname.endsWith('.' + location.hostname)) {
        const target = form.querySelector('button, input[type="submit"], input[type="button"]') || form;
        addEvidence(items, usedElements, {
          kind: 'form',
          label: 'ฟอร์มนี้ส่งข้อมูลไปคนละโดเมน',
          detail: `${location.hostname} -> ${actionUrl.hostname}`,
          target
        });
      }
    }

    const actionElements = Array.from(document.querySelectorAll(PAGE_EVIDENCE_ACTION_SELECTOR))
      .filter(el => !isPhishRadarUiNode(el) && isElementVisible(el))
      .filter(el => PAGE_EVIDENCE_ACTION_RE.test(evidenceTextForElement(el)))
      .slice(0, 6);
    for (const action of actionElements) {
      addEvidence(items, usedElements, {
        kind: 'action',
        label: 'ปุ่ม/ลิงก์นี้ชวนให้ทำรายการบนหน้าเสี่ยง',
        detail: evidenceTextForElement(action).slice(0, 120) || evidenceReason(result, ['keyword', 'page-context', 'brand'], 'พบคำชวนให้ล็อกอิน ยืนยัน หรือกรอกข้อมูล'),
        target: action
      });
    }

    const markedLinks = Array.from(document.querySelectorAll('a.phish-radar-link-target.phish-radar-high'))
      .filter(el => !isPhishRadarUiNode(el) && isElementVisible(el))
      .slice(0, 3);
    for (const link of markedLinks) {
      addEvidence(items, usedElements, {
        kind: 'link',
        label: 'ลิงก์นี้ถูกตรวจว่าเสี่ยงสูง',
        detail: link.dataset.phishRadarReasons || 'รูปแบบลิงก์หรือปลายทางมีความผิดปกติ',
        target: link
      });
    }

    return items.slice(0, 8);
  }

  function clearPageEvidence() {
    for (const item of pageEvidenceState.items || []) {
      if (!item.target?.classList) continue;
      item.target.classList.remove(
        'phish-radar-evidence-target',
        'phish-radar-evidence-secret-target',
        'phish-radar-evidence-action-target',
        'phish-radar-evidence-form-target',
        'phish-radar-evidence-critical-target',
        'phish-radar-evidence-visual-target',
        'phish-radar-evidence-flash'
      );
      delete item.target.dataset.phishRadarEvidenceId;
    }
    pageEvidenceState = { items: [] };
    evidenceLayerEl?.remove();
    evidenceLayerEl = null;
  }

  function evidenceKindClass(kind) {
    if (kind === 'secret') return 'phish-radar-evidence-secret-target';
    if (kind === 'critical') return 'phish-radar-evidence-critical-target';
    if (kind === 'action' || kind === 'link') return 'phish-radar-evidence-action-target';
    if (kind === 'form') return 'phish-radar-evidence-form-target';
    if (kind === 'visual') return 'phish-radar-evidence-visual-target';
    return '';
  }

  function ensureEvidenceListeners() {
    if (evidenceListenersReady) return;
    evidenceListenersReady = true;
    window.addEventListener('scroll', schedulePageEvidencePosition, true);
    window.addEventListener('resize', schedulePageEvidencePosition);
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && evidenceLayerEl) clearPageEvidence();
    }, true);
  }

  function renderPageEvidence(result) {
    const items = collectPageEvidence(result);
    clearPageEvidence();
    ensureEvidenceListeners();

    const layer = document.createElement('div');
    layer.id = 'phish-radar-evidence-layer';
    layer.setAttribute('role', 'region');
    layer.setAttribute('aria-label', 'Phish Radar evidence highlights');

    const list = items.length ? items.map((item, index) => `
      <button type="button" class="phish-radar-evidence-list-item" data-evidence-jump="${escapeHtml(item.id)}">
        <b>${index + 1}. ${escapeHtml(item.label)}</b>
        <span>${escapeHtml(item.detail || 'คลิกเพื่อชี้ตำแหน่งบนหน้า')}</span>
      </button>
    `).join('') : `
      <div class="phish-radar-evidence-empty">ยังไม่พบจุดบนหน้าเว็บที่ชี้ได้ชัดเจน แต่ URL/บริบทของหน้ายังมีความเสี่ยง</div>
    `;

    layer.innerHTML = `
      <div class="phish-radar-evidence-panel" tabindex="-1">
        <div class="phish-radar-evidence-panel-top">
          <div>
            <strong>หลักฐานที่ตรวจพบบนหน้า</strong>
            <small>${items.length ? `พบ ${items.length} จุดที่ควรตรวจสอบ` : 'ไม่มีตำแหน่งชี้ชัดบนหน้า'}</small>
          </div>
          <button type="button" data-evidence-close aria-label="ปิดหลักฐานบนหน้า">x</button>
        </div>
        <div class="phish-radar-evidence-list">${list}</div>
      </div>
    `;

    document.documentElement.appendChild(layer);
    evidenceLayerEl = layer;
    pageEvidenceState = { items };

    items.forEach((item, index) => {
      if (!item.target?.classList) return;
      item.target.dataset.phishRadarEvidenceId = item.id;
      item.target.classList.add('phish-radar-evidence-target');
      const kindClass = evidenceKindClass(item.kind);
      if (kindClass) item.target.classList.add(kindClass);

      const marker = document.createElement('button');
      marker.type = 'button';
      marker.className = `phish-radar-evidence-marker phish-radar-evidence-marker-${escapeHtml(item.kind)}`;
      marker.dataset.evidenceMarker = item.id;
      marker.innerHTML = `<span>${index + 1}</span>${escapeHtml(item.label)}`;
      layer.appendChild(marker);
    });

    layer.addEventListener('click', e => {
      if (e.target?.closest?.('[data-evidence-close]')) {
        e.preventDefault();
        clearPageEvidence();
        return;
      }
      const marker = e.target?.closest?.('[data-evidence-marker]');
      const listButton = e.target?.closest?.('[data-evidence-jump]');
      const id = marker?.dataset?.evidenceMarker || listButton?.dataset?.evidenceJump;
      if (id) {
        e.preventDefault();
        focusPageEvidence(id);
      }
    });

    requestAnimationFrame(() => {
      schedulePageEvidencePosition();
      layer.querySelector('.phish-radar-evidence-panel')?.focus({ preventScroll: true });
    });
  }

  function focusPageEvidence(id) {
    const item = (pageEvidenceState.items || []).find(entry => entry.id === id);
    if (!item?.target) return;
    item.target.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
    item.target.classList.add('phish-radar-evidence-flash');
    setTimeout(() => item.target?.classList?.remove('phish-radar-evidence-flash'), 1500);
    schedulePageEvidencePosition();
  }

  function schedulePageEvidencePosition() {
    if (!evidenceLayerEl) return;
    if (evidencePositionFrame) cancelAnimationFrame(evidencePositionFrame);
    evidencePositionFrame = requestAnimationFrame(() => {
      evidencePositionFrame = 0;
      positionPageEvidenceMarkers();
    });
  }

  function positionPageEvidenceMarkers() {
    if (!evidenceLayerEl) return;
    for (const marker of evidenceLayerEl.querySelectorAll('[data-evidence-marker]')) {
      const item = (pageEvidenceState.items || []).find(entry => entry.id === marker.dataset.evidenceMarker);
      if (!item?.target?.getBoundingClientRect || !isElementVisible(item.target)) {
        marker.style.display = 'none';
        continue;
      }

      const rect = item.target.getBoundingClientRect();
      const markerRect = marker.getBoundingClientRect();
      const margin = 10;
      const topAbove = rect.top - markerRect.height - 8;
      const top = topAbove > margin ? topAbove : Math.min(rect.bottom + 8, window.innerHeight - markerRect.height - margin);
      let left = rect.left;
      if (rect.width > 90) left = rect.left + Math.min(18, rect.width / 3);
      left = Math.max(margin, Math.min(left, window.innerWidth - markerRect.width - margin));

      marker.style.display = 'inline-flex';
      marker.style.left = `${left}px`;
      marker.style.top = `${Math.max(margin, top)}px`;
    }
  }


  function buildLinkTooltipHtml(data) {
    const result = data?.result || {};
    const reasons = (result.reasons || []).slice(0, 4).map(r => `
      <li><b>${escapeHtml(r.label)}</b>${r.detail ? `<br><small>${escapeHtml(r.detail)}</small>` : ''}</li>
    `).join('');
    const icon = result.score >= 81 ? '🚫' : result.score >= 61 ? '⛔' : '⚠️';
    const level = result.levelText || (result.score >= 61 ? 'เสี่ยงสูง' : 'น่าสงสัย');
    const threatTypes = Array.isArray(result.threatTypes) && result.threatTypes.length
      ? `<div class="phish-radar-link-tooltip-mini"><b>กลุ่มความเสี่ยง:</b> ${escapeHtml(result.threatTypes.join(' • '))}</div>`
      : '';
    const urlText = compactUrl(data?.url || result.url || '', 90);
    const original = data?.wasRedirectWrapper && data?.originalUrl
      ? `<div class="phish-radar-link-tooltip-mini">ปลายทางจริงจาก redirect: ${escapeHtml(compactUrl(data.originalUrl, 80))}</div>`
      : '';

    return `
      <div class="phish-radar-link-tooltip-top" data-role="tooltip-drag" title="ลากแถบนี้เพื่อย้ายหน้าต่าง">
        <div class="phish-radar-link-tooltip-title">${icon} ลิงก์นี้${escapeHtml(level)}<span class="phish-radar-drag-cue">ลากเพื่อย้าย</span></div>
        <button type="button" class="phish-radar-link-tooltip-close" data-tooltip-action="close" title="ปิดหน้าต่างรายละเอียด" aria-label="ปิดหน้าต่างรายละเอียด">×</button>
      </div>
      <div class="phish-radar-link-tooltip-scroll" data-role="tooltip-scroll">
        <div class="phish-radar-link-tooltip-score">Risk Score: <b>${escapeHtml(result.score ?? '-')}</b>/100</div>
        <div class="phish-radar-link-tooltip-url">${escapeHtml(urlText)}</div>
        ${threatTypes}
        ${original}
        <ul>${reasons || '<li>พบรูปแบบ URL ที่น่าสงสัย</li>'}</ul>
        <div class="phish-radar-link-tooltip-footer">ลากหัวหน้าต่างเพื่อย้ายตำแหน่ง • ระบบจะเตือนก่อนเปิดเว็บ</div>
      </div>
      <button type="button" class="phish-radar-tooltip-resize" data-tooltip-action="resize" title="ลากมุมนี้เพื่อขยายหรือย่อหน้าต่าง" aria-label="ปรับขนาดหน้าต่างรายละเอียด">↘</button>
    `;
  }

  function ensureLinkTooltip() {
    if (linkTooltipEl && document.documentElement.contains(linkTooltipEl)) return linkTooltipEl;
    linkTooltipEl = document.createElement('div');
    linkTooltipEl.id = 'phish-radar-link-tooltip';
    linkTooltipEl.setAttribute('role', 'tooltip');
    document.documentElement.appendChild(linkTooltipEl);
    applyUiTheme();
    linkTooltipEl.addEventListener('mouseenter', () => clearTimeout(linkTooltipHideTimer));
    linkTooltipEl.addEventListener('mouseleave', hideLinkTooltipSoon);
    linkTooltipEl.addEventListener('click', e => {
      if (e.target?.dataset?.tooltipAction === 'close') {
        e.preventDefault();
        e.stopPropagation();
        closeLinkTooltip();
      }
    });
    enableDraggableLinkTooltip(linkTooltipEl);
    return linkTooltipEl;
  }

  let linkTooltipPositionFrame = 0;
  function scheduleLinkTooltipPosition(trigger) {
    if (linkTooltipPositionFrame) cancelAnimationFrame(linkTooltipPositionFrame);
    linkTooltipPositionFrame = requestAnimationFrame(() => {
      linkTooltipPositionFrame = 0;
      positionLinkTooltip(trigger);
    });
  }

  function positionLinkTooltip(trigger) {
    if (!linkTooltipEl || !trigger?.getBoundingClientRect) return;
    if (linkTooltipDragging || linkTooltipEl.classList.contains('phish-radar-link-tooltip-manual')) return;

    const rect = trigger.getBoundingClientRect();
    const tipRect = linkTooltipEl.getBoundingClientRect();
    const gap = 10;
    const margin = 14;
    const viewportWidth = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    const viewportHeight = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
    const maxWidth = Math.max(240, viewportWidth - margin * 2);
    const preferredWidth = Math.min(360, maxWidth);
    const minReadableWidth = Math.min(320, maxWidth);
    const nextWidth = clampNumber(tipRect.width || preferredWidth, minReadableWidth, maxWidth);

    linkTooltipEl.style.setProperty('width', `${nextWidth}px`, 'important');
    linkTooltipEl.style.setProperty('max-width', `${maxWidth}px`, 'important');
    linkTooltipEl.style.setProperty('max-height', `${Math.max(180, viewportHeight - margin * 2)}px`, 'important');

    const width = nextWidth;
    const height = Math.min(tipRect.height || 220, Math.max(180, viewportHeight - margin * 2));
    let top = rect.top - height - gap;
    if (top < margin) top = rect.bottom + gap;
    top = clampNumber(top, margin, Math.max(margin, viewportHeight - height - margin));

    let left = rect.left + Math.min(22, Math.max(0, rect.width / 2)) - 24;
    left = clampNumber(left, margin, Math.max(margin, viewportWidth - width - margin));

    linkTooltipEl.style.setProperty('top', `${top}px`, 'important');
    linkTooltipEl.style.setProperty('left', `${left}px`, 'important');
    linkTooltipEl.style.setProperty('right', 'auto', 'important');
    linkTooltipEl.style.setProperty('bottom', 'auto', 'important');
  }

  function showLinkTooltip(trigger) {
    if (!settings.pageScanningEnabled) return;
    const dataRaw = trigger?.dataset?.phishRadarTooltip;
    if (!dataRaw) return;
    let data;
    try { data = JSON.parse(dataRaw); } catch (_) { return; }
    clearTimeout(linkTooltipHideTimer);
    activeTooltipTrigger = trigger;
    const tip = ensureLinkTooltip();
    const keepManualPosition = tip.classList.contains('phish-radar-link-tooltip-manual') && linkTooltipPinned;
    tip.innerHTML = buildLinkTooltipHtml(data);
    tip.className = data.result?.score >= 61 ? 'phish-radar-link-tooltip-open phish-radar-link-tooltip-high' : 'phish-radar-link-tooltip-open';
    if (keepManualPosition) tip.classList.add('phish-radar-link-tooltip-manual', 'phish-radar-link-tooltip-pinned');
    // Preserve the shared theme after className resets tooltip state classes.
    const tooltipTheme = uiTheme === 'dark' ? 'dark' : 'light';
    tip.classList.add(`phish-radar-theme-${tooltipTheme}`);
    tip.dataset.phishRadarTheme = tooltipTheme;
    // Position twice after layout is calculated, then guard against edge clipping.
    if (keepManualPosition) {
      requestAnimationFrame(() => keepLinkTooltipInViewport(tip));
    } else {
      positionLinkTooltip(trigger);
      requestAnimationFrame(() => {
        positionLinkTooltip(trigger);
        keepLinkTooltipInViewport(tip);
      });
    }
  }

  function closeLinkTooltip() {
    clearTimeout(linkTooltipHideTimer);
    linkTooltipPinned = false;
    linkTooltipDragging = false;
    if (linkTooltipEl) {
      linkTooltipEl.classList.remove(
        'phish-radar-link-tooltip-open',
        'phish-radar-link-tooltip-pinned',
        'phish-radar-link-tooltip-manual',
        'phish-radar-dragging',
        'phish-radar-resizing'
      );
      clearFloatingManualStyles(linkTooltipEl);
    }
    activeTooltipTrigger = null;
  }

  function hideLinkTooltipSoon() {
    if (linkTooltipPinned) return;
    clearTimeout(linkTooltipHideTimer);
    linkTooltipHideTimer = setTimeout(() => {
      if (linkTooltipPinned || linkTooltipEl?.matches(':hover') || activeTooltipTrigger?.matches?.(':hover')) return;
      if (linkTooltipEl) linkTooltipEl.classList.remove('phish-radar-link-tooltip-open');
      activeTooltipTrigger = null;
    }, 260);
  }


  function keepLinkTooltipInViewport(tip) {
    if (!tip) return;
    const rect = tip.getBoundingClientRect();
    const margin = 12;
    const viewportWidth = Math.max(document.documentElement.clientWidth || 0, window.innerWidth || 0);
    const viewportHeight = Math.max(document.documentElement.clientHeight || 0, window.innerHeight || 0);
    const maxWidth = Math.max(240, viewportWidth - margin * 2);
    const minReadableWidth = Math.min(320, maxWidth);
    const width = clampNumber(rect.width || minReadableWidth, minReadableWidth, maxWidth);
    const maxHeight = Math.max(180, viewportHeight - margin * 2);
    const height = clampNumber(rect.height || 220, 180, maxHeight);
    const left = clampNumber(rect.left, margin, Math.max(margin, viewportWidth - width - margin));
    const top = clampNumber(rect.top, margin, Math.max(margin, viewportHeight - height - margin));

    tip.style.setProperty('width', `${width}px`, 'important');
    tip.style.setProperty('max-width', `${maxWidth}px`, 'important');
    tip.style.setProperty('max-height', `${maxHeight}px`, 'important');
    tip.style.setProperty('left', `${left}px`, 'important');
    tip.style.setProperty('top', `${top}px`, 'important');
    tip.style.setProperty('right', 'auto', 'important');
    tip.style.setProperty('bottom', 'auto', 'important');
  }


  function beginFloatingResize(el, e, options = {}) {
    if (!el) return;
    e.preventDefault();
    e.stopPropagation();

    const rect = el.getBoundingClientRect();
    const margin = 10;
    const minWidth = options.minWidth || 260;
    const minHeight = options.minHeight || 170;
    const maxWidth = Math.max(minWidth, window.innerWidth - rect.left - margin);
    const maxHeight = Math.max(minHeight, window.innerHeight - rect.top - margin);
    const startX = e.clientX;
    const startY = e.clientY;
    let frame = 0;

    options.onStart?.();
    el.classList.add(options.manualClass || 'phish-radar-window-manual', 'phish-radar-resizing');
    setFloatingStyle(el, 'right', 'auto');
    setFloatingStyle(el, 'bottom', 'auto');
    setFloatingStyle(el, 'left', `${rect.left}px`);
    setFloatingStyle(el, 'top', `${rect.top}px`);
    setFloatingStyle(el, 'width', `${rect.width}px`);
    setFloatingStyle(el, 'height', `${rect.height}px`);
    setFloatingStyle(el, 'max-width', 'none');
    setFloatingStyle(el, 'max-height', 'none');
    setFloatingStyle(el, 'transition', 'none');
    setFloatingStyle(el, 'transform', 'none');

    const onMove = ev => {
      ev.preventDefault();
      ev.stopPropagation();
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        frame = 0;
        const nextWidth = clampNumber(rect.width + ev.clientX - startX, minWidth, maxWidth);
        const nextHeight = clampNumber(rect.height + ev.clientY - startY, minHeight, maxHeight);
        setFloatingStyle(el, 'width', `${nextWidth}px`);
        setFloatingStyle(el, 'height', `${nextHeight}px`);
      });
    };
    const onUp = ev => {
      ev.preventDefault();
      ev.stopPropagation();
      if (frame) cancelAnimationFrame(frame);
      el.classList.remove('phish-radar-resizing');
      setFloatingStyle(el, 'transition', 'none');
      setFloatingStyle(el, 'transform', 'none');
      options.onEnd?.();
      document.removeEventListener('pointermove', onMove, true);
      document.removeEventListener('pointerup', onUp, true);
      document.removeEventListener('pointercancel', onUp, true);
    };

    document.addEventListener('pointermove', onMove, true);
    document.addEventListener('pointerup', onUp, true);
    document.addEventListener('pointercancel', onUp, true);
  }

  function enableDraggableLinkTooltip(tip) {
    if (!tip || tip.dataset.dragReady === '1') return;
    tip.dataset.dragReady = '1';
    tip.addEventListener('pointerdown', e => {
      const resizeHandle = e.target?.closest?.('[data-tooltip-action="resize"]');
      if (resizeHandle) {
        beginFloatingResize(tip, e, {
          manualClass: 'phish-radar-link-tooltip-manual',
          minWidth: 260,
          minHeight: 170,
          onStart: () => {
            clearTimeout(linkTooltipHideTimer);
            linkTooltipPinned = true;
            linkTooltipDragging = true;
            tip.classList.add('phish-radar-link-tooltip-pinned');
          },
          onEnd: () => {
            linkTooltipDragging = false;
            keepLinkTooltipInViewport(tip);
          }
        });
        return;
      }
      const header = e.target?.closest?.('.phish-radar-link-tooltip-top');
      if (!header || e.target?.closest?.('button, a, input, textarea, select')) return;
      e.preventDefault();
      e.stopPropagation();
      clearTimeout(linkTooltipHideTimer);
      linkTooltipPinned = true;
      linkTooltipDragging = true;
      const rect = tip.getBoundingClientRect();
      const offsetX = e.clientX - rect.left;
      const offsetY = e.clientY - rect.top;
      tip.classList.add('phish-radar-link-tooltip-manual', 'phish-radar-link-tooltip-pinned', 'phish-radar-dragging');
      setFloatingStyle(tip, 'right', 'auto');
      setFloatingStyle(tip, 'bottom', 'auto');
      setFloatingStyle(tip, 'left', `${rect.left}px`);
      setFloatingStyle(tip, 'top', `${rect.top}px`);
      setFloatingStyle(tip, 'transition', 'none');
      setFloatingStyle(tip, 'transform', 'none');

      const onMove = ev => {
        const w = tip.offsetWidth || rect.width;
        const h = tip.offsetHeight || rect.height;
        const margin = 10;
        const left = clampNumber(ev.clientX - offsetX, margin, Math.max(margin, window.innerWidth - w - margin));
        const top = clampNumber(ev.clientY - offsetY, margin, Math.max(margin, window.innerHeight - h - margin));
        setFloatingStyle(tip, 'left', `${left}px`);
        setFloatingStyle(tip, 'top', `${top}px`);
      };
      const onUp = ev => {
        linkTooltipDragging = false;
        tip.classList.remove('phish-radar-dragging');
        setFloatingStyle(tip, 'transition', 'none');
        setFloatingStyle(tip, 'transform', 'none');
        keepLinkTooltipInViewport(tip);
        document.removeEventListener('pointermove', onMove, true);
        document.removeEventListener('pointerup', onUp, true);
        document.removeEventListener('pointercancel', onUp, true);
      };
      document.addEventListener('pointermove', onMove, true);
      document.addEventListener('pointerup', onUp, true);
      document.addEventListener('pointercancel', onUp, true);
    }, true);
  }

  function attachLinkTooltip(trigger, result, resolved) {
    if (!trigger || trigger.dataset.phishRadarTooltipBound === '1') return;
    const tooltipData = {
      url: resolved?.effectiveUrl || result?.url || '',
      originalUrl: resolved?.originalUrl || '',
      wasRedirectWrapper: !!resolved?.wasRedirectWrapper,
      result: {
        score: result?.score,
        levelText: result?.levelText,
        url: result?.url,
        reasons: (result?.reasons || []).slice(0, 6),
        threatTypes: result?.threatTypes || []
      }
    };
    trigger.dataset.phishRadarTooltip = JSON.stringify(tooltipData);
    trigger.dataset.phishRadarTooltipBound = '1';
    trigger.addEventListener('mouseenter', () => showLinkTooltip(trigger));
    trigger.addEventListener('focus', () => showLinkTooltip(trigger));
    trigger.addEventListener('mousemove', () => scheduleLinkTooltipPosition(trigger));
    trigger.addEventListener('mouseleave', hideLinkTooltipSoon);
    trigger.addEventListener('blur', hideLinkTooltipSoon);
  }

  function createBadge(result, mode) {
    const badge = document.createElement('span');
    const high = result.score >= 61;
    const critical = result.score >= 81;
    badge.className = `phish-radar-badge ${high ? 'phish-radar-high' : ''} ${critical ? 'phish-radar-critical' : ''} ${mode === 'search' ? 'phish-radar-compact' : ''}`;
    // Search pages can distort inline score text; keep the badge icon-only and put the score in the tooltip.
    const displayScore = String(Math.round(Number(result.score) || 0));
    badge.textContent = '!';
    badge.dataset.score = displayScore;
    badge.dataset.level = critical ? 'critical' : high ? 'high' : 'medium';
    badge.setAttribute('dir', 'ltr');
    badge.setAttribute('lang', 'en');
    badge.style.setProperty('all', 'initial', 'important');
    badge.style.setProperty('box-sizing', 'border-box', 'important');
    badge.style.setProperty('display', 'inline-flex', 'important');
    badge.style.setProperty('align-items', 'center', 'important');
    badge.style.setProperty('justify-content', 'center', 'important');
    badge.style.setProperty('width', '22px', 'important');
    badge.style.setProperty('min-width', '22px', 'important');
    badge.style.setProperty('height', '22px', 'important');
    badge.style.setProperty('min-height', '22px', 'important');
    badge.style.setProperty('margin', '0 0 0 6px', 'important');
    badge.style.setProperty('padding', '0', 'important');
    badge.style.setProperty('border-radius', '999px', 'important');
    badge.style.setProperty('font-family', 'Arial, Helvetica, sans-serif', 'important');
    badge.style.setProperty('font-size', '14px', 'important');
    badge.style.setProperty('font-weight', '900', 'important');
    badge.style.setProperty('line-height', '1', 'important');
    badge.style.setProperty('letter-spacing', '0', 'important');
    badge.style.setProperty('color', '#ffffff', 'important');
    badge.style.setProperty('background', high ? '#dc2626' : '#f59e0b', 'important');
    badge.style.setProperty('border', '1px solid rgba(255,255,255,.5)', 'important');
    badge.style.setProperty('box-shadow', '0 1px 2px rgba(15,23,42,.22)', 'important');
    badge.style.setProperty('white-space', 'nowrap', 'important');
    badge.style.setProperty('direction', 'ltr', 'important');
    badge.style.setProperty('unicode-bidi', 'isolate', 'important');
    badge.style.setProperty('writing-mode', 'horizontal-tb', 'important');
    badge.style.setProperty('text-align', 'center', 'important');
    badge.style.setProperty('vertical-align', 'middle', 'important');
    badge.style.setProperty('position', 'relative', 'important');
    badge.style.setProperty('top', '-1px', 'important');
    badge.style.setProperty('transform', 'none', 'important');
    badge.style.setProperty('overflow', 'visible', 'important');
    badge.style.setProperty('cursor', 'pointer', 'important');
    badge.title = `Phish Radar: ${result.levelText} (${result.score}/100)\nSearch Safety Badge: ชี้หรือกดเพื่อดูเหตุผลก่อนเปิดลิงก์`;
    badge.setAttribute('aria-label', badge.title);
    badge.setAttribute('role', 'button');
    badge.setAttribute('tabindex', '0');
    return badge;
  }

  function ensureLinkId(a) {
    if (!a.dataset.phishRadarId) a.dataset.phishRadarId = `pr-link-${++linkIdCounter}`;
    return a.dataset.phishRadarId;
  }

  function markLink(a, result, mode, resolved) {
    if (!a) return '';
    const linkId = ensureLinkId(a);
    if (a.dataset.phishRadarMarked === '1') return linkId;
    a.dataset.phishRadarMarked = '1';
    a.dataset.phishRadarScore = String(result.score);
    a.dataset.phishRadarReasons = result.reasons.map(r => r.label).join(' | ');
    a.classList.add('phish-radar-link-target');
    if (mode === 'search') a.classList.add('phish-radar-search-result');
    if (result.score >= 61) a.classList.add('phish-radar-high');

    attachLinkTooltip(a, result, resolved);
    const badge = createBadge(result, mode);
    badge.dataset.phishRadarFor = linkId;
    attachLinkTooltip(badge, result, resolved);
    badge.addEventListener('click', e => {
      e.preventDefault();
      e.stopPropagation();
      showLinkTooltip(badge);
    });
    badge.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        showLinkTooltip(badge);
      }
    });
    if (a.parentElement) a.insertAdjacentElement('afterend', badge);
    return linkId;
  }

    function visualThresholdForMode(mode) {
    // Search pages have many tracking URLs and snippets. Show only high-confidence
    // hits visually, but still count medium hits in the popup statistics.
    if (mode === 'search') return Math.max(31, Number(settings.threshold || 31));
    if (mode === 'feed') return 55;
    return 31;
  }

  function shouldVisuallyMark(a, result, mode, resolved) {
    if (mode === 'search' && !settings.searchProtection) return false;
    if (result.score < visualThresholdForMode(mode)) return false;
    if (!isElementVisible(a)) return false;

    const eff = tryUrl(resolved?.effectiveUrl);
    if (!eff) return false;

    // Do not decorate internal search/navigation links unless the analyzer is highly confident.
    if (mode === 'search' && sameOrSubdomain(eff.hostname, location.hostname) && result.score < 90) return false;
    return true;
  }

  function scanLinks(limit = 600) {
    const mode = currentPageMode();
    if (!settings.pageScanningEnabled) return { scanned: 0, risky: 0, high: 0, medium: 0, shown: 0, mode: 'disabled', disabled: true };
    if (!settings.highlightLinks && !(settings.searchProtection && mode === 'search')) return { scanned: 0, risky: 0, high: 0, medium: 0, shown: 0, mode };
    const anchors = Array.from(document.querySelectorAll('a[href]')).slice(0, limit);
    let scanned = 0;
    let risky = 0;
    let high = 0;
    let medium = 0;
    let shown = 0;
    const items = [];
    const visuallyMarkedUrls = new Set();

    for (const a of anchors) {
      if (a.dataset.phishRadarSkip === '1') continue;
      const raw = a.getAttribute('href');
      if (shouldSkipUrl(raw)) continue;
      const resolved = resolveEffectiveUrl(raw);
      if (!resolved) continue;
      if (isTrustedWebAppUrl(resolved.effectiveUrl)) continue;
      scanned++;

      const result = PhishRadarAnalyzer.analyzeUrl(resolved.effectiveUrl, linkOptions(a, resolved, mode));
      if (result.score >= 31) {
        risky++;
        if (result.score >= 61) high++; else medium++;

        let markerId = '';
        const normalizedUrl = resolved.effectiveUrl.replace(/[#?].*$/, '');
        const visual = shouldVisuallyMark(a, result, mode, resolved) && !visuallyMarkedUrls.has(normalizedUrl);
        if (visual) {
          markerId = markLink(a, result, mode, resolved);
          visuallyMarkedUrls.add(normalizedUrl);
          shown++;
        }

        items.push({
          linkId: markerId || a.dataset.phishRadarId || '',
          score: result.score,
          levelText: result.levelText,
          url: resolved.effectiveUrl,
          originalUrl: resolved.originalUrl,
          wasRedirectWrapper: !!resolved.wasRedirectWrapper,
          visuallyShown: !!visual,
          reasons: result.reasons.slice(0, 4)
        });
      }
    }

    items.sort((a, b) => b.score - a.score);
    lastScan = { scanned, risky, high, medium, shown, mode, items: items.slice(0, 10) };
    updateMiniPanel(lastScan);
    return lastScan;
  }



  function clampNumber(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function setFloatingStyle(el, property, value) {
    el?.style?.setProperty(property, value, 'important');
  }

  function clearFloatingManualStyles(el) {
    if (!el?.style) return;
    [
      'left', 'top', 'right', 'bottom', 'width', 'height',
      'max-width', 'max-height', 'transition', 'transform'
    ].forEach(property => el.style.removeProperty(property));
  }

  function setDetailsStyle(details, property, value) {
    setFloatingStyle(details, property, value);
  }

  function clearDetailsManualStyles(details) {
    clearFloatingManualStyles(details);
  }

  function resetDetailsWindow(panel) {
    const details = panel?.querySelector?.('[data-role="details"]');
    if (!details) return;
    details.classList.remove('phish-radar-window-manual');
    clearDetailsManualStyles(details);
  }

  function keepDetailsInViewport(details) {
    if (!details || !details.classList.contains('phish-radar-window-manual')) return;
    const rect = details.getBoundingClientRect();
    const margin = 10;
    const maxLeft = Math.max(margin, window.innerWidth - rect.width - margin);
    const maxTop = Math.max(margin, window.innerHeight - rect.height - margin);
    const left = clampNumber(rect.left, margin, maxLeft);
    const top = clampNumber(rect.top, margin, maxTop);
    setDetailsStyle(details, 'left', `${left}px`);
    setDetailsStyle(details, 'top', `${top}px`);
  }

  function prepareDetailsForManualMove(details) {
    const rect = details.getBoundingClientRect();
    details.classList.add('phish-radar-window-manual');
    setDetailsStyle(details, 'right', 'auto');
    setDetailsStyle(details, 'bottom', 'auto');
    setDetailsStyle(details, 'left', `${rect.left}px`);
    setDetailsStyle(details, 'top', `${rect.top}px`);
    setDetailsStyle(details, 'width', `${rect.width}px`);
    setDetailsStyle(details, 'height', `${rect.height}px`);
    setDetailsStyle(details, 'max-width', 'none');
    setDetailsStyle(details, 'max-height', 'none');
    setDetailsStyle(details, 'transition', 'none');
    setDetailsStyle(details, 'transform', 'none');
    return rect;
  }

  function installFloatingDetailsMouseHandlers() {
    if (document.documentElement.dataset.phishRadarDetailsMouseReady === '1') return;
    document.documentElement.dataset.phishRadarDetailsMouseReady = '1';

    document.addEventListener('mousedown', e => {
      const details = e.target?.closest?.('#phish-radar-details-window');
      const panel = document.getElementById('phish-radar-mini-panel');
      if (!details || !panel?.classList.contains('phish-radar-details-open')) return;

      const resizeHandle = e.target?.closest?.('[data-action="details-resize"]');
      const header = e.target?.closest?.('.phish-radar-detail-top');
      if (!resizeHandle && (!header || e.target?.closest?.('button, a, input, textarea, select'))) return;

      e.preventDefault();
      e.stopPropagation();

      const rect = prepareDetailsForManualMove(details);
      const startX = e.clientX;
      const startY = e.clientY;
      const offsetX = e.clientX - rect.left;
      const offsetY = e.clientY - rect.top;
      const minWidth = 300;
      const minHeight = 190;
      let frame = 0;
      detailsInteracting = true;
      details.classList.add(resizeHandle ? 'phish-radar-resizing' : 'phish-radar-dragging');
      document.documentElement.classList.add('phish-radar-window-moving');

      const onMove = ev => {
        ev.preventDefault();
        ev.stopPropagation();
        if (frame) cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => {
          frame = 0;
          const margin = 10;
          if (resizeHandle) {
            const nextWidth = clampNumber(rect.width + ev.clientX - startX, minWidth, Math.max(minWidth, window.innerWidth - rect.left - margin));
            const nextHeight = clampNumber(rect.height + ev.clientY - startY, minHeight, Math.max(minHeight, window.innerHeight - rect.top - margin));
            setDetailsStyle(details, 'width', `${nextWidth}px`);
            setDetailsStyle(details, 'height', `${nextHeight}px`);
            return;
          }
          const w = details.offsetWidth || rect.width;
          const h = details.offsetHeight || rect.height;
          const left = clampNumber(ev.clientX - offsetX, margin, Math.max(margin, window.innerWidth - w - margin));
          const top = clampNumber(ev.clientY - offsetY, margin, Math.max(margin, window.innerHeight - h - margin));
          setDetailsStyle(details, 'left', `${left}px`);
          setDetailsStyle(details, 'top', `${top}px`);
        });
      };

      const onUp = ev => {
        ev.preventDefault();
        ev.stopPropagation();
        if (frame) cancelAnimationFrame(frame);
        detailsInteracting = false;
        suppressDetailsClickUntil = Date.now() + 220;
        details.classList.remove('phish-radar-dragging', 'phish-radar-resizing');
        document.documentElement.classList.remove('phish-radar-window-moving');
        keepDetailsInViewport(details);
        document.removeEventListener('mousemove', onMove, true);
        document.removeEventListener('mouseup', onUp, true);
      };

      document.addEventListener('mousemove', onMove, true);
      document.addEventListener('mouseup', onUp, true);
    }, true);
  }

  function enableFloatingDetailsWindow(panel) {
    const details = panel?.querySelector?.('[data-role="details"]');
    if (!panel || !details || details.dataset.floatWindowReady === '1') return;
    details.dataset.floatWindowReady = '1';
    installFloatingDetailsMouseHandlers();
  }

    function setDetailsOpen(panel, open) {
    if (!panel) return;
    detailsPinned = !!open;
    clearTimeout(detailCloseTimer);
    panel.classList.toggle('phish-radar-details-open', detailsPinned);
    panel.classList.toggle('phish-radar-details-pinned', detailsPinned);
    const hint = panel.querySelector('.phish-radar-hint');
    if (hint) {
      hint.textContent = detailsPinned ? 'กำลังแสดงรายละเอียด' : 'คลิกเพื่อดูรายละเอียด';
      hint.title = detailsPinned ? 'กดปิดเพื่อซ่อนรายละเอียด' : 'คลิกเพื่อเปิดรายละเอียดแบบค้างไว้ สามารถเลื่อนอ่านได้';
      hint.setAttribute('aria-expanded', detailsPinned ? 'true' : 'false');
    }
    if (!detailsPinned) {
      resetDetailsWindow(panel);
      return;
    }
    if (detailsPinned) {
      const details = panel.querySelector('[data-role="details"]');
      if (details && !details.innerHTML.trim()) details.innerHTML = buildHoverDetails(lastScan);
      applyUiTheme();
    }
  }

  function scheduleDetailsClose(panel) {
    // v1.0: details are click-to-open instead of hover-to-open to avoid flicker
    // and to make the scrollable detail card stable for presentation/demo use.
    return panel;
  }

  function flashLink(linkId) {
    if (!linkId) return;
    const link = document.querySelector(`[data-phish-radar-id="${CSS.escape(linkId)}"]`);
    if (!link) return;
    link.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
    link.classList.add('phish-radar-flash-target');
    setTimeout(() => link.classList.remove('phish-radar-flash-target'), 2200);
    showLinkTooltip(link);
  }

  function updateMiniPanel(scan) {
    if (!settings.pageScanningEnabled) return;
    if (!settings.highlightLinks) return;
    if (!settings.showStatusPanel && scan.risky === 0) return;

    let panel = document.getElementById('phish-radar-mini-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'phish-radar-mini-panel';
      panel.innerHTML = `
        <strong data-role="brand"><span data-role="icon">🛡️</span> Phish Radar</strong>
        <span data-role="text"></span>
        <button type="button" class="phish-radar-hint" data-action="details-toggle" title="คลิกเพื่อเปิดรายละเอียดแบบค้างไว้" aria-expanded="false" aria-controls="phish-radar-details-window">รายละเอียด</button>
        <div class="phish-radar-hover-details" data-role="details" id="phish-radar-details-window"></div>
        <button type="button" data-action="hide" title="ซ่อน" aria-label="ซ่อน Phish Radar">×</button>`;
      document.documentElement.appendChild(panel);
      applyUiTheme();
      enableFloatingDetailsWindow(panel);
      panel.addEventListener('click', async e => {
        if (Date.now() < suppressDetailsClickUntil) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        const action = e.target?.dataset?.action;
        if (action === 'hide') {
          detailsPinned = false;
          clearTimeout(detailCloseTimer);
          panel.remove();
          return;
        }
        if (action === 'details-close') {
          e.preventDefault();
          e.stopPropagation();
          setDetailsOpen(panel, false);
          return;
        }
        if (action === 'details-reset') {
          e.preventDefault();
          e.stopPropagation();
          resetDetailsWindow(panel);
          return;
        }        if (action === 'details-toggle') {
          e.preventDefault();
          e.stopPropagation();
          setDetailsOpen(panel, !detailsPinned);
          return;
        }
        if (action === 'scroll-link') {
          e.preventDefault();
          e.stopPropagation();
          flashLink(e.target.dataset.targetId);
          return;
        }
        if (action === 'warning-link') {
          e.preventDefault();
          e.stopPropagation();
          await sendMessage({ type: 'OPEN_WARNING', target: e.target.dataset.url, source: location.href });
          return;
        }
        if (action === 'copy-url') {
          e.preventDefault();
          e.stopPropagation();
          try { await navigator.clipboard.writeText(e.target.dataset.url || ''); e.target.textContent = 'คัดลอกแล้ว'; } catch (_) { e.target.textContent = 'คัดลอกไม่ได้'; }
          setTimeout(() => { e.target.textContent = 'คัดลอก URL'; }, 1200);
          return;
        }
      });
    }


    const visibleRisk = scan.mode === 'search' ? scan.shown > 0 : scan.risky > 0;
    const safe = !visibleRisk;
    panel.classList.toggle('phish-radar-safe-panel', safe);
    panel.classList.toggle('phish-radar-risk-panel', !safe);

    const icon = panel.querySelector('[data-role="icon"]');
    if (icon) icon.textContent = safe ? '✅' : '🛡️';

    const suffix = scan.mode === 'search'
      ? `Search Mode • แสดงเตือนบนหน้า ${scan.shown} รายการ`
      : `แสดงเตือนบนหน้า ${scan.shown} รายการ`;

    const message = safe
      ? (scan.mode === 'search'
        ? `สแกนแล้ว ${scan.scanned} ลิงก์ • ไม่พบลิงก์เสี่ยงสูง`
        : `เว็บไซต์นี้ดูปลอดภัย • สแกนแล้ว ${scan.scanned} ลิงก์`)
      : `พบลิงก์น่าสงสัย ${scan.shown || scan.risky}/${scan.scanned} รายการ (${suffix})`;

    panel.querySelector('[data-role="text"]').textContent = message;
    const details = panel.querySelector('[data-role="details"]');
    if (details && !detailsInteracting && !details.classList.contains('phish-radar-dragging') && !details.classList.contains('phish-radar-resizing') && (!detailsPinned || !details.innerHTML.trim())) {
      details.innerHTML = buildHoverDetails(scan);
      applyUiTheme();
    }
  }

    async function checkCurrentPage() {
    if (!settings.pageScanningEnabled) return;
    if (isTrustedWebAppUrl(location.href)) {
      if (!settings.privacyMode) await sendMessage({ type: 'ANALYZE_URL', url: location.href });
      return;
    }
    const options = pageRiskOptions();
    const result = PhishRadarAnalyzer.analyzeUrl(location.href, options);
    if (!settings.privacyMode) await sendMessage({ type: 'ANALYZE_URL', url: location.href, options });
    const visualHigh = Array.isArray(options.visualFindings) && options.visualFindings.some(item => Number(item.points || 0) >= 24);
    const hasSensitiveInput = document.querySelector('input[type="password"], input[name*="otp" i], input[name*="token" i]');
    if (settings.protectForms && result.score >= 50 && (hasSensitiveInput || visualHigh)) {
      showOverlay(result, visualHigh ? 'visual' : 'page');
    }
  }

  function showOverlay(result, mode = 'form') {
    if (document.getElementById('phish-radar-overlay')) {
      renderPageEvidence(result);
      return;
    }
    const pageEvidence = collectPageEvidence(result);
    const topReasons = result.reasons.slice(0, 5).map(r => `<li>${escapeHtml(r.label)}${r.detail ? `<br><small>${escapeHtml(r.detail)}</small>` : ''}</li>`).join('');
    const previousFocus = document.activeElement;
    const div = document.createElement('div');
    div.id = 'phish-radar-overlay';
    div.setAttribute('role', 'dialog');
    div.setAttribute('aria-modal', 'true');
    div.setAttribute('aria-labelledby', 'phish-radar-overlay-title');
    div.tabIndex = -1;
    div.innerHTML = `
      <h3 id="phish-radar-overlay-title">⚠ หยุดก่อน! หน้านี้อาจมีความเสี่ยง</h3>
      <p><b>Risk Score:</b> ${result.score}/100 — ${escapeHtml(result.levelText)}</p>
      <p>${mode === 'submit'
        ? 'ระบบหยุดการส่งฟอร์มไว้ก่อน เพราะพบสัญญาณเสี่ยงร่วมกับข้อมูลสำคัญ'
        : 'ระบบไม่ได้ดูแค่คะแนน แต่กำลังชี้หลักฐานบนหน้าเว็บให้เห็นว่าจุดไหนควรระวัง'}</p>
      ${pageEvidence.length ? `<p class="phish-radar-overlay-evidence-note">พบหลักฐานบนหน้า ${pageEvidence.length} จุด เช่น ช่องข้อมูลสำคัญ ปุ่มชวนกด หรือโดเมนเลียนแบบแบรนด์</p>` : ''}
      <ul>${topReasons || '<li>คะแนนสูงจากรูปแบบ URL/หน้าเว็บที่ผิดปกติ</li>'}</ul>
      <div class="phish-radar-actions">
        <button type="button" class="primary" data-action="back">ย้อนกลับ</button>
        <button type="button" class="secondary" data-action="evidence">ชี้จุดเสี่ยง${pageEvidence.length ? ` (${pageEvidence.length})` : ''}</button>
        <button type="button" class="secondary" data-action="dismiss">ฉันเข้าใจแล้ว</button>
      </div>`;
    const closeOverlay = () => {
      div.remove();
      if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus({ preventScroll: true });
    };
    document.documentElement.appendChild(div);
    applyUiTheme();
    if (pageEvidence.length) renderPageEvidence(result);
    requestAnimationFrame(() => div.focus({ preventScroll: true }));
    div.addEventListener('keydown', e => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeOverlay();
      }
    });
    div.addEventListener('click', e => {
      const action = e.target?.dataset?.action;
      if (action === 'back') {
        clearPageEvidence();
        history.length > 1 ? history.back() : location.assign('about:blank');
      }
      if (action === 'evidence') renderPageEvidence(result);
      if (action === 'dismiss') closeOverlay();
    });
  }

  async function handleClick(e) {
    if (!settings.pageScanningEnabled) return;
    const a = e.target?.closest?.('a[href]');
    if (!a) return;
    const raw = a.getAttribute('href');
    if (shouldSkipUrl(raw)) return;
    const resolved = resolveEffectiveUrl(raw);
    if (!resolved) return;
    if (isTrustedWebAppUrl(resolved.effectiveUrl)) return;
    const mode = currentPageMode();
    const result = PhishRadarAnalyzer.analyzeUrl(resolved.effectiveUrl, linkOptions(a, resolved, mode));

    if (result.score >= settings.threshold) {
      e.preventDefault();
      e.stopImmediatePropagation();
      await sendMessage({
        type: 'OPEN_WARNING',
        target: resolved.effectiveUrl,
        source: location.href,
        result
      });
    }
  }

  function protectClipboard() {
    document.addEventListener('paste', e => {
      if (!settings.pageScanningEnabled) return;
      if (!settings.clipboardProtection) return;
      if (isPhishRadarUiNode(e.target)) return;
      const text = e.clipboardData?.getData('text/plain') || '';
      const url = extractPotentialUrl(text);
      if (!url) return;
      if (isTrustedWebAppUrl(url)) return;
      const result = PhishRadarAnalyzer.analyzeUrl(url, { visibleText: text.slice(0, 500) });
      if (result.score < Number(settings.threshold || 61)) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      showClipboardProtectionOverlay(url, result, e.target, text);
    }, true);
  }

  function protectForms() {
    const secretSelector = 'input[type="password"], input[name*="otp" i], input[name*="token" i], input[name*="pin" i], input[autocomplete="one-time-code"]';

    document.addEventListener('focusin', e => {
      if (!settings.pageScanningEnabled) return;
      if (!settings.protectForms) return;
      if (isTrustedWebAppUrl(location.href)) return;
      if (!e.target?.matches?.(secretSelector)) return;
      const result = PhishRadarAnalyzer.analyzeUrl(location.href, pageRiskOptions());
      if (result.score >= 60) showOverlay(result, 'focus');
    }, true);

    document.addEventListener('submit', e => {
      if (!settings.pageScanningEnabled) return;
      if (!settings.protectForms) return;
      if (isTrustedWebAppUrl(location.href)) return;
      const form = e.target;
      if (!form?.querySelector?.(secretSelector)) return;
      const result = PhishRadarAnalyzer.analyzeUrl(location.href, pageRiskOptions());
      if (result.score >= 55) {
        e.preventDefault();
        e.stopImmediatePropagation();
        showOverlay(result, 'submit');
      }
    }, true);
  }

  function isPhishRadarUiNode(node) {
    if (!node) return false;
    const el = node.nodeType === 1 ? node : node.parentElement;
    return !!el?.closest?.('#phish-radar-mini-panel, #phish-radar-link-tooltip, #phish-radar-overlay, #phish-radar-evidence-layer, .phish-radar-badge');
  }

  function clearPageScanningUi() {
    pageScanObserver?.disconnect();
    pageScanObserver = null;
    alreadyScanned = false;
    closeLinkTooltip();
    clearPageEvidence();
    document.querySelectorAll('.phish-radar-badge').forEach(node => node.remove());
    document.querySelectorAll('a.phish-radar-link-target, a[data-phish-radar-marked="1"]').forEach(link => {
      link.classList.remove('phish-radar-link-target', 'phish-radar-search-result', 'phish-radar-high', 'phish-radar-flash-target');
      delete link.dataset.phishRadarMarked;
      delete link.dataset.phishRadarScore;
      delete link.dataset.phishRadarReasons;
    });
    [
      'phish-radar-mini-panel',
      'phish-radar-link-tooltip',
      'phish-radar-overlay',
      'phish-radar-evidence-layer',
      'phish-radar-clipboard-overlay'
    ].forEach(id => document.getElementById(id)?.remove());
    linkTooltipEl = null;
    activeTooltipTrigger = null;
    lastScan = { scanned: 0, risky: 0, high: 0, medium: 0, shown: 0, mode: 'disabled', disabled: true };
  }

  async function startPageScanning() {
    if (!settings.pageScanningEnabled || alreadyScanned) return lastScan;
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => void startPageScanning(), { once: true });
      return lastScan;
    }
    alreadyScanned = true;
    const scan = scanLinks();
    await checkCurrentPage();
    setupMutationObserver();
    return scan;
  }

  async function setPageScanningEnabled(enabled) {
    settings.pageScanningEnabled = enabled !== false;
    if (!settings.pageScanningEnabled) {
      clearPageScanningUi();
      return lastScan;
    }
    return startPageScanning();
  }

  function setupMutationObserver() {
    if (pageScanObserver || !settings.pageScanningEnabled) return;
    let timer = null;
    pageScanObserver = new MutationObserver(mutations => {
      if (!settings.pageScanningEnabled) return;
      if (mutations.every(m => isPhishRadarUiNode(m.target) || Array.from(m.addedNodes || []).every(isPhishRadarUiNode))) return;
      clearTimeout(timer);
      timer = setTimeout(() => { if (!document.hidden) scanLinks(180); }, 1400);
    });
    if (document.documentElement) pageScanObserver.observe(document.documentElement, { childList: true, subtree: true });
  }

    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message?.type === 'SET_UI_THEME') {
      uiTheme = message.theme === 'dark' ? 'dark' : 'light';
      applyUiTheme();
      sendResponse({ ok: true, theme: uiTheme });
      return true;
    }
    if (message?.type === 'SET_PAGE_SCANNING') {
      setPageScanningEnabled(message.enabled !== false)
        .then(scan => sendResponse({ ok: true, enabled: settings.pageScanningEnabled, ...scan }))
        .catch(error => sendResponse({ ok: false, error: String(error?.message || error) }));
      return true;
    }
    if (message?.type === 'SCAN_LINKS_NOW') {
      if (!settings.pageScanningEnabled) {
        sendResponse({ ok: false, error: 'page-scanning-disabled', disabled: true });
        return true;
      }
      const result = scanLinks(1000);
      sendResponse({ ok: true, ...result });
      return true;
    }
    if (message?.type === 'GET_PAGE_SCAN') {
      if (!settings.pageScanningEnabled) {
        sendResponse({ ok: true, disabled: true, lastScan });
        return true;
      }
      const pageResult = isTrustedWebAppUrl(location.href)
        ? trustedWebAppResult(location.href)
        : PhishRadarAnalyzer.analyzeUrl(location.href, pageRiskOptions());
      const linkScan = scanLinks(1000);
      sendResponse({ ok: true, pageResult, linkScan, lastScan });
      return true;
    }
    if (message?.type === 'GET_LAST_SCAN') {
      sendResponse({ ok: true, lastScan });
      return true;
    }
  });

  async function boot() {
    await loadSettings();
    document.addEventListener('click', handleClick, true);
    document.addEventListener('auxclick', handleClick, true);
    protectClipboard();
    protectForms();
    window.addEventListener('scroll', () => { if (activeTooltipTrigger) scheduleLinkTooltipPosition(activeTooltipTrigger); }, true);
    window.addEventListener('resize', () => {
      if (activeTooltipTrigger) scheduleLinkTooltipPosition(activeTooltipTrigger);
      const details = document.querySelector('#phish-radar-mini-panel [data-role="details"]');
      keepDetailsInViewport(details);
      keepLinkTooltipInViewport(linkTooltipEl);
    });

    const run = async () => startPageScanning();

    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', run, { once: true });
    } else {
      run();
    }
  }

  boot();
})();




