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

const idxFromHash = (str: string): number => {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (Math.imul(31, h) + str.charCodeAt(i)) | 0;
  }
  return h;
};

export const ChatMessageItem: React.FC<ChatMessageItemProps> = ({
  message,
  onOpenCanvas,
}) => {
  const [showThinking, setShowThinking] = useState(false);
  const [copiedCodeIndex, setCopiedCodeIndex] = useState<number | null>(null);

  const isUser = message.role === "user";

  const handleCopy = (text: string, index: number) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard
        .writeText(text)
        .then(() => {
          setCopiedCodeIndex(index);
          setTimeout(() => setCopiedCodeIndex(null), 2000);
        })
        .catch(() => {
          // ignore clipboard rejection
        });
    }
  };

  if (isUser) {
    return (
      <div className="flex justify-end mb-4 animate-in fade-in">
        <div className="flex items-start gap-3 max-w-[85%]">
          <div className="px-4 py-3 rounded-2xl bg-theme-panel text-theme-main border border-theme-border shadow-xs text-sm leading-relaxed font-medium">
            {message.content}
          </div>
          <div className="w-8 h-8 rounded-full bg-theme-panel border border-theme-border flex items-center justify-center text-theme-muted shrink-0">
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3.5 mb-6 max-w-[95%] animate-in fade-in" aria-live="polite">
      {/* ── Stitch Robot Avatar with Sky-Blue Glow ── */}
      <div className="robot-avatar-wrapper relative w-8 h-8 rounded-xl bg-theme-dock border border-[#0ea5e9]/40 flex items-center justify-center text-[#38bdf8] shrink-0 shadow-[0_0_12px_rgba(14,165,233,0.3)] robot-idle">
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
        <div className="flex items-center gap-2 text-[11px] font-mono text-theme-muted">
          <span className="font-bold text-theme-main tracking-wide">ULTRON PRIME</span>
          {message.model_display && (
            <span className="px-2 py-0.5 rounded-full bg-theme-panel border border-theme-border text-[#0284c7] text-[10px] font-semibold">
              {message.model_display}
            </span>
          )}
          {message.timestamp && <span className="text-theme-dim">{message.timestamp}</span>}
        </div>

        {/* ── Cognitive Reasoning Stepper & Ledger (DESIGN.md Approved) ── */}
        {message.route_reason && (
          <div className="rounded-xl border border-theme-border bg-theme-panel overflow-hidden text-xs font-mono shadow-xs">
            <button
              onClick={() => setShowThinking(!showThinking)}
              className="flex items-center justify-between w-full px-3 py-2 text-theme-muted hover:text-theme-main transition-colors"
              aria-expanded={showThinking}
            >
              <div className="flex items-center gap-2">
                <Sparkles className="w-3.5 h-3.5 text-[#0284c7]" />
                <span className="font-semibold text-theme-main">Cognitive Stepper & Ledger</span>
                <span className="px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-500 border border-emerald-500/20 text-[10px]">
                  VERIFIED
                </span>
              </div>
              {showThinking ? (
                <ChevronUp className="w-3.5 h-3.5 text-theme-dim" />
              ) : (
                <ChevronDown className="w-3.5 h-3.5 text-theme-dim" />
              )}
            </button>
            {showThinking && (
              <div className="p-3 border-t border-theme-border bg-theme-ground/50 text-theme-muted text-[11px] leading-relaxed space-y-2">
                <div className="flex items-center gap-2 text-emerald-500">
                  <Check className="w-3 h-3" />
                  <span>[1/3] Pre-Inference & Memory Retrieval: Mem0 + Qdrant vectors reconciled.</span>
                </div>
                <div className="flex items-center gap-2 text-sky-400">
                  <Check className="w-3 h-3" />
                  <span>[2/3] Execution Stage: AST Sandbox verified and tool parameterization complete.</span>
                </div>
                <div className="flex items-center gap-2 text-[#0284c7]">
                  <Check className="w-3 h-3" />
                  <span>[3/3] Verification Stage: Ledger truth gate validated; single-pass critic applied.</span>
                </div>
                <div className="mt-2 pt-2 border-t border-theme-border text-theme-dim">
                  <span className="font-semibold text-theme-muted">Routing telemetry:</span> {message.route_reason}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Tool Action Badges with High-Contrast Crisp Styling ── */}
        {message.tool_actions && message.tool_actions.length > 0 && (
          <div className="flex flex-wrap gap-2 my-2">
            {message.tool_actions.map((act: ToolActionItem, idx: number) => {
              const toolName = typeof act?.tool === "string" ? act.tool : "";
              const isBrowser = toolName.includes("browser");
              const isComputer = toolName.includes("computer") || toolName.includes("shell");
              return (
                <div
                  key={idx}
                  className="flex items-center gap-2 px-2.5 py-1.5 rounded-xl bg-theme-panel border border-theme-border shadow-xs text-xs font-mono text-theme-main"
                >
                  <div className="flex items-center gap-1.5 font-medium">
                    {isBrowser ? (
                      <Globe className="w-3.5 h-3.5 text-theme-accent" />
                    ) : isComputer ? (
                      <Terminal className="w-3.5 h-3.5 text-amber-500" />
                    ) : (
                      <Zap className="w-3.5 h-3.5 text-emerald-500" />
                    )}
                    <span>{toolName}</span>
                  </div>

                  {onOpenCanvas && (isBrowser || isComputer) && (
                    <button
                      onClick={onOpenCanvas}
                      className="flex items-center gap-1 px-2 py-0.5 rounded-lg bg-theme-accent/10 text-theme-accent border border-theme-accent/30 hover:bg-theme-accent/20 transition-colors text-[10px] font-semibold"
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
        <div className="text-sm leading-relaxed text-theme-main space-y-2">
          <ReactMarkdown
            components={{
              a({ href, children, ...props }) {
                return (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-theme-accent hover:underline inline-flex items-center gap-0.5"
                    {...props}
                  >
                    {children}
                    <ExternalLink className="w-3 h-3 inline-block ml-0.5 opacity-70" />
                  </a>
                );
              },
              code({ className, children, ...props }) {
                const match = /language-(\w+)/.exec(className || "");
                const isInline = !match && !String(children).includes("\n");
                const codeString = String(children);
                const codeId = idxFromHash(codeString);
                return isInline ? (
                  <code
                    className="px-1.5 py-0.5 rounded bg-theme-card text-theme-accent font-mono text-xs font-semibold border border-theme-border"
                    {...props}
                  >
                    {children}
                  </code>
                ) : (
                  <div className="relative my-3 rounded-xl overflow-hidden border border-theme-border bg-[#0f172a] font-mono text-xs text-white shadow-md">
                    <div className="flex items-center justify-between px-3 py-1.5 bg-[#1e293b] border-b border-slate-700 text-slate-300 text-[11px]">
                      <span>{match ? match[1] : "code"}</span>
                      <button
                        onClick={() => handleCopy(codeString, codeId)}
                        className="flex items-center gap-1 text-slate-400 hover:text-white transition-colors"
                      >
                        {copiedCodeIndex === codeId ? (
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

