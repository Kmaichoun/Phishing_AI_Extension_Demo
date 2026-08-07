# วิธีวิจัยและการคำนวณความเสี่ยง Phish Radar AI

เอกสารนี้อธิบายระบบที่ใช้งานจริงในระดับ **ประยุกต์แนวคิด** เท่านั้น ได้แก่
`FuzzyScore + Random Forest + learned fusion` โดยยังไม่เพิ่ม Transformer,
convolution/pooling หรือ differentiable fuzzy calibration

## 1. ขอบเขตที่นำมาประยุกต์

ระบบใช้แนวคิดการตรวจจับหลายชั้นจากงาน URL phishing detection ที่เป็นที่ยอมรับ
เช่น Beyond Blacklists, CANTINA+ และ URLTran แต่สถาปัตยกรรมและพารามิเตอร์ใน
โปรเจกต์นี้ผ่านการฝึกและประเมินจากชุดข้อมูลของโครงงานเอง จึงไม่กล่าวอ้างว่าสูตร
หรือผลลัพธ์ถูกคัดลอกมาจากงานวิจัยใดโดยตรง

งานที่ใช้เป็นกรอบแนวคิดประกอบการออกแบบ:

- Ma et al., **Beyond Blacklists: Learning to Detect Malicious Web Sites from
  Suspicious URLs**, ACM KDD 2009 — lexical/host-based URL learning
  <https://doi.org/10.1145/1557019.1557153>
- Xiang et al., **CANTINA+: A Feature-rich Machine Learning Framework for
  Detecting Phishing Web Sites**, ACM TISSEC 2011 — การตรวจจับแบบหลาย feature/layer
  <https://doi.org/10.1145/2019599.2019606>
- **URLTran: Improving Phishing URL Detection Using Transformers**, Microsoft
  Research/MILCOM 2021 — ใช้เป็นแนวคิดเรื่องการประเมิน threshold และ FPR ไม่ได้
  นำ Transformer มาใช้ในระดับนี้ <https://www.microsoft.com/en-us/research/?p=805918>
- งาน University of Cambridge ด้าน phishing dropboxes — ใช้สนับสนุนแนวคิดการใช้
  หลักฐานหลายแหล่งและบริบท <https://www.cl.cam.ac.uk/~rnc1/dropbox.pdf>

Fuzzy membership และ learned-fusion pipeline ในโปรเจกต์นี้เป็นการออกแบบและ
ทดลองของโครงงาน จึงต้องอ้างผลจาก evaluation report ของโปรเจกต์ควบคู่กัน

ชั้นคำนวณมี 4 ขั้นตอน:

1. Rule engine คำนวณ `RuleScore` จาก URL และบริบทใน browser
2. Fuzzy membership แปลง RuleScore เป็น `FuzzyScore`
3. Random Forest คำนวณ `RandomForestScore` จาก URL features
4. Logistic meta-model เรียนการรวมสองคะแนนเป็น learned-fusion probability
5. Consensus guardrail ยกระดับผลเมื่อ FuzzyScore และ RandomForestScore สูงตรงกัน

## 2. สูตรที่ใช้งาน

```text
FuzzyScore = Defuzzify(RuleScore)
RandomForestRaw = mean(tree phishing votes)
RandomForestScore = 100 × PlattCalibration(RandomForestRaw)
FusionScore = LearnedFusion(FuzzyScore, RandomForestScore)
FinalScore = 100 × ConsensusGuardrail(FusionScore, FuzzyScore, RandomForestScore)
```

`LearnedFusion` เป็น Logistic Regression ที่รับอินพุต 2 ค่า คือ FuzzyScore และ
RandomForestScore ซึ่งถูกปรับให้อยู่ช่วง 0–1 ก่อนฝึก ค่าสัมประสิทธิ์ถูกเรียนจาก
out-of-fold predictions ไม่ใช่น้ำหนักคงที่ 40/60

โมเดลปัจจุบันมีค่าสัมประสิทธิ์ที่บันทึกไว้ในรายงานการทดลอง:

