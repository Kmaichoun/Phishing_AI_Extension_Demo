import { useState } from 'react';
import { EmptyState, formatTime, Pager, ResourceState, useResource } from './WorkspaceUi';
import { api } from '../services/api';

const percent = value => Number.isFinite(value) ? `${(value * 100).toFixed(3)}%` : 'ไม่มีตัวอย่าง';
const number = value => Number.isFinite(value) ? value.toLocaleString('th-TH') : '—';
const dimensions = [['shape', 'รูปแบบ URL'], ['source', 'แหล่งข้อมูล'], ['length', 'ความยาว'], ['encoded', 'การเข้ารหัส URL']];

export function ModelLab({ data }) {
  const [selected, setSelected] = useState('');
  const [dimension, setDimension] = useState('shape');
  const current = data.items.find(item => item.id === selected) || data.items[0];
  const analysis = current?.analysis;
  if (!current) return <EmptyState>ยังไม่มีการทดลอง ให้ Dev สร้าง candidate และรัน analyze_model_errors.py ก่อน</EmptyState>;
  return <div className="workspace-page model-lab">
    <div className="workspace-notice"><p>นี่คือผลทดลองย้อนหลัง ยังไม่ใช่ความแม่นยำของการใช้งานจริง การดูหรือเลือกรอบทดลองไม่เปลี่ยนโมเดลที่เว็บใช้อยู่</p><small className="model-hash">รุ่นใช้งานจริง SHA-256: {data.production_sha256 || 'ไม่พบไฟล์โมเดล'}</small></div>
    <section className="workspace-section"><h2>เปรียบเทียบรอบทดลอง</h2><div className="workspace-table-wrap"><table className="workspace-table"><caption className="workspace-muted">FPR คือสัดส่วนเว็บปกติที่ถูกเตือน — เปรียบเทียบระหว่างรอบตรง ๆ ไม่ได้ เพราะชุดทดสอบต่างกัน</caption><thead><tr><th>รอบ / ข้อมูลทั้งหมด</th><th>สูตร</th><th>Warning FPR</th><th>Blocking FPR</th><th>ผลตรวจพร้อมใช้</th></tr></thead><tbody>{data.items.map(item => <tr key={item.id}><td>{item.id}<small>{number(item.rows)} รายการ</small></td><td>{item.formula || '—'}</td><td>{item.analysis ? percent(item.analysis.candidate.warning.fpr) : 'ยังไม่ตรวจ'}</td><td>{item.analysis ? percent(item.analysis.candidate.blocking.fpr) : 'ยังไม่ตรวจ'}</td><td>{item.promotion_ready ? 'ผ่านเกณฑ์ในระบบ' : 'ยังไม่พร้อม'}</td></tr>)}</tbody></table></div></section>
    <div className="workspace-select-label"><label htmlFor="model-experiment">เลือกรอบที่ต้องการวิเคราะห์</label><select id="model-experiment" value={current.id} onChange={event => setSelected(event.target.value)}>{data.items.map(item => <option key={item.id} value={item.id}>{item.id}</option>)}</select></div>
    {current.error && <div className="workspace-notice" role="status">{current.error}</div>}
    {analysis && <>
      <section className="workspace-section"><h2>{current.id} · สาเหตุที่ผ่าน / ไม่ผ่าน</h2><p>{current.formula}</p><p className="workspace-muted">Holdout {number(analysis.holdout_rows)} รายการ · ตรวจเมื่อ {formatTime(analysis.created_at)} · warning ≥ {analysis.thresholds.warning_threshold} / block ≥ {analysis.thresholds.blocking_threshold}</p>
        <ul className="model-checks">{analysis.checks.map(check => <li key={check.key}><span className={`decision-badge ${check.passed ? 'decision-allow' : 'decision-warn'}`}>{check.passed ? 'ผ่าน' : 'ไม่ผ่าน'}</span><span>{check.label}</span></li>)}</ul>
        <p>ข้อมูลสังเคราะห์ {number(analysis.quality.synthetic_rows)} รายการ · ป้ายเว็บปกติภายในที่ยังไม่ยืนยัน {number(analysis.quality.unverified_benign_rows)} รายการ · โดเมน Holdout ที่เคยเห็น {number(analysis.quality.previously_seen_holdout_domains)} โดเมน</p>
        <p className="workspace-muted">กลุ่มปัญหาอาจซ้อนกัน นับรวมเป็นจำนวน URL ที่ต้องแก้ไม่ได้ และยังไม่มี Temporal test ตามช่วงเวลา</p>
      </section>
      <section className="workspace-section"><h2>เทียบรุ่นใช้งานจริงบน Holdout ชุดเดียวกัน</h2><div className="workspace-table-wrap"><table className="workspace-table"><thead><tr><th>เกณฑ์</th><th>Candidate FPR / ขอบบน 95%</th><th>รุ่นใช้งานจริง FPR</th><th>Candidate Recall</th><th>รุ่นใช้งานจริง Recall</th></tr></thead><tbody>{['warning','blocking'].map(stage => <tr key={stage}><td>{stage}</td><td>{percent(analysis.candidate[stage].fpr)} / {percent(analysis.candidate[stage].fpr_upper_95)}</td><td>{percent(analysis.baseline[stage].fpr)}</td><td>{percent(analysis.candidate[stage].recall)}</td><td>{percent(analysis.baseline[stage].recall)}</td></tr>)}</tbody></table></div><p className="workspace-muted">Recall คือสัดส่วน URL อันตรายที่ตรวจพบ ขอบบน FPR ใช้สมมติฐานความเป็นอิสระของตัวอย่าง; URL ในโดเมนเดียวกันอาจสัมพันธ์กัน</p></section>
      <section className="workspace-section"><div className="workspace-actions"><h2>เตือนผิด / พลาดการเตือนตรงไหน</h2><div><label htmlFor="model-dimension">แยกตาม</label><select id="model-dimension" value={dimension} onChange={event => setDimension(event.target.value)}>{dimensions.map(([key,label]) => <option key={key} value={key}>{label}</option>)}</select></div></div><p className="workspace-muted">ใช้ Warning threshold: FP = เว็บปกติถูกเตือน · FN = URL อันตรายที่ไม่ถูกเตือน</p><div className="workspace-table-wrap"><table className="workspace-table"><thead><tr><th>กลุ่ม</th><th>เว็บปกติ / อันตราย</th><th>FP</th><th>FN</th><th>FPR</th><th>Recall</th></tr></thead><tbody>{analysis.slices.filter(slice => slice.dimension === dimension).map(slice => <tr key={slice.value}><td className="model-source">{slice.value}</td><td>{number(slice.warning.negatives)} / {number(slice.warning.positives)}</td><td>{number(slice.warning.fp)}</td><td>{number(slice.warning.fn)}</td><td>{percent(slice.warning.fpr)}</td><td>{percent(slice.warning.recall)}</td></tr>)}</tbody></table></div></section>
      <section className="workspace-section"><h2>ตรวจตัวอย่างในไฟล์ข้อมูล</h2><p className="workspace-muted">ตัวอย่างไม่เกินชนิดละ 10 รายการ ไม่ใช่การสุ่ม ใช้ SHA-256 หาแถวใน dataset.csv โดยไม่เปิดลิงก์อันตรายจากหน้านี้</p><div className="workspace-table-wrap"><table className="workspace-table"><thead><tr><th>ชนิด</th><th>Source / รูปแบบ</th><th>Rule / Final</th><th>URL SHA-256</th></tr></thead><tbody>{analysis.examples.map(item => <tr key={item.url_sha256}><td>{item.kind === 'false_positive' ? 'FP' : 'FN'}</td><td className="model-source">{item.source}<small>{item.shape}</small></td><td>{item.rule_score} / {item.score}</td><td><code className="model-hash">{item.url_sha256}</code></td></tr>)}</tbody></table></div></section>
    </>}
  </div>;
}

