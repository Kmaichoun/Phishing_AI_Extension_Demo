# แหล่งที่มาของชุดข้อมูล Phish Radar

> บริบทการส่ง 2026-10-29: เอกสารนี้เก็บข้อเท็จจริง/ผลและวันตรวจเดิม ไม่ใช่ผล evaluation ใหม่ Source ที่ root ของ `submission/latest-project-20261029` เป็น curated source รุ่นใหม่แล้ว ส่วนคำเตือนเกี่ยวกับ native source เก่าในเนื้อหาเดิมหมายถึง branch เก่า ดู [รายงานการส่ง](../submission-20261029/README.md) และ [ผลตรวจรอบนี้](../submission-20261029/VERIFICATION_TH.md)

เพิ่มเติมวันที่ 20 ตุลาคม 2026 สำหรับให้เพื่อนเขียนหัวข้อ 3.2 ข้อมูลและการเตรียมข้อมูล พร้อมเอกสารอ้างอิง ตรวจแหล่งเผยแพร่ต้นทางและไฟล์ provenance ของโครงงาน โดยใช้โมเดล `url-risk-rf-reference-root-repair-support2-20261008` ที่มี SHA256 `bc4e024e32aaf0ad695ea4a4dff552ece09d606c4963a49e8bf6aa8a447575bb` เป็นจุดอ้างอิง

## 1 แหล่งข้อมูลและบทบาทที่ตรวจยืนยันได้

