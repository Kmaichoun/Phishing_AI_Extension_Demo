# คู่มือ Web Workspace สำหรับ Developer

## เปิดใช้งานในเครื่อง

1. เปิด MySQL ใน XAMPP และตรวจ `.env` ให้ชี้ฐานข้อมูลในเครื่องที่ต้องการ
2. รัน `./migrate-db.sh` ใน Git Bash จากรากโปรเจกต์ เพื่อเพิ่มตารางให้ครบ 001–006 ก่อนใช้ Backend รุ่นนี้ การล้างประวัติและ Feedback ต้องใช้ตารางใหม่ด้วย
3. เปิด Ollama สำหรับคำอธิบาย LLM แล้วรัน `./start-demo.sh` เพื่อเปิด Backend และ Web App
4. เข้า `http://127.0.0.1:5505/#/login` และตรวจสถานะในเมนูบัญชี → สถานะระบบ

Migration 005 เพิ่ม `ScanFeedback` และ 006 เพิ่ม `AuditEvents` ไม่ลบตารางหรือผู้ใช้เดิม ไม่ต้องตั้ง Role ของบัญชีทั่วไปเป็น Admin เพื่อใช้งาน Scanner

## หน้าจอและการใช้งาน

| หน้า | สิ่งที่ทำได้ |
| --- | --- |
| ตรวจลิงก์ | กรอก URL ที่ด้านบน ดูคะแนน/คำตัดสิน และเลือกแท็บหลักฐาน โมเดล LLM หรือ Feedback |
| QR | อ่าน QR แล้วตรวจ URL ผ่านกระบวนการวิเคราะห์เดียวกับ Scanner |
| Dashboard | สถิติของบัญชี กราฟ 14 วัน ตัวกรอง URL/ผลตัดสิน/วัน UTC/อุปกรณ์ แบ่งหน้า และดูรายละเอียด |
| วิธีการทำงาน | อ่านสูตร Threshold รุ่นโมเดลและค่าประเมินที่ Backend ใช้จริง ไม่กำหนดสูตรตายตัวใน UI |
| สถานะระบบ | แยก Backend, Database, Model และ LLM พร้อมแนวทางตรวจเมื่อบริการไม่พร้อม |
| ความปลอดภัย | ดูอุปกรณ์และ Session ของตนเอง ยกเลิก Session หรืออุปกรณ์อื่นโดยมีการยืนยัน |
| ตั้งค่าบัญชี | เปลี่ยนข้อมูลส่วนตัวและรหัสผ่าน ภายใต้เมนูหลักเดียวกับหน้าอื่น |
| Admin | ค้นหาผู้ใช้ เปลี่ยน Role/สถานะ ทบทวน Feedback และอ่าน Audit log |

Admin ไม่สามารถเปลี่ยนสิทธิ์/ระงับตัวเองจากหน้านี้ และระบบป้องกันการลบสิทธิ์ Admin คนสุดท้าย การแก้สิทธิ์หรือระงับบัญชีจะยกเลิก Session ของบัญชีเป้าหมาย Backend ตรวจสิทธิ์ทุกครั้ง ไม่พึ่งการซ่อนปุ่มอย่างเดียว

## ข้อมูลและข้อจำกัดที่ต้องเข้าใจ

- CSV/JSON ส่งออกเฉพาะรายการในหน้าปัจจุบันตามตัวกรอง ไม่ใช่ทั้งฐานข้อมูล CSV ป้องกันค่า URL ที่อาจถูกตีความเป็นสูตร
- PDF ใช้ปุ่มพิมพ์ แล้วเลือก Save as PDF ในเบราว์เซอร์ ไม่ใช่ระบบสร้าง PDF ฝั่ง Server
- ประวัติเก่าไม่ได้เก็บข้อความหลักฐาน/คำอธิบาย LLM ครบ จะแสดงว่าไม่มีข้อมูล ไม่สร้างเหตุผลย้อนหลังแทนข้อมูลจริง
- Feedback ไม่ทำให้โมเดลฝึกใหม่อัตโนมัติ จำนวนรายงานเตือนผิดไม่ใช่ค่า False Positive Rate จากชุดทดสอบ
- Privacy Mode แสดงประวัติ local ไม่เรียกบริการวิเคราะห์ระยะไกล บางความสามารถจึงไม่เท่ากับโหมดปกติ
- การเชื่อมต่อฐานข้อมูลใหม่ตั้ง Session time zone เป็น UTC ให้ตรงกับ API ตัวกรองวันใช้ UTC ส่วนเวลาในหน้าจอแสดงตามเครื่องผู้ใช้
- ไม่ปรับเวลารายการเก่าย้อนหลังอัตโนมัติ รายการที่สร้างเมื่อ MySQL ใช้เวลาท้องถิ่นอาจเหลื่อม ควรสำรองและตรวจช่วงข้อมูลก่อนทำ migration แก้เวลาแยกต่างหาก
- งานนี้ไม่เปลี่ยนสูตร/น้ำหนัก/Threshold หรือฝึกโมเดลใหม่ ไม่แก้โค้ด Chrome Extension

## จุดแก้โค้ด

- `web-app/src/pages/` — หน้าจอแต่ละส่วน
- `web-app/src/components/AppHeader.jsx`, `WorkspaceUi.jsx` และ `workspace.css` — เมนู องค์ประกอบร่วม และ responsive/print
- `web-app/src/contexts/AppContext.jsx` — สถานะตรวจ URL, การบันทึก, ป้องกันผลเก่าทับผลใหม่ และ Privacy Mode
- `web-app/src/services/api.js` — การเรียก API และ timeout
- `backend/workspace_router.py` — สิทธิ์ Security/Admin, Feedback, สถิติ และ Audit
- `backend/history_router.py`, `history_models.py` — ค้นหา/แบ่งหน้าประวัติ และล้างข้อมูลที่เกี่ยวข้อง
- `backend/database.py` — สถานะ schema และการเชื่อมต่อ UTC
- `database/mysql/migrations/005_create_scan_feedback.sql`, `006_create_audit_events.sql` — ตารางใหม่

## ตรวจหลังแก้ไข

จาก PowerShell ที่รากโปรเจกต์:

```powershell
.\.venv\Scripts\python.exe -B scripts/test_workspace_flow.py
.\.venv\Scripts\python.exe -B scripts/test_auth_flow.py
.\.venv\Scripts\python.exe -B scripts/test_history_flow.py
.\.venv\Scripts\python.exe -B scripts/test_account_settings_flow.py
node scripts/test_web_app_ui.js
```

จาก `web-app` รัน `npm run build` และตรวจหน้าจอจริงทั้ง Dark/Light บน Desktop/Mobile ด้วย การ build ผ่านอย่างเดียวไม่ได้ยืนยันกล้อง QR, การพิมพ์ PDF หรือความแม่นยำโมเดล

`test_workspace_flow.py` ใช้บัญชีทดสอบชั่วคราวและลบข้อมูลของบัญชีเหล่านั้นหลังจบ ปฏิเสธฐานข้อมูลที่ไม่ใช่ localhost อย่าปรับ guard นี้เพื่อนำไปรันทดสอบบนฐานข้อมูลอาจารย์หรือ production
