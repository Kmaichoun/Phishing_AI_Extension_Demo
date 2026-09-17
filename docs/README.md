# เอกสารโปรเจกต์

เอกสารถูกแยกออกจากไฟล์ runtime เพื่อลดโอกาสแก้ผิดส่วน โดย Chrome Extension อยู่ใน `extension/` และ React Web App อยู่ใน `web-app/`

## คู่มือหลัก

- [MODEL_UPGRADE_WORKFLOW_TH.md](MODEL_UPGRADE_WORKFLOW_TH.md) — Error Analysis, reviewed feedback, ข้อมูลรอบใหม่ และ gated promote/rollback
- [WORKSPACE_GUIDE_TH.md](WORKSPACE_GUIDE_TH.md) — การใช้ Scanner, Dashboard, Status, Security และ Admin พร้อม migration และการทดสอบ
- [SIMPLE_RISK_EXPERIMENT_TH.md](SIMPLE_RISK_EXPERIMENT_TH.md) — ตรวจสูตรเดิม แหล่ง Dataset การทดลองสูตรง่าย และเหตุผลที่ยังไม่ promote โมเดลใหม่
- [DEVELOPER_GUIDE_TH.md](DEVELOPER_GUIDE_TH.md) — คู่มือส่งต่อสำหรับ Developer ตั้งแต่ Clone, ติดตั้ง, เปิดทุกระบบ, ทดสอบ และ Git workflow
- [PROJECT_STRUCTURE_TH.md](PROJECT_STRUCTURE_TH.md) — แผนผัง Frontend, Extension, Backend, Database, ML/LLM และจุดแก้ปัญหา
- [LLM_SETUP_TH.md](LLM_SETUP_TH.md) — การเปิด backend และตั้งค่า LLM
- [REACT_WEB_APP_TH.md](REACT_WEB_APP_TH.md) — โครงสร้าง React, Router, Context, Vite และแนวทางพัฒนาต่อ
- [LLM_COMPARISON_TH.md](LLM_COMPARISON_TH.md) — เปรียบเทียบ OpenAI/Ollama และแผน benchmark
- [RISK_MODEL_METHODOLOGY_TH.md](RISK_MODEL_METHODOLOGY_TH.md) — FuzzyScore, Random Forest, learned fusion, grouped evaluation และการเลือก warn/block threshold ภายใต้ FPR
- [ฐานข้อมูลสมาชิก MySQL/MariaDB](../database/mysql/README_TH.md) — schema, ตารางผู้ใช้ และข้อมูลอุปกรณ์

ไฟล์นำเสนอ ประวัติการพัฒนา และรายงานความคืบหน้าอยู่แยกจาก Source Code ที่
`../../presentation-progress/`

เมื่อเพิ่มเอกสารเกี่ยวกับ Runtime ให้เก็บใน `docs/` ส่วน Presentation และ Progress
ให้เก็บในโฟลเดอร์ `presentation-progress/` ภายนอกโปรเจกต์
