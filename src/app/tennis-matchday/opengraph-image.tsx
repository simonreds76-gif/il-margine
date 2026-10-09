import { ImageResponse } from 'next/og';
import { readFile } from 'node:fs/promises';
import path from 'node:path';

export const dynamic = 'force-static';
export const alt = 'Tennis Matchday by Il Margine. Upcoming matches, H2H records and historical betting returns.';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

export default async function Image() {
  const mark = await readFile(path.join(process.cwd(), 'public/tennis-matchday/mark.svg'));
  return new ImageResponse(<div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', background: '#101b23', color: '#f1f7f5', padding: '56px 64px', borderLeft: '12px solid #9de9c6' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
      {/* ImageResponse renders its own image elements on the server. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={`data:image/svg+xml;base64,${mark.toString('base64')}`} width={90} height={90} alt="" />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}><span style={{ fontSize: 25, letterSpacing: 3, color: '#9de9c6' }}>RETURN ATLAS</span><span style={{ fontSize: 62, fontWeight: 700, letterSpacing: -2 }}>Tennis Matchday</span></div>
    </div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}><span style={{ fontSize: 60, fontWeight: 700, letterSpacing: -2 }}>The next match. The past meetings.</span><span style={{ fontSize: 30, color: '#c1d3de', lineHeight: 1.4 }}>Explore upcoming fixtures, H2H records and historical betting returns.</span></div>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #365147', paddingTop: 26 }}><span style={{ fontSize: 23, color: '#9de9c6', letterSpacing: 1 }}>FREE TENNIS RESEARCH</span><span style={{ fontSize: 24 }}>ilmargine.bet</span></div>
  </div>, size);
}
