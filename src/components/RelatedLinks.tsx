import Link from "next/link";
import ToolEmblem, { emblemForHref, type ToolEmblemName } from "./ToolEmblem";
import styles from "./RelatedLinks.module.css";

export type RelatedLink = { href: string; title: string; description: string; icon?: ToolEmblemName };

/** Shared destination cards. Keep contextual links inside prose as ordinary links. */
export default function RelatedLinks({ title, description, links, label = "Related tools and guides", id }: {
  title?: string; description?: string; links: RelatedLink[]; label?: string; id?: string;
}) {
  return <section id={id} className={styles.root} aria-label={title ?? label}>
    {title && <h2>{title}</h2>}{description && <p>{description}</p>}
    <nav className={styles.cards} aria-label={label}>
      {links.map(link => <Link key={link.href} href={link.href} prefetch={false} className={styles.card}>
        <ToolEmblem name={link.icon ?? emblemForHref(link.href)} className={styles.icon} />
        <span className={styles.copy}><strong>{link.title}</strong><span>{link.description}</span></span>
        <svg className={styles.arrow} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden="true"><path d="M5 12h14m-6-6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </Link>)}
    </nav>
  </section>;
}
