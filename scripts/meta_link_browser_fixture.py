"""Serve a local native-DOM regression fixture for the submitted Meta AI link.

Run explicitly with the workspace Python; this module never starts a server
when imported. Extension sources are served without edits, inside a lexical
location/Chrome API wrapper. No destination is fetched, and link default
navigation is cancelled. MutationObserver, tooltip DOM, and click propagation
are the browser's real implementations.
"""

from html import escape
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlencode
import argparse
import json


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/meta-link-fix-20261009"


def fixtures():
    submitted = json.loads((OUT / "user-link.json").read_text(encoding="utf-8-sig"))["url"]
    destination = parse_qs(urlsplit(submitted).query)["u"][0]
    phishing = "https://meta.ai.evil.example/login?password=SyntheticCredential1234567890"
    dynamic_phishing = "https://meta-ai.example/account?password=SyntheticCredential1234567890"

    def wrap(target):
        return "https://l.facebook.com/l.php?" + urlencode({"u": target, "h": "synthetic-link-shim"})

    return {
        "submitted": submitted,
        "destination": destination,
        "phishing": phishing,
        "wrappedPhishing": wrap(phishing),
        "dynamicPhishing": dynamic_phishing,
        "wrappedDynamicPhishing": wrap(dynamic_phishing),
    }


def build_html(data):
    return """<!doctype html>
<html lang="th"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Phish Radar · Meta link regression</title><link rel="stylesheet" href="/content.css">
<style>
body{background:#101116;color:#eaeaf0;font:16px system-ui,sans-serif;max-width:900px;margin:38px auto;padding:0 24px}
h1{font-size:28px;margin-bottom:12px}p{line-height:1.6;color:#b0b5c2}button{font:inherit;background:#dd7985;color:#111;border:0;border-radius:8px;padding:12px 18px;cursor:pointer}
button:disabled{opacity:.55;cursor:wait}.row{display:flex;gap:16px;align-items:center;padding:24px 0;border-bottom:1px solid #343744}.row>span{color:#a4aabb;min-width:190px}.row a{color:#eedde1;text-decoration:none;padding:12px 18px;background:#252733;border-radius:8px;display:inline-block}
#result{margin:22px 0;padding:22px;background:#20242c;white-space:pre-wrap;border-radius:10px;line-height:1.65;color:#b6becd}.note{font-size:14px;color:#8992a5}.legend{color:#96c8a6}
</style></head><body>
<h1>Phish Radar · Meta AI link verification</h1>
<p>ใช้ URL ที่ผู้ใช้ส่งมาและ Extension runtime จริงบน DOM ของ browser<br>จำลอง Facebook link shim ในเครื่อง โดยไม่เรียก backend หรือเปิด URL ปลายทาง</p>
<button id="runTests" disabled>Run regression checks</button>
<div id="result" role="status">Waiting for the Extension runtime…</div>
<section id="fixtureLinks">
<div class="row" id="metaRow"><span>Submitted Meta AI bookmark</span><a id="metaLink" target="_blank" href="@META@">Meta AI</a></div>
<div class="row" id="phishRow"><span>Wrapped phishing fixture</span><a id="phishLink" target="_blank" href="@PHISH@">Meta AI sign in</a></div>
<div class="row" id="spaRow"><span>SPA link: phishing → Meta → phishing</span><a id="spaLink" target="_blank" href="@SPA@">Meta AI</a></div>
</section>
<p class="legend">Meta AI bookmark ควรไม่มีป้ายเตือน · phishing fixture ต้องยังมีป้ายและส่ง OPEN_WARNING</p>
<p class="note">การทดสอบเฉพาะกรณีนี้ไม่ใช่การวัด population FPR หรือประสิทธิภาพ Random Forest</p>
<script src="/fixture.js"></script><script src="/app-trust.js"></script><script src="/analyzer.js"></script><script src="/content.js"></script>
</body></html>""".replace("@META@", escape(data["submitted"], quote=True)).replace("@PHISH@", escape(data["wrappedPhishing"], quote=True)).replace("@SPA@", escape(data["wrappedDynamicPhishing"], quote=True))


