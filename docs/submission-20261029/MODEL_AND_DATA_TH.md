# โมเดล สูตรคะแนน ข้อมูล และผลการประเมิน Phish Radar

เอกสารประกอบการส่งอาจารย์ อัปเดตการตรวจไฟล์วันที่ **29 ตุลาคม 2569 (2026-10-29, Asia/Bangkok)**

Phish Radar รุ่นที่อธิบายในเอกสารนี้ใช้ **Random Forest จากคุณลักษณะของ URL จำนวน 174 ตัว แล้วปรับความน่าจะเป็นก่อนแปลงเป็นคะแนน 0–100** การตัดสินใจใช้เกณฑ์ Allow ต่ำกว่า 60, Warning ตั้งแต่ 60 แต่ต่ำกว่า 80 และ Block ตั้งแต่ 80 ขึ้นไป โมเดลยังมีสถานะทดลอง ผลที่บันทึกไว้แสดงทั้งความสามารถตรวจพบ phishing และการแจ้งเตือนเว็บปกติผิด จึงต้องอ่าน Recall คู่กับ False Positive Rate เสมอ

ตัวเลขผลประเมินในเอกสารนี้ถอดจากหลักฐาน JSON ของการทดลองเดิม **ไม่ได้รันประเมินโมเดลใหม่ในวันที่จัดทำรายงาน** การตรวจไฟล์และ hash ไม่ยืนยันว่า API, ฐานข้อมูล, Ollama หรือ Chrome Extension ที่เปิดอยู่ทำงานจริง

## 1. ขอบเขตรุ่นและหลักฐาน

เลือกอธิบาย source ของ **โครงการหลักในเครื่อง** ซึ่งตรงกับ source snapshot วันที่ 20 ตุลาคม 2026 และหลักฐานโมเดลที่บันทึกไว้วันที่ 17 ตุลาคม 2026 branch สำหรับส่งงานนำ source ชุดนี้มาเผยแพร่ให้อ่านที่ root โดยคัดข้อมูลลับ โมเดลไบนารี และข้อมูลดิบออก ไม่ใช้โมเดลของ Git checkout รุ่นเก่าที่เคยอยู่ซ้อนกันเป็นตัวแทนผลของรุ่นนี้

| รายการ | ค่า / ขอบเขต |
|---|---|
| Model version | `url-risk-rf-reference-root-repair-support2-20261008` |
| SHA256 ของโมเดลที่ผลประเมินอ้างถึง | `bc4e024e32aaf0ad695ea4a4dff552ece09d606c4963a49e8bf6aa8a447575bb` |
| Feature schema | `url-v10-reference-root-context` |
| จำนวน features | 174 ตัว |
| วิธีรวมคะแนนที่ artifact ระบุ | `fusion_method=ml_only`, `rule_weight=0`, `ml_weight=1` |
| เวลาที่ artifact บันทึก | `trained_at=2026-10-08T15:04:41.272134+00:00` |
| Deployment mode | `experimental_demo` |
| สถานะพร้อม production | `production_ready=false`, `promotion_ready=false`, `statistical_gate_passed=false` |

เวลาของ artifact เป็น metadata ของไฟล์โมเดล ไม่ใช่วันสังเกต URL ทั้งหมด ไม่ได้แปลว่าทุกข้อมูลเป็น phishing ที่เกิดในปี 2026 และไม่ได้แปลว่ามีการฝึก forest ใหม่ทุกต้นในเวลานั้น

หลักฐานหลัก:

- [active-model.json](../paper/evidence/active-model.json): model identity, parameters, feature names, calibrator และผลตรวจ boundary เดิม
- [source-manifest.json](../paper/evidence/source-manifest.json): hash เชื่อม source, โมเดล และผลทดลองต้นฉบับ
- [evaluation.json](../paper/evidence/evaluation.json): ผล candidate ที่ใช้ในตารางรายงานและสถานะการประเมิน
- [selection.json](../paper/evidence/selection.json): validation ที่ใช้เลือก `support2`
- [design.json](../paper/evidence/design.json): วิธีทดลอง สมมติฐาน การปรับใบ และข้อจำกัด
- [dataset-provenance.json](../paper/evidence/dataset-provenance.json): แหล่งข้อมูล จำนวน บทบาท split และ hash ของข้อมูล
- [PROJECT_FACTS_TH.md](../paper/PROJECT_FACTS_TH.md), [DATASET_SOURCES_TH.md](../paper/DATASET_SOURCES_TH.md): คำอธิบายและข้อจำกัดของหลักฐานเดิม

## 2. ลำดับการคำนวณ

```text
URL ที่ผู้ใช้ส่ง
   ↓
เลือก schema จาก model bundle และสกัด features 174 ตัวตามลำดับที่โมเดลใช้
   ↓
Random Forest: predict_proba → เลือก probability ของ class 1 (phishing)
   ↓
LogisticRegression calibrator: ปรับ raw RF probability
   ↓
คะแนนทศนิยม = calibrated probability × 100
   ↓
ตัดสิน Allow / Warn / Block ด้วยคะแนนทศนิยม
   ↓
ปัดคะแนนเพื่อแสดงผล พร้อมคืน decision และ metadata
```

source ที่กำหนดพฤติกรรมคือ [backend/app.py](../../backend/app.py) ฟังก์ชัน `predict`, `model_policy`, `risk_decision` และ [backend/feature_extractor.py](../../backend/feature_extractor.py) ฟังก์ชัน `feature_names`, `extract_features`, `feature_vector`

