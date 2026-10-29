# Phish Radar AI

**ระบบต้นแบบช่วยประเมินความเสี่ยงของ URL ผ่าน Web Application และ Chrome Extension พร้อมคำอธิบายภาษาไทย**

ชุดส่งอาจารย์ปรับปรุงวันที่ **29 ตุลาคม 2569 (2026-10-29)** บน branch **`submission/latest-project-20261029`**

## สไลด์นำเสนอ

**[▶ เปิดดูสไลด์ครบ 12 หน้า](docs/submission-20261029/slides/README.md)** · [เปิด PDF](docs/submission-20261029/slides/%E0%B9%80%E0%B8%88%E0%B8%B2%E0%B8%B0%E0%B8%A5%E0%B8%B6%E0%B8%81%E0%B8%A3%E0%B8%B0%E0%B8%9A%E0%B8%9A%E0%B9%81%E0%B8%A5%E0%B8%B0%E0%B8%9C%E0%B8%A5%E0%B8%97%E0%B8%94%E0%B8%AA%E0%B8%AD%E0%B8%9A%20Phish%20Radar%20AI.pdf) · [ดาวน์โหลด PDF](docs/submission-20261029/slides/%E0%B9%80%E0%B8%88%E0%B8%B2%E0%B8%B0%E0%B8%A5%E0%B8%B6%E0%B8%81%E0%B8%A3%E0%B8%B0%E0%B8%9A%E0%B8%9A%E0%B9%81%E0%B8%A5%E0%B8%B0%E0%B8%9C%E0%B8%A5%E0%B8%97%E0%B8%94%E0%B8%AA%E0%B8%AD%E0%B8%9A%20Phish%20Radar%20AI.pdf?raw=1)

[![หน้าปกสไลด์ Phish Radar AI คลิกเพื่อดูครบ 12 หน้า](docs/submission-20261029/slides/previews/slide-01.png)](docs/submission-20261029/slides/README.md)

> เริ่มอ่าน [รายงานภาพรวมสำหรับอาจารย์](docs/submission-20261029/README.md) แล้วอ่าน [การทำงานของระบบ](docs/submission-20261029/SYSTEM_WALKTHROUGH_TH.md), [โมเดลและข้อมูล](docs/submission-20261029/MODEL_AND_DATA_TH.md), [วิธีติดตั้ง/สาธิต](docs/submission-20261029/SETUP_AND_DEMO_TH.md) และ [ผลตรวจสอบชุดส่ง](docs/submission-20261029/VERIFICATION_TH.md)

## โครงงานทำอะไร

Phish Radar AI รับ URL ที่ผู้ใช้ต้องการตรวจ วิเคราะห์ลักษณะของ URL และแสดงคะแนนพร้อมผล Allow / Warning / Block ช่วยให้ผู้ใช้พิจารณาความเสี่ยงก่อนเปิดลิงก์หรือกรอกข้อมูลสำคัญ มี Web Application สำหรับตรวจ URL/QR และจัดการบัญชี มี Chrome Extension ช่วยตรวจระหว่างใช้งาน browser และมี Backend เชื่อมโมเดล ฐานข้อมูล และบริการคำอธิบาย

ความสามารถใน source ได้แก่

- **Web ภาษาไทย:** Dashboard, ตรวจ URL/QR, ประวัติผลตรวจ, ตั้งค่า, ความปลอดภัยของบัญชี, สถานะบริการ และหน้าผู้ดูแล
- **Chrome Extension MV3:** ตรวจ URL/navigation, ลิงก์และฟอร์ม, ผลค้นหา, clipboard, หน้าเตือน, QR, Safe Preview และกรองโฆษณาตามการตั้งค่า
- **Prediction API:** URL features → Random Forest → calibration → คะแนนและ decision พร้อม model metadata
- **ระบบสมาชิก:** บัญชี Session ประวัติ Feedback และ Audit Events ผ่าน MySQL/MariaDB
- **คำอธิบายและแชต:** แยกจาก prediction; `/explain` รองรับ provider ตามการตั้งค่า ส่วน `/chat` ใช้ Ollama ใน source รุ่นนี้
- **Privacy Mode:** แยกการวิเคราะห์ภายใน browser ออกจากเส้นทาง backend/LLM และแสดงสถานะให้ผู้ใช้รับทราบ

