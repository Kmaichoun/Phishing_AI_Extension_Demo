# คู่มือติดตั้งและสาธิต Phish Radar AI

สำหรับ source บน branch **`submission/latest-project-20261029`** จัดทำวันที่ **29 ตุลาคม 2569** ตัวอย่างคำสั่งใช้ Windows PowerShell โดยเริ่มจาก repository root ยกเว้นจุดที่ระบุให้เปลี่ยนโฟลเดอร์ คำสั่งในเอกสารเป็นขั้นตอนสำหรับผู้เตรียมเครื่องสาธิต ผลที่ตรวจจริงในรอบจัดทำชุดส่งแยกไว้ใน [VERIFICATION_TH.md](VERIFICATION_TH.md)

## 1. เลือกระดับการสาธิตก่อนติดตั้ง

| ระดับ | สิ่งที่ทำได้ | สิ่งที่ต้องมีเพิ่ม |
| --- | --- | --- |
| อ่าน source และหลักฐาน | อธิบาย architecture, สูตร, schema, policy, dataset provenance และผลประเมินที่บันทึกไว้ | Git/Python สำหรับ inspector; ไม่ต้องเปิด DB หรือโหลดโมเดล |
| เปิด Web/API และแสดงสถานะ | เปิด UI, เรียก `/health`, แสดงสถานะโมเดลไม่พร้อมหรือ fallback | Python dependencies, Node dependencies และการตั้งค่า local; หน้าสมาชิกยังต้องมี DB |
| บัญชี ประวัติ Feedback และ Admin | สมัคร/เข้าสู่ระบบ บันทึกประวัติ จัดการ Session และ Feedback | MySQL/MariaDB พร้อม schema ของ source รุ่นนี้ และบัญชีทดสอบ |
| RF ตรงกับรายงาน | แสดงคะแนน RF/calibration และ metadata ของรุ่นที่อ้าง | model binary, reference registry และ demo authorization ที่ตรงกันจากเจ้าของโครงงาน |
| คำอธิบายจาก LLM | ขอ `/explain` ตาม provider ที่ตั้งค่า; แชตสมาชิกใช้ Ollama ใน source รุ่นนี้ | Ollama พร้อมโมเดลที่ตั้งค่า; `/explain` อาจใช้ provider ทางเลือกได้ ต้องตรวจ readiness จริง |
| Extension ครบเส้นทาง | ตรวจการเรียก API หน้าเตือน privacy และ DOM ตาม browser ที่ใช้ | Extension ที่ตั้งปลายทางถูกต้อง, backend พร้อมตามโหมด และการ reload หลังแก้ source |

GitHub ไม่แนบ model binary, raw datasets, `.env`, `backend/reference-origin-v1.json` ต้นฉบับ และ `backend/model-demo-authorization.json` การ clone อย่างเดียวจึงไม่ทำให้ RF รุ่นในรายงานพร้อมใช้งาน ให้ขอ artifact จากเจ้าของโครงงานผ่านช่องทางส่วนตัวที่เหมาะสมและตรวจ hash ก่อนนำมาใช้

## 2. เครื่องมือและ dependencies

| เครื่องมือ | ฐานที่ใช้กำหนด |
| --- | --- |
| Git | ใช้ clone branch และตรวจสถานะไฟล์ |
| Python | ใช้ Python ที่รองรับแพ็กเกจใน [requirements.txt](../../backend/requirements.txt); สำเนา local ที่ใช้ตรวจชุดส่งมี Python 3.11 ไม่ได้กำหนดว่าต้องเป็น 3.12 เท่านั้น |
| Node.js / npm | [package-lock.json](../../web-app/package-lock.json) ของ Vite ระบุ engine `^20.19.0 || >=22.12.0`; เลือกรุ่นที่อยู่ในช่วงนี้ |
| MySQL หรือ MariaDB | ใช้เมื่อต้องสาธิตระบบบัญชี/history/workspace; พอร์ตตัวอย่าง 3306 |
| Chrome ที่รองรับ Manifest V3 | ใช้ Load unpacked สำหรับ Extension; บาง API เช่น `BarcodeDetector` ขึ้นกับ browser |
| Ollama | ตัวเลือกสำหรับคำอธิบาย local; template ระบุ `qwen3:4b` และพอร์ต default 11434 ให้ตรวจรุ่นที่ติดตั้งจริง |