```text
logit(p) = -3.129300 + 0.076040(FuzzyScore/100)
                       + 6.501955(RandomForestScore/100)
FusionScore = sigmoid(logit(p))
```

ค่านี้เป็นผลจาก dataset รุ่นปัจจุบัน เมื่อสร้าง dataset หรือฝึกใหม่ต้องใช้ค่าจาก
model bundle และรายงานรุ่นใหม่ ห้ามนำตัวเลขนี้ไป hard-code ใน client

## 3. FuzzyScore

`backend/fuzzy_scoring.py` กำหนด membership 3 กลุ่ม:

- safe: เป็นสมาชิกเต็มเมื่อ RuleScore ≤ 20 และลดลงจนเป็นศูนย์ที่ 45
- suspicious: รูปสามเหลี่ยมที่ 20, 50 และ 80
- dangerous: เริ่มเพิ่มที่ 55 และเป็นสมาชิกเต็มตั้งแต่ 85

ระบบ defuzzify ด้วย centroid 0, 50 และ 100 พร้อมเก็บ membership ทั้งสามค่าใน
`layer_results.fuzzy_rule_evidence.audit` เพื่อให้ตรวจสอบย้อนหลังได้

## 4. Random Forest และข้อมูล

Random Forest ใช้ URL features จาก `backend/feature_extractor.py` เช่น ความยาว URL,
จำนวน subdomain, IP host, encoded URL, nested URL, suspicious terms, redirect และ
credential parameters โมเดลรุ่นปัจจุบันใช้ 240 trees, `max_depth=18`,
`min_samples_leaf=2`, `max_features=sqrt` และ balanced subsampling

ชุดข้อมูลปัจจุบันมี 20,000 URL แบ่ง phishing และ legitimate อย่างละ 10,000 รายการ
จาก PhishTank, OpenPhish, Tranco, Common Crawl URL Index และ seed data ตัวเก็บ
Common Crawl รวบรวม legitimate deep links 485 รายการจาก curated trusted hosts
โดยอ่านเฉพาะ URL metadata และไม่ได้เปิดเว็บปลายทาง รายละเอียดแหล่งและ checksum อยู่ใน
`backend/data/risk_model_evaluation.json`

เพื่อแก้ dataset shortcut ที่เคยทำให้ URL ปลอดภัยแบบ `/watch?v=...` ถูกทายว่า
phishing ระบบเพิ่ม curated legitimate deep links และสร้าง benign URL shapes แบบ
deterministic โดยไม่เปิด URL จริง ปัจจุบันสัดส่วน legitimate/phishing คือ:

- deep link: 65.00% / 64.80%
- query string: 18.00% / 15.96%
- non-www subdomain: 65.00% / 68.46%

## 5. การป้องกันข้อมูลรั่วระหว่างการทดลอง

- แบ่งกลุ่มด้วย hostname ไม่ให้ host เดียวกันอยู่ทั้ง train และ test
- กัน grouped holdout ไว้ก่อนฝึกโมเดลและเลือก threshold
- ใช้ StratifiedGroupKFold สร้าง out-of-fold Random Forest probabilities
- ใช้ group-disjoint cross-fitted Platt scaling เพื่อ calibrate probability โดยไม่ให้
  label ของแถวเดียวกันเข้าไปอยู่ใน calibrator ที่ทายแถวนั้น
- ฝึก learned fusion จาก out-of-fold scores เท่านั้น
- ฝึก final base model และ final fusion หลังประเมินขั้นตอนออกแบบเสร็จแล้ว

## 6. Threshold และผลประเมินรุ่นปัจจุบัน

ระบบเลือก threshold จาก operational FinalScore หลัง consensus guardrail บน
development set ภายใต้ FPR:

- warn = 96/100, development FPR 0.008037, Recall 0.476781, Precision 0.981560
- block = 99/100, development FPR 0, Recall 0.022599, Precision 1.0

