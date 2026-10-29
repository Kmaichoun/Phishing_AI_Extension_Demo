import { useEffect, useRef, useState } from 'react';
import { useApp } from '../contexts/AppContext';
import { explanationReasonItems, flattenReason, safeHistoryUrl } from '../services/risk';
import { PageTitle, SystemStrip, DecisionBadge, decisionOf, decisionLabel } from '../components/WorkspaceUi';

export function ExplanationReasons({ title, items, emptyText }) {
  const reasons = explanationReasonItems(items);
  return <section className="explanation-reasons"><h4>{title}</h4>
    {reasons.length ? <ol>{reasons.map((item, index) => <li key={index}>
      <strong>{item.title}</strong><p>{item.explanation}</p>
    </li>)}</ol> : <p className="workspace-muted">{emptyText}</p>}
  </section>;
}

export function AnalysisResult({ result, phase = 'done', historical = false }) {
  const { submitFeedback } = useApp();
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [tab, setTab] = useState('evidence');
  useEffect(() => { setMessage(''); setSent(false); setTab('evidence'); }, [result?.time]);
  if (!result) return <div className="workspace-empty"><h2>เริ่มจากลิงก์ที่ต้องการตรวจสอบ</h2><p>วาง URL ด้านบน แล้วอ่านผลตัดสินพร้อมเหตุผลก่อนเปิดเว็บไซต์</p></div>;
  const rawDecision = decisionOf(result);
  let parsed;
  try { parsed = new URL(result.url); } catch { parsed = null; }
  const loading = phase === 'analyzing';
  const waiting = loading || phase === 'explaining';
  const modelReady = result.modelStatus === 'ready' || result.fusionApplied;
  const decision = loading || (!modelReady && rawDecision === 'allow') ? 'unknown' : rawDecision;
  const modelOnlyWarning = modelReady && result.fusionMethod === 'ml_only'
    && ['warn', 'block'].includes(decision) && result.ruleScore === 0
    && !(result.reasons || []).some(reason => Number(reason?.points) > 0);
  const scoreSource = modelReady ? result.fusionMethod === 'ml_only'
    ? 'Random Forest หลังปรับเทียบ' : 'โมเดลที่ใช้ในผลตรวจนี้' : 'กฎ URL ในเครื่อง';
  const riskReasons = explanationReasonItems(result.llm?.riskReasons);
  const reassuringReasons = explanationReasonItems(result.llm?.reassuringReasons);
  const hasDetailedReasons = typeof result.llm?.hasDetailedReasons === 'boolean'
    ? result.llm.hasDetailedReasons
    : Array.isArray(result.llm?.riskReasons) || Array.isArray(result.llm?.reassuringReasons);
  const noRiskReasonText = hasDetailedReasons
    ? 'ยังไม่พบข้อควรระวังจากข้อมูล URL ที่ตรวจในครั้งนี้'
    : result.llm?.explanation ? 'คำอธิบายนี้ไม่มีเหตุผลแยกรายข้อ อ่านสรุปด้านบนหรือตรวจ URL ใหม่เพื่อรับรายละเอียดล่าสุด' : 'ยังไม่มีคำอธิบายแยกรายข้อ';
  const noReassuringReasonText = hasDetailedReasons
    ? 'ยังไม่พบข้อมูลที่ช่วยลดความกังวลจาก URL ที่ตรวจ ผลนี้ไม่ยืนยันว่าเว็บไซต์ปลอดภัยหรืออันตราย'
    : 'ไม่มีข้อมูลประกอบส่วนนี้ในคำอธิบาย ไม่ได้หมายความว่าเว็บไซต์ปลอดภัยหรืออันตราย';
  const report = [
    'Phish Radar AI Report',
    'URL: ' + (result.privacy ? result.displayUrl : safeHistoryUrl(result.url)),
    'Decision: ' + decision, 'FinalScore: ' + result.finalScore,
    'Score source: ' + scoreSource,
    'Warning / Blocking: ' + result.warningThreshold + ' / ' + result.blockingThreshold,
    'Model: ' + (result.modelVersion || '-'), 'Policy: ' + (result.policyVersion || '-'),
    'Reasons: ' + (result.reasons || []).map(flattenReason).join(' | '),
    'Risk summary: ' + (result.llm?.riskType || '-'),
    'LLM: ' + (result.llm?.explanation || 'ไม่มีคำอธิบาย'),
    ...(riskReasons.length ? ['เหตุผลที่ควรระวัง:', ...riskReasons.map((item, index) => `${index + 1}. ${item.title}: ${item.explanation}`)] : hasDetailedReasons ? ['เหตุผลที่ควรระวัง: ' + noRiskReasonText] : []),
    ...(reassuringReasons.length ? ['สิ่งที่ช่วยลดความกังวล:', ...reassuringReasons.map((item, index) => `${index + 1}. ${item.title}: ${item.explanation}`)] : hasDetailedReasons ? ['สิ่งที่ช่วยลดความกังวล: ' + noReassuringReasonText] : []),
    'Advice: ' + (result.llm?.advice || '-'),
    ...(result.llm?.confidenceNote ? ['Limitations: ' + result.llm.confidenceNote] : [])
  ].join('\n');
  async function copy() {
    try {
      if (!navigator.clipboard) throw new Error();
      await navigator.clipboard.writeText(report); setMessage('คัดลอกสรุปแล้ว โดยตัด query และข้อมูลรับรองออก');
    } catch { setMessage('คัดลอกไม่ได้ กรุณาใช้พิมพ์รายงานแทน'); }
  }
  async function feedback(label) {
    setSending(true);
    try { const text = await submitFeedback(label); setMessage(text); setSent(text?.includes('บันทึก feedback แล้ว') || text?.includes('บันทึก feedback ไว้')); }
    finally { setSending(false); }
  }
  return <article className="scan-result" aria-label="ผลการตรวจสอบ">
    <div className="result-overview">
      <div className="result-verdict">
        <p className="workspace-muted">{historical ? 'ผลตรวจที่บันทึกไว้' : loading ? 'กำลังวิเคราะห์ URL' : 'ผลการตรวจสอบ'}</p>
        {loading ? <p role="status">กำลังตรวจหลักฐานและขอคำอธิบาย…</p> : <DecisionBadge decision={decision} label={modelOnlyWarning ? 'โมเดลประเมินว่าควรระวัง' : undefined} />}
        <h2>{parsed?.hostname || 'อ่านโดเมนไม่ได้'}</h2>
        <p className="url-text">{result.privacy ? result.displayUrl : safeHistoryUrl(result.url)}</p>
        {modelOnlyWarning && <p className="workspace-notice">โมเดลประเมินความเสี่ยงถึงเกณฑ์เตือน แต่ยังไม่พบหลักฐานเสี่ยงจากกฎ URL ที่ตรวจ ไม่ใช่การยืนยันว่าเว็บไซต์นี้เป็น phishing</p>}
        <p>{decision === 'block' ? 'หลีกเลี่ยงการกรอกข้อมูลหรือดาวน์โหลดไฟล์ จนกว่าจะตรวจสอบแหล่งที่มา' : decision === 'warn' ? 'ตรวจสอบโดเมนและแหล่งที่มาเพิ่มเติมก่อนกรอกข้อมูลสำคัญ' : decision === 'unknown' ? 'ยังสรุปความเสี่ยงไม่ได้ อ่านข้อสังเกตที่ตรวจพบด้านล่าง' : 'ผลตรวจครั้งนี้ยังไม่พบความเสี่ยงชัดเจน ควรตรวจแหล่งที่มาก่อนกรอกข้อมูลสำคัญ'}</p>
        {!loading && !modelReady && <p className="workspace-notice">{result.privacy ? 'Privacy Mode: ใช้กฎในเครื่อง' : result.modelStatus === 'offline' ? 'ครั้งนี้ไม่ได้รับผลจากโมเดล ใช้คะแนนกฎเบื้องต้น กรุณาลองตรวจสอบอีกครั้ง' : 'ครั้งนี้โมเดลไม่ได้คำนวณผล คะแนนนี้มาจากหลักฐานที่มี'}{result.predictionError && <span> · {result.predictionError}</span>}</p>}
        {result.deploymentMode === 'experimental_demo' && <p className="workspace-notice">โมเดลทดลอง: Random Forest สำหรับทดสอบบน Web app ยังไม่ผ่านเกณฑ์เปิดใช้งานจริงทั้งหมด</p>}
      </div>
      <div className="score-breakdown">
        <div className={'final-score decision-' + decision}><span>{loading ? 'คะแนนกฎเบื้องต้น' : modelReady && result.fusionMethod === 'ml_only' ? 'Random Forest' : !modelReady ? 'คะแนนตรวจในเครื่อง' : 'คะแนนความเสี่ยง'}</span><strong>{result.finalScore ?? '—'}<small>/100</small></strong></div>
        <small>{modelReady ? result.fusionMethod === 'ml_only' ? 'คะแนนจาก Random Forest หลังปรับเทียบ' : 'คะแนนจากโมเดลที่ใช้ในผลตรวจนี้' : 'คะแนนจากกฎที่ตรวจ URL ในเครื่อง'}</small>
      </div>
    </div>
    <div className="workspace-tabs" aria-label="รายละเอียดผลตรวจ">
      {[['evidence','เหตุผลสำคัญ'],['model','รายละเอียดโมเดล'],['llm','คำอธิบายจาก LLM'],['feedback','Feedback']].map(([id, label]) => <button key={id} aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>)}
    </div>
    <div className="result-detail">
      {tab === 'evidence' && <section><h3>หลักฐานจาก URL</h3>
        <ul className="evidence-list">{(result.reasons?.length ? result.reasons : [historical ? 'ประวัตินี้ไม่ได้บันทึกข้อความเหตุผลไว้' : 'ยังไม่พบสัญญาณเสี่ยงสำคัญจากกฎที่ตรวจ']).map((r, i) => <li key={i}>{flattenReason(r)}</li>)}</ul>
        <h3>บริบทของโดเมนและแบรนด์</h3><ul className="evidence-list">{(result.insights?.length ? result.insights : ['ไม่มีข้อมูลส่วนนี้ในผลตรวจ']).map((text, i) => <li key={i}>{text}</li>)}</ul>
        <small>ส่วนนี้วิเคราะห์ชื่อและโครงสร้าง URL ไม่ใช่การยืนยันภาพหรือเนื้อหาทั้งหน้าเว็บไซต์</small>
      </section>}
      {tab === 'model' && <section><h3>ข้อมูลโมเดลของผลตรวจนี้</h3><p>ที่มาของคะแนน: {scoreSource}</p><dl className="detail-list">
        <div><dt>Model version</dt><dd>{result.modelVersion || 'ไม่มีข้อมูล'}</dd></div><div><dt>Policy version</dt><dd>{result.policyVersion || 'ไม่มีข้อมูล'}</dd></div>
        <div><dt>Warning / Blocking</dt><dd>{result.warningThreshold ?? '-'} / {result.blockingThreshold ?? '-'}</dd></div><div><dt>ผลตัดสิน</dt><dd>{modelOnlyWarning ? 'โมเดลประเมินว่าควรระวัง' : decisionLabel[decision]}</dd></div>
      </dl><p>คะแนนนี้ไม่ใช่เปอร์เซ็นต์ยืนยันว่าเป็นเว็บปลอม ข้อสังเกตจากกฎไม่ใช่คำอธิบายการตัดสินภายใน Random Forest</p></section>}
      {tab === 'llm' && <section><h3>คำอธิบายจาก LLM</h3><p className="workspace-muted">{result.llm?.state || 'ไม่มีคำอธิบายในประวัตินี้'} / ไม่มีผลต่อคะแนนตัดสิน</p><dl className="detail-list">
        <div><dt>สรุปความเสี่ยง</dt><dd>{result.llm?.riskType || '-'}</dd></div><div><dt>เหตุผลของคะแนน</dt><dd>{result.llm?.explanation || 'ตรวจ URL ใหม่เพื่อขอคำอธิบายล่าสุด'}</dd></div>
      </dl>
      <ExplanationReasons title="เหตุผลที่ควรระวัง" items={riskReasons} emptyText={noRiskReasonText} />
      <ExplanationReasons title="สิ่งที่ช่วยลดความกังวล" items={reassuringReasons} emptyText={noReassuringReasonText} />
      <dl className="detail-list"><div><dt>คำแนะนำ</dt><dd>{result.llm?.advice || '-'}</dd></div>
        {result.llm?.confidenceNote && <div><dt>ข้อจำกัดของผลตรวจ</dt><dd>{result.llm.confidenceNote}</dd></div>}
      </dl></section>}
      {tab === 'feedback' && <section><h3>ผลตรวจตรงกับที่พบหรือไม่</h3><p>รายงานนี้จะส่งให้ผู้ดูแลตรวจทาน และไม่เปลี่ยนคะแนนหรือฝึกโมเดลทันที</p>{historical ? <p>ส่ง Feedback ได้จากผลตรวจล่าสุดในหน้าตรวจลิงก์</p> :
        <div className="workspace-actions">{[['dangerous','อันตรายจริง'],['safe','เป็นเว็บปกติ'],['unsure','ไม่แน่ใจ']].map(([value,label]) => <button key={value} disabled={waiting || sending || sent} onClick={() => feedback(value)}>{label}</button>)}</div>}</section>}
    </div>
    <div className="workspace-actions result-actions">
      <button onClick={copy}>คัดลอกสรุป</button><button onClick={() => window.print()}>พิมพ์ / บันทึก PDF</button>
      {!historical && parsed && ['http:', 'https:'].includes(parsed.protocol) && !loading && <details className="open-url-confirm"><summary>เปิดเว็บไซต์</summary><p>ผลตรวจไม่รับประกันความปลอดภัย โปรดตรวจโดเมนก่อนเปิด</p><a href={result.url} target="_blank" rel="noopener noreferrer">เปิด {parsed.hostname}</a></details>}
    </div>
    <p className="workspace-message" role="status">{message}</p>
    <pre className="print-report">{report}</pre>
  </article>;
}

