// Render the warning page with actual analyzer code and controlled backend states.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../extension');
async function render(extra = {}, settings = {}, llm = null, controls = {}) {
  const elements = new Map();
  const explanationRequests = [];
  const explanationCallbacks = [];
  const settingCallbacks = [];
  const messages = [];
  const runtime = { lastError: null };
  const element = id => {
    if (!elements.has(id)) {
      const handlers = new Map();
      const node = { textContent: '', style: {}, dataset: {}, children: [], hidden: false, disabled: false,
        classList: { toggle() {} },
        addEventListener(type, handler) {
          if (!handlers.has(type)) handlers.set(type, []);
          handlers.get(type).push(handler);
        },
        dispatch(type) { for (const handler of handlers.get(type) || []) handler({ target: this, preventDefault() {} }); },
        click() { if (!this.disabled) this.dispatch('click'); },
        appendChild(child) { this.children.push(child); }
      };
      let html = '';
      Object.defineProperty(node, 'innerHTML', { get: () => html, set(value) { html = value; this.children = []; } });
      elements.set(id, node);
    }
    return elements.get(id);
  };
  const defaultResponse = () => ({ ok: true, provider: 'ollama', model: 'configured-model', llm: llm || {
    risk_type: 'ควรระวัง', simple_explanation: 'คะแนน 66 สูงกว่าเกณฑ์เตือน 60',
    user_advice: 'ตรวจสอบโดเมนก่อนกรอกข้อมูล', confidence_note: 'ยังไม่ได้ตรวจเนื้อหาเว็บไซต์'
  } });
  const respond = (callback, response) => {
    runtime.lastError = controls.runtimeError ? { message: controls.runtimeError } : null;
    try { callback(response); } finally { runtime.lastError = null; }
  };
  const query = new URLSearchParams({ target: 'https://gemini.google.com/?hl=th', score: '66',
    rule_score: '0', fuzzy_score: '0', random_forest_score: '66', risk_score: '66',
    risk_probability: '.66', fusion_method: 'ml_only', fusion_applied: '', decision: 'warn',
    model_status: 'ready', model_version: 'test-random-forest', warning_threshold: '60', blocking_threshold: '80',
    ...extra });
  const context = vm.createContext({ console, URL, URLSearchParams, setTimeout, clearTimeout,
    location: { search: '?' + query, href: 'chrome-extension://test/warning.html', replace() {} },
    history: { length: 1, back() {} },
    document: { getElementById: element, createElement: () => element('created-' + Math.random()), body: element('body') },
    chrome: { runtime: Object.assign(runtime, { sendMessage(message, callback) {
      messages.push(message);
      if (message.type === 'GET_SETTINGS') {
        if (controls.deferSettings) settingCallbacks.push(callback);
        else callback({ settings: { privacyMode: false, llmEnabled: false, ...settings } });
      }
      if (message.type === 'EXPLAIN_WITH_LLM') {
        explanationRequests.push(message.payload);
        if (controls.throwExplanation) throw new Error(controls.throwExplanation);
        if (controls.deferExplanation) explanationCallbacks.push(callback);
        else respond(callback, Object.hasOwn(controls, 'response') ? controls.response : defaultResponse());
      }
    } }) }
  });
  for (const file of ['analyzer.js', 'app-trust.js', 'ml-feedback-client.js', 'warning.js']) {
    vm.runInContext(fs.readFileSync(path.join(root, file), 'utf8'), context, { filename: file });
  }
  await new Promise(resolve => setImmediate(resolve));
  return { elements, context, explanationRequests, messages,
    flushSettings() {
      const callback = settingCallbacks.shift();
      assert.ok(callback, 'a settings callback must be pending');
      callback({ settings: { privacyMode: false, llmEnabled: false, ...settings } });
    },
    flushExplanation(response = defaultResponse()) {
      const callback = explanationCallbacks.shift();
      assert.ok(callback, 'an explanation callback must be pending');
      respond(callback, response);
    }
  };
}
function itemText(element) {
  return element.children.map(item => item.children.map(child => child.textContent).join(' ')).join('\n');
}
(async () => {
  for (const model_status of ['ready', '']) {
    const { elements } = await render({ model_status });
    assert.match(elements.get('scoreFormulaBadge').textContent, /Random Forest.*Calibrated/);
    assert.doesNotMatch(elements.get('scoreBlendText').textContent, /ไม่พร้อม/);
    assert.match(elements.get('headline').textContent, /โมเดลประเมิน/);
    assert.match(elements.get('lead').textContent, /ยังไม่ยืนยัน/);
    assert.equal(elements.get('sourceLlmValue').textContent, 'ปิด');
    assert.doesNotMatch(elements.get('sourceLlmMeta').textContent, /Privacy Mode/);
    assert.equal(elements.get('scoreLabel').textContent, 'Random Forest หลังปรับเทียบ');
    assert.equal(elements.get('sourceMlValue').textContent, 'พร้อม');
    assert.equal(elements.has('sourceRuleValue'), false);
    assert.doesNotMatch(elements.get('scoreBlendText').textContent, /RuleScore|FuzzyScore|\d+\/100/);
  }
  assert.doesNotMatch(fs.readFileSync(path.join(root, 'warning.html'), 'utf8'), /sourceRuleRow|sourceRuleValue|sourceRuleFill/);
  const offline = await render({ model_status: 'offline', random_forest_score: '', risk_probability: '' });
  assert.match(offline.elements.get('scoreFormulaBadge').textContent, /offline/);
  assert.equal(offline.elements.get('sourceMlValue').textContent, 'ไม่พร้อม');
  assert.equal(offline.elements.get('scoreLabel').textContent, 'คะแนนตรวจ URL ในเครื่อง');
  const privacy = await render({ privacy_mode: '1' });
  assert.equal(privacy.elements.get('sourceMlValue').textContent, 'ปิด');
  assert.match(privacy.elements.get('sourceLlmMeta').textContent, /Privacy Mode/);
  assert.equal(privacy.explanationRequests.length, 0);
  assert.equal(privacy.elements.get('scoreLabel').textContent, 'คะแนนตรวจ URL ในเครื่อง');
  const online = await render({ feature_schema_version: 'url-v10-reference-root-context',
    reasons: JSON.stringify([
      { label: 'ชื่อเลียนแบบแบรนด์', detail: 'ตรวจชื่อโฮสต์', points: 20 },
      { label: 'โดเมนอ้างอิง', detail: 'ตรวจ origin', points: -25 },
      { label: 'ข้อมูลประกอบ', detail: 'HTTPS', points: 0 },
      { label: 'ไม่มีคะแนน', detail: 'ข้อความ' }
    ]) }, { llmEnabled: true });
  assert.equal(online.explanationRequests.length, 1);
  assert.equal(online.explanationRequests[0].feature_schema_version, 'url-v10-reference-root-context');
  assert.deepEqual(JSON.parse(JSON.stringify(online.explanationRequests[0].evidence_reasons)), [
    { title: 'ชื่อเลียนแบบแบรนด์', detail: 'ตรวจชื่อโฮสต์', points: 20 },
    { title: 'โดเมนอ้างอิง', detail: 'ตรวจ origin', points: -25 },
    { title: 'ข้อมูลประกอบ', detail: 'HTTPS', points: 0 }
  ]);
  assert.equal(online.elements.get('llmRiskType').textContent, 'ควรระวัง');
  assert.equal(online.elements.get('llmExplanation').textContent, 'คะแนน 66 สูงกว่าเกณฑ์เตือน 60');
  assert.equal(online.elements.get('llmConfidence').textContent, 'ยังไม่ได้ตรวจเนื้อหาเว็บไซต์');
  assert.equal(online.elements.get('llmRiskReasons').hidden, true);
  assert.match(online.elements.get('llmRiskReasonsEmpty').textContent, /ไม่มีเหตุผลแยกรายข้อ/);
  const grouped = await render({}, { llmEnabled: true }, {
    risk_type: 'ควรระวัง', simple_explanation: 'คะแนนมาจาก Random Forest',
    user_advice: 'ตรวจแหล่งที่มา', confidence_note: 'ไม่รับประกันเนื้อหา',
    risk_reasons: [{ title: 'คะแนนถึงเกณฑ์เตือน', explanation: 'โมเดลให้คะแนนสูง แต่ยังไม่มีหลักฐานยืนยัน phishing' }],
    reassuring_reasons: [{ title: '<img src=x onerror=alert(1)>', explanation: 'ใช้ HTTPS จึงเข้ารหัสการเชื่อมต่อ ไม่ได้รับประกันเนื้อหา' }]
  });
  assert.equal(grouped.elements.get('llmRiskReasons').hidden, false);
  assert.equal(grouped.elements.get('llmRiskReasonsEmpty').hidden, true);
  assert.equal(grouped.elements.get('llmRiskReasons').children[0].children[0].textContent, 'คะแนนถึงเกณฑ์เตือน');
  assert.equal(grouped.elements.get('llmReassuringReasons').children[0].children[0].textContent, '<img src=x onerror=alert(1)>');
  assert.equal(grouped.elements.get('llmReassuringReasons').children[0].children[0].innerHTML, '');
  const noRisk = await render({}, { llmEnabled: true }, {
    risk_type: 'ยังไม่พบความเสี่ยงชัดเจนจาก URL', simple_explanation: 'คะแนนต่ำกว่าเกณฑ์เตือน',
    risk_reasons: [], reassuring_reasons: [{ title: 'โดเมนอ้างอิง', explanation: 'ตรงกับข้อมูลอ้างอิงที่ตรวจ ไม่รับประกันเนื้อหา' }]
  });
  assert.equal(noRisk.elements.get('llmRiskReasons').hidden, true);
  assert.equal(noRisk.elements.get('llmRiskReasonsEmpty').textContent, 'ยังไม่พบข้อควรระวังจากข้อมูล URL ที่ตรวจในครั้งนี้');
  assert.doesNotMatch(noRisk.elements.get('llmRiskReasonsEmpty').textContent, /ตรวจ URL ใหม่|ไม่มีเหตุผลแยกรายข้อ/);
  assert.equal(noRisk.elements.get('llmReassuringReasons').hidden, false);
  const noReassuring = await render({}, { llmEnabled: true }, { risk_reasons: [], reassuring_reasons: [] });
  assert.match(noReassuring.elements.get('llmReassuringReasonsEmpty').textContent, /ยังไม่พบข้อมูลที่ช่วยลดความกังวลจาก URL ที่ตรวจ/);
  assert.match(noReassuring.elements.get('llmReassuringReasonsEmpty').textContent, /ไม่ยืนยันว่าเว็บไซต์ปลอดภัยหรืออันตราย/);
  const bounded = await render({}, { llmEnabled: true }, {
    risk_reasons: [{ title: 'ไม่มีรายละเอียด' }, ...Array.from({ length: 7 }, (_, i) => ({ title: 'ข้อ ' + i, explanation: 'เหตุผลประกอบ' }))],
    reassuring_reasons: 'invalid'
  });
  assert.equal(bounded.elements.get('llmRiskReasons').children.length, 4);
  assert.equal(bounded.elements.get('llmReassuringReasons').hidden, true);
  const manyReasons = await render({ reasons: JSON.stringify(Array.from({ length: 12 }, (_, i) => ({ label: 'หลักฐาน ' + i, points: i }))) }, { llmEnabled: true });
  assert.equal(manyReasons.explanationRequests[0].evidence_reasons.length, 8);
  const rounded = await render({ score: '80', risk_score: '80', random_forest_score: '80', decision: 'warn' });
  assert.equal(rounded.context.document.body.dataset.level, 'high');
  const allowed = await render({ score: '60', risk_score: '60', random_forest_score: '60', decision: 'allow' });
  assert.equal(allowed.context.document.body.dataset.level, 'medium');
  assert.equal(vm.runInContext("phishRadarClassifyPolicy(80, 60, 80, 'warn').decision", rounded.context), 'warn');

  // A blocked link must have useful facts before the asynchronous AI answer arrives.
  const blockParams = { target: 'https://bit.ly/demo', score: '90', risk_score: '90',
    random_forest_score: '90', risk_probability: '.9', decision: 'block', rule_score: '15' };
  const settingsPending = await render(blockParams, { llmEnabled: true }, null,
    { deferSettings: true, deferExplanation: true });
  assert.match(itemText(settingsPending.elements.get('llmRiskReasons')), /ลิงก์ย่อ/);
  assert.match(settingsPending.elements.get('llmExplanation').textContent, /90\/100/);
  assert.equal(settingsPending.explanationRequests.length, 0,
    'local facts must show before settings resolve, without prematurely contacting AI');
  settingsPending.flushSettings();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(settingsPending.explanationRequests.length, 1);
  settingsPending.flushExplanation();
  const pending = await render(blockParams, { llmEnabled: true }, null, { deferExplanation: true });
  assert.equal(pending.explanationRequests.length, 1);
  assert.equal(pending.elements.get('score').textContent, 90);
  assert.equal(pending.context.document.body.dataset.level, 'critical');
  assert.match(pending.elements.get('llmExplanation').textContent, /90\/100/);
  assert.match(pending.elements.get('llmExplanation').textContent, /Random Forest/);
  assert.match(itemText(pending.elements.get('llmRiskReasons')), /ลิงก์ย่อ/);
  assert.match(itemText(pending.elements.get('llmReassuringReasons')), /HTTPS/);
  assert.match(pending.elements.get('llmConfidence').textContent, /URL/);
  assert.equal(pending.elements.get('retryExplanation').disabled, true);
  pending.elements.get('retryExplanation').dispatch('click');
  assert.equal(pending.explanationRequests.length, 1, 'another click must not duplicate an in-flight request');

  const screenshot = await render({ ...blockParams, target: 'https://ibit.ly/sexy365bet', rule_score: '0' });
  assert.match(itemText(screenshot.elements.get('llmRiskReasons')), /sexy|Adult|Spam|เนื้อหาอ่อนไหว/);
  assert.doesNotMatch(itemText(screenshot.elements.get('llmRiskReasons')), /เป็นลิงก์ย่อ/,
    'ibit.ly is not a shortener recognized by the local analyzer');
  const modelOnly = await render({ ...blockParams, target: 'https://ibit.ly/demo', rule_score: '0' });
  assert.match(modelOnly.elements.get('llmExplanation').textContent, /โมเดล/);
  assert.match(modelOnly.elements.get('llmExplanation').textContent, /ยังไม่มี|ยังไม่พบ|ไม่พบ/);
  assert.doesNotMatch(itemText(modelOnly.elements.get('llmRiskReasons')), /ลิงก์ย่อ|การพนัน|Adult|Spam|เลียนแบบ|ขโมย/,
    'a high model score without URL evidence must not invent a malicious cause');

  for (const restricted of [
    await render(blockParams, { llmEnabled: false }),
    await render({ ...blockParams, privacy_mode: '1' }, { llmEnabled: true }),
    await render(blockParams, { privacyMode: true, llmEnabled: true })
  ]) {
    assert.equal(restricted.explanationRequests.length, 0);
    assert.match(itemText(restricted.elements.get('llmRiskReasons')), /ลิงก์ย่อ/);
    assert.equal(restricted.elements.get('retryExplanation').hidden, true);
    assert.equal(restricted.elements.get('retryExplanation').disabled, true);
    restricted.elements.get('retryExplanation').dispatch('click');
    assert.equal(restricted.explanationRequests.length, 0, 'privacy or disabled AI must remain local after a synthetic click');
    assert.doesNotMatch(restricted.elements.get('llmStatus').textContent, /วิเคราะห์ด้วย LLM สำเร็จ/);
  }

  for (const failure of [
    { response: undefined },
    { response: { ok: false, status: 'backend_unavailable', provider: 'fallback' } },
    { runtimeError: 'The message port closed before a response was received.', response: undefined },
    { throwExplanation: 'Extension context invalidated' }
  ]) {
    const failed = await render(blockParams, { llmEnabled: true }, null, failure);
    assert.equal(failed.explanationRequests.length, 1);
    assert.match(itemText(failed.elements.get('llmRiskReasons')), /ลิงก์ย่อ/);
    assert.match(failed.elements.get('llmExplanation').textContent, /90\/100/);
    assert.match(failed.elements.get('llmStatus').textContent, /สำรอง|เชื่อมต่อ|ไม่พร้อม|ไม่สำเร็จ/);
    assert.notEqual(failed.elements.get('sourceLlmValue').textContent, 'พร้อม');
    assert.equal(failed.elements.get('retryExplanation').disabled, false);
    assert.equal(failed.elements.get('retryExplanation').hidden, false);
    assert.equal(failed.elements.get('score').textContent, 90);
  }

  const originalPayload = JSON.parse(JSON.stringify(pending.explanationRequests[0]));
  pending.flushExplanation({ ok: false, status: 'backend_unavailable' });
  assert.match(itemText(pending.elements.get('llmRiskReasons')), /ลิงก์ย่อ/);
  assert.equal(pending.elements.get('retryExplanation').disabled, false);
  pending.elements.get('retryExplanation').click();
  assert.equal(pending.explanationRequests.length, 2);
  assert.deepEqual(JSON.parse(JSON.stringify(pending.explanationRequests[1])), originalPayload,
    'retrying an explanation must not change model scores, policy, decision, or URL evidence');
  pending.elements.get('retryExplanation').dispatch('click');
  assert.equal(pending.explanationRequests.length, 2);
  pending.flushExplanation({ ok: true, provider: 'ollama', model: 'local-test-model', llm: {
    risk_type: 'ควรหยุดตรวจสอบก่อน', simple_explanation: 'คำอธิบายล่าสุดจาก AI: คะแนน 90/100',
    user_advice: 'เปิดช่องทางทางการแทน', confidence_note: 'ยังไม่ได้ตรวจเนื้อหาเว็บไซต์',
    risk_reasons: [{ title: 'AI อธิบายปลายทาง', explanation: 'ลิงก์ย่อซ่อนปลายทางจริง ควรตรวจให้ชัดเจน' }],
    reassuring_reasons: [{ title: 'AI อธิบายการเข้ารหัส', explanation: 'HTTPS ช่วยเข้ารหัส แต่ไม่ยืนยันความปลอดภัย' }]
  } });
  assert.equal(pending.elements.get('llmExplanation').textContent, 'คำอธิบายล่าสุดจาก AI: คะแนน 90/100');
  assert.equal(pending.elements.get('llmRiskReasons').children.length, 1);
  assert.equal(pending.elements.get('llmRiskReasons').children[0].children[0].textContent, 'AI อธิบายปลายทาง');
  assert.match(pending.elements.get('llmStatus').textContent, /สำเร็จ.*local-test-model/);
  assert.equal(pending.elements.get('sourceLlmValue').textContent, 'พร้อม');
  assert.equal(pending.elements.get('retryExplanation').disabled, false);
  assert.equal(pending.elements.get('score').textContent, 90);
  assert.equal(pending.context.document.body.dataset.level, 'critical');
  pending.elements.get('retryExplanation').click();
  assert.equal(pending.explanationRequests.length, 3, 'a completed answer may be requested again without changing persistent settings');
  pending.flushExplanation();

  const html = fs.readFileSync(path.join(root, 'warning.html'), 'utf8');
  const scorePosition = html.indexOf('id="scoreCard"');
  const detailPosition = html.indexOf('id="llmPanel"');
  assert.ok(scorePosition >= 0 && detailPosition > scorePosition);
  assert.ok(detailPosition < html.indexOf('class="score-breakdown-card"'), 'the explanation must precede technical metadata');
  assert.ok(detailPosition < html.indexOf('id="reasons"'), 'the explanation must precede raw analyzer reasons');
  assert.match(html, /href="#llmPanel"/);
  assert.match(html, /id="retryExplanation"/);
  console.log('Warning state passed: immediate grouped URL facts, AI replacement and safe retry, local/privacy/network fallbacks, one model score, honest model-only warnings, layout prominence, and unchanged policy.');
})().catch(error => { console.error(error); process.exitCode = 1; });