def build_fixture_js(data):
    return "const fixtureUrls = " + json.dumps(data, ensure_ascii=False) + ";\n" + r"""
'use strict';
const fixtureLocation = new URL('https://www.facebook.com/');
const fixtureMessages = [], fixtureMessageListeners = [], fixtureStorageListeners = [];
const fixtureSettings = {
  threshold:60,warnMedium:true,highlightLinks:true,protectForms:false,
  showStatusPanel:false,pageScanningEnabled:true,privacyMode:true,
  searchProtection:true,clipboardProtection:false,phishRadarTheme:'dark'
};
const fixtureChrome = {
  runtime:{
    sendMessage(message,callback){
      fixtureMessages.push(message);
      callback(message.type==='GET_SETTINGS' ? {ok:true,settings:{...fixtureSettings}} : {ok:true,fixture:true});
    },
    onMessage:{addListener(listener){fixtureMessageListeners.push(listener)}}
  },
  storage:{
    sync:{get:async defaults=>({...defaults,...fixtureSettings})},
    onChanged:{addListener(listener){fixtureStorageListeners.push(listener)}}
  }
};
// Cancel harmless and malicious link defaults alike. The Extension capture
// listener is still responsible for recording actual OPEN_WARNING decisions.
document.addEventListener('click',event=>{if(event.target.closest?.('a[href]'))event.preventDefault()});
document.addEventListener('auxclick',event=>{if(event.target.closest?.('a[href]'))event.preventDefault()});

const fixtureSleep = ms=>new Promise(resolve=>setTimeout(resolve,ms));
const fixtureRequest = message=>new Promise((resolve,reject)=>{
  let answered=false;
  for(const listener of fixtureMessageListeners)listener(message,{},response=>{answered=true;resolve(response)});
  setTimeout(()=>{if(!answered)reject(Error('No runtime response to '+message.type))},1500);
});
const fixtureWait = async (predicate,label,timeout=6500)=>{
  const deadline=performance.now()+timeout;
  while(performance.now()<deadline){if(predicate())return;await fixtureSleep(45)}
  throw Error(label);
};
const fixtureBadge = link=>[...document.querySelectorAll('.phish-radar-badge')].find(badge=>badge.dataset.phishRadarFor===link.dataset.phishRadarId);
const fixtureTooltipData = link=>{try{return JSON.parse(link.dataset.phishRadarTooltip||'{}')}catch{return {}}};
const fixtureOpenWarnings = ()=>fixtureMessages.filter(message=>message.type==='OPEN_WARNING');
let fixtureChecks=[];
const fixtureAssert = (condition,label)=>{if(!condition)throw Error(label);fixtureChecks.push(label)};
window.fixtureResults={passed:null,phase:'initializing'};

window.addEventListener('load',async()=>{
  const result=document.getElementById('result');
  try {
    await fixtureWait(()=>fixtureMessageListeners.length>0,'Content runtime did not load');
    // Allow boot to register its real MutationObserver before the SPA test.
    await fixtureSleep(250);
    const scan=await fixtureRequest({type:'SCAN_LINKS_NOW'});
    if(!scan.ok)throw Error('Initial link scan failed');
    const meta=document.getElementById('metaLink');
    result.textContent=`Ready · native DOM and MutationObserver\nSubmitted Meta AI bookmark badge: ${fixtureBadge(meta)?'PRESENT':'none'}\nWrapped phishing badge: ${fixtureBadge(document.getElementById('phishLink'))?'present':'MISSING'}\nClick Run regression checks.`;
    document.getElementById('runTests').disabled=false;
    window.fixtureResults={passed:null,phase:'ready',initialScan:scan,metaDestinationLength:fixtureUrls.destination.length};
  }catch(error){window.fixtureResults={passed:false,phase:'initialization',error:error.message};result.textContent='FAIL: '+error.message;result.style.color='#ff8c8c'}
});

document.getElementById('runTests').addEventListener('click',async()=>{
  const button=document.getElementById('runTests'), result=document.getElementById('result');
  const meta=document.getElementById('metaLink'), phish=document.getElementById('phishLink'), spa=document.getElementById('spaLink');
  button.disabled=true;result.textContent='Running native DOM regression checks…';fixtureChecks=[];
  try {
    // Reset only through ordinary DOM changes. Manual scan is used to set up
    // the initial state; every subsequent href transition relies on the real
    // content runtime MutationObserver, without SCAN_LINKS_NOW calls.
    spa.href=fixtureUrls.wrappedDynamicPhishing;
    await fixtureRequest({type:'SCAN_LINKS_NOW'});
    fixtureAssert(fixtureUrls.destination.length===239,'Exact submitted destination remains 239 characters');
    fixtureAssert(!fixtureBadge(meta),'Submitted Meta AI bookmark has no warning badge');
    fixtureAssert(meta.dataset.phishRadarMarked!=='1','Submitted Meta AI bookmark is not marked risky');
    const metaRule=PhishRadarAnalyzer.analyzeUrl(fixtureUrls.destination,{linkText:'Meta AI'});
    fixtureAssert(metaRule.score<31,'Submitted Meta AI local rule score stays below the tooltip warning boundary');
    fixtureAssert(!metaRule.reasons.some(reason=>reason.points>0&&['brand','credential','combo'].includes(reason.category)),'Meta bookmark has no false brand or credential combination');
    fixtureAssert(!!fixtureBadge(phish),'Wrapped phishing destination keeps its warning badge');
    fixtureAssert(fixtureTooltipData(phish).url===fixtureUrls.phishing,'Wrapped phishing tooltip assesses the actual destination');
    fixtureAssert(fixtureTooltipData(phish).result.score>=60,'Wrapped phishing remains above the click warning threshold');

    const initialWarnings=fixtureOpenWarnings().length;
    meta.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));await fixtureSleep(60);
    fixtureAssert(fixtureOpenWarnings().length===initialWarnings,'Meta bookmark click does not send OPEN_WARNING');
    phish.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
    await fixtureWait(()=>fixtureOpenWarnings().length>initialWarnings,'Phishing click did not send OPEN_WARNING');
    fixtureAssert(fixtureOpenWarnings().at(-1).target===fixtureUrls.phishing,'Phishing click sends OPEN_WARNING for the actual destination');

    fixtureBadge(phish).dispatchEvent(new MouseEvent('mouseenter'));
    await fixtureSleep(70);
    let tip=document.getElementById('phish-radar-link-tooltip');
    fixtureAssert(tip?.classList.contains('phish-radar-link-tooltip-open'),'Native hover opens the phishing tooltip');
    fixtureAssert(tip.querySelector('.phish-radar-link-tooltip-score').textContent.includes('คะแนนกฎ URL (ในเครื่อง)'),'Tooltip explicitly identifies local URL rules');
    fixtureAssert(!tip.querySelector('.phish-radar-link-tooltip-score').textContent.includes('Random Forest'),'Tooltip score is not labelled Random Forest');
    fixtureAssert(tip.querySelector('.phish-radar-link-tooltip-footer').textContent.includes('คะแนนกฎถึงเกณฑ์เตือนก่อนเปิดลิงก์'),'High-score tooltip states that the click threshold was reached');

    fixtureAssert(!!fixtureBadge(spa),'Initial SPA phishing link is marked');
    const originalSpaBadge=fixtureBadge(spa);
    originalSpaBadge.dispatchEvent(new MouseEvent('mouseenter'));
    spa.href=fixtureUrls.submitted;
    await fixtureWait(()=>!fixtureBadge(spa)&&spa.dataset.phishRadarMarked!=='1','MutationObserver did not remove the stale SPA badge');
    fixtureAssert(!originalSpaBadge.isConnected,'SPA phishing-to-Meta transition removes its old badge');
    fixtureAssert(!spa.dataset.phishRadarTooltip,'SPA phishing-to-Meta transition clears stale tooltip data');
    fixtureAssert(!document.getElementById('phish-radar-link-tooltip')?.classList.contains('phish-radar-link-tooltip-open'),'SPA safe transition closes the old phishing tooltip');
    const safeSpaWarnings=fixtureOpenWarnings().length;
    spa.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));await fixtureSleep(60);
    fixtureAssert(fixtureOpenWarnings().length===safeSpaWarnings,'SPA link changed to Meta no longer sends OPEN_WARNING');

    spa.href=fixtureUrls.wrappedDynamicPhishing;
    await fixtureWait(()=>!!fixtureBadge(spa)&&fixtureTooltipData(spa).url===fixtureUrls.dynamicPhishing,'MutationObserver did not restore the SPA phishing badge');
    fixtureAssert(fixtureTooltipData(spa).result.score>=60,'SPA Meta-to-phishing transition restores the risky score');
    const badges=[...document.querySelectorAll('.phish-radar-badge')].filter(badge=>badge.dataset.phishRadarFor===spa.dataset.phishRadarId);
    fixtureAssert(badges.length===1,'SPA transitions do not duplicate warning badges');
    spa.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));
    await fixtureWait(()=>fixtureOpenWarnings().length>safeSpaWarnings,'Restored SPA phishing click did not send OPEN_WARNING');
    fixtureAssert(fixtureOpenWarnings().at(-1).target===fixtureUrls.dynamicPhishing,'SPA phishing click uses the current destination');
    fixtureBadge(spa).dispatchEvent(new MouseEvent('mouseenter'));await fixtureSleep(60);
    tip=document.getElementById('phish-radar-link-tooltip');
    fixtureAssert(Number(tip.querySelector('.phish-radar-link-tooltip-score b').textContent)===fixtureTooltipData(spa).result.score,'Visible tooltip score matches the current SPA result');

    const scan=await fixtureRequest({type:'GET_LAST_SCAN'});
    window.fixtureResults={
      passed:true,phase:'complete',checks:fixtureChecks.length,checkNames:[...fixtureChecks],
      metaScore:metaRule.score,metaHasBadge:!!fixtureBadge(meta),phishScore:fixtureTooltipData(phish).result.score,
      spaScore:fixtureTooltipData(spa).result.score,spaBadgeCount:badges.length,
      openWarningTargets:fixtureOpenWarnings().map(message=>message.target),
      tooltipScoreText:tip.querySelector('.phish-radar-link-tooltip-score').textContent,
      tooltipCaption:tip.querySelector('.phish-radar-link-tooltip-footer').textContent,lastScan:scan.lastScan,
      noBackendRequests:!fixtureMessages.some(message=>message.type==='ANALYZE_URL'),locationUnchanged:window.location.hostname==='127.0.0.1'
    };
    result.textContent=`PASS · ${fixtureChecks.length} native DOM checks\nMeta AI bookmark: ${metaRule.score}/100 · no warning badge\nWrapped phishing: ${window.fixtureResults.phishScore}/100 · OPEN_WARNING retained\nSPA phishing → Meta → phishing: badge removed and restored\nTooltip identifies local URL rules and uses the current score.\nNo backend or destination request was made.`;
    result.style.color='#8ee0ad';
  }catch(error){window.fixtureResults={passed:false,phase:'regression',error:error.message,checks:fixtureChecks};result.textContent='FAIL: '+error.message;result.style.color='#ff8c8c'}
  finally{button.disabled=false}
});
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route = self.path.split("?", 1)[0]
        if route == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        data = fixtures()
        if route == "/":
            payload, content_type = build_html(data).encode("utf-8"), "text/html"
        elif route == "/fixture.js":
            payload, content_type = build_fixture_js(data).encode("utf-8"), "text/javascript"
        elif route in {"/content.js", "/analyzer.js"}:
            source = (ROOT / "extension" / route[1:]).read_bytes()
            payload = b"(function(location,chrome){\n" + source + b"\n})(fixtureLocation,fixtureChrome);"
            content_type = "text/javascript"
        elif route in {"/app-trust.js", "/content.css"}:
            payload = (ROOT / "extension" / route[1:]).read_bytes()
            content_type = "text/css" if route.endswith(".css") else "text/javascript"
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-DNS-Prefetch-Control", "off")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    HTML = build_html(fixtures())
    (OUT / "browser-fixture.html").write_text(HTML, encoding="utf-8")
    print(f"Meta-link native DOM fixture: http://127.0.0.1:{args.port}/", flush=True)
    HTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
