import { runtime } from './runtime';

const CLIENT_HEADERS = { 'X-Phish-Radar-Client': 'web-app' };

function apiErrorMessage(payload, fallback) {
  if (typeof payload?.detail === 'string') return payload.detail;
  if (Array.isArray(payload?.detail)) {
    return payload.detail.map(item => item?.msg).filter(Boolean).join(' · ') || fallback;
  }
  return fallback;
}

async function request(path, options = {}) {
  const response = await fetch(`${runtime.apiBase}${path}`, {
    credentials: options.credentials ?? 'include',
    ...options,
    headers: {
      ...CLIENT_HEADERS,
      ...(options.body ? { 'Content-Type': 'application/json' } : {}),
      ...(options.headers || {})
    }
  });
  const payload = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(apiErrorMessage(payload, `ระบบตอบกลับ HTTP ${response.status}`));
  }
  return payload;
}

export const api = {
  health: () => request('/health', { credentials: 'omit' }),
  authHealth: () => request('/auth/health'),
  me: () => request('/auth/me'),
  login: body => request('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  register: body => request('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  updateProfile: body => request('/auth/profile', { method: 'PATCH', body: JSON.stringify(body) }),
  changePassword: body => request('/auth/change-password', { method: 'POST', body: JSON.stringify(body) }),
  predict: body => request('/predict', { method: 'POST', credentials: 'omit', body: JSON.stringify(body) }),
  explain: body => request('/explain', { method: 'POST', credentials: 'omit', body: JSON.stringify(body) }),
  feedback: body => request('/feedback', { method: 'POST', credentials: 'omit', body: JSON.stringify(body) }),
  history: (limit = 50) => request(`/history?limit=${limit}`),
  createHistory: body => request('/history', { method: 'POST', body: JSON.stringify(body) }),
  clearHistory: () => request('/history', { method: 'DELETE' })
};
