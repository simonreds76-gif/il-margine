import Link from "next/link";
import Image from "next/image";

type Props = {
  className?: string;
};

export default function PageHomeLink({ className = "" }: Props) {
  return (
    <Link
      href="/"
      className={`inline-flex items-center gap-2 rounded-full border border-[color:rgba(87,209,150,0.18)] bg-[rgba(87,209,150,0.055)] px-3 py-2 text-sm text-slate-200 shadow-[0_0_18px_rgba(87,209,150,0.06)] transition hover:-translate-y-0.5 hover:border-[color:rgba(87,209,150,0.46)] hover:text-[var(--brand-green)] ${className}`.trim()}
    >
      <Image src="/favicon.png" alt="" width={28} height={28} className="h-7 w-7 shrink-0 object-contain" />
      <span>Home</span>
    </Link>
  );
}
