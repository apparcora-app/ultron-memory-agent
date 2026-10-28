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
    const raw = urlInput.trim();
    if (!raw || !onNavigateUrl) return;
    const validatedUrl = raw.startsWith("http://") || raw.startsWith("https://") ? raw : `https://${raw}`;
    onNavigateUrl(validatedUrl);
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
        "flex flex-col h-full bg-theme-panel border-l border-theme-border shadow-xl relative select-none",
        className
      )}
    >
      {/* ── Top Canvas Header (Stitch Clean Semantic Tokens) ── */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-theme-dock/90 border-b border-theme-border backdrop-blur-md z-20 shrink-0">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-theme-accent" />
            <span className="font-sans text-xs font-bold text-theme-main tracking-wide">
              Ultron Browser
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-theme-card border border-theme-border text-[10px] font-mono shadow-xs">
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
            <span className={isConnected ? "text-emerald-500 font-semibold" : "text-theme-muted"}>
              {isConnected ? "60 FPS LIVE" : isConnecting ? "CONNECTING..." : "STANDBY"}
            </span>
          </div>
        </div>

        {/* Right Header Buttons */}
        <div className="flex items-center gap-1.5">
          {onReconnect && (
            <button
              onClick={onReconnect}
              className="p-1.5 rounded-lg text-theme-muted hover:text-theme-main hover:bg-theme-card transition-colors"
              title="Reconnect WebRTC"
            >
              <RefreshCw className={cn("w-3.5 h-3.5", isConnecting && "animate-spin text-theme-accent")} />
            </button>
          )}

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-theme-muted hover:text-theme-main hover:bg-theme-card transition-colors"
            title="Close Canvas (Return to Chat-Only)"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* ── URL Address Bar & Quick Navigation ── */}
      <div className="px-3 py-2 bg-theme-panel border-b border-theme-border flex flex-col gap-1.5 z-10 shrink-0">
        <form onSubmit={handleLaunchUrl} className="flex items-center gap-2">
          <div className="flex-1 flex items-center gap-2 px-2.5 py-1 rounded-xl bg-theme-ground border border-theme-border text-xs font-mono text-theme-main focus-within:border-theme-focus focus-within:bg-theme-panel shadow-xs transition-colors">
            <Search className="w-3.5 h-3.5 text-theme-muted" />
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="Enter URL to browse (e.g. https://duckduckgo.com)..."
              className="w-full bg-transparent focus:outline-none text-theme-main placeholder:text-theme-muted/60 text-xs font-medium"
            />
          </div>
          <button
            type="submit"
            className="flex items-center gap-1 px-3 py-1.5 rounded-xl bg-theme-accent text-white hover:bg-theme-accent/90 font-mono font-semibold text-xs transition-all shadow-xs"
          >
            <span>Navigate</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </form>

        {/* Quick Launch Shortcuts */}
        <div className="flex items-center gap-1.5 text-[10px] font-mono text-theme-muted overflow-x-auto pb-0.5">
          <span className="font-semibold text-theme-muted/70">Quick:</span>
          <button
            onClick={() => handleQuickUrl("https://duckduckgo.com")}
            className="px-2 py-0.5 rounded-lg bg-theme-dock hover:bg-theme-card text-theme-muted hover:text-theme-main border border-theme-border transition-colors"
          >
            DuckDuckGo
          </button>
          <button
            onClick={() => handleQuickUrl("https://news.ycombinator.com")}
            className="px-2 py-0.5 rounded-lg bg-theme-dock hover:bg-theme-card text-theme-muted hover:text-theme-main border border-theme-border transition-colors"
          >
            Hacker News
          </button>
          <button
            onClick={() => handleQuickUrl("https://github.com/trending")}
            className="px-2 py-0.5 rounded-lg bg-theme-dock hover:bg-theme-card text-theme-muted hover:text-theme-main border border-theme-border transition-colors"
          >
            GitHub
          </button>
          <button
            onClick={() => handleQuickUrl("https://en.wikipedia.org/wiki/Special:Random")}
            className="px-2 py-0.5 rounded-lg bg-theme-dock hover:bg-theme-card text-theme-muted hover:text-theme-main border border-theme-border transition-colors"
          >
            Wikipedia
          </button>
        </div>
      </div>

      {/* ── WebRTC Video Player Viewport ── */}
      <div className="flex-1 relative overflow-hidden p-2.5 bg-theme-ground">
        <WebRTCPlayer
          mediaStream={mediaStream}
          isConnected={isConnected}
          isConnecting={isConnecting}
          error={error}
          agentCursor={agentCursor}
          sendControlEvent={sendControlEvent}
          onReconnect={onReconnect}
          className="w-full h-full rounded-2xl border border-theme-border shadow-lg overflow-hidden bg-theme-panel"
          botName="Ultron Browser Controller"
        />
      </div>
    </div>
  );
};

