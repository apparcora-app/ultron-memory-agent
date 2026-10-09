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

      {/* Typography from Syntrix Spec */}
      <div className="mb-8 space-y-1.5">
        <h2 className="text-xs sm:text-sm font-semibold tracking-[0.28em] text-zinc-300 uppercase font-mono">
          WELCOME BACK
        </h2>
        <h1 className="text-2xl sm:text-4xl font-bold text-white tracking-tight font-sans">
          Bring your ideas to life today
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

      {/* 3 Syntrix Capability Starter Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 w-full max-w-3xl text-left">
        {CAPABILITY_CARDS.map((card, idx) => {
          const IconComponent = card.icon;
          return (
            <button
              key={idx}
              type="button"
              onClick={() => onSelectPrompt(card.prompt)}
              className="group relative flex flex-col justify-between p-4 rounded-2xl bg-[#161a22] border border-[#232936] hover:border-cyan-500/40 hover:bg-[#1a202c] transition-all duration-200 shadow-lg text-left"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center justify-center w-8 h-8 rounded-full bg-[#202735] text-zinc-300 group-hover:text-cyan-300 group-hover:bg-[#253043] transition-colors border border-white/5">
                  <IconComponent className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-4 h-4 text-zinc-500 group-hover:text-cyan-400 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all" />
              </div>

              <div>
                <h3 className="text-sm font-semibold text-zinc-100 group-hover:text-cyan-300 transition-colors mb-1">
                  {card.title}
                </h3>
                <p className="text-xs text-zinc-400 leading-relaxed">
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
