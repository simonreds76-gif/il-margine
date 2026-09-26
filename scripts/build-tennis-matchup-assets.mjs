import fs from 'node:fs';
import postcss from 'postcss';
import sharp from 'sharp';
import React from 'react';
import { ImageResponse } from 'next/dist/compiled/@vercel/og/index.node.js';

fs.mkdirSync('public/tennis-matchup',{recursive:true});
await sharp('research/tennis-matchup/assets/matchup-court-v1.png').resize(640,640).webp({quality:86}).toFile('public/tennis-matchup/court-v1.webp');
const css=postcss.parse(fs.readFileSync('research/tennis-matchup/panel.css','utf8'));
css.walkRules(rule=>{
  if(rule.parent.type==='atrule'&&rule.parent.name.includes('keyframes'))return;
  rule.selectors=rule.selectors.map(selector=>[':root','body','main'].includes(selector)?'.public-site .matchup-lab':`.public-site .matchup-lab ${selector}`);
});
fs.writeFileSync('src/app/tennis-matchup/matchup.css',css.toString()+`
.public-site .matchup-lab{font-family:inherit;--mint:#83e7c3;--blue:#91b6d5;--ink:#edf3f6;--muted:#9cb2c4;--line:#293b46}
.public-site .matchup-lab [hidden]{display:none!important}
.public-site .matchup-lab .matchup-breadcrumb{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:var(--muted);margin:0 0 35px}
.public-site .matchup-lab .matchup-breadcrumb a{min-height:32px;display:inline-flex;align-items:center}
.public-site .matchup-lab .matchup-breadcrumb>span{display:inline-flex;align-items:center}
.public-site .matchup-lab .matchup-freshness{display:flex;flex-wrap:wrap;gap:8px 24px;color:var(--muted);font-size:12px;line-height:1.8;margin:0 0 25px}
.public-site .matchup-lab .matchup-freshness time{color:var(--ink)}
.public-site .matchup-lab .matchup-faq,.public-site .matchup-lab .matchup-next{margin-top:44px;padding-top:32px;border-top:1px solid var(--line)}
.public-site .matchup-lab .matchup-faq h2,.public-site .matchup-lab .matchup-next h2{font-size:28px;line-height:1.3;font-weight:700;margin-bottom:14px}
.public-site .matchup-lab .matchup-faq>p,.public-site .matchup-lab .matchup-next>p{color:var(--muted);line-height:1.8;margin-bottom:24px}
.public-site .matchup-lab .matchup-faq details{margin:12px 0;border:1px solid var(--line);border-radius:12px;padding:0;background:#12202a}
.public-site .matchup-lab .matchup-faq summary{padding:20px;font-weight:600;line-height:1.5;cursor:pointer}
.public-site .matchup-lab .matchup-faq details p{padding:0 20px 20px;line-height:1.8;color:var(--muted)}
.public-site .matchup-lab .matchup-next nav{display:flex;flex-wrap:wrap;gap:12px 24px}.public-site .matchup-lab .matchup-next nav a{display:inline-flex;min-height:44px;align-items:center}
.public-site .matchup-lab section[id]{scroll-margin-top:110px}
@media(max-width:560px){.public-site .matchup-lab{padding-top:24px}.public-site .matchup-lab .product-signature{padding-right:120px}.public-site .matchup-lab h1{font-size:40px;letter-spacing:-1.8px}.public-site .matchup-lab .hero-mark{top:-8px}}
`);
const h=React.createElement;
const png=fs.readFileSync('research/tennis-matchup/assets/matchup-court-v1.png');
const font=fs.readFileSync('node_modules/next/dist/compiled/@vercel/og/noto-sans-v27-latin-regular.ttf');
const tree=h('div',{style:{width:1200,height:630,display:'flex',background:'#0f171e',color:'#f4faf8',fontFamily:'Matchup',alignItems:'center',padding:75}},
 h('div',{style:{display:'flex',flexDirection:'column',width:680}},
  h('div',{style:{fontSize:20,color:'#83e7c3',letterSpacing:3,marginBottom:24}},'IL MARGINE / TENNIS RESEARCH'),
  h('div',{style:{fontSize:65,lineHeight:1.12}},'Tennis Matchup Lab'),
  h('div',{style:{fontSize:27,color:'#b0c5d2',marginTop:24,lineHeight:1.5}},'Head-to-head. Serve. Return.\nUnderstand the players behind the match.'),
  h('div',{style:{fontSize:19,color:'#83e7c3',marginTop:35}},'ilmargine.bet/tennis-matchup')),
 h('img',{src:`data:image/png;base64,${png.toString('base64')}`,width:340,height:340,style:{objectFit:'contain'}}));
const response=new ImageResponse(tree,{width:1200,height:630,fonts:[{name:'Matchup',data:font,weight:400,style:'normal'}]});
fs.writeFileSync('public/tennis-matchup/share-v1.png',Buffer.from(await response.arrayBuffer()));
console.log('Scoped styles, optimised hero and static share card created');
