# วิเคราะห์ข้อผิดพลาดและเปลี่ยนรุ่นโมเดล

## ข้อมูลวิจัยรอบ 17 กันยายน 2026

เพิ่มตัวเก็บข้อมูล `scripts/collect_research_urls.py` และช่องทาง `--published-data` ใน trainer แยกจาก CSV ที่คนตรวจทานเอง ไม่อ้างว่าผู้พัฒนาได้ตรวจทุก URL และไม่เติมวันดาวน์โหลดเป็นวันสังเกต URL

- [PhreshPhish — Dalton และคณะ](https://huggingface.co/datasets/phreshphish/phreshphish): เฉพาะ publisher train 498,255 แถว, revision `eabec4b7a66324b79cc8a0ad856d1731dc26fe1a`, CC BY 4.0 ใช้เพื่อวิจัยต่อต้าน phishing ไม่แตะ publisher test
- [URL-Phish v1 — Linh Dam Minh และ Hung Tran Cong](https://data.mendeley.com/datasets/65z9twcx3r/1): CC BY 4.0 กันไว้เป็นแหล่งทดสอบภายนอก ตัด 24,913 แถวที่โดเมนเคยอยู่ในรอบก่อน เหลือ 91,687 แถวก่อน deduplicate/ตรวจ label ขัดแย้งใน trainer
- ไฟล์ URL-Phish ที่ดาวน์โหลดมีจริง 116,600 แถว ไม่ตรงกับตัวเลข 111,660 บนหน้าคำอธิบาย จึงใช้จำนวนจากไฟล์พร้อม SHA-256 ไม่คัดลอกจำนวนจากบทความมาเป็นผลการทดลอง
- อ่าน PhreshPhish ด้วย HTTPS byte ranges เฉพาะ URL/label/date และ metadata ไม่ดาวน์โหลดคอลัมน์ HTML ทั้งชุด และไม่เปิด URL ใดใน dataset
- บันทึก checksum ของ CSV ที่ดึงออกมา ส่วน checksum ของ Parquet ต้นฉบับเป็นค่าที่ publisher ประกาศ **ไม่ได้อ้างว่าได้ตรวจ hash ของไฟล์เต็ม** เพราะไม่ได้ดาวน์โหลดเต็มไฟล์

ข้อจำกัดสำคัญ: [บทความ PhreshPhish ภาคผนวก C.2](https://arxiv.org/html/2507.10854v1) ระบุว่าตัด query ของฝั่ง benign เพื่อปกป้อง PII ข้อมูลที่ผ่านการตรวจรูปแบบ URL จึงมี benign query เพียง 16 แถว แต่ phishing query 16,349 แถว ความต่างนี้อาจเป็นอคติจากการเตรียมข้อมูล ไม่ใช่สัญญาณ phishing จริง ห้ามอ้างว่าชุดนี้แก้ปัญหา Google Search/query ยาวได้โดยอัตโนมัติ ส่วน URL-Phish ใช้ benign จาก ROR และ phishing จาก PhishTank จึงเป็น benchmark ตาม label ของ publisher ไม่ใช่การรับรองความปลอดภัยปัจจุบัน

คำสั่งเก็บข้อมูล (ไม่เปลี่ยน production):

```bash
./.venv/Scripts/python.exe -m pip install -r backend/requirements-training.txt
./.venv/Scripts/python.exe -B scripts/collect_research_urls.py
```

ข้อมูลดิบ/URL เก็บใน `backend/data/cache/research-20260917/` ซึ่ง Git ignore ไว้ ข้อมูลที่เก็บเสร็จแล้วจะตรวจ checksum และใช้สำเนาเดิม ไม่เขียนทับหรืออ้างว่าเป็นข้อมูลใหม่ ให้ใช้ `--output` ใหม่สำหรับการเก็บอีกครั้ง และต้องยังตรวจประวัติการเห็นโดเมนด้วย

คำสั่งที่ใช้สร้างการทดลอง `simple_v4`:

```bash
./.venv/Scripts/python.exe -B backend/train_simple_model.py --uci-limit 235795 --mendeley --balance-shapes --published-data backend/data/cache/research-20260917/manifest.json --external-source published_urlphish_v1 --trees 180 --output backend/data/simple_v4
```

นี่เป็นคำสั่งบันทึกวิธีทดลอง ไม่ใช่คำสั่งให้รันซ้ำทับผลเดิม: output ต้องเป็นโฟลเดอร์ใหม่ และโดเมนที่เคยใช้ใน v4 จะถือว่าเคยเห็นแล้วในรอบถัดไป การตรวจซ้ำผลเดิมใช้ regression/error analysis ส่วนการอ้างผลทดสอบอิสระรอบใหม่ต้องมีข้อมูลใหม่จริง

ผลจำนวนแถว การเลือกสูตร และเปรียบเทียบ baseline อยู่ใน `backend/data/simple_v4/evaluation.json`; การตรวจ gate และผลย่อยอยู่ใน `error_analysis.json` เอกสารนี้ไม่แทนที่ผลตรวจ checksum ล่าสุด

### ผลจริงของ simple_v4

- หลัง normalization/deduplicate/conflict removal มี 836,508 แถว: Train 641,032, Calibration 22,938, Validation 23,314 และ Holdout 149,224 แถว แบ่งตาม registered domain ไม่ซ้ำ
- Validation เลือก `FinalScore = MLScore` ที่ warning 92.6 และ blocking 95.6; สูตร `0.40 RuleScore + 0.60 MLScore` มี Recall ต่ำกว่าที่ FPR ระดับเดียวกัน จึงไม่ถูกเลือก
- บน Holdout ใหม่ ML-only ลด warning FPR จาก production 29.50% เหลือ 27.16% และเพิ่ม warning Recall จาก 43.35% เป็น 48.26% แต่ยังห่างจากเกณฑ์ FPR 1% มาก
- blocking Recall เพิ่มจาก 4.52% เป็น 16.39% แต่ blocking FPR เพิ่มจาก 0.0576% เป็น 0.1302% (ขอบบน 95% = 0.1480%) จึงเกินเกณฑ์ 0.1%
- ชุดต่างแหล่ง URL-Phish มี warning FPR 39.99% และ Recall 35.86% แย่กว่า production ในทั้งสองค่า; ใช้แสดง source shift ได้ แต่ไม่รองรับการ promote
- กลุ่ม query ใน Holdout ดีขึ้นจาก warning FPR 55.47% เป็น 21.21% แต่ยังสูง และ Google Search query ยาวยังได้ 95/100 จึงไม่ผ่าน known-benign regression
- ผ่านด้าน provenance/split/freshness แต่ไม่ผ่าน regression, FPR และ external-source gates; `promotion_ready=false`

ดังนั้น `simple_v4` เป็น **research candidate ที่พอใช้สำหรับดูผลใน Model Lab** ไม่ใช่โมเดลใช้งานจริง ระบบไม่ได้เปลี่ยน `backend/model.pkl` และไม่มีการลด threshold/เพิ่ม allowlist เพื่อซ่อน false positive

## ส่วนที่เพิ่ม

- Admin → วิเคราะห์โมเดล: เปรียบเทียบ experiment, FPR/Recall, threshold, FP/FN แยก source, path/query/root, ความยาว และ percent encoding
- เปรียบเทียบ candidate กับ production บน Holdout ชุดเดียวกัน ไม่ตีความการเทียบข้ามรอบเป็นการเทียบชุดเดียวกัน
- ตรวจโดเมนซ้ำระหว่างชุด/รอบ, ข้อมูลสังเคราะห์ และ benign labels ภายในที่ยังไม่มีหลักฐานยืนยัน
- ผูกผลประเมินกับ SHA-256 ของ candidate/dataset/evaluation/regression, production และโค้ดคำนวณ หากเปลี่ยนต้องประเมินใหม่
- ส่งออกคิว Feedback ที่ Admin ยืนยันแล้วเป็น JSON หน้าละ 30 รายการ ไม่รวม unsure/pending/dismissed ไม่ส่งชื่อ อีเมล หรือหมายเหตุผู้ตรวจ
- CLI ตรวจความพร้อม, promote พร้อม backup และ rollback แบบตรวจ checksum ไม่มีตัวเลือกข้ามเกณฑ์

Backend ตรวจสิทธิ์ Admin เอง เว็บอ่านเฉพาะ JSON/metadata ไม่มี endpoint อัปโหลด pickle, train หรือ promote โหลด pickle เฉพาะสคริปต์ Dev จากไฟล์ในเครื่องที่เชื่อถือได้

## ข้อค้นพบจากรอบเดิม

| กลุ่มใน Holdout v2 | เว็บปกติ | เตือนผิด (FP) | FPR | Recall ฝั่งอันตราย |
| --- | ---: | ---: | ---: | ---: |
| root | 15,446 | 177 | 1.146% | 91.13% |
| path | 461 | 15 | 3.254% | 32.83% |
| query | 27 | 8 | 29.630% | 81.08% |
| Mendeley | 860 | 190 | 22.093% | 37.78% |
| UCI | 15,074 | 10 | 0.066% | 83.08% |

แถวรูปแบบกับแถวแหล่งข้อมูลซ้อนกัน ห้ามบวกจำนวนรวม กลุ่ม query มีเว็บปกติเพียง 27 ตัวอย่าง อัตรายังไม่เสถียร ข้อมูลรวมจำนวนมากไม่ชดเชยการขาดกลุ่มนี้ ผลนี้เป็นการวิเคราะห์ย้อนหลัง ไม่ใช่การทดสอบกับเว็บไซต์ปัจจุบันทั้งหมด

v2/v3 มีข้อมูลเติม query/subdomain สังเคราะห์ 166 แถว และ benign labels ภายในที่ต้องตรวจหลักฐาน 691 แถว (กลุ่มซ้อนกันได้) v3 มีโดเมน Holdout ที่เคยเห็น 26,159 โดเมน รวม 98 โดเมนจากชุดฝึก production จึงไม่ใช่ external benchmark ใหม่ที่ไม่เคยใช้ปรับแนวทาง

ทั้ง v1/v2/v3 ยังไม่ผ่านเงื่อนไขครบ **ไม่ได้เปลี่ยน `backend/model.pkl`** และยังไม่มี candidate รุ่นใหม่ที่รับรองว่าลด false positive ในการใช้งานจริง

## เปิดดูในเว็บ

เปิด MySQL ตามคู่มือเดิม รีสตาร์ต Backend เพื่อโหลด route ใหม่ และเปิด Web App ด้วย `./start-demo.sh` จากนั้นเข้าบัญชี Admin → เมนูบัญชี → จัดการระบบ → วิเคราะห์โมเดล ไม่ต้องสร้างตารางใหม่สำหรับ Model Lab; Feedback ใช้ migration 005/006 เดิม

ถ้ารายงานไม่ตรงกับไฟล์ปัจจุบัน ให้รันคำสั่งประเมินด้านล่างแล้วกดรีเฟรช

## ตรวจรอบเดิม

รันจากโฟลเดอร์หลักของโปรเจกต์:

```bash
./.venv/Scripts/python.exe -m pip install -r backend/requirements-training.txt
./.venv/Scripts/python.exe -B scripts/check_candidate_model.py backend/data/simple_v1
./.venv/Scripts/python.exe -B scripts/check_candidate_model.py backend/data/simple_v2
./.venv/Scripts/python.exe -B scripts/check_candidate_model.py backend/data/simple_v3
./.venv/Scripts/python.exe -B scripts/analyze_model_errors.py simple_v1 simple_v2 simple_v3
./.venv/Scripts/python.exe -B scripts/manage_model.py check simple_v2
```

Regression v1/v3 และ `check simple_v2` ต้องคืน exit code ไม่ใช่ 0 เพราะไม่ผ่านเกณฑ์ ไม่ใช่สคริปต์เสียหาย การวิเคราะห์บันทึก `error_analysis.json` ซึ่งมีผลทุก gate

ถ้าเครื่องเพื่อนไม่มี candidate.pkl/dataset.csv จะขึ้นว่ารายงานไม่พร้อมตรวจ ไฟล์ใหญ่ถูก ignore จาก Git ต้องโอนไฟล์ทดลองที่เชื่อถือได้ต่างหาก ไม่อนุมัติจาก JSON เก่าเพียงอย่างเดียว

## ข้อมูลที่ควรเก็บเพิ่ม

เก็บ benign query/search/video/filter/encoded URL จากหลาย registered domains และ phishing path จากหลายแหล่ง พร้อมกันอีกแหล่งใหม่ไว้เป็น external benchmark ก่อนเริ่มทดลอง ไม่ใช้ allowlist หรือความนิยมของโดเมนแทน benign label

ไฟล์รับเข้ารอบใหม่เป็น CSV ใน `backend/data/reviewed/` (ignore จาก Git) ต้องมีคอลัมน์:

| คอลัมน์ | ความหมาย |
| --- | --- |
| url | URL ต้นฉบับที่ได้รับอนุญาตให้ใช้ ไม่มี credentials/token ส่วนตัว |
| label | 0 = legitimate, 1 = phishing |
| source | แหล่งข้อมูลที่ตรวจสอบได้ |
| observed_at | เวลาที่สังเกต URL แบบ ISO 8601 พร้อม timezone ไม่ใช่เอาวันดาวน์โหลดมาแทน |
| label_evidence | หลักฐานตรวจ label และใบอนุญาต/สิทธิ์ใช้ข้อมูล |
| reviewed_by | รหัสผู้ตรวจ ไม่จำเป็นต้องเป็นชื่อจริง |

สคริปต์ตรวจความครบถ้วน ไม่ได้พิสูจน์ label แทนผู้ตรวจ ห้ามเปิด URL ที่สงสัยจากเครื่องใช้งานหลักเพื่อหาหลักฐาน

Feedback export ไม่ใช่ CSV นี้ เพราะประวัติตัด query/credentials แล้ว ทุกแถวจึงมี `training_eligible=false` ต้องเก็บต้นฉบับและหลักฐานใหม่โดยเคารพความเป็นส่วนตัว ห้ามเติม query สมมติหรือย้าย label ไปใช้กับทั้งโดเมน

## ฝึก candidate เมื่อมีข้อมูลใหม่พร้อม

เตรียมแหล่งข้อมูลสำหรับ development และ external ที่ไม่เคยใช้ ตัวอย่างนี้สมมติว่ามี `new_collection.csv` จริง พร้อม source ชื่อ `external_collection_2026_10` (ยังไม่ได้สร้างไฟล์ข้อมูลนี้ไว้ให้):

```bash
./.venv/Scripts/python.exe -B backend/train_simple_model.py --uci-limit 235795 --mendeley --balance-shapes --additional-data backend/data/reviewed/new_collection.csv --external-source reviewed_external_collection_2026_10 --output backend/data/simple_next
./.venv/Scripts/python.exe -B scripts/check_candidate_model.py backend/data/simple_next
./.venv/Scripts/python.exe -B scripts/analyze_model_errors.py simple_next
./.venv/Scripts/python.exe -B scripts/manage_model.py check simple_next
```

`reviewed_` เป็น prefix ที่เติมให้ source จาก CSV ตรวจทาน ทุกโดเมนของ external source ถูกกันออกจาก Train/Calibration/Validation และวัด metric เฉพาะแถว external แยกจาก mixed Holdout

Pipeline ใหม่ตัด benign seeds ภายใน/ข้อมูลเติม query/subdomain เดิม เก็บ provenance ของ source ที่ซ้ำกัน และถือทุกโดเมนจากรอบเก่าว่าเคยเห็นแล้ว ไม่รีไซเคิล Holdout เก่าเป็น test ใหม่ แยก Train/Calibration/Validation/Holdout ตาม registered domain เลือกสูตรและ threshold บน Validation เท่านั้น

จะหยุดหากชุดใหม่ไม่มีทั้งสอง class ให้แบ่ง หรือ external source เคยใช้แล้ว Output directory สร้างแบบ exclusive ป้องกันสอง process เขียนทับกัน หากรอบล้มเหลวให้ตรวจ error แล้วเลือกชื่อใหม่ ยังไม่มี temporal split ที่พิสูจน์ด้วยวันเก็บจริง การเก็บ observed_at เป็นเพียงพื้นฐานสำหรับงานนั้น

## Gate ก่อน Promote

- แบ่งโดเมนไม่ซ้ำ มีทั้งสอง class และไม่มี Holdout ที่เคยใช้รอบก่อน
- ไม่มีข้อมูลสังเคราะห์หรือ benign labels ภายในที่ยังไม่ยืนยัน
- known-benign regression ผ่าน แต่ไม่อ้างเป็น accuracy benchmark
- ทั้ง mixed Holdout และ external source ผ่านขอบบน FPR 95%: warning ≤1%, blocking ≤0.1%
- Recall ของ warning และ blocking ไม่ต่ำกว่า production บนชุดเดียวกัน
- checksum ของ artifact, production, โค้ด และรายการทดลองยังตรงกัน

Wilson bound สมมติว่าแถวเป็นอิสระ แต่แถวในโดเมนเดียวกันอาจสัมพันธ์กัน จำนวน benign น้อยอาจไม่พอพิสูจน์ FPR แม้ FP=0 เกณฑ์นี้ไม่รับประกันความปลอดภัยของ URL ใหม่ทั้งหมด

## Promote / Rollback

```bash
./.venv/Scripts/python.exe -B scripts/manage_model.py promote simple_next
./.venv/Scripts/python.exe -B scripts/manage_model.py list
```

ไม่มี `--force` ถ้าผ่านจะสำรองไฟล์เดิมใน `backend/data/model_registry/` ด้วยชื่อ SHA-256 บันทึก JSON event และสลับไฟล์แบบ atomic จากนั้นรีสตาร์ต Backend แล้วตรวจ `/health` และ smoke tests

Rollback ใช้ SHA-256 เต็ม 64 ตัวจาก `list`:

```bash
./.venv/Scripts/python.exe -B scripts/manage_model.py rollback <SHA256-จาก-list>
```

Rollback เป็นการกู้ snapshot ไม่ใช่การยืนยันว่ารุ่นนั้นผ่านเกณฑ์ล่าสุด มีการตรวจ checksum และสำรองรุ่นก่อน rollback ด้วย หาก process ปิดกลางทาง ให้ดู event `prepared` และ checksum จริงก่อนตัดสินใจ ห้ามลบ operation.lock ขณะคำสั่งจัดการโมเดลยังรันอยู่

Trainer เดิม `backend/train_model.py` ต้องระบุ `--output-dir` ใหม่แล้ว สร้าง research-only candidate ไม่ทับ production และรายงานเดิมใช้กับ gate ใหม่ไม่ได้โดยอัตโนมัติ

## ทดสอบ

```bash
./.venv/Scripts/python.exe -B scripts/test_model_lab.py
./.venv/Scripts/python.exe -B scripts/test_simple_policy.py
./.venv/Scripts/python.exe -B scripts/test_risk_pipeline.py
node scripts/test_web_app_ui.js
cd web-app
npm run build
```

Unit/API tests ใช้ SQLite ชั่วคราว และทดสอบ backup/rollback ด้วยไฟล์ชั่วคราว ไม่แก้บัญชีหรือโมเดลจริง `scripts/test_model_lab_ui.cjs` ใช้ Playwright + Edge กับ API จำลอง ภาพอยู่ใน `tmp/model-lab-ui/` กำหนด `PLAYWRIGHT_MODULE` เป็น path ของ Playwright ที่ติดตั้งแล้วได้

การตรวจ UI รอบก่อนใช้ API จำลอง ส่วนวันที่ 17 กันยายน 2026 เปิด MySQL ในเครื่องและรัน `scripts/test_workspace_flow.py` กับ `phish_radar_local` ผ่านจริง ครอบคลุม Login/Admin/Model Lab/Feedback review/export, owner isolation, history, session/device revocation และล้างเฉพาะบัญชีทดสอบของรอบนั้น ไม่อ้างว่า API integration test เป็นการคลิกทุกหน้าใน browser จริง

```bash
./.venv/Scripts/python.exe -B scripts/test_research_collection.py
./.venv/Scripts/python.exe -B scripts/test_workspace_flow.py
```
