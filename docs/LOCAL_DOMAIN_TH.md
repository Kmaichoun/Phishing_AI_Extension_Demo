# Local Domain ของ Phish Radar AI

โปรเจกต์กำหนดชื่อสำหรับใช้งานบนเครื่องนี้ไว้ดังนี้:

- Web App: `http://app.phishradar.localhost:5505/#/login`
- Backend: `http://api.phishradar.localhost:8765/health`
- URL เดิม `127.0.0.1` และ `localhost` ยังใช้เป็น fallback ได้

## เปิดใช้งาน Domain บน Windows

เริ่มระบบด้วย `./start-demo.sh` แล้วลองเปิด Domain ใหม่ใน Chrome ได้เลย เพราะชื่อที่ลงท้ายด้วย `.localhost` ถูกออกแบบมาสำหรับ loopback บนเครื่องพัฒนา

หากเบราว์เซอร์หรือเครื่องมือบน Windows รายงานว่าหา Domain ไม่พบ ให้เปิด PowerShell ด้วย **Run as administrator** ที่โฟลเดอร์โปรเจกต์ แล้วรัน:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_local_domain.ps1
```

สคริปต์เพิ่มเฉพาะ block ที่มี marker `PHISH RADAR AI LOCAL DOMAINS` ในไฟล์ hosts และทำงานซ้ำได้โดยไม่สร้างรายการซ้ำ

หากต้องการนำรายการออก:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_local_domain.ps1 -Remove
```

จากนั้นเข้า Web App ผ่าน Domain ใหม่ กด Reload Extension หนึ่งครั้งที่ `chrome://extensions/` เพื่อให้ manifest และ service worker รุ่นใหม่ทำงาน

## วิธีที่ Extension จดจำ Web App

ไฟล์ `extension/app-trust.js` เป็นรายการ Origin ที่ Extension เชื่อว่าเป็น Web App ของระบบ การตรวจใช้ค่า `protocol + hostname + port` แบบตรงตัว ไม่ได้เชื่อถือทุก service ที่อยู่บน localhost

เมื่ออยู่บน Web App:

- badge ของ Extension แสดง `APP`
- ไม่ redirect ไป `warning.html`
- Popup แสดงสถานะ `Web App ของ Phish Radar AI`
- ลิงก์ภายนอกที่อยู่ใน Web App ยังถูกตรวจตามปกติ

## เมื่อต้องการใช้ Domain จริงบนอินเทอร์เน็ต

Domain `.localhost` ใช้ได้เฉพาะเครื่องพัฒนา หากต้องการให้ผู้อื่นเข้าใช้งาน ต้องมี Domain จริง, DNS, HTTPS และ Server/Hosting สำหรับทั้ง Web App กับ Backend จากนั้น:

1. เพิ่ม HTTPS Origin ของ Web App ใน `TRUSTED_WEB_APP_ORIGINS` ที่ `extension/app-trust.js`
2. เพิ่ม Origin เดียวกันในตัวแปร `AUTH_WEB_ORIGINS` ของ Backend
3. กำหนด `window.PHISH_RADAR_API_BASE` ให้ชี้ไป HTTPS API หรือวาง reverse proxy ที่ `/api`
4. Reload/Package Extension ใหม่

อย่าเพิ่มเพียงชื่อ hostname กว้าง ๆ หรือ trust ทุก subdomain เพราะจะทำให้โดเมนที่ไม่ใช่ของระบบหลุดจากการตรวจได้
