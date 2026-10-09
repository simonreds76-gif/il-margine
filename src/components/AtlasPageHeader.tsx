import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./ResearchPage.module.css";
import "@/app/research-mobile.css";

const editions = [
  { id: "matchday", href: "/football-atlas/fixtures", label: "Matchday", image: "/football-atlas/matchday/mark-v1.svg" },
  { id: "football", href: "/football-atlas", label: "Football", image: "/images/tools/football-v1.webp" },
  { id: "managers", href: "/manager-atlas", label: "Managers", image: "/manager-atlas/mark-v2.svg" },
  { id: "tennis", href: "/return-atlas", label: "Tennis", image: "/images/tools/tennis-v1.webp" },
  { id: "tennis-matchday", href: "/tennis-matchday", label: "Tennis Matchday", image: "/tennis-matchday/mark.svg" },
  { id: "matchup", href: "/tennis-matchup", label: "Matchup Lab", image: "/tennis-matchup/court-v1.webp" },
] as const;

export default function AtlasPageHeader({ edition, description, children }: {
  edition: typeof editions[number]["id"];
  description: string;
  children?: ReactNode;
}) {
  const current = editions.find(item => item.id === edition)!;
  return <header className={styles.header}>
    <nav className={styles.breadcrumb} aria-label="Breadcrumb">
      <Link href="/" prefetch={false}>Home</Link><span aria-hidden="true">/</span>
      <Link href="/tools" prefetch={false}>Research tools</Link><span aria-hidden="true">/</span>
      <span aria-current="page">{current.label}</span>
    </nav>
    <div className={styles.identity}>
      <Image className={styles.mark} src={current.image} alt="" width={72} height={72} priority unoptimized />
      <div><h1 className={styles.title}>{edition === "matchup" ? <>Matchup <span>Lab</span></> : <>Return <span>Atlas</span></>}<span className="sr-only">{edition === "matchup" ? ": Tennis H2H & player statistics" : `: ${current.label}`}</span></h1>
        <p className={styles.edition}>{edition === "matchup" ? "Tennis" : current.label}</p></div>
    </div>
    <p className={styles.description}>{description}</p>
    <nav className={styles.editions} aria-label="Return Atlas tools">
      {editions.map(item => <Link key={item.id} href={item.href} prefetch={false} aria-label={item.id === "matchup" ? "Tennis Matchup Lab" : item.label} aria-current={edition === item.id ? "page" : undefined}><Image src={item.image} alt="" width={24} height={24} unoptimized /><span>{item.id === "matchup" ? "Matchup" : item.id === "tennis-matchday" ? "Daily H2H" : item.label}</span></Link>)}
    </nav>
    {children}
  </header>;
}
