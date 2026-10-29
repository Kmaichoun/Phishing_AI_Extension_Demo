# คู่มือให้ AI รับช่วงโครงงาน Phish Radar

> ชุดส่งอาจารย์รอบ 2026-10-29: อ่าน [รายงานล่าสุด](../submission-20261029/README.md) และ [ผลตรวจ](../submission-20261029/VERIFICATION_TH.md) ประกอบ คู่มือนี้แยก branch ใหม่จาก source เก่าตามตารางด้านล่าง

ปรับปรุงสำหรับ branch ส่งอาจารย์วันที่ 29 ตุลาคม 2026 (คู่มือและหลักฐานเดิมจัดทำ 20 ตุลาคม 2026) เพื่อให้ AI บนอีกเครื่องเริ่มจากข้อมูลชุดเดียวกัน ค้นส่วนที่เกี่ยวข้องได้ และบอกสิ่งที่ยังยืนยันไม่ได้ คู่มือนี้เป็นแผนที่สำหรับอ่านโค้ดและหลักฐาน ไม่ใช่การรับรองว่า AI ได้อ่านทุกไฟล์หรือระบบพร้อมใช้งานจริง

## 1 เริ่มใช้งานบนอีกเครื่อง

ต้องเลือก branch ที่มีชุดเอกสารนี้ เพราะ default branch ของ repository อาจยังเป็นรุ่นเก่า:

```bash
git clone --branch submission/latest-project-20261029 --single-branch https://github.com/Kmaichoun/Phishing_AI_Extension_Demo.git
cd Phishing_AI_Extension_Demo
python scripts/inspect_project_context.py --json
```

เครื่องมือที่รองรับ `AGENTS.md` สามารถใช้ไฟล์นั้นเป็นจุดเริ่มอ่าน ส่วนเครื่องมืออื่นให้ส่งข้อความต่อไปนี้พร้อมเปิดโฟลเดอร์ที่ clone ให้ AI เข้าถึง:

```text
อ่าน AGENTS.md และ docs/ai/README.md ก่อนทำงานกับ Phish Radar นี้
ตรวจ branch/source identity: branch ส่งอาจารย์มี curated source รุ่นใหม่ที่ root ส่วน branch เดิมมี source เก่า แยกผล/โมเดลตาม hash
ถ้าใช้ Python ได้ ให้รัน scripts/inspect_project_context.py --json
ตรวจ manifest แล้วแตก docs/ai/current-source.zip ไป .ai-context/current-source เพื่ออ่าน source ปัจจุบัน
อ่าน PROJECT_FACTS_TH.md, DATASET_SOURCES_TH.md และ evidence ที่เกี่ยวข้อง
สรุปภาษาไทยว่า architecture/request flow เป็นอย่างไร สูตรและ policy มาจากไฟล์ใด
ข้อมูลแต่ละชุดใช้ทำอะไร อะไรตรวจยืนยันแล้ว และยังขาดหลักฐานอะไร
อ้าง path ของไฟล์ที่อ่าน อย่าอ้างว่าเซิร์ฟเวอร์หรือการทดลองทำงานแล้วเพียงเพราะมีโค้ด
จากนั้นทำงานต่อไปนี้: [ใส่คำขอที่ต้องการให้ AI ทำ]
```

AI ต้องเข้าถึงไฟล์จริงใน checkout การส่ง URL repository อย่างเดียวไม่ได้ยืนยันว่าเครื่องมือนั้นได้ clone หรืออ่านทุกไฟล์แล้ว

## 2 บริบทของ source และ branch ต้องแยกก่อนอ่าน

