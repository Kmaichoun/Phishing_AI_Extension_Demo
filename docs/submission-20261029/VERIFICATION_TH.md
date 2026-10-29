# บันทึกการตรวจชุดส่ง Phish Radar วันที่ 29 ตุลาคม 2026

เอกสารนี้ระบุสิ่งที่ตรวจจริงในรอบจัดชุดส่งอาจารย์ โดยแยกผลการตรวจ source/ไฟล์ การทดสอบแยกส่วน และส่วนที่ยังไม่ได้ทดสอบบริการจริง รายละเอียดที่เครื่องอ่านได้อยู่ใน [VERIFICATION.json](VERIFICATION.json)

## 1. ฐาน source และ artifact

เลือก source ของโครงการหลักในเครื่องเป็นฐาน นำเฉพาะ source/templates/schema/assets ตาม allowlist ไปเผยแพร่ที่ root ของ branch `submission/latest-project-20261029` ผ่าน worktree แยก ไม่เปลี่ยน branch `docs/article-handoff-20261017` ที่เก็บงานส่งต่อเดิม

- ตรวจ SHA256 ของ model ต้นทางแบบอ่าน bytes โดยไม่ deserialize ได้ `bc4e024e32aaf0ad695ea4a4dff552ece09d606c4963a49e8bf6aa8a447575bb` ตรงกับหลักฐานโมเดลและ evaluation
- ตรวจ archive เดิมวันที่ 2026-10-20 ได้ SHA256 `ce339100ea8d96d9222f14e053cd3bba222fa8a03248117bea39412436986e45` ตรง manifest เดิม
- source ที่คัดสำหรับเผยแพร่รอบนี้มี **237 ไฟล์**; ตรวจ manifest/hash ของไฟล์และ archive ชุดเผยแพร่ทุก entry ดูค่า archive สุดท้ายใน [CURRENT_SOURCE_MANIFEST.json](../ai/CURRENT_SOURCE_MANIFEST.json)
- source ของ application ที่เผยแพร่ตรงกับโครงการหลักก่อนจัดส่ง การเปลี่ยนแปลงสำหรับ publication ใน source allowlist มีเฉพาะ `.gitignore` และ `.gitattributes` เพื่อกัน private artifacts และรักษา bytes สำหรับตรวจ hash ข้อความเอกสารถูกปรับให้ตรง branch ใหม่
- JSON หลักฐานเดิมทั้งหกไฟล์ใน `docs/paper/evidence/` คง bytes เดิม ไม่สร้าง evaluation ใหม่หรือแก้ตัวเลขให้ดูดีขึ้น

บันทึกที่มารายไฟล์และรายการ legacy files ที่นำออกจากปลาย branch ใหม่อยู่ใน [SOURCE_PUBLICATION.json](SOURCE_PUBLICATION.json) ประวัติ Git และ branch เดิมยังอยู่ การคัดไฟล์รอบนี้ไม่ใช่การลบข้อมูลย้อนหลังจาก Git history

## 2. การตรวจที่ผ่านในรอบนี้

| รายการ | ผล | ขอบเขตหลักฐาน |
|---|---|---|
| Context inventory พร้อม hash-model/verify-snapshot ในโครงการหลัก | ผ่าน | ยืนยัน source/archive/model bytes และตรวจพบความต่างจาก nested legacy Git; ไม่เรียกบริการ |
| Inspector self-test | ผ่าน | parser, hash comparison, path traversal และการปฏิเสธ environment file |
| Source/archive credential preflight | ผ่านโดยไม่พบ findings ตามกฎเครื่องมือ | heuristic scan ของไฟล์ที่คัด ไม่ใช่การรับประกันว่าตรวจ secret ได้ทุกแบบ |
| Source file/ZIP entry hashes | ผ่าน | จำนวน ชื่อ ขนาด และ SHA256 ตรง manifest; ไม่มี missing/duplicate entry หรือ path หลุด allowlist |
| Python syntax | ผ่าน | parse ด้วย AST โดยไม่ import application หรือ load model; จำนวนไฟล์ใน JSON |
| JavaScript syntax | ผ่าน | `node --check` สำหรับ `.js`, `.cjs`, `.mjs`; JSX ตรวจผ่าน frontend build |
| Backend policy boundary | ผ่าน 9 กรณี | แยกเฉพาะ AST ของ `risk_decision` มารัน ไม่ import app/อ่าน `.env`/เรียก DB |
| `test_probability_calibration.py` | ผ่าน 3 tests | synthetic data และ in-memory serialization ของตัวอย่าง calibrator ไม่ใช่การ fit calibrator ของ model ที่รายงานใหม่ |
| `test_prediction_response.cjs` | ผ่าน | mock fetch ตรวจ malformed/valid response และ HTTP failure ของ Web API adapter |
| `test_result_presentation.cjs` | ผ่าน | render React component จริงด้วย context คงที่ ตรวจคะแนนเดียว/ข้อความสถานะ/คำอธิบาย/legacy compatibility |
| `test_ad_filter_policy.cjs` | ผ่าน 76 กรณี | positive/negative fixtures และการโหลดแบบ browser/CommonJS |
| `test_ad_popup_guard.cjs` | ผ่าน | mocked Chrome worker: popup, exceptions, first-party/login, error, race และ settings |
| Frontend build | ผ่าน 74 modules | ใช้ source โครงการหลักที่ hash ตรงกับชุดส่งและ dependency ที่มีอยู่; Vite ที่รันจริง 7.3.6 |
| ลิงก์ relative ในเอกสารที่จัดชุดส่งและจุดเริ่มอ่าน | ผ่าน | ตรวจว่าไฟล์เป้าหมายมีจริง ไม่ได้ตรวจความพร้อมของเว็บไซต์ภายนอก |

