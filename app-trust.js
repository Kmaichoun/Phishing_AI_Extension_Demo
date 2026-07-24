(function initPhishRadarAppTrust(global) {
  'use strict';

  // Exact origins owned by this project. Keep protocol and port explicit so a
  // different local service is never trusted only because it uses localhost.
  const TRUSTED_WEB_APP_ORIGINS = Object.freeze([
    'http://app.phishradar.localhost:5505',
    'http://127.0.0.1:5505',
    'http://localhost:5505'
  ]);

  const DEFAULT_WEB_APP_URL = `${TRUSTED_WEB_APP_ORIGINS[0]}/login.html`;

  function normalizeHttpOrigin(value) {
    try {
      const url = new URL(String(value || ''));
      if (!['http:', 'https:'].includes(url.protocol)) return '';
      return url.origin;
    } catch (_) {
      return '';
    }
  }

  function isTrustedWebAppUrl(value) {
    const origin = normalizeHttpOrigin(value);
    return !!origin && TRUSTED_WEB_APP_ORIGINS.includes(origin);
  }

  function createTrustedResult(value) {
    let hostname = 'Phish Radar Web App';
    try { hostname = new URL(String(value || DEFAULT_WEB_APP_URL)).hostname; } catch (_) {}
    return {
      input: String(value || ''),
      url: String(value || DEFAULT_WEB_APP_URL),
      hostname,
      domain: hostname,
      score: 0,
      ruleScore: 0,
      mlScore: null,
      finalScore: 0,
      level: 'low',
      levelText: 'Web App ของระบบ',
      safe: true,
      trustedWebApp: true,
      summary: 'Trusted Phish Radar Web App',
      reasons: [{
        points: 0,
        label: 'โดเมน Web App ของ Phish Radar AI',
        detail: 'Origin ตรงกับรายการที่ระบบกำหนดไว้แบบ protocol + hostname + port',
        category: 'trust'
      }],
      threatTypes: []
    };
  }

  const api = {
    TRUSTED_WEB_APP_ORIGINS,
    DEFAULT_WEB_APP_URL,
    normalizeHttpOrigin,
    isTrustedWebAppUrl,
    createTrustedResult
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  global.PhishRadarAppTrust = api;
})(typeof globalThis !== 'undefined' ? globalThis : window);
