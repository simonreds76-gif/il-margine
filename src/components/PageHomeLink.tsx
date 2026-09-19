import Link from "next/link";

type Props = {
  className?: string;
};

export default function PageHomeLink({ className = "" }: Props) {
  return (
    <Link
      href="/"
      className={`page-home-link inline-flex min-h-9 items-center gap-2 rounded-md text-sm text-slate-400 transition hover:text-emerald-200 ${className}`.trim()}
    >
      <span aria-hidden="true">←</span>
      <span>Home</span>
    </Link>
  );
}