export function ScannerPage() {
  const { current, analysisPhase, formMessage, formError, analyzeUrl, privacyMode, setPrivacyMode } = useApp();
  const [url, setUrl] = useState(current?.url || '');
  const input = useRef(null);
  const busy = ['analyzing', 'explaining'].includes(analysisPhase);
  useEffect(() => { if (current?.url) setUrl(current.url); }, [current?.url]);
  async function submit(event) { event.preventDefault(); await analyzeUrl(url); }
  return <section id="scan" className="workspace-page">
    <PageTitle title="ตรวจสอบลิงก์" description="วาง URL เพื่อดูความเสี่ยง หลักฐาน และคำแนะนำก่อนเปิดเว็บไซต์" />
    <form className="workspace-scan-form" onSubmit={submit}>
      <label htmlFor="urlInput">ลิงก์ที่ต้องการตรวจสอบ</label>
      <div className="input-row scan-input-row"><input ref={input} id="urlInput" type="text" inputMode="url" autoComplete="off" placeholder="วาง URL ที่ต้องการตรวจสอบ" required value={url} onChange={e => setUrl(e.target.value)} aria-describedby="scan-message" />
        <button className="primary" disabled={analysisPhase === 'analyzing'}>{analysisPhase === 'analyzing' ? 'กำลังตรวจ…' : 'ตรวจสอบ'}</button></div>
      <div className="scan-options"><label><input type="checkbox" checked={privacyMode} onChange={e => setPrivacyMode(e.target.checked)} disabled={busy} />Privacy Mode: ตรวจด้วยกฎในเครื่อง</label>
        {current && <button type="button" disabled={analysisPhase === 'analyzing'} onClick={() => { setUrl(''); input.current?.focus(); }}>ล้างช่อง URL</button>}</div>
      <p id="scan-message" className={'workspace-message ' + (formError ? 'error' : '')} role="status">{formMessage}</p>
    </form>
    <SystemStrip />
    <AnalysisResult result={current} phase={analysisPhase} />
  </section>;
}
