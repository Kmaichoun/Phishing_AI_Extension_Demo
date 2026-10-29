// Exercise the real API adapter with malformed and valid server responses.
const path = require('node:path');
const fs = require('node:fs');
const {build} = require('../web-app/node_modules/esbuild');
const root = path.resolve(__dirname, '..');
const output = path.join(root, 'tmp/result-presentation/prediction.cjs');
fs.mkdirSync(path.dirname(output), {recursive:true});
build({
  stdin: {contents:`
    import assert from 'node:assert/strict';
    import {api} from './src/services/api';
    async function main() {
      for (const payload of [null, {}, {ok:true}, {ok:true,risk_score:'60',model_status:'ready'}]) {
        globalThis.fetch=async()=>({ok:true,status:200,json:async()=>payload});
        await assert.rejects(()=>api.predict({url:'https://example.com/'}), /ผลตรวจไม่ครบ/);
      }
      const valid={ok:true,risk_score:60,model_status:'ready',decision:'warn'};
      globalThis.fetch=async()=>({ok:true,status:200,json:async()=>valid});
      assert.deepEqual(await api.predict({url:'https://example.com/'}),valid);
      globalThis.fetch=async()=>({ok:false,status:503,json:async()=>({detail:'model temporarily unavailable'})});
      await assert.rejects(()=>api.predict({url:'https://example.com/'}),/model temporarily unavailable/);
      console.log('Prediction response tests passed: malformed response, HTTP failure, and valid RF result.');
    }
    main().catch(error=>{console.error(error);process.exitCode=1;});
  `,resolveDir:path.join(root,'web-app')},
  plugins:[{name:'runtime',setup(builder){
    builder.onResolve({filter:/^\.\/runtime$/},()=>({path:'runtime',namespace:'test'}));
    builder.onLoad({filter:/.*/,namespace:'test'},()=>({contents:'export const runtime={apiBase:"http://test.local"};'}));
  }}],
  bundle:true,platform:'node',outfile:output,logLevel:'warning'
}).then(()=>require(output)).catch(error=>{console.error(error);process.exitCode=1;});
