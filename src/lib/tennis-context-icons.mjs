/** Original 40-unit vector artwork matching Matchup Lab's Court Objects palette.
 * Decorative: the adjacent heading carries the accessible name.
 */
const drawings = {
  conditions: `
    <path d="M10 6h19l5 28H4Z" fill="#18332f" stroke="#9dc7bd" stroke-width="1.5"/>
    <path d="m13.5 6-4 28M25.5 6l3.8 28M8.6 14h21.8M6.2 26h26.4M19.5 14v12" stroke="#91b6d5" stroke-opacity=".72" stroke-width="1.25"/>
    <path d="M7 20h24.5" stroke="#d3eee4" stroke-width="1.7"/>
    <path d="m22 15 2-2m-5 5 1-1" stroke="#b4ead4" stroke-width="1.8"/>
    <circle cx="30" cy="8.5" r="5" fill="#b4ead4" stroke="#101b23" stroke-width="1.7"/>
    <path d="M26.5 5.5c2.9.2 5.8 3 6.4 6.1M27.4 12.5c-.1-2 1.6-3.9 3.8-4" stroke="#27584a" stroke-width="1.2"/>
  `,
  physical: `
    <rect x="8" y="7" width="24" height="28" rx="3" fill="#1c303a" stroke="#9dc7bd" stroke-width="1.5"/>
    <rect x="14" y="4" width="12" height="6" rx="2" fill="#101b23" stroke="#b4ead4" stroke-width="1.5"/>
    <circle cx="16.5" cy="16.5" r="2.8" fill="#b4ead4" fill-opacity=".13" stroke="#b4ead4" stroke-width="1.5"/>
    <path d="M12 25v-1.5a4.5 4.5 0 0 1 9 0V25" stroke="#b4ead4" stroke-width="1.5"/>
    <path d="M25 16h3m-3 4h3M12 30h6" stroke="#91b6d5" stroke-width="1.5"/>
    <circle cx="29" cy="29" r="6.5" fill="#101b23" stroke="#b4ead4" stroke-width="1.7"/>
    <path d="M29 25.5v3.8l2.5 1.4" stroke="#d3eee4" stroke-width="1.5"/>
  `,
};
export function contextIcon(kind) {
  const drawing=drawings[kind];
  return drawing?`<svg class="te-icon" width="40" height="40" viewBox="0 0 40 40" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${drawing}</svg>`:'';
}
