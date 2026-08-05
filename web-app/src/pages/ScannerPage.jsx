import { useEffect, useRef, useState } from 'react';
import brandIcon from '../../assets/icon128.png';
import { Icon } from '../components/Icon';
import { MotionFrame } from '../components/MotionFrame';
import { useApp } from '../contexts/AppContext';
import { flattenReason, riskLevel } from '../services/risk';

function reportText(item) {
  if (!item) return '';
  return [
    'Phish Radar AI Report',
    `URL: ${item.privacy ? item.displayUrl : item.url}`,
    `RuleScore: ${item.ruleScore}/100`,
    `MLScore: ${Number.isFinite(item.mlScore) ? item.mlScore : (item.privacy ? 'local-only' : 'offline')}`,
    `FinalScore: ${item.finalScore}/100`,
    `Formula: ${item.riskFormula || 'FinalScore = 0.40(RuleScore) + 0.60(MLScore)'}`,
    `Risk probability: ${Number.isFinite(item.riskProbability) ? item.riskProbability : '-'}`,
    `Decision: ${item.decision || '-'}`,
    `Warning threshold: ${Number.isFinite(item.warningThreshold) ? item.warningThreshold : '-'}`,
    `Blocking threshold: ${Number.isFinite(item.blockingThreshold) ? item.blockingThreshold : '-'}`,
    `Model version: ${item.modelVersion || '-'}`,
    `Policy version: ${item.policyVersion || '-'}`,
    `Privacy mode: ${item.privacy ? 'on' : 'off'}`,
    `Reasons: ${(item.reasons || []).slice(0, 5).map(flattenReason).join(' | ')}`,
    `Brand/Visual clues: ${(item.insights || []).join(' | ')}`
  ].join('\n');
}

function SafePreview({ result }) {
  let parsed;
  try {
    parsed = result?.url ? new URL(result.url) : null;
  } catch {
    parsed = null;
  }
  const level = result ? riskLevel(result.finalScore, result.warningThreshold, result.blockingThreshold) : null;
  return (
    <section className="preview">
      <div className="row-title">
        <h2>Safe Preview</h2>
        <span>{level?.label || 'รอการตรวจ'}</span>
      </div>
      <dl>
        <div><dt>โดเมน</dt><dd>{parsed?.hostname || '-'}</dd></div>
        <div><dt>โปรโตคอล</dt><dd>{parsed?.protocol ? parsed.protocol.replace(':', '').toUpperCase() : '-'}</dd></div>
        <div><dt>ปลายทาง</dt><dd>{result?.displayUrl || 'ยังไม่มีลิงก์'}</dd></div>
      </dl>
    </section>
  );
}

function AnalysisResult({ result, phase }) {
  const { submitFeedback } = useApp();
  const [feedbackStatus, setFeedbackStatus] = useState('');
  const [copyStatus, setCopyStatus] = useState('');
  if (!result) {
    return (
      <div className="empty">
        <div className="mark" />
        <h2>พร้อมตรวจสอบ</h2>
        <p>ผลวิเคราะห์จะแสดง RiskScore, การตัดสิน allow / warn / block, หลักฐานจากแต่ละชั้น และคำอธิบายจาก LLM</p>
      </div>
    );
  }

  const level = riskLevel(result.finalScore, result.warningThreshold, result.blockingThreshold);
  const reasons = (result.reasons || []).slice(0, 7);
  const policyText = Number.isFinite(result.warningThreshold)
    ? ` · warn ${result.warningThreshold} / block ${result.blockingThreshold}`
    : '';

  async function feedback(label) {
    setFeedbackStatus('กำลังบันทึก feedback...');
    setFeedbackStatus(await submitFeedback(label));
  }

  async function copyReport() {
    await navigator.clipboard?.writeText(reportText(result));
    setCopyStatus('คัดลอกสรุปแล้ว');
  }

  return (
    <div id="resultContent">
      <div className="result-head">
        <div>
          <p className={level.tone}>
            {phase === 'analyzing'
              ? 'กำลังตรวจหลักฐานหลายชั้นและคำนวณ RiskScore'
              : `ระดับความเสี่ยง: ${level.label}${policyText}`}
          </p>
          <h2>{result.url}</h2>
        </div>
        <div className={`score-ring risk-${level.key}`} style={{ '--score': result.finalScore }}>
          <span>{result.finalScore}</span><small>/100</small>
        </div>
      </div>

      <div className="score-grid">
        <div><span>RuleScore · 40%</span><strong>{result.ruleScore}</strong></div>
        <div><span>MLScore · 60%</span><strong>{Number.isFinite(result.mlScore) ? result.mlScore : (result.privacy ? 'local' : 'offline')}</strong></div>
        <div><span>FinalScore</span><strong>{result.finalScore}</strong></div>
      </div>

      <p className="score-formula">
        {Number.isFinite(result.mlScore)
          ? 'FinalScore = 0.40(RuleScore) + 0.60(MLScore)'
          : 'ML ยังไม่พร้อม จึงใช้ RuleScore เป็นคะแนนสำรองชั่วคราว'}
      </p>

      <section className="block">
        <div className="row-title">
          <h3>เหตุผลสำคัญ</h3>
          <span>{(result.threatTypes || []).slice(0, 3).join(' / ') || 'URL pattern'}</span>
        </div>
        <ul>
          {(reasons.length ? reasons : ['ยังไม่พบเหตุผลเสี่ยงสำคัญจากกฎที่ตรวจในขณะนี้'])
            .map((reason, index) => <li key={`${flattenReason(reason)}-${index}`}>{flattenReason(reason)}</li>)}
        </ul>
      </section>

      <section className="insight block">
        <div className="row-title">
          <h3>Brand / Visual clues beta</h3>
          <span>{result.finalScore >= (result.warningThreshold ?? 61) ? 'ควรตรวจสอบ' : 'ตรวจแล้ว'}</span>
        </div>
        <ul>{(result.insights || []).map(insight => <li key={insight}>{insight}</li>)}</ul>
      </section>

      <section className="llm block">
        <div className="row-title">
          <h3>คำอธิบายจาก LLM</h3><span>{result.llm?.state || 'รอผล'}</span>
        </div>
        <dl>
          <div><dt>ประเภทความเสี่ยง</dt><dd>{result.llm?.riskType || '-'}</dd></div>
          <div><dt>อธิบายแบบเข้าใจง่าย</dt><dd>{result.llm?.explanation || '-'}</dd></div>
          <div><dt>คำแนะนำ</dt><dd>{result.llm?.advice || '-'}</dd></div>
        </dl>
      </section>

      <section className="feedback block">
        <div className="row-title"><h3>ผลตรวจนี้ถูกต้องหรือไม่</h3><span>Feedback</span></div>
        <div className="feedback-actions">
          <button type="button" onClick={() => feedback('dangerous')}>อันตรายจริง</button>
          <button type="button" onClick={() => feedback('safe')}>แจ้งเตือนผิด</button>
          <button type="button" onClick={() => feedback('unsure')}>ไม่แน่ใจ</button>
        </div>
        <p aria-live="polite">{feedbackStatus}</p>
      </section>

      <div className="actions">
        <button className="secondary" type="button" onClick={copyReport}>คัดลอกสรุป</button>
        <a className="open-link" href={result.url} target="_blank" rel="noreferrer">เปิดลิงก์นี้</a>
      </div>
      <p className="message" aria-live="polite">{copyStatus}</p>
    </div>
  );
}

