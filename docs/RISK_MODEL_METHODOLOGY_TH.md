# วิธีวิจัยและการคำนวณความเสี่ยง Phish Radar AI

เอกสารนี้อธิบายระบบ Risk Model v2 ที่ใช้งานจริงในโปรเจกต์ สูตรเดิมแบบกำหนดน้ำหนัก
`RuleScore × alpha + MLScore × (1-alpha)` ถูกยกเลิก เพราะไม่มีหลักฐานเพียงพอว่า
น้ำหนักคงที่หนึ่งค่าจะเหมาะกับข้อมูลและภัยคุกคามที่เปลี่ยนตามเวลา

## 1. งานวิจัยที่ใช้เป็นหลักในการออกแบบ

1. **Beyond Blacklists: Learning to Detect Malicious Web Sites from Suspicious URLs**
   (Ma et al., ACM KDD 2009) รองรับแนวคิดการเรียนฟังก์ชันความเสี่ยงจาก lexical และ
   host-based features ของ URL แทนการตั้งน้ำหนักด้วยความเห็นของผู้พัฒนา
   DOI: <https://doi.org/10.1145/1557019.1557153>
2. **CANTINA+: A Feature-rich Machine Learning Framework for Detecting Phishing
   Web Sites** (Xiang et al., ACM TISSEC 2011) รองรับการใช้หลักฐานหลายชนิดและ
   สถาปัตยกรรมตรวจจับหลายชั้น ไม่พึ่งสัญญาณเดียว
   DOI: <https://doi.org/10.1145/2019599.2019606>
3. **URLTran: Improving Phishing URL Detection Using Transformers**
   (Microsoft Research, MILCOM 2021) ใช้เป็นหลักการประเมิน threshold ภายใต้
   False Positive Rate ที่เหมาะกับงานจริง ไม่ได้คัดลอกสถาปัตยกรรม Transformer
   มาใช้ในโปรเจกต์นี้
   <https://www.microsoft.com/en-us/research/?p=805918>
4. **Discovering Phishing Dropboxes Using Email Metadata**
   (University of Cambridge) สนับสนุนแนวคิดว่าบริบทและ metadata จากหลายแหล่ง
   ช่วยตรวจจับโครงสร้าง phishing ที่มองไม่เห็นจาก URL เพียงอย่างเดียว
   <https://www.cl.cam.ac.uk/~rnc1/dropbox.pdf>

งาน Cambridge ไม่ได้เสนอสูตร RiskScore ของโปรเจกต์และไม่ได้ใช้เป็นหลักฐานว่าโมเดล
URL ของเรามีประสิทธิภาพเท่ากับงานนั้น แต่ใช้สนับสนุนการออกแบบ evidence layer
เพิ่มเติมเท่านั้น

## 2. สูตร RiskScore

โมเดลหลักเป็น L1-regularized Logistic Regression:

```text
p(phishing | x) = sigmoid(w · x + b)
RiskScore = round(100 × p(phishing | x))
```

เวกเตอร์ `x` สร้างจาก URL features ใน `backend/feature_extractor.py` เช่น ความยาว
URL/hostname/path, จำนวน subdomain, entropy, IP host, HTTPS, Punycode, encoded URL,
nested URL, risky TLD, redirect/credential parameters, file type และสัดส่วนตัวเลข
ใน hostname ค่า `w` และ `b` เรียนจากข้อมูลจริง ไม่มี alpha ที่ผู้พัฒนากำหนดเอง

L1 regularization ทำให้ค่าสัมประสิทธิ์ที่ไม่ช่วยจำแนกถูกผลักเข้าใกล้ศูนย์ จึงตรวจสอบ
feature ที่มีผลต่อโมเดลได้จากส่วน `coefficients` ในรายงานการประเมิน

## 3. หลักฐานหลายชั้น

ระบบวางลำดับตามแนวคิด feature-rich/layered detection:

1. Normalize URL และตรวจ trusted app/allowlist
2. URL Risk Model คำนวณ probability และ RiskScore
3. Rule evidence ใน browser ตรวจ URL, link, form, credential และ page context
4. External reputation/DNS/WHOIS เป็นจุดต่อขยาย ปัจจุบันรายงาน `not_configured`
5. Policy แปลง RiskScore เป็น `allow`, `warn` หรือ `block`
6. Qwen/Ollama อธิบายผลตามหลักฐาน แต่ไม่มีสิทธิ์เปลี่ยนคะแนนหรือ decision

RuleScore ยังคงแสดงและบันทึกเพื่อ audit และใช้เป็น local fallback ใน Privacy Mode
หรือเมื่อ backend ไม่พร้อม แต่ไม่ถูกบวกหรือถ่วงน้ำหนักเข้า RiskScore

## 4. ข้อมูลและการป้องกัน data leakage

