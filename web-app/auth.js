const API_HOST = location.hostname === 'localhost' ? 'localhost' : '127.0.0.1';
const API_BASE = globalThis.PhishRadarRuntime?.apiBase || `http://${API_HOST}:8765`;
const CLIENT_HEADERS = { 'Content-Type': 'application/json', 'X-Phish-Radar-Client': 'web-app' };

const authMessage = document.querySelector('#authMessage');
const systemState = document.querySelector('#systemState');
const loginForm = document.querySelector('#loginForm');
const registerForm = document.querySelector('#registerForm');
const tabs = Array.from(document.querySelectorAll('[data-auth-tab]'));
let authTabsReady = false;

function suggestedDeviceName() {
  const agent = navigator.userAgent;
  const browser = /Edg\//.test(agent) ? 'Edge' : /Firefox\//.test(agent) ? 'Firefox' : /Chrome\//.test(agent) ? 'Chrome' : /Safari\//.test(agent) ? 'Safari' : 'Browser';
  const platform = /Windows/.test(agent) ? 'Windows' : /Android/.test(agent) ? 'Android' : /iPhone|iPad/.test(agent) ? 'iPhone/iPad' : /Mac OS/.test(agent) ? 'macOS' : /Linux/.test(agent) ? 'Linux' : 'อุปกรณ์นี้';
  return `${browser} บน ${platform}`;
}

function safeNextPage() {
  const next = new URLSearchParams(location.search).get('next') || 'index.html';
  if (/^(?:[a-z]+:)?\/\//i.test(next) || next.includes('\\')) return 'index.html';
  return next;
}

function setMessage(message = '', tone = '') {
  authMessage.textContent = message;
  authMessage.className = `auth-message${tone ? ` ${tone}` : ''}`;
  if (message) {
    authMessage.classList.add('is-updating');
    window.setTimeout(() => authMessage.classList.remove('is-updating'), 190);
  }
}

function setSystemState(message, tone = '') {
  systemState.lastElementChild.textContent = message;
  systemState.className = `system-state${tone ? ` ${tone}` : ''}`;
}

function setLoading(form, loading) {
  form.setAttribute('aria-busy', String(loading));
  Array.from(form.elements).forEach(element => { element.disabled = loading; });
  form.querySelector('.submit-button')?.classList.toggle('loading', loading);
}

function switchTab(name, moveFocus = false) {
  const isLogin = name === 'login';
  loginForm.hidden = !isLogin;
  registerForm.hidden = isLogin;
  const activeForm = isLogin ? loginForm : registerForm;
  if (authTabsReady) {
    activeForm.classList.remove('is-entering');
    window.requestAnimationFrame(() => activeForm.classList.add('is-entering'));
  } else {
    authTabsReady = true;
  }
  tabs.forEach(tab => {
    const selected = tab.dataset.authTab === name;
    tab.setAttribute('aria-selected', String(selected));
    tab.tabIndex = selected ? 0 : -1;
    if (selected && moveFocus) tab.focus();
  });
  setMessage();
  const url = new URL(location.href);
  if (isLogin) url.searchParams.delete('mode'); else url.searchParams.set('mode', 'register');
  history.replaceState({}, '', url);
}

function apiErrorMessage(data, fallback) {
  if (typeof data?.detail === 'string') return data.detail;
  if (Array.isArray(data?.detail)) return data.detail.map(item => item.msg).filter(Boolean).join(' · ') || fallback;
  return fallback;
}

async function authRequest(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: CLIENT_HEADERS,
    body: JSON.stringify(body)
  });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  if (!response.ok) throw new Error(apiErrorMessage(data, `ระบบตอบกลับ HTTP ${response.status}`));
  return data;
}

async function handleLogin(event) {
  event.preventDefault();
  if (!loginForm.reportValidity()) return;
  setLoading(loginForm, true);
  setMessage('กำลังตรวจสอบบัญชีและอุปกรณ์…');
  try {
    await authRequest('/auth/login', {
      identifier: loginForm.elements.identifier.value,
      password: loginForm.elements.password.value,
      device_name: loginForm.elements.device_name.value
    });
    setMessage('เข้าสู่ระบบสำเร็จ กำลังเปิดระบบ…', 'success');
    location.replace(safeNextPage());
  } catch (error) {
    setMessage(error.message || 'เข้าสู่ระบบไม่สำเร็จ', 'error');
    loginForm.elements.password.focus();
    loginForm.elements.password.select();
  } finally {
    setLoading(loginForm, false);
  }
}

async function handleRegister(event) {
  event.preventDefault();
  if (!registerForm.reportValidity()) return;
  const password = registerForm.elements.password.value;
  const confirmation = registerForm.elements.confirm_password.value;
  if (password !== confirmation) {
    setMessage('รหัสผ่านและการยืนยันรหัสผ่านไม่ตรงกัน', 'error');
    registerForm.elements.confirm_password.focus();
    return;
  }

  setLoading(registerForm, true);
  setMessage('กำลังสร้างบัญชีและลงทะเบียนอุปกรณ์…');
  try {
    await authRequest('/auth/register', {
      username: registerForm.elements.username.value,
      email: registerForm.elements.email.value,
      password,
      device_name: registerForm.elements.device_name.value
    });
    setMessage('สร้างบัญชีสำเร็จ กำลังเปิดระบบ…', 'success');
    location.replace(safeNextPage());
  } catch (error) {
    setMessage(error.message || 'สร้างบัญชีไม่สำเร็จ', 'error');
  } finally {
    setLoading(registerForm, false);
  }
}

async function checkSystem() {
  try {
    const healthResponse = await fetch(`${API_BASE}/auth/health`, { credentials: 'include' });
    const health = await healthResponse.json();
    if (!health.connected || !health.auth_schema_ready) {
      setSystemState('Database ยังไม่พร้อม', 'error');
      setMessage('เชื่อม SQL Server ได้แล้ว แต่ยังต้องรัน migration 001 และ 002', 'error');
      return;
    }
    setSystemState('ระบบบัญชีพร้อมใช้งาน', 'ready');

    const sessionResponse = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' });
    if (sessionResponse.ok) location.replace(safeNextPage());
  } catch (_) {
    setSystemState('Backend ยังไม่เปิด', 'error');
    setMessage('เปิด Backend ที่พอร์ต 8765 ก่อนเข้าสู่ระบบ', 'error');
  }
}

tabs.forEach(tab => {
  tab.addEventListener('click', () => switchTab(tab.dataset.authTab));
  tab.addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight'].includes(event.key)) return;
    event.preventDefault();
    switchTab(tab.dataset.authTab === 'login' ? 'register' : 'login', true);
  });
});

document.querySelectorAll('[data-password-toggle]').forEach(button => {
  button.addEventListener('click', () => {
    const input = document.getElementById(button.dataset.passwordToggle);
    const reveal = input.type === 'password';
    input.type = reveal ? 'text' : 'password';
    button.textContent = reveal ? 'ซ่อน' : 'แสดง';
    button.setAttribute('aria-label', reveal ? 'ซ่อนรหัสผ่าน' : 'แสดงรหัสผ่าน');
  });
});

const deviceName = suggestedDeviceName();
loginForm.elements.device_name.value = deviceName;
registerForm.elements.device_name.value = deviceName;
loginForm.addEventListener('submit', handleLogin);
registerForm.addEventListener('submit', handleRegister);
switchTab(new URLSearchParams(location.search).get('mode') === 'register' ? 'register' : 'login');
checkSystem();

if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js?v=20', { updateViaCache: 'none' }).catch(() => {});
