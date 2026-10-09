import React, { useState } from "react";
import {
  ChevronDown,
  Layout,
  ShieldCheck,
  Cpu,
} from "lucide-react";
import { cn } from "../lib/utils";

interface TopBarProps {
  operationMode: "DIRECT" | "SWARM";
  selectedModel: string;
  sessionTitle?: string;
  isCanvasOpen: boolean;
  onToggleCanvas: () => void;
  isStreamConnected: boolean;
  onOpenSettings?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
  operationMode,
  selectedModel,
  sessionTitle,
  isCanvasOpen,
  onToggleCanvas,
  isStreamConnected,
  onOpenSettings,
}) => {
  const [showStatusModal, setShowStatusModal] = useState(false);

  return (
    <header className="flex items-center justify-between px-6 py-3.5 bg-transparent z-20 select-none">
      {/* ── Left: Version Pill Dropdown ── */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setShowStatusModal(!showStatusModal)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#181d26] border border-[#2b3342] text-xs font-medium text-zinc-200 hover:border-cyan-500/40 hover:text-white transition-all shadow-sm"
        >
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
          <span>Ultron v4.5</span>
          <ChevronDown className="w-3.5 h-3.5 text-zinc-400" />
        </button>

        {/* Live Status Indicator */}
        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-[#141820] border border-white/5 text-[11px] text-zinc-400 font-mono">
          <span>Mode:</span>
          <span className="text-cyan-300 font-semibold">{operationMode}</span>
          <span className="text-zinc-600">•</span>
          <span className="text-zinc-300 flex items-center gap-1">
            <Cpu className="w-3 h-3 text-cyan-400" />
            <span className="max-w-[100px] truncate">{selectedModel}</span>
          </span>
          <span className="text-zinc-600">•</span>
          <span className="text-emerald-400 flex items-center gap-1">
            <ShieldCheck className="w-3 h-3" />
            {sessionTitle || "Online"}
          </span>
        </div>
      </div>

      {/* ── Right: Syntrix Navigation Links & User Avatar ── */}
      <div className="flex items-center gap-4 sm:gap-6 text-xs font-medium text-zinc-400">
        <button
          type="button"
          onClick={onToggleCanvas}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs transition-all",
            isCanvasOpen
              ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-[0_0_12px_rgba(0,240,255,0.3)]"
              : "bg-[#181d26] text-zinc-400 border-[#2b3342] hover:text-white"
          )}
          title="Toggle Parallel WebRTC Screencast Canvas"
        >
          <Layout className="w-3.5 h-3.5 text-cyan-400" />
          <span className="hidden sm:inline">Canvas</span>
          {isStreamConnected && (
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          )}
        </button>

        <a
          href="#dashboard"
          className="text-white font-semibold hover:text-cyan-300 transition-colors"
        >
          Dashboard
        </a>

        <button
          type="button"
          onClick={onOpenSettings}
          className="hover:text-white transition-colors hidden sm:inline"
        >
          Settings
        </button>

        <a
          href="https://github.com/apparcora-app/ultron-memory-agent"
          target="_blank"
          rel="noreferrer"
          className="hover:text-white transition-colors hidden md:inline"
        >
          Help & Support
        </a>

        {/* User Profile Avatar with glowing ring (Syntrix exact) */}
        <div className="relative cursor-pointer group">
          <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-amber-600 via-rose-500 to-cyan-500 p-0.5 shadow-md">
            <div className="w-full h-full rounded-full bg-[#12151b] flex items-center justify-center text-xs font-bold text-white">
              HR
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