Backend ระบุ FastAPI 0.111.0, Uvicorn 0.30.1, scikit-learn 1.5.0, joblib 1.4.2, SQLAlchemy 2.0.41, PyMySQL 1.1.1 และ dependencies ที่เหลือในไฟล์ requirements ส่วน Web ใช้ React 19 และ Vite 7 ตาม package/lockfile อย่าเปลี่ยนเวอร์ชันชุด dependency แล้วถือว่าเป็นสภาพแวดล้อมเดิมโดยไม่ทดสอบ

การอ่านเอกสารไม่จำเป็นต้องติดตั้ง training dependencies และไม่ต้องรัน training, collector หรือ model promotion

## 3. Clone และตรวจสำเนา

```powershell
git clone --branch submission/latest-project-20261029 --single-branch https://github.com/Kmaichoun/Phishing_AI_Extension_Demo.git
Set-Location Phishing_AI_Extension_Demo
git branch --show-current
python scripts/inspect_project_context.py --json --verify-snapshot
```

อ่าน `diagnostics`, รายการไฟล์ขาด และผล archive hash ใน JSON ด้วย exit code 0 ของ inventory หมายถึงสคริปต์ทำงานจบ ไม่ได้ยืนยันว่า application, DB, LLM หรือ model พร้อม

อ่าน source หลักจาก `backend/`, `web-app/`, `extension/` ของ branch ชุดส่งนี้ได้โดยตรง หากต้องการตรวจสำเนา archive แยก ให้แตกไปตำแหน่งอ่านอย่างเดียวที่ยังไม่มีไฟล์เดิม และไม่แตกทับ repository root

```powershell
python -m zipfile -e docs/ai/current-source.zip .ai-context/current-source
```

## 4. เตรียม Python และ Web

จาก repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

คำสั่งใช้ executable ของ virtual environment โดยตรง จึงไม่จำเป็นต้องเปลี่ยน PowerShell execution policy เพื่อ activate environment หาก `python` ไม่ทำงาน ให้เปลี่ยนเป็น path ของ Python ที่ติดตั้งจริงก่อนสร้าง `.venv`

ติดตั้งและ build Web ด้วย lockfile:

```powershell
Set-Location web-app
npm ci
npm run build
Set-Location ..
```

ผล build อยู่ใน `web-app/dist/` การ build สำเร็จตรวจการรวม source/resources ของ Web แต่ไม่ยืนยันว่า API, login หรือ RF ทำงานจริง

## 5. ตั้งค่า environment สำหรับเครื่องสาธิต

สร้าง `.env` จากแม่แบบเพียงครั้งแรก หากมีไฟล์เดิมอยู่ให้แก้ค่าที่จำเป็นในไฟล์เดิม ไม่เขียนทับโดยไม่ตรวจ:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

ตัวอย่างสำหรับ local demo ด้านล่างเป็นค่าตัวอย่าง ให้ใส่ชื่อฐานข้อมูลและบัญชีของเครื่องตนเอง ห้าม commit รหัสผ่านจริง

```dotenv
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=phish_radar_demo
MYSQL_USER=your_local_database_user
MYSQL_PASSWORD=your_local_database_password
MYSQL_CHARSET=utf8mb4

AUTH_SESSION_HOURS=168
AUTH_COOKIE_SECURE=false
AUTH_WEB_ORIGINS=http://127.0.0.1:5505,http://localhost:5505,http://app.phishradar.localhost:5505
SEARCH_HISTORY_RETENTION_DAYS=90

LLM_PROVIDER=ollama
OLLAMA_MODEL=qwen3:4b
OLLAMA_BASE_URL=http://127.0.0.1:11434
```

