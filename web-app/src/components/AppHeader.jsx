import { useEffect, useRef, useState } from 'react';
import brandIcon from '../../assets/icon128.png';
import { useAuth } from '../contexts/AuthContext';
import { useApp } from '../contexts/AppContext';
import { Link, useRouter } from '../contexts/RouterContext';
import { ThemeToggle } from './ThemeToggle';

export function AppHeader() {
  const { user, logout } = useAuth();
  const { privacyMode, setPrivacyMode, analysisPhase } = useApp();
  const { navigate, path } = useRouter();
  const menu = useRef(null);
  const [error, setError] = useState('');
  useEffect(() => { if (menu.current) menu.current.open = false; }, [path]);
  useEffect(() => {
    const close = event => {
      if (event.type === 'keydown' && event.key !== 'Escape') return;
      if (menu.current && (event.type === 'keydown' || !menu.current.contains(event.target))) {
        menu.current.open = false;
        if (event.type === 'keydown') menu.current.querySelector('summary')?.focus();
      }
    };
    document.addEventListener('pointerdown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('pointerdown', close); document.removeEventListener('keydown', close); };
  }, []);
  async function handleLogout() {
    try { await logout(); navigate('/login', { replace: true }); }
    catch (error) { setError(error.message || 'ออกจากระบบไม่สำเร็จ'); }
  }
  return <>
    <header className="workspace-topbar">
      <Link className="brand" to="/scan"><img src={brandIcon} alt="" /><strong>Phish Radar AI</strong></Link>
      <nav className="workspace-nav" aria-label="เมนูหลัก">
        <Link to="/scan">ตรวจลิงก์</Link><Link to="/qr">QR</Link><Link to="/dashboard">Dashboard</Link><Link to="/methodology">วิธีการทำงาน</Link>
      </nav>
      <div className="workspace-tools"><ThemeToggle />
        <details ref={menu} className="account-menu"><summary>{user?.username || 'บัญชี'} <span aria-hidden="true">⌄</span></summary>
          <div className="account-menu-content">
            <small>{user?.role === 'admin' ? 'ผู้ดูแลระบบ' : 'ผู้ใช้'}</small>
            <Link to="/settings">ตั้งค่าบัญชี</Link><Link to="/security">การเข้าสู่ระบบ</Link><Link to="/status">สถานะระบบ</Link>
            {user?.role === 'admin' && <Link to="/admin">จัดการระบบ</Link>}
            <label><input type="checkbox" checked={privacyMode} disabled={['analyzing', 'explaining'].includes(analysisPhase)} onChange={e => setPrivacyMode(e.target.checked)} />Privacy Mode</label>
            <small>เปิดแล้วตรวจ URL ด้วยกฎในเครื่อง</small>
            <button onClick={handleLogout}>ออกจากระบบ</button>
          </div>
        </details>
      </div>
    </header>{error && <p className="workspace-notice error" role="alert">{error}</p>}
  </>;
}
