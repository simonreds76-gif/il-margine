import Link from "next/link";
import Image from "next/image";
import { BRAND } from "@/lib/brand";
import ComplianceBar from "@/components/ComplianceBar";
import styles from "./Footer.module.css";

interface FooterProps { className?: string; }

const groups = [
  { title: "Return Atlas", links: [
    { label: "Matchday", href: "/football-atlas/fixtures" },
    { label: "Football club returns", href: "/football-atlas" },
    { label: "Football manager returns", href: "/manager-atlas" },
    { label: "Tennis player returns", href: "/return-atlas" },
    { label: "Tennis Matchup Lab", href: "/tennis-matchup" },
  ] },
  { title: "Betting tools", links: [
    { label: "Fair Odds Lab", href: "/fair-odds-lab" },
    { label: "Penalty takers", href: "/penalty-takers" },
    { label: "Mind the Margin", href: "/bookmakers", detail: "Bookmaker margins" },
    { label: "Betting calculators", href: "/calculator" },
    { label: "All betting tools", href: "/tools" },
  ] },
  { title: "Picks and guides", links: [
    { label: "Football player props", href: "/player-props" },
    { label: "Tennis tips", href: "/tennis-tips" },
    { label: "Track record", href: "/track-record" },
    { label: "Guides", href: "/resources" },
  ] },
  { title: "About", links: [
    { label: "Methodology", href: "/the-edge" },
    { label: "FAQ", href: "/faq" },
    { label: "Contact", href: "/contact" },
  ] },
];

export default function Footer({ className = "" }: FooterProps) {
  return (
    <footer id="site-footer" className={`${styles.footer} ${className}`.trim()}>
      <div className={styles.container}>
        <div className={styles.main}>
          <div className={styles.brand}>
            <Link prefetch={false} href="/" aria-label="Il Margine home" className={styles.logo}>
              <Image src={BRAND.compact} alt="Il Margine" width={700} height={168} unoptimized sizes="220px" />
            </Link>
            <p>Independent betting research and specialist tools for football and tennis.</p>
            <a href="https://x.com/ilmarginebet" target="_blank" rel="noopener noreferrer"
              aria-label="Follow Il Margine on X, @ilmarginebet (opens in a new tab)"
              title="Follow @ilmarginebet on X" className={styles.social}>
              <svg viewBox="0 0 24 24" fill="currentColor" width="19" height="19" aria-hidden="true" focusable="false">
                <path d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.64 7.584H.47l8.6-9.835L0 1.154h7.594l5.243 6.932 6.064-6.933Zm-1.29 19.49h2.039L6.486 3.24H4.298l13.313 17.403Z" />
              </svg>
            </a>
          </div>
          <nav aria-label="Footer" className={styles.groups}>
            {groups.map((group) => (
              <div className={styles.group} key={group.title}>
                <h2>{group.title}</h2>
                <ul>{group.links.map((link) => (
                  <li key={link.href}>
                    <Link prefetch={false} href={link.href} className={styles.link}>
                      <span>{link.label}</span>
                      {"detail" in link && <span className={styles.detail}>{link.detail}</span>}
                    </Link>
                  </li>
                ))}</ul>
              </div>
            ))}
          </nav>
        </div>
        <div className={styles.bottom}>
          <div className={styles.legal}>
            <span className={styles.copyright}>© {new Date().getUTCFullYear()} Il Margine</span>
            <nav aria-label="Legal" className={styles.legalLinks}>
              <Link prefetch={false} href="/disclaimer">Disclaimer</Link>
              <Link prefetch={false} href="/privacy-policy">Privacy</Link>
              <Link prefetch={false} href="/cookies-policy">Cookies</Link>
            </nav>
          </div>
          <div className={styles.support}><ComplianceBar /></div>
        </div>
      </div>
    </footer>
  );
}
