# คู่มือ Developer — Phish Radar AI

เอกสารนี้สำหรับผู้พัฒนาที่รับช่วงโปรเจกต์บน Windows ตั้งแต่การ Clone, ติดตั้งระบบ,
เปิด MySQL/Backend/Qwen/Web App, โหลด Chrome Extension ไปจนถึงการตรวจงานก่อนส่งขึ้น GitHub

## 1. ภาพรวมระบบ

| ส่วน | เทคโนโลยี | ตำแหน่ง | พอร์ต |
|---|---|---|---|
| Web App | React 19 + Vite | `web-app/` | `5505` |
| Chrome Extension | Manifest V3 + JavaScript | `extension/` | ไม่มี |
| Backend/API | Python + FastAPI + Uvicorn | `backend/` | `8765` |
| Database | MySQL/MariaDB | `database/mysql/` | `3306` |
| URL Risk Model | Random Forest + calibration/fusion | `backend/model.pkl` | ทำงานใน Backend |
| LLM | Qwen ผ่าน Ollama (ตัวเลือกเสริม) | Ollama ในเครื่อง | `11434` |

เส้นทางการทำงานหลัก:

```text
React Web App / Chrome Extension
             |
             v
FastAPI http://127.0.0.1:8765
       |                 |
       v                 v
MySQL/MariaDB       URL Model + Ollama
```

## 2. โปรแกรมที่ต้องติดตั้ง

ติดตั้งโปรแกรมเหล่านี้ก่อน:

1. Git for Windows และ Git Bash
2. Python 3.12 แบบ 64-bit โดยเลือก `Add Python to PATH`
3. Node.js `20.19+` หรือ `22.12+`
4. XAMPP สำหรับ MySQL/MariaDB และ phpMyAdmin
5. Google Chrome หรือ Brave
6. Ollama เฉพาะเมื่อต้องการคำอธิบายจาก Qwen

ตรวจเวอร์ชันใน Git Bash:

```bash
git --version
python --version
node --version
npm --version
```

## 3. Clone โปรเจกต์

โค้ดพัฒนาปัจจุบันอยู่บน branch `codex/fixed-formula-40-60`:

```bash
git clone -b codex/fixed-formula-40-60 https://github.com/Kmaichoun/Phishing_AI_Extension_Demo.git
cd Phishing_AI_Extension_Demo
```

ถ้ามีโปรเจกต์อยู่แล้ว:

```bash
git switch codex/fixed-formula-40-60
git pull --ff-only origin codex/fixed-formula-40-60
```

อย่าคัดลอก `.venv/` หรือ `web-app/node_modules/` มาจากเครื่องอื่น ให้สร้างใหม่ตามขั้นตอนด้านล่าง

## 4. ติดตั้ง Backend

รันจากโฟลเดอร์หลักของโปรเจกต์:

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install --upgrade pip
./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
```

ตรวจว่า Python ของโปรเจกต์ใช้งานได้:

```bash
./.venv/Scripts/python.exe --version
```

`backend/model.pkl` อยู่ใน Git อยู่แล้ว จึงเปิดระบบตรวจ URL ได้โดยไม่ต้องสร้าง dataset
หรือฝึกโมเดลใหม่

## 5. ติดตั้ง Web App

ใช้ `npm ci` เพื่อให้ dependency ตรงกับ `package-lock.json`:

```bash
cd web-app
npm ci
cd ..
```

## 6. เตรียม MySQL/MariaDB

1. เปิด XAMPP Control Panel
2. กด Start ที่ `MySQL`
3. กด Start ที่ `Apache` เมื่อต้องการใช้ phpMyAdmin
4. เปิด `http://localhost/phpmyadmin/`
5. สร้างฐานข้อมูลชื่อ `ip_std6730202581` โดยใช้ collation `utf8mb4_unicode_ci`

สร้างไฟล์ตั้งค่าจากแม่แบบ:

```bash
cp .env.example .env
```

ตั้งค่า `.env` สำหรับ XAMPP ค่าเริ่มต้น:

