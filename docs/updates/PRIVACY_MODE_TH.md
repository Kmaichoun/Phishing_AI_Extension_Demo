# Privacy Mode Update

## แนวคิด

Privacy Mode เป็นโหมดสำหรับผู้ใช้ที่ไม่ต้องการให้ URL ถูกส่งออกไปยัง backend, ML API หรือ LLM ภายนอก ระบบจะยังตรวจความเสี่ยงพื้นฐานได้จาก Rule-based engine และหลักฐานบนหน้าเว็บที่ทำงานอยู่ใน browser

## เมื่อเปิด Privacy Mode

- Extension จะไม่เรียก `/predict` สำหรับ Machine Learning backend
- Warning page จะไม่เรียก `/explain` สำหรับ LLM/ChatGPT
- Feedback จะไม่ถูกส่งไป `/feedback`
- Feedback จะถูกบันทึกไว้ในเครื่องผ่าน `chrome.storage.local` หรือ `localStorage` ของ web app
- URL ที่เก็บใน feedback local จะถูก redacted เหลือเฉพาะโดเมน เช่น `https://example.com/[redacted]`
- หน้า warning จะแสดงป้าย `Privacy Mode • Local analysis`

## เมื่อปิด Privacy Mode

- ระบบกลับไปใช้ workflow เต็ม ได้แก่ layered evidence + URL Risk Model + FPR policy + LLM explanation + Feedback backend
- RiskScore มาจาก probability ของโมเดลโดยตรง และใช้ warn/block threshold ที่เลือกจาก grouped development predictions
- LLM ใช้เพื่ออธิบายเหตุผล ไม่ได้นำมาบวกคะแนนโดยตรง

## จุดขายของฟีเจอร์

ฟีเจอร์นี้ทำให้ Phish Radar AI เป็นเครื่องมือแบบ local-first ผู้ใช้สามารถเลือกได้เองว่าจะแลกความเป็นส่วนตัวกับความสามารถขั้นสูงหรือไม่ ถ้าเปิด Privacy Mode ระบบยังช่วยเตือนความเสี่ยงได้โดยไม่ส่ง URL ออกจาก browser

## วิธีทดสอบ

1. Reload extension ที่ `chrome://extensions`
2. เปิด popup ของ Phish Radar AI
3. เปิดสวิตช์ `Privacy Mode`
4. เปิดเว็บหรือลิงก์ที่มีความเสี่ยง
5. ตรวจว่า warning page แสดง `Privacy Mode เปิดอยู่`
6. กด feedback แล้วตรวจว่าข้อความขึ้นว่าเก็บไว้ในเครื่อง ไม่ส่งไป backend
7. ปิด Privacy Mode แล้วทดสอบอีกครั้ง ระบบจะกลับไปใช้ ML/LLM ตามปกติ