backend เลือก probability ด้วยตำแหน่งของ class `1` ใน `model.classes_` จึงไม่ควรอธิบายว่าผล probability ตัวที่สองเป็น phishing โดยไม่ตรวจ class ของโมเดล สำหรับ artifact นี้หลักฐานระบุ label `0=benign`, `1=phishing`

### 2.1 Random Forest และการปรับใบ

| Parameter ที่ estimator เก็บไว้ | ค่า |
|---|---|
| Estimator | `sklearn.ensemble.RandomForestClassifier` |
| จำนวนต้นไม้จริง | 96 ต้น |
| `n_estimators` | 96 |
| `max_depth` | 20 |
| `min_samples_leaf` | 10 |
| `max_features` | `sqrt` |
| `class_weight` | `balanced_subsample` |
| `criterion` | `gini` |
| `bootstrap` | `true` |
| `random_state` | `20261005` |

รุ่นนี้เป็น **การปรับใบของ forest เดิมแบบเฉพาะบริบท** ไม่ใช่การฝึก Random Forest ใหม่ทั้งหมดจาก 925,602 แถว พารามิเตอร์ในตารางเป็นค่าที่ estimator เก็บไว้ การแก้โครงสร้างหลังการฝึกทำให้พารามิเตอร์เหล่านี้เพียงอย่างเดียวอธิบาย forest สุดท้ายได้ไม่ครบ

[design.json](../paper/evidence/design.json) ระบุวิธี `One-feature supervised leaf refinement on reference root context, guarded by phishing observations` ทดลองค่า support 1, 2 และ 4 แล้วใช้ validation เลือก `support2` โดยมีข้อกำหนดไม่เพิ่ม FP/FN ในชุดและกลุ่มแหล่งข้อมูลที่ระบุ พร้อมตรวจ probes ที่เลือกไว้ จำนวนตัวอย่างบางบริบทมีน้อย จึงใช้ยืนยันการแก้กรณีที่กำหนดได้เท่านั้น

อ่านกลไกจาก [forest_leaf_refinement.py](../../backend/forest_leaf_refinement.py), [forest_feature_adapter.py](../../backend/forest_feature_adapter.py) และ [train_reference_root_repair.py](../../scripts/train_reference_root_repair.py) การมี script ใน repository เป็นหลักฐานวิธีทำ ไม่ได้หมายความว่ารายงานนี้ได้สั่งรันฝึกหรือปรับโมเดลใหม่

### 2.2 สูตร calibration และคะแนน

ให้ `p_raw` เป็นความน่าจะเป็น class phishing ที่ Random Forest ให้มา และ `sigmoid(z)=1/(1+exp(-z))`

```text
z = 7.325676952040592 × p_raw − 3.4861145043219683
p_cal = sigmoid(z)
Score = 100 × p_cal
```

coefficient และ intercept มาจาก `probability_calibrator` ใน [active-model.json](../paper/evidence/active-model.json) ตัว calibrator เป็น `LogisticRegression` ที่รับค่าขาเข้าเพียงหนึ่งตัว คือ raw RF probability

**รุ่น support2 ใช้ Platt mapping เดิมต่อหลังปรับใบ ไม่ได้ fit calibrator ใหม่** แม้ lineage ของข้อมูลจะมี split ชื่อ calibration ก็ตาม การปรับค่า probability เป็นการแปลงคะแนนด้วย mapping ที่เรียนรู้ไว้ ไม่ได้ทำให้คะแนนเป็นโอกาส phishing จริงที่รับประกันได้สำหรับแต่ละ URL

ตัวอย่างต่อไปนี้เป็น **การแทนค่าทางคณิตศาสตร์เพื่ออธิบายสูตร** โดยสมมติค่า `p_raw` ไม่ใช่การทำนาย URL ที่ทดสอบสด:

| `p_raw` สมมติ | ค่า `z` | `p_cal` | คะแนนทศนิยม | คะแนนปัดแสดง | Decision |
|---:|---:|---:|---:|---:|---|
| 0.20 | -2.020979 | 0.117018 | 11.701779 | 12 | allow |
| 0.50 | 0.176724 | 0.544066 | 54.406636 | 54 | allow |
| 0.70 | 1.641859 | 0.837788 | 83.778778 | 84 | block |

ตัวอย่าง `p_raw=0.70` จึงได้ `z=1.641859` และ `p_cal≈0.837788` ก่อนคูณ 100 เป็นประมาณ 83.78 คะแนน การนำ raw RF probability ไปคูณ 100 โดยตรงจะได้ 70 ซึ่งเป็นคนละค่ากับคะแนนของสูตรที่ใช้อยู่

### 2.3 เกณฑ์ตัดสินและการปัดเศษ

| คะแนนทศนิยมก่อนปัด | Decision | ความหมายเชิงการทำงาน |
|---|---|---|
| `<60` | `allow` | ต่ำกว่าเกณฑ์แจ้งเตือนของโครงการ |
| `>=60` และ `<80` | `warn` | แจ้งเตือนตามนโยบายของโครงการ |
| `>=80` | `block` | ส่งผลให้ client ใช้พฤติกรรมบล็อก/หน้าเตือนตามความสามารถและ settings |

หลักฐาน boundary เดิมตรวจ `59→allow`, `60→warn`, `79→warn`, `80→block` การตัดสินใช้คะแนนทศนิยมก่อนปัด เช่น 59.6 อาจแสดง 60 แต่ยังเป็น `allow` และ 79.6 อาจแสดง 80 แต่ยังเป็น `warn` client จึงต้องใช้ `decision` ที่ backend คืนมา ไม่ตีความใหม่จากจำนวนเต็มบนหน้าจอ

