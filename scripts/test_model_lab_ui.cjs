/* Browser interaction/visual checks with mocked API. No login, DB writes or URL scans. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const dist = path.join(root, 'web-app', 'dist');
const artifacts = path.join(root, 'tmp', 'model-lab-ui');
fs.mkdirSync(artifacts, { recursive: true });
const items = ['simple_v1','simple_v2','simple_v3'].map(id => {
  const dir = path.join(root, 'backend','data',id);
  const evaluation = JSON.parse(fs.readFileSync(path.join(dir,'evaluation.json'),'utf8'));
  const analysis = JSON.parse(fs.readFileSync(path.join(dir,'error_analysis.json'),'utf8'));
  return {id, formula:evaluation.risk_formula, rows:evaluation.dataset_rows, analysis, promotion_ready:false};
});
const types = {'.html':'text/html','.js':'text/javascript','.css':'text/css','.woff2':'font/woff2','.png':'image/png','.svg':'image/svg+xml'};
const server = http.createServer((request,response) => {
  const file = path.resolve(dist, '.' + (new URL(request.url,'http://localhost').pathname === '/' ? '/index.html' : new URL(request.url,'http://localhost').pathname));
  if (!file.startsWith(dist + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) { response.writeHead(404); response.end(); return; }
  response.setHeader('Content-Type',types[path.extname(file)] || 'application/octet-stream'); fs.createReadStream(file).pipe(response);
});
(async () => {
  let browser;
  try {
    await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
    browser = await chromium.launch({ channel:process.env.PLAYWRIGHT_CHANNEL || 'msedge', headless:true });
    const context = await browser.newContext({viewport:{width:1440,height:1000}, reducedMotion:'reduce'});
    const page = await context.newPage();
    const errors = []; page.on('pageerror', error => errors.push(error.message));
    let role = 'admin', failModels = false;
    await page.route('http://127.0.0.1:8765/**', async route => {
      const endpoint = new URL(route.request().url()).pathname;
      let data = {}, status = 200;
      if (endpoint === '/auth/me') data = {user_id:1,username:'QA Admin',role};
      else if (endpoint === '/health') data = {ok:true,model_ready:true,database:{connected:true,auth_schema_ready:true,history_schema_ready:true}};
      else if (endpoint === '/workspace/admin/models') {
        status = failModels ? 503 : 200;
        data = failModels ? {detail:'รายงานไม่พร้อม ทดสอบข้อผิดพลาด'} : {items,production_sha256:'qa-production-hash'};
      } else if (endpoint === '/workspace/admin/feedback-export') data = {items:[{training_eligible:false,reviewed_label:'safe',sanitized_url:'https://example.com/path'}],total:1,purpose:'review_queue_only_not_training_data'};
      else data = {items:[],total:0};
      await route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
    });
    const url = `http://127.0.0.1:${server.address().port}/#/admin`;
    await page.goto(url);
    await page.getByRole('button',{name:'วิเคราะห์โมเดล',exact:true}).click();
    await page.getByRole('heading',{name:'เปรียบเทียบรอบทดลอง'}).waitFor();
    await page.getByLabel('เลือกรอบที่ต้องการวิเคราะห์').selectOption('simple_v2');
    await page.getByRole('heading',{name:'simple_v2 · สาเหตุที่ผ่าน / ไม่ผ่าน'}).waitFor();
    await page.getByLabel('แยกตาม',{exact:true}).selectOption('source');
    assert(await page.getByRole('cell',{name:'mendeley_webpage_v3',exact:true}).count() > 0);
    assert.equal(await page.locator('.model-lab a[href^="http"]').count(), 0);
    await page.screenshot({path:path.join(artifacts,'desktop.png'),fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), 'Mobile body overflows');
    await page.screenshot({path:path.join(artifacts,'mobile.png'),fullPage:true});
    failModels = true;
    await page.getByRole('button',{name:'รีเฟรช',exact:true}).click();
    await page.getByRole('alert').waitFor();
    failModels = false;
    await page.getByRole('button',{name:'ลองใหม่',exact:true}).click();
    await page.getByRole('heading',{name:'เปรียบเทียบรอบทดลอง'}).waitFor();
    await page.getByRole('button',{name:'ตรวจ Feedback',exact:true}).click();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button',{name:/ดาวน์โหลด JSON ของหน้านี้/}).click();
    const download = await downloadPromise;
    const exportPath = path.join(artifacts,'feedback.json'); await download.saveAs(exportPath);
    assert.equal(JSON.parse(fs.readFileSync(exportPath,'utf8')).items[0].training_eligible, false);
    role = 'user'; await page.reload();
    await page.getByRole('heading',{name:'ไม่มีสิทธิ์เข้าถึง'}).waitFor();
    assert.deepEqual(errors, []);
    console.log('Model lab UI passed: experiment selection, filters, mobile layout, retry, JSON download, non-admin view; API mocked.');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
