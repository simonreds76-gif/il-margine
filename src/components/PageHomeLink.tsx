import Link from "next/link";
import Image from "next/image";

type Props = {
  className?: string;
};

export default function PageHomeLink({ className = "" }: Props) {
  return (
    <Link
      href="/"
      className={`inline-flex items-center gap-2 rounded-full border border-[color:rgba(87,209,150,0.22)] bg-[rgba(87,209,150,0.06)] px-3 py-2 text-sm text-slate-200 shadow-[0_0_18px_rgba(87,209,150,0.08)] transition hover:-translate-y-0.5 hover:border-[color:rgba(87,209,150,0.52)] hover:text-[var(--brand-green)] hover:shadow-[0_0_26px_rgba(87,209,150,0.16)] ${className}`.trim()}
    >
      <Image
        src="/brand/il-margine-tube-icon.png"
        alt=""
        width={32}
        height={32}
        className="h-8 w-8 shrink-0 rounded-full object-contain"
      />
      <span>Home</span>
    </Link>
  );
}
