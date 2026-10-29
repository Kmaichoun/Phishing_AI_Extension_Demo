"""Serve native-DOM checks for the cross-site ad filter without ad traffic.

Only the page URL and Chrome APIs are lexical stubs. The extension's production
ad-filter.js, policy and app-trust.js are served directly from the workspace.
Images and the frame are local; CSP prevents external loads and connections.
Click the page's Run button in a browser to exercise the actual DOM observer,
event propagation, mode changes, frame filtering and style restoration.
"""
from argparse import ArgumentParser
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/global-ad-filter-20261009'

HTML = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phish Radar · Cross-site ad filter checks</title>
<style>
body{margin:28px auto;padding:0 24px;max-width:1080px;background:#101116;color:#ecedf1;font:15px/1.55 system-ui,sans-serif}
h1{font-size:28px;line-height:1.2;margin:0 0 14px}h2{font-size:19px;margin:26px 0 10px}p{color:#b7bbc5}
button{font:inherit;border:1px solid #676a78;border-radius:8px;background:#d57481;color:#171015;padding:10px 18px;cursor:pointer}
button:disabled{opacity:.5;cursor:wait}#phish-radar-result{padding:18px 22px;background:#20242c;border:1px solid #353b48;border-radius:10px;white-space:pre-wrap;font-size:16px}
#cases{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}#cases>div,#cases>nav,#cases>form,#cases>a{border:1px solid #343945;border-radius:7px;padding:10px}
#cases a{color:#c9b7eb;text-decoration:none}#cases img{display:block;max-width:100%;object-fit:contain}iframe{max-width:100%;border:0}
#floatingSlot{position:fixed;right:8px;bottom:8px;width:180px;background:#262b38;z-index:10}
#galleryControl{position:fixed;left:8px;bottom:8px;width:105px;background:#262b38;z-index:10}
#customerControl{position:fixed;right:210px;bottom:8px;width:190px;background:#262b38;z-index:10}
#cases input{max-width:100%;box-sizing:border-box}#cases button{padding:2px 8px}#phish-radar-summary{color:#8bd9aa}
</style></head><body>
<h1>Phish Radar · Cross-site ad filter verification</h1>
<p>Native browser DOM with production Extension source. Page-host and Chrome API stubs only. No advertising requests or external navigation.</p>
<button id="phish-radar-run" disabled>Run regression checks</button>
<p id="phish-radar-result">Waiting for local fixtures…</p>
<p id="phish-radar-summary">Checks include fin-manga.com, up-manga.com and a news publisher without a website allowlist.</p>
<h2>Advertising fixtures and protected reading controls</h2>
<section id="cases">
<div id="mixedSlot" class="ad-slot"><a id="mixedAd" href="https://ads.example/opaque/mixed"><img src="/image-local.svg" width="240" height="80" alt=""></a><a id="publisherBanner" data-first-party href="https://fin-manga.com/chapter/12"><img src="/image-local.svg" width="180" height="80" alt="Publisher reading banner"></a></div>
<div id="bookSlot" class="advertisement"><a id="bookAd" style="display:inline-flex!important" href="https://books.example/promotion"><img src="/image-local.svg" width="240" height="80" alt="New books this month"></a></div>
<a id="wideAd" rel="nofollow" href="https://ads.example/opaque/wide"><img id="wideImage" src="/banner-local.svg" width="728" height="200" alt=""></a>
<div id="floatingSlot"><button aria-label="Close advertisement">×</button><a id="floatingAd" rel="sponsored" href="https://ads.example/opaque/floating"><img src="/image-local.svg" width="180" height="90" alt=""></a></div>
<div class="ad-slot"><a id="gamblingAd" href="https://offers.example/register"><img src="/image-local.svg" width="240" height="80" alt="Casino bonus register"></a></div>
<div id="frameSlot" data-ad-slot="book-frame"><iframe id="frameAd" src="/frame.html" title="Book deals" width="240" height="110"></iframe></div>
<nav><a id="logoLink" rel="nofollow" href="https://publisher.example/home"><img src="/banner-local.svg" width="728" height="200" alt="Publisher navigation logo"></a></nav>
<div id="galleryControl" class="gallery"><button aria-label="Close gallery">×</button><a id="galleryLink" rel="nofollow" href="https://gallery.example/chapter"><img src="/banner-local.svg" width="100" height="90" alt="Reader gallery"></a></div>
<div class="reading-content"><a id="readerLink" rel="nofollow" href="https://cdn.example/chapter-12"><img src="/banner-local.svg" width="728" height="200" alt="Chapter 12 reader image"></a></div>
<div class="book-card"><a id="bookCardLink" rel="nofollow" href="https://publisher.example/series"><img src="/banner-local.svg" width="728" height="200" alt="Series cover"></a></div>
<a id="shareLink" href="https://www.facebook.com/share"><img src="/image-local.svg" width="40" height="40" alt="Share on Facebook"></a>
<form class="ad-slot"><input name="reader-account" placeholder="Reader account"><a id="formLink" href="https://login.example/collect?password="><img src="/image-local.svg" width="240" height="80" alt="Google verify your account"></a></form>
<div id="customerControl"><button aria-label="Close customer support">×</button><a id="customerLink" href="https://support.example/help"><img src="/image-local.svg" width="120" height="80" alt="Support representative"><span>Chat with customer support</span></a></div>
<div class="ad-slot"><a id="accountLink" href="https://accounts.google.com/o/oauth2/v2/auth"><img src="/image-local.svg" width="240" height="80" alt="Sign in with Google"></a></div>
<div id="dynamicContainer"></div>
</section>
<script src="/fixture.js"></script><script src="/app-trust.js"></script><script src="/ad-filter-policy.js"></script><script src="/ad-filter.js"></script>
</body></html>'''

FIXTURE = r'''
'use strict';
const fixtureLocation = {href:'https://www.fin-manga.com/',hostname:'www.fin-manga.com',protocol:'https:'};
const saved = {riskyAdProtection:true,adFilterMode:'all',adFilterAllowlist:[],privacyMode:true,pageScanningEnabled:false};
const messageListeners = [], storageListeners = [];
const fixtureChrome = {storage:{sync:{get:async defaults=>({...defaults,...saved})},onChanged:{addListener:fn=>storageListeners.push(fn)}},runtime:{onMessage:{addListener:fn=>messageListeners.push(fn)}}};
const realFrameUrl = new URL('/frame.html',window.location.href).href;
document.getElementById('frameAd').setAttribute('src',realFrameUrl);
const byId = id=>document.getElementById(id);
const sleep = ms=>new Promise(resolve=>setTimeout(resolve,ms));
const visible = element=>getComputedStyle(element).display!=='none' && (!element.parentElement || visible(element.parentElement));
const request = message=>new Promise((resolve,reject)=>{
 let answered=false;
 const timeout=setTimeout(()=>{if(!answered)reject(Error('Extension runtime did not respond'))},2000);
 for(const listener of messageListeners)listener(message,{},response=>{answered=true;clearTimeout(timeout);resolve(response)});
});
const setting = async change=>{Object.assign(saved,change);return request({type:'SETTINGS_UPDATED',settings:saved})};
const adIds = ['mixedAd','bookAd','wideAd','floatingAd','gamblingAd','frameAd'];
const normalAdIds = adIds.filter(id=>id!=='gamblingAd');
const controlIds = ['publisherBanner','logoLink','galleryLink','readerLink','bookCardLink','shareLink','formLink','customerLink','accountLink'];
const hosts = ['www.fin-manga.com','www.up-manga.com','news.example'];
let checks=[];
const assert = (condition,label)=>{if(!condition)throw Error(label);checks.push(label)};
const stats = async()=> (await request({type:'GET_AD_FILTER_STATS'})).stats;
const setPage = async hostname=>{
 fixtureLocation.hostname=hostname;fixtureLocation.href='https://'+hostname+'/reading';
 const apex=hostname.replace(/^www\./,'');
 for(const anchor of document.querySelectorAll('[data-first-party]'))anchor.href='https://'+apex+'/chapter/12';
 await setting({});
};

// Keep every fixture link inert, including normal controls. The extension's
// capture listener is still responsible for its filtered-click counter.
document.addEventListener('click',event=>{if(event.target.closest?.('a[href]'))event.preventDefault();});
document.addEventListener('auxclick',event=>{if(event.target.closest?.('a[href]'))event.preventDefault();});

window.addEventListener('load',async()=>{
 try {
  await sleep(350);
  const current=await stats();
  byId('phish-radar-result').textContent='Ready. All mode: '+current.hiddenCount+' advertising items hidden.\nProtected reading, navigation, forms and account controls remain visible.';
  byId('phish-radar-run').disabled=false;
 }catch(error){byId('phish-radar-result').textContent='Fixture initialization failed: '+error.message}
});

byId('phish-radar-run').addEventListener('click',async()=>{
 checks=[];const output=byId('phish-radar-result');const button=byId('phish-radar-run');button.disabled=true;output.textContent='Running native DOM checks…';
 try {
  await setting({riskyAdProtection:true,adFilterMode:'all',adFilterAllowlist:[]});
  for(const hostname of hosts){
   await setPage(hostname);
   for(const id of adIds)assert(!visible(byId(id)),hostname+': '+id+' hidden in all mode');
   for(const id of controlIds)assert(visible(byId(id)),hostname+': '+id+' preserved');
   assert(visible(byId('mixedSlot')),hostname+': mixed slot retains first-party reading banner');
   assert((await stats()).hiddenCount===adIds.length,hostname+': exact ad-item count');
  }
  await setPage('www.fin-manga.com');
  await setting({adFilterMode:'risky'});
  for(const id of normalAdIds)assert(visible(byId(id)),'Risky mode keeps normal identified ad '+id);
  assert(!visible(byId('gamblingAd')),'Risky mode retains gambling-promotion detection');
  assert((await stats()).mode==='risky','Stats reports risky mode');
  await setting({adFilterMode:'all'});
  for(const id of adIds)assert(!visible(byId(id)),'Switching back to all mode hides '+id);

  await setting({riskyAdProtection:false});
  assert(adIds.every(id=>visible(byId(id))),'Off switch restores every advertising fixture');
  assert(byId('bookAd').style.getPropertyValue('display')==='inline-flex'&&byId('bookAd').style.getPropertyPriority('display')==='important','Original inline display and priority restored');
  assert((await stats()).enabled===false,'Off switch reports filtering disabled');
  await setting({riskyAdProtection:true,adFilterAllowlist:['www.fin-manga.com']});
  assert(adIds.every(id=>visible(byId(id))),'Exact-host exception restores every advertising fixture');
  assert((await stats()).siteExempt===true,'Exact-host exception reported');
  await setting({adFilterAllowlist:['fin-manga.com']});
  assert(adIds.every(id=>!visible(byId(id))),'Apex exception does not exempt the www hostname');
  await setting({adFilterAllowlist:[]});

  const beforeClick=await stats();
  byId('bookAd').dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
  assert((await stats()).blockedClicks===beforeClick.blockedClicks+1,'Filtered ad click is intercepted by the production runtime');
  let decision=await request({type:'CHECK_AD_FILTER_TARGET',targetUrl:byId('wideAd').href});
  assert(decision.blocked===true,'An identified generic-banner popup destination is recognized');
  decision=await request({type:'CHECK_AD_FILTER_TARGET',targetUrl:byId('accountLink').href});
  assert(decision.blocked===false,'Normal account popup destination is preserved');
  const beforePopup=await stats();
  await request({type:'AD_FILTER_POPUP_BLOCKED',targetUrl:byId('wideAd').href});
  assert((await stats()).blockedPopups===beforePopup.blockedPopups+1,'Recognized advertising popup counter updates');

  const originalWideHref=byId('wideAd').href;
  byId('wideAd').href='https://fin-manga.com/chapter/14';await sleep(350);
  assert(visible(byId('wideAd')),'Async href change to publisher apex restores a previously hidden banner');
  byId('wideAd').href=originalWideHref;await sleep(350);
  assert(!visible(byId('wideAd')),'Async href change back to an external creative is filtered');
  byId('wideImage').src='/image-local.svg';await sleep(350);
  assert(visible(byId('wideAd')),'Async source change removes creative evidence and restores a generic image');
  byId('wideImage').src='/banner-local.svg';await sleep(350);
  assert(!visible(byId('wideAd')),'Async creative source change is filtered again');
  byId('frameAd').src='https://fin-manga.com/reader-frame';await sleep(350);
  assert(visible(byId('frameAd'))&&visible(byId('frameSlot')),'Async iframe source change to first-party restores frame and slot');
  byId('frameAd').src=realFrameUrl;await sleep(350);
  assert(!visible(byId('frameAd')),'Standalone explicit ad iframe is filtered after source changes back');

  const dynamic=document.createElement('div');dynamic.className='ad-slot';
  const link=document.createElement('a');link.href='https://ads.example/opaque/dynamic';
  const image=document.createElement('img');image.src='/image-local.svg';image.width=200;image.height=80;link.append(image);dynamic.append(link);byId('dynamicContainer').append(dynamic);
  await sleep(350);assert(!visible(link),'Dynamically inserted identified ad is filtered');
  link.href='https://fin-manga.com/chapter/15';await sleep(350);
  assert(visible(link)&&visible(dynamic),'Dynamic ad changing into first-party reading navigation is restored');dynamic.remove();await sleep(350);

  const deepFormWrapper=document.createElement('div');
  const innerFormWrapper=document.createElement('div');
  const embeddedForm=document.createElement('form');
  const embeddedInput=document.createElement('input');embeddedInput.name='overlay-account';
  embeddedForm.append(embeddedInput);innerFormWrapper.append(embeddedForm);deepFormWrapper.append(innerFormWrapper);byId('floatingSlot').append(deepFormWrapper);
  await sleep(350);
  assert(visible(byId('floatingAd'))&&visible(byId('floatingSlot'))&&visible(embeddedForm),'A form inserted deeply into a hidden floating ad restores the protected overlay');
  assert((await stats()).hiddenCount===adIds.length-1,'Protected floating form is removed from the filtered-ad count');
  deepFormWrapper.remove();await sleep(350);
  assert(!visible(byId('floatingAd')),'Removing the protected form restores identified floating-ad filtering');

  byId('wideAd').removeAttribute('href');await sleep(350);
  assert(visible(byId('wideAd')),'Removing href restores a previously hidden generic image');
  assert((await stats()).hiddenCount===adIds.length-1,'A destinationless image is removed from the filtered-ad count');
  byId('wideAd').href=originalWideHref;await sleep(350);
  assert(!visible(byId('wideAd')),'Restoring the advertising href filters the generic creative again');

  const firstPartyFrameLink=document.createElement('a');firstPartyFrameLink.href='https://fin-manga.com/reader-frame';
  byId('frameSlot').append(firstPartyFrameLink);firstPartyFrameLink.append(byId('frameAd'));await sleep(350);
  assert(visible(byId('frameAd'))&&visible(firstPartyFrameLink)&&visible(byId('frameSlot')),'Moving a hidden iframe inside a first-party reading anchor restores its presentation');
  assert((await stats()).hiddenCount===adIds.length-1,'First-party wrapped iframe is removed from filtered-ad count');
  byId('frameSlot').append(byId('frameAd'));firstPartyFrameLink.remove();await sleep(350);
  assert(!visible(byId('frameAd')),'Moving iframe back to a standalone ad slot reactivates filtering');

  const lateFloating=document.createElement('div');lateFloating.style.cssText='position:fixed;left:210px;bottom:8px;width:180px';
  const lateFloatingLink=document.createElement('a');lateFloatingLink.href='https://ads.example/opaque/late-close';lateFloatingLink.rel='sponsored';
  const lateFloatingImage=document.createElement('img');lateFloatingImage.src='/image-local.svg';lateFloatingImage.width=180;lateFloatingImage.height=90;
  lateFloatingLink.append(lateFloatingImage);lateFloating.append(lateFloatingLink);byId('dynamicContainer').append(lateFloating);await sleep(350);
  assert(visible(lateFloatingLink),'A floating sponsored image without a close control is not enough presentation evidence');
  const lateClose=document.createElement('button');lateClose.textContent='×';lateClose.setAttribute('aria-label','Close advertisement');lateFloating.append(lateClose);await sleep(350);
  assert(!visible(lateFloatingLink)&&!visible(lateFloating),'Adding a close control later filters the identified floating image asynchronously');
  assert((await stats()).hiddenCount===adIds.length+1,'Late floating ad adds one filtered item');
  lateFloating.remove();await sleep(350);
  assert((await stats()).hiddenCount===adIds.length,'Removing the late floating ad restores the stable ad count');

  byId('bookAd').style.setProperty('display','grid','important');await sleep(350);
  assert(!visible(byId('bookAd')),'Author display change while hidden is still filtered');
  await setting({riskyAdProtection:false});
  assert(visible(byId('bookAd'))&&byId('bookAd').style.getPropertyValue('display')==='grid'&&byId('bookAd').style.getPropertyPriority('display')==='important','Turning off preserves the latest author display and priority');
  await setting({riskyAdProtection:true,adFilterMode:'all'});

  saved.adFilterMode='risky';
  for(const listener of storageListeners)listener({adFilterMode:{newValue:'risky',oldValue:'all'}},'sync');
  await sleep(350);
  assert(visible(byId('bookAd'))&&!visible(byId('gamblingAd'))&&(await stats()).mode==='risky','Storage preference changes update actual filter mode');
  await setting({adFilterMode:'all'});
  assert(saved.privacyMode===true&&saved.pageScanningEnabled===false,'Ad filtering remains independent of Privacy Mode and page scanning');
  assert(controlIds.every(id=>visible(byId(id))),'All protected controls remain visible after mutations and preference changes');
  const finalStats=await stats();
  assert(finalStats.hiddenCount===adIds.length,'Final all-mode advertising count is stable');
  window.fixtureResults={passed:true,checks:checks.length,hosts,hiddenAdItems:finalStats.hiddenCount,protectedControls:controlIds.length,stats:finalStats,runtimeSource:'extension/ad-filter.js (unchanged; lexical API/page stubs)'};
  output.textContent='PASS · '+checks.length+' native DOM checks\n3 publishers: fin-manga.com · up-manga.com · news.example\nAll mode: '+finalStats.hiddenCount+'/'+adIds.length+' advertising items hidden\nProtected reading / navigation / form / account controls: '+controlIds.length+'/'+controlIds.length+' visible\nRisky mode, off switch, exact-site exception, popup decisions, dynamic sources and latest-style restoration passed.';output.style.color='#91dfb0';
 }catch(error){window.fixtureResults={passed:false,error:error.message,checks};output.textContent='FAIL: '+error.message+'\nPassed checks before failure: '+checks.length;output.style.color='#ff9292'}
 finally{button.disabled=false}
});
'''

BANNER_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="728" height="200"><rect width="728" height="200" fill="#344352"/><text x="24" y="110" fill="#d6e3ee" font-size="25">Local image fixture</text></svg>'
IMAGE_SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="120"><rect width="160" height="120" fill="#2d3f3a"/><text x="10" y="65" fill="#cfdfd7" font-size="13">Local content image</text></svg>'
FRAME_HTML = b'<!doctype html><meta charset="utf-8"><title>Local frame fixture</title><img alt="Local book image" src="/image-local.svg" width="200" height="100">'
CSP = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; connect-src 'none'; object-src 'none'; form-action 'none'; base-uri 'none'"


class ElementCounter(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = 0

    def handle_starttag(self, _tag, _attrs):
        self.elements += 1


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = self.path.split('?', 1)[0]
        if route == '/':
            payload, content_type = HTML.encode('utf-8'), 'text/html'
        elif route == '/fixture.js':
            payload, content_type = FIXTURE.encode('utf-8'), 'text/javascript'
        elif route == '/banner-local.svg':
            payload, content_type = BANNER_SVG, 'image/svg+xml'
        elif route == '/image-local.svg':
            payload, content_type = IMAGE_SVG, 'image/svg+xml'
        elif route == '/frame.html':
            payload, content_type = FRAME_HTML, 'text/html'
        elif route == '/ad-filter.js':
            source = (ROOT / 'extension/ad-filter.js').read_bytes()
            payload = b'(function(location,chrome){\n' + source + b'\n})(fixtureLocation,fixtureChrome);'
            content_type = 'text/javascript'
        elif route in {'/app-trust.js', '/ad-filter-policy.js'}:
            payload, content_type = (ROOT / 'extension' / route[1:]).read_bytes(), 'text/javascript'
        elif route == '/favicon.ico':
            self.send_response(204)
            self.end_headers()
            return
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', content_type + '; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', CSP)
        self.end_headers()
        self.wfile.write(payload)


if __name__ == '__main__':
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8768)
    parser.add_argument('--write-only', action='store_true', help='Write fixture assets without starting a server.')
    args = parser.parse_args()
    count = ElementCounter()
    count.feed(HTML)
    if count.elements >= 100:
        raise RuntimeError(f'Fixture should remain small; got {count.elements} elements')
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'browser-fixture.html').write_text(HTML, encoding='utf-8')
    (OUT / 'browser-fixture.js').write_text(FIXTURE, encoding='utf-8')
    print(f'Fixture: {count.elements} elements; production runtime unchanged. http://127.0.0.1:{args.port}/', flush=True)
    if not args.write_only:
        HTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
