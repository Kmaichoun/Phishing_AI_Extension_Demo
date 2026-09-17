import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';
import { PageTitle, ResourceState, EmptyState, Pager, formatTime, useResource, DecisionBadge } from '../components/WorkspaceUi';
import { ModelLab, ReviewedFeedbackExport } from '../components/ModelLab';

function AdminWorkspace() {
  const { user } = useAuth();
  const [tab, setTab] = useState('users');
  const [query, setQuery] = useState('');
  const [draft, setDraft] = useState('');
  const [state, setState] = useState('pending');
  const [offset, setOffset] = useState(0);
  const [editing, setEditing] = useState(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const resource = useResource(() => tab === 'models' ? api.adminModels() : tab === 'users' ? api.adminUsers(query, offset) : tab === 'feedback' ? api.adminFeedback(state, offset) : api.adminAudit(offset), [tab, query, state, offset]);
  async function save(event) {
    event.preventDefault(); setBusy(true); setMessage('');
    try {
      if (tab === 'users') await api.adminUpdateUser(editing.id, { role: editing.role, active: Boolean(editing.active) });
      else await api.adminReview(editing.id, { status: editing.status, note: editing.note });
      setEditing(null); resource.reload(); setMessage('บันทึกและลง Audit Log แล้ว');
    } catch (error) { setMessage(error.message); }
    finally { setBusy(false); }
  }
  return <section className="workspace-page"><PageTitle title="จัดการระบบ" description="จัดการสิทธิ์ ตรวจ Feedback และตรวจสอบประวัติการเปลี่ยนแปลง"><button onClick={resource.reload}>รีเฟรช</button></PageTitle>
    <div className="workspace-tabs">{[['users','ผู้ใช้'],['feedback','ตรวจ Feedback'],['models','วิเคราะห์โมเดล'],['audit','Audit Log']].map(([id,label]) => <button key={id} aria-pressed={tab === id} onClick={() => { setTab(id); setOffset(0); setEditing(null); setMessage(''); }}>{label}</button>)}</div>
    {tab === 'users' && <form className="workspace-search" onSubmit={e => { e.preventDefault(); setQuery(draft); setOffset(0); }}><label htmlFor="user-search">ค้นหาชื่อหรืออีเมล</label><input id="user-search" value={draft} onChange={e => setDraft(e.target.value)} /><button>ค้นหา</button></form>}
    {tab === 'feedback' && <><p>รายการจาก Web App ที่บันทึกในฐานข้อมูล Feedback เดิมของ Extension ในไฟล์ CSV ยังไม่รวมในหน้านี้</p><label className="workspace-select-label">สถานะ<select value={state} onChange={e => { setState(e.target.value); setOffset(0); }}><option value="pending">รอตรวจ</option><option value="confirmed">ยืนยันแล้ว</option><option value="dismissed">ไม่ยืนยัน</option><option value="all">ทั้งหมด</option></select></label></>}
    <p role="status" className="workspace-message">{message}</p>
    {editing && <form className="workspace-section edit-panel" onSubmit={save}><h2>{tab === 'users' ? 'แก้ไขบัญชี ' + editing.username : 'ตรวจทาน Feedback'}</h2>
      {tab === 'users' ? <><label>สิทธิ์<select value={editing.role} onChange={e => setEditing({ ...editing, role: e.target.value })}><option value="user">User</option><option value="admin">Admin</option></select></label><label><input type="checkbox" checked={Boolean(editing.active)} onChange={e => setEditing({ ...editing, active: e.target.checked })} />เปิดใช้งานบัญชี</label><p>เมื่อบันทึก ผู้ใช้นี้จะต้องเข้าสู่ระบบใหม่</p></> : <><label>ผลตรวจทาน<select value={editing.status} onChange={e => setEditing({ ...editing, status: e.target.value })}><option value="confirmed">ยืนยันรายงานของผู้ใช้</option><option value="dismissed">ไม่ยืนยันรายงาน</option></select></label><label>เหตุผลและหลักฐาน<textarea required minLength={3} maxLength={1000} value={editing.note} onChange={e => setEditing({ ...editing, note: e.target.value })} /></label></>}
      <div className="workspace-actions"><button className="primary" disabled={busy}>บันทึกการเปลี่ยนแปลง</button><button type="button" disabled={busy} onClick={() => setEditing(null)}>ยกเลิก</button></div></form>}
    <ResourceState resource={resource} />
    {resource.data && tab === 'models' && <ModelLab data={resource.data} />}
    {resource.data && tab !== 'models' && <section className="workspace-section"><div className="workspace-table-wrap"><table className="workspace-table">
      <thead>{tab === 'users' ? <tr><th>ชื่อผู้ใช้</th><th>อีเมล</th><th>สิทธิ์</th><th>สถานะ</th><th>เข้าสู่ระบบล่าสุด</th><th>จัดการ</th></tr> : tab === 'feedback' ? <tr><th>URL / ผู้รายงาน</th><th>ผลเดิม</th><th>รายงาน</th><th>สถานะตรวจทาน</th><th>จัดการ</th></tr> : <tr><th>วันและเวลา</th><th>ผู้ทำรายการ</th><th>การกระทำ</th><th>เป้าหมาย</th><th>รายละเอียด</th></tr>}</thead>
      <tbody>{resource.data.items.map(item => tab === 'users' ? <tr key={item.id}><td>{item.username}{item.id === user.user_id ? ' (คุณ)' : ''}</td><td>{item.email}</td><td>{item.role}</td><td>{item.active ? 'ใช้งานได้' : 'ระงับ'}</td><td>{formatTime(item.last_login)}</td><td><button disabled={item.id === user.user_id} onClick={() => setEditing(item)}>แก้ไข</button></td></tr> : tab === 'feedback' ? <tr key={item.id}><td className="history-url">{item.url}<small>{item.username} / {item.model_version || 'ไม่มีรุ่นโมเดล'}</small></td><td><DecisionBadge decision={item.decision} /> {item.score}/100</td><td>{{ safe:'เว็บปกติ', dangerous:'อันตราย', unsure:'ไม่แน่ใจ' }[item.user_label]}</td><td>{item.review_status}<small>{item.review_note}</small></td><td><button disabled={item.review_status !== 'pending'} onClick={() => setEditing({ ...item, status:'confirmed', note:'' })}>ตรวจทาน</button></td></tr> : <tr key={item.id}><td>{formatTime(item.created_at)}</td><td>{item.actor || 'บัญชีที่ไม่มีแล้ว'}</td><td>{item.action}</td><td>{item.target_type} #{item.target_id}</td><td><details><summary>ดูรายละเอียด</summary><pre className="json-detail">{item.details}</pre></details></td></tr>)}</tbody>
    </table></div>{!resource.data.items.length && <EmptyState>ยังไม่มีรายการในหมวดนี้</EmptyState>}<Pager offset={offset} total={resource.data.total} onChange={setOffset} /></section>}
    {tab === 'feedback' && <ReviewedFeedbackExport key={resource.data ? 'loaded-' + resource.data.total + '-' + message : 'loading'} />}
  </section>;
}
export function AdminPage() {
  const { user } = useAuth();
  return user?.role === 'admin' ? <AdminWorkspace /> : <section className="workspace-page"><PageTitle title="ไม่มีสิทธิ์เข้าถึง" description="หน้านี้สำหรับผู้ดูแลระบบ" /></section>;
}