| บริบท | ตำแหน่ง | ใช้ทำอะไร |
|---|---|---|
| Source ของ branch ส่งอาจารย์ | `backend/`, `web-app/`, `extension/`, `database/` ที่ root ของ `submission/latest-project-20261029` | คัดจากโครงการหลักที่ตรวจซ้ำ 29 ตุลาคม 2026; ดู publication provenance และ verification ใน `docs/submission-20261029/` |
| Native source รุ่นเดิมใน branch เก่า | root ของ `docs/article-handoff-20261017` และฐาน Git เดิม | เป็นบริบทเก่า ห้ามใช้ hash/model/runtime ของ branch เก่าอธิบาย branch ส่งอาจารย์ |
| Snapshot source ที่ตรวจในเครื่องล่าสุด | [current-source.zip](current-source.zip) และ [CURRENT_SOURCE_MANIFEST.json](CURRENT_SOURCE_MANIFEST.json) | อ่าน implementation ที่รองรับเอกสารรุ่นใหม่ โดยแตกไป `.ai-context/current-source/` |
| หลักฐานโมเดลและการทดลอง | [PROJECT_FACTS_TH.md](../paper/PROJECT_FACTS_TH.md), [evidence](../paper/evidence/) | ตรวจชื่อรุ่น hash สูตร policy ผลเดิม และข้อจำกัดของการตีความ |
| หลักฐานที่มาข้อมูล | [DATASET_SOURCES_TH.md](../paper/DATASET_SOURCES_TH.md) และ [dataset-provenance.json](../paper/evidence/dataset-provenance.json) | แยกแหล่ง รุ่น จำนวน split และบทบาทของ dataset |

ไฟล์ archive คัดเฉพาะ source และทรัพยากรที่ manifest ระบุ ไม่มี `.env`, model binary, raw dataset, dependency folders, output หรือ backup จึงอ่านวิธีทำงานได้ แต่ยังไม่ใช่ชุดทำซ้ำการทดลองหรือเปิดระบบครบทุกบริการ ถ้าไฟล์ใดไม่อยู่ใน manifest ให้ถือว่ายังไม่ได้แนบ

snapshot รุ่นเดิมมาจาก local working copy ที่ไม่มี Git commit ครอบคลุมทั้งชุด ส่วน branch ส่งอาจารย์รอบนี้มี curated source ที่ root และ archive ที่ refresh จาก source ชุดเผยแพร่ ใช้ SHA256 รายไฟล์/archive และ commit ที่เผยแพร่จริงร่วมกัน ระบุวันตรวจ source แยกจากวันของ model/evaluation เดิม

ไม่แนบ `backend/reference-origin-v1.json` ต้นฉบับและ `model-demo-authorization.json` ด้วย เพราะสำเนาต้นทางมี URL parameters ชั่วคราวหรือ path เฉพาะเครื่อง ให้ใช้ hash/status จาก evidence ประกอบการอ่าน code ไม่สร้างไฟล์แทนแล้วอ้างว่าเป็นต้นฉบับเดียวกัน

ตรวจ archive ก่อนแตก:

```bash
python scripts/inspect_project_context.py --json --verify-snapshot
```

แตกด้วย PowerShell จาก repository root:

```powershell
Expand-Archive -LiteralPath .\docs\ai\current-source.zip -DestinationPath .\.ai-context\current-source
```

หรือใช้ Python:

```bash
python -m zipfile -e docs/ai/current-source.zip .ai-context/current-source
```

ไม่แตกทับ application ที่ root และไม่ใช้ `--force` หรือคำสั่งลบ recursive เพื่อแก้ข้อขัดแย้งโดยไม่ตรวจไฟล์เดิม ส่วน `.ai-context/` เป็นสำเนาสำหรับอ่านและไม่ควร commit

ตรวจ hash ของ native model ได้เมื่อจำเป็น โดยไม่ deserialize:

```bash
python scripts/inspect_project_context.py --json --hash-model
```

ผล inventory ไม่ได้ตรวจว่า API, MySQL, Ollama หรือ Extension ที่เปิดอยู่ทำงานจริง และ source/schema markers ไม่ใช่หลักฐานยืนยัน schema ภายใน model binary

exit code 0 ของ inventory หมายถึงสคริปต์อ่านข้อมูลเสร็จ ไม่ได้แปลว่า model/source ตรงกัน ให้ดู `diagnostics`, ค่า `MISMATCH` และสถานะ archive ใน JSON ด้วย

## 3 ลำดับอ่านเพื่อเข้าใจระบบ

