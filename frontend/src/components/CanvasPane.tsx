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
        "flex flex-col h-full bg-zinc-950 border-l border-zinc-800/80 shadow-2xl relative select-none",
        className
      )}
    >
      {/* ── Top Canvas Header (Kimi / ChatGPT Canvas Style) ── */}
      <div className="flex items-center justify-between px-4 py-2.5 bg-zinc-900/90 border-b border-zinc-800/80 backdrop-blur-md z-20">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Globe className="w-4 h-4 text-cyan-400" />
            <span className="font-mono text-xs font-bold text-zinc-100 tracking-wide">
              OPENBOT CANVAS
            </span>
          </div>

          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-zinc-950 border border-zinc-800 text-[10px] font-mono">
            <span
              className={cn(
                "w-2 h-2 rounded-full",
                isConnected
                  ? "bg-emerald-400 shadow-[0_0_8px_#34d399]"
                  : isConnecting
                  ? "bg-amber-400 animate-ping"
                  : "bg-zinc-600"
              )}
            />
            <span className={isConnected ? "text-emerald-400 font-semibold" : "text-zinc-400"}>
              {isConnected ? "60 FPS LIVE" : isConnecting ? "CONNECTING..." : "STANDBY"}
            </span>
          </div>
        </div>

        {/* Right Header Buttons */}
        <div className="flex items-center gap-1.5">
          {onReconnect && (
            <button
              onClick={onReconnect}
              className="p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
              title="Reconnect WebRTC"
            >
              <RefreshCw className={cn("w-3.5 h-3.5", isConnecting && "animate-spin text-cyan-400")} />
            </button>
          )}

          <button
            onClick={onClose}
            className="p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800 transition-colors"
            title="Close Canvas (Return to Chat-Only)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* ── URL Address Bar & Quick Navigation ── */}
      <div className="px-3 py-2 bg-zinc-900/60 border-b border-zinc-800/60 flex flex-col gap-1.5 z-10">
        <form onSubmit={handleLaunchUrl} className="flex items-center gap-2">
          <div className="flex-1 flex items-center gap-2 px-2.5 py-1 rounded-lg bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-300 focus-within:border-cyan-500/60">
            <Search className="w-3.5 h-3.5 text-zinc-500" />
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="Enter URL to browse (e.g. https://news.ycombinator.com)..."
              className="w-full bg-transparent focus:outline-none text-zinc-100 placeholder:text-zinc-600 text-xs"
            />
          </div>
          <button
            type="submit"
            className="flex items-center gap-1 px-3 py-1 rounded-lg bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 hover:bg-cyan-500/30 font-mono text-xs transition-colors"
          >
            <span>Navigate</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </form>

        {/* Quick Launch Shortcuts */}
        <div className="flex items-center gap-1.5 text-[10px] font-mono text-zinc-500 overflow-x-auto pb-0.5">
          <span>Quick:</span>
          <button
            onClick={() => handleQuickUrl("https://duckduckgo.com")}
            className="px-2 py-0.5 rounded bg-zinc-800/80 hover:bg-zinc-800 text-zinc-300 hover:text-cyan-300 transition-colors"
          >
            DuckDuckGo
          </button>
          <button
            onClick={() => handleQuickUrl("https://news.ycombinator.com")}
            className="px-2 py-0.5 rounded bg-zinc-800/80 hover:bg-zinc-800 text-zinc-300 hover:text-cyan-300 transition-colors"
          >
            Hacker News
          </button>
          <button
            onClick={() => handleQuickUrl("https://github.com/trending")}
            className="px-2 py-0.5 rounded bg-zinc-800/80 hover:bg-zinc-800 text-zinc-300 hover:text-cyan-300 transition-colors"
          >
            GitHub
          </button>
          <button
            onClick={() => handleQuickUrl("https://en.wikipedia.org/wiki/Special:Random")}
            className="px-2 py-0.5 rounded bg-zinc-800/80 hover:bg-zinc-800 text-zinc-300 hover:text-cyan-300 transition-colors"
          >
            Wikipedia
          </button>
        </div>
      </div>

      {/* ── WebRTC Video Player Viewport ── */}
      <div className="flex-1 relative overflow-hidden p-2 bg-zinc-950">
        <WebRTCPlayer
          mediaStream={mediaStream}
          isConnected={isConnected}
          isConnecting={isConnecting}
          error={error}
          agentCursor={agentCursor}
          sendControlEvent={sendControlEvent}
          onReconnect={onReconnect}
          className="w-full h-full"
          botName="OpenBot Browser Controller"
        />
      </div>
    </div>
  );
};
