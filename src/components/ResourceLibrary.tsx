"use client";
import { useState, useSyncExternalStore } from "react";
import Link from "next/link";
import type { Resource } from "@/lib/resources";
import EditorialIcon, { type EditorialIconName } from "./EditorialIcon";

const icons: Record<string, EditorialIconName> = { "/resources/how-to-read-a-tipster-track-record": "guide", "/resources/closing-line-value": "markets", "/resources/kelly-criterion-sports-betting": "bankroll", "/resources/fair-odds-lab-explained": "compare", "/resources/clay-season-tennis-model-caveats": "analysis", "/calculator": "bankroll", "/return-atlas": "compare", "/resources/roger": "about" };
function subscribe(update: () => void) {
  window.addEventListener("popstate", update); window.addEventListener("resource-category-change", update);
  return () => { window.removeEventListener("popstate", update); window.removeEventListener("resource-category-change", update); };
}
function snapshot() { return new URLSearchParams(window.location.search).get("category") ?? ""; }
export default function ResourceLibrary({ resources }: { resources: Resource[] }) {
  const [query, setQuery] = useState("");
  const requested = useSyncExternalStore(subscribe, snapshot, () => "");
  const categories = Array.from(new Set(resources.map(r => r.category)));
  const category = categories.includes(requested as Resource["category"]) ? requested : "";
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  function select(value: string) { const url = new URL(window.location.href); if (value) url.searchParams.set("category", value); else url.searchParams.delete("category"); window.history.replaceState(null, "", url); window.dispatchEvent(new Event("resource-category-change")); }
  const matches = (r: Resource) => (!category || r.category === category) && words.every(w => `${r.title} ${r.description} ${r.category} ${r.href}`.toLowerCase().includes(w));
  const count = resources.filter(matches).length;
  return <section id="resource-library" className="resource-library" aria-labelledby="library-title"><div className="resource-library-top"><div><div className="guide-label">Your reference shelf</div><h2 id="library-title">Guides & tools</h2></div><label className="resource-search">Find a topic<input type="search" value={query} onChange={e => setQuery(e.target.value)} placeholder="Try CLV, Kelly or track record" /></label></div><div className="resource-filters" role="group" aria-label="Resource categories"><button type="button" aria-pressed={!category} onClick={() => select("")}>All resources</button>{categories.map(c => <button type="button" key={c} aria-pressed={category === c} onClick={() => select(c)}>{c === "Lab Notes" ? "Records & research" : c}</button>)}</div><p className="resource-count" role="status">{count} {count === 1 ? "resource" : "resources"}{query || category ? <button type="button" onClick={() => { setQuery(""); select(""); }}>Reset filters</button> : null}</p><div className="resource-card-grid">{resources.map(r => <Link prefetch={false} href={r.href} key={r.href} hidden={!matches(r)} className="resource-card"><div className="resource-card-top"><EditorialIcon name={icons[r.href] ?? "guide"} className="h-12 w-12" /><span>{r.surface === "tool" ? "Interactive tool" : `${r.minRead} min read`}</span></div><h3>{r.title}</h3><p>{r.description}</p><div className="resource-card-bottom"><span>{r.surface === "tool" ? "Explore tool" : "Read the guide"}</span><span aria-hidden="true">↗</span></div></Link>)}</div>{count === 0 && <div className="guide-note"><p>No matching resources. Try “odds”, “tennis” or clear the filters.</p></div>}</section>;
}
