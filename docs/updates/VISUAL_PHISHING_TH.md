# Visual Phishing Detection Update

> เอกสารนี้เป็นบันทึกการทดลองเดิม ไฟล์ `test-sites/fake-google-visual.html` ที่กล่าวถึงด้านล่างไม่ได้รวมอยู่ใน runtime v2.0

เพิ่มการตรวจจับแบบดูหน้าตาเว็บ ไม่ใช่ดูแค่ URL

## ระบบตรวจอะไรเพิ่ม

1. ตรวจสัญญาณแบรนด์จากหน้าเว็บ
   - โลโก้หรือรูปที่มีชื่อแบรนด์
   - title / heading ที่อ้างถึง Google, Facebook, Microsoft, ธนาคาร ฯลฯ
   - ปุ่ม login / verify / continue
   - ช่องรหัสผ่าน, OTP, PIN, ข้อมูลบัตร หรือ seed phrase

2. เปรียบเทียบกับโดเมนจริง
   - ถ้าหน้ามีหน้าตาเหมือนแบรนด์จริง แต่โดเมนไม่ใช่โดเมนทางการ ระบบจะเพิ่มเหตุผลเป็น visual-brand

3. ชี้หลักฐานบนหน้าเว็บ
   - เมื่อเปิดปุ่ม "ชี้จุดเสี่ยง" ระบบจะ highlight logo/heading/ปุ่ม/ช่องกรอกที่ทำให้ระบบสงสัย

## จุดสำคัญ

เวอร์ชันนี้เป็น visual phishing detection แบบ lightweight ที่ใช้ DOM และสิ่งที่ผู้ใช้มองเห็นในหน้าเว็บ จึงทำงานใน extension ได้ทันทีและไม่กิน token ของ LLM

ถ้าจะต่อยอดระดับงานวิจัย สามารถเพิ่ม screenshot similarity / perceptual hash / embedding เทียบกับภาพหน้า login จริงของแบรนด์ได้ในขั้นถัดไป

## วิธีทดสอบ

1. Reload extension ที่ chrome://extensions
2. เปิดไฟล์เดโม: test-sites/fake-google-visual.html
3. โฟกัสช่อง password หรือเปิดหน้าเว็บจนระบบเตือน
4. กด "ชี้จุดเสี่ยง" จะเห็นหลักฐาน visual phishing บนหน้าเว็บ
