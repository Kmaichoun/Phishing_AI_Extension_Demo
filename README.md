# Phish Radar AI Extension Demo v2.0

โปรเจกต์สาธิต Chrome Extension สำหรับตรวจจับความเสี่ยงจาก phishing ก่อนผู้ใช้เปิดลิงก์หรือกรอกข้อมูลสำคัญ โดยรวม rule-based scoring, โมเดล ML แบบ local, คำอธิบายจาก LLM, QR scanner, privacy mode และ web dashboard

> โปรเจกต์นี้ใช้เพื่อการศึกษาและการสาธิต ไม่ควรใช้แทนระบบ threat intelligence ระดับ production

## โครงสร้างโปรเจกต์

    .
    ├── manifest.json             # จุดเริ่มต้นของ Chrome Extension
    ├── analyzer.js               # เครื่องมือวิเคราะห์ URL สำหรับ extension
    ├── background.js             # service worker และ navigation protection
    ├── content.js / content.css  # ตรวจหน้าเว็บ ลิงก์ และแบบฟอร์ม
    ├── popup.*                   # หน้าควบคุมของ extension
    ├── warning.*                 # หน้าเตือนและ feedback
    ├── qr-scanner.*              # เครื่องมือตรวจ QR
    ├── safe-preview.*            # โหมดเปิดหน้าเสี่ยงแบบจำกัด
    ├── icons/                    # ไอคอน extension
    ├── backend/                  # FastAPI, Login/Session, ML model และ LLM integration
    │   └── data/                 # seed dataset และ feedback ที่เกิดระหว่างใช้งาน
    ├── database/                 # MySQL/MariaDB schema และ migration scripts
    ├── web-app/                  # React Web App + Vite
    ├── docs/                     # คู่มือ บันทึกการนำเสนอ และประวัติการพัฒนา
    └── scripts/                  # เครื่องมือตรวจความสมบูรณ์ของโปรเจกต์

## เริ่มใช้งาน Extension

1. เปิด chrome://extensions/
2. เปิด **Developer mode**
3. กด **Load unpacked**
4. เลือกโฟลเดอร์รากของโปรเจกต์นี้
5. เมื่อแก้โค้ด ให้กด **Reload** ที่หน้า Extensions

Extension ทำงานแบบ rule-based ได้โดยไม่ต้องเปิด backend ส่วน ML, LLM และการบันทึก feedback ไปยังไฟล์ต้องเปิด backend เพิ่ม

### Domain ของ Web App

Domain สำหรับพัฒนาในเครื่องคือ:

    http://app.phishradar.localhost:5505/#/login

Chrome และเบราว์เซอร์สมัยใหม่ควรเปิดชื่อนี้ได้โดยตรงหลังเริ่มระบบ หากเครื่องมือบน Windows หา Domain ไม่พบ ให้ตั้งค่า hosts ครั้งเดียวด้วย PowerShell แบบ **Run as administrator**:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_local_domain.ps1

จากนั้น Reload Extension ที่ `chrome://extensions/` ระบบจะแสดง badge `APP` และจะไม่ส่ง Domain ของ Web App เองเข้าหน้า Warning โดยยังตรวจลิงก์ภายนอกที่เปิดจาก Web App ตามปกติ รายละเอียดและขั้นตอนสำหรับ Domain จริงอยู่ใน [คู่มือ Local Domain](docs/LOCAL_DOMAIN_TH.md)

## เริ่ม Backend

เปิด Git Bash ที่โฟลเดอร์หลักของโปรเจกต์ โปรเจกต์ใช้ virtual environment ชื่อ `.venv` เพื่อแยก dependency ออกจาก Python ของเครื่อง:

    ./.venv/Scripts/python.exe -m pip install -r ./backend/requirements.txt
    ./migrate-db.sh
    ./start-backend.sh

หรือเปิด Backend และ Web App พร้อมกันในหน้าต่างเดียว:

    ./start-demo.sh

ให้เปิด Git Bash ค้างไว้ระหว่างใช้งาน กด `Ctrl+C` เพื่อหยุดระบบ

