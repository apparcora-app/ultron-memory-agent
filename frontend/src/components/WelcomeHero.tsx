import React from "react";
import {
  Brain,
  Network,
  Terminal,
} from "lucide-react";
import { OrbAvatar } from "./OrbAvatar";
import { ChatInput } from "./ChatInput";

interface WelcomeHeroProps {
  inputVal: string;
  onChangeInput: (val: string) => void;
  onSend: (files?: File[]) => void;
  isLoading: boolean;
  isCanvasOpen: boolean;
  onToggleCanvas: () => void;
  isStreamConnected: boolean;
  operationMode: "DIRECT" | "SWARM";
  onChangeMode: (mode: "DIRECT" | "SWARM") => void;
  selectedModel: string;
  onChangeModel: (modelId: string) => void;
  optimizePrompt: boolean;
  onToggleOptimizePrompt: () => void;
  onOpenSkills: () => void;
  onOpenMemories?: () => void;
  onSelectPrompt: (prompt: string) => void;
}

export const WelcomeHero: React.FC<WelcomeHeroProps> = ({
  inputVal,
  onChangeInput,
  onSend,
  isLoading,
  isCanvasOpen,
  onToggleCanvas,
  isStreamConnected,
  operationMode,
  onChangeMode,
  selectedModel,
  onChangeModel,
  optimizePrompt,
  onToggleOptimizePrompt,
  onOpenSkills,
  onOpenMemories,
  onSelectPrompt,
}) => {
  const SUGGESTED_DIRECTIVES = [
    {
      label: "System Status & Memory Audit",
      prompt: "Inspect system metrics, query Mem0 vectors, and report active memory bank status.",
      icon: Brain,
    },
    {
      label: "Sandbox Financial Verification",
      prompt: "Execute sandbox accounting engine to reconcile bank transactions against the ledger.",
      icon: Terminal,
    },
    {
      label: "Swarm Research Dispatch",
      prompt: "Dispatch the 6-agent swarm mesh to analyze system architecture and test coverage.",
      icon: Network,
    },
  ];

  return (
    <div className="flex flex-col items-center justify-center min-h-[82vh] px-4 py-8 max-w-4xl mx-auto w-full text-center relative z-20">
      {/* 3D Iridescent Glowing Sphere Avatar */}
      <div className="mb-5 transform hover:scale-105 transition-transform duration-500">
        <OrbAvatar size={100} />
      </div>

      {/* Typography — Confident Operator Command Voice */}
      <div className="mb-7 space-y-2">
        <h2 className="text-xs sm:text-sm font-semibold tracking-[0.25em] text-[#0284c7] uppercase font-mono">
          AUTONOMOUS COGNITIVE SYSTEM
        </h2>
        <h1 className="text-2xl sm:text-4xl font-bold text-theme-main tracking-tight">
          Ultron Operational Command
        </h1>
        <p className="text-xs sm:text-sm text-theme-muted max-w-xl mx-auto leading-relaxed">
          Persistent dual memory, multi-agent swarm orchestration, and isolated computer execution.
        </p>
      </div>

      {/* Centered Floating Chat Input Card */}
      <div className="w-full mb-6">
        <ChatInput
          value={inputVal}
          onChange={onChangeInput}
          onSend={onSend}
          isLoading={isLoading}
          isCanvasOpen={isCanvasOpen}
          onToggleCanvas={onToggleCanvas}
          isStreamConnected={isStreamConnected}
          operationMode={operationMode}
          onChangeMode={onChangeMode}
          selectedModel={selectedModel}
          onChangeModel={onChangeModel}
          optimizePrompt={optimizePrompt}
          onToggleOptimizePrompt={onToggleOptimizePrompt}
          onOpenSkills={onOpenSkills}
          onOpenMemories={onOpenMemories}
        />
      </div>

      {/* ── Subsystem Live Telemetry Strip (DESIGN.md Approved) ── */}
      <div className="flex flex-wrap items-center justify-center gap-2 max-w-3xl mx-auto mb-6">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-theme-panel border border-theme-border text-xs font-mono text-theme-muted shadow-xs transition-colors">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-theme-main font-semibold">Memory Bank:</span>
          <span>Mem0 + Qdrant Active</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-theme-panel border border-theme-border text-xs font-mono text-theme-muted shadow-xs transition-colors">
          <span className="w-2 h-2 rounded-full bg-purple-500" />
          <span className="text-theme-main font-semibold">Swarm Mesh:</span>
          <span>6 Agents Standby</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-theme-panel border border-theme-border text-xs font-mono text-theme-muted shadow-xs transition-colors">
          <span className="w-2 h-2 rounded-full bg-sky-500" />
          <span className="text-theme-main font-semibold">AST Sandbox:</span>
          <span>Docker / E2B Armed</span>
        </div>
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-theme-panel border border-theme-border text-xs font-mono text-theme-muted shadow-xs transition-colors">
          <span className="w-2 h-2 rounded-full bg-amber-500" />
          <span className="text-theme-main font-semibold">Ledger Gate:</span>
          <span>Physical Ground Truth</span>
        </div>
      </div>

      {/* ── Authentic Directive Chips (Clean Operator Shortcuts) ── */}
      <div className="flex flex-wrap items-center justify-center gap-2 max-w-2xl mx-auto text-left">
        {SUGGESTED_DIRECTIVES.map((item, idx) => {
          const IconComponent = item.icon;
          return (
            <button
              key={idx}
              type="button"
              onClick={() => onSelectPrompt(item.prompt)}
              className="flex items-center gap-2 px-3 py-2 rounded-xl bg-theme-panel/80 hover:bg-theme-card-hover border border-theme-border hover:border-theme-focus text-xs text-theme-muted hover:text-theme-main transition-all shadow-xs"
            >
              <IconComponent className="w-3.5 h-3.5 text-[#0284c7]" />
              <span className="font-medium">{item.label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
};

