"use client";
// Assistant: streaming multi-agent chat (conversation memory for follow-ups) beside the
// portfolio panel.
import { ChatView } from "@/components/ChatView";
import { PortfolioPanel } from "@/components/PortfolioPanel";
import { PageHeader } from "@/components/ui";
import { useChat } from "@/presenters/useChat";
import { usePortfolios } from "@/presenters/usePortfolios";
import { useSession } from "@/presenters/session";

export default function AssistantPage() {
  const { token } = useSession();
  const chat = useChat(token);
  const portfolios = usePortfolios(token);
  return (
    <>
      <PageHeader
        title="Assistant"
        subtitle="The supervisor routes your question to specialist agents (A2A); agents call tools over MCP. Follow-up questions keep the conversation's portfolio."
        actions={
          chat.turns.length > 0 && (
            <button onClick={chat.reset} className="rounded-lg border border-white/10 px-3 py-1 text-sm hover:border-accent">
              New conversation
            </button>
          )
        }
      />
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start">
        <ChatView turns={chat.turns} running={chat.running} onAsk={chat.ask} />
        <PortfolioPanel {...portfolios} onSelect={portfolios.select} />
      </div>
    </>
  );
}