ก่อนเปิดระบบสมาชิก ให้ใส่ข้อมูล MySQL/MariaDB ใน `.env` แล้วรัน:

    cp .env.example .env
    ./migrate-db.sh

หากใช้ phpMyAdmin ให้เลือกฐานข้อมูล `ip_std6730202581` แล้วรันไฟล์ใน
`database/mysql/migrations/` ตามลำดับ รายละเอียดอยู่ใน
[คู่มือฐานข้อมูล MySQL/MariaDB](database/mysql/README_TH.md)

รายละเอียดการตั้งค่า LLM อยู่ที่ [docs/LLM_SETUP_TH.md](docs/LLM_SETUP_TH.md)

LLM เริ่มต้นคือ `qwen3:4b` ผ่าน Ollama ส่วน Popup มีสวิตช์ **สแกนหน้าเว็บอัตโนมัติ** สำหรับพักหรือเปิดการตรวจการนำทาง ลิงก์ ฟอร์ม และ Clipboard ได้ทันที

## สร้าง Dataset และฝึก Risk Model

ค่าเริ่มต้นจะสร้างข้อมูลสมดุล 10,000 แถวจาก PhishTank, OpenPhish และ Tranco แล้วคำนวณ RuleScore ด้วย analyzer ของ Web App:

    ./.venv/Scripts/python.exe ./backend/build_dataset.py --refresh
    ./.venv/Scripts/python.exe ./backend/train_model.py
    ./.venv/Scripts/python.exe ./scripts/test_risk_pipeline.py

ตัวฝึกใช้ L1-regularized Logistic Regression สร้าง `MLScore = 100 × sigmoid(w·x+b)` แล้วคำนวณ `FinalScore = 0.40(RuleScore) + 0.60(MLScore)` โดยแบ่งข้อมูลแบบ Stratified Group ตาม hostname กัน grouped holdout ออกจากการเลือกโมเดล และเลือก warning/blocking threshold บน FinalScore ภายใต้เพดาน FPR พร้อม one-sided Wilson upper bound 95% ผลเต็มอยู่ที่ `backend/data/risk_model_evaluation.json` และคำอธิบายวิธีทดลองอยู่ที่ [docs/RISK_MODEL_METHODOLOGY_TH.md](docs/RISK_MODEL_METHODOLOGY_TH.md)

## เริ่ม Web App

Web App ใช้ React สำหรับเว็บ, hash routing และ Vite (ไม่ใช่ React Native/Expo)
ครั้งแรกให้ติดตั้ง dependency:

    cd web-app
    npm install
    cd ..

เปิดเฉพาะ web app:

    ./start-web.sh

เปิดทั้ง backend และ web app:

    ./start-demo.sh

หน้า Login เปิดที่ http://app.phishradar.localhost:5505/#/login และ backend ใช้ http://api.phishradar.localhost:8765/ โดย URL แบบ `127.0.0.1` ยังใช้เป็น fallback ได้

สร้างไฟล์สำหรับนำขึ้น Hosting ด้วย:

    cd web-app
    npm run build

ผลลัพธ์อยู่ที่ `web-app/dist/` ห้ามแก้ไฟล์ใน `dist/` ด้วยมือ รายละเอียดโครงสร้าง
Component, Router, Context และสิ่งที่ต้องรู้เมื่อพัฒนาต่ออยู่ใน
[คู่มือ React Web App](docs/REACT_WEB_APP_TH.md)

บัญชีใหม่มี Role เป็น `user` เสมอ ทั้ง User และ Admin เข้าสู่ระบบจากหน้าเดียวกัน หากต้องการตั้งบัญชีแรกเป็น Admin ให้สมัครผ่านหน้า Register ก่อน แล้วใช้คำสั่งเลื่อนสิทธิ์ใน [คู่มือฐานข้อมูล](database/mysql/README_TH.md) ห้ามเก็บหรือ INSERT รหัสผ่านจริงลง MySQL/MariaDB

ระบบเก็บรหัสผ่านด้วย Argon2, เก็บ session/device token เฉพาะค่า hash ใน MySQL/MariaDB และส่ง session ให้เบราว์เซอร์ด้วยคุกกี้ HttpOnly โดยไม่เก็บ password หรือ session secret ใน localStorage