ประเด็นที่ต้องให้ตรงกัน:

- `MYSQL_DATABASE` ต้องตรงกับฐานข้อมูลที่เลือก/สร้างจริง ค่าใน `.env.example` เป็นชื่อเดิมของเครื่องต้นทาง ไม่จำเป็นต้องใช้ชื่อนั้นบนเครื่องใหม่
- ถ้ากำหนด `DATABASE_URL` ไว้ จะใช้ค่านั้นแทนชุด `MYSQL_*`; อย่าปล่อย URL เดิมให้ชี้ฐานข้อมูลผิดเครื่อง
- [database.py](../../backend/database.py) อ่าน `.env` ที่ root แล้วอ่าน `backend/.env` และใช้ environment ของ process ตามพฤติกรรม `load_dotenv`; ตรวจไฟล์/ตัวแปรที่มีอยู่ในเครื่องใหม่หากแก้ค่าแล้วไม่เปลี่ยน
- ใช้ hostname เดียวกันให้สม่ำเสมอ เช่น Web `127.0.0.1:5505` และ API `127.0.0.1:8765` เพื่อให้ cookie/origin ของการสาธิตตรวจตามได้ง่าย
- `AUTH_COOKIE_SECURE=false` ใช้กับ local HTTP ตัวอย่างนี้ ส่วนการเปิดบริการจริงผ่าน HTTPS ต้องตั้ง cookie/origin ให้ตรงสภาพแวดล้อมและทดสอบใหม่
- เปิด LLM provider ภายนอกเมื่อผู้สาธิตตั้งใจใช้และมีสิทธิ์เท่านั้น ค่า API key ต้องอยู่ใน environment ส่วนตัว

Web มี [web-app/.env.example](../../web-app/.env.example) และ [runtime.js](../../web-app/src/services/runtime.js) ถ้าเปิด Web ที่ `http://127.0.0.1:5505` จะเลือก backend `http://127.0.0.1:8765` ตามค่า development mapping; หากต้องกำหนดเองให้สร้าง `web-app/.env.local`:

```dotenv
VITE_API_BASE=http://127.0.0.1:8765
```

ค่า `VITE_*` เข้าไปใน client build ได้ จึงห้ามใช้เก็บรหัสผ่านหรือ secret เปลี่ยนค่านี้แล้ว restart Vite หรือ build ใหม่ให้ตรงวิธีเปิด Web

## 6. เตรียม MySQL/MariaDB ให้ตรง schema

เปิด MySQL/MariaDB ก่อน ถ้าใช้ XAMPP ให้ Start MySQL ใน Control Panel จากนั้นเลือกฐานข้อมูลทดสอบว่างใน phpMyAdmin และ Import [phish_radar_phpmyadmin_import.sql](../../database/mysql/phish_radar_phpmyadmin_import.sql)

ไฟล์ Import ไม่สร้างหรือเลือกฐานข้อมูลให้โดยอัตโนมัติ ต้องเลือกฐานข้อมูลปลายทางให้ถูกก่อน ควรได้ 5 ตาราง:

| ตาราง | หน้าที่ |
| --- | --- |
| `Users` | บัญชี password hash และ role |
| `Sessions` | Session ฝั่ง server และ token hash |
| `SearchHistory` | ประวัติผลตรวจและ audit ของโมเดล |
| `ScanFeedback` | Feedback ของสมาชิกและสถานะทบทวน |
| `AuditEvents` | การทำรายการที่ต้องตรวจย้อนกลับ |

source รุ่นนี้ไม่มี active `UserDevices` workflow แล้ว ถ้าใช้ฐานข้อมูลเก่าต้องสำรองและอ่าน [คู่มือฐานข้อมูล](../../database/mysql/README_TH.md) ก่อนใช้ [007_remove_user_devices.sql](../../database/mysql/upgrades/007_remove_user_devices.sql) เพราะอัปเกรดนี้ลบ schema/บันทึกส่วนอุปกรณ์ การ Import ไฟล์สร้างตารางที่ใช้ `IF NOT EXISTS` ไม่ได้อัปเกรดตารางเก่าให้ตรงรุ่น

