"use client";

import { useState, useRef, useEffect, useMemo, FormEvent } from "react";
import { useChat } from "@ai-sdk/react";
import { DefaultChatTransport } from "ai";
import { useChatContext } from "@/contexts/ChatContext";

const SUGGESTED = [
  "What's Sinner's record vs left-handed players?",
  "Alcaraz's record at Indian Wells?",
  "Head-to-head for today's ATP matches?",
  "Who's won Indian Wells the most?",
];

const ROGER_ENABLED = process.env.NODE_ENV !== "production";

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
        className="fixed bottom-5 right-5 z-50 flex items-center justify-center w-14 h-14 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white shadow-lg shadow-emerald-900/30 transition-all hover:scale-105"
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
        <div className="fixed bottom-24 right-5 z-50 w-[380px] max-w-[calc(100vw-2.5rem)] h-[540px] max-h-[calc(100vh-8rem)] flex flex-col rounded-2xl border border-slate-700/60 bg-[#0f1117] shadow-2xl shadow-black/50 overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800/60 bg-[#0d0f14]">
            <img src="/favicon.png" alt="Il Margine" className="w-8 h-8 object-contain" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-slate-100">Roger</p>
              <p className="text-[11px] text-slate-500">Tennis stats chatbot. H2H, tournaments, records</p>
            </div>
            <button onClick={() => setOpen(false)} className="text-slate-500 hover:text-slate-300 transition-colors">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.length === 0 && !error && (
              <div className="space-y-3">
                <p className="text-sm text-slate-400">
                  Ask me anything about ATP tennis: player records, head to head, tournament history, serve stats, and more to enhance your betting.
                </p>
                <div className="space-y-2">
                  <p className="text-[11px] text-slate-600 uppercase tracking-wider font-medium">Try asking:</p>
                  {SUGGESTED.map((q) => (
                    <button
                      key={q}
                      onClick={() => submit(q)}
                      className="block w-full text-left text-xs px-3 py-2 rounded-lg border border-slate-800/60 text-slate-300 hover:bg-slate-800/40 hover:border-slate-700 transition-colors"
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
                  {error.message?.toLowerCase().includes("rate limit") || error.message?.toLowerCase().includes("quota")
                    ? "I've hit my daily question limit. Please try again in an hour or so."
                    : "Sorry, I'm a bit busy right now. Please try again in a moment."}
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
            className="flex items-center gap-2 px-3 py-3 border-t border-slate-800/60 bg-[#0d0f14]"
          >
            <input
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Ask about any player or tournament..."
              className="flex-1 bg-slate-800/50 border border-slate-700/50 rounded-xl px-3.5 py-2.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 transition-colors"
              disabled={isLoading}
            />
            <button
              type="submit"
              disabled={isLoading || !inputValue.trim()}
              className="flex items-center justify-center w-10 h-10 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white disabled:opacity-30 disabled:hover:bg-emerald-600 transition-all"
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