| รหัส | แหล่งต้นทาง | ข้อมูลที่นำมาใช้ | บทบาทในโครงงานและข้อจำกัด |
|---|---|---|---|
| D1 | [PhreshPhish บน Hugging Face](https://huggingface.co/datasets/phreshphish/phreshphish) | URL, label และ date จากผู้เผยแพร่ | อยู่ในข้อมูลพัฒนาและผลย้อนหลัง ต้องแยก publisher train/test และประวัติการใช้ข้อมูลก่อนเรียกชุดใดว่า test อิสระ โครงงานส่วนนี้ใช้ URL ไม่ได้ใช้ HTML ทั้งหมดของต้นทาง |
| D2 | [URL-Phish v1 บน Mendeley Data](https://data.mendeley.com/datasets/65z9twcx3r/1) | URL และ label ที่ผู้จัดทำกำหนด | อยู่ในข้อมูลพัฒนา เคยใช้ทดลองแล้ว จึงไม่ใช่แหล่ง test ใหม่ทั้งหมด ผู้เผยแพร่ระบุ phishing จาก PhishTank และ benign จาก ROR เป็นที่มาทางอ้อม ไม่ได้แปลว่าโครงงานดาวน์โหลด ROR ดิบเอง |
| D3 | [Web page phishing detection v3 บน Mendeley Data](https://data.mendeley.com/datasets/c2gw7fy2j4/3) | URL และ label แล้วสกัด feature ของโครงงานเอง | อยู่ในข้อมูลพัฒนาและการทดลองย้อนหลัง ไม่ได้ใช้ 87 features ของต้นทางทั้งหมดโดยอัตโนมัติ ข้อมูลต้นทางสร้างเดือนพฤษภาคม 2020 ส่วน v3 เผยแพร่ปี 2021 |
| D4 | [PhiUSIIL จาก UCI dataset 967](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset) | URL และ label จากชุดเผยแพร่ปี 2024 | ใช้เพิ่มข้อมูลพัฒนา และแยก confirmation 15,463 URL สำหรับผลที่บันทึกไว้ การแยกชุดต้องยึดไฟล์และ hash ของโครงงาน ไม่ใช้ข้อมูลต้นทางทั้งหมดเป็นชุดทดสอบ |
| D5 | [DeepURLBench ของ Deep Instinct](https://github.com/deepinstinct-algo/DeepURLBench) | เลือก benign/phishing จากข้อมูลที่มี benign/phishing/malware | มีทั้งข้อมูลพัฒนา holdout และ confirmation คนละส่วน ไม่ใช้ malware เป็น phishing โดยอัตโนมัติ ผล confirmation รอบสองที่รายงานมี 10,000 URL |
| D6 | [PhishTank developer information](https://phishtank.net/developer_info.php) | feed ของ URL ฟิชชิงที่ผ่านการยืนยันของชุมชน | ชุด `recent_phishing_regression` ที่รายงานมี 151 URL เป็น phishing-only ใช้ดู Recall/การถดถอย จึงประเมิน FPR จากชุดนี้เพียงอย่างเดียวไม่ได้ |
| D7 | เว็บไซต์และเอกสารทางการของผู้ให้บริการที่ทีมเลือกเก็บ | URL อ้างอิง พร้อมบันทึกเวลาและ HTML hash ของหน้าอ้างอิง | เป็น targeted benign examples และ metadata ของ exact origin สำหรับพัฒนา/ตรวจกรณีเฉพาะ ไม่ใช่ตัวแทนเว็บปกติทั้งอินเทอร์เน็ต และไม่ใช่ allowlist ที่รับรองทุกหน้า |

คำว่า “อยู่ในข้อมูลพัฒนา” หมายถึงตรวจพบใน lineage ของชุด train/calibration/validation ที่ใช้พัฒนาและปรับโมเดล ห้ามเปลี่ยนเป็นข้อความว่า “ฝึก forest ใหม่จากทุกแหล่งทั้งหมด” เพราะโมเดลที่อ้างมีการปรับใบของ forest เดิม และประวัติการสัมผัสข้อมูลของ baseline ดั้งเดิมยังตรวจย้อนหลังไม่ครบ

## 2 จำนวนที่อยู่ในชุดพัฒนาซึ่งใช้ปรับโมเดล

ตรวจนับ `source × split` จาก `backend/data/simple_quality_rf_20261008/dataset.csv` วันที่ 20 ตุลาคม 2026 ได้ SHA256 `c02bb2adf07c71ddc391403f3d190fb9ab289d058f62ba3177318612428b0df0` ตรงกับ `development_sha256` ใน design ของโมเดลที่อ้าง จำนวนต่อไปนี้เป็นแถวที่เหลือในไฟล์รวมหลังการเตรียมข้อมูล ไม่ใช่จำนวนดิบของผู้เผยแพร่

| แหล่งในไฟล์รวม | Train | Calibration | Validation | รวม |
|---|---:|---:|---:|---:|
| PhreshPhish | 330,944 | 39,204 | 123,698 | 493,846 |
| URL-Phish | 77,692 | 10,880 | 22,258 | 110,830 |
| Web page phishing detection v3 | 8,276 | 981 | 2,003 | 11,260 |
| DeepURLBench | 56,781 | 20,072 | 21,526 | 98,379 |
| UCI PhiUSIIL | 160,190 | 22,917 | 27,077 | 210,184 |
| Official references รอบเดิม | 95 | 86 | 29 | 210 |
| Official references รอบ quality | 767 | 36 | 90 | 893 |
| **รวม** | **634,745** | **94,176** | **196,681** | **925,602** |

ไม่มี source ชื่อ PhishTank โดยตรงในไฟล์รวมนี้ ส่วน PhishTank 151 URL อยู่ในชุด regression แยก ข้อมูลจาก URL-Phish อาจมีที่มาทางอ้อมจาก PhishTank ตามคำอธิบายของผู้เผยแพร่ จึงต้องแยก “ผู้เผยแพร่ dataset ที่นำเข้า” ออกจาก “ที่มาที่ผู้เผยแพร่ใช้รวบรวม”

จำนวน 925,602 ครอบคลุมทั้งสาม split ไม่ใช่จำนวน train เพียงอย่างเดียว และไม่ใช่หลักฐานว่า forest ทุกต้นถูกฝึกใหม่จากทุกแถว การทดลองรุ่นอ้างอิงใช้ข้อมูลนี้สำหรับการปรับใบและขั้นตอนที่ script กำหนด โดยคง forest หลักและ Platt mapping เดิม

## 3 รุ่นและการอ้างที่มาของแต่ละแหล่ง

ใช้รายการนี้เป็นข้อมูลบรรณานุกรมตั้งต้น แล้วจัดรูปแบบตามที่อาจารย์กำหนด ใส่การอ้างในหัวข้อข้อมูลและวิธีดำเนินงานด้วย ไม่ใส่แค่ท้ายบทความ

- **D1** Thomas Dalton et al., *PhreshPhish*, dataset v1.0.1, Hugging Face; revision ที่ manifest บันทึก `eabec4b7a66324b79cc8a0ad856d1731dc26fe1a`. [ชุดข้อมูล](https://huggingface.co/datasets/phreshphish/phreshphish) และ [บทความ arXiv:2507.10854](https://arxiv.org/abs/2507.10854). หน้า dataset ระบุ CC BY 4.0 และการใช้เพื่อ anti-phishing research
- **D2** Linh Dam Minh and Hung Tran Cong, *URL-Phish: A Feature-Engineered Dataset for Phishing Detection*, version 1, 2025. [DOI 10.17632/65z9twcx3r.1](https://doi.org/10.17632/65z9twcx3r.1). ผู้เผยแพร่ระบุ CC BY 4.0
- **D3** Abdelhakim Hannousse and Salima Yahiouche, *Web page phishing detection*, version 3, 2021. [DOI 10.17632/c2gw7fy2j4.3](https://doi.org/10.17632/c2gw7fy2j4.3). ผู้เผยแพร่ระบุ CC BY 4.0
- **D4** Arvind Prasad and Shalini Chandra, *PhiUSIIL Phishing URL (Website)*, UCI Machine Learning Repository, 2024, dataset 967. [หน้าชุดข้อมูล](https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset). ผู้เผยแพร่ระบุ CC BY 4.0
- **D5** Deep Instinct Research Team, *DeepURLBench*. [Repository ของผู้จัดทำ](https://github.com/deepinstinct-algo/DeepURLBench). revision ที่ใช้ใน manifest คือ `bf17c3fef854ff0ea40bcf93e373fc2c6dc30081`. ผู้เผยแพร่ระบุ CC BY-NC 4.0
- **D6** PhishTank, *Developer Information*. [คำอธิบาย feed และฟิลด์ข้อมูล](https://phishtank.net/developer_info.php). อ้าง snapshot/hash และเวลาที่โครงงานบันทึกด้วย เพราะ feed เปลี่ยนตามเวลา ไม่สมมติว่าใช้ใบอนุญาตเดียวกับ dataset อื่น
- **D7** อ้างหน้าเอกสารหรือเว็บไซต์ต้นทางของ URL อ้างอิงที่นำมาอธิบายจริง พร้อมวันที่เก็บหลักฐาน รายการสรุปอยู่ใน provenance ของโครงงาน ไม่ใช้ชื่อแบรนด์เป็นหลักฐานว่าทุก URL ปลอดภัย

## 4 หลักฐานภายในสำหรับตรวจย้อนกลับ

อ่าน [dataset-provenance.json](evidence/dataset-provenance.json) สำหรับสรุป source, รุ่น, บทบาท, จำนวนแถว และ hash ที่เชื่อมกับไฟล์ต้นทางในเครื่อง ไฟล์นี้สรุปเฉพาะข้อมูล provenance สำหรับเผยแพร่ ไม่ได้แนบ raw dataset หรือ URL จากหน้าเข้าสู่ระบบที่มีค่า session

| เรื่อง | Path ต้นทางในโครงงานหลัก |
|---|---|
| PhreshPhish และ URL-Phish ที่กู้คืน | `backend/data/recovered-20261004/recovery-manifest.json` และ `development-publisher-manifest.json` |
| DeepURLBench ที่คัดมาใช้ | `backend/data/host-context-20261008/manifest.json` |
| PhiUSIIL และการแยก confirmation | `backend/data/quality-augmentation-20261008/manifest.json` |
| ข้อมูลพัฒนาที่ใช้ปรับโมเดลอ้างอิง | `backend/data/simple_quality_rf_20261008/dataset.csv` |
| DeepURLBench confirmation รอบแรกและรอบสอง | `backend/data/incremental-confirmation-20261008/manifest.json` และ `backend/data/incremental-confirmation-round2-20261008/manifest.json` |
| PhishTank ชุด 151 URL | `backend/data/host-context-20261008/temporal-phishing-test.manifest.json` |
| URL อ้างอิงที่เก็บโดยโครงงาน | `backend/data/host-context-20261008/official-references.manifest.json` และ `backend/data/quality-official-references-20261008/manifest.json` |

path ในตารางเป็น provenance ของสำเนาโครงงานหลักที่ตรวจในเครื่อง ไม่ใช่คำยืนยันว่ามี raw files เหล่านี้อยู่ใน branch เอกสารบน GitHub ดูข้อจำกัดเรื่อง source รุ่นเก่าใน [README](README.md)

## 5 ประเด็นที่ต้องระบุเมื่อเขียนรายงาน

1. แยก **จำนวนต้นทาง / จำนวนหลังทำความสะอาด / จำนวน train / calibration / validation / confirmation** อย่าใช้จำนวนรวมแทนจำนวนฝึกทั้งหมด
2. โครงงานใช้ label `0=benign`, `1=phishing` แต่ PhiUSIIL ต้นทางระบุ `1=legitimate`, `0=phishing` จึงต้องอธิบายการแปลง label
3. ระบุวิธีตัด URL ซ้ำ ข้อมูล label ขัดกัน และการแยก registered domain พร้อมประวัติการใช้ชุดข้อมูล หากเคยใช้เลือกโมเดลแล้วห้ามเรียกชุดนั้นเป็น test ใหม่
4. แยกวันเผยแพร่ วันดาวน์โหลด วันสังเกต URL และวันรายงาน ผลเก็บในปี 2026 ไม่ได้ทำให้ URL ทุกแหล่งเป็นข้อมูลปี 2026
5. PhreshPhish มีข้อจำกัดจากการลบ query ฝั่ง benign ของผู้เผยแพร่ URL-Phish มีจำนวนบนคำอธิบายหน้าเว็บต่างจากไฟล์ที่โครงงานบันทึกไว้ จึงต้องใช้จำนวนจากไฟล์และ hash ที่เลือกจริง พร้อมระบุความต่าง
6. ชุด PhishTank ที่มีแต่ phishing ใช้แทนชุด benign/phishing ครบสอง class ไม่ได้ และชื่อ “fresh confirmation” ในไฟล์ไม่ได้ยืนยันว่าเป็น forward-temporal test
7. การมี provenance และแหล่งข้อมูลวิจัยที่ตรวจย้อนกลับได้ ไม่ใช่หลักฐานว่าระบบแม่นยำสูงหรือพร้อม production ผลต้องยึด [ตารางหลักฐานโมเดล](PROJECT_FACTS_TH.md)

## 6 แหล่งใน pipeline รุ่นเก่า

`backend/data/training_urls.manifest.json` บันทึก pipeline เก่าขนาด 20,000 URL ที่ใช้ PhishTank, [OpenPhish](https://openphish.com/) และ [Tranco](https://tranco-list.eu/) รวมถึง seed/curated links และ URL ที่สร้างรูปแบบเพิ่มเติม

รายการนี้ใช้เล่าประวัติการพัฒนาได้พร้อมชื่อรุ่นและวันที่ ไม่ใช้แทน lineage ของชุดพัฒนา/ประเมินในตารางข้างต้น และความนิยมโดเมนจาก Tranco ไม่ใช่ label ยืนยันว่าแต่ละ URL ปลอดภัย
