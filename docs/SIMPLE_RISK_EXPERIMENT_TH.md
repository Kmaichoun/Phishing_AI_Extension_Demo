# การตรวจสูตรและทดลองโมเดล URL Risk แบบง่าย

## ข้อสรุป

สูตร Production ปัจจุบันยังไม่ถูกแทนที่ เพราะสูตรเดิมซับซ้อนเกินกว่าจะอธิบายเป็นคะแนนความเสี่ยงตรง ๆ แต่โมเดลสูตรง่ายที่ฝึกเพิ่มยังไม่ผ่านเกณฑ์ False Positive บนข้อมูลต่างแหล่ง การคงโมเดลเดิมชั่วคราวจึงปลอดภัยกว่าการเลือกโมเดลจาก Accuracy สูงเพียงค่าเดียว

สูตรที่เสนอสำหรับรุ่นถัดไปคือ:

```text
FinalScore = MLScore
```

`RuleScore` ยังคงแสดงเป็นหลักฐานประกอบ แต่ไม่รวมซ้ำใน FinalScore จนกว่าจะพิสูจน์ได้ว่ากฎให้ข้อมูลเพิ่มจาก ML อย่างเป็นอิสระ

## สูตรเดิมและตัวแปร

```text
FinalScore = 100 × ConsensusGuardrail(
  LearnedFusion(FuzzyScore, RandomForestScore),
  FuzzyScore,
  RandomForestScore
)
```

- `RuleScore` คือคะแนน 0–100 จากกฎใน `web-app/analyzer.js` เช่น IP host, punycode, URL ซ้อน, redirect/credential parameters, คำเสี่ยง และชนิดไฟล์
- `FuzzyScore` แปลง `RuleScore` เดิมด้วย membership ของ safe, suspicious และ dangerous จึงไม่ใช่ข้อมูลอิสระอีกชุด
- `RandomForestScore` หรือ `MLScore` คือความน่าจะเป็น phishing หลัง Platt calibration คูณ 100 โมเดลอ่าน 34 ตัวแปร URL-only จาก `backend/feature_extractor.py`
- `LearnedFusion` เป็น Logistic Regression ที่รวม FuzzyScore กับ RandomForestScore
- `ConsensusGuardrail` บังคับ floor เป็น 99 หรือ 100 เมื่อสองคะแนนสูงพร้อมกัน จึงทำให้คะแนนกระจุกด้านบนและอธิบายความต่างระหว่าง URL ยาก
- `WarningThreshold` และ `BlockingThreshold` เป็นจุดตัดการตัดสิน ไม่ใช่ส่วนของคะแนน ต้องเลือกบน Validation แล้วตรวจบน Holdout แยกต่างหาก

ปัญหาหลักคือ Rule/Fuzzy และ Random Forest ใช้โครงสร้าง URL เดียวกัน การรวมทั้งสองไม่ได้แปลว่าเป็นหลักฐานอิสระ และอาจนับสัญญาณเดิมซ้ำ สูตรคงที่ `0.40 × RuleScore + 0.60 × MLScore` เข้าใจง่ายกว่า แต่ตัวเลข 40/60 ไม่มีเหตุผลทางสถิติในตัวเองและต้องชนะการเปรียบเทียบจาก Validation ก่อนจึงควรใช้

## Dataset ที่เพิ่ม

