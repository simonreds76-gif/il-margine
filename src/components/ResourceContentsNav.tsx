type TocItem = {
  id: string;
  label: string;
};

type ResourceContentsNavProps = {
  items: TocItem[];
};

function ContentsLinks({ items }: ResourceContentsNavProps) {
  return (
    <nav aria-label="Article contents" className="space-y-2">
      {items.map((item, index) => (
        <a
          key={item.id}
          href={`#${item.id}`}
          className="block text-sm leading-6 text-slate-400 transition-colors hover:text-emerald-300"
        >
          <span className="mr-2 font-mono text-[11px] text-slate-600">
            {String(index + 1).padStart(2, "0")}
          </span>
          {item.label}
        </a>
      ))}
    </nav>
  );
}

export default function ResourceContentsNav({ items }: ResourceContentsNavProps) {
  return (
    <aside className="mb-8 lg:sticky lg:top-24 lg:mb-0 lg:self-start">
      <details className="group rounded-xl border border-slate-800 bg-slate-900/60 p-4 lg:hidden">
        <summary className="flex cursor-pointer list-none items-center justify-between font-mono text-xs uppercase tracking-[0.16em] text-slate-300">
          Jump to a section
          <span aria-hidden="true" className="text-emerald-400 transition-transform group-open:rotate-45">
            +
          </span>
        </summary>
        <div className="mt-4 border-t border-slate-800 pt-4">
          <ContentsLinks items={items} />
        </div>
      </details>

      <div className="hidden rounded-xl border border-slate-800 bg-slate-900/55 p-5 lg:block">
        <h2 className="mb-4 font-mono text-xs uppercase tracking-[0.16em] text-slate-500">
          In this guide
        </h2>
        <ContentsLinks items={items} />
      </div>
    </aside>
  );
}