การทดสอบ calibration, API adapter, React presentation และ ad filtering ใช้ source โครงการหลักกับ dependencies ที่ติดตั้งอยู่แล้ว ตรวจ identity ของ source เทียบไฟล์ที่เผยแพร่ก่อนอ้างผล ไม่ใช่การติดตั้งและทดสอบใหม่จาก clean clone ส่วน syntax/policy/hash ตรวจบนไฟล์ชุดเผยแพร่โดยตรง

ระหว่าง calibration test มี `DeprecationWarning` เกี่ยวกับ `disp`/`iprint` ของ SciPy L-BFGS-B ผ่าน scikit-learn ผลทดสอบยังผ่าน ไม่มีการแก้ dependency เพื่อจัดเอกสารครั้งนี้

### Boundary ที่ตรวจจากฟังก์ชันจริงใน source

| คะแนนทศนิยม | Decision ที่ตรวจได้ |
|---:|---|
| 59 | allow |
| 60 | warn |
| 79 | warn |
| 80 | block |
| 59.6 | allow |
| 79.6 | warn |
| 59.99 | allow |
| 60.01 | warn |
| 80.01 | block |

กรณี 59.6/79.6 ช่วยยืนยันว่าฟังก์ชันรับค่าก่อนปัดตามนโยบาย แต่ผลนี้ยังไม่ใช่ HTTP test หรือการยืนยัน Web/Extension ที่เปิดอยู่จริง

## 3. สิ่งที่ไม่ได้ตรวจรอบนี้

- Live HTTP `/predict`, `/health`, auth, history, workspace และ chat รวมถึงความสอดคล้องกับ database schema ของเครื่องสาธิต
- MySQL/MariaDB connection, migrations, accounts, cookies, authorization และการบันทึกประวัติจริง
- Ollama/provider รุ่นที่ติดตั้ง ความพร้อม ความเร็ว คุณภาพคำอธิบาย และ cache จากคำตอบจริง
- Chrome Extension ที่โหลดในเบราวเซอร์, DOM ของเว็บจริง, กล้อง QR, network ของ Privacy Mode และการ reload source
- Public demo reachability, TLS/CORS/cookies และความพร้อม deployment
- Evaluation ใหม่บนข้อมูลเต็ม ชุด domain-disjoint/forward-temporal ใหม่ หรือผล accuracy ที่เพิ่มขึ้น
- การติดตั้ง dependency จาก clean clone, user study, ความพึงพอใจ, latency และ throughput benchmark

ค่า `runtime_verified=false` จึงคงไว้ ผลประเมินใน [MODEL_AND_DATA_TH.md](MODEL_AND_DATA_TH.md) เป็นผลเดิมตาม JSON ไม่ใช่ผลจาก tests ตารางข้างต้น และ `production_ready=false` / `statistical_gate_passed=false` ไม่เปลี่ยน

## 4. ประเด็นที่ต้องตรวจเพิ่มก่อนสาธิตครบระบบ

[รายงานการทำงาน](SYSTEM_WALKTHROUGH_TH.md) บันทึกความไม่ตรงกันของ history source จากแชต (`web-app-chat`), API/SQL source enum, ระดับการ validate response ของ Web/Extension และขอบเขตของ QR/local rules/Privacy Mode ไว้แล้ว เป็นข้อสังเกตจาก source ที่ยังต้องยืนยันด้วย HTTP/browser test

ยังไม่แก้ implementation หรือ schema เพื่อทำให้รายงานดูพร้อมใช้งาน การส่งครั้งนี้คัดและเผยแพร่ source พร้อมบันทึกความสามารถ/ข้อจำกัดตามหลักฐาน
