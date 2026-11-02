const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

const compile = file => ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
}).outputText;

function harness(stored = null, blocked = false) {
  const listeners = new Map(), attrs = new Map();
  const store = { value: stored };
  const localStorage = {
    getItem() { if (blocked) throw new Error('blocked'); return store.value; },
    setItem(key, value) { if (blocked) throw new Error('blocked'); store.value = value; },
  };
  const win = {
    localStorage,
    addEventListener: (name, cb) => listeners.set(name, cb),
    removeEventListener: name => listeners.delete(name),
    dispatchEvent: event => listeners.get(event.type)?.(event),
  };
  const doc = { documentElement: { setAttribute: (k,v) => attrs.set(k,v), removeAttribute: k => attrs.delete(k) } };
  const scope = { exports: {}, window: win, document: doc, Event, localStorage };
  vm.runInNewContext(compile('src/lib/cookie-consent.ts'), scope);
  const consent = scope.exports;
  return { consent, store, attrs, win, listeners, prepaint: () => vm.runInNewContext(consent.CONSENT_PREPAINT_SCRIPT, scope),
    render({ server = false, pathname = '/player-props', measurementId = 'G-TEST' } = {}) {
      const c = { exports: {}, require: id => {
        if (id === '@/lib/cookie-consent') return consent;
        if (id === 'react') return { ...React, useSyncExternalStore: (subscribe, client, ssr) => server ? ssr() : client() };
        if (id === 'next/navigation') return { usePathname: () => pathname };
        if (id === 'next/script') return { default: props => React.createElement('script', { ...props, strategy: undefined }) };
        if (id.startsWith('./')) return { default: () => null };
        return require(id);
      }};
      vm.runInNewContext(compile('src/components/CookieBanner.tsx'), c);
      return renderToStaticMarkup(React.createElement(c.exports.default, {measurementId}));
    },
  };
}

