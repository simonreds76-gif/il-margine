"use client";

import { useState, useRef, useEffect, useMemo, FormEvent } from "react";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { useChatContext } from "@/contexts/ChatContext";
import { track } from "@/lib/analytics";

const SUGGESTED = [
  "CPI of Miami in 2024?",
  "How do underdogs do at Indian Wells?",
  "Sinner's record vs left-handed players?",
  "Who's won Indian Wells the most?",
  "Dimitrov's record at Monte Carlo?",
];

const ROGER_ENABLED = true;

export default function ChatWidget() {
  const ctx = useChatContext();
  const [localOpen, setLocalOpen] = useState(false);
  const open = ctx?.open ?? localOpen;
  const setOpen = ctx?.setOpen ?? setLocalOpen;
  const [inputValue, setInputValue] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const transport = useMemo(() => new DefaultChatTransport({ api: "/api/chat" }), []);

  const { messages, sendMessage, status, error, clearError } = useChat({ transport });

  const isLoading = status === "streaming" || status === "submitted";

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  // When opened with a pending message (e.g. from Roger page), submit it
  useEffect(() => {
    if (open && ctx?.pendingMessage && !isLoading) {
      const msg = ctx.pendingMessage;
      ctx.clearPendingMessage();
      submit(msg);
    }
  }, [open, ctx?.pendingMessage, ctx?.clearPendingMessage, isLoading, submit]);

  function submit(text: string) {
    if (!text.trim() || isLoading) return;
    clearError();
    track("roger_query", { query: text.trim() });
    sendMessage({ text });
    setInputValue("");
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    submit(inputValue);
  }

  function getTextContent(msg: (typeof messages)[number]): string {
    return msg.parts
      .filter((p): p is Extract<typeof p, { type: "text" }> => p.type === "text")
      .map((p) => p.text)
      .join("");
  }

  if (!ROGER_ENABLED) return null;

  return (
    <>
      <button
        onClick={() => setOpen(!open)}
        className="fixed z-50 flex items-center justify-center w-14 h-14 min-w-[56px] min-h-[56px] rounded-full bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white shadow-lg shadow-emerald-900/30 transition-all hover:scale-105 touch-manipulation
          bottom-[max(1.25rem,env(safe-area-inset-bottom))] right-[max(1.25rem,env(safe-area-inset-right))]"
        aria-label="Open Roger tennis stats chat"
      >
        {open ? (
          <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        )}
      </button>

      {open && (
        <div
          className="fixed z-50 flex flex-col rounded-2xl border border-slate-700/60 bg-[#0f1117] shadow-2xl shadow-black/50 overflow-hidden
            left-4 right-4 top-[max(4rem,env(safe-area-inset-top))] bottom-[max(6.5rem,calc(5.5rem+env(safe-area-inset-bottom)))]
            sm:left-auto sm:right-5 sm:top-auto sm:bottom-24 sm:w-[380px] sm:max-w-[calc(100vw-2.5rem)] sm:h-[540px] sm:max-h-[calc(100vh-8rem)]"
        >
          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800/60 bg-[#0d0f14] shrink-0">
            <img src="/favicon.png" alt="Il Margine" className="w-8 h-8 object-contain shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-100">Roger</p>
              <p className="text-[11px] text-slate-500 hidden sm:block">Tennis stats chatbot. H2H, tournaments, records</p>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="shrink-0 p-2 -m-2 text-slate-500 hover:text-slate-300 active:text-slate-200 transition-colors touch-manipulation min-w-[44px] min-h-[44px] flex items-center justify-center"
              aria-label="Close chat"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto overflow-x-hidden px-4 py-3 space-y-3 overscroll-contain" style={{ WebkitOverflowScrolling: "touch" }}>
            {messages.length === 0 && !error && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">
                  Ask me anything about ATP tennis: player records, head to head, tournament history, court pace (CPI), serve stats, and more.
                </p>
                <p className="text-xs text-slate-500">
                  Player records and H2H use full ATP history; fav/dog ROI covers the last 4 years. Any tips from Roger are based solely on our stats and data. Roger doesn&apos;t speculate.
                </p>
                <div className="space-y-2">
                  <p className="text-[11px] text-slate-600 uppercase tracking-wider font-medium">Try asking:</p>
                  {SUGGESTED.map((q) => (
                    <button
                      key={q}
                      onClick={() => submit(q)}
                      className="block w-full text-left text-sm sm:text-xs px-4 py-3 sm:py-2 rounded-lg border border-slate-800/60 text-slate-300 hover:bg-slate-800/40 hover:border-slate-700 active:bg-slate-800/50 transition-colors touch-manipulation min-h-[44px] sm:min-h-0"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) => {
              const text = getTextContent(m);
              if (!text && m.role === "assistant") return null;
              return (
                <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed whitespace-pre-wrap ${
                      m.role === "user"
                        ? "bg-emerald-600/20 text-emerald-100 rounded-br-md"
                        : "bg-slate-800/60 text-slate-200 rounded-bl-md"
                    }`}
                  >
                    {text}
                  </div>
                </div>
              );
            })}

            {error && (
              <div className="flex justify-start">
                <div className="max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed bg-slate-800/60 text-slate-300 rounded-bl-md">
                  {error.message || "Sorry, I'm a bit busy right now. Please try again in a moment."}
                </div>
              </div>
            )}

            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-slate-800/60 rounded-2xl rounded-bl-md px-4 py-3">
                  <div className="flex items-center gap-1.5">
                    <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce [animation-delay:0ms]" />
                    <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce [animation-delay:150ms]" />
                    <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce [animation-delay:300ms]" />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <form
            onSubmit={onSubmit}
            className="flex items-center gap-2 px-3 py-3 border-t border-slate-800/60 bg-[#0d0f14] shrink-0"
          >
            <input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask about any player or tournament..."
              className="flex-1 min-w-0 bg-slate-800/50 border border-slate-700/50 rounded-xl px-3.5 py-3 text-base sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 transition-colors"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="flex items-center justify-center w-11 h-11 min-w-[44px] min-h-[44px] rounded-xl bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white disabled:opacity-30 disabled:hover:bg-emerald-600 transition-all touch-manipulation"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14M12 5l7 7-7 7" />
              </svg>
            </button>
          </form>
        </div>
      )}
    </>
  );
}
