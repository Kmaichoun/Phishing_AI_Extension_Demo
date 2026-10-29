import { useEffect, useState } from 'react';
import { useApp } from '../contexts/AppContext';
import { Link } from '../contexts/RouterContext';

export function useResource(loader, deps = []) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState({ data: null, error: '', loading: true });
  useEffect(() => {
    let active = true;
    setState({ data: null, error: '', loading: true });
    Promise.resolve().then(loader).then(data => {
      if (active) setState({ data, error: '', loading: false });
    }).catch(error => {
      if (active) setState({ data: null, error: error.message || 'โหลดข้อมูลไม่สำเร็จ', loading: false });
    });
    return () => { active = false; };
  }, [...deps, revision]);
  return { ...state, reload: () => setRevision(value => value + 1) };
}
export function PageTitle({ title, description, children }) {
  useEffect(() => { document.title = `${title} | Phish Radar AI`; }, [title]);
  return <header className="workspace-heading"><div><h1>{title}</h1>{description && <p>{description}</p>}</div>{children}</header>;
}
export function ResourceState({ resource }) {
  if (resource.loading) return <div className="workspace-skeleton" role="status"><span /><span /><span /><p>กำลังโหลดข้อมูล…</p></div>;
  if (resource.error) return <div className="workspace-notice error" role="alert"><p>{resource.error}</p><button onClick={resource.reload}>ลองใหม่</button></div>;
  return null;
}
export function EmptyState({ children = 'ยังไม่มีข้อมูลในส่วนนี้' }) {
  return <div className="workspace-empty">{children}</div>;
}
export function formatTime(value) {
  if (!value) return 'ยังไม่มีข้อมูล';
  const date = new Date(/(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.valueOf()) ? 'ยังไม่มีข้อมูล' : date.toLocaleString('th-TH', { dateStyle: 'medium', timeStyle: 'short' });
}
export const decisionLabel = { allow: 'ไม่พบความเสี่ยงชัดเจน', warn: 'พบสัญญาณน่าสงสัย', block: 'เสี่ยงสูง', unknown: 'ข้อมูลไม่เพียงพอ' };
export function decisionOf(item) {
  if (item.decision && decisionLabel[item.decision]) return item.decision;
  const score = item.finalScore ?? item.final_score;
  if (!Number.isFinite(score)) return 'unknown';
  if (score >= (item.blockingThreshold ?? item.blocking_threshold ?? 80)) return 'block';
  if (score >= (item.warningThreshold ?? item.warning_threshold ?? 60)) return 'warn';
  return 'allow';
}
export function DecisionBadge({ decision, label }) {
  return <span className={`decision-badge decision-${decision}`}>{label || decisionLabel[decision] || 'ไม่มีผลตัดสิน'}</span>;
}
export function serviceStates(health, privacyMode, checking) {
  const make = (key, name, ready) => ({ key, name, ready,
    text: privacyMode ? 'โหมดส่วนตัว' : checking ? 'กำลังตรวจ' : ready === true ? 'พร้อม' : ready === false ? 'ไม่พร้อม' : 'ยังไม่ได้ตรวจ' });
  return [make('backend', 'Backend', health?.ok ?? (health?.backendText === 'Offline' ? false : null)),
    make('database', 'Database', health?.database ? Boolean(health.database.connected && health.database.auth_schema_ready && health.database.history_schema_ready) : null),
    make('model', 'Model', health?.model_ready ?? null), make('llm', 'LLM', health?.llm?.llm_ready ?? null)];
}
export function SystemStrip() {
  const { health, privacyMode, backendStatus } = useApp();
  return <div className="system-strip" aria-label="สถานะบริการ">{serviceStates(health, privacyMode, backendStatus.online === null).map(item => <span key={item.key}>
    <i className={privacyMode || backendStatus.online === null ? '' : item.ready === true ? 'service-ready' : item.ready === false ? 'service-down' : ''} />{item.name} <strong>{item.text}</strong>
  </span>)}<Link to="/status">ดูรายละเอียด</Link></div>;
}
export function Pager({ offset, total, size = 30, onChange }) {
  return <div className="workspace-pager"><span>{total ? `${offset + 1}-${Math.min(offset + size, total)} จาก ${total} รายการ` : '0 รายการ'}</span>
    <button disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - size))}>ก่อนหน้า</button>
    <button disabled={offset + size >= total} onClick={() => onChange(offset + size)}>ถัดไป</button></div>;
}
