// Original Return Atlas identity. Decorative SVGs inherit surrounding colour.
const paths = {
 manager:'<path d="M9 10V6a4 4 0 0 1 8 0v1l2 3h-3v3h-3M9 4h7M4 21l2-6 4-2 3 5 2-4 3 2 2 5M10 13l-1 5 4 3 2-7"/>',
 versus:'<circle cx="5" cy="6" r="2"/><circle cx="19" cy="18" r="2"/><path d="M3 12h11m-3-3 3 3-3 3M21 6h-7m3-3-3 3 3 3M10 18H3"/>',
 club:'<path d="M12 3 4 6v6c0 4 3 7 8 10 5-3 8-6 8-10V6l-8-3Z"/><path d="M8 11h8m-4-4v10"/>',
 league:'<path d="M8 3h8v5a4 4 0 0 1-8 0V3Zm0 2H4v2a4 4 0 0 0 4 4m8-6h4v2a4 4 0 0 1-4 4M12 12v5m-4 4h8m-7-4h6v4H9Z"/>',
 calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4m10-4v4M3 11h18m-13 5h2m4 0h2"/>',
 pitch:'<rect x="3" y="4" width="18" height="16" rx="1"/><path d="M12 4v16M3 9h3v6H3m18-6h-3v6h3"/><circle cx="12" cy="12" r="3"/>',
 price:'<path d="m3 13 10-10h7v7L10 20a2 2 0 0 1-3 0l-4-4a2 2 0 0 1 0-3Z"/><circle cx="16.5" cy="6.5" r="1"/><path d="m8 12 4 4m-6-2 4-4"/>',
 chart:'<path d="M3 3v18h18M6 16l5-5 4 2 6-8m-5 0h5v5"/>',
 filter:'<path d="M4 6h16M4 12h16M4 18h16"/><path d="M8 3v6m8 0v6m-8 0v6"/>',
 draw:'<path d="M5 8h14M5 16h14"/>',
 arrow:'<path d="M4 12h16m-6-6 6 6-6 6"/>',
 table:'<rect x="3" y="4" width="18" height="16" rx="1"/><path d="M3 9h18M3 14h18M9 4v16"/>'
};
const aliases={opponent:'versus',opponents:'versus','head-to-head':'versus',season:'calendar',seasons:'calendar',history:'calendar',venue:'pitch',market:'price',odds:'price',trend:'chart',ranking:'chart',profit:'chart',sample:'calendar',team:'club',shield:'club',trophy:'league'};
export function icon(name){
 const key=aliases[name]||name;
 if(!paths[key])throw new Error(`Unknown Return Atlas icon: ${name}`);
 return `<svg class="atlas-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${paths[key]}</svg>`;
}
// A touchline coat and coach profile beside returns above and below break-even.
// Separate shapes leave genuine negative space, keeping the mark theme-independent.
export function brandMark(){
 return `<svg class="atlas-mark" viewBox="0 0 64 64" width="64" height="64" fill="none" aria-hidden="true" focusable="false">
 <path d="M15 17c0-7 4-11 11-11 5 0 9 3 10 7l-8-2-13 6Z" fill="currentColor"/>
 <path d="m16 20 12-6 6 2v5l4 5-5 2v5h-6v5l-8-4v-7c-2-1-3-4-3-7Z" fill="currentColor"/>
 <path d="m17 36-7 6-5 16h14l4-10-6-12Zm4 1 6 4 3-4 7 6 4 15H23l4-10-6-11Z" fill="currentColor"/>
 <path d="m12 44-2 9m22-9 3 9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" opacity=".45"/>
 <path d="m35 30 9-3" stroke="#d9b985" stroke-width="2.5" stroke-linecap="round"/>
 <path d="M44 21c-4-4 4-5 1-10" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity=".5"/>
 <path d="M42 45h18" stroke="currentColor" stroke-width="1.2" opacity=".4"/>
 <path d="M45 48v7" stroke="#d9b985" stroke-width="4"/>
 <path d="M52 42v-7m7 7V25" stroke="currentColor" stroke-width="4"/>
 </svg>`;
}
