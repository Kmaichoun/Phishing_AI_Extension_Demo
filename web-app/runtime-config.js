(() => {
  'use strict';

  const host = location.hostname.toLowerCase();
  const developmentBackends = {
    'app.phishradar.localhost': 'http://api.phishradar.localhost:8765',
    '127.0.0.1': 'http://127.0.0.1:8765',
    'localhost': 'http://localhost:8765'
  };

  // A production deployment can define window.PHISH_RADAR_API_BASE before this
  // file. Otherwise unknown public hosts use a same-origin reverse proxy.
  const configured = typeof globalThis.PHISH_RADAR_API_BASE === 'string'
    ? globalThis.PHISH_RADAR_API_BASE.trim().replace(/\/+$/, '')
    : '';
  const apiBase = configured || developmentBackends[host] || location.origin;

  globalThis.PhishRadarRuntime = Object.freeze({
    apiBase,
    webAppOrigin: location.origin,
    isLocalDomain: host === 'app.phishradar.localhost'
  });
})();