1. [UCI PhiUSIIL Phishing URL Dataset](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset) — 235,795 URL, CC BY 4.0, ผู้สร้าง Arvind Prasad และ Shalini Chandra; ป้ายต้นฉบับ `1=legitimate`, `0=phishing` ถูกแปลงเป็นมาตรฐานโปรเจกต์ `0=legitimate`, `1=phishing`
2. [Mendeley Web page phishing detection v3](https://data.mendeley.com/datasets/c2gw7fy2j4/3) — 11,430 URL แบบสมดุล, CC BY 4.0, Abdelhakim Hannousse และ Salima Yahiouche; ตรวจ SHA-256 ตาม metadata ของผู้เผยแพร่
3. PhishTank และ OpenPhish จาก pipeline เดิม สำหรับตัวอย่าง phishing จริง
4. `backend/data/legitimate_deep_links.csv` และ seeds เดิม — การตรวจภายหลังพบว่าไม่สามารถยืนยันทุก label ว่า audited ได้ รวมถึง legacy rows ที่เติม query/subdomain สังเคราะห์ รอบ v1–v3 มีส่วนนี้ปะปน; pipeline ใหม่ตัด benign seeds ภายในออกและต้องใช้หลักฐานใหม่

Pipeline อ่าน URL เป็นข้อความเท่านั้น ไม่เข้าเว็บไซต์ใน Dataset และไม่ใช้ HTML/content features แม้ Dataset ต้นทางจะมีคอลัมน์ดังกล่าว

## วิธีแบ่งข้อมูล

- แบ่งตาม registered domain ด้วย Public Suffix List เพื่อลดการรั่วของโดเมนเดียวกันข้ามชุด
- แยก Train, Calibration, Validation และ Holdout
- Train ใช้ฝึก Random Forest เท่านั้น
- Calibration ใช้ปรับความน่าจะเป็นด้วย Platt scaling
- Validation ใช้เลือกระหว่าง `MLScore` กับ `0.40 Rule + 0.60 ML` และเลือก Threshold ภายใต้ Wilson upper bound ของ FPR
- Holdout ไม่ใช้ปรับโมเดลหรือ Threshold
- รอบ v3 ย้ายโดเมนจาก Mendeley ไป Holdout แต่เป็นชุดผสมและมี 26,159 โดเมนที่เคยเห็นในรอบก่อน รวมถึง 98 โดเมนจากชุดฝึก production จึงไม่ใช่ external benchmark ใหม่ที่ไม่เคยใช้

## ผลทดลอง

| รอบ | ข้อมูล | สูตรที่ Validation เลือก | Warning FPR / Recall บน Holdout | Blocking FPR / Recall | Regression เว็บปกติ | พร้อมใช้ |
| --- | ---: | --- | --- | --- | --- | --- |
| v1 | 109,921 | `MLScore` | 0.612% / 95.63% | 0.060% / 91.95% | ไม่ผ่าน | ไม่พร้อม |
| v2 | 256,297 | `MLScore` | 1.255% / 77.12% | 0.169% / 28.85% | ผ่าน | ไม่พร้อม |
| v3 exploratory source split | 256,297 | `0.40 Rule + 0.60 ML` | 23.734% / 98.31% | 15.824% / 70.52% | ไม่ผ่าน | ไม่พร้อม |
| v4 publisher + external source | 836,508 | `MLScore` | 27.160% / 48.26% | 0.130% / 16.39% | ไม่ผ่าน (Google query ยาว) | ทดลองเท่านั้น |

เป้าหมายที่ตั้งไว้คือ Warning FPR ไม่เกิน 1% และ Blocking FPR ไม่เกิน 0.1% พร้อมผ่าน URL regression ที่เป็นเว็บปกติ ผล v3 แสดง dataset shift ชัดเจน จึงห้ามอ้างผล v1 ว่าโมเดลพร้อมใช้งานทั่วไป

v4 เพิ่ม PhreshPhish publisher-train และกัน URL-Phish เป็น external source หลังตัดโดเมนที่เคยเห็น สูตร ML-only ชนะสูตร 40/60 บน Validation แต่ยังเตือนผิดสูงบน Holdout และ external source จึงเก็บไว้ดูผลใน Model Lab เท่านั้น Production ยังใช้ไฟล์เดิม

ไฟล์ผลที่ตรวจสอบได้อยู่ใน `backend/data/simple_v1` ถึง `simple_v4` โดย `evaluation.json` เก็บเมตริก/ที่มา, `regression.json` เก็บ known-benign regression, `error_analysis.json` เก็บ gate และผลแยกกลุ่ม ส่วน model/dataset ขนาดใหญ่ถูก ignore จาก Git

## ตรวจรอบเดิมและเตรียมรอบใหม่

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-training.txt
.\.venv\Scripts\python.exe -B scripts\analyze_model_errors.py simple_v1 simple_v2 simple_v3
.\.venv\Scripts\python.exe -B scripts\manage_model.py check simple_v2
```

คำสั่ง check ต้องปฏิเสธ v2 เพราะยังไม่ผ่าน Pipeline ใหม่ไม่สร้าง v1–v3 ซ้ำเหมือนเดิม เพราะตัดข้อมูลป้ายที่ยังไม่ยืนยันและป้องกันการใช้ Holdout ซ้ำ ดู [คู่มือรอบใหม่และการเปลี่ยนรุ่น](MODEL_UPGRADE_WORKFLOW_TH.md) ก่อนฝึก ต้องผ่านทั้งข้อมูล/โดเมน, FPR confidence bound, Recall, regression และ external-source gate

## งานที่ควรทำต่อ

- เพิ่ม benign deep links จากหลายโดเมนและช่วงเวลาจริง โดยมีที่มา/วันเก็บและตรวจ label
- แยก external-source และ temporal test ที่ไม่แตะระหว่างปรับโมเดล
- วิเคราะห์ false positives แยกตาม path/query/encoded URL/provider ไม่เพิ่ม allowlist เพื่อซ่อนปัญหา
- ตรวจ probability calibration และ threshold drift เป็นระยะ
- พิจารณา RuleScore เป็น explanation หรือ veto เฉพาะกฎความมั่นใจสูง แทนการผสมทุกกฎเป็นคะแนนเดียว
