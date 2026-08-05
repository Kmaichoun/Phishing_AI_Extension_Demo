const developmentBackends = {
  'app.phishradar.localhost': 'http://api.phishradar.localhost:8765',
  '127.0.0.1': 'http://127.0.0.1:8765',
  localhost: 'http://localhost:8765'
};

function withoutTrailingSlash(value) {
  return String(value || '').trim().replace(/\/+$/, '');
}

const host = window.location.hostname.toLowerCase();
const configured = withoutTrailingSlash(import.meta.env.VITE_API_BASE);

export const runtime = Object.freeze({
  apiBase: configured || developmentBackends[host] || window.location.origin,
  webAppOrigin: window.location.origin,
  isLocalDomain: host === 'app.phishradar.localhost'
});
