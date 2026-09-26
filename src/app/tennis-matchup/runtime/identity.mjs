/**
 * Matchup Lab — Court Objects
 * Original vector artwork on a 32-unit grid. Mint carries the active object;
 * ice blue carries the opposing object or reference. Adjacent text supplies
 * meaning: these SVGs deliberately stay out of the accessibility tree.
 */
const namespace = `tml-${Math.random().toString(36).slice(2, 10)}`;
let instance = 0;
const attr = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

const drawings = {
  matchup: ({mint, blue}) => `
    <path d="M8 4h16l5 24H3Z" fill="#18262a" stroke="${blue}" stroke-width="1.4"/>
    <path d="M5.5 16h21M11 4 7.5 28M21 4l3.5 24M9.7 10h12.6M8.3 22h15.4M16 10v12" stroke="#91b6d5" stroke-opacity=".35" stroke-width="1.1"/>
    <path d="m12 21 8-10" stroke="#e0fff5" stroke-width="1.5" stroke-dasharray="2 3"/>
    <circle cx="11" cy="22" r="4.3" fill="${mint}" stroke="#0f1117" stroke-width="1.8"/>
    <circle cx="21" cy="10" r="4.3" fill="${blue}" stroke="#0f1117" stroke-width="1.8"/>
    <path d="M8.4 19.2c2.2.1 4.2 2.1 4.6 5.3M18.4 7.2c2.2.1 4.2 2.1 4.6 5.3" stroke="#0f1117" stroke-opacity=".55" stroke-width="1.2"/>`,
  serve: ({mint, blue}) => `
    <path d="M7 28 12 19" stroke="${blue}" stroke-width="3.5"/>
    <path d="M11.3 21.5 8.9 20" stroke="#e1eef7" stroke-opacity=".7" stroke-width="1"/>
    <ellipse cx="15" cy="13" rx="6.1" ry="8" transform="rotate(30 15 13)" fill="#1d3335" stroke="${mint}" stroke-width="2.5"/>
    <path d="m12 8 6 3m-8 1 8 4m-7 0 4 2m.5-11-5 9m9-6-5 9" stroke="#83e7c3" stroke-opacity=".4" stroke-width="1"/>
    <path d="M23 20c3-3 4-6 4-10" stroke="${blue}" stroke-width="1.8"/>
    <path d="m24.5 12.5 2.5-3 2 3" stroke="${blue}" stroke-width="1.8"/>
    <circle cx="26" cy="4.5" r="2.5" fill="${mint}"/>`,
  return: ({mint, blue}) => `
    <path d="m22 27-5-8" stroke="${blue}" stroke-width="3.5"/>
    <path d="m19.4 22-2.2 1.4" stroke="#e1eef7" stroke-opacity=".7" stroke-width="1"/>
    <ellipse cx="14" cy="13" rx="6.1" ry="8" transform="rotate(-30 14 13)" fill="#1d3335" stroke="${mint}" stroke-width="2.5"/>
    <path d="m11 8 6-2m-7 7 9-4m-6 7 7-3M10 8l5 10m-1-12 5 10" stroke="#83e7c3" stroke-opacity=".4" stroke-width="1"/>
    <path d="M28 9v8c0 4-3 6-7 6H7" stroke="${blue}" stroke-width="1.8"/>
    <path d="m10 20-3 3 3 3" stroke="${blue}" stroke-width="1.8"/>
    <circle cx="27.5" cy="4" r="2.5" fill="${mint}"/>`,
  aces: ({mint, blue}) => `
    <path d="M3 17h7M2 22h5M8 27l8-8" stroke="${blue}" stroke-width="2"/>
    <circle cx="21" cy="10" r="7.5" fill="${mint}"/>
    <path d="M15.3 5.2c4.4.2 9.4 5.3 10.4 10.3M17.5 16.6c-.1-3 2.7-5.8 5.8-5.8" stroke="#163c34" stroke-width="1.6"/>
    <path d="M20 26h8v-8" stroke="${blue}" stroke-width="1.8"/>
    <path d="m23 22 5 4" stroke="#91b6d5" stroke-opacity=".4" stroke-width="1.3"/>`,
  doubleFaults: ({mint, blue}) => `
    <path d="M3 21h26v6H3Z" fill="#203039"/>
    <path d="M3 29V19m26 10V19M3 21h26M4 26h24M9 21v6m7-6v6m7-6v6" stroke="${blue}" stroke-width="1.5"/>
    <path d="M8 3c-3 3-3 7 0 10m16-10c-3 3-3 7 0 10" stroke="#91b6d5" stroke-opacity=".65" stroke-width="1.5" stroke-dasharray="2 3"/>
    <circle cx="9" cy="16" r="3.7" fill="${mint}"/>
    <circle cx="24" cy="16" r="3.7" fill="${mint}"/>
    <path d="M6.4 13.5c2.2.4 3.8 2.2 4.1 5.4m10.9-5.4c2.2.4 3.8 2.2 4.1 5.4" stroke="#163c34" stroke-width="1.1"/>`,
  first: ({mint, blue}) => `
    <path d="M8 4h16v24H8Z" fill="#1a2b31" stroke="${blue}" stroke-width="1.5"/>
    <path d="M8 9h16M8 23h16" stroke="#91b6d5" stroke-opacity=".35" stroke-width="1.2"/>
    <path d="m13 13 3-2v10m-3 0h6" stroke="${mint}" stroke-width="2.6"/>
    <path d="M5 7v18" stroke="#83e7c3" stroke-opacity=".55" stroke-width="1.6"/>`,
  second: ({mint, blue}) => `
    <path d="M8 4h16v24H8Z" fill="#1a2b31" stroke="${blue}" stroke-width="1.5"/>
    <path d="M8 9h16M8 23h16" stroke="#91b6d5" stroke-opacity=".35" stroke-width="1.2"/>
    <path d="M12.7 13.5c.2-3.5 6.3-3.4 6.3.2 0 2.5-5.6 4.1-6.1 7.3H19" stroke="${mint}" stroke-width="2.4"/>
    <path d="M5 7v18M2 10v12" stroke="#83e7c3" stroke-opacity=".55" stroke-width="1.4"/>`,
  court: ({mint, blue}) => `
    <path d="M9 3h14l7 25H2Z" fill="#1a3133" stroke="${mint}" stroke-width="1.7"/>
    <path d="M12 3 7 28M20 3l5 25M7.2 15.5h17.6M10.6 10h10.8M8.5 21h15M16 10v11" stroke="${blue}" stroke-width="1.25"/>
    <path d="M5.5 16.5h21" stroke="#0f1117" stroke-width="3.3"/>
    <path d="M5.5 15.5h21M5.5 13.5v5m21-5v5" stroke="#d1eee4" stroke-width="1.5"/>
    <path d="M3 30h26" stroke="#91b6d5" stroke-opacity=".25" stroke-width="1.3"/>`,
  history: ({mint, blue}) => `
    <path d="M5 8h19v20H5Z" fill="#1b2d33" stroke="${blue}" stroke-width="1.6"/>
    <path d="M8 5h19v20" stroke="#91b6d5" stroke-opacity=".45" stroke-width="1.5"/>
    <path d="M5 13h19M10 6v4m9-4v4" stroke="${blue}" stroke-width="1.7"/>
    <path d="M9 18h4M9 23h4" stroke="#91b6d5" stroke-opacity=".6" stroke-width="1.8"/>
    <circle cx="23" cy="23" r="7" fill="#0f1117" stroke="${mint}" stroke-width="2"/>
    <path d="M23 19v4l3 2" stroke="${mint}" stroke-width="1.9"/>`,
  odds: ({mint, blue}) => `
    <path d="M5 5h9v22H5Z" fill="#1f3a35" stroke="${mint}" stroke-width="1.6"/>
    <path d="M18 5h9v22h-9Z" fill="#21303c" stroke="${blue}" stroke-width="1.6"/>
    <path d="M8 10h3M8 22h3m10-12h3m-3 12h3" stroke="#d6eee8" stroke-opacity=".55" stroke-width="1.5"/>
    <path d="M9 16h14m-11-3-3 3 3 3m8-6 3 3-3 3" stroke="#0f1117" stroke-width="5"/>
    <path d="M9 16h14m-11-3-3 3 3 3m8-6 3 3-3 3" stroke="#d4f5e9" stroke-width="1.7"/>`,
  actual: ({mint, blue}) => `
    <path d="M7 5h18v24H7Z" fill="#1b2d33" stroke="${blue}" stroke-width="1.5"/>
    <path d="M12 3h8v5h-8Z" fill="${blue}"/>
    <path d="m11 17 4 4 7-9" stroke="${mint}" stroke-width="3"/>
    <path d="M12 25h8" stroke="#91b6d5" stroke-opacity=".4" stroke-width="1.5"/>`,
  expected: ({mint, blue}) => `
    <path d="M4 27h24M5 25V9m22 16V9" stroke="${blue}" stroke-width="1.5"/>
    <path d="M6 24C10 24 10 8 16 8s6 16 10 16" fill="#1e3733" stroke="${mint}" stroke-width="2"/>
    <path d="M16 5v22" stroke="#d5eee7" stroke-opacity=".8" stroke-width="1.5" stroke-dasharray="2 3"/>
    <circle cx="16" cy="8" r="2.8" fill="${blue}" stroke="#0f1117" stroke-width="1"/>`,
  excess: ({mint, blue}) => `
    <path d="M5 26h22" stroke="${blue}" stroke-width="1.7"/>
    <path d="M7 16h6v10H7Z" fill="${blue}"/>
    <path d="M19 16h6v10h-6Z" fill="#29423e"/>
    <path d="M19 7h6v9h-6Z" fill="${mint}"/>
    <path d="M4 16h24" stroke="#daeae5" stroke-opacity=".7" stroke-width="1.3" stroke-dasharray="2 3"/>
    <path d="M10 5v6M7 8h6" stroke="${mint}" stroke-width="1.9"/>`,
  gap: ({mint, blue}) => `
    <path d="M6 8h20M6 24h20" stroke="${blue}" stroke-width="1.7"/>
    <circle cx="10" cy="8" r="3.5" fill="${blue}" stroke="#0f1117" stroke-width="1.5"/>
    <circle cx="22" cy="24" r="3.5" fill="${mint}" stroke="#0f1117" stroke-width="1.5"/>
    <path d="M16 11v10m-3-7 3-3 3 3m-6 4 3 3 3-3" stroke="${mint}" stroke-width="1.9"/>
    <path d="M5 13v6m22-6v6" stroke="#91b6d5" stroke-opacity=".3" stroke-width="1.2"/>`
};

/** Return one decorative inline SVG. Use adjacent visible text for its label. */
export function symbol(name, className = '') {
  const draw = Object.hasOwn(drawings, name) ? drawings[name] : null;
  if (!draw) throw new RangeError(`Unknown Matchup Lab symbol: ${name}`);
  const id = `${namespace}-${++instance}`;
  const mint = `url(#${id}-mint)`;
  const blue = `url(#${id}-blue)`;
  return `<svg xmlns="http://www.w3.org/2000/svg" class="${attr(className)}" viewBox="0 0 32 32" width="32" height="32" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"><defs><linearGradient id="${id}-mint" x1="5" y1="3" x2="26" y2="30" gradientUnits="userSpaceOnUse"><stop stop-color="#c7ffe9"/><stop offset=".45" stop-color="#83e7c3"/><stop offset="1" stop-color="#44a68e"/></linearGradient><linearGradient id="${id}-blue" x1="5" y1="2" x2="28" y2="31" gradientUnits="userSpaceOnUse"><stop stop-color="#d5e9f6"/><stop offset=".48" stop-color="#91b6d5"/><stop offset="1" stop-color="#567d9d"/></linearGradient></defs>${draw({mint, blue})}</svg>`;
}
