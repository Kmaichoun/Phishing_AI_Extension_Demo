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
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), path === '/explain' ? 120000 : 15000);
  try {
  const response = await fetch(`${runtime.apiBase}${path}`, {
    credentials: options.credentials ?? 'include',
    ...options,
    signal: controller.signal,
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
  } catch (error) {
    if (controller.signal.aborted) {
      throw new Error('เซิร์ฟเวอร์ตอบกลับนานเกินไป กรุณาตรวจว่า Backend และ MySQL ทำงานอยู่ แล้วลองใหม่');
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
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
  clearHistory: () => request('/history', { method: 'DELETE' }),
  searchHistory: params => request(`/history?${new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null))}`),
  stats: () => request('/workspace/stats'),
  security: () => request('/workspace/security'),
  revokeSession: id => request(`/workspace/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  revokeDevice: id => request(`/workspace/devices/${id}`, { method: 'DELETE' }),
  accountFeedback: body => request('/workspace/feedback', { method: 'POST', body: JSON.stringify(body) }),
  adminUsers: (q = '', offset = 0) => request(`/workspace/admin/users?${new URLSearchParams({ q, offset })}`),
  adminUpdateUser: (id, body) => request(`/workspace/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  adminFeedback: (state = 'pending', offset = 0) => request(`/workspace/admin/feedback?${new URLSearchParams({ state, offset })}`),
  adminReview: (id, body) => request(`/workspace/admin/feedback/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  adminAudit: (offset = 0) => request(`/workspace/admin/audit?offset=${offset}`),
  adminModels: () => request('/workspace/admin/models'),
  adminFeedbackExport: (offset = 0) => request(`/workspace/admin/feedback-export?offset=${offset}`)
};
