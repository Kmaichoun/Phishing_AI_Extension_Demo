import { useMemo, useState } from 'react';
import { useApp, mapServerHistory } from '../contexts/AppContext';
import { api } from '../services/api';
import { flattenReason } from '../services/risk';
import { AnalysisResult } from './ScannerPage';
import { PageTitle, ResourceState, EmptyState, Pager, DecisionBadge, decisionOf, formatTime, useResource } from '../components/WorkspaceUi';

const initialFilters = { q: '', decision: '', date_from: '', date_to: '' };
export function historyExportItem(item) {
  const modelReady = !item.privacy && (item.modelStatus === 'ready' || item.fusionApplied);
  return {
    time: item.time, url: item.displayUrl || item.url, decision: decisionOf(item),
    risk_score: item.finalScore,
    score_source: modelReady ? item.fusionMethod === 'ml_only' ? 'random_forest_calibrated' : 'model_result' : 'local_url_rules',
    warning_threshold: item.warningThreshold, blocking_threshold: item.blockingThreshold,
    model_version: item.modelVersion, policy_version: item.policyVersion,
    source: item.source, reasons: (item.reasons || []).map(flattenReason)
  };
}
function csvCell(value) {
  let text = String(value ?? '');
  if (/^[=+@\-\t\r]/.test(text)) text = "'" + text;
  return '"' + text.replace(/"/g, '""') + '"';
}
function saveFile(contents, name, type) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function Trend({ daily = [] }) {
  const days = Array.from({ length: 14 }, (_, i) => {
    const date = new Date(); date.setUTCDate(date.getUTCDate() - 13 + i);
    const key = date.toISOString().slice(0,10);
    return { day: key, ...(daily.find(row => row.day === key) || {}) };
  });
  const max = Math.max(1, ...days.map(d => Number(d.total) || 0));
  return <figure className="trend-chart"><figcaption>จำนวนผลตรวจ 14 วันล่าสุด (UTC)</figcaption>
    <div className="chart-legend"><span className="decision-allow">Allow</span><span className="decision-warn">Warn</span><span className="decision-block">Block</span></div>
    <div className="chart-columns">{days.map(day => <div className="chart-column" key={day.day}>
      <span>{day.total || 0}</span><div className="chart-stack" aria-label={day.day + ': allow ' + (day.allowed || 0) + ', warn ' + (day.warned || 0) + ', block ' + (day.blocked || 0)}>
        {[['blocked','block'],['warned','warn'],['allowed','allow']].map(([key,tone]) => <div key={key} className={'bar-' + tone} style={{ height: ((day[key] || 0) / max * 120) + 'px' }} />)}
      </div><small>{day.day.slice(8)}</small></div>)}</div>
  </figure>;
}
export function DashboardPage() {
  const { history, privacyMode, reloadHistory, clearHistory } = useApp();
  const [filters, setFilters] = useState(initialFilters);
  const [draft, setDraft] = useState(initialFilters);
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState(null);
  const [message, setMessage] = useState('');
  const [confirmClear, setConfirmClear] = useState(false);
  const [busy, setBusy] = useState(false);
  const records = useResource(() => privacyMode ? Promise.resolve({ items: [], total: 0 }) : api.searchHistory({ ...filters, offset, limit: 30 }), [privacyMode, filters, offset]);
  const stats = useResource(() => privacyMode ? Promise.resolve(null) : api.stats(), [privacyMode]);
  const localFiltered = useMemo(() => history.filter(item => item.privacy && (item.url || '').toLowerCase().includes(filters.q.toLowerCase()) && (!filters.decision || decisionOf(item) === filters.decision) && (!filters.date_from || item.time.slice(0,10) >= filters.date_from) && (!filters.date_to || item.time.slice(0,10) <= filters.date_to)), [history, filters]);
  const items = privacyMode ? localFiltered.slice(offset, offset + 30) : (records.data?.items || []).map(mapServerHistory);
  const total = privacyMode ? localFiltered.length : records.data?.total || 0;
  function exportHistory(format) {
    if (!items.length) { setMessage('ยังไม่มีข้อมูลในหน้านี้ให้ส่งออก'); return; }
    const stamp = new Date().toISOString().slice(0,10);
    const exported = items.map(historyExportItem);
    if (format === 'json') saveFile(JSON.stringify(exported, null, 2), 'phish-radar-history-' + stamp + '.json', 'application/json;charset=utf-8');
    else {
      const header = ['time','url','decision','risk_score','score_source','warning_threshold','blocking_threshold','model_version','policy_version','source','reasons'];
      const rows = exported.map(item => header.map(key => csvCell(key === 'reasons' ? item.reasons.join(' | ') : item[key])).join(','));
      saveFile('\uFEFF' + [header.join(','), ...rows].join('\n'), 'phish-radar-history-' + stamp + '.csv', 'text/csv;charset=utf-8');
    }
    setMessage('ส่งออกข้อมูลในหน้านี้ ' + items.length + ' รายการแล้ว');
  }
  async function removeHistory() {
    setBusy(true);
    try {
      const cleared = await clearHistory();
      if (!cleared) { setMessage('ยังล้างประวัติไม่ได้ กรุณาตรวจสอบ Backend แล้วลองใหม่'); return; }
      setMessage(privacyMode ? 'ล้างประวัติ Privacy Mode ในเครื่องแล้ว' : 'ล้างประวัติของบัญชีนี้แล้ว');
      setSelected(null); setOffset(0); records.reload(); stats.reload(); await reloadHistory();
    }
    finally { setBusy(false); setConfirmClear(false); }
  }
  const counts = stats.data?.totals;
  return <section id="dashboard" className="workspace-page">
    <PageTitle title="ภาพรวมการตรวจสอบ" description={privacyMode ? 'แสดงประวัติในเครื่องเฉพาะ Privacy Mode' : 'ผลตรวจและประวัติของบัญชีนี้จากฐานข้อมูล'}>
      <button onClick={() => { records.reload(); stats.reload(); }}>รีเฟรช</button>
    </PageTitle>
    {!privacyMode && <><ResourceState resource={stats} />{counts && <div className="workspace-section">
      <dl className="metric-strip">{[['ตรวจทั้งหมด',counts.total],['Allow',counts.allowed],['Warn',counts.warned],['Block',counts.blocked]].map(([label,value]) => <div key={label}><dt>{label}</dt><dd>{Number(value || 0).toLocaleString()}</dd></div>)}</dl>
      <Trend daily={stats.data.daily} />
      <p className="workspace-muted">รายงานจากผู้ใช้ว่าเตือนผิด: {stats.data.feedback.reported_false_positives || 0} รายการ / ผู้ดูแลยืนยันแล้ว: {stats.data.feedback.confirmed_false_positives || 0} รายการ ข้อมูลนี้ไม่ใช่ FPR ของโมเดล</p>
    </div>}</>}
    <section className="workspace-section"><h2>ประวัติการตรวจ</h2>
      <form className="history-filters" onSubmit={e => { e.preventDefault(); setOffset(0); setSelected(null); setFilters({ ...draft }); }}>
        <label>URL หรือโดเมน<input type="search" value={draft.q} onChange={e => setDraft({ ...draft, q: e.target.value })} placeholder="ค้นหาในประวัติ" /></label>
        <label>ระดับความเสี่ยง<select value={draft.decision} onChange={e => setDraft({ ...draft, decision: e.target.value })}><option value="">ทั้งหมด</option><option value="allow">Allow</option><option value="warn">Warn</option><option value="block">Block</option></select></label>
        <label>ตั้งแต่ (UTC)<input type="date" value={draft.date_from} max={draft.date_to || undefined} onChange={e => setDraft({ ...draft, date_from: e.target.value })} /></label>
        <label>ถึง (UTC)<input type="date" value={draft.date_to} min={draft.date_from || undefined} onChange={e => setDraft({ ...draft, date_to: e.target.value })} /></label>
        <button className="primary">ค้นหา</button>
      </form>
      {!privacyMode && <ResourceState resource={records} />}
      {(privacyMode || records.data) && <><div className="workspace-table-wrap"><table className="workspace-table"><thead><tr><th>วันและเวลา</th><th>URL</th><th>ผลตัดสิน</th><th>คะแนน</th><th>รายละเอียด</th></tr></thead><tbody>
        {items.map((item,i) => <tr key={item.historyId || i}><td>{formatTime(item.time)}</td><td className="history-url">{item.displayUrl || item.url}</td><td><DecisionBadge decision={decisionOf(item)} /></td><td>{item.finalScore}/100</td><td><button onClick={() => setSelected(selected?.time === item.time ? null : item)}>ดูผล</button></td></tr>)}
      </tbody></table></div>{!items.length && <EmptyState>ไม่มีประวัติตรงกับเงื่อนไขนี้ ลองเปลี่ยนตัวกรองหรือเริ่มตรวจลิงก์</EmptyState>}
      <Pager total={total} offset={offset} onChange={setOffset} /></>}
      <div className="workspace-actions"><span>ส่งออกหน้านี้:</span><button disabled={!items.length} onClick={() => exportHistory('csv')}>Export CSV</button><button disabled={!items.length} onClick={() => exportHistory('json')}>Export JSON</button><button disabled={!items.length} onClick={() => window.print()}>พิมพ์ / บันทึก PDF</button><button onClick={() => setConfirmClear(true)}>ล้างประวัติทั้งหมด</button></div>
      {confirmClear && <div className="workspace-notice"><p>ล้างประวัติทั้งหมดของบัญชีนี้หรือไม่? การค้นหาและตัวกรองไม่จำกัดรายการที่จะลบ</p><div className="workspace-actions"><button disabled={busy} onClick={removeHistory}>ยืนยันล้างประวัติ</button><button disabled={busy} onClick={() => setConfirmClear(false)}>ยกเลิก</button></div></div>}
      <p className="workspace-message" role="status">{message}</p>
    </section>
    {selected && <section className="workspace-section"><div className="workspace-actions"><h2>รายละเอียดผลตรวจ</h2><button onClick={() => setSelected(null)}>ปิดรายละเอียด</button></div><AnalysisResult result={selected} historical /></section>}
  </section>;
}
