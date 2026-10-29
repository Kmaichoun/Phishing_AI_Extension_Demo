'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { classifyCandidate } = require('../extension/ad-filter-policy.js');

const pageUrl = 'https://video.example/watch/42';
let checks = 0;
function check(candidate, expected, description) {
  const result = classifyCandidate({ pageUrl, ...candidate });
  assert.equal(result.hide, expected, description);
  assert.ok(Array.isArray(result.reasons));
  assert.equal(result.reasons.length > 0, expected, description + ': factual reasons');
  assert.ok(result.reasons.every(reason => typeof reason === 'string' && !/เป็น phishing แน่นอน/.test(reason)));
  checks += 1;
}

check({ adLike: true, media: true, targetUrl: 'https://ibit.ly/ad-42', label: 'HYDRA888 CASINO สมัครสมาชิก คืนยอดเสีย' }, true, 'Promotional casino banner linking through shortener');
check({ overlay: true, media: true, targetUrl: 'https://bit.ly/promo', text: 'สล็อต เครดิตฟรี สมัครเลย' }, true, 'Media overlay with gambling promotion');
check({ adLike: true, targetUrl: 'https://sports.example/promo', text: 'Place a bet, register for a bonus' }, true, 'Whole-word bet with a promotional action');
check({ adLike: true, targetUrl: 'https://promo.example/prize', text: 'You have won an iPhone! Claim now' }, true, 'Prize claim advertisement');
check({ adLike: true, targetUrl: 'https://accounts.google.com.attacker.example/verify', text: 'Google: verify your account' }, true, 'Brand credential lure on a different domain');
check({ adLike: true, targetUrl: 'https://login.example/collect?otp=', text: 'กรอก OTP เพื่อยืนยันบัญชี' }, true, 'Credential input encoded in advertised destination');
check({ adLike: true, targetUrl: 'https://installer.example/player.exe', text: 'Download player required to watch this video' }, true, 'Forced player installation advertisement');

check({ targetUrl: 'https://casino.example', text: 'Casino registration and bonus scams explained' }, false, 'Article text is not an ad');
check({ adLike: false, overlay: true, media: false, targetUrl: 'https://casino.example', text: 'สมัครคาสิโน โบนัส' }, false, 'Plain dialog is not sufficient ad presentation');
check({ adLike: true, targetUrl: 'https://bit.ly/promo', text: 'A new movie trailer' }, false, 'Shortener alone is not phishing evidence');
check({ adLike: true, media: true, targetUrl: 'https://store.example/product', text: 'Buy a new laptop today' }, false, 'Ordinary external product ad');
check({ adLike: true, targetUrl: 'https://store.example/alphabet', text: 'Alphabet books: register for a bonus' }, false, 'Bet substring must not match alphabet even with promotional wording');
check({ adLike: true, targetUrl: '/login', text: 'Google: verify your account' }, false, 'First-party login navigation');
check({ adLike: true, hasForm: true, targetUrl: 'https://verify.example', text: 'Google: verify your account' }, false, 'Forms are left intact');
check({ overlay: true, media: true, hasForm: true, targetUrl: 'https://casino.example', text: 'สล็อต เครดิตฟรี สมัคร' }, false, 'Consent/form overlay is left intact');
check({ adLike: true, targetUrl: 'https://accounts.google.com/signin', text: 'Google: verify your account' }, false, 'Official account destination');
check({ adLike: true, targetUrl: 'https://notgoogle.com/login', text: 'Account settings' }, false, 'Brand substring alone is insufficient');
check({ overlay: true, media: true, targetUrl: 'https://video.example/player', text: 'Install player required to watch video' }, false, 'First-party video controls');
check({ overlay: true, media: true, targetUrl: 'javascript:void(0)', text: 'CASINO สมัครรับโบนัส' }, false, 'Script controls are not inferred external URLs');
check({ adLike: true, targetUrl: 'https://publisher.example/article', text: 'Casino regulation research and statistics' }, false, 'Gambling topic without promotion');
check({ adLike: true, targetUrl: 'https://browser.example', text: 'Chrome browser update announcement' }, false, 'Update information without installation pressure');
check({ targetUrl: 'https://search.example', text: 'Search results: free money claim scams', attributes: 'search-results adblock-enabled' }, false, 'Attribute substrings do not supply ad presentation');
check({ adLike: true, targetUrl: 'https://store.example', text: 'Casino documentary: buy on DVD' }, false, 'Casino documentary without gambling promotion');
check({ adLike: true, targetUrl: 'https://risk.example', text: 'Ordinary link', randomForestScore: 99 }, false, 'High RF score is not evidence for hiding an ad');
check({ adLike: 'true', targetUrl: 'https://casino.example', text: 'คาสิโน เครดิตฟรี สมัคร' }, false, 'Presentation must be an explicit boolean');
check({ adLike: true, targetUrl: '', text: 'คาสิโน เครดิตฟรี สมัคร' }, false, 'No guessed destination');

