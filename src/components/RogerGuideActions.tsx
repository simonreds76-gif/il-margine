"use client";
import { useChatContext } from "@/contexts/ChatContext";
const prompts = ["Alcaraz vs Sinner head to head on clay?", "Dimitrov’s match record at Monte Carlo?", "Sinner’s serve and return stats on hard courts?"];
export default function RogerGuideActions() {
  const chat = useChatContext();
  return <div className="roger-guide-actions"><button type="button" className="roger-open" onClick={() => chat?.openChat()}>Open Roger ↗</button><h3>Try a specific question</h3>{prompts.map(prompt => <button type="button" key={prompt} onClick={() => chat?.openChatWithMessage(prompt)}>{prompt}<span aria-hidden="true"> ↗</span></button>)}</div>;
}
