import React, { useRef, useEffect, useState } from "react";
import {
  ArrowUp,
  Bot,
  ChevronDown,
  Cpu,
  FileText,
  Image as ImageIcon,
  Mic,
  MicOff,
  Paperclip,
  Sparkles,
  Wrench,
  X,
  Zap,
  Layout,
} from "lucide-react";
import { cn } from "../lib/utils";

export interface LLMOption {
  id: string;
  name: string;
  badge: string;
  tagline: string;
}

export const DEFAULT_LLM_MODELS: LLMOption[] = [
  {
    id: "auto",
    name: "Auto-Route",
    badge: "Smart",
    tagline: "Dynamically selects optimal model based on query complexity",
  },
];

interface ChatInputProps {
  value: string;
  onChange: (val: string) => void;
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
}

export const ChatInput: React.FC<ChatInputProps> = ({
  value,
  onChange,
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
}) => {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [showModelDropdown, setShowModelDropdown] = useState<boolean>(false);
  const [showToolsDropdown, setShowToolsDropdown] = useState<boolean>(false);
  const [isRecording, setIsRecording] = useState<boolean>(false);
  const [models, setModels] = useState<LLMOption[]>(DEFAULT_LLM_MODELS);

  // Fetch dynamic providers from backend on mount
  useEffect(() => {
    fetch("/api/providers")
      .then((res) => res.json())
      .then((data) => {
        if (data && data.providers && data.providers.length > 0) {
          setModels([DEFAULT_LLM_MODELS[0], ...data.providers]);
        }
      })
      .catch((err) => console.error("Failed to load providers:", err));
  }, []);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if ((value.trim() || attachedFiles.length > 0) && !isLoading) {
        onSend(attachedFiles);
        setAttachedFiles([]);
      }
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const newFiles = Array.from(e.target.files);
      setAttachedFiles((prev) => [...prev, ...newFiles]);
    }
  };

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const currentModelObj =
    models.find((m) => m.id === selectedModel) || models[0];

  // Speech Recognition hook fallback
  const handleToggleVoice = () => {
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
      alert("Voice speech recognition is not supported in this browser.");
      return;
    }

    if (isRecording) {
      setIsRecording(false);
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onstart = () => setIsRecording(true);
    recognition.onresult = (event: any) => {
      const transcript = event.results[0][0].transcript;
      onChange(value ? `${value} ${transcript}` : transcript);
      setIsRecording(false);
    };
    recognition.onerror = () => setIsRecording(false);
    recognition.onend = () => setIsRecording(false);

    try {
      recognition.start();
    } catch {
      setIsRecording(false);
    }
  };

  return (
    <div className="w-full max-w-3xl mx-auto px-4 pb-4 select-none relative z-30">
      {/* Attached Files Carousel / Preview */}
      {attachedFiles.length > 0 && (
        <div className="flex items-center gap-2 mb-2 px-2 overflow-x-auto py-1">
          {attachedFiles.map((file, idx) => (
            <div
              key={idx}
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-[#1c222e] border border-white/10 text-xs text-zinc-300 shadow-md flex-shrink-0"
            >
              {file.type.startsWith("image/") ? (
                <ImageIcon className="w-3.5 h-3.5 text-cyan-400" />
              ) : (
                <FileText className="w-3.5 h-3.5 text-amber-400" />
              )}
              <span className="max-w-[130px] truncate">{file.name}</span>
              <button
                type="button"
                onClick={() => removeFile(idx)}
                className="text-zinc-500 hover:text-white transition-colors ml-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Floating Syntrix Chat Input Card */}
      <div className="relative rounded-2xl sm:rounded-3xl bg-[#181c24] border border-[#272e3b] shadow-[0_15px_45px_rgba(0,0,0,0.6)] backdrop-blur-xl focus-within:border-cyan-500/50 transition-all p-3 sm:p-4">
        {/* Top Textarea with Sparkle */}
        <div className="flex items-start gap-2.5">
          <Sparkles className="w-4 h-4 text-cyan-400 mt-1 flex-shrink-0 animate-pulse" />
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything..."
            className="w-full max-h-40 resize-none bg-transparent text-sm sm:text-base text-zinc-100 placeholder:text-zinc-500 focus:outline-none font-sans leading-relaxed pt-0.5"
          />
        </div>

        {/* Hidden File Input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={handleFileChange}
          accept="image/*,.pdf,.csv,.xlsx,.xls,.docx,.py,.js,.ts,.json,.txt"
        />

        {/* Bottom Controls Bar (Syntrix Layout) */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-white/5 mt-2">
          {/* Left Controls Group */}
          <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
            {/* '+' Attach File Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center justify-center w-7 h-7 sm:w-8 sm:h-8 rounded-full bg-[#202632] hover:bg-[#28303f] text-zinc-300 hover:text-white transition-colors border border-white/5"
              title="Attach document, spreadsheet, or image"
            >
              <Paperclip className="w-3.5 h-3.5 sm:w-4 sm:h-4" />
            </button>

            {/* Tools Dropdown Button */}
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setShowToolsDropdown(!showToolsDropdown);
                  setShowModelDropdown(false);
                }}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs font-medium transition-all border",
                  showToolsDropdown || isCanvasOpen
                    ? "bg-[#252d3c] text-cyan-300 border-cyan-500/40"
                    : "bg-[#202632] text-zinc-300 border-white/5 hover:bg-[#28303f]"
                )}
                title="Tools & Browser Automation"
              >
                <Wrench className="w-3 h-3 text-cyan-400" />
                <span>Tools</span>
                <ChevronDown className="w-3 h-3 opacity-60" />
              </button>

              {/* Tools Dropdown Menu */}
              {showToolsDropdown && (
                <div className="absolute left-0 bottom-full mb-2 w-56 rounded-2xl bg-[#1c222e] border border-white/10 shadow-2xl p-2 z-50 animate-in fade-in slide-in-from-bottom-2">
                  <div className="text-[10px] font-mono text-zinc-400 uppercase px-2 py-1 tracking-wider">
                    Execution Tools
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      onToggleCanvas();
                      setShowToolsDropdown(false);
                    }}
                    className="flex items-center justify-between w-full px-2.5 py-1.5 rounded-xl text-xs text-zinc-200 hover:bg-white/5 transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <Layout className="w-3.5 h-3.5 text-cyan-400" />
                      <span>WebRTC Canvas</span>
                    </span>
                    <span
                      className={`flex items-center gap-1 text-[9px] font-mono px-1.5 py-0.5 rounded ${
                        isCanvasOpen ? "bg-cyan-500/20 text-cyan-300" : "text-zinc-500"
                      }`}
                    >
                      {isStreamConnected && (
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                      )}
                      <span>{isCanvasOpen ? "OPEN" : "OFF"}</span>
                    </span>
                  </button>

                  <div className="h-px bg-white/5 my-1" />

                  <div className="text-[10px] font-mono text-zinc-400 uppercase px-2 py-1 tracking-wider">
                    Autonomous Capabilities
                  </div>
                  <div className="px-2.5 py-1 text-[11px] text-zinc-400 leading-snug">
                    OpenBot Browser Screencast, Forensic Ledger CPA, Shell Sandbox, & Graph RAG.
                  </div>
                </div>
              )}
            </div>

            {/* Solo Agent vs Swarm Agent Mode Toggle */}
            <button
              type="button"
              onClick={() => onChangeMode(operationMode === "DIRECT" ? "SWARM" : "DIRECT")}
              className={cn(
                "flex items-center gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs font-medium transition-all border",
                operationMode === "SWARM"
                  ? "bg-amber-500/15 text-amber-300 border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.2)]"
                  : "bg-[#202632] text-zinc-300 border-white/5 hover:bg-[#28303f]"
              )}
              title={
                operationMode === "SWARM"
                  ? "Swarm Mode Active (6 Specialized Autonomous Bots)"
                  : "Solo Agent Mode Active (Fast Single-Turn Execution)"
              }
            >
              <Bot
                className={cn(
                  "w-3 h-3",
                  operationMode === "SWARM" ? "text-amber-400" : "text-zinc-400"
                )}
              />
              <span>{operationMode === "SWARM" ? "Swarm (6 Bots)" : "Solo Agent"}</span>
            </button>

            {/* Prompt Optimizer On/Off Toggle */}
            <button
              type="button"
              onClick={onToggleOptimizePrompt}
              className={cn(
                "flex items-center gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs font-medium transition-all border",
                optimizePrompt
                  ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.2)]"
                  : "bg-[#202632] text-zinc-400 border-white/5 hover:bg-[#28303f] hover:text-zinc-300"
              )}
              title="Toggle Ultron Prompt Optimizer (Enhances input clarity & tool adherence)"
            >
              <Zap
                className={cn(
                  "w-3 h-3",
                  optimizePrompt ? "text-emerald-400" : "text-zinc-500"
                )}
              />
              <span>Opt: {optimizePrompt ? "ON" : "OFF"}</span>
            </button>

            {/* LLM Shift Dropdown Button */}
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setShowModelDropdown(!showModelDropdown);
                  setShowToolsDropdown(false);
                }}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs font-medium transition-all border",
                  showModelDropdown
                    ? "bg-[#252d3c] text-cyan-300 border-cyan-500/40"
                    : "bg-[#202632] text-zinc-300 border-white/5 hover:bg-[#28303f]"
                )}
                title="Shift Active LLM Inference Engine"
              >
                <Cpu className="w-3 h-3 text-cyan-400" />
                <span className="max-w-[95px] truncate">{currentModelObj.name}</span>
                <ChevronDown className="w-3 h-3 opacity-60" />
              </button>

              {/* LLM Shift Dropdown Menu */}
              {showModelDropdown && (
                <div className="absolute left-0 bottom-full mb-2 w-64 rounded-2xl bg-[#1c222e] border border-white/10 shadow-2xl p-2 z-50 animate-in fade-in slide-in-from-bottom-2">
                  <div className="text-[10px] font-mono text-zinc-400 uppercase px-2.5 py-1 tracking-wider">
                    LLM Engine Shift
                  </div>
                  {models.map((model) => (
                    <button
                      key={model.id}
                      type="button"
                      onClick={() => {
                        onChangeModel(model.id);
                        setShowModelDropdown(false);
                      }}
                      className={cn(
                        "flex flex-col w-full px-2.5 py-2 rounded-xl text-left transition-colors mb-0.5",
                        selectedModel === model.id
                          ? "bg-cyan-500/15 border border-cyan-500/30"
                          : "hover:bg-white/5 border border-transparent"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-zinc-100">
                          {model.name}
                        </span>
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-zinc-800 text-cyan-300">
                          {model.badge}
                        </span>
                      </div>
                      <span className="text-[10px] text-zinc-400 mt-0.5 leading-snug line-clamp-1">
                        {model.tagline}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Skills Button */}
            <button
              type="button"
              onClick={onOpenSkills}
              className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1 sm:py-1.5 rounded-full text-xs font-medium bg-[#202632] hover:bg-[#28303f] text-cyan-300 border border-cyan-500/20 hover:border-cyan-500/50 transition-all shadow-sm"
              title="Open Ultron Skills Matrix (View & Install Skills)"
            >
              <Sparkles className="w-3 h-3 text-cyan-400" />
              <span>Skills</span>
            </button>
          </div>

          {/* Right Controls: Voice & Circular Send Button */}
          <div className="flex items-center gap-2">
            {/* Voice Microphone Pill */}
            <button
              type="button"
              onClick={handleToggleVoice}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1 sm:py-1.5 rounded-full text-xs font-medium transition-all border",
                isRecording
                  ? "bg-rose-500/20 text-rose-300 border-rose-500 animate-pulse"
                  : "bg-[#202632] text-zinc-300 border-white/5 hover:bg-[#28303f] hover:text-white"
              )}
              title="Voice Input"
            >
              {isRecording ? (
                <MicOff className="w-3.5 h-3.5 text-rose-400" />
              ) : (
                <Mic className="w-3.5 h-3.5 text-zinc-400" />
              )}
              <span>Voice</span>
            </button>

            {/* Circular Send Button (White with black arrow as in Syntrix) */}
            <button
              type="button"
              onClick={() => {
                if ((value.trim() || attachedFiles.length > 0) && !isLoading) {
                  onSend(attachedFiles);
                  setAttachedFiles([]);
                }
              }}
              disabled={(!value.trim() && attachedFiles.length === 0) || isLoading}
              className={cn(
                "flex items-center justify-center w-8 h-8 sm:w-9 sm:h-9 rounded-full font-bold transition-all shadow-lg flex-shrink-0",
                (value.trim() || attachedFiles.length > 0) && !isLoading
                  ? "bg-white text-zinc-950 hover:bg-zinc-200 shadow-[0_0_15px_rgba(255,255,255,0.4)]"
                  : "bg-zinc-800 text-zinc-500 cursor-not-allowed"
              )}
              title="Send Prompt"
            >
              {isLoading ? (
                <div className="w-4 h-4 border-2 border-zinc-900 border-t-transparent rounded-full animate-spin" />
              ) : (
                <ArrowUp className="w-4 h-4 stroke-[2.5]" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