เกณฑ์ 60/80 เป็น operating policy ของโครงการ ไม่ใช่ค่ามาตรฐานจากงานวิจัยทุกชิ้น การเปลี่ยน threshold เปลี่ยน trade-off ระหว่างการจับ phishing และการเตือนเว็บปกติผิด จึงไม่ควรเรียกการเปลี่ยน threshold เพียงอย่างเดียวว่าเป็นการเพิ่มความแม่นยำของโมเดล

### 2.4 บทบาทของ Rule, Fuzzy และ LLM

ในโหมด `ml_only` คะแนนสุดท้ายใช้ calibrated Random Forest โดยตรง Rule อาจให้หลักฐานประกอบและแสดงใน `layer_results` ส่วน Fuzzy, learned fusion และ consensus guardrail ที่ยังมีอยู่ใน source รองรับบริบทอื่น ไม่ถูกใช้เปลี่ยนคะแนนสุดท้ายในโหมดนี้

`POST /explain` และ `/chat` เป็นเส้นทางคำอธิบาย/สนทนาแยกจากการให้คะแนน LLM มีหน้าที่อธิบายผลและให้คำแนะนำ ไม่เปลี่ยน `risk_score`, `decision`, thresholds หรือสถานะพร้อมใช้งานของโมเดล การมี source สำหรับ LLM ไม่ยืนยันว่า provider/model พร้อมให้บริการจริง

หากโหลดโมเดลไม่ได้ backend มีเส้นทาง fallback ที่ source ระบุ `model_status=model_unavailable_fuzzy_evidence`, `risk_source=local_fuzzy_evidence`, `formula_applied=false` ผลนั้นต้องติดป้ายว่าเป็นหลักฐาน fallback ห้ามนำมารายงานเป็น RF prediction รุ่นนี้ ส่วน Privacy Mode และการกรองโฆษณาเป็นพฤติกรรม client คนละส่วนกับคะแนน RF

## 3. คุณลักษณะขาเข้า 174 ตัว

ตรวจลำดับและชื่อได้จาก `feature_names` ใน [active-model.json](../paper/evidence/active-model.json) และค่าคงที่ใน [feature_extractor.py](../../backend/feature_extractor.py)

| กลุ่ม | จำนวน | สิ่งที่บอกโมเดล |
|---|---:|---|
| URL structural features ที่คงจาก schema v5 | 32 | โครงสร้าง host/path, รูปแบบอักขระ, สัญญาณ URL ซ้อน, พารามิเตอร์ และชนิดไฟล์ |
| Registered-domain และ subdomain context ที่เพิ่ม | 9 | ความยาว/entropy ของโดเมนจดทะเบียน และรูปแบบ subdomain |
| Hashed domain n-grams | 128 | รูปแบบชุดอักขระ 2, 3, 4 ตัวจากชื่อโดเมนหลัก |
| สัญญาณคำและชื่อพารามิเตอร์เพิ่มเติม | 3 | credential, redirect และคำต้องสงสัยแบบ token |
| Publisher reference context | 2 | exact reference origin และบริบททางเข้ารากเว็บไซต์ |
| **รวม** | **174** | **32 + 9 + 128 + 3 + 2** |

### 3.1 รายชื่อกลุ่ม 32 ตัว

```text
url_length, hostname_length, path_length, num_dots,
num_hyphens, num_digits, num_slashes, subdomain_count,
has_https, has_ip_host, has_at_symbol, has_encoded_url,
has_nested_url, is_shortener, risky_tld, suspicious_word_count,
hostname_entropy, path_depth, max_hostname_label_length, tld_length,
num_underscores, percent_encoding_count, has_punycode, has_backslash,
has_non_ascii, redirect_parameter_count, credential_parameter_count,
has_suspicious_file, has_archive_file, uses_free_hosting_or_ddns,
hostname_digit_ratio, domain_vowel_ratio
```

ชื่อบางตัวสืบทอดมาจาก schema ก่อนหน้า ความหมายจริงต้องอ่านการสกัดตาม schema v10 ที่เรียกต่อผ่าน v8/v7/v6/v5 เช่น v5 สร้าง structural URL โดยตัด query/fragment ก่อนสกัดบางค่า และยังเก็บสัญญาณเสี่ยงจาก query แยกต่างหาก

### 3.2 รายชื่อกลุ่มบริบทโดเมน 9 ตัว

```text
registered_domain_length, registered_domain_entropy,
registered_label_length, structural_path_url_length,
subdomain_suspicious_word_count, subdomain_has_punycode,
subdomain_digit_ratio, subdomain_max_label_length, subdomain_label_count
```

การแยก registered domain ช่วยแยกบริบทชื่อโดเมนหลักจาก subdomain เช่น ชื่อผู้ให้บริการที่ปรากฏใน subdomain ของโดเมนอื่นไม่เท่ากับเป็นโดเมนของผู้ให้บริการนั้น source ทำ canonicalization และแปลงชื่อโดเมนแบบ IDNA ตามเส้นทางสกัดที่ระบุ

### 3.3 Hashed domain n-grams 128 ตัว

ชื่อ features คือ `domain_ngram_000` ถึง `domain_ngram_127` รวม 128 ช่อง source นำ registered-domain label เติมขอบเขต `^` และ `$` แล้วสร้างชุดอักขระ 2/3/4 ตัว ใช้ `blake2s` แปลงเป็น bucket modulo 128 และกำหนดค่าแบบ binary ว่าพบชุดอักขระใน bucket นั้นหรือไม่

