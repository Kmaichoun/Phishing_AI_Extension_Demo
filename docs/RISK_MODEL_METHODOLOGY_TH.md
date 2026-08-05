# วิธีวิจัยและการคำนวณความเสี่ยง Phish Radar AI

เอกสารนี้อธิบาย Risk Model ที่ใช้งานจริงในโปรเจกต์ โดยกำหนดให้ RuleScore มี
น้ำหนัก 40% และ MLScore มีน้ำหนัก 60% จากนั้นเลือก warning/blocking threshold
บน FinalScore ด้วยข้อมูล development แบบ out-of-fold ภายใต้เพดาน False Positive Rate

## 1. งานวิจัยที่ใช้เป็นหลักในการออกแบบ

1. **Beyond Blacklists: Learning to Detect Malicious Web Sites from Suspicious URLs**
   (Ma et al., ACM KDD 2009) รองรับการเรียน MLScore จาก lexical และ host-based
   features ของ URL DOI: <https://doi.org/10.1145/1557019.1557153>
2. **CANTINA+: A Feature-rich Machine Learning Framework for Detecting Phishing
   Web Sites** (Xiang et al., ACM TISSEC 2011) รองรับสถาปัตยกรรมตรวจจับหลายชั้น
   DOI: <https://doi.org/10.1145/2019599.2019606>
3. **URLTran: Improving Phishing URL Detection Using Transformers**
   (Microsoft Research, MILCOM 2021) ใช้สนับสนุนการเลือก threshold โดยคำนึงถึง
   False Positive Rate <https://www.microsoft.com/en-us/research/?p=805918>
4. **Discovering Phishing Dropboxes Using Email Metadata**
   (University of Cambridge) สนับสนุนการใช้ข้อมูลหลายแหล่งและบริบท
   <https://www.cl.cam.ac.uk/~rnc1/dropbox.pdf>

เอกสารเหล่านี้สนับสนุนองค์ประกอบของระบบ แต่ไม่ได้ระบุน้ำหนัก 0.40/0.60 โดยตรง
น้ำหนักดังกล่าวเป็น policy คงที่ในขอบเขตการทดลองของโครงงานและต้องรายงานตามจริง

## 2. สูตรคะแนน

โมเดล ML เป็น L1-regularized Logistic Regression:

```text
p(phishing | x) = sigmoid(w · x + b)
MLScore = round(100 × p(phishing | x))
FinalScore = round(0.40 × RuleScore + 0.60 × MLScore)
```

RuleScore มาจากกฎที่ตรวจ URL, โดเมน, redirect, credential parameter และบริบทใน
browser ส่วน MLScore มาจาก probability ของโมเดลบนสเกล 0–100 ค่า 0.40/0.60
เป็นค่าคงที่ ไม่ใช่พารามิเตอร์ที่ Logistic Regression เรียนเอง

เมื่อ ML พร้อม ระบบใช้ FinalScore เพื่อตัดสิน `allow`, `warn` หรือ `block` หากเปิด
Privacy Mode หรือ backend ไม่พร้อม ระบบใช้ RuleScore เป็น local fallback และตั้ง
`formula_applied=false` เพื่อไม่กล่าวว่าได้ใช้สูตรผสมทั้งที่ไม่มี MLScore

## 3. หลักฐานหลายชั้น

1. Normalize URL และตรวจ trusted app/allowlist
2. Rule engine คำนวณ RuleScore
3. URL Risk Model คำนวณ probability และ MLScore
4. คำนวณ FinalScore ด้วยสูตร 40/60
5. Decision policy เปรียบเทียบ FinalScore กับ warning/blocking threshold
6. Qwen/Ollama อธิบายผล แต่ไม่มีสิทธิ์เปลี่ยนคะแนนหรือ decision
7. External reputation, DNS และ WHOIS เป็นจุดต่อขยายที่ยัง `not_configured`

## 4. ข้อมูลและการป้องกัน data leakage

