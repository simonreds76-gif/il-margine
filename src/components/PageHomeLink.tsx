import Link from "next/link";
import Image from "next/image";
import { BRAND } from "@/lib/brand";

type Props = {
  className?: string;
};

export default function PageHomeLink({ className = "" }: Props) {
  return (
    <Link
      href="/"
      className={`page-home-link brand-home-button ${className}`.trim()}
    >
      <Image src={BRAND.icon} alt="" width={36} height={36} unoptimized />
      <span><small>IL MARGINE</small><strong>Back to home</strong></span>
      <span className="brand-home-arrow" aria-hidden="true">↗</span>
    </Link>
  );
}
