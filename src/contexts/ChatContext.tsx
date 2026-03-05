"use client";

import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

type ChatContextValue = {
  open: boolean;
  setOpen: (v: boolean) => void;
  openChat: () => void;
  /** Open chat and submit this message immediately */
  openChatWithMessage: (text: string) => void;
  pendingMessage: string | null;
  clearPendingMessage: () => void;
};

const ChatContext = createContext<ChatContextValue | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const openChat = useCallback(() => setOpen(true), []);
  const openChatWithMessage = useCallback((text: string) => {
    setPendingMessage(text.trim() || null);
    setOpen(true);
  }, []);
  const clearPendingMessage = useCallback(() => setPendingMessage(null), []);
  return (
    <ChatContext.Provider value={{ open, setOpen, openChat, openChatWithMessage, pendingMessage, clearPendingMessage }}>
      {children}
    </ChatContext.Provider>
  );
}

export function useChatContext() {
  const ctx = useContext(ChatContext);
  return ctx;
}
