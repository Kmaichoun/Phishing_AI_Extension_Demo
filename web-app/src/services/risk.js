import analyzer from './analyzer';

export function normalizeInputUrl(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  return /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//.test(raw) ? raw : `https://${raw}`;
}

export function flattenReason(reason) {
  if (!reason) return '';
  if (typeof reason === 'string') return reason;
  return reason.detail ? `${reason.label}: ${reason.detail}` : reason.label;
}

export function riskLevel(score, warningThreshold = 61, blockingThreshold = 81) {
  const warnCut = Number.isFinite(warningThreshold)
    ? Math.max(1, Math.min(99, warningThreshold))
    : 61;
  const blockCut = Number.isFinite(blockingThreshold)
    ? Math.max(warnCut, Math.min(100, blockingThreshold))
    : Math.min(100, warnCut + 20);
  const mediumCut = Math.max(5, Math.round(warnCut * 0.6));
  if (score >= blockCut) {
    return { key: 'critical', label: 'อันตรายมาก', decision: 'block', tone: 'risk-text-critical' };
  }
  if (score >= warnCut) {
    return { key: 'high', label: 'เสี่ยงสูง', decision: 'warn', tone: 'risk-text-high' };
  }
  if (score >= mediumCut) {
    return { key: 'medium', label: 'น่าสงสัย', decision: 'allow', tone: 'risk-text-medium' };
  }
  return { key: 'low', label: 'ค่อนข้างปลอดภัย', decision: 'allow', tone: 'risk-text-low' };
}

export function redactUrl(url) {
  try {
    const parsed = new URL(url);
    return `${parsed.protocol}//${parsed.hostname}/[path-hidden]`;
  } catch {
    return '[url-hidden]';
  }
}

export function safeHistoryUrl(url, privacy = false) {
  if (privacy) return redactUrl(url);
  try {
    const parsed = new URL(url);
    parsed.username = '';
    parsed.password = '';
    parsed.search = '';
    parsed.hash = '';
    return parsed.href;
  } catch {
    return '[invalid-url]';
  }
}

function sameOrSubdomain(host, domain) {
  const normalizedHost = String(host || '').replace(/^www\./, '').toLowerCase();
  const normalizedDomain = String(domain || '').replace(/^www\./, '').toLowerCase();
  return normalizedHost === normalizedDomain || normalizedHost.endsWith(`.${normalizedDomain}`);
}

export function brandVisualInsights(url, ruleResult) {
  const insights = [];
  let parsed;
  try {
    parsed = new URL(url);
  } catch {
    return ['อ่าน URL ไม่ได้ จึงตรวจ brand/visual clue ไม่ครบ'];
  }

  const hostname = parsed.hostname.toLowerCase();
  let decoded = url.toLowerCase();
  try { decoded = decodeURIComponent(url).toLowerCase(); } catch { /* Keep malformed percent escapes as literal evidence. */ }
  const profiles = analyzer.BRAND_PROFILES || [];
  const official = profiles.filter(profile =>
    (profile.officialDomains || []).some(domain => sameOrSubdomain(hostname, domain))
  );
  if (official.length) {
    insights.push(
      `โดเมนตรงกับรายการทางการของ ${official.map(profile => profile.brand).slice(0, 2).join(', ')} จึงลดความเสี่ยงด้านการเลียนแบบแบรนด์`
    );
  }

  for (const profile of profiles) {
    const tokens = [profile.brand, ...(profile.aliases || [])]
      .filter(Boolean)
      .map(value => String(value).toLowerCase());
    const mentionsBrand = tokens.some(token => decoded.includes(token));
    const isOfficial = (profile.officialDomains || [])
      .some(domain => sameOrSubdomain(hostname, domain));
    if (mentionsBrand && !isOfficial) {
      insights.push(`พบคำ/แบรนด์ "${profile.brand}" แต่โดเมนไม่ใช่โดเมนทางการ อาจเป็นหน้าเลียนแบบแบรนด์`);
      break;
    }
  }

  if (/xn--/i.test(hostname)) {
    insights.push('โดเมนใช้ Punycode/IDN ซึ่งอาจใช้ตัวอักษรหลอกตาให้คล้ายแบรนด์จริง');
  }
  if (
    /(login|verify|secure|account|password|otp|wallet|bank|signin)/i.test(decoded) &&
    ruleResult.score >= 31
  ) {
    insights.push('URL มีบริบท login/verify/account ร่วมกับคะแนนเสี่ยง จึงควรระวังหน้าเก็บรหัสผ่าน');
  }
  if (
    (ruleResult.reasons || [])
      .some(reason => ['brand', 'homograph', 'credential', 'form'].includes(reason.category))
  ) {
    insights.push('Rule-based พบสัญญาณที่เกี่ยวกับแบรนด์ ตัวอักษรหลอกตา หรือข้อมูลลับ');
  }
  if (!insights.length) {
    insights.push('ยังไม่พบสัญญาณเลียนแบบแบรนด์จาก URL และชื่อโดเมนในรอบนี้');
  }
  return insights.slice(0, 5);
}

export { analyzer };
