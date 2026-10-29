"""Serve a local DOM regression fixture; never load or visit ad destinations.

The runtime source is unchanged, wrapped with lexical Chrome/location stubs.
Native browser DOM, MutationObserver, event propagation and style restoration
are exercised against the captured supplied page's ad markup.
"""
from html import escape
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/ad-filter-20261009'
EVIDENCE = json.loads((OUT / 'live-dom-evidence.json').read_text(encoding='utf-8'))
IMAGE = 'data:image/svg+xml,' + '%3Csvg xmlns="http://www.w3.org/2000/svg" width="728" height="110"%3E%3Crect width="728" height="110" fill="%23282a30"/%3E%3Ctext x="30" y="60" fill="white" font-size="20"%3ERecorded banner placeholder%3C/text%3E%3C/svg%3E'


class SafeMarkup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style'}:
            self.skip += 1
        if self.skip or tag not in {'div', 'a', 'img', 'p', 'span'}:
            return
        clean = [(k, v) for k, v in attrs if k in {'id', 'class', 'href', 'alt', 'width', 'height', 'aria-label', 'rel'} and v and not v.lower().startswith('javascript:')]
        # Keep captured geometry without executing event handlers or CSS URLs.
        safe_style = []
        for prop in dict(attrs).get('style', '').split(';'):
            name, _, value = prop.partition(':')
            if name.strip().lower() in {'position', 'bottom', 'top', 'left', 'right', 'width', 'height', 'z-index', 'text-align', 'padding', 'padding-top', 'float'} and re.fullmatch(r'[a-zA-Z0-9 .%+-]*', value.strip()):
                safe_style.append(name.strip() + ':' + value.strip())
        if safe_style:
            clean.append(('style', ';'.join(safe_style)))
        if tag == 'img':
            if dict(attrs).get('src'):
                clean.append(('data-original', dict(attrs)['src']))
            clean.append(('src', IMAGE))
        self.parts.append('<' + tag + ''.join(f' {k}="{escape(v, quote=True)}"' for k, v in clean) + '>')

    def handle_endtag(self, tag):
        if tag in {'script', 'style'} and self.skip:
            self.skip -= 1
            return
        if not self.skip and tag in {'div', 'a', 'p', 'span'}:
            self.parts.append('</' + tag + '>')

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(escape(data))


safe = SafeMarkup()
for slot in EVIDENCE['slots']:
    safe.feed(slot['html'])
reading = ''.join(f'<li><a href="{escape(item["href"], quote=True)}">{escape(item["text"].strip())}</a></li>' for item in EVIDENCE['readingLinks'])
HTML = '''<!doctype html><meta charset="utf-8"><title>Phish Radar · Ad filter regression</title>
<style>body{background:#101116;color:#eaeaf0;font:16px system-ui;max-width:960px;margin:40px auto;padding:0 25px}h1{font-size:28px}p{line-height:1.6;color:#adb2c0}button{font:inherit;background:#dd7985;border:0;border-radius:8px;padding:12px 18px;cursor:pointer}#result{padding:20px;background:#20242c;white-space:pre-wrap;border-radius:10px;line-height:1.6}.center_upmanga,.center_upmangaza,.center_upmangasolo{display:flex;gap:10px;margin:8px 0}img{max-width:100%;height:80px}a{color:#dba5b0}li{margin:12px 0}#genericCases{margin-top:25px}.testnote{color:#8dcdaa}nav{position:fixed;right:0;top:0}</style>
<h1>Phish Radar · Local ad filter verification</h1>
<p>Captured DOM from up-manga.com · No ad requests, redirects or third-party scripts run here. This tests the Extension runtime, using local Chrome API and page URL stubs.</p>
<button id="runTests">Run regression checks</button><p id="result">Checking captured banners…</p>
<section id="capturedSlots">''' + ''.join(safe.parts) + '''</section>
<h2>Reading links retained</h2><ul id="readingLinks">''' + reading + '''</ul>
<section id="genericCases">
<div class="ad-slot"><a id="riskyText" href="https://offers.example/register">คาสิโน สมัครรับโบนัส</a></div>
<div class="ad-slot"><a id="normalAd" href="https://books.example/"><img alt="Buy books" src="''' + escape(IMAGE, quote=True) + '''"></a></div>
<div style="position:fixed"><a id="fixedArticle" href="https://security-news.example/facebook-guide"><img alt="Facebook verify your account phishing guide" src="''' + escape(IMAGE, quote=True) + '''"></a></div>
<nav><a id="menuLink" href="https://security-news.example/guide"><img alt="Facebook verify your account phishing guide" src="''' + escape(IMAGE, quote=True) + '''"></a></nav>
<form class="ad-slot"><label>Login <input name="user"></label><a id="formLink" href="https://other.example/register">คาสิโน สมัครรับโบนัส</a></form>
<a id="community" href="https://www.facebook.com/upmangath">Facebook community</a>
</section><script src="/fixture.js"></script><script src="/app-trust.js"></script><script src="/ad-filter-policy.js"></script><script src="/ad-filter.js"></script>'''