- ชุดฝึก 10,000 URL: legitimate 5,000 และ phishing 5,000
- แหล่งข้อมูลและ SHA-256 อยู่ใน `backend/data/training_urls.manifest.json`
- แบ่งกลุ่มด้วย hostname ไม่ให้ host เดียวกันอยู่ทั้ง train และ test
- กัน grouped holdout ก่อนเลือก hyperparameter และ threshold
- ใช้ StratifiedGroupKFold สร้าง out-of-fold ML probability บน development
- เลือกค่า `C` จาก log loss, Brier score และ ROC-AUC บน development เท่านั้น
- คำนวณ out-of-fold FinalScore ด้วย RuleScore และ MLScore ก่อนเลือก threshold

ข้อจำกัดคือข้อมูลยังไม่มี first-seen timestamp ที่เชื่อถือได้ จึงยังทำ time-split
evaluation ไม่ได้ และ Tranco เป็น legitimate proxy ไม่ใช่คำรับรองความปลอดภัย

## 5. การเลือก warn/block threshold

- `warning_threshold`: ตั้งเป้า FPR ไม่เกิน 1%
- `blocking_threshold`: ตั้งเป้า FPR ไม่เกิน 0.1%

ระบบบังคับให้ขอบบน one-sided Wilson 95% ของ FPR บน development ไม่เกินเพดาน
ก่อนเลือกค่าที่ให้ Recall สูงที่สุด ตามด้วย F1 และ Precision ผลล่าสุดคือ:

| ชุดประเมิน | Policy | Threshold | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|---:|
| Development OOF | warn | 0.35 | 0.9925 | 0.9615 | 0.9768 | 0.0067 |
| Development OOF | block | 0.8006 | 1.0000 | 0.0773 | 0.1434 | 0.0000 |
| Independent grouped holdout | warn | 0.35 | 0.9913 | 0.9704 | 0.9807 | 0.0112 |
| Independent grouped holdout | block | 0.8006 | 0.9873 | 0.0607 | 0.1144 | 0.0010 |

ML probability บน independent holdout มี ROC-AUC 0.9933, PR-AUC 0.9958,
Brier score 0.0172 และ log loss 0.0736 ส่วน FinalScore มี ROC-AUC 0.9919 และ
PR-AUC 0.9930 ค่า warn FPR บน holdout 1.12% สูงกว่าเป้าหมาย 1% เล็กน้อย จึงยัง
ไม่ควรอ้างผลนี้เป็น production guarantee

## 6. API และการตรวจสอบย้อนหลัง

`POST /predict` คืนค่า:

- `rule_score`, `ml_score`, `risk_probability`
- `risk_score` และ `final_score` ซึ่งเป็นผลสูตรผสม
- `rule_weight=0.40`, `ml_weight=0.60`, `risk_formula`, `formula_applied`
- `decision`, `warning_threshold`, `blocking_threshold`
- `model_version`, `policy_version`, `feature_schema_version`, `layer_results`

`alpha` ยังคงส่งเป็น `0.40` เพื่อรองรับ schema ประวัติเดิม ตาราง `SearchHistory`
จึงเก็บ RuleScore, MLScore, FinalScore, threshold และเวอร์ชัน policy ย้อนหลังได้

## 7. สิ่งที่ต้องทำก่อนอ้างผลระดับใช้งานจริง

1. ทดลองน้ำหนักอื่นและเปรียบเทียบกับ 0.40/0.60 ด้วยข้อมูลที่แยกจากชุดเลือก policy
2. เพิ่ม benign sample สำหรับประเมิน FPR ต่ำกว่า 0.1%
3. เก็บ first-seen timestamp และทำ time-split evaluation
4. ทำ source-held-out test เช่นกัน PhishTank/OpenPhish ออกจาก training ทีละแหล่ง
5. ติดตาม calibration drift, FPR และ campaign drift หลัง deploy

ผล machine-readable อยู่ที่ `backend/data/risk_model_evaluation.json` และ model
bundle อยู่ที่ `backend/model.pkl`
