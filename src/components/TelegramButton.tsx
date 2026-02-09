import { TELEGRAM_CHANNEL_URL } from "@/lib/config";

const telegramIcon = (
  <svg className="shrink-0" width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69a.2.2 0 00-.05-.18c-.06-.05-.14-.03-.21-.02-.09.02-1.49.95-4.22 2.79-.4.27-.76.41-1.08.4-.36-.01-1.04-.2-1.55-.37-.63-.2-1.12-.31-1.08-.66.02-.18.27-.36.74-.55 2.92-1.27 4.86-2.11 5.83-2.51 2.78-1.16 3.35-1.36 3.73-1.36.08 0 .27.02.39.12.1.08.13.19.14.27-.01.06.01.24 0 .38z" />
  </svg>
);

interface TelegramButtonProps {
  variant?: "nav" | "cta" | "inline";
  className?: string;
  onClick?: () => void;
}

const baseClass = "inline-flex items-center justify-center gap-2 font-medium text-white rounded transition-colors bg-[#0088cc] hover:bg-[#0077b5] focus:outline-none focus:ring-2 focus:ring-[#0088cc] focus:ring-offset-2 focus:ring-offset-[#0f1117]";

export default function TelegramButton({ variant = "nav", className = "", onClick }: TelegramButtonProps) {
  const variantClasses = {
    nav: "px-4 py-2.5 text-sm",
    cta: "px-6 sm:px-8 py-3 sm:py-3.5 text-base sm:text-lg shadow-lg",
    inline: "px-5 py-2.5 text-sm",
  };

  return (
    <a
      href={TELEGRAM_CHANNEL_URL}
      target="_blank"
      rel="noopener noreferrer"
      onClick={onClick}
      className={`${baseClass} ${variantClasses[variant]} ${className}`.trim()}
    >
      <span className="text-white" aria-hidden>✓</span>
      {telegramIcon}
      <span>Join free on Telegram</span>
    </a>
  );
}
