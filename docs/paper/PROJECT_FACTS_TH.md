# ตารางข้อเท็จจริงและหลักฐานสำหรับผู้เขียนบทความ

เอกสารนี้เป็นข้อมูลให้เพื่อนตรวจสอบและเลือกใช้ประกอบการเขียนเอง ไม่ใช่เนื้อหาบทความสำเร็จรูป ตรวจไฟล์ในโครงการหลักวันที่ 17 ตุลาคม 2569 (2026-10-17, Asia/Bangkok) ผลประเมินด้านล่างเป็นผลที่บันทึกไว้เดิมและผูกกับโมเดลด้วย SHA256 ไม่ใช่การประเมินชุดข้อมูลใหม่ในวันตรวจ

## 1. ขอบเขตของหลักฐาน

| รายการ | ข้อเท็จจริงที่ตรวจได้ | หลักฐาน / ข้อจำกัด |
| --- | --- | --- |
| โครงการที่ใช้ตรวจ | โครงการหลักซึ่งมี `backend/`, `web-app/`, `extension/` อยู่ข้างโฟลเดอร์ `Phishing_AI_Extension_Demo/` | ต้นทางไฟล์ทั้งหมดระบุใน [source-manifest.json](evidence/source-manifest.json) โดยใช้ path สัมพันธ์กับโครงการหลัก |
| Git repository ที่อยู่ซ้อน | `Phishing_AI_Extension_Demo/backend/model.pkl` มี SHA256 ต่างจากโมเดลโครงการหลัก | อย่านำผลในชุดเอกสารนี้ไปกล่าวว่าตรงกับ runtime ของ repository ที่อยู่ซ้อนโดยอัตโนมัติ ดู `nested_repository_model_comparison` ใน manifest |
| สิ่งที่ตรวจใหม่ | อ่าน artifact ด้วย joblib; ตรวจ hash ของ model/candidate/evaluation/selection/design/registry; เทียบ feature names; ตรวจฟังก์ชันตัดสินใจแบบแยกเดี่ยว | รายละเอียดอยู่ใน `inspection` และ `decision_boundary_check` ของ [active-model.json](evidence/active-model.json) |
| สิ่งที่ไม่ได้ตรวจใหม่ | HTTP API, backend ที่กำลังรัน, public demo, Chrome extension ที่โหลดจริง, latency, user study และการประเมินชุดข้อมูลเต็ม | ห้ามเขียนว่าใช้งานออนไลน์สำเร็จหรือทดสอบ end-to-end แล้วจากชุดหลักฐานนี้ |
| ชุดเอกสารบน GitHub | สำเนาหลักฐานและคู่มือสำหรับผู้เขียน | ไม่มี model binary และ raw datasets จึงยังไม่ใช่ชุดทำซ้ำการทดลองครบถ้วน |

## 2. โมเดลและสูตรที่อ้างได้