// Image-only and floating presentation on different publishers must preserve
// normal reading/navigation content unless the DOM layer supplies ad evidence.
check({ media: true, targetUrl: 'https://cdn.example/manga/chapter-12.jpg', label: 'Chapter 12' }, false, 'An external manga image without ad presentation stays visible');
check({ media: true, targetUrl: 'https://publisher.example/series/42', label: 'Read the next chapter' }, false, 'An external manga cover without ad presentation stays visible');
check({ media: true, targetUrl: 'https://facebook.com/share', label: 'Share on Facebook' }, false, 'A share image without ad presentation stays visible');
check({ overlay: true, media: true, targetUrl: 'https://help.example/support', label: 'Customer support' }, false, 'A floating support image is not classified as an ad by position alone');
check({ overlay: true, media: true, targetUrl: 'https://publisher.example/author', label: 'Author profile' }, false, 'A floating author image is not phishing evidence');
check({ adLike: true, media: true, targetUrl: 'https://shopping.example/laptop?fbclid=abc123&token_tracking=abcdefghijk', label: 'Laptop offer' }, false, 'Tracking-looking query data does not imply a credential lure');
check({ adLike: true, media: true, targetUrl: 'https://shopping.example/?message=casino%20register%20bonus', label: 'New releases' }, false, 'Unrelated query values do not manufacture gambling evidence');

// Confirm that semantic evidence works without OCR when the page supplies
// meaningful image metadata, including normalization and encoded parameters.
check({ adLike: true, media: true, targetUrl: 'https://short.example/promo', label: 'คาสิโน เครดิตฟรี สมัครสมาชิก' }, true, 'Thai image metadata supplies gambling promotion evidence');
check({ adLike: true, media: true, targetUrl: 'https://short.example/promo', attributes: 'casino bonus register' }, true, 'Explicit ad metadata supplies gambling promotion evidence');
check({ adLike: true, media: true, targetUrl: 'https://short.example/promo', label: 'ＣＡＳＩＮＯ ＢＯＮＵＳ ＲＥＧＩＳＴＥＲ' }, true, 'Full-width gambling metadata normalizes consistently');
check({ overlay: true, media: true, targetUrl: 'https://login-attacker.example/?%70assword=', text: 'Enter your password' }, true, 'Encoded credential parameter names remain detectable');
check({ adLike: true, media: true, targetUrl: 'https://promo.example', text: 'You have won a prize: claim now', hasForm: true }, false, 'A form remains protected even when surrounding text looks promotional');