วิธีนี้ใช้กับทุกโดเมนตามขั้นตอนเดียวกัน ไม่ใช่ตารางคะแนนพิเศษรายแบรนด์ การ hash อาจทำให้ชุดอักขระหลายแบบชน bucket เดียวกัน จึงไม่ควรอธิบายว่า feature แต่ละช่องแทนคำหนึ่งคำแบบตายตัว

### 3.4 Features เพิ่มเติม 3 ตัว

```text
enhanced_credential_parameter_count
enhanced_redirect_parameter_count
token_suspicious_word_count
```

features เหล่านี้เพิ่มการตรวจชื่อพารามิเตอร์และคำตาม token ขณะยังรักษา prefix 32 columns ให้เข้ากับ forest รุ่นเดิม ตัวแปร `query_length` และ `num_params` **ไม่อยู่ใน 174 features ขาเข้า** เพราะมีความต่างเชิงที่มาระหว่าง query ฝั่ง benign ของผู้เผยแพร่ แต่ไม่ได้หมายความว่า query ถูกละทิ้งทั้งหมด สัญญาณเช่น nested URL และชื่อ credential/redirect parameter ยังมีผลต่อ features

### 3.5 Publisher reference 2 ตัว

| Feature | ความหมาย |
|---|---|
| `publisher_reference_origin_match` | exact HTTPS origin ปรากฏในทะเบียน reference จาก metadata ของแหล่งอ้างอิงที่โครงการเก็บไว้ |
| `publisher_reference_root_context` | origin match ร่วมกับ path ทางเข้า root ความยาว/ความลึกที่กำหนด และไม่มี hazard/query บางประเภทตามโค้ด |

reference origin เป็น feature ให้โมเดลเรียนรู้ ไม่ใช่ blanket allowlist ไม่รับรองทุกหน้าในโดเมนนั้น และไม่ใช่การเปิดอ่านเนื้อหาเว็บจริง เช่น URL ที่ path เป็น `/th` ไม่ใช่ root context เพียงเพราะ host เดียวกับหน้า root

ดู [reference_origin_features.py](../../backend/reference_origin_features.py) และฟังก์ชัน `reference_root_sensitive_query`, `reference_root_context` ใน [feature_extractor.py](../../backend/feature_extractor.py) ต้นฉบับ registry มีข้อมูล URL ชั่วคราว จึงไม่เผยแพร่ในชุดนี้ ใช้ hash `118e8734190109e64bd45a839dd78d75be94503ce33e75a9a8524195b05bd9b4` ในหลักฐานเพื่อระบุตัวตนของสำเนาอ้างอิง การไม่แนบ registry ทำให้ clone เพียงอย่างเดียวยังสร้าง feature สองตัวนี้ให้เหมือนต้นฉบับครบทุกกรณีไม่ได้

## 4. แหล่งข้อมูลและจำนวนในชุดพัฒนา

ข้อมูลพัฒนาที่อ้างถึงคือ `backend/data/simple_quality_rf_20261008/dataset.csv` SHA256 `c02bb2adf07c71ddc391403f3d190fb9ab289d058f62ba3177318612428b0df0` หลักฐาน provenance บันทึกว่าตรวจจำนวนจาก CSV แบบ streaming ในวันที่ 20 ตุลาคม 2026 ตัวไฟล์ข้อมูลดิบไม่ได้แนบใน branch ส่งงานนี้

### 4.1 จำนวนต่อแหล่งและ split

จำนวนในตารางคือ **แถวที่เหลือในไฟล์รวมหลังการเตรียมข้อมูล** ไม่ใช่จำนวนดิบทั้งหมดของผู้เผยแพร่ และไม่ใช่จำนวน URL บนอินเทอร์เน็ตที่ระบบเคยตรวจ

| แหล่งใน combined development | Train | Calibration | Validation | รวม | Benign | Phishing |
|---|---:|---:|---:|---:|---:|---:|
| PhreshPhish v1.0.1 | 330,944 | 39,204 | 123,698 | 493,846 | 272,540 | 221,306 |
| URL-Phish v1 | 77,692 | 10,880 | 22,258 | 110,830 | 98,341 | 12,489 |
| Web page phishing detection v3 | 8,276 | 981 | 2,003 | 11,260 | 5,587 | 5,673 |
| DeepURLBench | 56,781 | 20,072 | 21,526 | 98,379 | 49,523 | 48,856 |
| UCI PhiUSIIL | 160,190 | 22,917 | 27,077 | 210,184 | 117,938 | 92,246 |
| Official references รอบเดิม | 95 | 86 | 29 | 210 | 210 | 0 |
| Official references รอบ quality | 767 | 36 | 90 | 893 | 893 | 0 |
| **รวม** | **634,745** | **94,176** | **196,681** | **925,602** | **545,032** | **380,570** |

อ่านค่าต้นฉบับได้ที่ `combined_dataset` และ `development_sources[].counts_in_combined_dataset` ใน [dataset-provenance.json](../paper/evidence/dataset-provenance.json)

### 4.2 บทบาทของ split ในการทดลอง support2

| ส่วนข้อมูล | จำนวนแถว | บทบาทที่บันทึก |
|---|---:|---|
| Train | 634,745 | เรียนรู้บริเวณ/ใบที่ต้องปรับจาก forest เดิมและ labels |
| Calibration | 94,176 | แบ่งตาม parity ของ SHA256 registered domain เป็น positive guard และส่วนสงวนสำหรับ calibration |
| Positive guard ภายใน calibration | 44,286 | ใช้ guard การปรับเฉพาะบริบทตาม pipeline |
| ส่วนสงวน probability calibration | 49,890 | ชื่อ partition ของข้อมูล; รุ่น support2 ไม่ได้ fit mapping ใหม่จากส่วนนี้ |
| Validation | 196,681 | เลือก support และตรวจเงื่อนไขไม่ถดถอย; เป็น tuning/selection data |

