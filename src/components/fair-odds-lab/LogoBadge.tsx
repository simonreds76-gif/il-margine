import Image from "next/image";

type LogoBadgeProps = {
  src?: string;
  alt: string;
  fallback?: string;
  size?: number;
  shape?: "circle" | "rounded";
  className?: string;
};

export function LogoBadge({
  src,
  alt,
  fallback,
  size = 28,
  shape = "circle",
  className = "",
}: LogoBadgeProps) {
  const initials =
    fallback
      ?.split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "?";

  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center overflow-hidden border border-slate-700/65 bg-slate-900/80 text-[10px] font-black uppercase text-slate-300 ${
        shape === "circle" ? "rounded-full" : "rounded-xl"
      } ${className}`}
      style={{ width: size, height: size }}
    >
      {src ? (
        <Image
          src={src}
          alt={alt}
          width={size}
          height={size}
          className="h-full w-full object-contain"
          loading="lazy"
        />
      ) : (
        initials.slice(0, 2)
      )}
    </span>
  );
}
