import { useEffect, useMemo, useState } from 'react';
import brandIcon from '../../assets/icon128.png';
import { MotionFrame } from '../components/MotionFrame';
import { PasswordField } from '../components/PasswordField';
import { ThemeToggle } from '../components/ThemeToggle';
import { useAuth } from '../contexts/AuthContext';
import { useRouter } from '../contexts/RouterContext';
import { api } from '../services/api';

function suggestedDeviceName() {
  const agent = navigator.userAgent;
  const browser = /Edg\//.test(agent)
    ? 'Edge'
    : /Firefox\//.test(agent)
      ? 'Firefox'
      : /Chrome\//.test(agent)
        ? 'Chrome'
        : /Safari\//.test(agent)
          ? 'Safari'
          : 'Browser';
  const platform = /Windows/.test(agent)
    ? 'Windows'
    : /Android/.test(agent)
      ? 'Android'
      : /iPhone|iPad/.test(agent)
        ? 'iPhone/iPad'
        : /Mac OS/.test(agent)
          ? 'macOS'
          : /Linux/.test(agent)
            ? 'Linux'
            : 'อุปกรณ์นี้';
  return `${browser} บน ${platform}`;
}

function safeNext(search) {
  const target = new URLSearchParams(search).get('next') || '/scan';
  if (!target.startsWith('/') || target.startsWith('//') || target.includes('\\')) return '/scan';
  return target;
}