1. อ่าน `AGENTS.md` และตารางบริบทข้างต้น แล้วบันทึกว่าจะอ้าง root source ของ branch ใด หรือ extracted snapshot
2. อ่าน `web-app/package.json`, `extension/manifest.json`, `backend/requirements.txt` เพื่อดูเทคโนโลยีและ entry points
3. อ่าน `backend/app.py` → `feature_extractor.py` → `probability_calibration.py` → `risk_policy.py` เพื่อเข้าใจคะแนนและสถานะโมเดล
4. อ่าน `web-app/src/contexts/AppContext.jsx` และ `src/services/api.js` ตามด้วย `extension/background.js`, `ml-feedback-client.js`, `analyzer.js` และ `content.js` เพื่อเข้าใจ client flow
5. อ่าน `auth_router.py`, `history_router.py`, `workspace_router.py`, `chat_router.py`, `database.py` และ SQL migrations เพื่อเข้าใจข้อมูลและสิทธิ์
6. อ่าน JSON หลักฐานและคู่มือ dataset ก่อนอธิบายการฝึกหรือผลทดลอง แล้วเลือกอ่าน training/evaluation script ของรุ่นที่มี hash ตรงกัน
7. อ่านเฉพาะ test ที่ตรงกับคำขอ อ่านวิธีเริ่มบริการก่อนรัน และรายงานข้อจำกัดของเครื่องใหม่

path ในหัวข้อที่เหลือเป็น path ภายใน source root ที่เลือก หากอธิบายรุ่นใหม่ให้ใส่ prefix `.ai-context/current-source/` เมื่ออ้างไฟล์จริง

## 4 สถาปัตยกรรมและ request flow

```text
React Web App                         Chrome Extension MV3
AppContext + API adapter              service worker + content/popup
            \                           /
             local URL rules / client settings
                         |
                  FastAPI backend
        +----------------+-------------------+
        |                |                   |
  URL feature model   MySQL/MariaDB       Ollama / LLM
  RF + calibration    users/sessions     explanation/chat
  score + decision    history/feedback    advisory output
```

**Web ปกติ:** รับ URL → normalize/local rules → `POST /predict` → อ่าน score/decision/readiness/model metadata → แสดงผล → บันทึก history เมื่อเงื่อนไขอนุญาต → ขอคำอธิบายแยกผ่าน `/explain`

**Extension:** service worker รับ navigation หรือคำขอจาก popup/content → อ่าน settings/exceptions/Privacy Mode → local rules → backend เมื่อเปิดใช้งาน → badge/หน้าเตือน ส่วน content script ตรวจลิงก์/แบบฟอร์ม/หลักฐานบนหน้าเว็บเพิ่มเติม การเรียก navigation hook เพียงอย่างเดียวไม่รับรองว่าป้องกันทุก request ก่อนถึงปลายทาง

**Privacy และ fallback:** local-only mode, backend ใช้งานไม่ได้, backend ไม่มีโมเดล และ LLM fallback เป็นคนละกรณี ตรวจ source และ network ของ client ที่เกี่ยวข้องก่อนอ้างว่าไม่ส่งข้อมูลออก ห้ามนำคะแนน fallback มารายงานเป็น RF prediction

**การกรองโฆษณา:** `extension/ad-filter*.js` เป็น presentation behavior บน DOM การซ่อน banner ไม่ได้เปลี่ยน RF score

## 5 API และข้อมูลหลัก

ใช้ request/response models และ route definitions ใน source เป็นข้อกำหนดจริง ตารางนี้เป็นแผนที่ ไม่ใช่ schema ที่แทน source ได้ครบทุก field

| เส้นทาง | จุดอ่าน | หน้าที่และข้อควรระวัง |
|---|---|---|
| `GET /health` | `backend/app.py` | readiness ของแต่ละส่วน ต้องอ่านค่าที่ตอบจริง ไม่อนุมานจาก HTTP 200 เพียงอย่างเดียว |
| `POST /predict` | `app.py`, `feature_extractor.py` | URL และหลักฐานที่รับได้ → features → model/calibration → policy และ metadata ผล |
| `POST /explain` | `app.py`, `llm_explainer.py` | อธิบายผลที่มีอยู่ ไม่เปลี่ยน prediction หรือ threshold |
| `POST /feedback` | `app.py` | feedback CSV ของเส้นทางนี้ แยกจาก feedback ของบัญชี |
| `/auth/*` | `auth_router.py`, `auth_models.py` | register/login/me/profile/password/logout/health ใช้ session cookie และ server-side authorization |
| `/history` | `history_router.py`, `history_models.py` | ประวัติรายบัญชีและ metadata ของผลเก่า ไม่ตีความผลเก่าว่าใช้โมเดลปัจจุบัน |
| `/workspace/*` | `workspace_router.py` | security/sessions/stats/feedback/admin/audit/model experiments ตามสิทธิ์ |
| `POST /chat` | `chat_router.py` | chatbot ของสมาชิกใน source รุ่นใหม่ ไม่ถือว่า native legacy source มี route นี้ |

