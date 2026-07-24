/*
  Phish Radar AI-Lite Analyzer v1.2
  ------------------------------------------------------------
  Demo-only URL + DOM risk scoring engine. It DOES NOT call external APIs
  and DOES NOT use a trained ML model. The goal is to demonstrate a clear,
  explainable phishing detection pipeline for a seminar/project prototype.
*/
(function (global) {
  'use strict';

  const BRAND_PROFILES = [
    { brand: 'google', aliases: ['gmail', 'youtube'], officialDomains: ['google.com', 'gmail.com', 'youtube.com', 'accounts.google.com', 'mail.google.com'] },
    { brand: 'facebook', aliases: ['fb', 'meta'], officialDomains: ['facebook.com', 'fb.com', 'meta.com', 'messenger.com'] },
    { brand: 'instagram', aliases: ['ig'], officialDomains: ['instagram.com'] },
    { brand: 'tiktok', aliases: ['tik tok'], officialDomains: ['tiktok.com'] },
    { brand: 'medium', aliases: [], officialDomains: ['medium.com'] },
    { brand: 'twitter', aliases: [], officialDomains: ['x.com', 'twitter.com'] },
    { brand: 'line', aliases: ['line'], officialDomains: ['line.me', 'linecorp.com', 'today.line.me'] },
    { brand: 'paypal', aliases: ['pay pal'], officialDomains: ['paypal.com', 'paypal.me'] },
    { brand: 'apple', aliases: ['icloud'], officialDomains: ['apple.com', 'icloud.com'] },
    { brand: 'microsoft', aliases: ['office', 'outlook', 'onedrive'], officialDomains: ['microsoft.com', 'live.com', 'outlook.com', 'office.com', 'office365.com', 'microsoftonline.com', 'login.microsoftonline.com'] },
    { brand: 'amazon', aliases: ['aws'], officialDomains: ['amazon.com', 'amazon.co.th', 'amazonaws.com', 'aws.amazon.com'] },
    { brand: 'netflix', aliases: [], officialDomains: ['netflix.com'] },
    { brand: 'steam', aliases: ['steampowered'], officialDomains: ['steampowered.com', 'steamcommunity.com'] },
    { brand: 'discord', aliases: [], officialDomains: ['discord.com', 'discord.gg'] },
    { brand: 'binance', aliases: [], officialDomains: ['binance.com'] },
    { brand: 'kbank', aliases: ['kasikorn', 'kasikornbank'], officialDomains: ['kbank.co.th', 'kasikornbank.com'] },
    { brand: 'scb', aliases: ['scbeasy', 'siamcommercial'], officialDomains: ['scb.co.th', 'scbeasy.com'] },
    { brand: 'krungsri', aliases: ['bay'], officialDomains: ['krungsri.com', 'bankofayudhya.com'] },
    { brand: 'ttb', aliases: ['tmb', 'thanachart'], officialDomains: ['ttbbank.com', 'ttb.co.th'] },
    { brand: 'krungthai', aliases: ['ktb'], officialDomains: ['krungthai.com', 'ktb.co.th'] },
    { brand: 'truemoney', aliases: ['truewallet', 'wallet'], officialDomains: ['truemoney.com', 'truemoney.co.th'] },
    { brand: 'promptpay', aliases: [], officialDomains: ['promptpay.io'] },
    { brand: 'shopee', aliases: ['shopeepay'], officialDomains: ['shopee.co.th', 'shopee.com', 'shopeepay.co.th'] },
    { brand: 'lazada', aliases: [], officialDomains: ['lazada.co.th', 'lazada.com'] }
  ];

  const KNOWN_BRANDS = BRAND_PROFILES.flatMap(p => [p.brand, ...p.aliases]).filter(Boolean);

  const SUSPICIOUS_KEYWORDS = [
    'login', 'signin', 'sign-in', 'verify', 'verification', 'secure', 'security',
    'account', 'update', 'confirm', 'unlock', 'wallet', 'banking', 'payment',
    'billing', 'support', 'helpdesk', 'password', 'passwd', 'otp', '2fa', 'mfa',
    'reset', 'limited', 'suspend', 'suspended', 'locked', 'gift', 'bonus', 'claim',
    'airdrop', 'free', 'urgent', 'reward', 'prize', 'refund', 'invoice', 'kyc',
    'validate', 'restore', 'appeal', 'risk', 'safe', 'protect', 'admin', 'webscr',
    'auth', 'authentication', 'session', 'token', 'seed', 'phrase', 'privatekey',
    'ยืนยัน', 'บัญชี', 'รหัสผ่าน', 'โอนเงิน', 'รับเงิน', 'ด่วน', 'ล็อกอิน', 'OTP'
  ];

  const CREDENTIAL_KEYWORDS = [
    'password', 'passwd', 'otp', '2fa', 'mfa', 'token', 'credential', 'seed',
    'recovery-phrase', 'privatekey', 'private-key', 'session', 'auth', 'pin',
    'รหัสผ่าน', 'รหัส', 'otp', 'โค้ด', 'seed phrase'
  ];

  const PRESSURE_WORDS = [
    'urgent', 'immediately', 'within 24 hours', 'suspended', 'locked',
    'verify your account', 'your account will be closed', 'limited time',
    'unusual activity', 'security alert', 'final warning', 'ด่วน',
    'ภายใน 24 ชั่วโมง', 'บัญชีถูกระงับ', 'บัญชีถูกล็อก', 'ยืนยันบัญชี',
    'ระงับบัญชี', 'รับสิทธิ์', 'ของรางวัล', 'แจ้งเตือนความปลอดภัย'
  ];

  const TLD_RISK = new Set([
    'zip', 'mov', 'top', 'xyz', 'click', 'link', 'country', 'stream', 'gq', 'tk',
    'ml', 'cf', 'rest', 'monster', 'quest', 'work', 'cam', 'icu', 'cfd', 'cyou',
    'buzz', 'fit', 'kim', 'lol', 'mom', 'sbs', 'skin', 'surf', 'tokyo'
  ]);

  const SHORTENERS = [
    'bit.ly', 'tinyurl.com', 't.co', 'goo.gl', 'is.gd', 'cutt.ly', 'shorturl.at',
    'rebrand.ly', 'buff.ly', 'ow.ly', 's.id', 'lnkd.in', 'rb.gy', 'tiny.cc'
  ];

  const FREE_HOSTING_OR_DDNS = [
    'github.io', 'pages.dev', 'netlify.app', 'vercel.app', 'web.app', 'firebaseapp.com',
    'glitch.me', '000webhostapp.com', 'weebly.com', 'wixsite.com', 'blogspot.com',
    'duckdns.org', 'no-ip.org', 'ddns.net', 'hopto.org', 'serveo.net', 'ngrok-free.app'
  ];

  const SUSPICIOUS_FILE_EXTENSIONS = [
    '.exe', '.scr', '.bat', '.cmd', '.com', '.pif', '.vbs', '.js', '.jse', '.wsf',
    '.ps1', '.msi', '.apk', '.dmg', '.iso', '.img', '.jar', '.hta', '.lnk'
  ];

  const ARCHIVE_EXTENSIONS = ['.zip', '.rar', '.7z', '.tar', '.gz'];


  // Search-result context rules: not every adult/spam result is phishing, but
  // adult keywords appearing on unrelated .org/.edu/CMS upload/PDF results are a
  // common sign of SEO spam, compromised pages, or risky redirects.
  const ADULT_SEO_KEYWORDS = [
    'porn', 'porno', 'pornhub', 'xvideos', 'xnxx', 'xhamster', 'xxx', 'adult',
    'sex videos', 'sex video', '18+', '+18', 'viral', 'droba', 'seks', 'sexy',
    'หนังโป๊', 'คลิปหลุด', 'ผู้ใหญ่'
  ];

  const ADULT_CONTENT_DOMAINS = [
    'xvideos.com', 'xnxx.com', 'pornhub.com', 'xhamster.com', 'redtube.com', 'youporn.com'
  ];

  // v1.2: broader risky-content categories for seminar demo. These are NOT
  // content-moderation labels and do not prove a site is illegal; they are
  // explainable signals for "ควรระวังก่อนเปิด" beyond phishing only.
  const MALWARE_CONTENT_KEYWORDS = [
    'malware', 'virus', 'trojan', 'ransomware', 'spyware', 'keylogger', 'stealer',
    'crack', 'keygen', 'activator', 'serial key', 'license crack', 'patch.exe',
    'setup.exe', 'download player', 'video codec', 'flash update', 'chrome update',
    'browser update', 'driver update', 'mod apk', 'apk download', 'free download',
    'torrent', 'โปรแกรมแครก', 'ตัวเปิดใช้งาน', 'ไวรัส', 'มัลแวร์', 'โทรจัน',
    'แครก', 'ดาวน์โหลด apk', 'โหลดโปรแกรมฟรี'
  ];

  const SCAM_CONTENT_KEYWORDS = [
    'get rich', 'make money fast', 'guaranteed profit', 'risk free profit',
    'double your money', 'investment bonus', 'giveaway', 'airdrop', 'claim reward',
    'claim prize', 'free money', 'loan approved', 'quick loan', 'work from home income',
    'รายได้เสริม', 'รายได้ดี', 'รวยเร็ว', 'กำไรแน่นอน', 'รับประกันกำไร',
    'ลงทุนผลตอบแทนสูง', 'แจกเงินฟรี', 'กู้เงินด่วน', 'ปล่อยกู้', 'อนุมัติไว',
    'เครดิตฟรี', 'รับรางวัล', 'รับสิทธิ์ฟรี', 'งานออนไลน์', 'โอนเงินก่อน'
  ];

  const GAMBLING_CONTENT_KEYWORDS = [
    'casino', 'slots', 'slot game', 'betting', 'sportsbook', 'บาคาร่า', 'สล็อต',
    'พนัน', 'แทงบอล', 'หวยออนไลน์', 'คาสิโน', 'เว็บพนัน', 'เดิมพัน', 'ฝากถอน'
  ];

  const SENSITIVE_ADULT_CONTEXT_KEYWORDS = [
    ...ADULT_SEO_KEYWORDS, 'leak video', 'คลิปหลุด', '18 video', 'adult video'
  ];

  const CMS_UPLOAD_PATTERNS = [
    'wp-content', 'wpforms', 'wpcf7-files', '/tmp/', '/temp/', '/uploads/', '/files/', '/publication/', '/publicacao/'
  ];

  const IGNORE_BRAND_TOKEN_MATCH = new Set([
    'www', 'www2', 'www3', 'm', 'mobile', 'web', 'app', 'api', 'cdn', 'static',
    'img', 'assets', 'mail', 'email', 'login', 'signin', 'auth', 'account',
    'secure', 'security', 'support', 'help', 'service', 'shop', 'blog'
  ]);

  function normalizeUrl(input) {
    if (!input) return null;
    try {
      return new URL(input, (typeof location !== 'undefined' ? location.href : 'https://example.com'));
    } catch (e) {
      try { return new URL('https://' + input); } catch (_) { return null; }
    }
  }

  function safeDecode(str) {
    try { return decodeURIComponent(str); } catch (_) { return String(str || ''); }
  }

  function getRegistrableGuess(hostname) {
    const clean = String(hostname || '').toLowerCase().replace(/^www\./, '').replace(/\.$/, '');
    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(clean) || clean.includes(':')) return clean;
    const parts = clean.split('.').filter(Boolean);
    if (parts.length <= 2) return parts.join('.');
    const last2 = parts.slice(-2).join('.');
    const last3 = parts.slice(-3).join('.');
    const multiLevelSuffixes = new Set(['co.th', 'ac.th', 'go.th', 'or.th', 'in.th', 'co.uk', 'org.uk', 'ac.uk', 'com.au', 'co.jp']);
    if (multiLevelSuffixes.has(last2)) return last3;
    return last2;
  }

  function isSubdomainOrSame(host, domain) {
    host = String(host || '').replace(/^www\./, '').toLowerCase();
    domain = String(domain || '').replace(/^www\./, '').toLowerCase();
    return host === domain || host.endsWith('.' + domain);
  }

  function officialProfilesForHost(hostname) {
    return BRAND_PROFILES.filter(profile => profile.officialDomains.some(d => isSubdomainOrSame(hostname, d)));
  }

  function levenshtein(a, b) {
    a = String(a || ''); b = String(b || '');
    const dp = Array.from({ length: a.length + 1 }, () => Array(b.length + 1).fill(0));
    for (let i = 0; i <= a.length; i++) dp[i][0] = i;
    for (let j = 0; j <= b.length; j++) dp[0][j] = j;
    for (let i = 1; i <= a.length; i++) {
      for (let j = 1; j <= b.length; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        dp[i][j] = Math.min(dp[i - 1][j] + 1, dp[i][j - 1] + 1, dp[i - 1][j - 1] + cost);
      }
    }
    return dp[a.length][b.length];
  }

  function skeleton(str) {
    return String(str || '').toLowerCase()
      .normalize('NFKD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[0οо]/g, 'o')
      .replace(/[1!|ιіӏ]/g, 'l')
      .replace(/[3]/g, 'e')
      .replace(/[4@]/g, 'a')
      .replace(/[5$]/g, 's')
      .replace(/[7]/g, 't')
      .replace(/[8]/g, 'b')
      .replace(/[9]/g, 'g')
      .replace(/rn/g, 'm')
      .replace(/vv/g, 'w')
      .replace(/[^a-z0-9]/g, '');
  }

  function shannonEntropy(str) {
    str = String(str || '');
    if (!str) return 0;
    const counts = {};
    for (const ch of str) counts[ch] = (counts[ch] || 0) + 1;
    let entropy = 0;
    for (const ch in counts) {
      const p = counts[ch] / str.length;
      entropy -= p * Math.log2(p);
    }
    return entropy;
  }

  function hasPrivateIp(hostname) {
    const m = String(hostname).match(/^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/);
    if (!m) return false;
    const [a, b] = m.slice(1).map(Number);
    return a === 10 || a === 127 || (a === 192 && b === 168) || (a === 172 && b >= 16 && b <= 31);
  }

  function addReason(reasons, points, label, detail = '', category = 'general') {
    reasons.push({ points, label, detail, category });
  }

  function findKeywordHits(text, list, limit = 8) {
    const lower = String(text || '').toLowerCase();
    const hits = [];
    for (const raw of list) {
      const key = String(raw || '').toLowerCase();
      if (!key || hits.includes(raw)) continue;
      if (lower.includes(key)) hits.push(raw);
      if (hits.length >= limit) break;
    }
    return hits;
  }

  function classify(score) {
    if (score >= 81) return { level: 'critical', text: 'อันตรายมาก' };
    if (score >= 61) return { level: 'high', text: 'เสี่ยงสูง' };
    if (score >= 31) return { level: 'medium', text: 'น่าสงสัย' };
    return { level: 'low', text: 'ปลอดภัย' };
  }

  function deriveThreatTypes(reasons) {
    const cats = new Set((reasons || []).filter(r => r.points > 0).map(r => r.category));
    const out = [];
    if (cats.has('brand') || cats.has('credential') || cats.has('form') || cats.has('combo')) out.push('Phishing / ขโมยข้อมูล');
    if (cats.has('malware-content') || cats.has('download')) out.push('Malware / ไฟล์เสี่ยง');
    if (cats.has('scam-content') || cats.has('gambling-content') || cats.has('crypto-content')) out.push('Scam / Fraud');
    if (cats.has('adult-content') || cats.has('search-context')) out.push('SEO Spam / เนื้อหาอ่อนไหว');
    if (cats.has('redirect')) out.push('Redirect / ปลายทางไม่ชัดเจน');
    if (cats.has('transport')) out.push('No HTTPS');
    return out.length ? out.slice(0, 4) : ['ไม่พบกลุ่มความเสี่ยงสำคัญ'];
  }

  function findRedirectTargets(url, search) {
    const results = [];
    for (const [key, value] of url.searchParams.entries()) {
      const k = key.toLowerCase();
      const v = safeDecode(value);
      if (/^(url|u|redirect|redirect_uri|next|target|to|continue|return|returnurl|dest|destination)$/i.test(k) || /^https?:\/\//i.test(v)) {
        const nested = normalizeUrl(v);
        if (nested && nested.hostname && nested.hostname !== url.hostname) {
          results.push(`${key} → ${nested.hostname}`);
        }
      }
    }
    if (/https?%3a%2f%2f/i.test(search)) results.push('พบ URL ที่ถูก encode อยู่ใน query');
    return results;
  }

  function detectLinkTextMismatch(text, hostname) {
    const cleaned = String(text || '').replace(/\s+/g, ' ').trim();
    if (!cleaned) return null;
    const match = cleaned.match(/((?:https?:\/\/)?(?:www\.)?[a-z0-9.-]+\.[a-z]{2,})(?:\/\S*)?/i);
    if (!match) return null;
    const visible = normalizeUrl(match[1])?.hostname?.replace(/^www\./, '');
    const actual = String(hostname || '').replace(/^www\./, '');
    if (visible && actual && visible !== actual && !actual.endsWith('.' + visible) && !visible.endsWith('.' + actual)) {
      return `${visible} → ${actual}`;
    }
    return null;
  }

  function analyzeUrl(input, options = {}) {
    let url = normalizeUrl(input);
    const reasons = [];
    let score = 0;
    let localFileContextMode = false;

    if (!url) {
      return {
        input,
        url: String(input || ''),
        score: 100,
        level: 'high',
        levelText: 'เสี่ยงสูง',
        reasons: [{ points: 100, label: 'URL ไม่ถูกต้อง', detail: 'ระบบอ่านรูปแบบ URL ไม่ได้', category: 'parse' }],
        safe: false,
        summary: 'URL parse failed'
      };
    }

    if (!/^https?:$/.test(url.protocol)) {
      const hasPageContext = !!(
        options.pageHasPasswordForm ||
        Number(options.passwordFieldCount || 0) > 0 ||
        Number(options.otpFieldCount || 0) > 0 ||
        (Array.isArray(options.formIssues) && options.formIssues.length) ||
        options.pageText ||
        options.documentTitle
      );

      // For local classroom test pages opened as file://, continue scoring the
      // DOM/page context. This lets the extension demonstrate form protection
      // without hosting a real phishing site. Non-web pages without context stay safe.
      if (url.protocol === 'file:' && hasPageContext) {
        localFileContextMode = true;
        const virtualPath = String(url.pathname || '/').replace(/[^a-z0-9/_.,-]/gi, '-');
        url = new URL(`http://local-file-demo.invalid${virtualPath.startsWith('/') ? virtualPath : '/' + virtualPath}`);
      } else {
        return {
          input,
          url: url.href,
          hostname: url.hostname || url.protocol,
          domain: url.hostname || url.protocol,
          score: 0,
          level: 'low',
          levelText: 'ไม่ใช่หน้าเว็บปกติ',
          reasons: [{ points: 0, label: 'โปรโตคอลนี้ไม่ถูกตรวจแบบเว็บ', detail: url.protocol, category: 'protocol' }],
          safe: true,
          summary: 'Non-web URL'
        };
      }
    }

    const hrefRaw = url.href;
    const href = safeDecode(hrefRaw);
    const hostname = url.hostname.toLowerCase().replace(/\.$/, '');
    const pathname = safeDecode(url.pathname || '').toLowerCase();
    const search = safeDecode(url.search || '').toLowerCase();
    const fullLower = href.toLowerCase();
    const domainGuess = getRegistrableGuess(hostname);
    const domainLabel = domainGuess.split('.')[0] || hostname;
    const parts = hostname.split('.').filter(Boolean);
    const tld = parts[parts.length - 1] || '';
    const officialProfiles = officialProfilesForHost(hostname);
    const isKnownOfficial = officialProfiles.length > 0;
    const positiveBeforeTrust = () => reasons.filter(r => r.points > 0).reduce((sum, r) => sum + r.points, 0);
    const searchContextRaw = String(options.searchContextText || options.resultText || '').replace(/\s+/g, ' ').trim().slice(0, 1200);
    const searchContextLower = searchContextRaw.toLowerCase();
    const isAdultOfficialDomain = ADULT_CONTENT_DOMAINS.some(d => isSubdomainOrSame(hostname, d));
    const looksLikeCmsUpload = CMS_UPLOAD_PATTERNS.some(p => (pathname + '/' + search).includes(p));
    const pageTextLower = String(options.pageText || '').toLowerCase().slice(0, 8000);
    const visibleContextLower = String(options.linkText || options.visibleText || '').toLowerCase().slice(0, 700);
    const combinedContextLower = [fullLower, searchContextLower, visibleContextLower, pageTextLower].filter(Boolean).join(' ');

    if (localFileContextMode) {
      addReason(reasons, 0, 'โหมดจำลองไฟล์ในเครื่อง', 'ใช้สำหรับทดสอบฟอร์ม/ข้อความโดยไม่เข้าเว็บจริง', 'protocol');
    }

    if (url.protocol !== 'https:') {
      score += 18;
      addReason(reasons, 18, 'ไม่ได้ใช้ HTTPS', 'เว็บล็อกอิน/ชำระเงินควรเข้ารหัสข้อมูล', 'transport');
    }

    if (isKnownOfficial) {
      score -= 25;
      addReason(reasons, -25, 'โดเมนอยู่ในรายการทางการของแบรนด์', officialProfiles.map(p => p.brand).join(', '), 'trust');
    }

    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(hostname)) {
      score += 25;
      addReason(reasons, 25, 'ใช้ IP address แทนชื่อโดเมน', hostname, 'domain');
      if (!hasPrivateIp(hostname)) {
        score += 6;
        addReason(reasons, 6, 'เป็น public IP ที่ผู้ใช้จำได้ยาก', 'มักใช้หลอกให้ดูไม่ออกว่าเป็นเว็บใคร', 'domain');
      }
    }

    if (hasPrivateIp(hostname)) {
      score += 4;
      addReason(reasons, 4, 'เป็น private/local IP', 'อาจเป็นหน้าอุปกรณ์ภายในหรือเดโม ไม่ควรกรอกข้อมูลสำคัญหากไม่แน่ใจ', 'domain');
    }

    if (url.port && !['80', '443'].includes(url.port)) {
      score += 6;
      addReason(reasons, 6, 'ใช้พอร์ตที่ไม่ใช่มาตรฐาน', `:${url.port}`, 'domain');
    }

    if (hrefRaw.length > 120) {
      score += 14;
      addReason(reasons, 14, 'URL ยาวผิดปกติมาก', `${hrefRaw.length} ตัวอักษร`, 'url-shape');
    } else if (hrefRaw.length > 85) {
      score += 8;
      addReason(reasons, 8, 'URL ยาวกว่าปกติ', `${hrefRaw.length} ตัวอักษร`, 'url-shape');
    }

    if (hostname.length > 45) {
      score += 10;
      addReason(reasons, 10, 'ชื่อโฮสต์ยาวผิดปกติ', hostname, 'domain');
    }

    if (domainLabel.length > 24) {
      score += 8;
      addReason(reasons, 8, 'ชื่อโดเมนหลักยาวผิดปกติ', domainLabel, 'domain');
    }

    const longestLabel = parts.reduce((max, part) => part.length > max.length ? part : max, '');
    if (longestLabel.length > 32) {
      score += 8;
      addReason(reasons, 8, 'มี label ในโดเมนยาวผิดปกติ', longestLabel, 'domain');
    }

    const hyphenCount = (domainLabel.match(/-/g) || []).length;
    if (hyphenCount >= 3) {
      const points = Math.min(16, 6 + hyphenCount * 3);
      score += points;
      addReason(reasons, points, 'มีขีดกลางในชื่อโดเมนจำนวนมาก', `${hyphenCount} จุด`, 'domain');
    } else if (hyphenCount === 2) {
      score += 6;
      addReason(reasons, 6, 'มีขีดกลางในชื่อโดเมนหลายจุด', domainLabel, 'domain');
    }

    if (parts.length >= 5) {
      score += 14;
      addReason(reasons, 14, 'มี subdomain ซ้อนหลายชั้นมาก', hostname, 'domain');
    } else if (parts.length >= 4) {
      score += 9;
      addReason(reasons, 9, 'มี subdomain หลายชั้น', hostname, 'domain');
    }

    if (TLD_RISK.has(tld)) {
      score += 13;
      addReason(reasons, 13, 'นามสกุลโดเมนมีความเสี่ยงในบริบท phishing', `.${tld}`, 'domain');
    }

    if (hostname.includes('xn--')) {
      score += 24;
      addReason(reasons, 24, 'อาจใช้ตัวอักษรหลอกตาแบบ IDN/Punycode', hostname, 'homograph');
    }

    if (url.username || url.password) {
      score += 22;
      addReason(reasons, 22, 'URL มีเครื่องหมาย @ ในส่วน userinfo', 'อาจใช้ซ่อนปลายทางจริงหลังเครื่องหมาย @', 'url-shape');
    }

    if (/[\\]/.test(hrefRaw)) {
      score += 8;
      addReason(reasons, 8, 'URL มี backslash', 'อาจทำให้ผู้ใช้สับสนกับ path จริง', 'url-shape');
    }

    const encodedCount = (hrefRaw.match(/%[0-9a-f]{2}/gi) || []).length;
    if (encodedCount >= 8) {
      score += 10;
      addReason(reasons, 10, 'มีการ encode ตัวอักษรจำนวนมาก', `${encodedCount} จุด`, 'url-shape');
    }

    if ((hrefRaw.match(/https?:\/\//gi) || []).length > 1) {
      score += 12;
      addReason(reasons, 12, 'มี URL ซ้อนอยู่ใน URL', 'มักพบในลิงก์ redirect หลอกปลายทาง', 'redirect');
    }

    const redirectTargets = findRedirectTargets(url, search);
    if (redirectTargets.length) {
      score += 18;
      addReason(reasons, 18, 'พบพารามิเตอร์ redirect ไปโดเมนอื่น', redirectTargets.slice(0, 3).join(', '), 'redirect');
    }

    const pathDepth = pathname.split('/').filter(Boolean).length;
    if (pathDepth >= 6) {
      score += 8;
      addReason(reasons, 8, 'path ลึกหลายชั้น', `${pathDepth} ชั้น`, 'url-shape');
    }

    if (url.searchParams && Array.from(url.searchParams).length >= 7) {
      score += 8;
      addReason(reasons, 8, 'มี query parameters จำนวนมาก', `${Array.from(url.searchParams).length} รายการ`, 'url-shape');
    }

    if (/(password|passwd|otp|token|session|auth|credential|pin|seed|private.?key)=/i.test(search)) {
      score += 24;
      addReason(reasons, 24, 'URL อาจส่งข้อมูลลับผ่าน query string', 'พบ password/otp/token/session หรือคำใกล้เคียง', 'credential');
    }

    if (/[A-Za-z0-9+/=_-]{32,}/.test(search)) {
      score += 8;
      addReason(reasons, 8, 'พบ token/ข้อความยาวคล้ายรหัสใน query', 'ควรระวังลิงก์ session หรือ tracking หลอก', 'credential');
    }

    const lowerPath = pathname.toLowerCase();
    const suspiciousFile = SUSPICIOUS_FILE_EXTENSIONS.find(ext => lowerPath.endsWith(ext) || lowerPath.includes(ext + '?'));
    if (suspiciousFile) {
      score += 24;
      addReason(reasons, 24, 'ลิงก์ไปยังไฟล์ที่อาจเป็นอันตราย', suspiciousFile, 'download');
    }
    const archiveFile = ARCHIVE_EXTENSIONS.find(ext => lowerPath.endsWith(ext) || lowerPath.includes(ext + '?'));
    if (archiveFile) {
      score += 7;
      addReason(reasons, 7, 'ลิงก์ดาวน์โหลดไฟล์บีบอัด', archiveFile, 'download');
    }

    if (searchContextRaw) {
      const adultHits = ADULT_SEO_KEYWORDS.filter(k => searchContextLower.includes(k.toLowerCase()));
      const contextMentionsAdultBrand = ADULT_CONTENT_DOMAINS
        .map(d => d.replace(/\.com$/i, ''))
        .filter(name => searchContextLower.includes(name));
      const isDocLike = /\.(pdf|docx?|xlsx?|pptx?)(?:$|[?#/])/i.test(pathname) || /\bpdf\b/i.test(searchContextLower);
      const isPublicOrAcademicHost = /\.(edu|org|gov|ac\.[a-z]{2}|go\.[a-z]{2}|or\.[a-z]{2})$/i.test(hostname);

      if (adultHits.length && !isAdultOfficialDomain) {
        score += 18;
        addReason(reasons, 18, 'ผลค้นหามีคำกลุ่ม Adult/SEO spam แต่ปลายทางไม่ใช่โดเมนเนื้อหานั้นโดยตรง', adultHits.slice(0, 5).join(', '), 'search-context');
      }
      if (adultHits.length && isPublicOrAcademicHost && !isAdultOfficialDomain) {
        score += 18;
        addReason(reasons, 18, 'โดเมนสาธารณะ/องค์กร/การศึกษาถูกใช้กับหัวข้อผิดบริบท', hostname, 'search-context');
      }
      if (adultHits.length && looksLikeCmsUpload) {
        score += 14;
        addReason(reasons, 14, 'path คล้ายไฟล์อัปโหลดจาก CMS หรือโฟลเดอร์ชั่วคราว', pathname.slice(0, 120), 'search-context');
      }
      if (adultHits.length && isDocLike && !isAdultOfficialDomain) {
        score += 14;
        addReason(reasons, 14, 'ลิงก์เอกสาร/PDF ในผลค้นหาที่มีคำเสี่ยง', 'อาจเป็น SEO spam หรือไฟล์ที่ถูกฝังในเว็บที่ถูกโจมตี', 'search-context');
      }
      if (contextMentionsAdultBrand.length && !isAdultOfficialDomain) {
        score += 16;
        addReason(reasons, 16, 'ข้อความผลค้นหาอ้างเว็บ Adult ชื่อดัง แต่ URL ปลายทางเป็นคนละโดเมน', contextMentionsAdultBrand.slice(0, 4).join(', '), 'search-context');
      }
    }

    // Broader harmful/risky content detection beyond phishing.
    const malwareContentHits = findKeywordHits(combinedContextLower, MALWARE_CONTENT_KEYWORDS);
    if (malwareContentHits.length) {
      const points = Math.min(28, 12 + malwareContentHits.length * 4);
      score += points;
      addReason(reasons, points, 'พบคำหรือบริบทที่เกี่ยวกับมัลแวร์/ไฟล์เสี่ยง', malwareContentHits.slice(0, 6).join(', '), 'malware-content');
    }

    const scamContentHits = findKeywordHits(combinedContextLower, SCAM_CONTENT_KEYWORDS);
    if (scamContentHits.length) {
      const points = Math.min(24, 10 + scamContentHits.length * 4);
      score += points;
      addReason(reasons, points, 'พบคำที่มักใช้ในเว็บหลอกลวงหรือกลโกงออนไลน์', scamContentHits.slice(0, 6).join(', '), 'scam-content');
    }

    const gamblingHits = findKeywordHits(combinedContextLower, GAMBLING_CONTENT_KEYWORDS);
    if (gamblingHits.length) {
      const points = Math.min(22, 10 + gamblingHits.length * 4);
      score += points;
      addReason(reasons, points, 'พบเนื้อหาเว็บพนัน/การพนันออนไลน์', gamblingHits.slice(0, 6).join(', '), 'gambling-content');
    }

    const adultContextHits = findKeywordHits([fullLower, searchContextLower, visibleContextLower].join(' '), SENSITIVE_ADULT_CONTEXT_KEYWORDS);
    if (adultContextHits.length && !isAdultOfficialDomain && !searchContextRaw) {
      const points = Math.min(20, 8 + adultContextHits.length * 3);
      score += points;
      addReason(reasons, points, 'พบคำกลุ่มเนื้อหา Adult/Spam ใน URL หรือข้อความลิงก์', adultContextHits.slice(0, 6).join(', '), 'adult-content');
    }

    if (/allow notifications|enable notifications|click allow|กดอนุญาต|เปิดการแจ้งเตือน/i.test(combinedContextLower) &&
        /virus|download|player|verify|captcha|malware|ไวรัส|ดาวน์โหลด|ยืนยัน/i.test(combinedContextLower)) {
      score += 16;
      addReason(reasons, 16, 'พบข้อความหลอกให้กด Allow/Notification', 'มักพบในเว็บหลอกโหลดไฟล์หรือโฆษณาอันตราย', 'malware-content');
    }

    if (/seed phrase|recovery phrase|private key|wallet connect|airdrop|claim token|กระเป๋าเงิน|คริปโต|โทเคน/i.test(combinedContextLower) &&
        /claim|verify|connect|bonus|free|รับสิทธิ์|แจก|ยืนยัน|ล็อกอิน/i.test(combinedContextLower)) {
      score += 18;
      addReason(reasons, 18, 'พบบริบทหลอกลวงเกี่ยวกับคริปโต/กระเป๋าเงิน', 'ควรระวังการขอ seed phrase หรือการเชื่อมกระเป๋าเงิน', 'crypto-content');
    }

    if (SHORTENERS.some(d => isSubdomainOrSame(hostname, d))) {
      score += 15;
      addReason(reasons, 15, 'เป็นลิงก์ย่อ', 'ควรตรวจปลายทางจริงก่อนเปิด', 'redirect');
    }

    const hosting = FREE_HOSTING_OR_DDNS.find(d => isSubdomainOrSame(hostname, d));
    if (hosting) {
      score += 9;
      addReason(reasons, 9, 'ใช้ free hosting หรือ dynamic DNS', hosting, 'hosting');
    }

    const labelSkeleton = skeleton(domainLabel);
    const hostTokens = hostname.split(/[.-]/).filter(Boolean).map(skeleton).filter(Boolean).filter(t => !IGNORE_BRAND_TOKEN_MATCH.has(t));
    const entropy = shannonEntropy(domainLabel.replace(/-/g, ''));
    const digitCount = (domainLabel.match(/\d/g) || []).length;
    const digitRatio = domainLabel.length ? digitCount / domainLabel.length : 0;
    const vowelRatio = domainLabel.length ? ((domainLabel.match(/[aeiou]/gi) || []).length / domainLabel.length) : 1;

    if (domainLabel.length >= 13 && entropy >= 3.55 && vowelRatio < 0.28 && !isKnownOfficial) {
      score += 11;
      addReason(reasons, 11, 'ชื่อโดเมนดูสุ่มผิดปกติ', `entropy ${entropy.toFixed(2)}`, 'domain');
    }

    if (digitRatio >= 0.28 && domainLabel.length >= 8) {
      score += 8;
      addReason(reasons, 8, 'ชื่อโดเมนมีตัวเลขปนมาก', `${Math.round(digitRatio * 100)}% เป็นตัวเลข`, 'domain');
    }

    const keywordHits = SUSPICIOUS_KEYWORDS.filter(k => fullLower.includes(k.toLowerCase()));
    if (keywordHits.length) {
      const points = Math.min(24, keywordHits.length * 4 + 2);
      score += points;
      addReason(reasons, points, 'พบคำที่มักใช้หลอกให้ล็อกอิน/ยืนยันตัวตน', keywordHits.slice(0, 8).join(', '), 'keyword');
      if (keywordHits.length >= 6) {
        score += 8;
        addReason(reasons, 8, 'พบ keyword เสี่ยงเป็นกลุ่มจำนวนมาก', `${keywordHits.length} คำ`, 'keyword');
      }
    }

    const credentialHits = CREDENTIAL_KEYWORDS.filter(k => fullLower.includes(k.toLowerCase()));
    if (credentialHits.length) {
      const points = Math.min(18, credentialHits.length * 6);
      score += points;
      addReason(reasons, points, 'พบคำเกี่ยวกับข้อมูลลับ/รหัสผ่าน', credentialHits.slice(0, 5).join(', '), 'credential');
    }

    const brandFindings = [];
    for (const profile of BRAND_PROFILES) {
      const names = [profile.brand, ...profile.aliases].filter(Boolean).filter(name => skeleton(name).length >= 3);
      const official = profile.officialDomains.some(d => isSubdomainOrSame(hostname, d));
      const hostContains = names.find(name => skeleton(hostname).includes(skeleton(name)) || hostname.includes(name));
      const fullContains = names.find(name => skeleton(fullLower).includes(skeleton(name)) || fullLower.includes(name));
      let lookalike = null;
      for (const name of names) {
        const nameSkel = skeleton(name);
        const dist = levenshtein(labelSkeleton, nameSkel);
        const tokenClose = hostTokens.some(t => {
          if (t.length < Math.max(3, nameSkel.length - 2) || t.length > nameSkel.length + 4) return false;
          const d = levenshtein(t, nameSkel);
          return d > 0 && d <= 2;
        });
        const close = dist > 0 && dist <= 2 && Math.abs(labelSkeleton.length - nameSkel.length) <= 3;
        const embedded = labelSkeleton.includes(nameSkel) && labelSkeleton !== nameSkel;
        const tokenEmbedded = hostTokens.some(t => t.includes(nameSkel) && t !== nameSkel);
        const confusable = labelSkeleton === nameSkel && domainLabel.toLowerCase() !== name.toLowerCase();
        if (close || tokenClose || confusable || ((embedded || tokenEmbedded) && /login|secure|verify|support|account|update|help|pay|wallet/.test(labelSkeleton + hostTokens.join('')))) {
          lookalike = name;
          break;
        }
      }
      if (!official && (hostContains || lookalike)) {
        brandFindings.push({ brand: profile.brand, matched: hostContains || lookalike, lookalike: !!lookalike });
      } else if (!official && fullContains && (keywordHits.length || credentialHits.length)) {
        brandFindings.push({ brand: profile.brand, matched: fullContains, lookalike: false, inPath: true });
      }
    }

    if (brandFindings.length) {
      const main = brandFindings[0];
      const points = main.lookalike ? 30 : main.inPath ? 16 : 24;
      score += points;
      addReason(reasons, points, 'โดเมน/URL มีลักษณะเลียนแบบแบรนด์จริง', `${hostname} อ้างถึง ${main.brand}`, 'brand');
    }

    if (brandFindings.length && (keywordHits.some(k => /login|verify|account|secure|update|support|kyc|payment|wallet|ล็อกอิน|ยืนยัน/.test(k.toLowerCase())) || credentialHits.length)) {
      score += 14;
      addReason(reasons, 14, 'พบชื่อแบรนด์ร่วมกับคำเกี่ยวกับบัญชีหรือรหัสผ่าน', brandFindings.map(b => b.brand).slice(0, 3).join(', '), 'brand');
    }

    if ((options.linkText || options.visibleText) && !options.ignoreLinkText) {
      const text = String(options.linkText || options.visibleText || '').slice(0, 300);
      const mismatch = detectLinkTextMismatch(text, hostname);
      if (mismatch) {
        score += 24;
        addReason(reasons, 24, 'ข้อความลิงก์ไม่ตรงกับปลายทางจริง', mismatch, 'link-context');
      }
      const textLower = text.toLowerCase();
      const textPressure = PRESSURE_WORDS.filter(w => textLower.includes(w.toLowerCase()));
      if (textPressure.length) {
        score += 6;
        addReason(reasons, 6, 'ข้อความลิงก์มีคำเร่งเร้า/กดดัน', textPressure.slice(0, 3).join(', '), 'link-context');
      }
    }

    if (options.opensNewTabNoNoopener) {
      score += 3;
      addReason(reasons, 3, 'ลิงก์เปิดแท็บใหม่โดยไม่มี noopener', 'มีความเสี่ยง tabnabbing ระดับต่ำ', 'link-context');
    }

    const formIssues = Array.isArray(options.formIssues) ? options.formIssues : [];
    for (const issue of formIssues.slice(0, 6)) {
      const points = Number(issue.points || 0);
      if (!points) continue;
      score += points;
      addReason(reasons, points, issue.label || 'พบความเสี่ยงในฟอร์ม', issue.detail || '', 'form');
    }

    if (options.pageHasPasswordForm) {
      const points = isKnownOfficial && url.protocol === 'https:' ? 3 : 12;
      score += points;
      addReason(reasons, points, 'หน้านี้มีช่องรหัสผ่าน', 'เพิ่มความเสี่ยงหากโดเมนไม่น่าเชื่อถือ', 'form');
    }

    if (options.passwordFieldCount > 1) {
      score += 5;
      addReason(reasons, 5, 'มีช่องรหัสผ่านหลายช่อง', `${options.passwordFieldCount} ช่อง`, 'form');
    }

    if (options.otpFieldCount > 0) {
      score += 10;
      addReason(reasons, 10, 'มีช่องกรอก OTP/Token', `${options.otpFieldCount} ช่อง`, 'form');
    }

    if (options.documentTitle && !isKnownOfficial) {
      const title = String(options.documentTitle).toLowerCase();
      const titleBrand = KNOWN_BRANDS.find(b => title.includes(b.toLowerCase()));
      const titleCred = CREDENTIAL_KEYWORDS.find(k => title.includes(k.toLowerCase()));
      if (titleBrand && (titleCred || keywordHits.length)) {
        score += 10;
        addReason(reasons, 10, 'ชื่อหน้าเว็บอ้างถึงแบรนด์/บัญชี แต่โดเมนไม่ใช่ทางการ', options.documentTitle.slice(0, 80), 'page-context');
      }
    }

    if (options.pageText) {
      const text = String(options.pageText).slice(0, 8000).toLowerCase();
      const pressureHits = PRESSURE_WORDS.filter(w => text.includes(w.toLowerCase()));
      if (pressureHits.length) {
        score += 8;
        addReason(reasons, 8, 'พบข้อความเร่งให้รีบทำรายการ', pressureHits.slice(0, 5).join(', '), 'page-context');
      }
      if (/(seed phrase|recovery phrase|private key|รหัส otp|กรอก otp|รหัสผ่าน|ข้อมูลบัตร|หมายเลขบัตร|cvv)/i.test(text)) {
        score += 12;
        addReason(reasons, 12, 'หน้าเว็บขอข้อมูลสำคัญ', 'พบคำเกี่ยวกับ OTP/รหัสผ่าน/บัตร/seed phrase', 'page-context');
      }
    }

    // Combination rules: phishing is usually a cluster of weak signals.
    const categories = new Set(reasons.filter(r => r.points > 0).map(r => r.category));
    if (categories.has('brand') && categories.has('credential')) {
      score += 10;
      addReason(reasons, 10, 'สัญญาณร่วม: เลียนแบบแบรนด์ + ขอข้อมูลลับ', 'ความเสี่ยงเพิ่มขึ้นเมื่อสองเงื่อนไขเกิดพร้อมกัน', 'combo');
    }
    if (categories.has('brand') && categories.has('transport')) {
      score += 8;
      addReason(reasons, 8, 'สัญญาณร่วม: อ้างแบรนด์แต่ไม่ใช้ HTTPS', 'ผิดปกติสำหรับบริการจริง', 'combo');
    }
    if (categories.has('form') && (categories.has('brand') || categories.has('keyword')) && !isKnownOfficial) {
      score += 10;
      addReason(reasons, 10, 'สัญญาณร่วม: มีฟอร์มล็อกอินบนเว็บที่น่าสงสัย', 'ควรบล็อกก่อนผู้ใช้กรอกข้อมูล', 'combo');
    }
    if (categories.has('redirect') && categories.has('keyword')) {
      score += 6;
      addReason(reasons, 6, 'สัญญาณร่วม: redirect + คำชวนให้ยืนยันบัญชี', 'มักใช้พาผู้ใช้ไปปลายทางหลอก', 'combo');
    }
    if (categories.has('download') && categories.has('keyword')) {
      score += 8;
      addReason(reasons, 8, 'สัญญาณร่วม: ไฟล์ดาวน์โหลด + คำหลอกให้ทำรายการ', 'ควรเตือนก่อนดาวน์โหลดไฟล์', 'combo');
    }

    if (categories.has('search-context') && (categories.has('url-shape') || categories.has('download'))) {
      score += 8;
      addReason(reasons, 8, 'สัญญาณร่วม: ผลค้นหาผิดบริบท + รูปแบบ URL/ไฟล์น่าสงสัย', 'เข้าข่าย SEO spam หรือเว็บที่ถูกฝังลิงก์แปลกปลอม', 'combo');
    }

    if ((categories.has('malware-content') || categories.has('adult-content') || categories.has('gambling-content') || categories.has('scam-content') || categories.has('crypto-content')) &&
        (categories.has('redirect') || categories.has('url-shape') || categories.has('download'))) {
      score += 9;
      addReason(reasons, 9, 'สัญญาณร่วม: เนื้อหาเสี่ยง + รูปแบบลิงก์ผิดปกติ', 'ไม่ใช่ phishing เสมอไป แต่อาจเป็นเว็บหลอก โฆษณาอันตราย หรือไฟล์เสี่ยง', 'combo');
    }

    if (url.protocol === 'https:' && positiveBeforeTrust() === 0) {
      score -= 8;
      addReason(reasons, -8, 'ไม่พบสัญญาณเสี่ยงชัดเจน', 'URL เป็น HTTPS และรูปแบบปกติ', 'trust');
    }

    // Trust cap for known official HTTPS domains unless there are form/action or credential anomalies.
    const criticalOnOfficial = reasons.some(r => r.points > 0 && ['form', 'credential', 'redirect', 'download'].includes(r.category));
    if (isKnownOfficial && url.protocol === 'https:' && !criticalOnOfficial) {
      score = Math.min(score, 18);
    } else if (isKnownOfficial && url.protocol === 'https:') {
      score = Math.min(score, 42);
    }

    score = Math.max(0, Math.min(100, Math.round(score)));
    const c = classify(score);
    const sortedReasons = reasons
      .sort((a, b) => Math.abs(b.points) - Math.abs(a.points))
      .slice(0, 12);

    return {
      input,
      url: hrefRaw,
      hostname,
      domain: domainGuess,
      score,
      level: c.level,
      levelText: c.text,
      reasons: sortedReasons,
      threatTypes: deriveThreatTypes(sortedReasons),
      safe: score < 31,
      summary: `${c.text} (${score}/100)`,
      features: {
        urlLength: hrefRaw.length,
        hostLength: hostname.length,
        domain: domainGuess,
        tld,
        subdomainLevels: Math.max(0, parts.length - 2),
        entropy: Number(entropy.toFixed(2)),
        keywordHits: keywordHits.slice(0, 10),
        credentialHits: credentialHits.slice(0, 10),
        officialBrand: officialProfiles.map(p => p.brand)
      }
    };
  }

  function badgeText(score) {
    if (score >= 81) return '!!';
    if (score >= 61) return 'HIGH';
    if (score >= 31) return 'WARN';
    return '✓';
  }

  const api = { analyzeUrl, classify, badgeText, KNOWN_BRANDS, SUSPICIOUS_KEYWORDS, BRAND_PROFILES };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  global.PhishRadarAnalyzer = api;
})(typeof globalThis !== 'undefined' ? globalThis : window);
