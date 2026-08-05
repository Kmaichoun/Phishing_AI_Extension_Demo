# Backend data

โฟลเดอร์นี้แยกข้อมูลตั้งต้น ข้อมูลที่ดาวน์โหลด และผลการประเมินออกจากโค้ดอย่างชัดเจน

- `seed_urls.csv` — ตัวอย่างขนาดเล็กสำหรับ smoke test หรือใช้เมื่อยังไม่ได้สร้าง dataset หลัก
- `cache/` — snapshot ต้นทางจาก PhishTank, OpenPhish และ Tranco (ไม่บันทึกเข้า Git)
- `training_urls.csv` — dataset ที่ผ่าน normalize, deduplicate และมี RuleScore แล้ว (ไม่บันทึกเข้า Git)
- `training_urls.manifest.json` — วันที่สร้าง สถิติ และ SHA-256 ของ snapshot ต้นทาง
- `risk_model_evaluation.json` — ผล grouped cross-validation/holdout, probability quality, coefficients และการเลือก warn/block threshold ภายใต้ FPR
- `feedback.csv` — feedback ระหว่างใช้งานจริง (ไม่บันทึกเข้า Git)

สร้างข้อมูลใหม่ด้วย:

    .\.venv\Scripts\python.exe .\backend\build_dataset.py --refresh

ฝึกและประเมินโมเดลด้วย:

    .\.venv\Scripts\python.exe .\backend\train_model.py

ไฟล์ `model.pkl` จะถูกบีบอัดอัตโนมัติเพื่อลดพื้นที่ โดย Backend ยังโหลดผ่าน `joblib.load()` ได้ตามเดิม

ตัวสร้าง dataset จะอ่าน URL เป็นข้อความเท่านั้นและไม่เข้าเยี่ยมชม URL จาก feed แต่ไฟล์อาจมีลิงก์อันตรายจริง จึงไม่ควรคลิกหรือเปิดไฟล์ด้วยโปรแกรมที่ทำให้ลิงก์ทำงานอัตโนมัติ
