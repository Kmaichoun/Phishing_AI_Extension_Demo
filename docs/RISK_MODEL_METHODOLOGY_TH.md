# วิธีสร้างและประเมิน Risk Model

เอกสารนี้อธิบาย pipeline ที่ใช้สร้าง `backend/model.pkl` และเหตุผลของการตัดสินใจแต่ละขั้น เพื่อให้ทำซ้ำ ตรวจสอบ และพัฒนาต่อได้

## 1. ชุดข้อมูล

ค่าเริ่มต้นของ `backend/build_dataset.py` สร้างข้อมูลสมดุล 10,000 URL:

- phishing 5,000 รายการ จาก [PhishTank verified online feed](https://phishtank.org/developer_info.php), [OpenPhish Community Feed](https://www.openphish.com/phishing_feeds.html) และ seed ขนาดเล็กของโปรเจกต์
- legitimate 5,000 รายการ จาก [Tranco top-sites list](https://tranco-list.eu/) และ seed ขนาดเล็กของโปรเจกต์

Tranco ถูกออกแบบให้เป็น top-sites ranking ที่ทำซ้ำได้และต้านทานการปั่นอันดับมากกว่าการใช้รายการยอดนิยมจากผู้ให้บริการรายเดียว ดูงานของ Le Pochat และคณะ: [Tranco: A Research-Oriented Top Sites Ranking Hardened Against Manipulation](https://doi.org/10.14722/ndss.2019.23386)

ขั้นตอนเตรียมข้อมูล:

1. รับเฉพาะ URL แบบ `http` หรือ `https` ที่มี hostname และตัด fragment ออก
2. ลบ URL ซ้ำแบบ case-insensitive
3. ถ้า hostname เดียวกันพบใน phishing และ Tranco จะตัดฝั่ง legitimate ออก เพื่อลด label conflict
4. เก็บ `source`, `label`, `hostname group` และ RuleScore ของ analyzer จริง
5. สุ่มด้วย seed 42 และบันทึก SHA-256 ของ snapshot ทุกต้นทางใน manifest

RuleScore สำหรับการฝึกมาจาก `web-app/analyzer.js` แบบ URL-only โดยตรง และบันทึก hash ของ analyzer ทั้ง Web App/Extension ไว้ใน manifest การตรวจชุดข้อมูลรอบนี้พบว่าทั้งสอง runtime ให้ URL-only score ตรงกัน 10,000/10,000 รายการ แม้ไฟล์จะมี logic สำหรับบริบทหน้าเว็บที่ต่างกันบางส่วน

ข้อจำกัดสำคัญ: การอยู่ใน Tranco เป็นเพียง proxy ของ legitimate ไม่ใช่การรับรองว่าเว็บไซต์ปลอดภัยตลอดเวลา และ feed phishing มีการเปลี่ยนแปลงตามเวลา จึงควรเก็บวันที่ snapshot และ retrain เป็นระยะ

ตัวสร้างจะไม่เข้าเยี่ยมชม URL ใน feed แต่จะ parse เป็นข้อความเท่านั้น

## 2. Cross-validation และการป้องกันข้อมูลรั่วไหล

ใช้ `StratifiedGroupKFold` 5 folds โดย stratify ตาม label และ group ตาม hostname URL จาก hostname เดียวกันจึงไม่ถูกแยกระหว่าง train/test fold วิธีนี้เข้มกว่าการสุ่มราย URL เพราะ path หลายรายการจากโดเมนเดียวกันมักมี feature คล้ายกันมาก ดูคำอธิบาย API ที่ [scikit-learn: StratifiedGroupKFold](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.StratifiedGroupKFold.html)

ทุกแถวจะได้รับ out-of-fold prediction เพียงครั้งเดียว แล้วจึงนำคะแนนเหล่านี้ไปประเมิน policy การผสมคะแนน

## 3. Probability calibration

Random Forest ให้ `predict_proba` ได้ แต่ค่าดิบไม่จำเป็นต้องตรงกับความถี่ของเหตุการณ์จริง ระบบจึงครอบโมเดลด้วย `CalibratedClassifierCV(method="sigmoid")` และใช้ inner Stratified Group folds ภายใน training fold เท่านั้น

รายงานเปรียบเทียบค่าก่อนและหลัง calibration ด้วย Brier score และ log loss ซึ่งยิ่งต่ำยิ่งดี แนวคิดและ reliability diagram อ้างอิงได้จาก [scikit-learn probability calibration](https://scikit-learn.org/stable/modules/calibration.html) และงานคลาสสิกของ Niculescu-Mizil และ Caruana: [Predicting Good Probabilities with Supervised Learning](https://doi.org/10.1145/1102351.1102430)

## 4. การค้นหา alpha และ threshold

สูตรที่ใช้คือ:

    FinalScore = alpha * RuleScore + (1 - alpha) * MLScore

โดยคะแนนทั้งสองถูกแปลงเป็นช่วง 0–1 ก่อนคำนวณ:

- alpha: 0.00, 0.05, ..., 1.00 รวม 21 ค่า
- threshold: 0.05, 0.06, ..., 0.95 รวม 91 ค่า
- รวม 1,911 policy candidates

สำหรับแต่ละ candidate จะคำนวณ Precision, Recall, F1, ROC-AUC และ False Positive Rate จาก out-of-fold scores ชุดเดียวกัน

กติกาเลือกค่าเริ่มต้นตั้งเพดาน FPR ไม่เกิน 5% แล้วเรียงความสำคัญดังนี้:

1. Recall สูงสุด เพื่อพลาด phishing ให้น้อย
2. F1 สูงสุด
3. Precision สูงสุด
4. ROC-AUC สูงสุด
5. FPR ต่ำกว่าเมื่อค่าอื่นเท่ากัน

ถ้าไม่มี candidate ใดผ่านเพดาน FPR ระบบจะเลือก FPR ต่ำสุดก่อน เมตริก PR เหมาะกับข้อมูลตรวจจับที่อาจไม่สมดุลมากกว่า accuracy อย่างเดียว ดู [The Precision-Recall Plot Is More Informative than the ROC Plot](https://doi.org/10.1371/journal.pone.0118432)

## 5. ไฟล์ผลลัพธ์

- `backend/data/training_urls.manifest.json` — แหล่งข้อมูล hash และสถิติ RuleScore
- `backend/data/risk_model_evaluation.json` — configuration, calibration metrics, ผลทุก alpha ที่ดีที่สุด, top candidates และผลแยก fold
- `backend/model.pkl` — calibrated model พร้อม alpha, decision threshold, metrics, dataset hash และวันฝึก

backend อ่าน policy จาก model bundle โดยตรงและคืน `alpha`, `decision_threshold`, `risk_margin` ใน `/predict` ทั้ง Web App และ Extension จึงแสดงสูตรที่ใช้จริงได้

เมื่อ Extension ติดต่อ ML backend ได้ จะใช้ `decision_threshold` ของ calibrated model สำหรับการเตือน ส่วน threshold ที่ผู้ใช้ตั้งใน Extension จะใช้กับการตรวจแบบ local/offline ที่ยังไม่ได้รับ model policy

## 6. คำสั่งใช้งาน

สร้าง snapshot ใหม่จากอินเทอร์เน็ต:

    .\.venv\Scripts\python.exe .\backend\build_dataset.py --refresh

สร้าง dataset ซ้ำจาก cache เดิมโดยไม่ใช้อินเทอร์เน็ต:

    .\.venv\Scripts\python.exe .\backend\build_dataset.py --offline

ฝึกโมเดล:

    .\.venv\Scripts\python.exe .\backend\train_model.py

ก่อนใช้ production ควรเพิ่ม time-split holdout ที่ไม่ถูกใช้เลือก policy, ทดสอบบน traffic จริงที่ได้รับอนุญาต, ตรวจ concept drift และกำหนด FPR ตามต้นทุนความผิดพลาดของระบบจริง ไม่ควรตีความผล cross-validation ชุดเดียวว่าเป็นการรับรองความปลอดภัย
