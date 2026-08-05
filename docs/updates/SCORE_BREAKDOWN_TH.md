# Score Breakdown: Fixed 40/60 Policy

หน้า Web App และ Warning แสดงคะแนนแต่ละส่วนแยกกัน:

1. **RuleScore (40%)** — หลักฐานจาก URL, DOM และ form ที่ตรวจใน browser
2. **MLScore (60%)** — `100 × p(phishing | URL features)` จาก L1 Logistic Regression
3. **FinalScore** — `0.40(RuleScore) + 0.60(MLScore)`
4. **Decision policy** — `allow / warn / block` ตาม warning และ blocking threshold
5. **LLM explanation** — Qwen อธิบายหลักฐาน แต่ไม่แก้คะแนนหรือ decision

เมื่อ Privacy Mode เปิดหรือโมเดลไม่พร้อม ระบบใช้ RuleScore เป็น fallback และแสดงว่า
ยังไม่ได้ใช้สูตร 40/60 เพราะไม่มี MLScore ในรอบนั้น