provenance บันทึก `registered_domain_disjoint=true` สำหรับ partition ที่ตรวจไว้ ชุด validation มี benign 98,622 และ phishing 98,059 จาก confusion counts ที่บันทึกใน selection อย่างไรก็ดี การกันโดเมนในข้อมูลที่มีให้ตรวจไม่ได้สร้างหลักฐานย้อนกลับว่าข้อมูลทั้งหมดไม่เคยอยู่ในการฝึก baseline ดั้งเดิม เพราะไฟล์ฝึกเดิมบางส่วนไม่อยู่แล้ว

### 4.3 รุ่น แหล่ง และข้อสังเกตด้าน lineage

| แหล่ง | รุ่น/ตัวระบุที่บันทึก | วิธีนำมาใช้และข้อจำกัด |
|---|---|---|
| PhreshPhish | v1.0.1; revision `eabec4b7a66324b79cc8a0ad856d1731dc26fe1a` | ใช้ URL/labels ตามส่วนที่กู้คืนและคัดไว้; publisher ตัด query ฝั่ง benign จึงมีข้อจำกัดเชิงที่มา |
| URL-Phish | Mendeley version 1; DOI `10.17632/65z9twcx3r.1` | ใช้ URL/labels แล้วโครงการสกัด features เอง; จำนวนในคำอธิบายหน้าเผยแพร่กับไฟล์ที่โครงงานบันทึกต่างกัน ให้ยึดไฟล์/hash ที่เลือกจริง |
| Web page phishing detection | Mendeley version 3; DOI `10.17632/c2gw7fy2j4.3` | ใช้ URL และ status label; provenance ระบุว่ายังไม่พบ dedicated publisher provenance manifest ของแหล่งนี้ |
| UCI PhiUSIIL | UCI dataset 967; เผยแพร่ปี 2024 | เพิ่มในข้อมูลพัฒนา และกัน confirmation 15,463 URL แยก; ไม่ทราบ observation date ของแต่ละ URL |
| DeepURLBench | revision `bf17c3fef854ff0ea40bcf93e373fc2c6dc30081` | เลือก benign/phishing; ไม่เหมารวม malware เป็น phishing; `first_seen` เป็นเวลาสังเกตของ publisher ไม่ใช่เวลาที่โครงการดาวน์โหลด |
| Official references สองรอบ | manifest ของโครงงานวันที่ 8 ตุลาคม 2026 | ตัวอย่าง benign เฉพาะกรณีสำหรับพัฒนา; ไม่เป็นตัวแทน benign ทั้งอินเทอร์เน็ต และไม่ได้เป็น independent test |
| PhishTank | verified-online snapshot ที่บันทึกในโครงงาน | ไม่มี source-column โดยตรงใน 925,602 แถว; ใช้แยกเป็น phishing-only regression 151 URL |

label ของโครงงานคือ `0=benign`, `1=phishing` แต่ PhiUSIIL ต้นทางระบุ `1=legitimate`, `0=phishing` จึงต้องแปลง label ให้ทิศทางตรงกันก่อนใช้ ไม่สามารถนำค่าต้นทางมาผสมโดยไม่แปลง

URL-Phish อาจอ้าง PhishTank เป็นแหล่งรวบรวมต้นทางตามคำอธิบายผู้เผยแพร่ ประเด็นนี้เป็น provenance ทางอ้อม ต่างจากการมี PhishTank เป็น `source` โดยตรงใน combined development ของโครงงาน เช่นเดียวกับ OpenPhish/Tranco ใน manifest pipeline รุ่นเก่าขนาด 20,000 URL ซึ่งไม่ใช้แทน lineage ของ artifact รุ่นนี้

provenance บันทึกใบอนุญาตหลายแหล่งเป็น CC BY 4.0 และ DeepURLBench เป็น CC BY-NC 4.0 ข้อมูลนี้เป็น metadata ที่บันทึกไว้ ไม่ใช่การตรวจสิทธิ์เผยแพร่ raw dataset ใหม่ในวันที่ 29 ตุลาคม 2026 ดูลิงก์ publisher และบรรณานุกรมใน [DATASET_SOURCES_TH.md](../paper/DATASET_SOURCES_TH.md)

## 5. ชุด confirmation และ regression

ห้ามบวกจำนวนทุกชุดในตารางเป็น test set เดียว เพราะมีบทบาท ประวัติการใช้ และข้อจำกัดต่างกัน ชุดที่เคยเปิดดูหรือใช้พัฒนาแล้วต้องเรียก regression ให้ตรงประวัติ ไม่เรียก untouched test ซ้ำ

| Key ใน evaluation | แหล่ง / บทบาท | URL | Domains | Benign | Phishing |
|---|---|---:|---:|---:|---:|
| `fresh_uci_confirmation` | PhiUSIIL confirmation ที่กันแยก | 15,463 | 15,463 | 11,322 | 4,141 |
| `fresh_deepurlbench_confirmation_round2` | DeepURLBench confirmation รอบสอง | 10,000 | 10,000 | 5,000 | 5,000 |
| `historical_regression` | PhreshPhish publisher test split ที่เคยตรวจแล้ว | 70,085 | 46,703 | 27,684 | 42,401 |
| `prior_deepurlbench_regression` | DeepURLBench holdout เดิม | 20,000 | 17,420 | 10,000 | 10,000 |
| `prior_confirmation_regression` | confirmation รอบแรกที่นำกลับเป็น regression | 10,000 | 10,000 | 5,000 | 5,000 |
| `recent_phishing_regression` | PhishTank phishing-only diagnostic ที่นำกลับเป็น regression | 151 | 151 | 0 | 151 |

