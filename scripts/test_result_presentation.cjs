// Render the real result component with a fixed context; no backend or account writes.
const path = require('node:path');
const fs = require('node:fs');
const {build} = require('../web-app/node_modules/esbuild');
const root = path.resolve(__dirname, '..');
const out = path.join(root, 'tmp/result-presentation');
fs.mkdirSync(out, {recursive:true});
// Use a real module alias instead of mocking the UI component under test.
fs.writeFileSync(path.join(out, 'context.js'), 'export function useApp(){return {submitFeedback:async()=>"",health:null,backendStatus:{online:null}}} export function mapServerHistory(item){return item;}');
fs.writeFileSync(path.join(out, 'api.js'), 'export const api = {};');
build({
  stdin:{contents:`
    import React from 'react';
    import {renderToStaticMarkup} from 'react-dom/server';
    import {AnalysisResult,ExplanationReasons} from './src/pages/ScannerPage.jsx';
    import {historyExportItem} from './src/pages/DashboardPage.jsx';
    import {explanationEvidenceReasons,explanationReasonItems} from './src/services/risk.js';
    import assert from 'node:assert/strict';
    import fs from 'node:fs';
    const base={url:'https://www.ku.ac.th/th',finalScore:89,ruleScore:0,randomForestScore:81,
      decision:'allow',modelStatus:'ready',warningThreshold:96,blockingThreshold:100,reasons:[]};
    const render=(result,phase='done')=>renderToStaticMarkup(<AnalysisResult result={result} phase={phase}/>);
    const html=render(base);
    const overview=html.split('class="workspace-tabs"')[0];
    assert(overview.includes('ไม่พบความเสี่ยงชัดเจน'));
    assert(overview.includes('/100') && overview.includes('คะแนนความเสี่ยง') && overview.includes('>89<small>'));
    assert(!overview.includes('RuleScore') && !overview.includes('FuzzyScore'));
    const rfOnly=render({...base,finalScore:81,fusionMethod:'ml_only'}).split('class="workspace-tabs"')[0];
    assert(rfOnly.includes('คะแนนจาก Random Forest หลังปรับเทียบ'));
    assert(rfOnly.includes('<span>Random Forest</span>'));
    assert(!rfOnly.includes('RuleScore') && !rfOnly.includes('FuzzyScore'));
    const legacyFormula=render({...base,fusionMethod:'ml_only',riskFormula:'FinalScore = 100 x LearnedFusion(FuzzyScore, RuleScore)',llm:{}});
    assert(!legacyFormula.includes('LearnedFusion') && !legacyFormula.includes('FuzzyScore') && !legacyFormula.includes('RuleScore'));
    assert(!legacyFormula.includes('Random Forest: 81'));
    const offline=render({...base,modelStatus:'offline'}).split('class="workspace-tabs"')[0];
    assert(offline.includes('ข้อมูลไม่เพียงพอ') && !offline.includes('decision-allow'));
    const failed=render({...base,modelStatus:'offline',predictionError:'HTTP 503'});
    assert(failed.includes('ครั้งนี้ไม่ได้รับผลจากโมเดล') && failed.includes('HTTP 503'));
    assert(!failed.includes('โมเดลยังไม่พร้อม'));
    assert(failed.includes('คะแนนตรวจในเครื่อง'));
    const boundary=render({...base,finalScore:60,decision:undefined,warningThreshold:60});
    assert(boundary.includes('decision-warn'));
    assert(render({...base,finalScore:59,decision:undefined,warningThreshold:60}).includes('decision-allow'));
    assert(render({...base,decision:'warn'}).includes('พบสัญญาณน่าสงสัย'));
    const modelOnlyWarn=render({...base,finalScore:63,decision:'warn',fusionMethod:'ml_only'});
    assert(modelOnlyWarn.includes('โมเดลประเมินว่าควรระวัง'));
    assert(modelOnlyWarn.includes('ยังไม่พบหลักฐานเสี่ยงจากกฎ URL'));
    assert(!modelOnlyWarn.includes('พบสัญญาณน่าสงสัย'));
    assert(render({...base,decision:'warn',fusionMethod:'ml_only',ruleScore:20}).includes('พบสัญญาณน่าสงสัย'));
    assert(render({...base,decision:'warn',fusionMethod:'ml_only',ruleScore:0,reasons:[{label:'ข้อควรตรวจ',points:20}]}).includes('พบสัญญาณน่าสงสัย'));
    assert(render({...base,decision:'block'}).includes('เสี่ยงสูง'));
    const pending=render(base,'analyzing').split('class="workspace-tabs"')[0];
    assert(!pending.includes('decision-allow'));
    assert.deepEqual(explanationEvidenceReasons([
      {label:'หลักฐานเสี่ยง',detail:'ชื่อโฮสต์',points:20},
      {label:'ข้อมูลอ้างอิง',points:-25},
      {label:'ข้อมูลประกอบ',points:0},
      {label:'ไม่มีคะแนน'}, {label:'คะแนนไม่ถูกต้อง',points:NaN}, 'ข้อความเดิม'
    ]),[
      {title:'หลักฐานเสี่ยง',detail:'ชื่อโฮสต์',points:20},
      {title:'ข้อมูลอ้างอิง',detail:'',points:-25},
      {title:'ข้อมูลประกอบ',detail:'',points:0}
    ]);
    assert.equal(explanationEvidenceReasons(Array.from({length:12},(_,i)=>({label:'หลักฐาน',points:i}))).length,8);
    const withLlm=render({...base,llm:{riskType:'ควรระวัง',explanation:'คะแนนจากโมเดล',advice:'ตรวจสอบแหล่งที่มา',confidenceNote:'ยังไม่ได้ตรวจเนื้อหาเว็บไซต์'}});
    assert(withLlm.includes('Risk summary: ควรระวัง'));
    assert(withLlm.includes('Limitations: ยังไม่ได้ตรวจเนื้อหาเว็บไซต์'));
    const riskReasons=[{title:'คะแนนถึงเกณฑ์เตือน',explanation:'ควรตรวจแหล่งที่มาก่อนกรอกข้อมูล'}];
    const reassuringReasons=[{title:'เชื่อมต่อ HTTPS',explanation:'ช่วยเข้ารหัสการเชื่อมต่อ แต่ไม่รับประกันเนื้อหา'}];
    const withGroups=render({...base,fusionMethod:'ml_only',llm:{riskType:'ควรระวัง',explanation:'คะแนนจากโมเดล',riskReasons,reassuringReasons}});
    assert(withGroups.includes('เหตุผลที่ควรระวัง:'));
    assert(withGroups.includes('1. คะแนนถึงเกณฑ์เตือน: ควรตรวจแหล่งที่มา'));
    assert(withGroups.includes('สิ่งที่ช่วยลดความกังวล:'));
    const noRisk=render({...base,fusionMethod:'ml_only',llm:{explanation:'คะแนนต่ำกว่าเกณฑ์เตือน',hasDetailedReasons:true,riskReasons:[],reassuringReasons}});
    assert(noRisk.includes('เหตุผลที่ควรระวัง: ยังไม่พบข้อควรระวังจากข้อมูล URL ที่ตรวจในครั้งนี้'));
    assert(!noRisk.includes('ตรวจ URL ใหม่เพื่อรับรายละเอียดล่าสุด'));
    const noReassuring=render({...base,llm:{explanation:'สรุปผลตรวจ',hasDetailedReasons:true,riskReasons:[],reassuringReasons:[]}});
    assert(noReassuring.includes('สิ่งที่ช่วยลดความกังวล: ยังไม่พบข้อมูลที่ช่วยลดความกังวลจาก URL ที่ตรวจ'));
    assert(noReassuring.includes('ไม่ยืนยันว่าเว็บไซต์ปลอดภัยหรืออันตราย'));
    const mappedLegacy=render({...base,llm:{explanation:'คำอธิบายเดิม',hasDetailedReasons:false,riskReasons:[],reassuringReasons:[]}});
    assert(!mappedLegacy.includes('เหตุผลที่ควรระวัง: ยังไม่พบข้อควรระวัง'));
    const riskGroup=renderToStaticMarkup(<ExplanationReasons title="เหตุผลที่ควรระวัง" items={riskReasons} emptyText="ไม่มีข้อมูล"/>);
    assert(riskGroup.includes('<ol>') && riskGroup.includes('<strong>คะแนนถึงเกณฑ์เตือน</strong>'));
    assert(riskGroup.includes('ควรตรวจแหล่งที่มาก่อนกรอกข้อมูล'));
    const legacyGroup=renderToStaticMarkup(<ExplanationReasons title="เหตุผลที่ควรระวัง" items={undefined} emptyText="อ่านคำอธิบายเดิม"/>);
    assert(legacyGroup.includes('อ่านคำอธิบายเดิม') && !legacyGroup.includes('<ol>'));
    assert.equal(explanationReasonItems(Array.from({length:7},(_,i)=>({title:'ข้อ '+i,explanation:'ข้อมูลประกอบ'}))).length,4);
    assert.deepEqual(explanationReasonItems([{title:'ไม่มีรายละเอียด'},null,'invalid',{title:'',explanation:'เหตุผล'}]),[]);
    const exported=historyExportItem({...base,fusionMethod:'ml_only',riskFormula:'RuleScore + FuzzyScore',layerResults:{rule_score:20}});
    assert.equal(exported.risk_score,89);
    assert.equal(exported.score_source,'random_forest_calibrated');
    assert(!JSON.stringify(exported).includes('rule_score') && !JSON.stringify(exported).includes('fuzzy_score') && !JSON.stringify(exported).includes('ml_score'));
    assert.equal(historyExportItem({...base,privacy:true}).score_source,'local_url_rules');
    fs.writeFileSync(${JSON.stringify(path.join(root,'output/risk-fix/result-preview.html'))},
      '<!doctype html><html lang="th"><meta charset="utf-8"><title>ตัวอย่างผลตรวจหลังแก้ไข</title><body>'+html+'</body></html>');
    console.log('Result presentation passed: single-score reports, textual observations, numbered explanation groups, legacy compatibility, honest local source.');
  `, resolveDir:path.join(root,'web-app'), loader:'jsx'},
  plugins:[{name:'fixed-app-context',setup(builder){
    builder.onResolve({filter:/contexts\/AppContext$/},()=>({path:path.join(out,'context.js')}));
    builder.onResolve({filter:/services\/api$/},()=>({path:path.join(out,'api.js')}));
  }}],
  bundle:true,platform:'node',jsx:'automatic',outfile:path.join(out,'test.cjs'),logLevel:'warning'
}).then(()=>require(path.join(out,'test.cjs'))).catch(error=>{console.error(error);process.exitCode=1;});