ทางเลือกสำหรับ **ฐานข้อมูลสาธิตที่เลือกไว้แล้วและตรวจไฟล์ migration แล้ว** คือรันจาก root:

```powershell
.\.venv\Scripts\python.exe scripts/apply_database_migrations.py
```

คำสั่งนี้แก้ไขฐานข้อมูลและรันทั้ง migrations กับ upgrades ไม่ใช่คำสั่งตรวจแบบอ่านอย่างเดียว จึงใช้เมื่อผู้เตรียมเครื่องตั้งใจติดตั้ง/อัปเกรดฐานข้อมูลนั้นเท่านั้น

ไฟล์ SQL ไม่แนบบัญชีตัวอย่าง ให้สมัครบัญชีผ่าน Web หากต้องสาธิต Admin ให้กำหนด role ของบัญชีทดสอบตามคู่มือ DB และใช้บัญชีแยกจากข้อมูลจริง

## 7. เตรียม artifact ก่อนอ้างว่าเป็น RF รุ่นรายงาน

ต้องมีอย่างน้อย 3 ส่วนที่สอดคล้องกัน:

1. `backend/model.pkl` จากแหล่งที่เชื่อถือได้ และ hash ตรงกับหลักฐานของรายงาน
2. `backend/reference-origin-v1.json` ต้นฉบับที่ hash ตรงกับ `reference_origin_registry_sha256` ของ model bundle
3. `backend/model-demo-authorization.json` ที่เจ้าของอนุญาตไว้สำหรับ artifact นั้น เนื่องจากโมเดลมี `production_ready=false`

ทั้งสามส่วนนี้ไม่ได้เผยแพร่ใน branch ชุดส่ง ไม่ควรนำ pickle คนละรุ่นมาวางแทน เปลี่ยนค่า readiness ให้ดูพร้อม หรือสร้าง registry/authorization แล้วอ้างว่าเป็นต้นฉบับที่ใช้ในผลเดิม ดูเงื่อนไขจริงที่ [app.py](../../backend/app.py) และ [demo_model.py](../../backend/demo_model.py)

ตรวจ hash โดยไม่ deserialize:

```powershell
Get-FileHash -LiteralPath backend/model.pkl -Algorithm SHA256
python scripts/inspect_project_context.py --json --hash-model
```

ค่าที่คาดสำหรับโมเดลในรายงาน:

```text
bc4e024e32aaf0ad695ea4a4dff552ece09d606c4963a49e8bf6aa8a447575bb
```

Hash ตรงยืนยันตัวไฟล์ที่เทียบ ไม่ได้ยืนยันว่าระบบที่เปิดอยู่โหลดไฟล์นั้นหรือผ่านการทดสอบ HTTP แล้ว หลังเตรียมครบต้องตรวจ `/health` และ prediction จริงเพิ่มเติม

กรณีไม่แนบ model ให้แสดง `model_ready=false` และสถานะ fallback ตามจริง ห้ามใช้คะแนน local evidence แทนผล RF ในตารางทดลอง

## 8. เปิด Backend และ Web

Terminal ที่หนึ่ง จาก root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8765
```

Terminal ที่สอง:

```powershell
Set-Location web-app
npm run dev
```

เปิด Web ที่ `http://127.0.0.1:5505/#/login` และ API docs ที่ `http://127.0.0.1:8765/docs` สำหรับเครื่อง local ของผู้สาธิต ให้เปิดหน้าต่างบริการทั้งสองไว้ระหว่างสาธิต

ตรวจสถานะจาก PowerShell อีกหน้าต่าง:

