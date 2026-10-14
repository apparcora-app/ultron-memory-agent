import React, { useState } from "react";
import {
  ChevronDown,
} from "lucide-react";

interface TopBarProps {
  operationMode?: "DIRECT" | "SWARM";
  selectedModel?: string;
  sessionTitle?: string;
  isCanvasOpen?: boolean;
  onToggleCanvas?: () => void;
  isStreamConnected?: boolean;
  onOpenSettings?: () => void;
  onOpenMemories?: () => void;
}

export const TopBar: React.FC<TopBarProps> = ({
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
      </div>

      {/* ── Right: Stitch Navigation Links & User Avatar ── */}
      <div className="flex items-center gap-3 sm:gap-5 text-xs font-medium text-slate-600">

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

