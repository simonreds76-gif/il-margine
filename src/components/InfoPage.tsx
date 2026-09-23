import type { ReactNode } from "react";
import Link from "next/link";
import Footer from "./Footer";
import PageHomeLink from "./PageHomeLink";
import EditorialIcon, { type EditorialIconName } from "./EditorialIcon";
import "./resource-guides.css";
import "./info-pages.css";

const pages = [["Contact", "/contact"], ["Disclaimer", "/disclaimer"], ["Privacy", "/privacy-policy"], ["Cookies", "/cookies-policy"]];
export default function InfoPage({ title, intro, icon, path, children }: { title: string; intro: string; icon: EditorialIconName; path: string; children: ReactNode }) {
  return <div className="guide-page info-page"><header className="guide-hero"><div className="guide-container"><PageHomeLink /><div className="guide-hero-title info-title"><EditorialIcon name={icon} /><div><div className="guide-label">Il Margine · help & information</div><h1>{title}</h1><p className="guide-deck">{intro}</p><div className="guide-meta"><time dateTime="2026-09-23">Updated 23 September 2026</time></div></div></div></div></header><main className="guide-container info-layout"><nav aria-label="Help and policies" className="info-nav">{pages.map(([label, href]) => <Link key={href} href={href} aria-current={path === href ? "page" : undefined}>{label}<span aria-hidden="true">↗</span></Link>)}<Link href="/faq">Frequently asked questions<span aria-hidden="true">↗</span></Link></nav><div className="guide-copy">{children}</div></main><Footer /></div>;
}