ความสามารถข้างต้นเป็นสิ่งที่พบใน source การทำงานจริงขึ้นกับ artifact, settings, services และข้อจำกัดของ browser อ่านสิ่งที่ตรวจจริงใน [ผลตรวจสอบ](docs/submission-20261029/VERIFICATION_TH.md)

## เอกสารส่งอาจารย์

| เอกสาร | เนื้อหา |
| --- | --- |
| [สไลด์นำเสนอ (PDF)](docs/submission-20261029/slides/%E0%B9%80%E0%B8%88%E0%B8%B2%E0%B8%B0%E0%B8%A5%E0%B8%B6%E0%B8%81%E0%B8%A3%E0%B8%B0%E0%B8%9A%E0%B8%9A%E0%B9%81%E0%B8%A5%E0%B8%B0%E0%B8%9C%E0%B8%A5%E0%B8%97%E0%B8%94%E0%B8%AA%E0%B8%AD%E0%B8%9A%20Phish%20Radar%20AI.pdf) | สไลด์ที่เจ้าของโครงงานแนบสำหรับนำเสนอ |
| [รายงานภาพรวม](docs/submission-20261029/README.md) | ปัญหา วัตถุประสงค์ ขอบเขต สิ่งที่พัฒนา และฐาน source |
| [การทำงานของระบบ](docs/submission-20261029/SYSTEM_WALKTHROUGH_TH.md) | Architecture, request flow, API, Web, Extension, privacy, สมาชิก และ DB |
| [โมเดล ข้อมูล และผลประเมิน](docs/submission-20261029/MODEL_AND_DATA_TH.md) | รุ่น/hash สูตร/features นโยบาย ที่มาข้อมูล split Recall/FPR และข้อจำกัด |
| [ติดตั้งและสาธิต](docs/submission-20261029/SETUP_AND_DEMO_TH.md) | Clone, dependencies, `.env.example`, ฐานข้อมูล, model readiness และลำดับสาธิต |
| [ผลตรวจสอบชุดส่ง](docs/submission-20261029/VERIFICATION_TH.md) | รายการที่ตรวจผ่านและขอบเขตที่ยังไม่ได้ตรวจ |
| [ข้อเท็จจริงโมเดล](docs/paper/PROJECT_FACTS_TH.md) / [provenance ข้อมูล](docs/paper/DATASET_SOURCES_TH.md) | หลักฐานเดิมและ JSON สำหรับตรวจย้อนกลับ |
| [คู่มือรับช่วงสำหรับ AI](docs/ai/README.md) | ลำดับอ่าน แผนที่ source และข้อควรระวังของ artifact |

## สูตรและสถานะโมเดลที่อ้างในรายงาน

```text
URL → 174 features → Random Forest P(class=1) → Calibration → Score = calibrated probability ×100

Score < 60       : Allow
60 ≤ Score < 80  : Warning
Score ≥ 80       : Block
```

รุ่นที่อ้างคือ `url-risk-rf-reference-root-repair-support2-20261008`, schema `url-v10-reference-root-context`, `fusion_method=ml_only` Backend ใช้คะแนนก่อนปัดเศษตัดสินใจ Rule/Fuzzy และ LLM ไม่เปลี่ยนคะแนนสุดท้ายในโหมดนี้ การกรองโฆษณาเป็นการจัดการ DOM แยกจากโมเดล

```text
Model SHA256:
bc4e024e32aaf0ad695ea4a4dff552ece09d606c4963a49e8bf6aa8a447575bb
```

