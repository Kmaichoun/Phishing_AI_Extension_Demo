# ฐานข้อมูลสมาชิก MySQL/MariaDB

โปรเจกต์ใช้ฐานข้อมูล `ip_std6730202581` และตารางต่อไปนี้:

1. `Users` — บัญชี, Argon2 PasswordHash และ Role
2. `UserDevices` — อุปกรณ์และ SHA-256 DeviceKeyHash
3. `Sessions` — Session ฝั่งเซิร์ฟเวอร์และ SHA-256 TokenHash
4. `SearchHistory` — URL ที่ตัดข้อมูลลับแล้ว พร้อม Risk Model audit

ไม่เก็บรหัสผ่านจริง, session token หรือ device token ลงฐานข้อมูล

## หมายเหตุสำหรับ Shared Hosting

บัญชีฐานข้อมูลบาง Hosting ไม่มีสิทธิ์ `REFERENCES` จึงไม่สามารถสร้าง Foreign Key
ได้ ไฟล์ migration ชุดนี้ใช้ Primary Key, Unique Index และ Index สำหรับ
`UserId`/`UserDeviceId` โดยให้ Backend ตรวจสอบความสัมพันธ์และข้อมูลช่วงคะแนนแทน
เพื่อให้ Import ผ่าน phpMyAdmin ได้โดยไม่ต้องขอสิทธิ์ระดับผู้ดูแล

ถ้าผู้ให้บริการเพิ่มสิทธิ์ `REFERENCES` ให้ภายหลัง สามารถเพิ่ม Foreign Key เป็น
งาน hardening แยกได้ แต่ไม่จำเป็นต่อการสมัคร, Login, Session และ Search History
ของระบบปัจจุบัน

## สร้างตารางผ่าน phpMyAdmin

ฐานข้อมูลใน Shared Hosting มักถูกสร้างจาก Control Panel ไว้แล้ว จากภาพให้เลือก
`ip_std6730202581` ทางซ้าย แล้วเปิดแท็บ **SQL** จากนั้นรันไฟล์ตามลำดับ:

```text
database/mysql/migrations/001_create_users.sql
database/mysql/migrations/002_create_user_devices.sql
database/mysql/migrations/003_create_sessions.sql
database/mysql/migrations/004_create_search_history.sql
```

ถ้าบัญชี MySQL มีสิทธิ์ `CREATE DATABASE` และยังไม่มีฐานข้อมูลจริง ๆ จึงค่อยรัน
`database/mysql/create_database.sql` ก่อน การรันไฟล์นี้บน Shared Hosting อาจถูกปฏิเสธ
เพราะผู้ให้บริการเป็นผู้สร้างชื่อฐานข้อมูลให้

หรือรันทุก migration จาก Git Bash:

```bash
./migrate-db.sh
```

คำสั่งนี้อ่านค่าการเชื่อมต่อจาก `.env`

## ตั้งค่า `.env`

คัดลอกไฟล์ตัวอย่างก่อน:

```bash
cp .env.example .env
```

จากนั้นเปิด `.env` และแทนค่าตัวอย่างด้วยข้อมูลจากผู้ให้บริการ:

```dotenv
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ip_std6730202581
MYSQL_USER=ใส่ชื่อผู้ใช้ฐานข้อมูล
MYSQL_PASSWORD=ใส่รหัสผ่านฐานข้อมูล
MYSQL_CHARSET=utf8mb4
```

`localhost` ใช้ได้เมื่อ Backend ทำงานบนเซิร์ฟเวอร์เดียวกับ MySQL เท่านั้น ถ้า Backend
ทำงานบนเครื่องอื่น ให้ใช้ Remote MySQL Host จากผู้ให้บริการและเปิด Remote MySQL Access
สำหรับ IP ของเครื่อง Backend

## ตั้งผู้ใช้เป็น Admin

สมัครสมาชิกผ่านหน้าเว็บก่อน แล้วรัน:

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