ฐานข้อมูลใช้ SQLAlchemy กับ MySQL/MariaDB ผ่าน PyMySQL รหัสผ่านถูก hash ด้วย Argon2 และเก็บ session token แบบ hash ดู SQL จริงก่อนวาด ERD ใน snapshot รุ่นใหม่ไม่มี active UserDevices workflow แล้ว แต่ native legacy source อาจยังมี จึงห้ามนำ schema สองรุ่นมารวมกันโดยไม่ระบุ

## 6 โมเดล คะแนน และข้อมูลฝึก

| ประเด็น | ข้อมูลอ้างอิงของรุ่นใหม่ |
|---|---|
| Model version | `url-risk-rf-reference-root-repair-support2-20261008` |
| Model SHA256 | `bc4e024e32aaf0ad695ea4a4dff552ece09d606c4963a49e8bf6aa8a447575bb` |
| Features | `url-v10-reference-root-context`, 174 ตัว |
| Formula | `Score = 100 × Calibrate(Random Forest)`; `fusion_method=ml_only` |
| Policy | `<60 allow`, `60–<80 warn`, `>=80 block`; ตัดสินก่อนปัดเศษแสดงผล |
| Calibration หลังปรับใบ | ใช้ Platt mapping เดิม ไม่ได้ fit ใหม่ |
| สถานะ | ทดลอง; `production_ready=false`, `statistical_gate_passed=false` |
| ข้อมูลพัฒนารวม | 925,602 แถว = train 634,745 + calibration 94,176 + validation 196,681 |

อ่าน [ข้อเท็จจริง](../paper/PROJECT_FACTS_TH.md) สำหรับ parameters, confusion matrices, Recall/FPR และขอบเขตการประเมิน ตัวเลขรวมข้อมูลพัฒนาไม่ใช่จำนวน train เพียงอย่างเดียว และไม่ยืนยันว่ามีการฝึก forest ใหม่ทุกต้น

แหล่งข้อมูลภายนอกหลักคือ PhreshPhish, URL-Phish, Web page phishing detection, PhiUSIIL และ DeepURLBench ร่วมกับ official references สองกลุ่มที่ทีมเก็บเพิ่ม ส่วน PhishTank 151 URL อยู่ใน regression แยก ไม่ใช่ source โดยตรงใน combined development CSV ดู [ตารางและบรรณานุกรม dataset](../paper/DATASET_SOURCES_TH.md)

อย่ารวมคะแนน local rules หรือคำตอบ LLM เข้ากับ RF score ในคำอธิบายรุ่นนี้ และอย่าใช้ชื่อ script ใหม่สุดหรือ report เก่าแทนการตรวจ artifact/hash

## 7 แผนที่งานให้ AI เลือกอ่าน

