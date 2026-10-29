// Real scanner flow with controlled API replies; no account or history writes.
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.BROWSER_EXECUTABLE ? {executablePath:process.env.BROWSER_EXECUTABLE} : {})});
  try {
    const page=await browser.newPage();
    let score=60, failure=false;
    const errors=[];
    page.on('pageerror', e=>errors.push(e.message));
    await page.route('**/*', async route=>{
      const url=new URL(route.request().url());
      if(url.port!=='8765') return route.continue();
      let body={}; let status=200;
      if(url.pathname==='/auth/me') body={user_id:1,username:'Scanner test',role:'user'};
      if(url.pathname==='/health') body={ok:true,model_ready:true,model_policy:{fusion_method:'ml_only',warning_threshold:60,blocking_threshold:80},llm:{llm_ready:true}};
      if(url.pathname==='/history') body=route.request().method()==='POST'?{history_id:1}:{items:[]};
      if(url.pathname==='/predict') {
        body={ok:true,risk_score:score,model_status:'ready',decision:score>=80?'block':score>=60?'warn':'allow',warning_threshold:60,blocking_threshold:80,random_forest_score:score,fusion_method:'ml_only'};
        if(failure){status=503;body={detail:'Test model request failed'};}
      }
      if(url.pathname==='/explain') body={ok:true,provider:'test',llm:{simple_explanation:'Test result',user_advice:'Test advice'}};
      await route.fulfill({status,json:body,headers:{'Access-Control-Allow-Origin':'http://127.0.0.1:5505','Access-Control-Allow-Credentials':'true'}});
    });
    await page.goto('http://127.0.0.1:5505/#/scan');
    const scan=async()=>{
      await page.locator('#urlInput').fill('https://example.com/');
      await page.getByRole('button',{name:'ตรวจสอบ',exact:true}).click();
      await page.getByText('วิเคราะห์เสร็จแล้ว',{exact:true}).waitFor();
    };
    await scan();
    assert.equal(await page.locator('.decision-badge.decision-warn').count(),1);
    score=59; await scan();
    assert.equal(await page.locator('.decision-badge.decision-allow').count(),1);
    score=79; await scan();
    assert.equal(await page.locator('.decision-badge.decision-warn').count(),1);
    score=80; await scan();
    assert.equal(await page.locator('.decision-badge.decision-block').count(),1);
    failure=true; await scan();
    assert.equal(await page.locator('.decision-badge.decision-unknown').count(),1);
    await page.getByText(/ครั้งนี้ไม่ได้รับผลจากโมเดล/).waitFor();
    await page.getByText(/Test model request failed/).waitFor();
    assert.deepEqual(errors,[]);
    console.log('Scanner browser tests passed: boundaries 59/60/79/80 and explicit failed-scan state despite healthy service.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
