# QR / Clipboard / Search Protection Update

## แนวคิด

รอบนี้เพิ่มการป้องกันก่อนผู้ใช้เปิดเว็บจริง เพื่อให้ Phish Radar AI ไม่ได้ตรวจแค่หลังจากเข้าเว็บแล้ว แต่ช่วยเตือนตั้งแต่ก่อนกดลิงก์ ก่อนวางลิงก์ และก่อนเปิด URL จาก QR code

## สิ่งที่เพิ่ม

### 1. Search Protection

- ตรวจลิงก์บนหน้าค้นหา เช่น Google, Bing, DuckDuckGo, Yahoo
- วิเคราะห์ปลายทางจริงของลิงก์ ไม่ใช่ดูแค่ redirect wrapper ของ search engine
- แสดง badge ข้างผลค้นหาที่น่าสงสัย
- ผู้ใช้ hover หรือกด badge เพื่อดูเหตุผลก่อนเปิดลิงก์
- ถ้าคะแนนเกิน threshold จะพาไปหน้า warning ก่อนเปิดเว็บ

### 2. Clipboard Protection

- ตรวจข้อความที่ผู้ใช้ paste ลงในหน้าเว็บ
- ถ้าพบ URL เสี่ยงสูง ระบบจะหยุดการ paste ชั่วคราว
- แสดงหน้าต่างเตือนพร้อมคะแนนและเหตุผล
- ผู้ใช้เลือกได้ว่าจะเปิดหน้า warning, วางต่อ หรือยกเลิก
- ใน popup มีปุ่ม `ตรวจ Clipboard` สำหรับอ่าน URL จาก clipboard และวิเคราะห์ก่อนเปิด

### 3. QR Protection

- เพิ่มหน้า `QR Scanner` ใน extension
- รองรับการสแกนจากกล้องและการอัปโหลดรูป QR
- อ่าน URL จาก QR แล้วตรวจด้วย analyzer เดิมก่อนเปิดจริง
- แสดง risk score, URL ที่อ่านได้ และเหตุผลที่พบ
- ผู้ใช้กดเปิดหน้า warning ก่อนได้ แทนการเปิดเว็บปลายทางทันที

## ไฟล์ที่เกี่ยวข้อง

- `manifest.json`
- `background.js`
- `popup.html`
- `popup.js`
- `content.js`
- `content.css`
- `qr-scanner.html`
- `qr-scanner.css`
- `qr-scanner.js`

## วิธีทดสอบ

1. Reload extension ที่ `chrome://extensions`
2. เปิด Google แล้วค้นหาคำที่มีลิงก์เสี่ยง จากนั้นดู badge ข้างผลค้นหา
3. คัดลอก URL เสี่ยง แล้วกด `ตรวจ Clipboard` ใน popup
4. ลอง paste URL เสี่ยงลงในช่องข้อความบนเว็บ ระบบควรเตือนก่อนวาง
5. เปิด popup แล้วกด `QR Scanner`
6. อัปโหลดรูป QR หรือเปิดกล้องเพื่ออ่าน QR แล้วดูผลวิเคราะห์ก่อนเปิดเว็บ
