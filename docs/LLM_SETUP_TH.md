# Phish Radar AI — Qwen/Ollama Setup ด้วย Git Bash

LLM มีหน้าที่อธิบายผลจาก Rule-based และ Machine Learning ให้ผู้ใช้อ่านง่ายขึ้น ไม่ได้เป็นตัวตัดสินว่าลิงก์เป็น phishing โดยตรง ค่าเริ่มต้นของโปรเจกต์คือ `qwen3:4b` ที่รันในเครื่องผ่าน Ollama

## วิธีใช้ Qwen (ค่าเริ่มต้น)

ติดตั้งและเปิด Ollama ก่อน จากนั้นเปิด Git Bash ที่โฟลเดอร์หลักของโปรเจกต์แล้วรัน:

```bash
ollama pull qwen3:4b
export LLM_PROVIDER=ollama
export OLLAMA_MODEL=qwen3:4b
./start-backend.sh
```

ถ้า Ollama ทำงานเป็น Windows service อยู่แล้ว ไม่ต้องเปิด `ollama serve` เพิ่ม หากคำสั่ง `ollama` ใช้ไม่ได้ ต้องติดตั้ง Ollama หรือเพิ่มโปรแกรมลง PATH ก่อน

## เปิดทั้ง Backend และ Web App

หลังเปิด Ollama แล้วใช้คำสั่งเดียว:

```bash
./start-demo.sh
```

จากนั้นเปิด `http://127.0.0.1:5505/#/login` และคงหน้าต่าง Git Bash ไว้ กด `Ctrl+C` เพื่อหยุด Backend/Web App

## ใช้ OpenAI เป็นตัวเลือกสำรอง

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY="ใส่ API key ของคุณตรงนี้"
export OPENAI_MODEL=gpt-5.6-luna
./start-backend.sh
```

ห้ามใส่ API key ใน Extension, JavaScript หรือ commit ลง Git หากต้องการให้ระบบเลือก Ollama เมื่อพร้อมและกลับไป OpenAI เมื่อ Ollama ไม่ทำงาน ให้ใช้ `export LLM_PROVIDER=auto` และตั้ง `OPENAI_API_KEY` ไว้ด้วย

## ความเป็นส่วนตัว

ระบบส่ง URL ให้ LLM หลังตัด username/password, query string และ fragment ออกแล้ว เหลือเฉพาะ protocol, hostname, port และ path ที่จำเป็นต่อการอธิบาย เมื่อเปิด Privacy Mode จะไม่เรียก LLM

หาก Ollama ยังไม่พร้อม ระบบยังใช้ URL Risk Model และหลักฐานหลายชั้นได้ตามปกติ และจะแสดงคำอธิบายสำรองแทน

ดูตัวเลือกโมเดลและแผนทดสอบได้ที่ [LLM_COMPARISON_TH.md](LLM_COMPARISON_TH.md)
