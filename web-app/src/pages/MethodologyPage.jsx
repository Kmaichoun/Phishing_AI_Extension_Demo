import { useApp } from '../contexts/AppContext';
import { PageTitle, SystemStrip, formatTime } from '../components/WorkspaceUi';
const percent = value => Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : '—';
export function MethodologyPage() {
  const { health, checkHealth } = useApp();
  const p = health?.model_policy;
  const independent = p?.evaluation_design?.independent_test !== false && p?.metrics?.independent_holdout;
  const metrics = independent || p?.metrics?.reused_benchmark;
  const metricRows = ['warning', 'blocking'].filter(key => metrics?.[key]);
  return <section className="workspace-page">
    <PageTitle title="วิธีการทำงาน" description="การประเมิน URL และเกณฑ์ของโมเดลที่กำลังใช้งาน"><button onClick={checkHealth}>โหลดข้อมูลใหม่</button></PageTitle>
    <SystemStrip />
    <ol className="pipeline-list"><li><strong>ตรวจ URL</strong><span>แยกชื่อโดเมนและโครงสร้าง URL</span></li><li><strong>ประเมินด้วยโมเดล</strong><span>{p?.fusion_method === 'ml_only' ? 'Random Forest และปรับเทียบคะแนน' : 'โมเดลตามรุ่นที่ Backend โหลด'}</span></li><li><strong>ตัดสินความเสี่ยง</strong><span>เทียบคะแนนกับเกณฑ์เตือนและบล็อก</span></li><li><strong>อธิบายผล</strong><span>LLM อธิบายผลและข้อสังเกตจาก URL โดยไม่เปลี่ยนคะแนน</span></li></ol>
    <section className="workspace-section"><h2>การคำนวณที่ใช้งานจริง</h2>
      {health?.model_ready && p?.risk_formula ? <p className="formula-display">{p.risk_formula}</p> : <p>ยังไม่ได้รับข้อมูลการคำนวณจากโมเดล</p>}
      {p?.fusion_method === 'ml_only' && <p>คะแนนสุดท้ายมาจาก Random Forest หลังปรับเทียบ ส่วนข้อสังเกตจาก URL และคำอธิบายจาก LLM ใช้ประกอบการอ่านผล</p>}
      <dl className="detail-list"><div><dt>Model version</dt><dd>{p?.model_version || 'ยังไม่มีข้อมูล'}</dd></div><div><dt>Policy version</dt><dd>{p?.policy_version || 'ยังไม่มีข้อมูล'}</dd></div><div><dt>เกณฑ์เตือน</dt><dd>{p?.warning_threshold ?? 'ยังไม่มีข้อมูล'}</dd></div><div><dt>เกณฑ์บล็อก</dt><dd>{p?.blocking_threshold ?? 'ยังไม่มีข้อมูล'}</dd></div>{p?.trained_at && <div><dt>ฝึกโมเดลเมื่อ</dt><dd>{formatTime(p.trained_at)}</dd></div>}</dl>
      <p className="workspace-muted">ต่ำกว่าเกณฑ์เตือน: allow / ตั้งแต่เกณฑ์เตือน: warn / ตั้งแต่เกณฑ์บล็อก: block คะแนนไม่ใช่การรับประกันความปลอดภัย</p>
      {p?.production_ready === false && <p className="workspace-notice">โมเดลทดลอง ยังไม่ผ่านเกณฑ์เปิดใช้งานจริงทั้งหมด</p>}
    </section>
    {metricRows.length > 0 && <section className="workspace-section"><h2>ผลการประเมินที่บันทึกไว้</h2>
      <div className="workspace-table-wrap"><table className="workspace-table"><caption>{independent ? 'ผลบนชุดทดสอบแยกที่โมเดลบันทึกไว้' : 'ผลบนชุดข้อมูลย้อนหลังที่เคยใช้ประเมินแล้ว ไม่ใช่ชุดทดสอบอิสระใหม่'}</caption><thead><tr><th>เกณฑ์</th><th>Precision</th><th>Recall</th><th>F1</th><th>ROC-AUC</th><th>FPR</th></tr></thead><tbody>{metricRows.map(key => <tr key={key}><th>{key === 'warning' ? 'เตือน' : 'บล็อก'}{Number.isFinite(metrics[key].threshold) && ` ≥ ${Number((metrics[key].threshold * 100).toFixed(2))}`}</th>{['precision','recall','f1','roc_auc','false_positive_rate'].map(metric => <td key={metric}>{percent(metrics[key][metric])}</td>)}</tr>)}</tbody></table></div>
      <p className="workspace-muted">FPR คือสัดส่วน URL ปกติที่ถูกเตือนหรือบล็อกผิดบนชุดข้อมูลที่มี label อ้างอิง ผลนี้ไม่ยืนยันความแม่นยำกับทุกเว็บไซต์ในปัจจุบัน</p>
    </section>}
    <section className="workspace-section"><h2>ข้อจำกัดและ False Positive</h2><p>URL ของเว็บปกติอาจมีโครงสร้างคล้าย URL อันตรายและถูกเตือนผิดได้ ควรตรวจโดเมน แหล่งที่มา และข้อสังเกตในผลตรวจเพิ่มเติม การเป็น HTTPS เพียงอย่างเดียวไม่ยืนยันว่าเว็บไซต์ปลอดภัย</p><p>Feedback ต้องผ่านการตรวจทานก่อนนำไปฝึกโมเดล และจำนวนผู้รายงานว่าเตือนผิดไม่ใช่อัตรา False Positive ของทั้งระบบ</p></section>
  </section>;
}