| งานที่ได้รับ | เริ่มอ่านใน source root ที่เลือก | สิ่งที่ต้องตรวจเพิ่ม |
|---|---|---|
| อธิบายสูตรหรือคะแนน URL | `backend/app.py`, `feature_extractor.py`, `probability_calibration.py`, `risk_policy.py`, reference-origin modules | model hash/schema, unrounded score, actual API response หากอ้าง runtime |
| แก้ Scanner หรือผลบน Web | `web-app/src/contexts/AppContext.jsx`, `src/pages/ScannerPage.jsx`, `src/services/api.js`, `src/services/risk.js` | malformed response, error/readiness/privacy states, backend decision |
| แก้หน้าเตือนและ Extension | `extension/background.js`, `ml-feedback-client.js`, `warning.js`, `popup.js`, `content.js` | source version, loaded extension/reload, policy boundaries, actual DOM/network |
| แก้โฆษณา/ป๊อปอัป | `extension/ad-filter.js`, `ad-filter-policy.js` และ test fixtures | DOM ของเว็บเป้าหมายและ mixed-content wrappers; แยกจาก ML |
| ตรวจ QR และ safe preview | `extension/qr-scanner.js`, `safe-preview.js`, HTML/CSS ที่เกี่ยวข้อง และ `web-app/src/pages/ScannerPage.jsx` | ตรวจเส้นทาง URL หลัง decode และขอบเขตที่ browser จำกัด ไม่สรุปว่า preview ทำให้เว็บเสี่ยงปลอดภัย |
| แก้ login/history/admin | `backend/auth_router.py`, `history_router.py`, `workspace_router.py`, SQL migrations และ Web contexts/pages | migration version, user/admin scope, cookies/CORS, test accounts |
| แก้คำอธิบาย/แชต | `backend/llm_explainer.py`, `chat_router.py`, Web chat components | configured provider/model, health, real response/cache/fallback, consistency with score |
| ลด false positive หรือทดลองโมเดล | `backend/model_registry.py`, trainer/evaluator ที่ตรง design และ source manifests | Recall/FPR ร่วมกัน, split/exposure audit, promotion gates และ backup |
| ทำบทความส่งอาจารย์ | `docs/paper/README.md` และหลักฐานในโฟลเดอร์นั้น | หัวข้อครบ อ้างงานวิจัยแยกจากผลโครงงาน ไม่แต่งผู้แต่ง ผลทดลอง หรือ user study |
| เปิด demo/deploy | startup scripts, `scripts/run_public_backend.py`, `Dockerfile`, `.env.example` | สิทธิ์รันบริการจริง static build, DB/LLM readiness, CORS/cookie origins และการเข้าถึงจากภายนอก |

## 8 การติดตั้งและตรวจงานตามขอบเขต

การอ่านคู่มือไม่ต้องติดตั้ง dependency ถ้าจะรันระบบ ให้เลือก source root และ model artifact ที่ตรงกันก่อน snapshot นี้ไม่แนบ binary ของโมเดลที่บันทึกในหลักฐาน อย่านำ native model คนละรุ่นมาใส่แล้วอ้างว่าเป็นระบบรุ่นใหม่

พื้นฐานของโครงงานคือ Python 3.12 ตามคู่มือเดิม, React/Vite และ Node รุ่นที่รองรับ Vite ใน `package.json`, MySQL/MariaDB และ Chrome ที่รองรับ MV3 ตรวจรุ่นจริงของเครื่องใหม่ก่อนติดตั้ง

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
cd web-app
npm ci
npm run build
```

ตัวอย่างนี้เป็น path บน Windows/Git Bash ให้ปรับ executable path สำหรับ OS อื่น ใช้ `.env.example` เป็นแม่แบบและใส่ค่าของเครื่องใหม่เอง ก่อนใช้ระบบสมาชิกต้องเปิดฐานข้อมูลและทำ migrations ที่ตรงรุ่น เปิด Ollama เฉพาะเมื่อต้องการคำอธิบายจริง

พอร์ตตั้งต้น: backend 8765, Web 5505, MySQL 3306; Ollama default ใน template คือ 11434 กับ `qwen3:4b` ค่าที่เคยรันในอีกเครื่องอาจต่างออกไป อย่าใช้ค่า default ยืนยัน provider/model ที่กำลังให้บริการ

### เลือก checks ที่ตรงงาน

| งาน | คำสั่งหรือจุดตรวจ | ข้อกำหนด |
|---|---|---|
| เข้าใจ checkout | `python scripts/inspect_project_context.py --json` | stdlib; read-only ไม่ใช่ live health |
| ตรวจ archive | เพิ่ม `--verify-snapshot` | อ่าน hash ของ zip เทียบ manifest |
| ตรวจ native model เทียบหลักฐาน | เพิ่ม `--hash-model` | hash bytes เท่านั้น ไม่ load pickle |
| ตรวจเครื่องมือ inventory เอง | `python scripts/inspect_project_context.py --self-test` | ตรวจพฤติกรรม inspector ไม่ใช่ฟังก์ชันแอป |
| Policy/score | `scripts/test_warning60.py`, `test_probability_calibration.py`, `test_reference_origin_features.py` | อ่าน test ก่อนรันใน source ที่ตรงรุ่นและมี Python dependencies |
| Web response/UI | `scripts/test_prediction_response.cjs`, `test_result_presentation.cjs`, `test_warning60_ui.cjs`, `test_web_app_ui.js` | บางตัวใช้ `web-app/node_modules`, สร้างไฟล์ใน tmp หรือ browser จึงไม่ใช่ read-only inventory |
| Extension/filter | `scripts/test_ad_filter_policy.cjs`, `test_ad_popup_guard.cjs`, fixture ที่เกี่ยวข้อง | แยก unit/fixture จากการทดสอบเว็บจริงและ reload extension |
| Source/resources | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/validate_project.ps1` | อาจเรียกหลาย checks และต้องมีทรัพยากรครบ ไม่ใช่ test ว่าโมเดลแม่นยำ |
| DB/auth/history/chat | `test_auth_flow.py`, `test_history_flow.py`, `test_workspace_flow.py`, `test_chat.py` | ต้องอ่านสคริปต์และเตรียม service/test account ตามข้อกำหนด ไม่รันต่อ production อัตโนมัติ |