| ประเด็น | ค่าที่ตรวจได้จาก artifact / source | หลักฐานและวิธีใช้ |
| --- | --- | --- |
| Model version | `url-risk-rf-reference-root-repair-support2-20261008` | [active-model.json](evidence/active-model.json) → `model_version` |
| Model SHA256 | `bc4e024e32aaf0ad695ea4a4dff552ece09d606c4963a49e8bf6aa8a447575bb` | ตรงกับ `candidate_sha256` ใน [evaluation.json](evidence/evaluation.json) และ model-demo authorization ที่ตรวจในโครงการหลัก |
| Model family | `sklearn.ensemble.RandomForestClassifier` | snapshot → `estimator`; เป็น forest ที่ผ่านการปรับใบแบบเฉพาะกรณี ไม่ควรอธิบายว่าเป็น RF ฝึกใหม่ทั้งหมด |
| จำนวนต้นไม้ | 96 ต้น | ตรวจจำนวน `estimators_` จริง และ `n_estimators` ใน artifact |
| Parameters ที่บันทึก | `max_depth=20`, `min_samples_leaf=10`, `max_features=sqrt`, `class_weight=balanced_subsample`, `random_state=20261005` | เป็นพารามิเตอร์ที่ estimator เก็บไว้; การปรับใบภายหลังทำให้พารามิเตอร์เพียงอย่างเดียวไม่เพียงพออธิบายโครงสร้างสุดท้าย |
| Feature schema | `url-v10-reference-root-context` จำนวน 174 ตัว | feature names ใน artifact ตรงกับ `feature_names(schema)` ของ extractor ขณะตรวจ |
| กลุ่ม feature | 32 ตัวแปรโครงสร้างตาม v5 + 9 ตัวแปรบริบทโดเมน + 128 hashed domain n-grams + 3 ตัวแปรคำ/พารามิเตอร์เพิ่มเติม + 2 ตัวแปร publisher reference | snapshot → `feature_names`; ความหมายอ้างโค้ด `backend/feature_extractor.py` เวอร์ชันตาม manifest |
| Query | `query_length` และ `num_params` ไม่อยู่ใน 174 features ที่ป้อนโมเดล แต่ยังตรวจสัญญาณบางชนิด เช่น nested URL และชื่อพารามิเตอร์ credential/redirect | อย่าเขียนว่า query ถูกละทิ้งทั้งหมด |
| Reference origin | exact HTTPS origin ที่พบใน metadata ของผู้เผยแพร่เป็น feature ที่โมเดลเรียนรู้ | `backend/reference_origin_features.py`; ไม่ใช่การยืนยันว่าเนื้อหาบนโดเมนนั้นปลอดภัย |
| Reference root context | ใช้ reference origin ร่วมกับทางเข้ารากเว็บไซต์และการไม่พบ hazard/query บางชนิดตามโค้ด | `backend/feature_extractor.py` → `reference_root_context`; ไม่ใช่การตรวจเนื้อหาเว็บจริง |
| สูตรคะแนนปัจจุบัน | `Score = 100 × Calibrate(Random Forest)` | `fusion_method=ml_only`, `rule_weight=0`, `ml_weight=1`; path ของ `/predict` ใน `backend/app.py` ใช้ calibrated score โดยตรง |
| Calibration | LogisticRegression รับ raw RF probability หนึ่งค่า; `p_cal = sigmoid(7.325676952040592 × p_raw − 3.4861145043219683)` | snapshot → `probability_calibrator`; ใช้ mapping Platt เดิมต่อหลังการปรับใบ ไม่ได้ fit calibration ใหม่ |
| การแสดงคะแนน | source สร้างคะแนนจำนวนเต็มด้วยการปัดเศษ แต่ตัดสินใจด้วยคะแนนทศนิยมก่อนปัด | `backend/app.py` → `predict`, `risk_decision`; ไม่ควรคำนวณ decision จากคะแนนจำนวนเต็มที่แสดงเพียงอย่างเดียว |
| Rule / Fuzzy ในโหมดนี้ | Rule ใช้เป็นหลักฐานประกอบ; Fuzzy และ consensus guardrail ไม่ถูกใช้เปลี่ยนคะแนนสุดท้ายเมื่อ `fusion_method=ml_only` | `/predict` ใน source และ `layer_results` |
| LLM | มีเส้นทางขอคำอธิบายแยกจากการคำนวณคะแนน | `backend/llm_explainer.py`, `backend/app.py`; การตรวจครั้งนี้ไม่ยืนยัน provider/model ที่กำลังรันหรือคุณภาพคำอธิบายจริง |
| Dataset row count ใน artifact | `925602` | เป็น metadata ที่ artifact เก็บไว้ ไม่ได้ตรวจนับตัวอย่างฝึกทั้งหมดใหม่ และไม่ใช่จำนวนตัวอย่างที่ใช้ปรับใบครั้งนี้โดยอัตโนมัติ |
| เวลาที่ artifact ระบุ | `trained_at=2026-10-08T15:04:41.272134+00:00` | เป็นเวลาที่บันทึกกับ artifact ไม่ใช่ช่วงวันที่เกิด phishing หรือวันสังเกตทุก URL |

