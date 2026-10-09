import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  BrainCircuit,
  Check,
  ChevronDown,
  ChevronUp,
  Copy,
  ExternalLink,
  Globe,
  Sparkles,
  Terminal,
  User,
  Zap,
} from "lucide-react";
import type { ChatMessage, ToolActionItem } from "../types/chat";

interface ChatMessageItemProps {
  message: ChatMessage;
  onOpenCanvas?: () => void;
}

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  onOpenCanvas,
}) => {
  const [showThinking, setShowThinking] = useState(false);
  const [copiedCodeIndex, setCopiedCodeIndex] = useState<number | null>(null);

  const isUser = message.role === "user";

  const handleCopy = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedCodeIndex(index);
    setTimeout(() => setCopiedCodeIndex(null), 2000);
  };

  if (isUser) {
    return (
      <div className="flex justify-end mb-6">
        <div className="flex items-start gap-3 max-w-[80%]">
          <div className="px-4 py-3 rounded-2xl bg-zinc-800 text-zinc-100 border border-zinc-700/60 shadow-lg text-sm leading-relaxed">
            {message.content}
          </div>
          <div className="w-8 h-8 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-300 flex-shrink-0">
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3.5 mb-7 max-w-[90%]">
      {/* ── Ultron Assistant Avatar ── */}
      <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/40 flex items-center justify-center text-cyan-400 flex-shrink-0 shadow-[0_0_12px_rgba(0,240,255,0.2)]">
        <BrainCircuit className="w-4 h-4 animate-pulse" />
      </div>

      <div className="flex-1 overflow-hidden space-y-2">
        {/* Model Badge & Meta */}
        <div className="flex items-center gap-2 text-[11px] font-mono text-zinc-500">
          <span className="font-semibold text-zinc-300">ULTRON</span>
          {message.model_display && (
            <span className="px-1.5 py-0.5 rounded bg-zinc-800/80 border border-zinc-700/50 text-cyan-400 text-[10px]">
              {message.model_display}
            </span>
          )}
          {message.timestamp && <span>{message.timestamp}</span>}
        </div>

        {/* ── Optional Reasoning Accordion (Kimi / ChatGPT Thinking) ── */}
        {message.route_reason && (
          <div className="rounded-lg border border-zinc-800 bg-zinc-900/40 overflow-hidden text-xs font-mono">
            <button
              onClick={() => setShowThinking(!showThinking)}
              className="flex items-center justify-between w-full px-3 py-1.5 text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                <span>Heuristic Routing & Reasoning</span>
              </div>
              {showThinking ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
            {showThinking && (
              <div className="p-3 border-t border-zinc-800/60 bg-zinc-950/60 text-zinc-400 text-[11px] leading-relaxed">
                {message.route_reason}
              </div>
            )}
          </div>
        )}

        {/* ── Tool Actions Badges (OpenBot Browser / Computer Shell) ── */}
        {message.tool_actions && message.tool_actions.length > 0 && (
          <div className="flex flex-wrap gap-2 my-2">
            {message.tool_actions.map((act: ToolActionItem, idx: number) => {
              const isBrowser = act.tool.includes("browser");
              const isComputer = act.tool.includes("computer") || act.tool.includes("shell");
              return (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-2.5 py-1.5 rounded-lg bg-zinc-900 border border-zinc-700/80 shadow-md text-xs font-mono"
                >
                  <div className="flex items-center gap-1.5 text-amber-300">
                    {isBrowser ? (
                      <Globe className="w-3.5 h-3.5 text-cyan-400" />
                    ) : isComputer ? (
                      <Terminal className="w-3.5 h-3.5 text-amber-400" />
                    ) : (
                      <Zap className="w-3.5 h-3.5 text-emerald-400" />
                    )}
                    <span>{act.tool}</span>
                  </div>

                  {onOpenCanvas && (isBrowser || isComputer) && (
                    <button
                      onClick={onOpenCanvas}
                      className="flex items-center gap-1 px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30 transition-colors text-[10px]"
                      title="Open Live WebRTC Screencast Player"
                    >
                      <ExternalLink className="w-2.5 h-2.5" />
                      <span>Live Canvas</span>
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ── Markdown Formatted Assistant Content ── */}
        <div className="prose prose-invert prose-zinc max-w-none text-sm leading-relaxed text-zinc-200">
          <ReactMarkdown
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "");
                const isInline = !match && !String(children).includes("\n");
                return isInline ? (
                  <code
                    className="px-1.5 py-0.5 rounded bg-zinc-800 text-cyan-300 font-mono text-xs border border-zinc-700/60"
                    {...props}
                  >
                    {children}
                  </code>
                ) : (
                  <div className="relative my-3 rounded-lg overflow-hidden border border-zinc-800 bg-zinc-900/90 font-mono text-xs">
                    <div className="flex items-center justify-between px-3 py-1.5 bg-zinc-950/80 border-b border-zinc-800 text-zinc-400 text-[11px]">
                      <span>{match ? match[1] : "code"}</span>
                      <button
                        onClick={() => handleCopy(String(children), 1)}
                        className="flex items-center gap-1 text-zinc-400 hover:text-zinc-200 transition-colors"
                      >
                        {copiedCodeIndex === 1 ? (
                          <>
                            <Check className="w-3 h-3 text-emerald-400" />
                            <span className="text-emerald-400">Copied</span>
                          </>
                        ) : (
                          <>
                            <Copy className="w-3 h-3" />
                            <span>Copy</span>
                          </>
                        )}
                      </button>
                    </div>
                    <pre className="p-3 overflow-x-auto text-zinc-100">
                      <code>{children}</code>
                    </pre>
                  </div>
                );
              },
            }}
          >
            {message.content}
          </ReactMarkdown>
        </div>
      </div>
    </div>
  );
};
