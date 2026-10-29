// Browser integration tests use controlled API responses, never real accounts.
const assert = require('node:assert/strict');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

(async () => {
  const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  try {
    const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let chats = 0, predicts = 0, lastChat;
    await page.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.port !== '8765') return route.continue();
      let body = {};
      if (url.pathname === '/auth/me') body = { user_id: 1, username: 'Chat test', role: 'user' };
      if (url.pathname === '/history') body = route.request().method() === 'POST' ? { history_id: 1 } : { items: [] };
      if (url.pathname === '/health') body = { ok: true, model_ready: true, llm: { provider: 'ollama', llm_ready: true } };
      if (url.pathname === '/chat') { chats++; lastChat = route.request().postDataJSON(); body = { ok: false, provider: 'fallback' }; }
      if (url.pathname === '/predict') { predicts++; body = { ok: true, risk_score: 77, model_status: 'ready', decision: 'warn', warning_threshold: 61, blocking_threshold: 81 }; }
      if (url.pathname === '/explain') body = { ok: true, provider: 'ollama', llm: { simple_explanation: 'พบสัญญาณที่ควรระวัง', user_advice: 'ตรวจโดเมนก่อนกรอกข้อมูล' } };
      await route.fulfill({ json: body, headers: { 'Access-Control-Allow-Origin': 'http://127.0.0.1:5505', 'Access-Control-Allow-Credentials': 'true' } });
    });
    await page.goto('http://127.0.0.1:5505/#/scan');
    await page.getByRole('button', { name: 'เปิดแชทผู้ช่วย', exact: true }).click();
    await page.getByRole('button', { name: 'Phishing คืออะไร', exact: true }).click();
    await page.getByText('คำแนะนำสำรอง · AI ยังไม่พร้อม', { exact: true }).waitFor();
    assert.equal(chats, 1);
    const input = page.getByLabel('ข้อความหรือ URL ที่ต้องการตรวจ', { exact: true });
    await input.fill('ช่วยตรวจ https://example.com/login');
    await page.getByRole('button', { name: 'ส่งข้อความ', exact: true }).click();
    await page.locator('.radar-chat-result').waitFor();
    assert.match(await page.locator('.radar-chat-result').innerText(), /77/);
    assert.equal(predicts, 1);
    await page.getByRole('button', { name: 'อธิบายผลตรวจล่าสุด', exact: true }).click();
    await page.waitForFunction(() => document.querySelectorAll('.radar-chat-message.assistant').length === 4);
    assert.equal(lastChat.context.score, 77);
    assert.match(await page.locator('.radar-chat-log').innerText(), /77\/100/);
    await page.screenshot({ path: path.join(__dirname, '../output/chat-desktop.png') });
    await page.setViewportSize({ width: 390, height: 844 });
    const box = await page.locator('.radar-chat-panel').boundingBox();
    assert.ok(box.x >= 0 && box.x + box.width <= 390 && box.y >= 0);
    await page.screenshot({ path: path.join(__dirname, '../output/chat-mobile.png') });
    await page.keyboard.press('Escape');
    assert.equal(await page.getByRole('dialog').count(), 0);
    await page.evaluate(() => localStorage.setItem('phishRadarPrivacyMode', '1'));
    await page.reload();
    await page.getByRole('button', { name: 'เปิดแชทผู้ช่วย', exact: true }).click();
    const countBeforePrivacy = chats;
    await page.getByRole('button', { name: 'Phishing คืออะไร', exact: true }).click();
    await page.getByText('คำแนะนำพื้นฐาน · Privacy Mode', { exact: true }).waitFor();
    assert.equal(chats, countBeforePrivacy);
    await input.fill('https://example.com');
    await page.getByRole('button', { name: 'ส่งข้อความ', exact: true }).click();
    await page.locator('.radar-chat-result').waitFor();
    assert.equal(predicts, 1);
    await page.getByRole('button', { name: 'ล้างแชท', exact: true }).click();
    assert.equal(await page.locator('.radar-chat-message').count(), 1);
    assert.deepEqual(errors, []);
    console.log('Chat browser tests passed: fallback, scan, follow-up, mobile, Escape, privacy, clear.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
