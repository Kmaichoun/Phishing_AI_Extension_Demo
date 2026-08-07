(() => {
  'use strict';

  function applyTheme(value) {
    const theme = value === 'light' ? 'light' : 'dark';
    const dark = theme === 'dark';
    document.documentElement.classList.toggle('phish-radar-theme-dark', dark);
    document.documentElement.classList.toggle('phish-radar-theme-light', !dark);
    document.body?.classList.toggle('phish-radar-theme-dark', dark);
    document.body?.classList.toggle('phish-radar-theme-light', !dark);
    if (document.body) document.body.dataset.phishRadarTheme = theme;
  }

  applyTheme('dark');

  try {
    chrome.storage.sync.get({ phishRadarTheme: 'dark' }).then(data => {
      applyTheme(data.phishRadarTheme);
    }).catch(() => applyTheme('dark'));

    chrome.storage.onChanged.addListener((changes, area) => {
      if (area === 'sync' && changes.phishRadarTheme) {
        applyTheme(changes.phishRadarTheme.newValue);
      }
    });
  } catch (_) {
    applyTheme('dark');
  }
})();
