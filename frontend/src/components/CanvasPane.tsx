import React, { useState } from "react";
import {
  ArrowRight,
  Globe,
  RefreshCw,
  Search,
  X,
} from "lucide-react";
import { WebRTCPlayer } from "./WebRTCPlayer";
import type { AgentCursorState } from "../hooks/useWebRTCStream";
import { cn } from "../lib/utils";

interface CanvasPaneProps {
  mediaStream: MediaStream | null;
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  agentCursor: AgentCursorState | null;
  sendControlEvent: (payload: Record<string, unknown>) => void;
  onReconnect?: () => void;
  onClose: () => void;
  onNavigateUrl?: (url: string) => void;
  className?: string;
}

export const CanvasPane: React.FC<CanvasPaneProps> = ({
  mediaStream,
  isConnected,
  isConnecting,
  error,
  agentCursor,
  sendControlEvent,
  onReconnect,
  onClose,
  onNavigateUrl,
  className,
}) => {
  const [urlInput, setUrlInput] = useState("https://duckduckgo.com");

  const handleLaunchUrl = (e: React.FormEvent) => {
    e.preventDefault();
    if (urlInput.trim() && onNavigateUrl) {
      onNavigateUrl(urlInput.trim());
    }
  };

  const handleQuickUrl = (url: string) => {
    setUrlInput(url);
    if (onNavigateUrl) {
      onNavigateUrl(url);
    }
  };

  return (
    <div
      className={cn(
        "flex flex-col h-full bg-white border-l border-[#e2e8f0] shadow-xl relative select-none",
        className
      )}
    >
      {/* ── Top Canvas Header (Stitch Clean Light Style) ── */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-[#f8fafc] border-b border-[#e2e8f0] backdrop-blur-md z-20 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-[#0284c7]" />
            <span className="font-sans text-xs font-bold text-[#0f172a] tracking-wide">
              Ultron Browser
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-white border border-[#cbd5e1] text-[10px] font-mono shadow-xs">
            <span
              className={cn(
                "w-2 h-2 rounded-full",
                isConnected
                  ? "bg-emerald-500 shadow-[0_0_8px_#10b981]"
                  : isConnecting
                  ? "bg-amber-400 animate-ping"
                  : "bg-slate-400"
              )}
            />
            <span className={isConnected ? "text-emerald-600 font-semibold" : "text-slate-500"}>
              {isConnected ? "60 FPS LIVE" : isConnecting ? "CONNECTING..." : "STANDBY"}
            </span>
          </div>
        </div>

        {/* Right Header Buttons */}
        <div className="flex items-center gap-1.5">
          {onReconnect && (
            <button
              onClick={onReconnect}
              className="p-1 rounded-lg text-slate-500 hover:text-[#0f172a] hover:bg-slate-200/60 transition-colors"
              title="Reconnect WebRTC"
            >
              <RefreshCw className={cn("w-3.5 h-3.5", isConnecting && "animate-spin text-[#0284c7]")} />
            </button>
          )}

          <button
            onClick={onClose}
            className="p-1 rounded-lg text-slate-500 hover:text-[#0f172a] hover:bg-slate-200/60 transition-colors"
            title="Close Canvas (Return to Chat-Only)"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ── URL Address Bar & Quick Navigation ── */}
      <div className="px-3 py-2 bg-white border-b border-[#e2e8f0] flex flex-col gap-1.5 z-10 shrink-0">
        <form onSubmit={handleLaunchUrl} className="flex items-center gap-2">
          <div className="flex-1 flex items-center gap-2 px-2.5 py-1 rounded-xl bg-[#f8fafc] border border-[#cbd5e1] text-xs font-mono text-slate-800 focus-within:border-[#0284c7] focus-within:bg-white shadow-sm">
            <Search className="w-3.5 h-3.5 text-slate-400" />
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="Enter URL to browse (e.g. https://duckduckgo.com)..."
              className="w-full bg-transparent focus:outline-none text-[#0f172a] placeholder:text-slate-400 text-xs font-medium"
            />
          </div>
          <button
            type="submit"
            className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-[#0f172a] text-white hover:bg-black font-mono font-semibold text-xs transition-all shadow-sm"
          >
            <span>Navigate</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </form>

        {/* Quick Launch Shortcuts */}
        <div className="flex items-center gap-1.5 text-[10px] font-mono text-slate-500 overflow-x-auto pb-0.5">
          <span className="font-semibold text-slate-400">Quick:</span>
          <button
            onClick={() => handleQuickUrl("https://duckduckgo.com")}
            className="px-2 py-0.5 rounded-lg bg-[#f1f5f9] hover:bg-[#e2e8f0] text-slate-700 hover:text-[#0f172a] border border-[#e2e8f0] transition-colors"
          >
            DuckDuckGo
          </button>
          <button
            onClick={() => handleQuickUrl("https://news.ycombinator.com")}
            className="px-2 py-0.5 rounded-lg bg-[#f1f5f9] hover:bg-[#e2e8f0] text-slate-700 hover:text-[#0f172a] border border-[#e2e8f0] transition-colors"
          >
            Hacker News
          </button>
          <button
            onClick={() => handleQuickUrl("https://github.com/trending")}
            className="px-2 py-0.5 rounded-lg bg-[#f1f5f9] hover:bg-[#e2e8f0] text-slate-700 hover:text-[#0f172a] border border-[#e2e8f0] transition-colors"
          >
            GitHub
          </button>
          <button
            onClick={() => handleQuickUrl("https://en.wikipedia.org/wiki/Special:Random")}
            className="px-2 py-0.5 rounded-lg bg-[#f1f5f9] hover:bg-[#e2e8f0] text-slate-700 hover:text-[#0f172a] border border-[#e2e8f0] transition-colors"
          >
            Wikipedia
          </button>
        </div>
      </div>

      {/* ── WebRTC Video Player Viewport ── */}
      <div className="flex-1 relative overflow-hidden p-2.5 bg-[#f1f5f9]">
        <WebRTCPlayer
          mediaStream={mediaStream}
          isConnected={isConnected}
          isConnecting={isConnecting}
          error={error}
          agentCursor={agentCursor}
          sendControlEvent={sendControlEvent}
          onReconnect={onReconnect}
          className="w-full h-full rounded-2xl border border-[#cbd5e1] shadow-lg overflow-hidden bg-white"
          botName="Ultron Browser Controller"
        />
      </div>
    </div>
  );
};