Independent grouped holdout ของ operational score ให้ ROC-AUC 0.956597,
PR-AUC 0.968405, Brier score 0.088089 และ log loss 0.304379 ผลเหล่านี้เป็น
ผลการทดลองของ dataset รุ่นปัจจุบัน ไม่ใช่คำรับรองประสิทธิภาพบนทราฟฟิกจริงทั้งหมด

ใน holdout ฝั่ง legitimate มี warning FPR รวม 0.2092%, deep-link warning FPR
0.0825% และ query warning FPR 0% รายละเอียดแยก root, deep link, query และ subdomain อยู่ในหัวข้อ
`independent_holdout_legitimate_segments` ของ evaluation report

Consensus guardrail รุ่นปัจจุบันกำหนดว่า:

- warning consensus: FuzzyScore ≥ 50 และ RandomForestScore ≥ 90
- blocking consensus: FuzzyScore ≥ 85 และ RandomForestScore ≥ 95

กฎนี้ไม่พึ่ง allowlist และต้องมีหลักฐานสูงจากสองชั้นพร้อมกัน การเลือก threshold และ
การคำนวณ FPR รวมผลของ guardrail ไว้แล้ว

## 7. API และการตรวจสอบย้อนหลัง

`POST /predict` คืนค่าหลักดังนี้:

- `rule_score`, `fuzzy_score`, `random_forest_raw_score`, `random_forest_score`
- `probability_calibrated`
- `risk_probability`, `risk_score`, `final_score`
- `fusion_method`, `fusion_applied`, `risk_formula`
- `decision`, `warning_threshold`, `blocking_threshold`
- `model_version`, `policy_version`, `feature_schema_version`, `layer_results`

ฟิลด์ `ml_score` ยังคงอยู่เป็น alias ของ RandomForestScore เพื่อให้ฐานข้อมูลและ
client รุ่นเก่าทำงานต่อได้ ส่วน `alpha`, `rule_weight` และ `ml_weight` เป็น `null`
เพราะระบบใหม่ไม่ได้ใช้น้ำหนักคงที่

เมื่อ Privacy Mode เปิดอยู่ Extension/Web จะใช้ RuleScore ในเครื่องและไม่เรียก
Backend, Random Forest, learned fusion หรือ LLM ส่วน Qwen/Ollama มีหน้าที่อธิบายผล
เท่านั้นและไม่มีสิทธิ์แก้คะแนนหรือ decision

## 8. ไฟล์ที่เกี่ยวข้อง

- `backend/fuzzy_scoring.py` — fuzzy membership และ defuzzification
- `backend/feature_extractor.py` — URL features
- `backend/train_model.py` — grouped CV, Random Forest, Platt calibration, learned fusion, threshold
- `backend/risk_policy.py` — consensus guardrail ที่ใช้ร่วมกันระหว่าง training/runtime
- `backend/collect_legitimate_deep_links.py` — เก็บ URL metadata จาก Common Crawl แบบ sequential
- `backend/app.py` — runtime inference และ API response
- `backend/model.pkl` — model bundle
- `backend/data/risk_model_evaluation.json` — configuration และผลประเมินเต็ม
- `scripts/test_risk_pipeline.py` — contract test ของ pipeline

## 9. ข้อจำกัด

- dataset ยังไม่มี first-seen timestamp ที่น่าเชื่อถือ จึงยังไม่มี time-split test
- Tranco เป็น legitimate proxy ไม่ใช่หลักฐานว่าเว็บไซต์ปลอดภัยทุกกรณี
- benign URL shapes ที่สร้างขึ้นช่วยลด source-format shortcut แต่ไม่แทนที่ชุดทดสอบ
  legitimate deep links จากทราฟฟิกจริงและแยกแหล่งข้อมูล
- blocking threshold ที่เข้มมากทำให้ recall บน holdout ลดลง
- ต้องประเมินกับข้อมูลใหม่และข้อมูลจริงก่อนอ้างผลในระดับ production
