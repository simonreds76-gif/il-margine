import type { ReactNode } from "react";
import PageHomeLink from "./PageHomeLink";

export default function PageHeading({ eyebrow, title, children }: { eyebrow: string; title: string; children: ReactNode }) {
  return <header className="page-heading">
    <PageHomeLink />
    <p className="site-eyebrow">{eyebrow}</p>
    <h1>{title}</h1>
    <div className="page-intro">{children}</div>
  </header>;
}
