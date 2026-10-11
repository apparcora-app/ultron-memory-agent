import React, { useState } from "react";
import ReactMarkdown from "react-markdown";
import {
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
      <div className="flex justify-end mb-4 animate-in fade-in">
        <div className="flex items-start gap-3 max-w-[85%]">
          <div className="px-4 py-3 rounded-2xl bg-[#f1f5f9] text-[#0f172a] border border-[#e2e8f0] shadow-sm text-sm leading-relaxed font-medium">
            {message.content}
          </div>
          <div className="w-8 h-8 rounded-full bg-[#e2e8f0] border border-[#cbd5e1] flex items-center justify-center text-slate-700 shrink-0">
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3.5 mb-6 max-w-[95%] animate-in fade-in">
      {/* ── Stitch Robot Avatar with Sky-Blue Glow ── */}
      <div className="robot-avatar-wrapper relative w-8 h-8 rounded-xl bg-[#0f0f11] border border-[#0ea5e9]/40 flex items-center justify-center text-[#38bdf8] shrink-0 shadow-[0_0_12px_rgba(14,165,233,0.3)] robot-idle">
        <svg className="robot-body w-6 h-6 overflow-visible" fill="none" viewBox="0 0 36 36">
          <circle className="antenna-light" cx="18" cy="4" fill="#38bdf8" r="2.2" />
          <line stroke="#38bdf8" strokeLinecap="round" strokeWidth="1.8" x1="18" x2="18" y1="6" y2="10" />
          <rect fill="#0284c7" height="6" opacity="0.9" rx="1" width="2" x="3.5" y="16" />
          <rect fill="#0284c7" height="6" opacity="0.9" rx="1" width="2" x="30.5" y="16" />
          <rect fill="#0f1f2e" height="20" rx="6" stroke="#38bdf8" strokeWidth="1.6" width="25" x="5.5" y="10" />
          <rect fill="#081521" height="10" rx="3.5" stroke="#7dd3fc" strokeOpacity="0.4" strokeWidth="1" width="19" x="8.5" y="14" />
          <g className="robot-eyes">
            <circle cx="13.5" cy="18.5" fill="#38bdf8" r="2.2" />
            <circle cx="14" cy="17.8" fill="#ffffff" r="0.75" />
            <circle cx="22.5" cy="18.5" fill="#38bdf8" r="2.2" />
            <circle cx="23" cy="17.8" fill="#ffffff" r="0.75" />
          </g>
          <path d="M 15 26.5 Q 18 28.2 21 26.5" fill="none" opacity="0.9" stroke="#38bdf8" strokeLinecap="round" strokeWidth="1.2" />
        </svg>
      </div>

      <div className="flex-1 overflow-hidden space-y-2">
        {/* Model Badge & Meta */}
        <div className="flex items-center gap-2 text-[11px] font-mono text-slate-500">
          <span className="font-bold text-[#0f172a] tracking-wide">ULTRON PRIME</span>
          {message.model_display && (
            <span className="px-2 py-0.5 rounded-full bg-[#f0f9ff] border border-[#bae6fd] text-[#0284c7] text-[10px] font-semibold">
              {message.model_display}
            </span>
          )}
          {message.timestamp && <span className="text-slate-400">{message.timestamp}</span>}
        </div>

        {/* ── Heuristic Reasoning Accordion (Stitch High-Contrast Light Style) ── */}
        {message.route_reason && (
          <div className="rounded-xl border border-[#e2e8f0] bg-[#f8fafc] overflow-hidden text-xs font-mono shadow-sm">
            <button
              onClick={() => setShowThinking(!showThinking)}
              className="flex items-center justify-between w-full px-3 py-2 text-slate-700 hover:text-[#0f172a] transition-colors"
            >
              <div className="flex items-center gap-1.5">
                <Sparkles className="w-3.5 h-3.5 text-[#0284c7]" />
                <span className="font-semibold text-slate-800">Heuristic Routing & Reasoning</span>
              </div>
              {showThinking ? (
                <ChevronUp className="w-3.5 h-3.5 text-slate-500" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
              )}
            </button>
            {showThinking && (
              <div className="p-3 border-t border-[#e2e8f0] bg-white text-slate-600 text-[11px] leading-relaxed">
                {message.route_reason}
              </div>
            )}
          </div>
        )}

        {/* ── Tool Action Badges with High-Contrast Crisp Styling ── */}
        {message.tool_actions && message.tool_actions.length > 0 && (
          <div className="flex flex-wrap gap-2 my-2">
            {message.tool_actions.map((act: ToolActionItem, idx: number) => {
              const isBrowser = act.tool.includes("browser");
              const isComputer = act.tool.includes("computer") || act.tool.includes("shell");
              return (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-[#f8fafc] border border-[#cbd5e1] shadow-xs text-xs font-mono text-[#0f172a]"
                >
                  <div className="flex items-center gap-1.5 font-medium">
                    {isBrowser ? (
                      <Globe className="w-3.5 h-3.5 text-[#0284c7]" />
                    ) : isComputer ? (
                      <Terminal className="w-3.5 h-3.5 text-amber-600" />
                    ) : (
                      <Zap className="w-3.5 h-3.5 text-emerald-600" />
                    )}
                    <span>{act.tool}</span>
                  </div>

                  {onOpenCanvas && (isBrowser || isComputer) && (
                    <button
                      onClick={onOpenCanvas}
                      className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-[#f0f9ff] text-[#0284c7] border border-[#bae6fd] hover:bg-[#e0f2fe] transition-colors text-[10px] font-semibold"
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

        {/* ── Markdown Formatted Assistant Content (Crisp Dark Text) ── */}
        <div className="text-sm leading-relaxed text-[#0f172a] space-y-2">
          <ReactMarkdown
            components={{
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "");
                const isInline = !match && !String(children).includes("\n");
                return isInline ? (
                  <code
                    className="px-1.5 py-0.5 rounded bg-slate-100 text-[#0f172a] font-mono text-xs font-semibold border border-slate-200"
                    {...props}
                  >
                    {children}
                  </code>
                ) : (
                  <div className="relative my-3 rounded-xl overflow-hidden border border-[#cbd5e1] bg-[#0f172a] font-mono text-xs text-white shadow-md">
                    <div className="flex items-center justify-between px-3 py-1.5 bg-[#1e293b] border-b border-slate-700 text-slate-300 text-[11px]">
                      <span>{match ? match[1] : "code"}</span>
                      <button
                        onClick={() => handleCopy(String(children), 1)}
                        className="flex items-center gap-1 text-slate-400 hover:text-white transition-colors"
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
                    <pre className="p-3 overflow-x-auto text-slate-100">
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