- ชุดฝึกปัจจุบัน 10,000 URL: legitimate 5,000 และ phishing 5,000
- แหล่งข้อมูลและ SHA-256 บันทึกใน `backend/data/training_urls.manifest.json`
- แบ่งกลุ่มด้วย hostname เพื่อไม่ให้ URL จาก host เดียวกันกระจายข้าม train/test
- กันหนึ่ง grouped holdout ไว้ก่อนเลือก hyperparameter และ threshold
- ส่วน development ใช้ StratifiedGroupKFold เพื่อสร้าง out-of-fold probability
- เลือกค่า `C` จาก log loss, Brier score และ ROC-AUC บน development เท่านั้น
- ฝึก deployment model บนข้อมูลทั้งหมดด้วยค่า `C` ที่เลือกโดยไม่ดู holdout

ข้อจำกัดสำคัญคือข้อมูลปัจจุบันไม่มี first-seen timestamp ที่เชื่อถือได้ จึงยังทำ
time-split evaluation ไม่ได้ และ Tranco เป็นเพียง legitimate proxy ไม่ใช่คำรับรองว่า
ทุกโดเมนปลอดภัยตลอดเวลา

## 5. การเลือก warn/block threshold

ระบบมี threshold สองระดับ:

- `warning_threshold`: ตั้งเป้า FPR ไม่เกิน 1%
- `blocking_threshold`: ตั้งเป้า FPR ไม่เกิน 0.1%

บน development out-of-fold predictions ระบบคำนวณ Precision, Recall, F1, ROC-AUC,
PR-AUC และ FPR ทุก threshold จากนั้นบังคับให้ **ขอบบน one-sided Wilson 95% ของ FPR**
ไม่เกินเพดาน ก่อนเลือกค่าที่ให้ Recall สูงที่สุด ตามด้วย F1 และ Precision วิธีนี้
เข้มกว่าการดู observed FPR เพียงจุดเดียว

ผลจากการฝึกล่าสุด:

| ชุดประเมิน | Policy | Threshold | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|---:|
| Development OOF | warn | 0.37 | 0.9920 | 0.9650 | 0.9783 | 0.0072 |
| Development OOF | block | 1.00 | 1.0000 | 0.1828 | 0.3091 | 0.0000 |
| Independent grouped holdout | warn | 0.37 | 0.9913 | 0.9712 | 0.9811 | 0.0112 |
| Independent grouped holdout | block | 1.00 | 1.0000 | 0.0506 | 0.0963 | 0.0000 |

Independent holdout มี ROC-AUC 0.9933, PR-AUC 0.9958, Brier score 0.0172 และ
log loss 0.0736 ค่า warn FPR บน holdout เท่ากับ 1.12% ซึ่งสูงกว่าเป้าหมาย 1%
เล็กน้อย จึงต้องรายงานตามจริงและยังไม่ควรอ้างว่าเป็น production guarantee

blocking threshold ที่ 1.00 สะท้อนว่าชุด benign ปัจจุบันยังเล็กเกินกว่าจะยืนยัน
FPR 0.1% พร้อม Recall สูงได้อย่างมั่นคง ในระยะนี้ระบบจึงเตือน URL ส่วนใหญ่ที่เกิน
warn threshold และ block เฉพาะความน่าจะเป็นที่อิ่มตัวถึง 1.0 เท่านั้น

## 6. API และการตรวจสอบย้อนหลัง

`POST /predict` คืนค่า:

- `risk_probability`, `risk_score`, `decision`
- `warning_threshold`, `blocking_threshold`
- `model_version`, `policy_version`, `feature_schema_version`
- `layer_results` และ `model_status`

ฟิลด์ `ml_score`, `final_score` และ `decision_threshold` ยังถูกส่งเป็น alias ชั่วคราว
สำหรับ client รุ่นเดิม ส่วน `alpha` เป็น `null` และไม่ถูกใช้คำนวณ

Migration `004_create_search_history.sql` สร้างฟิลด์ดังกล่าวใน
`SearchHistory` บน MySQL/MariaDB ทำให้ผลย้อนหลังระบุได้ว่าเกิดจากโมเดลและ
policy เวอร์ชันใด

## 7. สิ่งที่ต้องทำก่อนอ้างผลระดับใช้งานจริง

1. เพิ่ม benign sample จำนวนมากพอสำหรับวัด FPR ต่ำกว่า 0.1% อย่างมีนัยสำคัญ
2. เก็บ first-seen timestamp และทำ time-split evaluation
3. ทำ source-held-out test เช่นกัน PhishTank/OpenPhish ออกจาก training ทีละแหล่ง
4. เพิ่ม reputation/DNS/WHOIS และ page-context dataset โดยมี provenance
5. ติดตาม calibration drift, FPR และ campaign drift หลัง deploy
6. ทบทวน threshold เป็นราย model version โดยห้ามปรับจาก production test set

ผลฉบับ machine-readable อยู่ที่ `backend/data/risk_model_evaluation.json`
และ model bundle อยู่ที่ `backend/model.pkl`