```powershell
$health = Invoke-RestMethod -Uri http://127.0.0.1:8765/health
$health | ConvertTo-Json -Depth 12
```

| Field ที่ต้องอ่าน | ความหมาย |
| --- | --- |
| `ok` | API ตอบ health สำเร็จตาม code path นี้ |
| `model_ready` | backend พบและโหลด model bundle ได้หรือไม่ |
| `model_policy` | รุ่น schema threshold fusion method และ readiness ของ artifact ที่โหลด |
| `database.connected` | เชื่อม DB ได้หรือไม่ |
| `database.auth_schema_ready`, `history_schema_ready`, `risk_audit_schema_ready`, `workspace_schema_ready` | ตาราง/คอลัมน์ที่ระบบตรวจตรงตามความต้องการหรือไม่ |
| `llm` | provider/model และเหตุผลของ readiness ตามที่ backend ตรวจได้ |

HTTP 200 และ `ok=true` ไม่ได้แปลว่าทุกส่วนพร้อม หาก model/registry/authorization ไม่เข้าคู่กันให้แก้ที่ artifact ที่ขาดหรือไม่ตรง ห้ามปิดการตรวจความตรงกันเพียงเพื่อให้ demo ผ่าน

ทดสอบ prediction ด้วย URL ปกติที่ไม่มีข้อมูลส่วนตัว ตัวอย่างนี้ส่ง URL เป็นข้อความให้ backend วิเคราะห์ ไม่ใช่คำสั่งเปิด URL ปลายทาง:

```powershell
$body = @{ url = 'https://example.com/' } | ConvertTo-Json
$result = Invoke-RestMethod -Uri http://127.0.0.1:8765/predict -Method Post -ContentType 'application/json' -Body $body
$result | ConvertTo-Json -Depth 12
```

อ่าน `model_status`, `risk_score`, `decision`, model version/schema และ threshold จากผลจริง ไม่กำหนดล่วงหน้าว่า URL ตัวอย่างต้องได้คะแนนใด ผลต่ำกว่าเกณฑ์ไม่ใช่การรับรองความปลอดภัย

## 9. เปิดคำอธิบายจาก Ollama เมื่อจะสาธิต LLM

ตรวจว่า Ollama ให้บริการและมี model tag ตรงกับ `OLLAMA_MODEL` เช่นใช้ `ollama list` ดูรายการที่ติดตั้ง ค่า template คือ `qwen3:4b` แต่เครื่องต้นทางหรือเครื่องใหม่อาจมี tag อื่น อย่าอ้าง tag จาก template ว่าเป็นรุ่นที่กำลังทำงาน

หากยังไม่มี model ต้องจัดเตรียมตามทรัพยากรของเครื่องก่อนวันสาธิต เมื่อแก้ `.env` ให้ restart backend แล้วตรวจ `llm` ใน `/health` จากนั้นขอคำอธิบายผ่าน UI และตรวจว่าคะแนน/decision เดิมไม่เปลี่ยน

ถ้า Ollama หรือ provider ไม่พร้อม ระบบอาจตอบคำอธิบายสำรอง ต้องระบุว่าเป็น fallback ตัวอักษรคำอธิบายที่ปรากฏเพียงอย่างเดียวไม่ยืนยันว่า LLM สร้างคำตอบแล้ว เส้นทาง `/chat` ต้องเข้าสู่ระบบสมาชิกและใช้ Ollama ตาม source รุ่นนี้ ส่วน `/explain` รองรับ provider ตามการตั้งค่า

## 10. ติดตั้งและตั้งปลายทาง Extension

ก่อนโหลด ให้ตรวจ [extension/app-trust.js](../../extension/app-trust.js) สำเนา source อาจมี public demo origin จากการตั้งค่าในเครื่องต้นทาง ซึ่งไม่รับประกันว่ายังเปิดใช้งาน และจะมีลำดับเหนือ local API เมื่อค่าดังกล่าวไม่ว่าง

