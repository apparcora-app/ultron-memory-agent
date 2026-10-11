import React from "react";
import {
  ArrowUpRight,
  Code2,
  Globe,
  Video,
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
  onSelectPrompt,
}) => {
  const CAPABILITY_CARDS = [
    {
      title: "Image Generator",
      desc: "Turn ideas into stunning visuals in seconds.",
      icon: Globe,
      prompt: "Generate a high-resolution, futuristic conceptual visual for an autonomous AI command interface.",
    },
    {
      title: "Video Generator",
      desc: "Create cinematic videos from simple prompts.",
      icon: Video,
      prompt: "Generate a cinematic storyboard and script for an autonomous AI operations video showcase.",
    },
    {
      title: "Dev Assistant",
      desc: "Accelerate development with intelligent assistance.",
      icon: Code2,
      prompt: "Execute a shell command in your sandbox to inspect system metrics and verify live backend APIs.",
    },
  ];

  return (
    <div className="flex flex-col items-center justify-center min-h-[82vh] px-4 py-8 max-w-4xl mx-auto w-full text-center relative z-20">
      {/* 3D Iridescent Glowing Sphere Avatar */}
      <div className="mb-6 transform hover:scale-105 transition-transform duration-500">
        <OrbAvatar size={110} />
      </div>

      {/* Typography from Stitch Spec */}
      <div className="mb-8 space-y-2">
        <h2 className="text-xs sm:text-sm font-semibold tracking-[0.25em] text-[#0284c7] uppercase font-mono">
          AI COLLABORATIVE WORKSPACE
        </h2>
        <h1 className="text-2xl sm:text-4xl font-bold text-[#0f172a] tracking-tight">
          With What You Want To Work Today?
        </h1>
      </div>

      {/* Centered Floating Chat Input Card */}
      <div className="w-full mb-8">
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
        />
      </div>

      {/* 3 Stitch Capability Starter Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 w-full max-w-3xl text-left">
        {CAPABILITY_CARDS.map((card, idx) => {
          const IconComponent = card.icon;
          return (
            <button
              key={idx}
              type="button"
              onClick={() => onSelectPrompt(card.prompt)}
              className="group relative flex flex-col justify-between p-4 rounded-2xl bg-white border border-[#e2e8f0] hover:border-[#0284c7] hover:shadow-md transition-all duration-200 shadow-sm text-left"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#f1f5f9] text-slate-700 group-hover:text-[#0284c7] group-hover:bg-[#f0f9ff] transition-colors border border-[#e2e8f0]">
                  <IconComponent className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-slate-400 group-hover:text-[#0284c7] group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all" />
              </div>

              <div>
                <h3 className="text-sm font-bold text-[#0f172a] group-hover:text-[#0284c7] transition-colors mb-1">
                  {card.title}
                </h3>
                <p className="text-xs text-slate-500 leading-relaxed">
                  {card.desc}
                </p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