คำสั่งในตารางเป็นแผนตรวจ ไม่ใช่รายการที่ยืนยันว่าผ่านในเครื่องใหม่ สำหรับงานนี้ให้ดูผล inspector และการตรวจ package ที่รายงานแยกต่างหาก การฝึกโมเดลหรือเพิ่ม URL ลงชุดข้อมูลไม่ใช่ smoke test

## 9 ข้อจำกัดและข้อขัดแย้งที่ต้องจำ

- source ใน branch เก่าและเอกสารประวัติบางไฟล์ยังอธิบาย learned fusion/consensus อย่าใช้ยืนยันสูตร ml_only ของ artifact รุ่นรายงาน; branch ส่งอาจารย์มีหลาย compatibility paths ใน code เช่นกัน ต้องยึด metadata ของ bundle ที่ตรง hash
- SHA256 ต่างอาจเกิดจาก line endings ได้ ต้องดูเนื้อหาและ code path ร่วมด้วยก่อนสรุปว่าพฤติกรรมเปลี่ยน
- source archive ไม่มี private settings, model binary หรือ raw dataset จึงไม่อาจรันทุก workflow ได้จากการ clone เพียงอย่างเดียว
- ไม่มี fresh forward-temporal test ครบ benign/phishing และประวัติ baseline exposure บางส่วนยังไม่ครบ จึงไม่รับรองความแม่นยำปัจจุบันทั่วอินเทอร์เน็ต
- ข้อมูล JSON อ้างผลที่บันทึกไว้ ไม่ใช่การรัน evaluation ใหม่ทุกครั้งที่สร้างเอกสาร
- public URL ที่เคยบันทึกใน source ไม่รับประกันว่ายังเปิดอยู่หรือ services พร้อม ต้องตรวจปัจจุบันหากงานต้องใช้
- ห้ามให้การอ่าน archive กระตุ้นการ train, activate, migrate, เปิด tunnel หรือเยี่ยมชม phishing URLs โดยอัตโนมัติ
- ถ้าโจทย์ต้องแก้ runtime รุ่นใหม่จริง ให้ยืนยัน baseline/source root และรับ artifact ที่ตรง hash ก่อนเริ่มงาน ไม่แก้รายงานให้เข้ากับของคนละรุ่น

## 10 รูปแบบที่ให้ AI สรุปหลังเริ่มอ่าน

ให้ AI สรุปสั้น ๆ ว่าเลือก source root ใด แผนภาพ request flow เป็นอย่างไร ไฟล์หลักของคำขออยู่ที่ใด สูตร/policy/model identity ใดยืนยันได้ แหล่งข้อมูลและ split ที่เกี่ยวข้องคืออะไร มีข้อขัดแย้งหรือไฟล์ขาดใด และจะตรวจงานระดับไหน วิธีนี้ช่วยตรวจว่า AI ใช้หลักฐานถูกชุดก่อนลงมือทำงานต่อ

เมื่อเจ้าของโครงงานจะอัปเดตชุด context ให้ใช้ `scripts/package_ai_source_context.py --root <โฟลเดอร์ source ปัจจุบัน> --source-date YYYY-MM-DD` กับ source ที่ตรวจแล้ว ตรวจ manifest/ข้อจำกัดและเอกสารที่เกี่ยวข้องใหม่ก่อนเผยแพร่ ไม่ใช้ native legacy source จาก branch เก่าสร้าง snapshot ทับรุ่นใหม่โดยไม่ตรวจรุ่น