## 3. เกณฑ์และสถานะ

| ประเด็น | ค่าที่ตรวจได้ | ข้อจำกัดในการเขียน |
| --- | --- | --- |
| Allow | คะแนนทศนิยม `<60` | เป็นผลต่ำกว่าเกณฑ์ ไม่ใช่คำรับรองว่าเว็บไซต์ปลอดภัย |
| Warning | คะแนนทศนิยม `>=60` และ `<80` | เป็นนโยบายของโครงการ ไม่ใช่ค่าที่ได้จากงานวิจัยทุกชิ้น |
| Block | คะแนนทศนิยม `>=80` | backend คืน decision; การทำงานจริงของหน้าเตือน/ส่วนขยายต้องมีหลักฐานทดสอบอีกชุด |
| Boundary check | `59→allow`, `60→warn`, `79→warn`, `80→block` ผ่าน | ตรวจฟังก์ชัน `risk_decision` แยกเดี่ยว ไม่ใช่ HTTP/UI test |
| Deployment metadata | `experimental_demo` | อ่านจาก artifact; ไม่ใช่ผลตรวจ live server |
| Production / promotion | `production_ready=false`, `promotion_ready=false`, `statistical_gate_passed=false` | ห้ามอ้างว่าผ่านเกณฑ์นำไปใช้งานจริง |
| Measured gate | `measured_gate_passed=true` | ผ่านเฉพาะขอบเขตแก้กรณี reference-root และตรวจไม่ให้ผลชุดที่กำหนดถดถอย ไม่ใช่หลักฐานลด FPR ทั่วอินเทอร์เน็ต |
| นโยบายเดิมที่ artifact เก็บไว้ | warning `85.05`, block `95.77` | การใช้ 60/80 เป็นการเปลี่ยน operating policy; artifact ระบุว่า FPR ในผลย้อนหลังสูงขึ้นเมื่อเทียบกับเกณฑ์เดิม อย่าเรียกการเปลี่ยน threshold ว่าเพิ่มความแม่นยำ |

## 4. ผลที่บันทึกไว้และใช้ประกอบตารางผลได้

ทุกตัวเลขในตารางนี้มาจาก `evaluations.<ชื่อชุด>.candidate` ของ [evaluation.json](evidence/evaluation.json) ค่า Precision, Recall, F1 และ FPR แสดงเป็นร้อยละและปัดทศนิยมสองตำแหน่ง ขนาดชุดเป็นจำนวน URL ไม่ใช่จำนวน URL ที่นำมารวมกันเป็นชุดทดสอบเดียว ควรเลือกชุดให้สอดคล้องกับคำถามวิจัยและคงข้อจำกัดของแต่ละชุดไว้ด้วย