ทดสอบวงจรระบบบัญชีด้วยบัญชีชั่วคราว (สคริปต์ล้างข้อมูลทดสอบให้อัตโนมัติ):

    ./.venv/Scripts/python.exe ./scripts/test_auth_flow.py
    ./.venv/Scripts/python.exe ./scripts/test_history_flow.py

## ตรวจโปรเจกต์ก่อนพัฒนาต่อ

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./scripts/validate_project.ps1

สคริปต์จะตรวจ JSON, path ที่ประกาศใน manifest, resource ของ HTML, JavaScript/Python syntax, smoke test ของ analyzer ทั้งสอง runtime และ artifact ที่ไม่ควรหลงเหลือในโฟลเดอร์หลัก

## ทำความสะอาดพื้นที่

ลบเฉพาะไฟล์ที่สร้างใหม่ได้ เช่น `tmp/`, `__pycache__/`, `.pytest_cache/` และไฟล์ตรวจงานนำเสนอ โดยไม่ลบโมเดล ฐานข้อมูล feedback, PDF/PPTX หรือ virtual environment:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./scripts/clean_project.ps1

หากต้องการคืนพื้นที่จาก `.venv` เพิ่ม ให้ใช้ตัวเลือกด้านล่าง หลังลบแล้วต้องสร้าง `.venv` และติดตั้ง `backend/requirements.txt` ใหม่ก่อนเปิด Backend:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./scripts/clean_project.ps1 -IncludeVenv

หากต้องการคืนพื้นที่จาก React dependencies ด้วย ให้เพิ่ม `-IncludeNodeModules`
จากนั้นต้องรัน `npm install` ใน `web-app/` ก่อนเปิดเว็บอีกครั้ง:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./scripts/clean_project.ps1 -IncludeNodeModules

`.venv` และไฟล์ชั่วคราวถูกกันออกจาก Git อยู่แล้ว จึงไม่เพิ่มขนาด Repository บน GitHub ส่วน `backend/model.pkl` ถูกบีบอัดด้วย LZMA แต่ยังโหลดด้วย `joblib.load()` ได้ตามเดิม

## แนวทางรักษาโครงสร้าง

- เก็บโค้ดที่ Chrome โหลดโดยตรงไว้ที่ root และอย่าย้ายโดยไม่แก้ manifest.json
- เก็บเอกสารทั้งหมดไว้ใต้ docs/; ให้ root เหลือเฉพาะ README และไฟล์ runtime
- เก็บข้อมูล backend ใต้ backend/data/; feedback.csv เป็นข้อมูล runtime และถูก ignore จาก Git
- เก็บ feed และ training_urls.csv ไว้เฉพาะเครื่อง; บันทึก manifest และผลประเมินเพื่อทำซ้ำการทดลอง
- อย่าสร้างโฟลเดอร์ backup-* ในโปรเจกต์ ให้ใช้ Git commit หรือ branch แทน
- analyzer.js ที่ root และ web-app/analyzer.js เป็นคนละ runtime เมื่อแก้ logic ควรตรวจทั้งสองชุด
- Web App เป็น React/Vite ส่วน Chrome Extension ยังเป็น Manifest V3 + JavaScript แยกกัน
- แก้ React source ใน web-app/src/ และให้ `npm run build` สร้าง dist/
- รัน validation ทุกครั้งก่อน package หรือส่งต่อโปรเจกต์

## เอกสารเพิ่มเติม

- [ดัชนีเอกสาร](docs/README.md)
- [ฐานข้อมูลสมาชิก MySQL/MariaDB](database/mysql/README_TH.md)
- [โครงสร้าง React Web App](docs/REACT_WEB_APP_TH.md)
- [วิธีสร้างและประเมิน Risk Model](docs/RISK_MODEL_METHODOLOGY_TH.md)
- [สคริปต์นำเสนอ](docs/PRESENTATION_NOTES_TH.md)
- [ประวัติการพัฒนาเดิม](docs/PROJECT_HISTORY_TH.md)
