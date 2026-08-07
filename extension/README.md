# Browser Extension

โฟลเดอร์นี้คือ Chrome/Brave Extension แบบ Manifest V3 ทั้งหมด และเป็นโฟลเดอร์ที่ต้องเลือกเมื่อกด **Load unpacked**

## กลุ่มไฟล์

- `manifest.json` — permissions, service worker, content scripts และ icons
- `background.js` — navigation protection, Backend communication และ Chrome storage
- `content.js` / `content.css` — สแกนหน้าเว็บ ลิงก์ ฟอร์ม และ UI ที่ฉีดลงหน้าเว็บ
- `popup.*` — หน้าควบคุม Extension
- `warning.*` — หน้าเตือนและคำอธิบายผล
- `safe-preview.*` — เปิดหน้าเสี่ยงแบบจำกัดการกรอกข้อมูล
- `qr-scanner.*` — สแกน QR และวิเคราะห์ URL
- `analyzer.js` — Rule-based scoring สำหรับ Extension runtime
- `ml-feedback-client.js` — `/predict`, `/explain` และ `/feedback`
- `app-trust.js` — รายการ Web App origin ที่เชื่อถือ
- `icons/` — ไอคอนที่ Manifest และหน้าเตือนใช้งาน

## ตรวจหลังแก้ไข

รันจากโฟลเดอร์หลักของโปรเจกต์:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./scripts/validate_project.ps1
```

จากนั้น Reload Extension และ Reload แท็บเว็บที่ใช้ทดสอบ
