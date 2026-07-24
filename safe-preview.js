(() => {
  'use strict';

  if (window.__phishRadarSafePreviewReady) return;
  window.__phishRadarSafePreviewReady = true;

  const SENSITIVE_SELECTOR = [
    'input[type="password"]',
    'input[name*="otp" i]',
    'input[name*="token" i]',
    'input[name*="pin" i]',
    'input[name*="card" i]',
    'input[name*="cvv" i]',
    'input[name*="seed" i]',
    'input[name*="recovery" i]',
    'input[name*="private" i]',
    'input[autocomplete="current-password"]',
    'input[autocomplete="one-time-code"]',
    'textarea[name*="seed" i]',
    'textarea[name*="recovery" i]',
    'textarea[name*="private" i]',
    '[contenteditable="true"]'
  ].join(', ');

  const SUBMIT_SELECTOR = 'button, input[type="submit"], input[type="button"], [role="button"]';
  const ACTION_TEXT_RE = /(login|log in|signin|sign in|verify|confirm|continue|submit|next|send|pay|transfer|connect|unlock|recover|reset|เข้าสู่ระบบ|ลงชื่อ|ยืนยัน|ดำเนินการต่อ|ส่ง|ชำระ|โอน|เชื่อมต่อ|ปลดล็อก|กู้คืน)/i;
  let lastNoticeTimer = null;

  function applyBannerTheme(bar, value) {
    if (!bar) return;
    const dark = value !== 'light';
    bar.classList.toggle('phish-radar-theme-dark', dark);
    bar.classList.toggle('phish-radar-theme-light', !dark);
    bar.dataset.phishRadarTheme = dark ? 'dark' : 'light';
  }

  function escapeHtml(value) {
    return String(value || '').replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
  }

  function textOf(el) {
    return [el?.innerText, el?.value, el?.placeholder, el?.getAttribute?.('aria-label'), el?.getAttribute?.('title'), el?.getAttribute?.('name')]
      .filter(Boolean)
      .join(' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  function isSensitiveField(el) {
    return !!el?.matches?.(SENSITIVE_SELECTOR) || /password|otp|token|pin|seed|recovery|private|cvv|card|รหัสผ่าน|โอทีพี/i.test(textOf(el));
  }

  function formHasSensitiveData(form) {
    if (!form) return false;
    if (form.querySelector(SENSITIVE_SELECTOR)) return true;
    return /password|otp|token|pin|seed|recovery|private|cvv|card|รหัสผ่าน|โอทีพี/i.test(textOf(form));
  }

  function showNotice(message) {
    const notice = document.getElementById('phish-radar-safe-preview-notice');
    if (!notice) return;
    notice.textContent = message;
    notice.hidden = false;
    clearTimeout(lastNoticeTimer);
    lastNoticeTimer = setTimeout(() => { notice.hidden = true; }, 2600);
  }

  function lockField(field) {
    if (!field || field.dataset.phishRadarSafeLocked === '1') return;
    field.dataset.phishRadarSafeLocked = '1';
    field.classList.add('phish-radar-safe-preview-locked');
    field.setAttribute('aria-disabled', 'true');
    field.setAttribute('data-phish-radar-safe-preview', 'locked');
    if ('readOnly' in field) field.readOnly = true;
    if (field.matches?.('[contenteditable="true"]')) field.setAttribute('contenteditable', 'false');
    if ('placeholder' in field) {
      field.dataset.phishRadarOriginalPlaceholder = field.placeholder || '';
      field.placeholder = 'Safe Preview: ไม่อนุญาตให้กรอกข้อมูลนี้';
    }
  }

  function lockSensitiveFields(root = document) {
    root.querySelectorAll?.(SENSITIVE_SELECTOR).forEach(lockField);
    root.querySelectorAll?.('input, textarea, [contenteditable="true"]').forEach(el => {
      if (isSensitiveField(el)) lockField(el);
    });
    root.querySelectorAll?.('form').forEach(form => {
      if (formHasSensitiveData(form)) form.classList.add('phish-radar-safe-preview-form');
    });
  }

  function installBanner() {
    if (document.getElementById('phish-radar-safe-preview-bar')) return;
    const host = escapeHtml(location.hostname || 'เว็บไซต์นี้');
    const bar = document.createElement('div');
    bar.id = 'phish-radar-safe-preview-bar';
    applyBannerTheme(bar, 'dark');
    bar.setAttribute('role', 'region');
    bar.setAttribute('aria-label', 'Phish Radar Safe Preview');
    bar.innerHTML = [
      '<div class="phish-radar-safe-preview-copy">',
      '<strong>Safe Preview เปิดอยู่</strong>',
      '<span>คุณกำลังดู ' + host + ' แบบอ่านอย่างเดียว ช่องรหัสผ่าน OTP บัตร และ seed phrase ถูกล็อกไว้</span>',
      '</div>',
      '<div class="phish-radar-safe-preview-actions">',
      '<button type="button" data-safe-preview-action="back">กลับหน้าเตือน</button>',
      '<button type="button" data-safe-preview-action="full">เปิดแบบเต็ม</button>',
      '</div>',
      '<p id="phish-radar-safe-preview-notice" hidden></p>'
    ].join('');
    document.documentElement.appendChild(bar);

    try {
      chrome.storage.sync.get({ phishRadarTheme: 'dark' }).then(data => {
        applyBannerTheme(bar, data.phishRadarTheme);
      }).catch(() => applyBannerTheme(bar, 'dark'));
      chrome.storage.onChanged.addListener((changes, area) => {
        if (area === 'sync' && changes.phishRadarTheme) applyBannerTheme(bar, changes.phishRadarTheme.newValue);
      });
    } catch (_) {}

    bar.addEventListener('click', event => {
      const action = event.target?.dataset?.safePreviewAction;
      if (!action) return;
      event.preventDefault();
      event.stopPropagation();

      if (action === 'back') {
        chrome.runtime.sendMessage({ type: 'END_SAFE_PREVIEW', url: location.href }, () => {
          if (history.length > 1) history.back();
          else location.href = 'https://www.google.com/';
        });
      }

      if (action === 'full') {
        const ok = confirm('เปิดแบบเต็มจะปลดล็อกช่องกรอกและการส่งฟอร์มบนเว็บนี้ คุณต้องมั่นใจว่าเว็บปลอดภัยก่อนดำเนินการต่อ');
        if (!ok) return;
        chrome.runtime.sendMessage({ type: 'END_SAFE_PREVIEW', url: location.href, openFull: true }, () => location.reload());
      }
    }, true);
  }

  function blockEvent(event, message) {
    event.preventDefault();
    event.stopImmediatePropagation();
    showNotice(message);
  }

  document.addEventListener('submit', event => {
    blockEvent(event, 'Safe Preview บล็อกการส่งฟอร์มไว้แล้ว');
  }, true);

  document.addEventListener('beforeinput', event => {
    if (isSensitiveField(event.target)) blockEvent(event, 'ช่องข้อมูลสำคัญถูกล็อกใน Safe Preview');
  }, true);

  document.addEventListener('keydown', event => {
    if (isSensitiveField(event.target) && !['Tab', 'Shift', 'Escape', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
      blockEvent(event, 'ช่องข้อมูลสำคัญถูกล็อกใน Safe Preview');
    }
  }, true);

  document.addEventListener('paste', event => {
    if (isSensitiveField(event.target)) blockEvent(event, 'Safe Preview ไม่อนุญาตให้วางข้อมูลลับ');
  }, true);

  document.addEventListener('click', event => {
    const button = event.target?.closest?.(SUBMIT_SELECTOR);
    if (!button || button.closest('#phish-radar-safe-preview-bar')) return;
    const form = button.form || button.closest('form');
    if (form || ACTION_TEXT_RE.test(textOf(button))) {
      blockEvent(event, 'Safe Preview บล็อกปุ่มที่อาจส่งข้อมูลไว้ก่อน');
    }
  }, true);

  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      mutation.addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE) lockSensitiveFields(node);
      });
    }
  });

  function boot() {
    installBanner();
    lockSensitiveFields();
    observer.observe(document.documentElement, { childList: true, subtree: true });
    document.documentElement.classList.add('phish-radar-safe-preview-active');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
