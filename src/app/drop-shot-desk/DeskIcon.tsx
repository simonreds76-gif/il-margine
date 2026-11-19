export function DeskIcon({ name }: {name:"drop"|"replay"|"record"|"download"}) {
  const paths={
    drop:<><path d="M3 6h6v5h6v6h5"/><circle cx="20" cy="17" r="2" fill="currentColor"/></>,
    replay:<><path d="M3.5 10a8.5 8.5 0 1 1 1.2 7.1M3.5 4.5V10H9"/><path d="m10 8 6 4-6 4z" strokeLinejoin="round"/></>,
    record:<><rect x="3.5" y="4" width="17" height="16" rx="2"/><path d="M7 8h9M7 12h3m3 2 2 2 4-5"/></>,
    download:<><path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/></>,
  };
  return <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}