export function ReviewedFeedbackExport() {
  const [offset, setOffset] = useState(0);
  const resource = useResource(() => api.adminFeedbackExport(offset), [offset]);
  function download() {
    const blob = new Blob([JSON.stringify(resource.data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a'); link.href = url;
    link.download = `feedback-review-${offset + 1}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <section className="workspace-section"><h2>คิวข้อมูลสำหรับตรวจเพิ่มก่อนฝึก</h2><p>ส่งออกเฉพาะ Feedback ที่ Admin ยืนยันว่าเป็นเว็บปกติหรืออันตราย ข้อมูลนี้ยังฝึกไม่ได้ทันที เพราะประวัติตัด query ออกแล้ว ต้องรวบรวม URL ต้นฉบับพร้อมหลักฐานใหม่ ไม่ใช้ label นี้เหมารวมทั้งโดเมน</p><ResourceState resource={resource} />{resource.data && <><p>{resource.data.total} รายการที่ยืนยันแล้ว — Feedback เป็นกลุ่มผู้รายงาน ไม่ใช่ชุดวัด Accuracy</p><button disabled={!resource.data.items.length} onClick={download}>ดาวน์โหลด JSON ของหน้านี้ ({resource.data.items.length} รายการ)</button><Pager offset={offset} total={resource.data.total} onChange={setOffset} /></>}</section>;
}