export function LoginPage() {
  const { search, navigate } = useRouter();
  const { user, loading: sessionLoading, login, register } = useAuth();
  const nextPage = useMemo(() => safeNext(search), [search]);
  const initialMode = new URLSearchParams(search).get('mode') === 'register'
    ? 'register'
    : 'login';
  const [mode, setMode] = useState(initialMode);
  const [message, setMessage] = useState({ text: '', tone: '' });
  const [systemState, setSystemState] = useState({
    label: 'กำลังตรวจสอบระบบ',
    tone: ''
  });
  const [submitting, setSubmitting] = useState(false);
  const deviceName = useMemo(suggestedDeviceName, []);

  useEffect(() => {
    document.title = 'เข้าสู่ระบบ | Phish Radar AI';
    document.body.classList.add('login-page');
    return () => document.body.classList.remove('login-page');
  }, []);

  useEffect(() => {
    if (!sessionLoading && user) navigate(nextPage, { replace: true });
  }, [navigate, nextPage, sessionLoading, user]);

  useEffect(() => {
    let active = true;
    async function checkSystem() {
      try {
        const health = await api.authHealth();
        if (!active) return;
        if (!health.connected || !health.auth_schema_ready) {
          setSystemState({ label: 'Database ยังไม่พร้อม', tone: 'error' });
          setMessage({
            text: 'เชื่อม MySQL/MariaDB ได้แล้ว แต่ยังต้องรัน migration ของระบบบัญชีให้ครบ',
            tone: 'error'
          });
          return;
        }
        setSystemState({ label: 'ระบบบัญชีพร้อมใช้งาน', tone: 'ready' });
      } catch {
        if (!active) return;
        setSystemState({ label: 'Backend ยังไม่เปิด', tone: 'error' });
        setMessage({ text: 'เปิด Backend ที่พอร์ต 8765 ก่อนเข้าสู่ระบบ', tone: 'error' });
      }
    }
    checkSystem();
    return () => { active = false; };
  }, []);

  function switchMode(nextMode) {
    setMode(nextMode);
    setMessage({ text: '', tone: '' });
    const parameters = new URLSearchParams(search);
    if (nextMode === 'register') parameters.set('mode', 'register');
    else parameters.delete('mode');
    const query = parameters.toString();
    navigate(`/login${query ? `?${query}` : ''}`, { replace: true });
  }

  async function handleLogin(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setSubmitting(true);
    setMessage({ text: 'กำลังตรวจสอบบัญชีและอุปกรณ์…', tone: '' });
    try {
      await login({
        identifier: String(data.get('identifier') || '').trim(),
        password: String(data.get('password') || ''),
        device_name: String(data.get('device_name') || '').trim()
      });
      setMessage({ text: 'เข้าสู่ระบบสำเร็จ กำลังเปิดระบบ…', tone: 'success' });
      navigate(nextPage, { replace: true });
    } catch (error) {
      setMessage({ text: error.message || 'เข้าสู่ระบบไม่สำเร็จ', tone: 'error' });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRegister(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const password = String(data.get('password') || '');
    const confirmation = String(data.get('confirm_password') || '');
    if (password !== confirmation) {
      setMessage({ text: 'รหัสผ่านและการยืนยันรหัสผ่านไม่ตรงกัน', tone: 'error' });
      return;
    }

    setSubmitting(true);
    setMessage({ text: 'กำลังสร้างบัญชีและลงทะเบียนอุปกรณ์…', tone: '' });
    try {
      await register({
        username: String(data.get('username') || '').trim(),
        email: String(data.get('email') || '').trim(),
        password,
        device_name: String(data.get('device_name') || '').trim()
      });
      setMessage({ text: 'สร้างบัญชีสำเร็จ กำลังเปิดระบบ…', tone: 'success' });
      navigate(nextPage, { replace: true });
    } catch (error) {
      setMessage({ text: error.message || 'สร้างบัญชีไม่สำเร็จ', tone: 'error' });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <MotionFrame className="login-react-shell">
      <a className="skip-link" href="#authMain">ข้ามไปยังแบบฟอร์ม</a>
      <header className="auth-header" data-reveal>
        <a className="auth-brand" href="#/login" aria-label="Phish Radar AI หน้าเข้าสู่ระบบ">
          <img src={brandIcon} alt="" width="42" height="42" />
          <span><strong>Phish Radar AI</strong><small>React secure access</small></span>
        </a>
        <div className="auth-header-actions">
          <ThemeToggle />
          <div className={`system-state ${systemState.tone}`} role="status">
            <span aria-hidden="true" />
            <span>{systemState.label}</span>
          </div>
        </div>
      </header>

      <main id="authMain" className="auth-layout">
        <section className="auth-intro" aria-labelledby="introTitle" data-reveal>
          <h1 id="introTitle">ตรวจลิงก์อย่างมั่นใจ<br />ในพื้นที่ของคุณ</h1>
          <p className="intro-copy">
            เข้าสู่ระบบเพื่อใช้งาน URL Scanner, QR Scanner และ Dashboard
            โดยอุปกรณ์ที่เชื่อมต่อจะถูกบันทึกเพื่อช่วยตรวจสอบความปลอดภัยของบัญชี
          </p>
          <div className="auth-radar" aria-hidden="true">
            <div className="auth-radar-visual">
              <span className="auth-radar-ring ring-one" />
              <span className="auth-radar-ring ring-two" />
              <span className="auth-radar-ring ring-three" />
              <span className="auth-radar-sweep" />
              <span className="auth-radar-blip blip-one" />
              <span className="auth-radar-blip blip-two" />
              <span className="auth-radar-blip blip-three" />
              <span className="auth-radar-core"><img src={brandIcon} alt="" /></span>
            </div>
            <div className="auth-radar-copy">
              <span className="auth-radar-live"><i /> Real-time protection</span>
              <strong>ตรวจจับหลายชั้น</strong>
              <small>Rule-based · ML · LLM</small>
            </div>
          </div>
        </section>

        <section className="auth-panel" aria-labelledby="panelTitle" data-reveal>
          <div className="panel-heading">
            <p className="eyebrow">ยินดีต้อนรับ</p>
            <h2 id="panelTitle">เข้าสู่ Phish Radar</h2>
          </div>

          <div className="auth-tabs" role="tablist" aria-label="เลือกรูปแบบการยืนยันตัวตน">
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'login'}
              onClick={() => switchMode('login')}
            >
              เข้าสู่ระบบ
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === 'register'}
              onClick={() => switchMode('register')}
            >
              สมัครสมาชิก
            </button>
          </div>

          <div className={`auth-message ${message.tone}`} role="status" aria-live="polite">
            {message.text}
          </div>

          {mode === 'login' ? (
            <form className="auth-form react-form-enter" onSubmit={handleLogin} aria-busy={submitting}>
              <div className="field">
                <label htmlFor="loginIdentifier">ชื่อผู้ใช้หรืออีเมล</label>
                <input
                  id="loginIdentifier"
                  name="identifier"
                  type="text"
                  autoComplete="username"
                  maxLength="254"
                  placeholder="username หรือ name@example.com"
                  required
                  disabled={submitting}
                />
              </div>
              <div className="field">
                <label htmlFor="loginPassword">รหัสผ่าน</label>
                <PasswordField
                  id="loginPassword"
                  name="password"
                  autoComplete="current-password"
                  maxLength="128"
                  placeholder="กรอกรหัสผ่าน"
                  required
                  disabled={submitting}
                />
              </div>
              <div className="field">
                <label htmlFor="loginDevice">ชื่ออุปกรณ์นี้</label>
                <input
                  id="loginDevice"
                  name="device_name"
                  type="text"
                  autoComplete="off"
                  maxLength="200"
                  defaultValue={deviceName}
                  required
                  disabled={submitting}
                />
                <small>ตั้งชื่อที่จำง่าย เช่น “Chrome บนโน้ตบุ๊ก”</small>
              </div>
              <button className={`submit-button ${submitting ? 'loading' : ''}`} type="submit" disabled={submitting}>
                <span>เข้าสู่ระบบ</span><span className="button-loader" aria-hidden="true" />
              </button>
            </form>
          ) : (
            <form className="auth-form react-form-enter" onSubmit={handleRegister} aria-busy={submitting}>
              <div className="field-row">
                <div className="field">
                  <label htmlFor="registerUsername">Username</label>
                  <input id="registerUsername" name="username" type="text" autoComplete="username" minLength="3" maxLength="50" placeholder="อย่างน้อย 3 ตัวอักษร" required disabled={submitting} />
                </div>
                <div className="field">
                  <label htmlFor="registerEmail">อีเมล</label>
                  <input id="registerEmail" name="email" type="email" inputMode="email" autoComplete="email" maxLength="254" placeholder="name@example.com" required disabled={submitting} />
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label htmlFor="registerPassword">รหัสผ่าน</label>
                  <PasswordField id="registerPassword" name="password" autoComplete="new-password" minLength="12" maxLength="128" placeholder="อย่างน้อย 12 ตัวอักษร" required disabled={submitting} />
                </div>
                <div className="field">
                  <label htmlFor="registerConfirm">ยืนยันรหัสผ่าน</label>
                  <PasswordField id="registerConfirm" name="confirm_password" autoComplete="new-password" minLength="12" maxLength="128" placeholder="กรอกอีกครั้ง" required disabled={submitting} />
                </div>
              </div>
              <p className="form-hint">ใช้รหัสผ่านอย่างน้อย 12 ตัวอักษร และไม่ควรใช้ซ้ำกับระบบอื่น</p>
              <div className="field">
                <label htmlFor="registerDevice">ชื่ออุปกรณ์นี้</label>
                <input id="registerDevice" name="device_name" type="text" autoComplete="off" maxLength="200" defaultValue={deviceName} required disabled={submitting} />
              </div>
              <button className={`submit-button ${submitting ? 'loading' : ''}`} type="submit" disabled={submitting}>
                <span>สร้างบัญชี User</span><span className="button-loader" aria-hidden="true" />
              </button>
            </form>
          )}
        </section>
      </main>
      <footer className="auth-footer" data-reveal>Phish Radar AI · React local development environment</footer>
    </MotionFrame>
  );
}
