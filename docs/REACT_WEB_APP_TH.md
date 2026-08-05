# โครงสร้าง React Web App

Web App ของ Phish Radar AI ใช้ **React สำหรับเว็บ** และ **Vite** ไม่ได้ใช้
React Native, Expo หรือ Metro bundler ส่วน Chrome Extension และ Backend
ยังเป็นคนละ runtime และไม่ถูกย้ายเข้า React

## เทคโนโลยีที่ใช้

- React: สร้าง UI จาก Component และอัปเดตหน้าจอด้วย State
- React DOM: mount React ลงใน `web-app/index.html`
- React hash routing: แยกหน้า Login, Scanner, QR, Dashboard และ Settings
- Vite: development server, hot reload และ production build
- React Context + Hooks: จัดการ Session, Theme, Privacy Mode, ผลตรวจ และประวัติ
- GSAP: animation ตอนเปิดหน้าและ reveal เนื้อหา
- jsQR + BarcodeDetector: อ่าน QR จากไฟล์และกล้อง
- Fetch API: เชื่อม FastAPI ที่พอร์ต 8765

## เส้นทางหน้าเว็บ

ระบบใช้ routing แบบ hash ที่เขียนเป็น React Context ขนาดเล็ก เพื่อให้เปิดจาก
static hosting ได้โดยไม่ต้องตั้งค่า server rewrite เพิ่มเติม และหลีกเลี่ยง
dependency routing ที่มี security advisory ในวันที่ย้ายระบบ

| URL | Component | หน้าที่ |
| --- | --- | --- |
| `/#/login` | `LoginPage.jsx` | Login, Register และตรวจสถานะระบบบัญชี |
| `/#/scan` | `ScannerPage.jsx` | วิเคราะห์ URL และแสดง Rule/ML/LLM |
| `/#/qr` | `QrPage.jsx` | อ่าน QR จากกล้องหรือรูป |
| `/#/dashboard` | `DashboardPage.jsx` | Metrics, Health, History และ Export |
| `/#/settings` | `SettingsPage.jsx` | แก้ Username, Email และ Password |

## โครงสร้างไฟล์สำคัญ

```text
web-app/
├── index.html                 # HTML shell มีเพียง React mount point
├── package.json               # React/Vite dependencies และคำสั่ง
├── vite.config.mjs            # พอร์ต 5505, local domain และ bundle splitting
├── analyzer.js                # Rule-based analyzer เดิม ใช้ร่วมผ่าน service wrapper
├── src/
│   ├── main.jsx               # createRoot, Router และ Context providers
│   ├── App.jsx                # Route map และ protected layout
│   ├── components/            # Header, Theme, Password, Motion, Route guard
│   ├── contexts/              # Router, Auth, Theme และสถานะการวิเคราะห์
│   ├── pages/                 # Login, Scanner, QR, Dashboard, Settings
│   └── services/              # API client, runtime config และ risk helpers
└── assets/                    # Logo และ local fonts
```

## การทำงานของข้อมูล

```text
React Page
  -> React Context / Hook
  -> services/api.js
  -> FastAPI :8765
  -> MySQL/MariaDB + ML model + Qwen/Ollama
  -> JSON response
  -> React State
  -> Component re-render
```

Session ยังใช้ HttpOnly cookie และทุก request ของระบบบัญชี/ประวัติส่ง
`credentials: include` เหมือนเดิม รหัสผ่านไม่ถูกเก็บใน React state ส่วนกลาง
และไม่ถูกเก็บใน localStorage

## คำสั่งใช้งาน

ติดตั้ง dependency ครั้งแรก:

```bash
cd web-app
npm install
```

เปิดเฉพาะ React Web App:

```bash
npm run dev
```

หรือจากโฟลเดอร์หลัก:

```bash
./start-web.sh
```

เปิดทั้ง Backend และ React Web App:

```bash
./start-demo.sh
```

สร้าง production build:

```bash
cd web-app
npm run build
```

ไฟล์ที่ build แล้วอยู่ใน `web-app/dist/` และไม่ควรแก้ด้วยมือ

## สิ่งที่ต้องรู้เวลาพัฒนาต่อ

1. แก้ UI ใน `src/pages` และ `src/components` ไม่แก้ `dist/`
2. เพิ่ม API endpoint ใน `src/services/api.js` แล้วเรียกจาก Context หรือ Page
3. ข้อมูลที่ใช้หลายหน้าให้เก็บใน Context; state ที่ใช้เฉพาะหน้าให้เก็บใน Page
4. Route ที่ต้อง Login ต้องอยู่หลัง `ProtectedRoute`
5. ตัวแปรฝั่งเว็บที่เปิดเผยได้เท่านั้นจึงใช้ชื่อขึ้นต้น `VITE_`; ห้ามใส่ password,
   database credential หรือ API secret เพราะค่าจะถูกรวมใน JavaScript bundle
6. `node_modules/` และ `dist/` เป็นไฟล์สร้างใหม่ได้และถูกกันออกจาก Git
7. Chrome Extension ยังไม่ใช่ React และไม่ต้องรัน Vite เพื่อโหลด Extension
8. Backend, Database schema, ML model และ Qwen/Ollama ไม่ได้เปลี่ยนจากการย้าย UI

## ตั้งค่า Backend URL

ระบบเลือก URL ให้อัตโนมัติจาก hostname:

- `127.0.0.1` ใช้ `http://127.0.0.1:8765`
- `localhost` ใช้ `http://localhost:8765`
- `app.phishradar.localhost` ใช้ `http://api.phishradar.localhost:8765`

ถ้าต้องการ override ให้คัดลอก `web-app/.env.example` เป็น `web-app/.env`
แล้วกำหนด:

```dotenv
VITE_API_BASE=http://127.0.0.1:8765
```

หลังแก้ `.env` ต้องหยุดและเปิด Vite ใหม่
