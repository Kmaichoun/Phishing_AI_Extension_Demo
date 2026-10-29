# เอกสารโปรเจกต์

เริ่มอ่านชุดส่งอาจารย์ล่าสุด 29 ตุลาคม 2026 ที่ [รายงานการส่ง](submission-20261029/README.md), [การทำงานของระบบ](submission-20261029/SYSTEM_WALKTHROUGH_TH.md), [โมเดลและข้อมูล](submission-20261029/MODEL_AND_DATA_TH.md) และ [ผลตรวจ](submission-20261029/VERIFICATION_TH.md) เอกสารเดิมด้านล่างเป็นประวัติหลายรุ่น ให้ตรวจ model/source identity ก่อนอ้างอิง

เอกสารถูกแยกออกจากไฟล์ runtime เพื่อลดโอกาสแก้ผิดส่วน โดย Chrome Extension อยู่ใน `extension/` และ React Web App อยู่ใน `web-app/`

## คู่มือหลัก

- [ชุดโครงบทความและคู่มือให้เพื่อนเขียน](paper/README.md) — ครบหัวข้อส่งอาจารย์ พร้อมข้อเท็จจริง แหล่งอ้างอิง และหลักฐานของรุ่นที่ตรวจวันที่ 17 ตุลาคม 2026

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
