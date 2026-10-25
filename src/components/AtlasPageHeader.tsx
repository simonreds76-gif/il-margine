import Image from "next/image";
import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./ResearchPage.module.css";
import "@/app/research-mobile.css";

import ResearchToolNav from './ResearchToolNav';
import { researchTools as editions } from './research-tools';

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
      <div><h1 className={styles.title}>{edition === "aerial" ? <>Air <span>Control</span></> : edition === "matchup" ? <>Matchup <span>Lab</span></> : <>Return <span>Atlas</span></>}<span className="sr-only">{edition === "aerial" ? ": Lineup height, headers and delivery" : edition === "matchup" ? ": Tennis H2H & player statistics" : `: ${current.label}`}</span></h1>
        <p className={styles.edition}>{edition === "aerial" ? "Lineup research · beta" : edition === "matchup" ? "Tennis" : current.label}</p></div>
    </div>
    <p className={styles.description}>{description}</p>
    <ResearchToolNav current={edition}/>
    {children}
  </header>;
}