```dotenv
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=ip_std6730202581
MYSQL_USER=root
MYSQL_PASSWORD=
MYSQL_CHARSET=utf8mb4

AUTH_SESSION_HOURS=168
AUTH_COOKIE_SECURE=false
AUTH_WEB_ORIGINS=http://app.phishradar.localhost:5505,http://127.0.0.1:5505,http://localhost:5505
SEARCH_HISTORY_RETENTION_DAYS=90

LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3:4b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

หาก MySQL มีรหัสผ่าน ให้ใส่ใน `MYSQL_PASSWORD` ห้าม commit `.env` หรือส่งรหัสผ่านขึ้น GitHub

สร้างตารางทั้งหมด:

```bash
./migrate-db.sh
```

ผลสำเร็จต้องลงท้ายประมาณนี้:

```text
MySQL/MariaDB migrations completed successfully
```

ถ้ารันสคริปต์ไม่ได้ สามารถ Import ไฟล์ต่อไปนี้ใน phpMyAdmin ตามลำดับ:

```text
database/mysql/migrations/001_create_users.sql
database/mysql/migrations/002_create_user_devices.sql
database/mysql/migrations/003_create_sessions.sql
database/mysql/migrations/004_create_search_history.sql
```

## 7. เปิด Qwen/Ollama (ตัวเลือกเสริม)

ทำครั้งแรก:

```bash
ollama pull qwen3:4b
```

ปกติ Ollama บน Windows ทำงานเป็น service อยู่แล้ว ทดสอบด้วย:

```bash
ollama list
```

ถ้ายังไม่ทำงาน:

```bash
ollama serve
```

ถ้า `ollama serve` แจ้งว่าพอร์ต `11434` ถูกใช้อยู่ แปลว่า Ollama เปิดอยู่แล้ว
ระบบตรวจ URL ยังทำงานได้แม้ไม่เปิด Ollama แต่จะแสดงคำอธิบายสำรองแทน LLM

## 8. เปิดระบบ

### วิธีแนะนำ: เปิด Backend และ Web App พร้อมกัน

```bash
./start-demo.sh
```

เปิดหน้าเว็บ:

```text
http://app.phishradar.localhost:5505/#/login
```

ถ้า local domain เปิดไม่ได้ ใช้:

```text
http://127.0.0.1:5505/#/login
```

### เปิดแยกหน้าต่าง

Git Bash หน้าต่างที่ 1:

```bash
./start-backend.sh
```

Git Bash หน้าต่างที่ 2:

```bash
./start-web.sh
```

ให้เปิดหน้าต่าง Git Bash ค้างไว้ กด `Ctrl+C` เพื่อหยุดระบบ

## 9. ตรวจสถานะ Backend

เปิด URL ต่อไปนี้ในเบราว์เซอร์:

```text
http://127.0.0.1:8765/health
http://127.0.0.1:8765/docs
```

ใน `/health` ควรตรวจค่าหลัก:

- `ok` เป็น `true`
- `model_ready` เป็น `true`
- `database.connected` เป็น `true`
- schema ของ auth/history/risk audit เป็น `true`
- LLM พร้อมเมื่อเปิด Ollama และติดตั้ง `qwen3:4b`

## 10. โหลด Chrome Extension

1. เปิด `chrome://extensions/`
2. เปิด **Developer mode**
3. กด **Load unpacked**
4. เลือกโฟลเดอร์ `extension/` ไม่ใช่โฟลเดอร์หลักของโปรเจกต์
5. Pin ไอคอน Phish Radar AI
6. เมื่อแก้ไฟล์ Extension ให้กด **Reload** ที่ `chrome://extensions/`
7. Refresh หน้าเว็บที่กำลังทดสอบอีกครั้ง

Extension ใช้ Rule-based ได้แม้ Backend ปิด แต่ ML, Login, History, Feedback และ LLM
ต้องเปิด Backend

## 11. ตั้งบัญชี Admin สำหรับทดสอบ

สมัครบัญชีผ่านหน้า Register ก่อน ทุกบัญชีใหม่จะเป็น `user` จากนั้นเปิด phpMyAdmin,
เลือกฐานข้อมูล และรัน:

```sql
UPDATE `Users`
SET `Role` = 'admin'
WHERE `NormalizedEmail` = LOWER(TRIM('name@example.com'));
```

Logout และ Login ใหม่เพื่อให้ session รับ Role ล่าสุด ห้ามแก้หรือพยายามถอดรหัส
`PasswordHash`; ระบบใช้ Argon2 และไม่เก็บรหัสผ่านจริง

## 12. จุดแก้โค้ดหลัก

| ต้องการแก้ | ไฟล์/โฟลเดอร์ |
|---|---|
| หน้า React | `web-app/src/pages/` |
| Component React | `web-app/src/components/` |
| CSS ของ Web App | `web-app/src/react.css` |
| API/Authentication | `backend/app.py`, `backend/auth_router.py` |
| Database connection | `backend/database.py`, `.env` |
| Database schema | `database/mysql/migrations/` |
| Feature ของโมเดล | `backend/feature_extractor.py` |
| ฝึกโมเดล | `backend/train_model.py` |
| Rule-based ของเว็บ | `web-app/analyzer.js` |
| Rule-based ของ Extension | `extension/analyzer.js` |
| Popup Extension | `extension/popup.*` |
| Service worker/navigation | `extension/background.js` |
| Content scanning | `extension/content.js` |

