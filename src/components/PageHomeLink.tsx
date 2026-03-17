import Link from "next/link";
import Image from "next/image";

type Props = {
  className?: string;
};

export default function PageHomeLink({ className = "" }: Props) {
  return (
    <Link
      href="/"
      className={`inline-flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/70 px-3 py-2 text-sm text-slate-300 transition hover:-translate-y-0.5 hover:border-slate-700 hover:text-white ${className}`.trim()}
    >
      <Image src="/favicon.png" alt="" width={28} height={28} className="h-7 w-7 shrink-0 object-contain" />
      <span>Home</span>
    </Link>
  );
}