export function ScannerPage() {
  const { current, analysisPhase, formMessage, formError, analyzeUrl } = useApp();
  const [url, setUrl] = useState(current?.url || '');
  const formRef = useRef(null);

  useEffect(() => {
    document.title = 'ตรวจลิงก์ | Phish Radar AI';
    if (current?.url) setUrl(current.url);
  }, [current?.url]);

  async function handleSubmit(event) {
    event.preventDefault();
    const result = await analyzeUrl(url);
    if (result?.url) setUrl(result.url);
  }

  function focusScanner() {
    formRef.current?.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
      block: 'center'
    });
    formRef.current?.querySelector('input')?.focus({ preventScroll: true });
  }

  return (
    <MotionFrame>
      <section id="scan" className="page active">
        <header className="app-hero" aria-labelledby="scanHeroTitle">
          <div className="hero-radar" aria-hidden="true" data-reveal>
            <span className="hero-radar-core"><img src={brandIcon} alt="" /></span>
          </div>
          <p className="hero-context" data-reveal>พื้นที่วิเคราะห์ความเสี่ยงสำหรับทุกลิงก์</p>
          <h1 id="scanHeroTitle" className="app-hero-title" data-reveal>
            <span className="hero-title-line">ท่องเว็บไซต์อย่างปลอดภัยด้วย</span>
            <span className="hero-title-line hero-title-accent">Phis radar AI</span>
          </h1>
          <p className="hero-lede" data-reveal>
            ตรวจสอบ URL ด้วยหลักฐานจาก Rule-based, Machine Learning และคำอธิบายที่อ่านเข้าใจง่าย
            โดยยังให้คุณควบคุมข้อมูลที่ส่งออกจากเครื่องได้เสมอ
          </p>
          <div className="hero-actions" data-reveal>
            <button className="primary hero-primary" type="button" onClick={focusScanner}>
              เริ่มตรวจลิงก์ <Icon name="arrow" />
            </button>
          </div>
          <form ref={formRef} className="scan-form hero-scan-form" onSubmit={handleSubmit} data-reveal>
            <label htmlFor="urlInput">ลิงก์ที่ต้องการตรวจสอบ</label>
            <div className="input-row scan-input-row">
              <input
                id="urlInput"
                type="text"
                inputMode="url"
                autoComplete="url"
                placeholder="วาง URL ที่ต้องการตรวจสอบ"
                value={url}
                onChange={event => setUrl(event.target.value)}
                required
              />
              <button className="primary" type="submit" disabled={analysisPhase === 'analyzing'}>
                {analysisPhase === 'analyzing' ? 'กำลังตรวจ' : 'ตรวจสอบ'}
              </button>
            </div>
            <p className={`message ${formError ? 'error' : ''}`} aria-live="polite">{formMessage}</p>
          </form>
        </header>

        <div className="grid scanner-workbench" data-reveal>
          <section className="panel result-panel">
            <SafePreview result={current} />
            <AnalysisResult result={current} phase={analysisPhase} />
          </section>
        </div>
      </section>
    </MotionFrame>
  );
}
