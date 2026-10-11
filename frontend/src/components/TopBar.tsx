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
    <header className="flex items-center justify-between px-5 py-3 bg-white/95 border-b border-[#e2e8f0] backdrop-blur-md z-20 shrink-0 select-none">
      {/* ── Left: Version Pill Dropdown ── */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => setShowStatusModal(!showStatusModal)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-[#f8fafc] border border-[#e2e8f0] text-xs font-medium text-[#0f172a] hover:border-[#0284c7] transition-all shadow-sm"
        >
          <span className="w-2 h-2 rounded-full bg-[#0284c7] animate-pulse" />
          <span className="font-sans font-semibold">Ultron v4.5</span>
          <ChevronDown className="w-3.5 h-3.5 text-slate-500" />
        </button>

        {/* Live Status Indicator */}
        <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-[#f8fafc] border border-[#e2e8f0] text-[11px] text-slate-600 font-mono shadow-xs">
          <span>Mode:</span>
          <span className="text-[#0284c7] font-semibold">{operationMode}</span>
          <span className="text-slate-300">•</span>
          <span className="text-slate-700 flex items-center gap-1">
            <Cpu className="w-3 h-3 text-[#0284c7]" />
            <span className="max-w-[100px] truncate">{selectedModel}</span>
          </span>
          <span className="text-slate-300">•</span>
          <span className="text-emerald-600 flex items-center gap-1 font-semibold">
            <ShieldCheck className="w-3 h-3 text-emerald-500" />
            {sessionTitle || "Online"}
          </span>
        </div>
      </div>

      {/* ── Right: Stitch Navigation Links & User Avatar ── */}
      <div className="flex items-center gap-3 sm:gap-5 text-xs font-medium text-slate-600">
        <button
          type="button"
          onClick={onToggleCanvas}
          className={cn(
            "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs transition-all shadow-sm",
            isCanvasOpen
              ? "bg-[#f0f9ff] text-[#0284c7] border-[#bae6fd] shadow-sm font-semibold"
              : "bg-[#f8fafc] text-slate-700 border-[#e2e8f0] hover:text-[#0f172a] hover:border-[#cbd5e1]"
          )}
          title="Toggle Parallel WebRTC Screencast Canvas"
        >
          <Layout className="w-3.5 h-3.5 text-[#0284c7]" />
          <span className="hidden sm:inline">Canvas</span>
          {isStreamConnected && (
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          )}
        </button>

        <a
          href="#dashboard"
          className="text-[#0f172a] font-semibold hover:text-[#0284c7] transition-colors"
        >
          Dashboard
        </a>

        <button
          type="button"
          onClick={onOpenSettings}
          className="hover:text-[#0f172a] transition-colors hidden sm:inline"
        >
          Settings
        </button>

        <a
          href="https://github.com/apparcora-app/ultron-memory-agent"
          target="_blank"
          rel="noreferrer"
          className="hover:text-[#0f172a] transition-colors hidden md:inline"
        >
          Help & Support
        </a>

        {/* User Profile Avatar */}
        <div className="relative cursor-pointer group">
          <div className="w-8 h-8 rounded-full bg-[#0284c7] flex items-center justify-center text-xs font-bold text-white shadow-sm ring-2 ring-white">
            HR
          </div>
        </div>
      </div>
    </header>
  );
};

