# ฐานข้อมูลสมาชิกสำหรับ SQL Server

สคริปต์ migration อยู่ที่:

    database/sqlserver/migrations/001_create_auth_schema.sql
    database/sqlserver/migrations/002_create_auth_sessions.sql
    database/sqlserver/migrations/003_create_search_history.sql

ให้รันตามลำดับ 001, 002 และ 003 เพื่อสร้างฐานข้อมูล PhishRadarDB, schema ชื่อ auth และตาราง Users, UserDevices, Sessions, SearchHistory ระบบไม่สร้างบัญชี Admin อัตโนมัติ

ถ้าใช้ Git Bash สามารถรัน migration ทั้งหมดแบบ idempotent ได้จาก root ของโปรเจกต์:

    ./migrate-db.sh

## ตารางที่สร้าง

### auth.Users

- UserId — รหัสผู้ใช้แบบ BIGINT IDENTITY
- Username — ชื่อที่ใช้เข้าสู่ระบบ
- PasswordHash — รหัสผ่านที่ผ่าน Argon2id แล้ว ห้ามเก็บรหัสผ่านจริง
- Email — อีเมล
- Role — user หรือ admin โดยค่าเริ่มต้นเป็น user
- IsActive — เปิดหรือระงับบัญชี
- EmailVerified — สถานะยืนยันอีเมล
- CreatedAt, UpdatedAt, LastLoginAt — เวลาที่เกี่ยวข้องกับบัญชี

Username และ Email มี normalized computed columns และ unique indexes เพื่อป้องกันข้อมูลซ้ำโดยไม่สนตัวพิมพ์ใหญ่-เล็ก

### auth.UserDevices

ผู้ใช้หนึ่งคนสามารถมีหลายอุปกรณ์ได้ ตารางนี้จึงแยกจาก Users และเชื่อมด้วย UserId

- UserDeviceId — รหัสรายการอุปกรณ์
- UserId — foreign key ไปยัง auth.Users
- DeviceName — ชื่ออุปกรณ์ที่แสดงให้ผู้ใช้เห็น
- DeviceKeyHash — SHA-256 ขนาด 32 bytes สำหรับระบุอุปกรณ์โดยไม่เก็บ device secret ดิบ
- IsTrusted — ผู้ใช้ยืนยันว่าเชื่อถืออุปกรณ์นี้หรือไม่
- IsRevoked, RevokedAt — ยกเลิกสิทธิ์อุปกรณ์
- FirstSeenAt, LastSeenAt — เวลาเชื่อมต่อครั้งแรกและล่าสุด

DeviceName เป็นข้อมูลเพื่อแสดงผลเท่านั้น ไม่ควรใช้เป็นหลักฐานยืนยันตัวตน เพราะหลายอุปกรณ์อาจใช้ชื่อเหมือนกันได้ ควรให้ผู้ใช้ตั้งชื่อเอง เช่น `Notebook ส่วนตัว` หรือใช้ชื่อกว้าง ๆ เช่น `Chrome บน Windows` แทนการพยายามอ่านชื่อเครื่องจริง

DeviceKeyHash ควรมาจาก hash ของ random device token ที่ระบบสร้างหลัง Login ไม่ใช่ hardware fingerprint และห้ามเก็บ token ดิบลงฐานข้อมูล

### auth.Sessions

- SessionId — รหัส session ภายใน
- UserId, UserDeviceId — บัญชีและอุปกรณ์ของ session
- TokenHash — SHA-256 hash ของ token สุ่ม ระบบไม่เก็บ token จริงในฐานข้อมูล
- CreatedAt, LastSeenAt, ExpiresAt, RevokedAt — อายุและสถานะการใช้งาน session

### auth.SearchHistory

- ผูกประวัติกับ UserId และ UserDeviceId ของ session ที่ล็อกอิน
- เก็บ URL ที่ตัด credentials, query string และ fragment ออกแล้ว
- เก็บ SHA-256 ของ URL ต้นฉบับเพื่อ correlation โดยไม่เก็บ query string ดิบ
- เก็บ RuleScore, MLScore, FinalScore, alpha, threshold และ detection label
- ค่าเริ่มต้นเก็บย้อนหลัง 90 วัน ปรับได้ด้วย `SEARCH_HISTORY_RETENTION_DAYS`

## วิธีรันผ่าน SSMS

1. เปิด SQL Server Management Studio
2. เชื่อมต่อ instance เช่น .\SQLEXPRESS ด้วย Windows Authentication
3. เลือก File > Open > File
4. เปิดไฟล์ 001_create_auth_schema.sql ตรวจว่าชื่อฐานข้อมูล PhishRadarDB ถูกต้อง แล้วกด Execute
5. เปิดไฟล์ 002_create_auth_sessions.sql แล้วกด Execute
6. เปิดไฟล์ 003_create_search_history.sql แล้วกด Execute

สคริปต์สามารถรันซ้ำได้โดยไม่ลบตารางหรือข้อมูลเดิม

ตรวจผลหลังรัน:

    USE [PhishRadarDB];
    GO

    SELECT * FROM [auth].[Users];
    SELECT * FROM [auth].[UserDevices];
    SELECT * FROM [auth].[Sessions];
    SELECT * FROM [auth].[SearchHistory] ORDER BY [CreatedAt] DESC;

## การสร้าง Admin

อย่า INSERT บัญชี Admin ด้วย password ดิบใน SSMS ให้สมัครบัญชีผ่านหน้า Register เพื่อให้ Backend สร้าง PasswordHash ก่อน แล้วจึงเลื่อนสิทธิ์ด้วยคำสั่ง:

    USE [PhishRadarDB];
    GO

    UPDATE [auth].[Users]
    SET
        [Role] = N'admin',
        [UpdatedAt] = SYSUTCDATETIME()
    WHERE [NormalizedEmail] = LOWER(N'your-email@example.com');

    IF @@ROWCOUNT <> 1
        THROW 50001, 'Expected exactly one user to be promoted.', 1;
    GO

ควรใช้คำสั่งนี้เฉพาะครั้งแรก หลังจากนั้นการเปลี่ยนสิทธิ์ควรทำผ่าน Admin API พร้อม audit log