เมื่อแก้ analyzer ต้องตรวจทั้ง Web App และ Extension เพราะทำงานคนละ runtime

## 13. ตรวจงานก่อน Commit

ตรวจทั้งโปรเจกต์:

```bash
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./scripts/validate_project.ps1
```

ทดสอบโมเดล:

```bash
./.venv/Scripts/python.exe ./scripts/test_risk_pipeline.py
```

ทดสอบการ Build ของ React:

```bash
cd web-app
npm run build
cd ..
```

ดูไฟล์ที่เปลี่ยนก่อน commit:

```bash
git status
git diff
```

## 14. Workflow Git สำหรับผู้พัฒนา

อย่าพัฒนางานใหม่ทับ branch หลักโดยตรง ให้สร้าง branch ของงาน:

```bash
git switch codex/fixed-formula-40-60
git pull --ff-only origin codex/fixed-formula-40-60
git switch -c dev/ชื่อฟีเจอร์
```

หลังแก้และตรวจผ่าน:

```bash
git status
git add -- path/ไฟล์ที่แก้
git commit -m "อธิบายสิ่งที่แก้แบบสั้นและชัดเจน"
git push -u origin dev/ชื่อฟีเจอร์
```

จากนั้นเปิด Pull Request บน GitHub เข้า `codex/fixed-formula-40-60`

ห้าม commit ไฟล์เหล่านี้:

- `.env`
- `.venv/`
- `web-app/node_modules/`
- `backend/data/cache/`
- `backend/data/training_urls.csv`
- log, temporary file หรือข้อมูลบัญชีจริง

## 15. ปัญหาที่พบบ่อย

### `.venv/Scripts/python.exe: No such file or directory`

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
```

### `ModuleNotFoundError`

ตรวจว่าใช้ Python ใน `.venv` และติดตั้ง requirements แล้ว ห้ามเปิดด้วย Python คนละตัว

### Login แจ้งว่า Database ไม่พร้อม

1. Start MySQL ใน XAMPP
2. ตรวจชื่อฐานข้อมูลและรหัสผ่านใน `.env`
3. รัน `./migrate-db.sh`
4. ตรวจ `http://127.0.0.1:8765/health`

### หน้าเว็บขึ้น `Failed to fetch` หรือ Backend ยังไม่เปิด

เปิด `./start-backend.sh` และตรวจ `/health` หากแก้ `web-app/.env` ต้องหยุดและเปิด
Vite ใหม่

### `ERR_CONNECTION_REFUSED` ที่พอร์ต 5505

Web App ยังไม่เปิด ให้ใช้ `./start-web.sh` หรือ `./start-demo.sh`

### พอร์ต 8765 ถูกใช้อยู่

อาจมี Backend เปิดซ้ำ ให้กลับไปหน้าต่างเดิมแล้วกด `Ctrl+C` จากนั้นเปิดใหม่เพียงหนึ่งชุด

### Ollama แจ้ง `Only one usage of each socket address`

Ollama เปิดอยู่แล้ว ไม่ต้องรัน `ollama serve` ซ้ำ ใช้ `ollama list` ตรวจแทน

### Chrome แจ้ง `Manifest file is missing or unreadable`

ตอน Load unpacked ให้เลือก `extension/` ซึ่งมี `manifest.json` อยู่ภายใน

### แก้ Extension แล้วหน้าเดิมไม่เปลี่ยน

กด Reload ใน `chrome://extensions/` แล้ว Refresh tab ที่ทดสอบ หากหน้า Errors แสดง
รายการเก่าให้กด `Clear all` ก่อนทดสอบใหม่

## 16. Quick Start หลังติดตั้งครั้งแรกเสร็จแล้ว

ทุกวันให้ทำเพียง:

1. Start MySQL ใน XAMPP
2. ตรวจว่า Ollama เปิดอยู่ หากต้องการ LLM
3. เปิด Git Bash ในโฟลเดอร์โปรเจกต์
4. รัน:

```bash
git pull --ff-only
./start-demo.sh
```

5. เปิด `http://127.0.0.1:5505/#/login`

ถ้ามีปัญหา ให้เริ่มตรวจตามลำดับ `MySQL -> .env -> Backend /health -> Web App -> Extension`
