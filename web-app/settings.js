(() => {
  'use strict';

  const API_BASE = globalThis.PhishRadarRuntime?.apiBase || 'http://127.0.0.1:8765';
  const $ = selector => document.querySelector(selector);
  const state = { user: null };

  const elements = {
    accountSummary: $('#accountSummary'), accountAvatar: $('#accountAvatar'), accountName: $('#accountName'), accountRole: $('#accountRole'),
    profileAvatar: $('#profileAvatar'), profileUsername: $('#profileUsername'), profileEmail: $('#profileEmail'), profileRole: $('#profileRole'), profileDevice: $('#profileDevice'),
    profileForm: $('#profileForm'), profileMessage: $('#profileMessage'), passwordForm: $('#passwordForm'), passwordMessage: $('#passwordMessage'), logoutButton: $('#logoutButton')
  };

  function loginUrl() {
    return `login.html?next=${encodeURIComponent('settings.html')}`;
  }

  function redirectToLogin() {
    location.replace(loginUrl());
  }

  function apiErrorMessage(payload, fallback) {
    if (typeof payload?.detail === 'string') return payload.detail;
    if (Array.isArray(payload?.detail) && payload.detail[0]?.msg) return payload.detail[0].msg;
    return fallback;
  }

  async function accountRequest(path, options = {}) {
    const response = await fetch(`${API_BASE}/auth${path}`, {
      credentials: 'include',
      ...options,
      headers: {
        'Content-Type': 'application/json',
        'X-Phish-Radar-Client': 'web-app',
        ...(options.headers || {})
      }
    });
    const payload = response.status === 204 ? null : await response.json().catch(() => null);
    if (!response.ok) throw new Error(apiErrorMessage(payload, `ดำเนินการไม่สำเร็จ (HTTP ${response.status})`));
    return payload;
  }

  function renderUser(user) {
    state.user = user;
    const initial = (user.username || 'U').slice(0, 1).toUpperCase();
    const role = user.role === 'admin' ? 'Admin' : 'User';
    elements.accountAvatar.textContent = initial;
    elements.accountName.textContent = user.username;
    elements.accountRole.textContent = role;
    elements.accountRole.classList.toggle('admin', user.role === 'admin');
    elements.profileAvatar.textContent = initial;
    elements.profileUsername.textContent = user.username;
    elements.profileEmail.textContent = user.email;
    elements.profileRole.textContent = role;
    elements.profileDevice.textContent = user.device_name || '-';
    elements.profileForm.elements.username.value = user.username;
    elements.profileForm.elements.email.value = user.email;
    elements.accountSummary.hidden = false;
    document.body.classList.toggle('role-admin', user.role === 'admin');
    document.body.classList.remove('auth-pending');
  }

  function setMessage(element, message = '', tone = '') {
    element.textContent = message;
    element.className = `settings-message${tone ? ` ${tone}` : ''}`;
  }

  function setLoading(form, loading, pendingLabel) {
    const button = form.querySelector('button[type="submit"]');
    const label = button.querySelector('[data-button-label]');
    if (!button.dataset.defaultLabel) button.dataset.defaultLabel = label.textContent;
    button.disabled = loading;
    label.textContent = loading ? pendingLabel : button.dataset.defaultLabel;
    Array.from(form.elements).forEach(control => {
      if (control !== button) control.disabled = loading;
    });
  }

  async function loadUser() {
    try {
      const response = await fetch(`${API_BASE}/auth/me`, { credentials: 'include' });
      if (response.status === 401) return redirectToLogin();
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      renderUser(await response.json());
    } catch (_) {
      redirectToLogin();
    }
  }

  async function updateProfile(event) {
    event.preventDefault();
    if (!elements.profileForm.reportValidity()) return;
    const formData = new FormData(elements.profileForm);
    setMessage(elements.profileMessage);
    setLoading(elements.profileForm, true, 'กำลังบันทึก…');
    try {
      const user = await accountRequest('/profile', {
        method: 'PATCH',
        body: JSON.stringify({
          username: String(formData.get('username') || '').trim(),
          email: String(formData.get('email') || '').trim(),
          current_password: String(formData.get('current_password') || '')
        })
      });
      renderUser(user);
      elements.profileForm.elements.current_password.value = '';
      setMessage(elements.profileMessage, 'บันทึกชื่อผู้ใช้และอีเมลแล้ว', 'success');
    } catch (error) {
      setMessage(elements.profileMessage, error.message || 'บันทึกข้อมูลไม่สำเร็จ', 'error');
      elements.profileForm.elements.current_password.focus();
    } finally {
      setLoading(elements.profileForm, false, 'กำลังบันทึก…');
    }
  }

  async function changePassword(event) {
    event.preventDefault();
    if (!elements.passwordForm.reportValidity()) return;
    const formData = new FormData(elements.passwordForm);
    const currentPassword = String(formData.get('current_password') || '');
    const newPassword = String(formData.get('new_password') || '');
    const confirmation = String(formData.get('confirm_password') || '');
    if (newPassword !== confirmation) {
      setMessage(elements.passwordMessage, 'รหัสผ่านใหม่และการยืนยันไม่ตรงกัน', 'error');
      elements.passwordForm.elements.confirm_password.focus();
      return;
    }
    if (newPassword === currentPassword) {
      setMessage(elements.passwordMessage, 'รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านปัจจุบัน', 'error');
      elements.passwordForm.elements.new_password.focus();
      return;
    }

    setMessage(elements.passwordMessage);
    setLoading(elements.passwordForm, true, 'กำลังเปลี่ยน…');
    try {
      const result = await accountRequest('/change-password', {
        method: 'POST',
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword })
      });
      elements.passwordForm.reset();
      const sessionText = result.other_sessions_revoked > 0
        ? ` และออกจากระบบอีก ${result.other_sessions_revoked} Session แล้ว`
        : '';
      setMessage(elements.passwordMessage, `เปลี่ยนรหัสผ่านสำเร็จ${sessionText}`, 'success');
    } catch (error) {
      setMessage(elements.passwordMessage, error.message || 'เปลี่ยนรหัสผ่านไม่สำเร็จ', 'error');
      elements.passwordForm.elements.current_password.focus();
    } finally {
      setLoading(elements.passwordForm, false, 'กำลังเปลี่ยน…');
    }
  }

  function togglePassword(button) {
    const input = document.getElementById(button.dataset.togglePassword);
    if (!input) return;
    const showing = input.type === 'text';
    input.type = showing ? 'password' : 'text';
    button.textContent = showing ? 'แสดง' : 'ซ่อน';
    button.setAttribute('aria-label', showing ? 'แสดงรหัสผ่าน' : 'ซ่อนรหัสผ่าน');
    input.focus({ preventScroll: true });
  }

  async function logout() {
    elements.logoutButton.disabled = true;
    elements.logoutButton.textContent = 'กำลังออก…';
    try {
      await accountRequest('/logout', { method: 'POST', body: undefined });
      location.replace('login.html');
    } catch (_) {
      elements.logoutButton.disabled = false;
      elements.logoutButton.textContent = 'ลองออกอีกครั้ง';
    }
  }

  elements.profileForm.addEventListener('submit', updateProfile);
  elements.passwordForm.addEventListener('submit', changePassword);
  elements.logoutButton.addEventListener('click', logout);
  document.querySelectorAll('[data-toggle-password]').forEach(button => button.addEventListener('click', () => togglePassword(button)));
  loadUser();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js?v=20', { updateViaCache: 'none' }).catch(() => {});
})();