ชื่อ `fresh` ใน key หมายถึงสถานะชุดในกระบวนการทดลองที่บันทึกไว้ ไม่ได้ยืนยันว่าเก็บจากอนาคตหลัง train และไม่ใช่ชื่อ test ใหม่ของวันที่จัดทำรายงาน หลักฐานระบุ `forward_temporal_test=false`, `prior_exposure_audit_complete=false`

เส้นทางต้นฉบับ/hash ของแต่ละชุดและ selector เช่น `split=holdout` อยู่ใน `confirmation_and_regression_sets` ของ [dataset-provenance.json](../paper/evidence/dataset-provenance.json) หลักฐานบันทึก hash ตรง evaluation แต่ `counts_recounted_now=false` สำหรับชุดเหล่านี้ จึงแยกจากการตรวจนับ combined development โดยตรง

## 6. ผลการประเมินที่บันทึกไว้

### 6.1 นิยามตัวชี้วัด

ให้ phishing เป็น positive และ benign เป็น negative:

```text
TP = phishing ที่ระบบเตือน/บล็อกตาม threshold
FN = phishing ที่ต่ำกว่า threshold
FP = benign ที่ระบบเตือน/บล็อกตาม threshold
TN = benign ที่ต่ำกว่า threshold

Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
FPR       = FP / (FP + TN)
F1        = 2 × Precision × Recall / (Precision + Recall)
```

ในแถว Warning 60 ให้นับทั้งคะแนน 60–<80 และ >=80 เป็น positive เพราะทั้งสองระดับถึงเกณฑ์ warning แล้ว ส่วนแถว Block 80 นับเฉพาะคะแนน >=80 จึงห้ามบวก TP ของแถว Warning และ Block เข้าด้วยกัน

### 6.2 Precision, Recall, F1 และ FPR

ค่าร้อยละในตารางคำนวณจาก `evaluations.<key>.candidate.warning/blocking` ใน [evaluation.json](../paper/evidence/evaluation.json) คูณ 100 และปัดสองตำแหน่ง FPR upper 95% คือขอบบนที่ไฟล์ผลบันทึกไว้ ไม่ใช่ FPR ที่คำนวณจากชุดใหม่

| ชุด | เกณฑ์ | Precision % | Recall % | F1 % | FPR % | FPR upper 95% (ร้อยละ) |
|---|---|---:|---:|---:|---:|---:|
| UCI confirmation | 60 | 74.30 | 34.48 | 47.11 | 4.36 | 4.69 |
| UCI confirmation | 80 | 85.59 | 26.68 | 40.68 | 1.64 | 1.85 |
| DeepURLBench confirmation รอบสอง | 60 | 76.80 | 58.72 | 66.55 | 17.74 | 18.65 |
| DeepURLBench confirmation รอบสอง | 80 | 80.85 | 43.82 | 56.84 | 10.38 | 11.11 |
| Historical regression | 60 | 94.85 | 67.29 | 78.73 | 5.60 | 5.83 |
| Historical regression | 80 | 97.38 | 51.06 | 66.99 | 2.11 | 2.25 |
| Prior DeepURLBench regression | 60 | 77.26 | 60.07 | 67.59 | 17.68 | 18.32 |
| Prior DeepURLBench regression | 80 | 80.98 | 42.92 | 56.10 | 10.08 | 10.59 |
| Prior confirmation regression | 60 | 78.29 | 58.84 | 67.18 | 16.32 | 17.20 |
| Prior confirmation regression | 80 | 82.13 | 43.48 | 56.86 | 9.46 | 10.16 |
| PhishTank phishing-only regression | 60 | — | 72.85 | — | ประเมินไม่ได้ | — |
| PhishTank phishing-only regression | 80 | — | 61.59 | — | ประเมินไม่ได้ | — |

สำหรับ phishing-only 151 URL ไม่รายงาน Precision/F1 ในตารางนี้ตามหลักฐานสรุป และไม่สามารถประเมิน FPR, ROC-AUC หรือการจำแนก benign จากข้อมูลที่ไม่มี benign ตัวอย่างได้ ค่า FP=0 ใน confusion counts จึงไม่ได้แปลว่า FPR เป็นศูนย์

### 6.3 Confusion counts เพื่อให้ตรวจย้อนกลับได้

| ชุด | เกณฑ์ | TN | FP | FN | TP |
|---|---:|---:|---:|---:|---:|
| UCI confirmation | 60 | 10,828 | 494 | 2,713 | 1,428 |
| UCI confirmation | 80 | 11,136 | 186 | 3,036 | 1,105 |
| DeepURLBench confirmation รอบสอง | 60 | 4,113 | 887 | 2,064 | 2,936 |
| DeepURLBench confirmation รอบสอง | 80 | 4,481 | 519 | 2,809 | 2,191 |
| Historical regression | 60 | 26,135 | 1,549 | 13,868 | 28,533 |
| Historical regression | 80 | 27,101 | 583 | 20,751 | 21,650 |
| Prior DeepURLBench regression | 60 | 8,232 | 1,768 | 3,993 | 6,007 |
| Prior DeepURLBench regression | 80 | 8,992 | 1,008 | 5,708 | 4,292 |
| Prior confirmation regression | 60 | 4,184 | 816 | 2,058 | 2,942 |
| Prior confirmation regression | 80 | 4,527 | 473 | 2,826 | 2,174 |
| PhishTank phishing-only regression | 60 | 0 | 0 | 41 | 110 |
| PhishTank phishing-only regression | 80 | 0 | 0 | 58 | 93 |