FIXTURE = r'''
const fixtureLocation = {href:'https://www.up-manga.com/genres/manhwa/',hostname:'www.up-manga.com',protocol:'https:'};
const messageListeners = [], storageListeners = [];
const saved = {riskyAdProtection:true,adFilterAllowlist:[],privacyMode:true,pageScanningEnabled:false};
const fixtureChrome = {storage:{sync:{get:async defaults=>({...defaults,...saved})},onChanged:{addListener:fn=>storageListeners.push(fn)}},runtime:{onMessage:{addListener:fn=>messageListeners.push(fn)}}};
document.addEventListener('click',e=>{if(e.target.closest('a'))e.preventDefault();});
const req = message=>new Promise((resolve,reject)=>{let answered=false;for(const listener of messageListeners)listener(message,{},response=>{answered=true;resolve(response)});setTimeout(()=>{if(!answered)reject(Error('No runtime response'))},2000)});
const setting = async change=>{Object.assign(saved,change);return req({type:'SETTINGS_UPDATED',settings:saved})};
const sleep = ms=>new Promise(resolve=>setTimeout(resolve,ms));
const visible = el=>getComputedStyle(el).display!=='none' && (!el.parentElement || visible(el.parentElement));
const assert = (condition,label)=>{if(!condition)throw Error(label);checks.push(label)};
let checks=[];
const originalAnchors = [...document.querySelectorAll('#capturedSlots a[href]')].filter(a=>!!a.querySelector('img')&&new URL(a.href).hostname!=='www.up-manga.com');
const initialDisplay = originalAnchors[0];initialDisplay.style.setProperty('display','inline-flex','important');
window.addEventListener('load',async()=>{await sleep(200);const r=await req({type:'GET_AD_FILTER_STATS'});document.getElementById('result').textContent=`Captured ad links hidden: ${originalAnchors.filter(a=>!visible(a)).length}/${originalAnchors.length}\nReading links retained: ${[...document.querySelectorAll('#readingLinks a')].filter(visible).length}/10\nReady for regression checks.`});
document.getElementById('runTests').addEventListener('click',async()=>{
 checks=[]; const result=document.getElementById('result'); result.textContent='Running…';
 try {
  assert(originalAnchors.every(a=>!visible(a)),'Reviewed external image banners hidden');
  assert([...document.querySelectorAll('#readingLinks a')].every(visible),'All 10 manga reading links preserved');
  assert([...document.querySelectorAll('#capturedSlots a[href]')].filter(a=>new URL(a.href).hostname==='www.up-manga.com').every(visible),'First-party reading banner preserved in mixed slot');
  assert(!visible(document.getElementById('riskyText')),'Explicit risky ad wording hidden');
  assert(!visible(document.getElementById('normalAd')),'All mode hides an ordinary detected ad');
  for(const id of ['fixedArticle','menuLink','formLink','community'])assert(visible(document.getElementById(id)),id+' preserved');
  let d=await req({type:'CHECK_AD_FILTER_TARGET',targetUrl:originalAnchors[0].href});assert(d.blocked===true,'Exact filtered popup destination recognized');
  d=await req({type:'CHECK_AD_FILTER_TARGET',targetUrl:'https://accounts.google.com/o/oauth2/v2/auth'});assert(d.blocked===false,'Normal login popup not filtered');
  const event=new MouseEvent('click',{bubbles:true,cancelable:true});originalAnchors[0].dispatchEvent(event);assert(event.defaultPrevented,'Risky ad click cancelled before navigation');
  await req({type:'AD_FILTER_POPUP_BLOCKED',targetUrl:originalAnchors[0].href});let stats=(await req({type:'GET_AD_FILTER_STATS'})).stats;assert(stats.blockedClicks===1&&stats.blockedPopups===1,'Click and popup counters updated');
  await setting({riskyAdProtection:false});assert(originalAnchors.every(visible),'Turning off restores every banner');assert(initialDisplay.style.getPropertyValue('display')==='inline-flex'&&initialDisplay.style.getPropertyPriority('display')==='important','Original inline display and priority restored');
  await setting({riskyAdProtection:true,adFilterAllowlist:['www.up-manga.com']});assert(originalAnchors.every(visible),'Exact-host exception restores banners');
  await setting({adFilterAllowlist:['up-manga.com']});assert(originalAnchors.every(a=>!visible(a)),'Apex exception does not exempt www host');
  const dynamic=document.createElement('div');dynamic.className='center_upmanga';dynamic.innerHTML='<a href="https://new-ad.example/register"><img alt="new banner"></a>';document.getElementById('capturedSlots').append(dynamic);await sleep(250);assert(!visible(dynamic.firstElementChild),'Dynamically added ad filtered');
  dynamic.firstElementChild.href='https://www.up-manga.com/new-chapter/';await sleep(250);assert(visible(dynamic.firstElementChild),'Ad changed to first-party reading URL restored');dynamic.remove();
  const oldLocation={...fixtureLocation};fixtureLocation.href='https://news.example/';fixtureLocation.hostname='news.example';await setting({});assert(originalAnchors.every(a=>!visible(a)),'Known advertisement markup filters across publisher hosts');assert(!visible(document.getElementById('riskyText')),'Generic risky ad still filtered');Object.assign(fixtureLocation,oldLocation);await setting({});
  assert(saved.privacyMode===true&&saved.pageScanningEnabled===false,'Works independently of Privacy Mode and page scanning');
  stats=(await req({type:'GET_AD_FILTER_STATS'})).stats;window.fixtureResults={passed:true,checks:checks.length,hiddenCapturedAds:originalAnchors.filter(a=>!visible(a)).length,totalCapturedAds:originalAnchors.length,retainedReadingLinks:10,stats};result.textContent=`PASS · ${checks.length} checks\nCaptured ad links hidden: ${window.fixtureResults.hiddenCapturedAds}/${originalAnchors.length}\nReading links retained: 10/10\nOff switch, exact-site exception, dynamic ads, popup decisions and restoration passed.`;result.style.color='#8ee0ad';
 }catch(error){window.fixtureResults={passed:false,error:error.message,checks};result.textContent='FAIL: '+error.message;result.style.color='#ff8c8c'}
});
'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = self.path.split('?', 1)[0]
        if route == '/':
            payload, content_type = HTML.encode(), 'text/html'
        elif route == '/fixture.js':
            payload, content_type = FIXTURE.encode(), 'text/javascript'
        elif route == '/ad-filter.js':
            source = (ROOT / 'extension/ad-filter.js').read_bytes()
            payload = b'(function(location,chrome){\n' + source + b'\n})(fixtureLocation,fixtureChrome);'
            content_type = 'text/javascript'
        elif route in {'/app-trust.js', '/ad-filter-policy.js'}:
            payload, content_type = (ROOT / 'extension' / route[1:]).read_bytes(), 'text/javascript'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)


if __name__ == '__main__':
    (OUT / 'browser-fixture.html').write_text(HTML, encoding='utf-8')
    HTTPServer(('127.0.0.1', 8766), Handler).serve_forever()
