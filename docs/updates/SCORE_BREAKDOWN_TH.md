# Score Breakdown: Risk Model v2

หน้า Web App และ Warning แยกบทบาทของแต่ละส่วนอย่างชัดเจน:

1. **Rule evidence** — หลักฐานจาก URL/DOM/form ที่ตรวจใน browser ใช้อธิบายและ
   เป็น local fallback แต่ไม่ถูกนำไปถ่วงน้ำหนักกับโมเดล
2. **URL Risk Model** — แสดง `RiskScore = 100 × p(phishing | URL features)` จาก
   L1 Logistic Regression
3. **Decision policy** — แสดง `allow / warn / block` พร้อม warning และ blocking
   threshold ที่ผูกกับ model/policy version
4. **LLM explanation** — Qwen อธิบายหลักฐานและคำแนะนำ ไม่ได้บวกคะแนนและไม่เปลี่ยน
   decision

เมื่อ Privacy Mode เปิด ระบบจะระบุ `local evidence` และไม่แสดงคะแนน local เป็น
ML probability เพื่อป้องกันความเข้าใจผิด
