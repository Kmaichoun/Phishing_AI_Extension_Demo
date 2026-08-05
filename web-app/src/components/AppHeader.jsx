import brandIcon from '../../assets/icon128.png';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import { Link, useRouter } from '../contexts/RouterContext';
import { Icon } from './Icon';
import { ThemeToggle } from './ThemeToggle';

export function AppHeader() {
  const { user, logout } = useAuth();
  const { privacyMode, setPrivacyMode, backendStatus, checkHealth } = useApp();
  const { navigate } = useRouter();

  async function handleLogout() {
    try {
      await logout();
      navigate('/login', { replace: true });
    } catch {
      // The session stays visible so the user can retry.
    }
  }

  return (
    <header className="topbar">
      <Link className="brand" to="/scan" aria-label="Phish Radar AI">
        <img src={brandIcon} alt="" />
        <span><strong>Phish Radar AI</strong><small>React Web App</small></span>
      </Link>

      <nav className="tabs" aria-label="เมนูหลัก">
        <Link to="/scan">ตรวจลิงก์</Link>
        <Link to="/qr">QR</Link>
        <Link to="/dashboard">Dashboard</Link>
      </nav>

      <div className="top-actions">
        <ThemeToggle />
        <label
          className="privacy-toggle"
          title="เปิดแล้วจะวิเคราะห์ในเครื่องเป็นหลัก และไม่ส่ง URL หรือ feedback ไป server"
        >
          <input
            id="privacyMode"
            type="checkbox"
            checked={privacyMode}
            onChange={event => setPrivacyMode(event.target.checked)}
          />
          <span>Privacy Mode</span>
        </label>
        <button
          id="backendStatus"
          className={`status ${backendStatus.online === true ? 'online' : ''} ${backendStatus.online === false ? 'offline' : ''} ${backendStatus.online === null ? 'checking' : ''}`}
          type="button"
          onClick={checkHealth}
        >
          {backendStatus.label}
        </button>
        <div id="accountSummary" className="account-summary">
          <Link
            className="account-profile-link"
            to="/settings"
            aria-label="เปิดการตั้งค่าบัญชี"
            title="ตั้งค่าบัญชี"
          >
            <span id="accountAvatar" className="account-avatar" aria-hidden="true">
              {(user?.username || 'U').slice(0, 1).toUpperCase()}
            </span>
            <span className="account-copy">
              <strong id="accountName">{user?.username || 'ผู้ใช้'}</strong>
              <small id="accountRole" className={user?.role === 'admin' ? 'admin' : ''}>
                {user?.role === 'admin' ? 'Admin' : 'User'}
              </small>
            </span>
            <Icon name="settings" className="ui-icon account-settings-mark" />
          </Link>
          <button id="logoutButton" className="logout-button" type="button" onClick={handleLogout}>
            ออกจากระบบ
          </button>
        </div>
      </div>
    </header>
  );
}
