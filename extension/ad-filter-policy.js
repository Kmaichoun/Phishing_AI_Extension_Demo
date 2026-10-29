/*
 * Local-only presentation filtering. A match is a reason to hide
 * an advertisement, not proof of phishing or a replacement for URL scoring.
 */
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.PhishRadarAdFilterPolicy = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const GAMBLING = [
    'casino', 'bet', 'betting', 'sportsbook', 'slot game', 'slots',
    'บาคาร่า', 'สล็อต', 'พนัน', 'แทงบอล', 'หวยออนไลน์', 'คาสิโน', 'เดิมพัน'
  ];
  const PROMOTION = [
    'sign up', 'signup', 'register', 'join now', 'bonus', 'deposit', 'withdraw',
    'free credit', 'cashback', 'สมัคร', 'สมาชิก', 'โบนัส', 'เครดิตฟรี',
    'ฝากถอน', 'ฝากเงิน', 'ถอนเงิน', 'คืนยอดเสีย', 'ชวนเพื่อน', 'แจกเงิน'
  ];
  const SCAM_CLAIM = [
    'guaranteed profit', 'risk free profit', 'double your money', 'free money',
    'you have won', "you've won", 'you are a winner',
    'คุณได้รับรางวัล', 'คุณชนะรางวัล', 'แจกเงินฟรี', 'รับประกันกำไร',
    'กำไรแน่นอน', 'รวยเร็ว'
  ];
  const CLAIM_ACTION = [
    'claim', 'deposit', 'pay now', 'transfer money', 'invest now', 'sign up',
    'signup', 'register', 'รับรางวัล', 'คลิกรับ', 'โอนเงินก่อน', 'ลงทุน', 'สมัคร'
  ];
  const CREDENTIAL_ACTION = [
    'verify your account', 'verify account', 'confirm your account',
    'enter password', 'enter your password', 'enter otp', 'enter your otp',
    'seed phrase', 'recovery phrase', 'private key', 'ยืนยันบัญชี',
    'กรอกรหัสผ่าน', 'กรอก otp', 'กรอกotp', 'กรอกรหัส otp', 'คำกู้คืน'
  ];
  const UPDATE_BAIT = [
    'install player', 'download player', 'install codec', 'video codec',
    'flash update', 'browser update', 'chrome update',
    'ติดตั้งโปรแกรมเพื่อดู', 'ติดตั้งตัวเล่น', 'อัปเดตเบราว์เซอร์',
    'อัพเดทเบราว์เซอร์'
  ];
  const UPDATE_PRESSURE = [
    'required', 'must install', 'out of date', 'outdated', 'to continue',
    'to watch', 'จำเป็น', 'ต้องติดตั้ง', 'ก่อนดู', 'เพื่อดู', 'เวอร์ชันเก่า'
  ];
  // These exact official domains also exist in the URL analyzer. Common-word
  // aliases (e.g. "line", "office", "wallet") are deliberately omitted.
  const BRANDS = [
    { words: ['google', 'gmail'], domains: ['google.com', 'gmail.com'] },
    { words: ['facebook'], domains: ['facebook.com', 'fb.com', 'meta.com', 'meta.ai', 'messenger.com'] },
    { words: ['paypal'], domains: ['paypal.com', 'paypal.me'] },
    { words: ['microsoft', 'outlook'], domains: ['microsoft.com', 'live.com', 'outlook.com', 'microsoftonline.com'] },
    { words: ['apple', 'icloud'], domains: ['apple.com', 'icloud.com'] }
  ];

  function boundedString(value) {
    return typeof value === 'string' ? value.slice(0, 4000).normalize('NFKC').toLowerCase() : '';
  }

  function containsTerm(text, term) {
    if (!/[a-z0-9]/i.test(term)) return text.includes(term);
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+');
    return new RegExp('(?:^|[^a-z0-9])' + escaped + '(?=$|[^a-z0-9])', 'i').test(text);
  }

  function containsAny(text, terms) {
    return terms.some(term => containsTerm(text, term));
  }

  function parseHttpUrl(value, base) {
    if (typeof value !== 'string' || !value.trim() || value.length > 8192) return null;
    try {
      const parsed = new URL(value, base);
      return /^https?:$/.test(parsed.protocol) ? parsed : null;
    } catch (_) {
      return null;
    }
  }

  function isDomain(hostname, domain) {
    return hostname === domain || hostname.endsWith('.' + domain);
  }

  function samePublisher(hostname, otherHostname) {
    return hostname.replace(/^www\./, '').replace(/\.$/, '') === otherHostname.replace(/^www\./, '').replace(/\.$/, '');
  }

  function classifyCandidate(candidate) {
    if (!candidate || typeof candidate !== 'object') return { hide: false, reasons: [] };
    const presentedAsAd = candidate.adLike === true || (candidate.overlay === true && candidate.media === true);
    if (!presentedAsAd || candidate.hasForm === true) return { hide: false, reasons: [] };

    const page = parseHttpUrl(candidate.pageUrl);
    const target = parseHttpUrl(candidate.targetUrl, page && page.href);
    // Leave first-party navigation, invalid/missing destinations and normal
    // script controls intact. A shortened/external URL alone is insufficient.
    if (!page || !target || samePublisher(target.hostname, page.hostname)) return { hide: false, reasons: [] };

    if (candidate.mode === 'all' && candidate.identifiedAd === true) {
      return { hide: true, reasons: ['ตรวจพบช่องโฆษณาหรือภาพแบนเนอร์ลิงก์ออกนอกเว็บ ซ่อนตามโหมดโฆษณาทั้งหมด ไม่ใช่การยืนยันว่าเป็น phishing'] };
    }

    let path = target.pathname;
    try { path = decodeURIComponent(path); } catch (_) { /* Use the literal path. */ }
    const context = [candidate.text, candidate.label, candidate.attributes]
      .map(boundedString).join(' ').slice(0, 8000);
    const destination = boundedString(target.hostname + ' ' + path);
    const evidence = context + ' ' + destination;
    const reasons = [];

    if (containsAny(evidence, GAMBLING) && containsAny(evidence, PROMOTION)) {
      reasons.push('โฆษณามีข้อความการพนันร่วมกับการชวนสมัครหรือรับโบนัส และลิงก์ออกนอกเว็บ');
    }
    if (containsAny(context, SCAM_CLAIM) && containsAny(context, CLAIM_ACTION)) {
      reasons.push('โฆษณาอ้างรางวัลหรือผลตอบแทนแน่นอน พร้อมชวนรับสิทธิ์ สมัคร หรือโอนเงิน');
    }

    const namedBrands = BRANDS.filter(brand => containsAny(evidence, brand.words));
    const officialBrandTarget = BRANDS.some(brand => brand.domains.some(domain => isDomain(target.hostname, domain)));
    if (namedBrands.length && !officialBrandTarget && containsAny(context, CREDENTIAL_ACTION)) {
      reasons.push('โฆษณาขอให้ยืนยันบัญชีหรือกรอกข้อมูลสำคัญ แต่ปลายทางไม่ใช่โดเมนทางการของแบรนด์ที่อ้าง');
    }

    const credentialInUrl = Array.from(target.searchParams.keys()).some(key =>
      /^(?:password|passwd|otp|seed|seed_phrase|recovery_phrase|private_key)$/i.test(key));
    if (credentialInUrl && containsAny(context, CREDENTIAL_ACTION)) {
      reasons.push('โฆษณาชวนกรอกข้อมูลสำคัญ และลิงก์มีช่องข้อมูลรหัสผ่านหรือรหัสยืนยันใน URL');
    }

    if (containsAny(context, UPDATE_BAIT) && containsAny(context, UPDATE_PRESSURE) && !officialBrandTarget) {
      reasons.push('โฆษณาเร่งให้ติดตั้งหรืออัปเดตโปรแกรมเพื่อดูเนื้อหา ผ่านลิงก์นอกเว็บ');
    }
    return { hide: reasons.length > 0, reasons };
  }

  return Object.freeze({ classifyCandidate });
});