Artifact ยังมี `production_ready=false` และ `statistical_gate_passed=false` ผลประเมินที่แนบเป็นผลที่บันทึกไว้เดิม ไม่ใช่ evaluation ใหม่ในวันอัปเดต GitHub ควรอ่าน Recall คู่กับ FPR และขอบเขตชุดข้อมูล ไม่ใช้ผล Allow เป็นการรับรองความปลอดภัย

## Source และสิ่งที่เผยแพร่

Branch นี้นำ source ที่คัดจากโครงการหลักมาไว้ที่ root ของ repository เพื่อให้ตรงกับเอกสารรุ่นใหม่ ต่างจาก branch เดิม `docs/article-handoff-20261017` ซึ่ง application ที่ root ยังเป็นฐานเก่าจากเดือนกันยายน อ่าน [CURRENT_SOURCE_MANIFEST.json](docs/ai/CURRENT_SOURCE_MANIFEST.json) สำหรับวันที่ รายการไฟล์ และ SHA256 ของ source snapshot ที่แนบ

```text
backend/                    FastAPI, URL features, scoring, auth/history/workspace/chat
web-app/                    React/Vite Web Application
extension/                  Chrome Extension Manifest V3
database/mysql/             SQL schema, migrations และคู่มือฐานข้อมูล
scripts/                    เครื่องมือ inventory และ checks ตามขอบเขต
docs/submission-20261029/    รายงานฉบับอธิบายละเอียดสำหรับอาจารย์
docs/paper/                 หลักฐานโมเดล/ข้อมูลและคู่มือบทความเดิม
docs/ai/                    source snapshot, manifest และคู่มือรับช่วง
```

**ไม่แนบ** `.env`, credentials/tokens, model binary, raw datasets, reference-origin registry ต้นฉบับ, demo-authorization ต้นฉบับ, dependencies, build outputs หรือประวัติส่วนตัว จึงต้องเตรียม artifact ที่ตรงรุ่นเพิ่มเติมเพื่อสาธิต RF ครบระบบ การ clone อย่างเดียวใช้ศึกษาการทำงานและหลักฐานได้ ไม่ใช่การทำซ้ำการทดลองทั้งหมด

## เริ่มอ่านและเตรียมสาธิต

```powershell
git clone --branch submission/latest-project-20261029 --single-branch https://github.com/Kmaichoun/Phishing_AI_Extension_Demo.git
Set-Location Phishing_AI_Extension_Demo
python scripts/inspect_project_context.py --json --verify-snapshot
```

Inspector ใช้ standard library เป็นการอ่านไฟล์และ hash ไม่โหลด pickle ไม่อ่าน `.env` และไม่เรียกบริการ สำหรับการติดตั้ง Python/Node, ฐานข้อมูล, เปิด API/Web, ปรับปลายทาง Extension และสาธิตโมเดล ให้ทำตาม [คู่มือติดตั้งและสาธิต](docs/submission-20261029/SETUP_AND_DEMO_TH.md)

เทคโนโลยีหลัก: Python/FastAPI, scikit-learn/joblib, React/Vite, JavaScript Manifest V3, MySQL/MariaDB และ Ollama แบบเลือกใช้ รุ่น dependencies ใช้ [backend/requirements.txt](backend/requirements.txt) และ [web-app/package-lock.json](web-app/package-lock.json) เป็นหลัก

## ขอบเขตของโครงงาน

โครงงานนี้ใช้เพื่อการศึกษาและสาธิต ยังไม่มีหลักฐานรับรองความแม่นยำทั่วอินเทอร์เน็ต ความพร้อม production หรือการป้องกัน request ทุกชนิด ผลประเมินแต่ละชุดมีข้อจำกัดด้านเวลา โดเมน และประวัติข้อมูลที่ใช้พัฒนา อ่านรายละเอียดใน [โมเดลและข้อมูล](docs/submission-20261029/MODEL_AND_DATA_TH.md) และ [ผลตรวจสอบ](docs/submission-20261029/VERIFICATION_TH.md) ก่อนนำตัวเลขหรือภาพหน้าจอไปอ้างในรายงาน
