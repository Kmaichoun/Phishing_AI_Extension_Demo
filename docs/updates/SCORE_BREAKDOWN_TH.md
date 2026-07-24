# อัปเดต Score Breakdown

เพิ่มการแสดงผลให้ผู้ใช้เห็นชัดว่า Phish Radar AI ใช้หลายชั้นในการวิเคราะห์ ไม่ใช่แค่แสดง Risk Score เดียว

## สิ่งที่เพิ่ม

1. หน้า Warning เต็มจอมีส่วน "คะแนนนี้มาจากอะไรบ้าง"
   - Rule-base: คะแนนจากกฎ เช่น URL ยาวผิดปกติ, subdomain, IP host, คำเสี่ยง, redirect และ encoded URL
   - Machine Learning: คะแนนความน่าจะเป็นจากโมเดล backend หลังทำ calibration
   - LLM Explanation: แสดงสถานะว่าพร้อมใช้งาน / ใช้ข้อความสำรอง / ปิดอยู่

2. อธิบายสูตรคะแนนรวมให้ชัดเจน
   - Final score = alpha(Rule-base) + (1-alpha)(Machine Learning)
   - ค่า alpha และ threshold มาจากผล cross-validation ใน `backend/data/risk_model_evaluation.json`
   - LLM ใช้สร้างคำอธิบายและคำแนะนำ ไม่ได้นำมาบวกคะแนนโดยตรง เพื่อไม่ให้ระบบอ้างว่า LLM เป็นตัวตัดสินหลัก

## วิธีทดสอบ

1. เปิด backend
2. Reload extension ที่ chrome://extensions
3. เปิดเว็บหรือลิงก์ที่ถูกเตือน
4. ดูหน้า Warning จะเห็นแถบ Rule-base, Machine Learning และ LLM Explanation

ถ้า ML ยังไม่ขึ้น ให้ตรวจว่า backend เปิดอยู่ที่ http://127.0.0.1:8765 และ model_ready เป็น True
