export const CHAT_GREETING = 'สวัสดีครับ ส่งลิงก์ที่สงสัยให้ผมช่วยตรวจ หรือถามเรื่อง phishing ได้เลยครับ';

export function extractChatUrls(message) {
  const explicit = message.match(/https?:\/\/[^\s<>"'“”]+/gi) || [];
  const bare = message.trim().match(/^(?:www\.)?[\p{L}\d-]+(?:\.[\p{L}\d-]+)+(?:[/?#][^\s]*)?$/u);
  return [...new Set((explicit.length ? explicit : bare ? [bare[0]] : []).map(value => {
    const cleaned = value.replace(/[.,!?;:)}\]。、]+$/, '');
    return /^https?:\/\//i.test(cleaned) ? cleaned : `https://${cleaned}`;
  }))];
}

export function basicChatReply(message, result) {
  const question = message.toLowerCase();
  if (/(กด|คลิก|กรอก|โดน|หลง|clicked|entered)/.test(question)) {
    return 'หากเผลอเปิดลิงก์ ให้ปิดหน้าเว็บและอย่าดาวน์โหลดไฟล์ หากกรอกรหัสผ่านแล้ว ให้เปลี่ยนผ่านแอปหรือเว็บไซต์ทางการและออกจากเซสชันที่ไม่รู้จัก หากให้ข้อมูลการเงิน ให้ติดต่อธนาคารผ่านช่องทางทางการทันที อย่าส่งรหัสผ่านหรือ OTP ในแชทนี้ครับ';
  }
  if (/(ผลตรวจ|คะแนน|ทำไม|เหตุผล|ลิงก์นี้|เว็บนี้|ต่อ|why|score)/.test(question) && result) {
    const reasons = (result.reasons || []).map(reason => typeof reason === 'string' ? reason : [reason.label, reason.detail].filter(Boolean).join(': ')).filter(Boolean);
    return `ผลตรวจล่าสุดได้ ${result.riskScore ?? result.finalScore}/100${result.modelStatus !== 'ready' ? ' เป็นผลตรวจเบื้องต้นจากกฎ ยังไม่มีผลโมเดลที่พร้อมใช้งาน' : ''}\n\n${reasons.length ? reasons.slice(0, 4).join('\n') : 'ระบบไม่ได้ส่งเหตุผลเพิ่มเติมมา จึงยังอธิบายเจาะจงกว่านี้ไม่ได้'}\n\nคะแนนต่ำไม่ได้ยืนยันว่าปลอดภัย ควรเปิดบริการผ่านแอปหรือพิมพ์โดเมนทางการด้วยตนเองก่อนกรอกข้อมูลครับ`;
  }
  if (/(ตรวจ|เช็ค|เช็ก|ลิงก์|url|link)/.test(question)) {
    return 'ส่งลิงก์ http:// หรือ https:// มาได้ครั้งละหนึ่งลิงก์ครับ ผมจะเรียกระบบตรวจสอบแล้วแสดงคะแนนและเหตุผล ไม่ต้องเปิดลิงก์นั้นเอง';
  }
  if (/(phish|ฟิชช|เว็บปลอม|หลอก|sms|อีเมล|email|สังเกต)/.test(question)) {
    return 'Phishing คือการปลอมเป็นบุคคลหรือบริการที่น่าเชื่อถือ เพื่อหลอกให้เปิดลิงก์ ส่งข้อมูล หรือโอนเงิน\n\nสังเกตโดเมนสะกดผิด ข้อความเร่งด่วน ของรางวัล และการขอรหัสผ่านหรือ OTP แม้มี HTTPS ก็อาจเป็นเว็บหลอกลวงได้ ควรตรวจสอบกับผู้ส่งผ่านช่องทางที่รู้จักครับ';
  }
  return 'ผมช่วยอธิบายเรื่อง phishing และตรวจลิงก์ได้ครับ ลองถาม “Phishing คืออะไร” หรือส่ง URL มา หากต้องการวิเคราะห์ข้อความเฉพาะกรณี ต้องใช้ AI ที่พร้อมใช้งาน และควรลบข้อมูลส่วนตัวออกก่อนครับ';
}