// Exact host/domain boundaries preserve legitimate destinations and retain
// detection of lookalikes; shortening and long parameters alone never suffice.
check({ adLike: true, media: true, targetUrl: 'https://ACCOUNTS.GOOGLE.COM/signin', text: 'Google: verify account' }, false, 'Official account destination is case insensitive');
check({ adLike: true, media: true, targetUrl: 'https://gmail.com/', text: 'Gmail: verify your account' }, false, 'Official Gmail destination remains visible');
check({ adLike: true, media: true, targetUrl: 'https://accounts.google.com.evil.example/login', text: 'Google: verify account' }, true, 'Official-looking hostname suffix does not bypass credential lure detection');
check({ adLike: true, media: true, targetUrl: 'https://notgoogle.com/login', text: 'Google: verify account' }, true, 'Hostname containing a brand is not an official domain');
check({ adLike: true, media: true, targetUrl: 'https://video.example/login?password=', text: 'Enter your password' }, false, 'First-party account destination remains protected');
check({ adLike: true, media: true, targetUrl: 'mailto:reader@example.com', text: 'casino bonus register' }, false, 'Non-HTTP contact link is not a presentation-filter destination');
check({ adLike: true, media: true, targetUrl: 'https://bit.ly/' + 'a'.repeat(200), label: 'Read a new chapter' }, false, 'Long shortener path alone does not turn a reader image into a risky ad');

// "All" is an explicit presentation preference. It broadens what ads are
// hidden without reclassifying a normal ad as phishing or weakening DOM guards.
const identifiedBookAd = {
  adLike: true, identifiedAd: true, media: true,
  targetUrl: 'https://books.example/promo', label: 'New books this month'
};
check({ ...identifiedBookAd, mode: 'all' }, true, 'All mode hides an identified ordinary book ad');
check({ ...identifiedBookAd, mode: 'risky' }, false, 'Risky mode retains an ordinary identified book ad');
check({ ...identifiedBookAd }, false, 'Pure policy defaults to risky mode when mode is absent');
check({ ...identifiedBookAd, mode: 'ALL' }, false, 'Only the exact all mode activates all-ad filtering');
check({ ...identifiedBookAd, mode: 'everything' }, false, 'Unknown mode does not activate all-ad filtering');
check({ ...identifiedBookAd, mode: 'all', label: '', text: '', attributes: '' }, true, 'Identified image-only ad needs no readable promotional text in all mode');
check({ ...identifiedBookAd, mode: 'all', targetUrl: 'https://redirect.example/?q=opaque123' }, true, 'Identified ad with an opaque destination is hidden in all mode');
check({ ...identifiedBookAd, mode: 'risky', targetUrl: 'https://redirect.example/?q=opaque123' }, false, 'An opaque identified destination remains insufficient risk evidence');
check({ ...identifiedBookAd, mode: 'all', identifiedAd: false }, false, 'External image with weak ad presentation is insufficient in all mode');
check({ ...identifiedBookAd, mode: 'all', identifiedAd: 'true' }, false, 'Identified ad evidence must be an explicit boolean');
check({ ...identifiedBookAd, mode: 'all', identifiedAd: 1 }, false, 'Truthy numeric identified ad evidence is insufficient');
check({ ...identifiedBookAd, mode: 'all', adLike: false }, false, 'An image without ad presentation is not hidden merely by identification metadata');
check({ mode: 'all', identifiedAd: true, overlay: true, media: true, targetUrl: 'https://books.example/promo' }, true, 'Identified floating media ad is hidden in all mode');
check({ mode: 'all', identifiedAd: true, overlay: true, media: false, targetUrl: 'https://books.example/promo' }, false, 'Plain floating dialog stays visible even in all mode');
check({ ...identifiedBookAd, mode: 'all', hasForm: true }, false, 'All mode preserves form content');
check({ ...identifiedBookAd, mode: 'all', targetUrl: '/chapter/12' }, false, 'All mode preserves first-party reading navigation');
check({ ...identifiedBookAd, mode: 'all', targetUrl: 'https://www.video.example/chapter/12' }, false, 'All mode preserves the www variant of the same publisher');
check({ ...identifiedBookAd, pageUrl: 'https://www.video.example/read', mode: 'all', targetUrl: 'https://video.example/chapter/12' }, false, 'All mode preserves the apex variant of the same publisher');
check({ ...identifiedBookAd, mode: 'all', targetUrl: 'https://www.video.example.evil.example/promo' }, true, 'A publisher hostname suffix does not gain first-party protection');
check({ ...identifiedBookAd, mode: 'all', targetUrl: '' }, false, 'All mode does not guess a missing destination');
check({ ...identifiedBookAd, mode: 'all', targetUrl: 'javascript:void(0)' }, false, 'All mode leaves script controls intact');
check({ ...identifiedBookAd, mode: 'all', targetUrl: 'mailto:reader@example.com' }, false, 'All mode leaves non-HTTP controls intact');
check({ ...identifiedBookAd, mode: 'risky', label: 'CASINO เครดิตฟรี สมัคร' }, true, 'Risky mode still hides identified gambling promotions');
check({ ...identifiedBookAd, mode: 'all', label: 'CASINO เครดิตฟรี สมัคร' }, true, 'All mode still hides risky ad content');
check({ mode: 'risky', adLike: true, identifiedAd: false, targetUrl: 'https://risk.example', text: 'CASINO bonus register' }, true, 'Risky semantic detection remains available independently of geometry identification');

