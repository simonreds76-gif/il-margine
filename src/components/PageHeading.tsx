import type { ReactNode } from "react";
import Link from "next/link";
import ToolEmblem, { type ToolEmblemName } from "./ToolEmblem";
import styles from "./PublicPageHeading.module.css";

export default function PageHeading({ eyebrow, title, children, icon = "guide", parent, meta, actions, titleId, introClassName = "" }: {
  eyebrow: string; title: string; children: ReactNode; icon?: ToolEmblemName;
  parent?: { href: string; label: string }; meta?: ReactNode; actions?: ReactNode; titleId?: string; introClassName?: string;
}) {
  return <header className={styles.header}>
    <nav className={styles.breadcrumb} aria-label="Breadcrumb">
      <Link href="/" prefetch={false}>Home</Link><span aria-hidden="true">/</span>
      {parent && <><Link href={parent.href} prefetch={false}>{parent.label}</Link><span aria-hidden="true">/</span></>}
      <span aria-current="page">{title}</span>
    </nav>
    <div className={styles.identity}><ToolEmblem name={icon} className={styles.mark} /><div>
      <h1 id={titleId}>{title}</h1><p className={styles.category}>{eyebrow}</p>
    </div></div>
    <div className={`${styles.intro} ${introClassName}`}>{children}</div>
    {meta && <div className={styles.meta}>{meta}</div>}
    {actions && <div className={styles.actions}>{actions}</div>}
  </header>;
}
