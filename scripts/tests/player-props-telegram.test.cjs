const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const root = path.resolve(__dirname, '../..');
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file).exports;
  const m = {exports:{}}; cache.set(file,m);
  const code = ts.transpileModule(fs.readFileSync(file,'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const localRequire = id => id==='server-only' ? {} : id.startsWith('@/') ? load(path.join(root,'src',id.slice(2)+'.ts')) : require(id);
  new Function('require','module','exports',code)(localRequire,m,m.exports);
  return m.exports;
}
const api = load(path.join(root,'src/lib/player-props-telegram.ts'));
const tip = {id:90001,market:'props',category:'ucl',event:'Sporting vs Galatasaray',player:'Goncalves F.',selection:'Over 1.5 Tackles',odds:2.7,stake:.75,match_date:'2026-09-09',bookmaker:{name:'Betway'}};

test('only the selected affiliate is promoted; both approved names resolve',()=>{
  for (const [name,end] of [['Betway','betway'],['William Hill','william-hill'],['WH','william-hill']]) {
    const p=api.renderPlayerPropsTipPayload({...tip,bookmaker:{name}});
    assert.equal(p.reply_markup.inline_keyboard.length,2);
    assert.ok(p.reply_markup.inline_keyboard[0][0].url.endsWith('/api/go/'+end));
    assert.equal(p.entities.filter(e=>e.type==='text_link').length,2);
  }
  const p=api.renderPlayerPropsTipPayload({...tip,bookmaker:{name:'Pinnacle'}});
  assert.equal(p.reply_markup.inline_keyboard.length,1);
  assert.ok(!JSON.stringify(p).includes('/api/go/'));
});

test('caption stays within Telegram limit and entity offsets handle emoji',()=>{
  const p=api.renderPlayerPropsTipPayload({...tip,event:'🎾 '.repeat(100),player:'👤 '.repeat(100),selection:'Over '.repeat(100),notes:'Reason '.repeat(200)});
  assert.ok(p.text.length<=1024);
  for (const e of p.entities) assert.ok(e.offset>=0 && e.length>0 && e.offset+e.length<=p.text.length);
  const link=p.entities.find(e=>e.url?.includes('/api/go/'));
  assert.equal(p.text.slice(link.offset,link.offset+link.length),'Betway');
});

test('HTML links cover complete labels and escape user-supplied markup',()=>{
  const p=api.renderPlayerPropsTipPayload({...tip,event:'A & B <Cup> 🎾',notes:'<a href="https://invalid.test">bad</a>',bookmaker:{short_name:'Paddy',name:'Paddy Power'}});
  assert.ok(p.html.includes('A &amp; B &lt;Cup&gt; 🎾'));
  assert.ok(p.html.includes('&lt;a href=&quot;https://invalid.test&quot;&gt;bad&lt;/a&gt;'));
  assert.ok(p.html.includes('Bookmaker: Paddy Power'));
  assert.match(p.html,/Match: <b>9 Sept<\/b>/);
  const anchors=[...p.html.matchAll(/<a href="([^"]+)">([^<]+)<\/a>/g)];
  assert.equal(anchors.length,1);
  assert.equal(anchors[0][2],'Full pick &amp; tracked results');
});

test('all 22 known bookmakers have decodable embedded artwork',async()=>{
  const sharp=require('sharp');
  assert.ok(fs.statSync(path.join(root,'src/lib/telegram-brand-assets.ts')).size<=150_000,'embedded artwork must stay within the edge bundle budget');
  const {BOOKMAKER_LOGO_KEYS}=load(path.join(root,'src/lib/bookmaker-logos.ts'));
  const {TELEGRAM_BRAND_ASSETS,TELEGRAM_BRAND_ASPECTS}=load(path.join(root,'src/lib/telegram-brand-assets.ts'));
  assert.equal(BOOKMAKER_LOGO_KEYS.length,22);
  for(const key of BOOKMAKER_LOGO_KEYS){
    assert.ok(TELEGRAM_BRAND_ASSETS[key]?.startsWith('data:image/png;base64,'),key);
    const m=await sharp(Buffer.from(TELEGRAM_BRAND_ASSETS[key].split(',')[1],'base64')).metadata();
    assert.ok(m.width>0&&m.height>0,key);
    assert.equal(TELEGRAM_BRAND_ASPECTS[key],m.width/m.height);
  }
});

test('photo upload and text fallback both retain clickable buttons; no real sends',async()=>{
  const originalFetch=global.fetch;
  const keys=['PLAYER_PROPS_TELEGRAM_POSTING_ENABLED','PLAYER_PROPS_TELEGRAM_BOT_TOKEN','PLAYER_PROPS_TELEGRAM_CHAT_ID'];
  const old=Object.fromEntries(keys.map(k=>[k,process.env[k]]));
  Object.assign(process.env,{PLAYER_PROPS_TELEGRAM_POSTING_ENABLED:'true',PLAYER_PROPS_TELEGRAM_BOT_TOKEN:'test-token',PLAYER_PROPS_TELEGRAM_CHAT_ID:'test-chat'});
  try {
    for(const failPhoto of [false,true]) {
      const calls=[];
      global.fetch=async(url,init)=>{
        if(String(url).includes('/wc-tip-card?')) return new Response(new Uint8Array([1,2,3]),{headers:{'Content-Type':'image/png'}});
        // Serialize real multipart bytes: FormData changes LF into CRLF.
        const wire=String(url).endsWith('/sendPhoto')
          ? await new Request('https://telegram-test.invalid',{method:'POST',body:init.body}).formData() : null;
        calls.push({url,init,wire});
        return new Response('{}',{status:failPhoto&&String(url).endsWith('/sendPhoto')?400:200});
      };
      const result=await api.postPlayerPropTipToTelegram(tip);
      assert.equal(result.status,'posted');
      assert.equal(result.mode,failPhoto?'text_fallback':'photo');
      const photo=JSON.parse(calls[0].init.body.get('reply_markup'));
      assert.equal(calls[0].wire.get('parse_mode'),'HTML');
      assert.equal(calls[0].wire.get('caption_entities'),null);
      const caption=calls[0].wire.get('caption');
      assert.ok(caption.includes('\r\n'));
      assert.match(caption,/<a href="[^"]+\/api\/go\/betway">Betway<\/a>/);
      assert.match(caption,/Match: <b>9 Sept<\/b>\r\n\r\n<a href="[^"]+">Full pick &amp; tracked results<\/a>/);
      assert.ok(photo.inline_keyboard[0][0].url.endsWith('/api/go/betway'));
      if(failPhoto) {
        const fallback=JSON.parse(calls[1].init.body);
        assert.deepEqual(fallback.reply_markup,photo);
        assert.equal(fallback.parse_mode,'HTML');
        assert.equal(fallback.entities,undefined);
        assert.equal(fallback.text,caption.replace(/\r\n/g,'\n'));
      }
    }
  } finally {global.fetch=originalFetch;for(const k of keys) old[k]===undefined?delete process.env[k]:process.env[k]=old[k];}
});
