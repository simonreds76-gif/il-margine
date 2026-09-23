import fs from 'node:fs';
import path from 'node:path';
import React from 'react';
import { ImageResponse } from 'next/dist/compiled/@vercel/og/index.node.js';

// Build once and serve as static files: sharing must never trigger a render function.
const logo='data:image/png;base64,'+fs.readFileSync('public/football-atlas/wordmark-football-v1.png').toString('base64');
const font=fs.readFileSync('node_modules/next/dist/compiled/@vercel/og/noto-sans-v27-latin-regular.ttf');
const h=React.createElement;
for(const [name,height] of [['square',1200],['wide',630]]) {
 const square=name==='square';
 const tree=h('div',{style:{width:1200,height,display:'flex',alignItems:'center',justifyContent:'center',background:'radial-gradient(ellipse at 20% 10%, #174237 0%, #101b20 45%, #0c1118 100%)',fontFamily:'Atlas',color:'#f3f6f5',position:'relative'}},
  h('div',{style:{position:'absolute',inset:32,border:'1px solid #36524f',borderRadius:36,display:'flex'}}),
  h('div',{style:{display:'flex',flexDirection:'column',alignItems:'center',width:1080}},
   h('div',{style:{fontSize:square?25:19,letterSpacing:5,color:'#8ee3c2',marginBottom:square?30:8}},'IL MARGINE / FOOTBALL RESEARCH'),
   h('img',{src:logo,width:square?1080:930,height:square?360:310,style:{objectFit:'contain'}}),
   h('div',{style:{fontSize:square?36:30,marginTop:square?4:-10,color:'#e3eceb'}},'The club. The price. The return.'),
   h('div',{style:{display:'flex',gap:14,marginTop:square?40:28}},...['League matches','Pinnacle prices','Flat 1u stakes'].map(text=>h('div',{key:text,style:{display:'flex',fontSize:square?25:21,border:'1px solid #416960',borderRadius:14,background:'#19332e',padding:'13px 23px',color:'#a4eed2'}},text))),
   h('div',{style:{fontSize:square?24:20,color:'#95acae',marginTop:square?48:25}},'ilmargine.bet/football-atlas')
  )
 );
 const response=new ImageResponse(tree,{width:1200,height,fonts:[{name:'Atlas',data:font,weight:400,style:'normal'}]});
 const out=`public/football-atlas/share-v1-${name}.png`;
 fs.writeFileSync(out,Buffer.from(await response.arrayBuffer()));
 console.log(out);
}
