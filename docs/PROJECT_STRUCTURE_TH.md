# โครงสร้างและขอบเขตของ Phish Radar AI

## แผนผังการทำงาน

```text
Chrome/Brave Extension ─┐
                       ├─> FastAPI Backend ─> MySQL/MariaDB
React Web App ─────────┘         │
                                 ├─> Machine Learning model.pkl
                                 ├─> Ollama / Qwen
                                 └─> feedback.csv
```

Frontend ทั้งสองตัวต้องเรียก Backend ผ่าน HTTP API และต้องไม่เชื่อมฐานข้อมูลโดยตรง

## โครงสร้างระดับบนสุด

| ตำแหน่ง | ขอบเขต | แก้เมื่อ |
| --- | --- | --- |
| `extension/` | Chrome/Brave Extension | การสแกนในหน้าเว็บ, Popup, Warning, QR และ Extension settings |
| `web-app/` | React + Vite Web App | Login, Scanner, Dashboard, Settings และ Web UI |
| `backend/` | Python FastAPI | API, Auth, History, Risk Model และ LLM integration |
| `database/mysql/` | MySQL schema และ migrations | เพิ่ม/เปลี่ยนตารางหรือ index |
| `scripts/` | Tests, validation และ maintenance | ตรวจระบบหรือทำงานซ้ำอัตโนมัติ |
| `docs/` | คู่มือและบันทึกการออกแบบ | อธิบายวิธีใช้และเหตุผลของระบบ |

## Configuration และ Launcher ที่ root

- `.env` — secret และค่าการเชื่อมต่อเฉพาะเครื่อง ห้าม commit
- `.env.example` — แม่แบบ configuration ที่ส่งต่อได้
- `start-backend.sh` — เปิด FastAPI พอร์ต 8765
- `start-web.sh` — เปิด React/Vite พอร์ต 5505
- `start-demo.sh` — เปิด Backend และ Web พร้อมกัน
- `migrate-db.sh` — รัน MySQL migrations
- `README.md` — คู่มือเริ่มต้นของทั้งโปรเจกต์
- `DESIGN.md` / `PRODUCT.md` — หลักการออกแบบและขอบเขตผลิตภัณฑ์

Presentation, PDF/PPTX, สคริปต์นำเสนอ และ Progress Update ไม่อยู่ใน Runtime
Project โดยจัดเก็บแยกที่ `../presentation-progress/`

## Source of truth

| เรื่อง | ไฟล์หลัก |
| --- | --- |
| Extension permissions/resources | `extension/manifest.json` |
| Extension RuleScore | `extension/analyzer.js` |
| Web RuleScore | `web-app/analyzer.js` |
| FuzzyScore | `backend/fuzzy_scoring.py` |
| Random Forest, learned fusion และ threshold | `backend/train_model.py` |
| FinalScore และ API `/predict` | `backend/app.py` |
| ML features | `backend/feature_extractor.py` |
| Train model/threshold | `backend/train_model.py` |
| Login และ session | `backend/auth_router.py` |
| Search history | `backend/history_router.py` |
| Database connection | `backend/database.py` และ `.env` |
| Database schema | `database/mysql/migrations/` |
| Qwen/Ollama explanation | `backend/llm_explainer.py` |
| React API client | `web-app/src/services/api.js` |
| React routes | `web-app/src/App.jsx` |

## ไฟล์ที่สร้างใหม่ได้และไม่ควรแก้ด้วยมือ

- `.venv/` — Python dependencies
- `web-app/node_modules/` — Node dependencies
- `web-app/dist/` — Production build ของ React
- `__pycache__/` และ cache/test artifacts

## ลำดับตรวจเมื่อเกิดปัญหา

1. ตรวจ Web พอร์ต 5505 และ Backend พอร์ต 8765
2. เปิด `/health` เพื่อตรวจ Model, Database และ Ollama
3. ถ้าเป็นปัญหา UI ให้ตรวจ `web-app/` หรือ `extension/` ตามหน้าที่เกิดปัญหา
4. ถ้า Login/History ผิดปกติ ให้ตรวจ Backend, `.env` และ MySQL
5. ถ้าไม่มี FuzzyScore, RandomForestScore หรือ learned fusion ให้ตรวจ `backend/model.pkl` และ `backend/data/risk_model_evaluation.json`
6. ถ้าไม่มีคำอธิบาย ให้ตรวจ Ollama พอร์ต 11434 และโมเดล Qwen
7. รัน `scripts/validate_project.ps1` ก่อนส่งต่อทุกครั้ง