สำหรับ local demo บนเครื่องตนเอง ตั้งค่าที่สำเนา local ให้ปลายทางชัดเจน:

```javascript
const PUBLIC_WEB_APP_ORIGIN = '';
const DEFAULT_WEB_APP_URL = 'http://127.0.0.1:5505/#/login';
```

คงการคำนวณ `API_BASE_URL = PUBLIC_WEB_APP_ORIGIN || 'http://127.0.0.1:8765'` และรายการ trusted local origins ตาม source ไว้ การแก้ค่านี้เป็น local configuration ทำให้ hash ของไฟล์ local ต่างจากสำเนาเผยแพร่ได้ จึงควรบันทึกค่า configuration ที่ใช้ในการสาธิต

`scripts/configure_public_demo.py` รองรับการกำหนด HTTPS origin และเขียนการตั้งค่า/public package สำหรับ demo ไม่ใช่คำสั่งตั้ง local แบบอัตโนมัติ และการใช้ script ดังกล่าวไม่ได้เปิดบริการ hosting ให้เอง

จากนั้น:

1. เปิด `chrome://extensions` และเปิด Developer mode
2. เลือก Load unpacked แล้วเลือกโฟลเดอร์ `extension/` ของ branch ชุดส่ง
3. ตรวจชื่อ Phish Radar AI และเวอร์ชัน 2.4.10 ตาม manifest
4. ปิดหรือเอา Extension สำเนาเก่าที่ชนกันออกจาก browser profile สาธิต
5. หลังแก้ source/configuration กด Reload ที่ Extension และ reload แท็บเว็บที่ใช้ทดสอบ
6. ตรวจ Service worker/Console และ Network ว่า `/predict` ไปปลายทาง local ที่เลือกจริง

Extension ขอสิทธิ์ host, tabs, storage, navigation, scripting และ clipboard ตาม manifest; การใช้ไฟล์ local ต้องเปิดสิทธิ์ file URLs ใน Chrome เพิ่มเมื่อจำเป็น บางหน้า เช่น `chrome://` อยู่ภายใต้ข้อจำกัดของ browser และ content script ใช้งานเหมือนหน้าเว็บทั่วไปไม่ได้

ทดลอง Privacy Mode แยกจากโหมด backend: เปิดสวิตช์ วิเคราะห์ URL แล้วดูสถานะ local/privacy และตรวจ network ของ action นั้นว่าไม่ส่ง URL ไป backend/LLM ผลนี้เป็น local rules/visual evidence ไม่ใช่ RF prediction

## 11. ลำดับสาธิตต่ออาจารย์

| ลำดับ | สิ่งที่ทำ | สิ่งที่อธิบาย/หลักฐานที่แสดง |
| --- | --- | --- |
| 1 | เปิด README และแผนภาพระบบ | ปัญหา วัตถุประสงค์ Web–Extension–API–DB–LLM และข้อจำกัดต้นแบบ |
| 2 | เปิด `/health` | แยก model, DB และ LLM readiness; ถ้าไม่มี artifact ให้บอกว่าสาธิต UI/fallback |
| 3 | สมัคร/เข้าสู่ระบบด้วยบัญชีทดสอบ | Session เป็นของบัญชี ใช้ DB รุ่น 5 ตาราง |
| 4 | ตรวจ URL ปกติที่เลือกไว้ใน Web | คะแนน threshold decision schema/version และหลักฐาน URL |
| 5 | อธิบายสูตรจากเอกสาร | RF probability → calibration → ×100 และ 60/80; ตัดสินก่อนปัดเศษ |
| 6 | ขอคำอธิบาย | ระบุ provider/model/fallback และยืนยันว่าคะแนน/decision เดิมไม่เปลี่ยน |
| 7 | ดูประวัติและส่ง Feedback | ผลเก่ามี metadata ของรอบนั้น; Feedback ยังไม่ใช่การ retrain อัตโนมัติ |
| 8 | เปิด Extension กับหน้า demo ที่ควบคุมได้ | แสดง popup, ป้าย/หน้าเตือน และแยก local evidence ออกจาก backend result |
| 9 | เปิด Privacy Mode แล้ววิเคราะห์ซ้ำ | แสดงสถานะ privacy และตรวจ request ของ action ที่ทดสอบ |
| 10 | สาธิต QR หรือ DOM filtering ถ้า browser รองรับ | QR เป็นอีกทางรับ URL; filtering เปลี่ยนการแสดงผลและไม่เปลี่ยน RF score |
| 11 | เปิดตารางผลประเมินเดิม | รายงาน Recall คู่ FPR พร้อมขนาดชุด ความต่างชุดข้อมูล และสถานะไม่พร้อม production |

