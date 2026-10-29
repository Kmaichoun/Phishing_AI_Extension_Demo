import { useEffect, useState } from 'react';
import { Icon } from '../components/Icon';
import { PasswordField } from '../components/PasswordField';
import { useAuth } from '../contexts/AuthContext';
import { Link } from '../contexts/RouterContext';
import { api } from '../services/api';

export function SettingsPage() {
  const { user, setUser } = useAuth();
  const [profile, setProfile] = useState({
    username: user?.username || '',
    email: user?.email || ''
  });
  const [profileMessage, setProfileMessage] = useState({ text: '', tone: '' });
  const [passwordMessage, setPasswordMessage] = useState({ text: '', tone: '' });
  const [profileLoading, setProfileLoading] = useState(false);
  const [passwordLoading, setPasswordLoading] = useState(false);

  useEffect(() => {
    document.title = 'ตั้งค่าบัญชี | Phish Radar AI';
    document.body.classList.add('settings-page');
    return () => document.body.classList.remove('settings-page');
  }, []);

  useEffect(() => {
    setProfile({ username: user?.username || '', email: user?.email || '' });
  }, [user]);

  async function updateProfile(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setProfileLoading(true);
    setProfileMessage({ text: '', tone: '' });
    try {
      const updated = await api.updateProfile({
        username: profile.username.trim(),
        email: profile.email.trim(),
        current_password: String(data.get('current_password') || '')
      });
      setUser(updated);
      form.elements.current_password.value = '';
      setProfileMessage({ text: 'บันทึกชื่อผู้ใช้และอีเมลแล้ว', tone: 'success' });
    } catch (error) {
      setProfileMessage({ text: error.message || 'บันทึกข้อมูลไม่สำเร็จ', tone: 'error' });
    } finally {
      setProfileLoading(false);
    }
  }

  async function changePassword(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const currentPassword = String(data.get('current_password') || '');
    const newPassword = String(data.get('new_password') || '');
    const confirmation = String(data.get('confirm_password') || '');
    if (newPassword !== confirmation) {
      setPasswordMessage({ text: 'รหัสผ่านใหม่และการยืนยันไม่ตรงกัน', tone: 'error' });
      return;
    }
    if (newPassword === currentPassword) {
      setPasswordMessage({ text: 'รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านปัจจุบัน', tone: 'error' });
      return;
    }

    setPasswordLoading(true);
    setPasswordMessage({ text: '', tone: '' });
    try {
      const result = await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword
      });
      form.reset();
      const sessionText = result.other_sessions_revoked > 0
        ? ` และออกจากระบบอีก ${result.other_sessions_revoked} Session แล้ว`
        : '';
      setPasswordMessage({ text: `เปลี่ยนรหัสผ่านสำเร็จ${sessionText}`, tone: 'success' });
    } catch (error) {
      setPasswordMessage({ text: error.message || 'เปลี่ยนรหัสผ่านไม่สำเร็จ', tone: 'error' });
    } finally {
      setPasswordLoading(false);
    }
  }

  const initial = (user?.username || 'U').slice(0, 1).toUpperCase();
  const role = user?.role === 'admin' ? 'Admin' : 'User';

  return (
      <section id="settingsMain" className="workspace-page workspace-settings">
        <header className="settings-heading" data-reveal>
          <p className="eyebrow">บัญชีและความปลอดภัย</p>
          <h1>ตั้งค่าบัญชี</h1>
          <p>แก้ไขข้อมูลที่ใช้เข้าสู่ระบบ โดยไม่มีสิทธิ์เปลี่ยน Role ของตัวเองจากหน้านี้</p>
          <Link to="/security">จัดการ Session</Link>
        </header>

        <section className="identity-strip" aria-labelledby="identityTitle" data-reveal>
          <div className="profile-avatar" aria-hidden="true">{initial}</div>
          <div className="identity-primary">
            <h2 id="identityTitle">{user?.username}</h2>
            <p>{user?.email}</p>
          </div>
          <dl className="identity-meta">
            <div><dt>สิทธิ์</dt><dd>{role}</dd></div>
          </dl>
        </section>

        <div className="settings-grid">
          <section className="panel settings-panel" aria-labelledby="profileFormTitle" data-reveal>
            <div className="section-heading">
              <span className="section-icon" aria-hidden="true">Aa</span>
              <div><h2 id="profileFormTitle">ข้อมูลโปรไฟล์</h2><p>Username และ Email ใช้เข้าสู่ระบบได้ทั้งคู่</p></div>
            </div>
            <form className="settings-form" onSubmit={updateProfile}>
              <div className="field">
                <label htmlFor="username">ชื่อผู้ใช้</label>
                <input id="username" name="username" type="text" minLength="3" maxLength="50" autoComplete="username" spellCheck="false" required value={profile.username} onChange={event => setProfile(value => ({ ...value, username: event.target.value }))} disabled={profileLoading} />
                <small>3–50 ตัวอักษร ห้ามมีช่องว่างหรือเครื่องหมาย @</small>
              </div>
              <div className="field">
                <label htmlFor="email">อีเมล</label>
                <input id="email" name="email" type="email" maxLength="254" autoComplete="email" spellCheck="false" required value={profile.email} onChange={event => setProfile(value => ({ ...value, email: event.target.value }))} disabled={profileLoading} />
              </div>
              <div className="field">
                <label htmlFor="profileCurrentPassword">รหัสผ่านปัจจุบันเพื่อยืนยัน</label>
                <PasswordField id="profileCurrentPassword" name="current_password" maxLength="128" autoComplete="current-password" required disabled={profileLoading} />
              </div>
              <p className={`settings-message ${profileMessage.tone}`} role="status" aria-live="polite">{profileMessage.text}</p>
              <button className="submit-button" type="submit" disabled={profileLoading}>
                <span>{profileLoading ? 'กำลังบันทึก…' : 'บันทึกข้อมูล'}</span>
              </button>
            </form>
          </section>

          <section className="panel settings-panel" aria-labelledby="passwordFormTitle" data-reveal>
            <div className="section-heading">
              <span className="section-icon" aria-hidden="true">02</span>
              <div><h2 id="passwordFormTitle">เปลี่ยนรหัสผ่าน</h2><p>หลังบันทึก ระบบจะออกจาก Session อื่นเพื่อป้องกันบัญชี</p></div>
            </div>
            <form className="settings-form" onSubmit={changePassword}>
              <div className="field">
                <label htmlFor="passwordCurrent">รหัสผ่านปัจจุบัน</label>
                <PasswordField id="passwordCurrent" name="current_password" maxLength="128" autoComplete="current-password" required disabled={passwordLoading} />
              </div>
              <div className="field-row">
                <div className="field">
                  <label htmlFor="newPassword">รหัสผ่านใหม่</label>
                  <PasswordField id="newPassword" name="new_password" minLength="12" maxLength="128" autoComplete="new-password" required disabled={passwordLoading} />
                  <small>อย่างน้อย 12 ตัวอักษร</small>
                </div>
                <div className="field">
                  <label htmlFor="confirmPassword">ยืนยันรหัสผ่านใหม่</label>
                  <PasswordField id="confirmPassword" name="confirm_password" minLength="12" maxLength="128" autoComplete="new-password" required disabled={passwordLoading} />
                </div>
              </div>
              <p className={`settings-message ${passwordMessage.tone}`} role="status" aria-live="polite">{passwordMessage.text}</p>
              <button className="submit-button" type="submit" disabled={passwordLoading}>
                <span>{passwordLoading ? 'กำลังเปลี่ยน…' : 'เปลี่ยนรหัสผ่าน'}</span>
              </button>
            </form>
          </section>
        </div>

        <aside className="security-note" aria-label="ข้อมูลความปลอดภัย" data-reveal>
          <Icon name="shield" />
          <p>
            <strong>ระบบไม่บันทึกรหัสผ่านจริง</strong> รหัสผ่านใหม่จะถูกแปลงเป็น Password Hash
            ก่อนเก็บใน MySQL/MariaDB และการแก้ข้อมูลทุกครั้งต้องยืนยันรหัสผ่านปัจจุบัน
          </p>
        </aside>
      </section>
  );
}
