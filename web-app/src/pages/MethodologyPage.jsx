import { useApp } from '../contexts/AppContext';
import { PageTitle, SystemStrip, formatTime } from '../components/WorkspaceUi';
const percent = value => Number.isFinite(value) ? `${(value * 100).toFixed(2)}%` : 'ไม่มีข้อมูล';
export function MethodologyPage() {
  const { health, checkHealth } = useApp();
  const p = health?.model_policy;
  const holdout = p?.metrics?.independent_holdout;
  const evaluation = p?.evaluation_design;
  return <section className="workspace-page">
    <PageTitle title="วิธีการทำงาน" description="สูตร เกณฑ์ตัดสิน และค่าประเมินของโมเดลที่ Backend กำลังใช้งาน"><button onClick={checkHealth}>โหลดข้อมูลใหม่</button></PageTitle>
    <SystemStrip />
    <ol className="pipeline-list"><li><strong>ตรวจ URL</strong><span>แยกโดเมนและหลักฐานตามกฎ</span></li><li><strong>ประเมินด้วยโมเดล</strong><span>Fuzzy evidence และ Random Forest ตามรุ่นที่โหลด</span></li><li><strong>ตัดสินความเสี่ยง</strong><span>รวมผลตาม Policy และเทียบ Threshold</span></li><li><strong>อธิบายผล</strong><span>LLM อธิบายหลักฐาน ไม่เปลี่ยนคะแนน</span></li></ol>
    <section className="workspace-section"><h2>สูตรที่ใช้งานจริง</h2><p className="formula-display">{health?.model_ready ? p?.risk_formula || 'โมเดลไม่ได้บันทึกสูตร' : 'ยังไม่ยืนยันสูตรของโมเดล กรุณาตรวจสถานะระบบ'}</p>
      <dl className="detail-list"><div><dt>Model version</dt><dd>{p?.model_version || 'ไม่มีข้อมูล'}</dd></div><div><dt>Policy version</dt><dd>{p?.policy_version || 'ไม่มีข้อมูล'}</dd></div><div><dt>Warning threshold</dt><dd>{p?.warning_threshold ?? 'ไม่มีข้อมูล'}</dd></div><div><dt>Blocking threshold</dt><dd>{p?.blocking_threshold ?? 'ไม่มีข้อมูล'}</dd></div><div><dt>ฝึกโมเดลเมื่อ</dt><dd>{formatTime(p?.trained_at)}</dd></div></dl>
      <p className="workspace-muted">คะแนนต่ำกว่า Warning: allow / ตั้งแต่ Warning: warn / ตั้งแต่ Blocking: block คะแนนเป็นค่าความเสี่ยงตาม Policy ไม่ใช่การรับประกันความปลอดภัย</p>
    </section>
    <section className="workspace-section"><h2>ตัวแปรในสูตรมาจากไหน</h2><dl className="detail-list">
      <div><dt>RuleScore</dt><dd>คะแนน 0–100 จากกฎที่ตรวจโครงสร้าง URL เช่น IP ในชื่อโฮสต์, punycode, URL ซ้อน, redirect parameter, คำชวนกรอกข้อมูล และไฟล์เสี่ยง</dd></div>
      <div><dt>FuzzyScore</dt><dd>การแปลง RuleScore ให้เป็นระดับ safe / suspicious / dangerous แบบต่อเนื่อง จึงเป็นข้อมูลจาก RuleScore เดิม ไม่ใช่หลักฐานอิสระอีกชุด</dd></div>
      <div><dt>RandomForestScore หรือ MLScore</dt><dd>ความน่าจะเป็นหลังปรับเทียบ 0–100 จาก Random Forest ที่อ่านตัวแปรเชิงโครงสร้างของ URL เช่น ความยาว path/query, จำนวนจุด ตัวเลข subdomain entropy และอักขระเข้ารหัส</dd></div>
      <div><dt>LearnedFusion</dt><dd>Logistic model ที่เรียนวิธีรวม FuzzyScore กับ RandomForestScore จากข้อมูลฝึก ไม่ใช่น้ำหนัก 40/60 ที่กำหนดเอง</dd></div>
      <div><dt>ConsensusGuardrail</dt><dd>กฎที่ดันคะแนนขึ้นเมื่อ Fuzzy และ ML สูงพร้อมกัน ขั้นนี้ทำให้สูตรเดิมอธิบายยากและอาจกระจุกที่ 99–100</dd></div>
      <div><dt>Warning / Blocking threshold</dt><dd>จุดตัดสำหรับ allow, warn และ block ต้องเลือกจาก Validation ภายใต้เพดาน False Positive แล้วตรวจซ้ำกับ Holdout ที่ไม่ใช้ฝึก</dd></div>
    </dl></section>
    <section className="workspace-section"><h2>สูตรที่เสนอให้เรียบง่ายขึ้น</h2>
      <p className="formula-display">FinalScore = MLScore</p>
      <p>เหตุผลคือ FuzzyScore ถูกสร้างจากกฎบน URL และ Random Forest ก็อ่านลักษณะ URL เช่นกัน การนำมารวมซ้ำอาจนับสัญญาณเดียวกันสองครั้ง สูตรที่เสนอจึงใช้คะแนน ML ที่ calibrate แล้วในการตัดสิน และเก็บ RuleScore ไว้อธิบายเหตุผลแก่ผู้ใช้</p>
      <p className="workspace-notice">ยังไม่ใช่สูตร Production: การทดลองกับข้อมูลเพิ่ม 256,297 URL ลดปัญหาลิงก์ตัวอย่างบางชุดได้ แต่ไม่ผ่านเพดาน False Positive บน Holdout จากต่างแหล่ง จึงยังไม่แทนโมเดลที่ใช้งานอยู่</p>
    </section>
    <section className="workspace-section"><h2>ข้อมูลและการประเมิน</h2><dl className="detail-list">
      <div><dt>ข้อมูลทั้งหมด</dt><dd>{p?.dataset_row_count?.toLocaleString() ?? 'ไม่มีข้อมูล'} รายการ</dd></div>
      <div><dt>Development / OOF</dt><dd>{evaluation?.development_rows?.toLocaleString() ?? 'ไม่ได้บันทึกแยกในโมเดล'}</dd></div>
      <div><dt>Independent holdout</dt><dd>{evaluation?.holdout_rows?.toLocaleString() ?? 'ไม่ได้บันทึกแยกในโมเดล'}</dd></div>
      <div><dt>วิธีแบ่งข้อมูล</dt><dd>{p?.cv_strategy || 'ไม่มีข้อมูล'}</dd></div></dl>
      <p>{evaluation ? 'Development ใช้ฝึกและตรวจสอบแบบแบ่งกลุ่ม (OOF) ส่วน Holdout ใช้ประเมินแยกต่างหาก โดยจำนวนและวิธีแบ่งอ้างอิงจาก metadata ของโมเดล' : 'โมเดลรุ่นนี้ไม่ได้ส่งรายละเอียดการแบ่งข้อมูล จึงยังยืนยันจำนวน Train, Validation และ Test แยกชุดไม่ได้'}</p>
      <div className="workspace-table-wrap"><table className="workspace-table"><caption>ผลบน independent holdout ของ Policy นี้</caption><thead><tr><th>เกณฑ์</th><th>Precision</th><th>Recall</th><th>F1</th><th>ROC-AUC</th><th>FPR</th></tr></thead><tbody>{['warning', 'blocking'].map(key => <tr key={key}><th>{key}</th>{['precision','recall','f1','roc_auc','false_positive_rate'].map(metric => <td key={metric}>{percent(holdout?.[key]?.[metric])}</td>)}</tr>)}</tbody></table></div>
      <p className="workspace-muted">FPR = FP / (FP + TN) บนชุดที่มีคำตอบอ้างอิง ค่าเป้าหมายในการเลือก Threshold อาจต่างจาก FPR ที่วัดได้บน Holdout</p>
    </section>
    <section className="workspace-section"><h2>ข้อจำกัดและ False Positive</h2><p>URL ของเว็บปกติที่มี query ยาวหรืออักขระเข้ารหัสอาจมีลักษณะคล้าย URL อันตราย ควรตรวจเหตุผลและส่ง Feedback เมื่อพบผลผิดพลาด การเป็น HTTPS เพียงอย่างเดียวไม่ยืนยันว่าเว็บไซต์ปลอดภัย</p><p>ข้อมูลจากผู้ใช้เป็นรายงานที่ต้องตรวจทานก่อนนำไปฝึกใหม่ สัดส่วนผู้รายงานว่าเตือนผิดไม่ใช่ FPR ของทั้งระบบ และค่าประเมินในหน้านี้ไม่ใช่ผลทดสอบกับเว็บไซต์ทั้งหมดบนอินเทอร์เน็ต</p></section>
  </section>;
}