ใช้ URL ปกติ หน้า local หรือ fixture ที่ควบคุมได้สำหรับสาธิต ไม่ต้องเปิด phishing URL จาก dataset และไม่ควรใส่รหัสผ่านจริงในฟอร์มทดสอบ การสาธิต 59/60/79/80 ใช้ test policy/fixture เพื่อแสดง boundary ไม่แต่งผล RF ของ URL ให้ตรงตัวเลขที่ต้องการ

## 12. ปัญหาที่ตรวจได้ตามลำดับ

| อาการ | จุดตรวจ |
| --- | --- |
| `python` เปิด Microsoft Store หรือรันไม่ได้ | ใช้ path Python ที่ติดตั้งจริงหรือ executable ใน `.venv` |
| `npm ci`/Vite ไม่เริ่ม | ตรวจ Node engine ตาม lockfile แล้วติดตั้งใน `web-app/` |
| พอร์ต 5505/8765 ถูกใช้อยู่ | หาบริการที่ครองพอร์ตก่อน เปลี่ยนพอร์ตแล้วต้องเปลี่ยน API base/origins ให้ตรงกัน |
| MySQL connection refused / 10061 | ตรวจว่าบริการ MySQL เปิดอยู่ host/port ถูก และบัญชีมีสิทธิ์ก่อนตรวจ schema |
| Login ไม่สำเร็จแต่ API health เปิดได้ | ตรวจ DB schema flags, origin, cookie secure และ hostname ที่ใช้จริง |
| `model_ready=false` | ตรวจว่ามี artifact ครบและตรงรุ่น; clone ชุดส่งไม่มี binary เป็นปกติ |
| Model load ปฏิเสธ demo/registry | ตรวจ authorization/hash และ registry ต้นฉบับที่คู่กับโมเดล ห้ามข้ามเงื่อนไข |
| Extension ยังเรียกปลายทางเก่า | ตรวจ `app-trust.js`, reload Extension, reload แท็บ และดู network จริง |
| มีคำอธิบายแต่ LLM ไม่พร้อม | อ่าน status/provider ของคำตอบ อาจเป็นข้อความ fallback |
| QR อ่านไม่ได้ | ตรวจกล้อง/สิทธิ์ภาพและ `BarcodeDetector` ของ browser; ใช้ Web QR ตามความสามารถที่มี |
| บางหน้าแสดงโฆษณาอยู่ | ตรวจ DOM/setting/fixture ของ filtering โดยแยกจากผล ML |

## 13. หลักฐานที่ควรบันทึกหลังสาธิต

บันทึกวันเวลา branch/commit, model hash, Python/Node ที่ใช้, สถานะ `/health`, test case ที่ใช้ และสิ่งที่ตรวจใน browser หากเก็บภาพหน้าจอให้ตัด token, cookie, รหัสผ่าน, URL parameters ส่วนตัว และข้อมูลสมาชิกจริงออกก่อนเผยแพร่

รายงานการตรวจ source, unit/fixture, live API, browser, การเข้าถึงจากภายนอก และ model evaluation แยกกัน การเปิด Web ได้ไม่เท่ากับฝึกซ้ำสำเร็จ และผล evaluation เดิมไม่ใช่ผลของเครื่องสาธิตใหม่
