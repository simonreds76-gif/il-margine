"use client";

import { useEffect, useRef, type FocusEvent, type KeyboardEvent } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { BRAND } from "@/lib/brand";

const TIP_LINKS = [{ href: "/tennis-tips", label: "Tennis tips" }, { href: "/player-props", label: "Player props" }];
const PRIMARY_LINKS = [
  { href: "/the-edge", label: "Methodology" },
  { href: "/penalty-takers", label: "Penalty takers" },
  { href: "/fair-odds-lab", label: "Fair Odds Lab" },
  { href: "/return-atlas", label: "Return Atlas" },
  { href: "/track-record", label: "Track record" },
];
const RESOURCE_LINKS = [
  { href: "/resources", label: "All resources" },
  { href: "/bookmakers", label: "Bookmakers" },
  { href: "/calculator", label: "Calculator" },
];

function closeWhenFocusLeaves(event: FocusEvent<HTMLDetailsElement>) {
  if (!event.currentTarget.contains(event.relatedTarget as Node | null)) event.currentTarget.open = false;
}

function Chevron() {
  return <svg aria-hidden="true" className="h-4 w-4 transition-transform group-open:rotate-180" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="m6 9 6 6 6-6" /></svg>;
}

export default function GlobalNav() {
  const pathname = usePathname();
  const nav = useRef<HTMLElement>(null);
  const showMonitorLink = process.env.NODE_ENV !== "production" || process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
  const resources = showMonitorLink ? [...RESOURCE_LINKS, { href: "/model-monitor", label: "Model monitor" }] : RESOURCE_LINKS;
  const closeMenus = () => nav.current?.querySelectorAll<HTMLDetailsElement>("details[open]").forEach((menu) => { menu.open = false; });
  const active = (href: string) => pathname === href || pathname.startsWith(href + "/");
  const linkClass = (href: string) => `inline-flex min-h-11 items-center rounded-xl border border-transparent px-3 text-sm font-semibold transition-colors ${active(href) ? "border-emerald-300/25 bg-emerald-300/10 text-emerald-200" : "text-slate-300 hover:border-emerald-300/20 hover:bg-emerald-300/10 hover:text-emerald-100"}`;
  const current = (href: string) => pathname === href ? "page" as const : active(href) ? "location" as const : undefined;

  useEffect(() => {
    const closeOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !nav.current?.contains(event.target)) {
        nav.current?.querySelectorAll<HTMLDetailsElement>("details[open]").forEach((menu) => { menu.open = false; });
      }
    };
    document.addEventListener("pointerdown", closeOutside);
    return () => document.removeEventListener("pointerdown", closeOutside);
  }, []);

  useEffect(() => {
    nav.current?.querySelectorAll<HTMLDetailsElement>("details[open]").forEach((menu) => { menu.open = false; });
  }, [pathname]);

  const escapeMenu = (event: KeyboardEvent<HTMLElement>) => {
    if (event.key !== "Escape") return;
    const menu = event.target instanceof HTMLElement ? event.target.closest<HTMLDetailsElement>("details[open]") : null;
    if (menu) { event.preventDefault(); closeMenus(); menu.querySelector("summary")?.focus(); }
  };

  return <nav ref={nav} aria-label="Main navigation" onKeyDown={escapeMenu} className="public-navigation sticky top-0 z-50 border-b border-slate-800 bg-[#0f1117]/95 backdrop-blur-sm">
    <div className="mx-auto flex h-[72px] max-w-7xl items-center justify-between gap-4 px-4 sm:px-6 lg:px-8 xl:h-20">
      <Link prefetch={false} href="/" aria-label="Il Margine home" onClick={closeMenus} className="flex min-h-11 shrink-0 items-center rounded-lg"><Image src={BRAND.compact} alt="Il Margine" width={700} height={168} className="h-auto w-[196px] max-w-full object-contain lg:w-[210px] xl:w-[240px]" priority unoptimized /></Link>
      <div className="hidden items-center gap-1 xl:flex">
        <details name="desktop-site-navigation" onBlur={closeWhenFocusLeaves} className="group relative">
          <summary className={`flex min-h-11 cursor-pointer list-none items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium hover:bg-slate-800/60 [&::-webkit-details-marker]:hidden ${TIP_LINKS.some((link) => active(link.href)) ? "text-emerald-300" : "text-slate-300"}`}>Tips <Chevron /></summary>
          <div className="absolute left-0 top-full mt-2 w-48 rounded-xl border border-slate-700 bg-slate-950 p-2 shadow-xl shadow-black/30">{TIP_LINKS.map((link) => <Link prefetch={false} key={link.href} href={link.href} onClick={closeMenus} aria-current={current(link.href)} className={`flex w-full ${linkClass(link.href)}`}>{link.label}</Link>)}</div>
        </details>
        {PRIMARY_LINKS.map((link) => <Link prefetch={false} key={link.href} href={link.href} onClick={closeMenus} aria-current={current(link.href)} className={linkClass(link.href)}>{link.label}</Link>)}
        <details name="desktop-site-navigation" onBlur={closeWhenFocusLeaves} className="group relative">
          <summary className={`flex min-h-11 cursor-pointer list-none items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium hover:bg-slate-800/60 [&::-webkit-details-marker]:hidden ${resources.some((link) => active(link.href)) ? "text-emerald-300" : "text-slate-300"}`}>Resources <Chevron /></summary>
          <div className="absolute right-0 top-full mt-2 w-64 rounded-xl border border-slate-700 bg-slate-950 p-2 shadow-xl shadow-black/30">{resources.map((link) => <Link prefetch={false} key={link.href} href={link.href} onClick={closeMenus} aria-current={current(link.href)} className={`flex w-full ${linkClass(link.href)}`}>{link.label}</Link>)}</div>
        </details>
      </div>
      <details onBlur={closeWhenFocusLeaves} className="group xl:hidden">
        <summary className="flex min-h-11 min-w-11 cursor-pointer list-none items-center justify-center gap-2 rounded-xl border border-slate-700 px-3 text-sm font-medium text-slate-200 hover:bg-slate-800 [&::-webkit-details-marker]:hidden">
          <svg aria-hidden="true" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" d="M4 6h16M4 12h16M4 18h16" /></svg>Menu
        </summary>
        <div className="absolute inset-x-0 top-full max-h-[calc(100dvh-72px)] overflow-y-auto border-b border-slate-700 bg-[#0f1117] shadow-xl shadow-black/30">
          <div className="mx-auto grid max-w-7xl gap-5 px-4 py-5 sm:grid-cols-3 sm:px-6">
            {[{ label: "Tips", links: TIP_LINKS }, { label: "Explore", links: PRIMARY_LINKS }, { label: "Resources", links: resources }].map((group) => <div key={group.label}>
              <p className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{group.label}</p>
              <ul className="space-y-1">{group.links.map((link) => <li key={link.href}><Link prefetch={false} href={link.href} onClick={closeMenus} aria-current={current(link.href)} className={`flex w-full min-h-11 rounded-xl px-3 py-3 text-sm font-medium ${active(link.href) ? "bg-emerald-400/10 text-emerald-200" : "text-slate-200 hover:bg-slate-800"}`}>{link.label}</Link></li>)}</ul>
            </div>)}
          </div>
        </div>
      </details>
    </div>
  </nav>;
}
