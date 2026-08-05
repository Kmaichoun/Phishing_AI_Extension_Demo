import { useEffect, useMemo } from 'react';
import { MotionFrame } from '../components/MotionFrame';
import { useApp } from '../contexts/AppContext';

function exceedsPolicyThreshold(item) {
  return item.decision
    ? item.decision !== 'allow'
    : item.finalScore >= (Number.isFinite(item.warningThreshold) ? item.warningThreshold : 61);
}

function csvEscape(value) {
  return `"${String(value ?? '').replace(/"/g, '""')}"`;
}

function downloadBlob(blob, name) {
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = name;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

export function DashboardPage() {
  const {
    history,
    feedbackCount,
    health,
    checkHealth,
    reportState,
    reportStatus,
    setReportStatus,
    clearHistory
  } = useApp();

  useEffect(() => {
    document.title = 'Dashboard | Phish Radar AI';
  }, []);

  const metrics = useMemo(() => {
    const total = history.length;
    const high = history.filter(exceedsPolicyThreshold).length;
    const average = total
      ? Math.round(history.reduce((sum, item) => sum + Number(item.finalScore || 0), 0) / total)
      : 0;
    return { total, high, average };
  }, [history]);

  function exportHistory(format) {
    if (!history.length) {
      setReportStatus('ยังไม่มีข้อมูลให้ส่งออก');
      return;
    }
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');
    if (format === 'json') {
      const name = `phish-radar-history-${stamp}.json`;
      downloadBlob(
        new Blob([JSON.stringify(history, null, 2)], { type: 'application/json;charset=utf-8' }),
        name
      );
      setReportStatus(`ส่งออก ${name} แล้ว`);
      return;
    }

    const header = [
      'time', 'url', 'privacy', 'rule_evidence_score', 'risk_probability',
      'risk_score', 'decision', 'warning_threshold', 'blocking_threshold',
      'model_version', 'policy_version', 'threat_types', 'insights'
    ];
    const rows = history.map(item => [
      item.time,
      item.privacy ? item.displayUrl : item.url,
      item.privacy ? 'on' : 'off',
      item.ruleScore,
      Number.isFinite(item.riskProbability) ? item.riskProbability : '',
      item.riskScore ?? item.finalScore,
      item.decision || '',
      item.warningThreshold ?? '',
      item.blockingThreshold ?? '',
      item.modelVersion || '',
      item.policyVersion || '',
      (item.threatTypes || []).join(' | '),
      (item.insights || []).join(' | ')
    ].map(csvEscape).join(','));
    const name = `phish-radar-history-${stamp}.csv`;
    downloadBlob(
      new Blob([[header.join(','), ...rows].join('\n')], { type: 'text/csv;charset=utf-8' }),
      name
    );
    setReportStatus(`ส่งออก ${name} แล้ว`);
  }

  async function copySummary() {
    const text = [
      'Phish Radar AI Dashboard',
      `ตรวจทั้งหมด: ${metrics.total}`,
      `เสี่ยงสูง: ${metrics.high}`,
      `คะแนนเฉลี่ย: ${metrics.average}`,
      `Feedback: ${feedbackCount}`
    ].join('\n');
    await navigator.clipboard?.writeText(text);
    setReportStatus('คัดลอกสรุป Dashboard แล้ว');
  }

  return (
    <MotionFrame>
      <section id="dashboard" className="page active">
        <div className="dash-grid">
          <section className="panel metrics-panel" data-reveal>
            <div className="page-heading">
              <p className="eyebrow">ACCOUNT OVERVIEW</p>
              <h1>ภาพรวมการตรวจสอบ</h1>
            </div>
            <div className="metrics">
              <div><span>ตรวจทั้งหมด</span><strong>{metrics.total}</strong></div>
              <div><span>เสี่ยงสูง</span><strong>{metrics.high}</strong></div>
              <div><span>คะแนนเฉลี่ย</span><strong>{metrics.average}</strong></div>
              <div><span>Feedback</span><strong>{feedbackCount}</strong></div>
            </div>
          </section>

          <section className="panel report-panel" data-reveal>
            <div className="row-title"><h2>Report Center</h2><span>{reportState}</span></div>
            <p className="report-copy">
              ประวัติผูกกับบัญชีผู้ใช้และอุปกรณ์ URL จะถูกตัด query string
              และข้อมูลรับรองก่อนบันทึก สามารถส่งออกเพื่อตรวจสอบ false positive ได้
            </p>
            <div className="report-actions">
              <button className="secondary compact" type="button" onClick={() => exportHistory('csv')}>Export CSV</button>
              <button className="secondary compact" type="button" onClick={() => exportHistory('json')}>Export JSON</button>
              <button className="secondary compact" type="button" onClick={copySummary}>คัดลอกสรุป</button>
            </div>
            <p className="message" aria-live="polite">{reportStatus}</p>
          </section>

          <section className="panel health-panel" data-reveal>
            <div className="row-title">
              <h2>สถานะระบบ</h2>
              <button className="secondary compact" type="button" onClick={checkHealth}>รีเฟรช</button>
            </div>
            <dl className="health">
              <div><dt>Backend</dt><dd>{health?.backendText || '-'}</dd></div>
              <div><dt>URL Risk Model</dt><dd>{health?.modelText || '-'}</dd></div>
              <div><dt>LLM</dt><dd>{health?.llmText || '-'}</dd></div>
              <div><dt>Feedback file</dt><dd>{health?.feedbackText || '-'}</dd></div>
            </dl>
          </section>

          <section className="panel history-panel" data-reveal>
            <div className="row-title">
              <h2>ประวัติการตรวจของบัญชีนี้</h2>
              <button className="secondary compact" type="button" onClick={clearHistory}>ล้าง</button>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>เวลา</th><th>URL</th><th>Rule evidence</th><th>Risk model</th><th>RiskScore</th>
                  </tr>
                </thead>
                <tbody>
                  {history.length ? history.map((item, index) => (
                    <tr key={item.historyId || `${item.time}-${index}`}>
                      <td>{new Date(item.time).toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' })}</td>
                      <td>{item.displayUrl || item.url}</td>
                      <td>{item.ruleScore}</td>
                      <td>{Number.isFinite(item.mlScore) ? item.mlScore : (item.privacy ? 'local' : '-')}</td>
                      <td>{item.finalScore}</td>
                    </tr>
                  )) : (
                    <tr><td colSpan="5">ยังไม่มีประวัติการตรวจ</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      </section>
    </MotionFrame>
  );
}