test('server output contains the banner without enabling Google Analytics, regardless of saved choice', () => {
  for (const value of [null, '0', '1', 'invalid']) {
    const h = harness(value); const html = h.render({ server: true });
    assert.match(html, /data-consent-banner/);
    assert.doesNotMatch(html, /googletagmanager|ga-config/);
    assert.equal(h.consent.readServerConsentSnapshot(), 'pending');
  }
});
test('only an explicit accepted choice renders Google Analytics', () => {
  for (const value of [null, '0', 'invalid']) assert.doesNotMatch(harness(value).render(), /googletagmanager|ga-config/);
  assert.match(harness('1').render(), /googletagmanager/);
  assert.doesNotMatch(harness('1').render(), /data-consent-banner/);
});
test('existing choices are hidden by prepaint, fresh and malformed choices stay undecided', () => {
  for (const [value, expected] of [['0','rejected'], ['1','accepted'], [null,undefined], ['yes',undefined]]) {
    const h=harness(value); h.prepaint(); assert.equal(h.attrs.get('data-cookie-consent'), expected);
  }
});
test('Allow and Decline persist the existing key values, notify subscribers and survive a new instance', () => {
  for (const [choice, value] of [['accepted','1'], ['rejected','0']]) {
    const h=harness(); let updates=0; const unsub=h.consent.subscribeToConsent(()=>updates++);
    h.consent.saveConsent(choice);
    assert.equal(h.store.value,value); assert.equal(h.consent.readConsentSnapshot(),choice);
    assert.equal(h.attrs.get('data-cookie-consent'),choice); assert.equal(updates,1);
    assert.equal(harness(h.store.value).consent.readConsentSnapshot(),choice);
    unsub(); assert.equal(h.listeners.size,0);
  }
});
test('storage exceptions retain an explicit choice for the session without crashing or auto-consenting', () => {
  for (const choice of ['accepted','rejected']) {
    const h=harness(null,true); h.prepaint(); assert.equal(h.consent.readConsentSnapshot(),'pending');
    h.consent.saveConsent(choice); assert.equal(h.consent.readConsentSnapshot(),choice);
    assert.equal(h.attrs.get('data-cookie-consent'),choice);
    assert.equal(h.render().includes('googletagmanager'),choice==='accepted');
    assert.equal(harness(null,true).consent.readConsentSnapshot(),'pending');
  }
});
test('storage events update other tabs, ignore unrelated keys and clear stale prepaint state', () => {
  const h=harness('1'); let updates=0; h.consent.subscribeToConsent(()=>updates++);
  h.store.value='0'; h.win.dispatchEvent({type:'storage',key:'unrelated'}); assert.equal(updates,0);
  h.win.dispatchEvent({type:'storage',key:h.consent.CONSENT_KEY});
  assert.equal(h.consent.readConsentSnapshot(),'rejected'); assert.equal(h.attrs.get('data-cookie-consent'),'rejected');
  h.store.value=null; h.win.dispatchEvent({type:'storage',key:null});
  assert.equal(h.consent.readConsentSnapshot(),'pending'); assert.equal(h.attrs.has('data-cookie-consent'),false);
});
test('policy routes and missing measurement IDs keep their exemption', () => {
  for (const pathname of ['/cookies-policy','/privacy-policy']) {
    assert.equal(harness().render({pathname}), ''); assert.equal(harness().render({pathname,server:true}),'');
  }
  assert.equal(harness().render({measurementId:''}), '');
});
test('JS-disabled output hides nonfunctional controls and no request-time API is introduced', () => {
  const layout=fs.readFileSync('src/app/layout.tsx','utf8');
  assert.match(layout, /<noscript><style>.*data-consent-banner.*display:none/);
  assert.doesNotMatch(layout, /cookies\(|headers\(/);
});

test('accepted AI referral visits tolerate blocked storage and do not repeat the event on rerender', () => {
  let sent=0;
  const blocked={getItem(){throw new Error('blocked');},setItem(){throw new Error('blocked');}};
  const scope={exports:{},URL,URLSearchParams,localStorage:blocked,sessionStorage:blocked,
    document:{referrer:''},window:{gtag:()=>sent++},require:id=>{
      if(id==='react')return {useEffect:fn=>fn()};
      if(id==='next/navigation')return {usePathname:()=>'/player-props',useSearchParams:()=>new URLSearchParams('utm_source=chatgpt')};
      return require(id);
    }};
  vm.runInNewContext(compile('src/components/AiReferralTracker.tsx'),scope);
  scope.exports.default(); scope.exports.default(); assert.equal(sent,1);
});

test('policy controls can withdraw session-only consent even when every browser storage API is blocked', () => {
  const h=harness(null,true); h.consent.saveConsent('accepted');
  let reloads=0; const messages=[];
  const blocked={removeItem(){throw new Error('blocked');}};
  const doc={get cookie(){throw new Error('blocked');}};
  const win={location:{reload:()=>reloads++},gtag:(...args)=>messages.push(args)};
  const scope={exports:{},window:win,document:doc,location:{hostname:'ilmargine.bet'},localStorage:blocked,sessionStorage:blocked,
    require:id=>{
      if(id==='react')return {useSyncExternalStore:(_s,read)=>read(),useState:()=>['',()=>{}]};
      if(id==='@/lib/cookie-consent')return h.consent;
      if(id==='@/lib/config')return {GA_MEASUREMENT_ID:'G-TEST'};
      return require(id);
    }};
  vm.runInNewContext(compile('src/components/CookieSettings.tsx'),scope);
  const tree=scope.exports.default(); const buttons=tree.props.children[2].props.children;
  buttons[1].props.onClick();
  assert.equal(h.consent.readConsentSnapshot(),'rejected');
  assert.equal(win['ga-disable-G-TEST'],true); assert.equal(reloads,1);
  assert.equal(messages[0][2].analytics_storage,'denied');
  buttons[0].props.onClick();
  assert.equal(h.consent.readConsentSnapshot(),'accepted'); assert.equal(reloads,1,'session-only Allow must not reset itself by reloading');
});