ตัวอย่างอ่านผล UCI ที่ Warning 60: benign ทั้งหมด `10,828+494=11,322` รายการ ถูกเตือนผิด 494 รายการ จึงได้ FPR `494/11,322≈4.36%` ขณะที่ phishing ทั้งหมด `2,713+1,428=4,141` รายการ ตรวจถึงเกณฑ์ได้ 1,428 รายการ จึงได้ Recall `1,428/4,141≈34.48%` การนำเสนอเฉพาะ FPR ต่ำโดยไม่ระบุ Recall จะปกปิด phishing ที่พลาดไปจำนวนมาก

### 6.4 คุณภาพ probability และ ranking

ค่าต่อไปนี้ถอดจาก `candidate.probability` และ `candidate.calibration` ไม่ได้ผูกกับ threshold เดียว และยังขึ้นกับชุดตัวอย่าง/สัดส่วน class ที่ใช้วัด

| ชุด | ROC-AUC | PR-AUC ตามชื่อ field | Brier score | Log loss | ECE 10 bins |
|---|---:|---:|---:|---:|---:|
| UCI confirmation | 0.689091 | 0.598435 | 0.160876 | 0.513616 | 0.053760 |
| DeepURLBench confirmation รอบสอง | 0.778650 | 0.764233 | 0.204211 | 0.612341 | 0.104981 |
| Historical regression | 0.901096 | 0.934301 | 0.150263 | 0.470155 | 0.141909 |
| Prior DeepURLBench regression | 0.789302 | 0.771879 | 0.198211 | 0.596267 | 0.097874 |
| Prior confirmation regression | 0.782300 | 0.772640 | 0.201428 | 0.606270 | 0.102876 |

ROC-AUC/PR-AUC สรุปการจัดอันดับ ส่วน Brier/log loss/ECE ช่วยดูคุณภาพ probability ค่า Brier, log loss และ ECE ต่ำกว่ามักดีกว่าเมื่อเปรียบเทียบบนชุดและวิธีเดียวกัน ไม่ควรเทียบข้ามชุดที่มี distribution ต่างกันแล้วสรุปว่าโมเดลดีขึ้น การใช้ชื่อ `PR-AUC` ในที่นี้รักษาชื่อ field ของหลักฐานไว้ ไม่เหมารวมกับ AP ของเดโม Colab โดยไม่ตรวจวิธีคำนวณ

### 6.5 สิ่งที่ผลสนับสนุนและไม่สนับสนุน

ผลที่บันทึกสนับสนุนว่า targeted repair ผ่านเงื่อนไขจำนวน FP/FN ที่กำหนดบนชุดที่ระบุ และแก้ probes เฉพาะบางกรณีได้ เช่น probe ของ `https://www.ku.ac.th/th` บันทึกคะแนนแสดง 9 และ `allow` ใน `evaluation.probes` ผล probe นี้เป็นผลเก่าที่เลือกดูเพื่อพัฒนา ไม่ใช่การตรวจหน้าเว็บสดหรือหลักฐานว่าเว็บไซต์ทั้งโดเมนปลอดภัย

ใน validation ที่ใช้เลือกแบบจำลอง warning FP ลดจาก 5,199 เป็น 5,197 และ Recall คงประมาณ 0.674594 ขณะที่ block FP/FN เดิม ผลนี้มาจาก selection data ไม่ใช่ independent test การผ่าน `measured_gate_passed=true` จึงหมายถึงผ่านขอบเขต targeted correction ที่ประกาศไว้ ไม่ได้ทำให้ `statistical_gate_passed` หรือ `production_ready` เปลี่ยนเป็น true

ผลรวม FN ไม่เพิ่มไม่ได้รับประกันว่า phishing ทุก URL ที่รุ่นเดิมตรวจพบจะยังถูกตรวจพบเหมือนเดิมทุกตัว และผล confirmation ต่างชุดแสดงชัดว่าทั้ง Recall/FPR เปลี่ยนตามแหล่งข้อมูล จึงไม่อ้างค่าตัวเดียวเป็น accuracy ทั่วอินเทอร์เน็ต

## 7. เดโม RF เทียบ MLP เป็นคนละการทดลอง

มีเดโมที่จัดเตรียมวันที่ 23 ตุลาคม 2026 สำหรับเปรียบเทียบ Random Forest กับ Deep Learning แบบ MLP บนข้อมูลย่อยจาก development pool เดิม เดโม **ไม่ได้เปลี่ยนโมเดลใน Extension/Backend** และไม่ใช้ผลของมันแทนตาราง 174-feature RF ข้างต้น

| ประเด็น | โมเดลระบบในรายงานนี้ | เดโม RF–MLP |
|---|---|---|
| Schema | `url-v10-reference-root-context` | `url-v8-domain-enriched` |
| จำนวน features | 174 | 172; ไม่มี publisher reference 2 ตัว |
| ที่มาของโมเดล | forest เดิมผ่าน targeted leaf repair | ฝึก RF และ MLP ใหม่ใน notebook |
| Calibration | ใช้ Platt mapping เดิม | ไม่ได้ calibrate |
| เกณฑ์ | Warning 60 / Block 80 | ตารางหลัก probability 0.5 |
| ข้อมูลเดโม | ใช้หลักฐานหลายชุดตามตารางก่อนหน้า | 30,000 แถว: train 21,000 / validation 4,500 / test 4,500 |
| ขอบเขตผล | recorded model evaluation | Local CPU single-seed demo; ยังไม่ใช่ผล Colab GPU |

