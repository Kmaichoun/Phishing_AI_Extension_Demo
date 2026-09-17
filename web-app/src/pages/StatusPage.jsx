import { useApp } from '../contexts/AppContext';
import { PageTitle, formatTime, serviceStates } from '../components/WorkspaceUi';

const guidance = {
  backend: 'เปิด Backend ด้วย ./start-backend.sh หรือ ./start-demo.sh',
  database: 'กด Start ที่ MySQL ใน XAMPP แล้วตรวจค่าฐานข้อมูลใน .env',
  model: 'ตรวจว่า backend/model.pkl มีอยู่และเป็นโมเดลที่ใช้กับโปรเจกต์นี้',
  llm: 'เปิด Ollama และติดตั้งโมเดลที่ระบุใน .env เช่น ollama pull qwen3:4b'
};
export function StatusPage() {
  const { health, backendStatus, checkHealth, privacyMode } = useApp();
  const services = serviceStates(health, privacyMode, backendStatus.online === null);
  return <section className="workspace-page">
    <PageTitle title="สถานะระบบ" description="ตรวจความพร้อมของแต่ละบริการ และดูขั้นตอนแก้ไขเมื่อเชื่อมต่อไม่ได้"><button onClick={checkHealth} disabled={backendStatus.online === null}>ตรวจอีกครั้ง</button></PageTitle>
    {privacyMode && <p className="workspace-notice">Privacy Mode เปิดอยู่ จึงไม่ตรวจบริการภายนอก ปิดได้จากเมนูบัญชี</p>}
    <div className="workspace-section service-list">{services.map(item => <section key={item.key}>
      <div><h2>{item.name}</h2><span className={`decision-badge ${!privacyMode && item.ready ? 'decision-allow' : 'decision-unknown'}`}>{item.text}</span></div>
      <p>{privacyMode ? 'ข้ามการเรียกบริการในโหมดส่วนตัว' : backendStatus.online === null ? 'กำลังตรวจสอบการเชื่อมต่อ' : item.ready ? (item.key === 'llm' ? 'คำอธิบายพร้อมใช้งาน และไม่มีผลต่อคะแนนความเสี่ยง' : 'เชื่อมต่อบริการได้') : guidance[item.key]}</p>
    </section>)}</div>
    <p className="workspace-muted">ตรวจล่าสุด: {formatTime(health?.checkedAt)}</p>
    {!privacyMode && <section className="workspace-section"><h2>ความพร้อมของฐานข้อมูล</h2><dl className="detail-list">
      <div><dt>ฐานข้อมูล</dt><dd>{health?.database?.database || 'ยังเชื่อมต่อไม่ได้'}</dd></div>
      <div><dt>บัญชีและ Session</dt><dd>{health?.database?.auth_schema_ready ? 'พร้อม' : 'ยังไม่พร้อม'}</dd></div>
      <div><dt>ประวัติและข้อมูลโมเดล</dt><dd>{health?.database?.risk_audit_schema_ready ? 'พร้อม' : 'ยังไม่พร้อม'}</dd></div>
      <div><dt>Feedback และ Audit Log</dt><dd>{health?.database?.workspace_schema_ready ? 'พร้อม' : 'ต้องนำเข้า SQL 005 และ 006'}</dd></div>
    </dl></section>}
    <section className="workspace-section"><h2>เริ่มใช้งานบนเครื่องนี้</h2><ol className="setup-list">
      <li>เปิด MySQL ใน XAMPP เพื่อใช้บัญชีและบันทึกประวัติ</li><li>เปิด Ollama เพื่อรับคำอธิบายจาก LLM</li>
      <li>เปิด Git Bash ในโฟลเดอร์โปรเจกต์ แล้วรัน <code>./start-demo.sh</code> เพื่อเปิด Backend และ Web App</li></ol>
      <p>Extension: เปิดหน้าจัดการส่วนขยาย เปิด Developer mode แล้วเลือก Load unpacked ที่โฟลเดอร์ <code>extension/</code></p>
      <p className="workspace-muted">หน้าเว็บนี้ยังไม่ตรวจยืนยันการติดตั้ง Extension อัตโนมัติ</p>
    </section>
  </section>;
}