| ชุดประเมิน | จำนวน URL / domains | เกณฑ์ | Precision % | Recall % | F1 % | FPR % | TN / FP / FN / TP |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `fresh_uci_confirmation` | 15,463 / 15,463 | warning 60 | 74.30 | 34.48 | 47.11 | 4.36 | 10,828 / 494 / 2,713 / 1,428 |
| `fresh_uci_confirmation` | 15,463 / 15,463 | block 80 | 85.59 | 26.68 | 40.68 | 1.64 | 11,136 / 186 / 3,036 / 1,105 |
| `fresh_deepurlbench_confirmation_round2` | 10,000 / 10,000 | warning 60 | 76.80 | 58.72 | 66.55 | 17.74 | 4,113 / 887 / 2,064 / 2,936 |
| `fresh_deepurlbench_confirmation_round2` | 10,000 / 10,000 | block 80 | 80.85 | 43.82 | 56.84 | 10.38 | 4,481 / 519 / 2,809 / 2,191 |
| `historical_regression` | 70,085 / 46,703 | warning 60 | 94.85 | 67.29 | 78.73 | 5.60 | 26,135 / 1,549 / 13,868 / 28,533 |
| `historical_regression` | 70,085 / 46,703 | block 80 | 97.38 | 51.06 | 66.99 | 2.11 | 27,101 / 583 / 20,751 / 21,650 |
| `prior_deepurlbench_regression` | 20,000 / 17,420 | warning 60 | 77.26 | 60.07 | 67.59 | 17.68 | 8,232 / 1,768 / 3,993 / 6,007 |
| `prior_deepurlbench_regression` | 20,000 / 17,420 | block 80 | 80.98 | 42.92 | 56.10 | 10.08 | 8,992 / 1,008 / 5,708 / 4,292 |
| `prior_confirmation_regression` | 10,000 / 10,000 | warning 60 | 78.29 | 58.84 | 67.18 | 16.32 | 4,184 / 816 / 2,058 / 2,942 |
| `prior_confirmation_regression` | 10,000 / 10,000 | block 80 | 82.13 | 43.48 | 56.86 | 9.46 | 4,527 / 473 / 2,826 / 2,174 |
| `recent_phishing_regression` | 151 / 151 | warning 60 | — | 72.85 | — | ประเมินไม่ได้ | 0 / 0 / 41 / 110 |
| `recent_phishing_regression` | 151 / 151 | block 80 | — | 61.59 | — | ประเมินไม่ได้ | 0 / 0 / 58 / 93 |

| ประเด็นประกอบการตีความ | หลักฐาน / ข้อจำกัด |
| --- | --- |
| นิยาม metric | Precision = TP/(TP+FP), Recall = TP/(TP+FN), FPR = FP/(FP+TN); ควรรายงาน Recall และ FPR ร่วมกัน |
| ชุด phishing-only 151 URL | ไม่มี benign ตัวอย่าง จึงคำนวณ FPR และ ROC-AUC ไม่ได้; เลข FP=0 ไม่ได้แปลว่าอัตราแจ้งผิดเป็นศูนย์ |
| ROC-AUC / PR-AUC ของ UCI fresh | `0.689091 / 0.598435` ทั้งสอง threshold; AUC ไม่ใช่ผลจาก threshold เดียว |
| ROC-AUC / PR-AUC ของ DeepURLBench fresh round2 | `0.77865 / 0.764233` ทั้งสอง threshold |
| ชุด fresh | evaluation ระบุว่าตัด domains ที่มีในข้อมูลเก่าที่ตรวจหาได้ แต่ยังไม่ใช่ forward-temporal test และ audit การสัมผัสข้อมูลฝึกดั้งเดิมยังไม่ครบ |
| การเทียบ baseline/candidate ใน confirmation | ผลรวม FP/FN ที่บันทึกไม่ถดถอยบนชุดที่กำหนด; ไม่ใช่ statistical guarantee หรือหลักฐานว่าทุก URL เก่าถูกตรวจได้เหมือนเดิม |
| Validation ที่ใช้เลือกแบบจำลอง | [selection.json](evidence/selection.json) เลือก `support2`; warning FP จาก 5,199 เหลือ 5,197 และ Recall เดิม 0.674594; block FP/FN เดิม ตัวเลขนี้มาจากข้อมูลที่ใช้พัฒนา/เลือกโมเดล จึงไม่ใช่ผลทดสอบอิสระ |
| ขนาด validation ที่อ่านจาก confusion matrix | 196,681 ตัวอย่าง (`98,622` benign + `98,059` phishing) จาก `baseline_validation.all`; ไม่ใช้ `dataset_row_count` แทนขนาดชุดนี้ |
| URL ตัวอย่างที่ใช้เลือกหรือเช็ก | ใช้อธิบายกรณีเฉพาะได้ แต่ห้ามใช้กรณีที่เลือกไว้เป็นหลักฐานความแม่นยำทั่วไป |
| ช่วงความเชื่อมั่นและ calibration | ไฟล์ evaluation เก็บ `false_positive_rate_upper_95`, Brier score, log loss และ calibration bins; อย่าอ้าง calibrated probability เป็นโอกาส phishing จริงของ URL ใด ๆ โดยไม่มีการประเมินบริบทการใช้งาน |