// Keep the local ad policy synchronized with the analyzer's official Facebook
// family domains so Meta AI account links do not regress to impersonation ads.
check({ mode: 'risky', adLike: true, identifiedAd: true, targetUrl: 'https://meta.ai/', text: 'Facebook: verify your account' }, false, 'Meta AI is an official Facebook-family destination in risky mode');
check({ mode: 'risky', adLike: true, identifiedAd: true, targetUrl: 'https://www.meta.ai/', text: 'Facebook: verify your account' }, false, 'Meta AI www variant remains official');
check({ mode: 'risky', adLike: true, identifiedAd: true, targetUrl: 'https://help.meta.ai/', text: 'Facebook: verify your account' }, false, 'Meta AI subdomain remains official');
check({ mode: 'risky', adLike: true, identifiedAd: true, targetUrl: 'https://messenger.com/', text: 'Facebook: verify your account' }, false, 'Messenger remains an official Facebook-family destination');
check({ mode: 'risky', adLike: true, identifiedAd: true, targetUrl: 'https://meta.ai.evil.example/', text: 'Facebook: verify your account' }, true, 'Meta AI suffix spoof is still a credential lure');
check({ mode: 'all', adLike: true, identifiedAd: true, targetUrl: 'https://www.meta.ai/', text: 'Facebook: verify your account' }, true, 'All mode may hide an identified official-domain ad as advertising');

assert.deepEqual(classifyCandidate(null), { hide: false, reasons: [] });
assert.deepEqual(classifyCandidate({ adLike: true, pageUrl, targetUrl: 42, text: {} }), { hide: false, reasons: [] });

const script = fs.readFileSync(path.join(__dirname, '../extension/ad-filter-policy.js'), 'utf8');
const browser = { URL };
vm.createContext(browser);
vm.runInContext(script, browser);
assert.equal(typeof browser.PhishRadarAdFilterPolicy.classifyCandidate, 'function');
assert.equal(browser.PhishRadarAdFilterPolicy.classifyCandidate({ pageUrl, adLike: true, targetUrl: 'https://casino.example', text: 'casino bonus register' }).hide, true);
assert.equal(browser.PhishRadarAdFilterPolicy.classifyCandidate({ pageUrl, ...identifiedBookAd, mode: 'all' }).hide, true);
assert.equal(browser.PhishRadarAdFilterPolicy.classifyCandidate({ pageUrl, ...identifiedBookAd, mode: 'risky' }).hide, false);

const ordinaryAdDecision = classifyCandidate({ pageUrl, ...identifiedBookAd, mode: 'all' });
for (const scoreField of ['score', 'randomForestScore', 'finalScore']) {
  assert.equal(Object.hasOwn(ordinaryAdDecision, scoreField), false, 'Ad presentation filtering must not return or replace ' + scoreField);
}

console.log(`Ad filter policy: ${checks} positive/negative cases and browser/CommonJS loading passed.`);
