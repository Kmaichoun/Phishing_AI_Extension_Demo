# ฐานข้อมูล MySQL/MariaDB

โปรเจกต์ใช้ 5 ตาราง โดย Session และประวัติการสแกนผูกกับบัญชีผ่าน `UserId`:

1. `Users` — บัญชี, Argon2 PasswordHash และ Role
2. `Sessions` — Session ฝั่งเซิร์ฟเวอร์และ SHA-256 TokenHash
3. `SearchHistory` — URL ที่ตัดข้อมูลลับแล้ว พร้อม Risk Model audit
4. `ScanFeedback` — ความเห็นต่อผลตรวจและการทบทวนโดย Admin
5. `AuditEvents` — บันทึกการเปลี่ยนสิทธิ์ การยกเลิก Session และการทบทวน Feedback

ระบบไม่เก็บชื่ออุปกรณ์ ตัวระบุอุปกรณ์ หรือความสัมพันธ์ UserDevice แล้ว
รหัสผ่านและ session token เก็บเฉพาะค่า hash และใช้คุกกี้ HttpOnly สำหรับ Session
แต่ละการเข้าสู่ระบบสร้าง Session ของบัญชี สามารถดูเวลาเริ่มใช้งาน/ใช้งานล่าสุด
และยกเลิก Session อื่นได้ในหน้า “การเข้าสู่ระบบ” คุกกี้อุปกรณ์จากรุ่นเก่าจะถูกล้าง
เมื่อสมัครสมาชิก เข้าสู่ระบบ เรียกข้อมูลที่ต้องเข้าสู่ระบบ หรือออกจากระบบสำเร็จ

## ฐานข้อมูลใหม่หรือฐานข้อมูลว่าง

1. เลือกฐานข้อมูลปลายทางที่ภาควิชาสร้างให้ใน phpMyAdmin
2. เลือก **Import** แล้วเลือก `phish_radar_phpmyadmin_import.sql` ในโฟลเดอร์นี้
3. กด **Go** หลังสำเร็จควรเห็น 5 ตารางตามรายการด้านบน

ไฟล์นี้ไม่มี `CREATE DATABASE` หรือ `USE` จึงทำงานกับฐานข้อมูลที่เลือกอยู่
ไม่มีบัญชีหรือข้อมูลตัวอย่าง สมัครบัญชีผ่านหน้าเว็บหลังเชื่อมต่อ Backend แล้ว
ชื่อฐานข้อมูลจริงอาจต่างจากค่าเริ่มต้น `ip_std6730202581` ของโปรเจกต์
ให้ตั้ง `MYSQL_DATABASE` ให้ตรงกับชื่อที่เลือกใน phpMyAdmin

## ฐานข้อมูลที่เคย Import รุ่นที่มี UserDevices

หยุด Backend รุ่นเดิมและ Export สำรองฐานข้อมูลก่อน แล้วเลือกฐานข้อมูลเดิมใน
phpMyAdmin → **Import** → `upgrades/007_remove_user_devices.sql` → **Go**
จากนั้นเริ่ม Backend รุ่นใหม่พร้อม Web App ที่ build ใหม่

ไฟล์อัปเกรดลบคอลัมน์ `UserDeviceId` จาก `Sessions` และ `SearchHistory`,
ลบตาราง `UserDevices` และลบบันทึก Audit ที่เกี่ยวกับอุปกรณ์โดยตรง
บัญชี, password hash, Session, ประวัติการสแกน และ Feedback เดิมยังอยู่
รันซ้ำได้เมื่อคอลัมน์หรือตารางอุปกรณ์ถูกลบไปแล้ว
ไฟล์นี้รองรับ schema ของโปรเจกต์ที่ไม่มี Foreign Key ตามชุดเดิม
หากเพิ่ม Foreign Key เอง ต้องนำ constraint ที่ผูก `UserDeviceId` ออกก่อน

**Import ไฟล์สร้างตารางใหม่อย่างเดียวจะไม่อัปเกรดตารางเดิม** เพราะใช้
`CREATE TABLE IF NOT EXISTS` จึงต้องใช้ไฟล์อัปเกรดสำหรับฐานข้อมูลเดิม

## รันจากโปรเจกต์

```bash
./migrate-db.sh
```

คำสั่งอ่าน `.env`, สร้างตารางที่ยังไม่มี และรันไฟล์ใน `upgrades/` โดยอัตโนมัติ
หากต้องการรันไฟล์สร้างตารางแยก ให้ใช้ตามลำดับนี้ (เลข 002 ถูกยกเลิก):

```text
migrations/001_create_users.sql
migrations/003_create_sessions.sql
migrations/004_create_search_history.sql
migrations/005_create_scan_feedback.sql
migrations/006_create_audit_events.sql
```

บัญชี Shared Hosting อาจไม่มีสิทธิ์ `REFERENCES` ชุดนี้จึงใช้ Primary Key,
Unique Index และ Index ของ `UserId` โดยให้ Backend ตรวจสอบความสัมพันธ์
หากยังไม่มีฐานข้อมูลและบัญชีมีสิทธิ์ `CREATE DATABASE` จึงค่อยใช้
`create_database.sql`; ฐานข้อมูลที่ภาควิชาสร้างไว้แล้วไม่ต้องรันไฟล์นั้น

## ตั้งค่า Backend

ตั้งค่าใน `.env` โดยใช้ชื่อและข้อมูลเชื่อมต่อจริงจากภาควิชา:

```dotenv
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ชื่อฐานข้อมูลที่เลือกใน phpMyAdmin
MYSQL_USER=ชื่อผู้ใช้ฐานข้อมูล
MYSQL_PASSWORD=รหัสผ่านฐานข้อมูล
MYSQL_CHARSET=utf8mb4
```

ถ้ากำหนด `DATABASE_URL` ไว้ ค่านั้นมีลำดับความสำคัญเหนือ `MYSQL_*`
`localhost` ใช้ได้เมื่อ Backend และ MySQL อยู่เครื่องเดียวกัน หาก Backend
อยู่เครื่องอื่น ต้องใช้ Remote MySQL Host และสิทธิ์เชื่อมต่อที่ภาควิชาอนุญาต
การ Import ฐานข้อมูลอย่างเดียวไม่ได้เปิด Web App และ Backend ตลอดเวลา
ต้องติดตั้งและเปิดบริการทั้งสองส่วนบนเซิร์ฟเวอร์ด้วย

## ตั้งผู้ใช้เป็น Admin

สมัครสมาชิกผ่านหน้าเว็บก่อน แล้วรัน โดยเปลี่ยนอีเมลให้เป็นบัญชีจริง:

```sql
UPDATE `Users`
SET `Role` = 'admin'
WHERE `NormalizedEmail` = LOWER(TRIM('name@example.com'));
```

ตรวจผล:

```sql
SELECT `UserId`, `Username`, `Email`, `Role`, `IsActive`, `CreatedAt`
FROM `Users`
ORDER BY `UserId`;
```
