(() => {
  'use strict';

  const STORAGE_KEY = 'phishRadarTheme';
  const validTheme = value => value === 'light' || value === 'dark';

  function currentTheme() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (validTheme(stored)) return stored;
    } catch (_) {}
    return 'dark';
  }

  function renderTheme(theme, persist = true) {
    const next = validTheme(theme) ? theme : 'dark';
    document.documentElement.dataset.theme = next;
    document.documentElement.style.colorScheme = next;
    if (persist) {
      try { localStorage.setItem(STORAGE_KEY, next); } catch (_) {}
    }

    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      const dark = next === 'dark';
      button.setAttribute('aria-label', dark ? 'เปลี่ยนเป็นโหมดสว่าง' : 'เปลี่ยนเป็นโหมดมืด');
      button.setAttribute('aria-pressed', String(dark));
      const label = button.querySelector('[data-theme-label]');
      if (label) label.textContent = dark ? 'Light' : 'Dark';
    });
  }

  function bindThemeControls() {
    renderTheme(document.documentElement.dataset.theme || currentTheme(), false);
    document.querySelectorAll('[data-theme-toggle]').forEach(button => {
      button.addEventListener('click', () => {
        const next = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (document.startViewTransition && !reduceMotion) {
          document.startViewTransition(() => renderTheme(next));
        } else {
          renderTheme(next);
        }
      });
    });
  }

  renderTheme(currentTheme(), false);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindThemeControls, { once: true });
  else bindThemeControls();

  window.PhishRadarTheme = { set: renderTheme, get: () => document.documentElement.dataset.theme || 'dark' };
})();