## 5. ข้อจำกัดที่ต้องพิจารณาในบทอภิปราย

| ข้อจำกัด / สิ่งที่ยังต้องหา | หลักฐานหรือสิ่งที่ผู้เขียนต้องทำต่อ |
| --- | --- |
| รูปแบบการแก้เป็นรายบริบท | [design.json](evidence/design.json) ระบุ targeted reference-entry repair และ sparse observations; ไม่ใช่ข้อสรุปว่าลด false positive ทั่วอินเทอร์เน็ต |
| Calibration ไม่ได้ fit ใหม่ | ใช้ mapping Platt ดั้งเดิมต่อ; ต้องอ่านผล reliability ของ confirmation และไม่เรียกเป็น calibration ที่รับประกันความน่าจะเป็น |
| ผลด้าน Recall ยังต่ำในบางชุด | ดูตารางผล โดยเฉพาะ UCI fresh; อย่าเลือกนำเสนอเฉพาะ Precision หรือ FPR |
| วันสังเกต URL ไม่ครบ | evaluation ระบุ historical publisher labels และไม่ทราบวันสังเกตของแต่ละ URL; ต้องแยกเวลาของ artifact ออกจากช่วงข้อมูล |
| Original exposure audit ไม่ครบ | ไฟล์ฝึก baseline เดิมหายตามข้อจำกัดใน evaluation; ไม่สามารถรับรองว่าไม่มีข้อมูลจากชุดทดสอบทุก URL ปรากฏในการฝึกดั้งเดิม |
| ไม่ใช่ temporal validation | `forward_temporal_test=false` |
| Labels ไม่ผ่าน manual review ทุก URL | evaluation ระบุว่าไม่ได้เยี่ยมชม phishing URL และไม่ได้ตรวจป้ายกำกับทุก URL อย่างอิสระ |
| License / attribution | design บันทึก UCI PhiUSIIL `CC BY 4.0`, DeepURLBench `CC BY-NC 4.0`; ผู้เขียนต้องตรวจแหล่งเผยแพร่ต้นทางและอ้างอิงให้ครบก่อนนำข้อมูลไปแจกจ่ายหรืออ้างในบทความ |
| เอกสารเก่าอาจขัดกัน | `docs/RESEARCH_REFERENCES_TH.md` ในโครงการหลักยังกล่าวถึง artifact v5 ณ ตอนที่เขียน; ใช้เพื่อค้นเอกสารอ้างอิง แล้วตรวจ method/version กับ snapshot ชุดนี้ใหม่ |
| ไม่มีหลักฐาน user study/UX/latency | หากต้องการอ้าง ต้องออกแบบและเก็บผลเพิ่ม; อย่าเติมจำนวนผู้ทดลอง เวลา หรือผลความพึงพอใจเอง |
| ผู้แต่ง สถาบัน อาจารย์ที่ปรึกษา กิตติกรรมประกาศ และรูปแบบส่ง | ให้เจ้าของโครงงานกรอกและยืนยันเอง |

## 6. แผนที่ไฟล์หลักฐาน

| ไฟล์ | หน้าที่ |
| --- | --- |
| [active-model.json](evidence/active-model.json) | snapshot metadata/parameters/features/calibration และผลตรวจขอบเขตจาก artifact ปัจจุบัน |
| [evaluation.json](evidence/evaluation.json) | สำเนาตรง byte ของผล confirmation/regression ที่ hash ผูกกับ artifact |
| [selection.json](evidence/selection.json) | สำเนาตรง byte ของผล validation และการเลือก `support2` |
| [design.json](evidence/design.json) | สมมติฐาน วิธีแก้ แบบการประเมิน และข้อจำกัดที่ประกาศไว้ |
| [source-manifest.json](evidence/source-manifest.json) | SHA256/ขนาด/ที่มาของ source และหลักฐาน; ระบุความต่างระหว่างโครงการหลักกับ Git repository ที่อยู่ซ้อน |