ผลเดโม Local CPU ที่บันทึกด้วย seed `20261023` บน test เดียวกัน 4,500 แถวและ threshold 0.5:

| โมเดล | Precision % | Recall % | FPR % | F1 | AP |
|---|---:|---:|---:|---:|---:|
| Random Forest เดโม | 89.21 | 66.30 | 4.20 | 0.7607 | 0.8914 |
| MLP เดโม | 81.63 | 74.71 | 8.80 | 0.7801 | 0.8734 |

MLP เดโมตรวจ phishing ได้มากขึ้นพร้อมเตือน benign ผิดมากขึ้น ส่วน RF เดโมได้ AP และ Precision สูงกว่าในรอบนี้ จึงไม่มีข้อสรุปว่า Deep Learning เหนือกว่าทุกด้าน ข้อมูลแบ่งแบบ domain-disjoint ภายในเดโม แต่ยังเป็นข้อมูลพัฒนาเดิมและ seed เดียว ไม่ใช่ fresh temporal test

แหล่งผลในเครื่องที่ตรวจคือ `output/colab-rf-dl-20261023/RESULTS_LOCAL_CPU_TH.md` และ `local_cpu_results/metrics_threshold_0_5.csv` ชุดส่งงาน GitHub นี้ไม่ได้แนบ notebook, features dataset หรือผลเดโมต้นฉบับครบชุด ตัวเลขในหัวข้อนี้จึงเป็นสรุปประกอบแยกต่างหาก หากต้องทำซ้ำเดโม ต้องรับแพ็กเดโมและ manifest ของมันเพิ่มเติม และแยกผลรันบน Colab ออกจากผล Local CPU

## 8. ข้อจำกัดและงานประเมินที่ยังต้องทำ

1. **ยังเป็นโมเดลทดลอง:** `production_ready=false`, `promotion_ready=false`, `statistical_gate_passed=false` ห้ามอ้างว่าโมเดลผ่านเกณฑ์ใช้งานจริงแล้ว
2. **Recall ยังต่ำในบางชุด:** UCI confirmation ที่ Warning 60 ตรวจพบประมาณ 34.48% ของ phishing ในชุดนั้น ผลนี้ต้องแสดงพร้อม FPR 4.36% ไม่เลือกเฉพาะค่าที่ดูดี
3. **การแจ้งผิดขึ้นกับแหล่งข้อมูล:** DeepURLBench confirmation รอบสองมี FPR 17.74% ที่ Warning 60 จึงยังมีข้อจำกัดต่อการใช้งานที่ต้องคุม false positive ต่ำ
4. **ไม่มี forward-temporal evaluation ครบสอง class:** หลักฐานไม่รองรับการรับประกันผลกับ phishing ในอนาคตหรือ benign ปัจจุบันทั่วอินเทอร์เน็ต
5. **ตรวจ baseline exposure ย้อนหลังไม่ครบ:** ไฟล์ฝึก baseline ดั้งเดิมบางส่วนหาย จึงไม่สามารถยืนยัน absence of training exposure ทุก URL ได้ แม้ชุด confirmation จะตัด domains ที่ตรวจพบในประวัติที่มีออกแล้ว
6. **labels และ observation dates ไม่สมบูรณ์:** ไม่ได้ manual review ทุก label; วันเผยแพร่/ดาวน์โหลด/สังเกต URL/สร้าง artifact เป็นคนละความหมาย
7. **targeted references ไม่แทน benign ทั้งโลก:** ตัวอย่างจากผู้เผยแพร่ที่เลือกไว้และการซ่อมกรณี root context ไม่เป็นหลักฐานลด FPR โดยทั่วไป
8. **calibration ไม่ได้ fit ใหม่หลัง repair:** ต้องประเมิน reliability ภายใต้ distribution ที่จะใช้งานจริงเพิ่มเติม ไม่ตีความ calibrated score เป็นโอกาส phishing ของแต่ละ URL แบบรับประกัน
9. **เป็น URL-derived model:** การมี HTTPS หรือคะแนนต่ำไม่ได้ยืนยันเนื้อหา/พฤติกรรมหน้าเว็บปลอดภัย การกรอง DOM และคำอธิบาย LLM เป็นคนละขอบเขต
10. **แพ็กเผยแพร่ยังทำซ้ำการทดลองไม่ครบ:** ไม่มี model binary, raw datasets และ registry ต้นฉบับที่มี URL ชั่วคราว จึงอ่านวิธีทำงานและตรวจหลักฐานที่บันทึกได้ แต่ไม่สามารถ clone แล้วสร้างผลทั้งหมดใหม่จากไฟล์เผยแพร่เพียงอย่างเดียว
11. **การตรวจ source ไม่ใช่ live verification:** ยังต้องแยก HTTP tests, Web/Extension ที่โหลดจริง, Privacy Mode/network behavior, ฐานข้อมูล, LLM และ public reachability ตามผลตรวจเฉพาะส่วน ห้ามใช้เอกสารนี้แทนผลเหล่านั้น

การประเมินเพื่อพิจารณาใช้งานต่อควรล็อก artifact/schema/policy ให้ตรงกัน จัดชุด benign/phishing ใหม่ที่กัน registered domain และเวลา รายงาน Recall พร้อม FPR/ช่วงความเชื่อมั่น ประเมิน calibration และตรวจพฤติกรรม client ด้วย decision ก่อนปัดเศษ โดยไม่ใช้ชุดที่เคยเลือกโมเดลแล้วเป็น independent test ซ้ำ
