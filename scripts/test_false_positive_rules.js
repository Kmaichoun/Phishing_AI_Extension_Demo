const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const results = [];
for (const runtime of ['web-app', 'extension']) {
  const a = require('../' + runtime + '/analyzer.js');
  for (const url of ['https://www.ku.ac.th/th', 'https://www.chula.ac.th/', 'https://www.cmu.ac.th/', 'https://www.kmitl.ac.th/', 'https://www.su.ac.th/', 'https://www.school.sch.uk/']) {
    const r = a.analyzeUrl(url);
    assert(!r.reasons.some(x => x.category === 'brand'), `${runtime}: false brand on ${url}`);
    assert(!r.reasons.some(x => x.label.includes('subdomain')), `${runtime}: false subdomain on ${url}`);
    assert(r.score < 31);
    results.push({runtime, url, rule_score:r.score});
  }
  const article = a.analyzeUrl('https://school.ac.th/news/microsoft-account');
  assert(!article.reasons.some(x => x.category === 'brand'));
  assert(!a.analyzeUrl('https://online-school.ac.th/').reasons.some(x => x.category === 'brand'));
  assert.equal(a.analyzeUrl('https://login.ku.ac.th/').features.subdomainLevels, 1);
  assert.equal(a.analyzeUrl('https://www.city.kawasaki.jp/').domain, 'city.kawasaki.jp');
  assert.equal(a.analyzeUrl('https://a.b.ck/').domain, 'a.b.ck');
  assert.equal(a.analyzeUrl('https://www.ku.ac.th.evil.example/login').domain, 'evil.example');
  for (const url of ['https://paypa1.com/login', 'https://paypal.evil.example/login', 'https://scb-login.example/account']) {
    assert(a.analyzeUrl(url).reasons.some(x => x.category === 'brand'), `Lost brand signal: ${url}`);
  }
  assert(a.analyzeUrl('http://paypal-login-verify.top/account/otp?redirect=https%3A%2F%2Fevil.example').score >= 61);
  const incidental = a.analyzeUrl('https://shopping.example/shipping/spinning/pinwheel/tokenizer/author/');
  assert(!incidental.reasons.some(x => ['keyword', 'credential'].includes(x.category)), `${runtime}: incidental substring evidence`);
  assert.equal(incidental.score, 0);
  const otp = a.analyzeUrl('https://example.com/otp');
  assert.deepEqual(otp.features.credentialHits, ['otp']);
  assert.equal(otp.reasons.find(x => x.category === 'credential').points, 6);
  assert(a.analyzeUrl('https://example.com/password/reset').reasons.some(x => x.category === 'credential'));
  assert(a.analyzeUrl('https://example.com/%70assword').reasons.some(x => x.category === 'credential'));
  results.push({runtime, url:incidental.url, rule_score:incidental.score, description:'No credential evidence in unrelated words'});
}
fs.mkdirSync(path.join(__dirname, '../output/risk-fix'), {recursive:true});
fs.writeFileSync(path.join(__dirname, '../output/risk-fix/rule-regressions.json'), JSON.stringify({
  description:'Rule regressions only; not a measured population FPR or model accuracy claim.', results
}, null, 2));
console.log('False-positive regressions passed in web and extension; phishing signals retained.');
