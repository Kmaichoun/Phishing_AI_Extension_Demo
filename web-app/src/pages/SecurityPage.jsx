import { useState } from 'react';
import { api } from '../services/api';
import { PageTitle, ResourceState, EmptyState, formatTime, useResource } from '../components/WorkspaceUi';

export function SecurityPage() {
  const resource = useResource(api.security);
  const [pending, setPending] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  async function revoke() {
    setBusy(true); setMessage('');
    try { await api.revokeSession(pending.id); setMessage('ยกเลิกการเข้าถึงแล้ว'); setPending(null); resource.reload(); }
    catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }
  return <section className="workspace-page"><PageTitle title="การเข้าสู่ระบบ" description="ตรวจสอบและยกเลิก Session ของบัญชี"><button onClick={resource.reload}>รีเฟรช</button></PageTitle>
    <ResourceState resource={resource} />
    {pending && <div className="workspace-notice"><p>ยกเลิก {pending.name} หรือไม่? Session นี้จะใช้งานต่อไม่ได้</p><div className="workspace-actions"><button disabled={busy} onClick={revoke}>ยืนยันยกเลิกการเข้าถึง</button><button disabled={busy} onClick={() => setPending(null)}>กลับ</button></div></div>}
    <p className="workspace-message" role="status">{message}</p>
    {resource.data && <section className="workspace-section"><h2>Session ที่ยังใช้งานได้</h2><div className="security-list">{resource.data.sessions.map((s, index) => <article key={s.id}><div><h3>Session {index + 1} {s.current && <span className="decision-badge decision-allow">Session นี้</span>}</h3><p>เข้าสู่ระบบเมื่อ {formatTime(s.created_at)}</p><p>ใช้งานล่าสุด {formatTime(s.last_seen)}</p><small>หมดอายุ {formatTime(s.expires_at)}</small></div><button disabled={s.current || busy} onClick={() => setPending({ id: s.id, name: `Session ${index + 1}` })}>ยกเลิก Session</button></article>)}</div>{!resource.data.sessions.length && <EmptyState />}</section>}
  </section>;
}
