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
    try { await (pending.type === 'device' ? api.revokeDevice(pending.id) : api.revokeSession(pending.id)); setMessage('ยกเลิกการเข้าถึงแล้ว'); setPending(null); resource.reload(); }
    catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }
  return <section className="workspace-page"><PageTitle title="อุปกรณ์และ Session" description="ตรวจสอบการเข้าสู่ระบบ และยกเลิกการเข้าถึงจากอุปกรณ์อื่น"><button onClick={resource.reload}>รีเฟรช</button></PageTitle>
    <ResourceState resource={resource} />
    {pending && <div className="workspace-notice"><p>ยกเลิก {pending.name} หรือไม่? {pending.type === 'device' ? 'ทุก Session ของอุปกรณ์นี้จะถูกยกเลิก อุปกรณ์ยังเข้าสู่ระบบใหม่ได้เมื่อมีรหัสผ่าน' : 'Session นี้จะใช้งานต่อไม่ได้'}</p><div className="workspace-actions"><button disabled={busy} onClick={revoke}>ยืนยันยกเลิกการเข้าถึง</button><button disabled={busy} onClick={() => setPending(null)}>กลับ</button></div></div>}
    <p className="workspace-message" role="status">{message}</p>
    {resource.data && <><section className="workspace-section"><h2>Session ที่ยังใช้งานได้</h2><div className="security-list">{resource.data.sessions.map(s => <article key={s.id}><div><h3>{s.device_name} {s.current && <span className="decision-badge decision-allow">Session นี้</span>}</h3><p>ใช้งานล่าสุด {formatTime(s.last_seen)}</p><small>หมดอายุ {formatTime(s.expires_at)}</small></div><button disabled={s.current || busy} onClick={() => setPending({ type: 'session', id: s.id, name: s.device_name })}>ยกเลิก Session</button></article>)}</div>{!resource.data.sessions.length && <EmptyState />}</section>
    <section className="workspace-section"><h2>อุปกรณ์ในบัญชี</h2><div className="security-list">{resource.data.devices.map(d => <article key={d.id}><div><h3>{d.name}</h3><p>{d.current ? 'อุปกรณ์ปัจจุบัน' : d.revoked ? 'ยกเลิกแล้ว' : 'เคยเชื่อมต่อ'} / ล่าสุด {formatTime(d.last_seen)}</p></div><button disabled={d.current || Boolean(d.revoked) || busy} onClick={() => setPending({ type: 'device', id: d.id, name: d.name })}>ยกเลิกอุปกรณ์</button></article>)}</div>{!resource.data.devices.length && <EmptyState />}</section></>}
  </section>;
}
