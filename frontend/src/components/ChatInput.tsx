import React, { useRef, useEffect, useState } from "react";
import {
  ArrowUp,
  Bot,
  Brain,
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
  onOpenMemories?: () => void;
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
  onOpenMemories,
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
              className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl bg-[#f1f5f9] border border-[#cbd5e1] text-xs text-[#0f172a] shadow-sm flex-shrink-0"
            >
              {file.type.startsWith("image/") ? (
                <ImageIcon className="w-3.5 h-3.5 text-[#0284c7]" />
              ) : (
                <FileText className="w-3.5 h-3.5 text-amber-600" />
              )}
              <span className="max-w-[130px] truncate">{file.name}</span>
              <button
                type="button"
                onClick={() => removeFile(idx)}
                className="text-slate-400 hover:text-slate-700 transition-colors ml-0.5"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Floating Stitch Chat Input Card (Crisp White with High-Contrast Border) */}
      <div className="relative rounded-2xl bg-white border border-[#cbd5e1] shadow-lg focus-within:border-[#0284c7] focus-within:ring-2 focus-within:ring-[#0284c7]/20 transition-all p-3 sm:p-4">
        {/* Top Textarea with Sparkle */}
        <div className="flex items-start gap-2.5">
          <Sparkles className="w-4 h-4 text-[#0284c7] mt-1 flex-shrink-0" />
          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="How can I help you today?"
            className="w-full max-h-40 resize-none bg-transparent text-sm sm:text-base text-[#0f172a] placeholder:text-slate-400 focus:outline-none font-sans leading-relaxed pt-0.5 font-medium"
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

        {/* Bottom Controls Bar (Stitch Layout) */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2.5 border-t border-[#e2e8f0] mt-2">
          {/* Left Controls Group with High-Contrast Pills */}
          <div className="flex items-center gap-1.5 flex-wrap">
            {/* Paperclip Attach File Button */}
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center justify-center w-7 h-7 rounded-full bg-[#f1f5f9] hover:bg-[#e2e8f0] text-slate-700 hover:text-[#0f172a] transition-colors border border-[#cbd5e1]"
              title="Attach document, spreadsheet, or image"
            >
              <Paperclip className="w-3.5 h-3.5" />
            </button>

            {/* Tools Dropdown Button with Sky Blue Accents */}
            <div className="relative">
              <button
                type="button"
                onClick={() => {
                  setShowToolsDropdown(!showToolsDropdown);
                  setShowModelDropdown(false);
                }}
                className={cn(
                  "flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold transition-all border",
                  showToolsDropdown || isCanvasOpen
                    ? "bg-[#f0f9ff] text-[#0284c7] border-[#bae6fd]"
                    : "bg-[#f1f5f9] text-slate-700 border-[#cbd5e1] hover:bg-[#e2e8f0]"
                )}
                title="Tools & Browser Automation"
              >
                <Wrench className="w-3.5 h-3.5 text-[#0284c7]" />
                <span>Tools</span>
                <ChevronDown className="w-3.5 h-3.5 opacity-70" />
              </button>

              {/* Tools Dropdown Menu */}
              {showToolsDropdown && (
                <div className="absolute left-0 bottom-full mb-2 w-56 rounded-2xl bg-white border border-[#cbd5e1] shadow-2xl p-2 z-50 animate-in fade-in slide-in-from-bottom-2 text-[#0f172a]">
                  <div className="text-[10px] font-mono text-slate-500 uppercase px-2 py-1 tracking-wider">
                    Execution Tools
                  </div>
                  <button
                    type="button"
                    onClick={() => {
                      onToggleCanvas();
                      setShowToolsDropdown(false);
                    }}
                    className="flex items-center justify-between w-full px-2.5 py-1.5 rounded-xl text-xs text-slate-800 hover:bg-[#f1f5f9] transition-colors"
                  >
                    <span className="flex items-center gap-2">
                      <Layout className="w-3.5 h-3.5 text-[#0284c7]" />
                      <span>WebRTC Canvas</span>
                    </span>
                    <span
                      className={`flex items-center gap-1 text-[9px] font-mono px-1.5 py-0.5 rounded ${
                        isCanvasOpen ? "bg-sky-50 text-[#0284c7] border border-sky-200" : "text-slate-400"
                      }`}
                    >
                      {isStreamConnected && (
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                      )}
                      <span>{isCanvasOpen ? "OPEN" : "OFF"}</span>
                    </span>
                  </button>

                  <div className="h-px bg-slate-200 my-1" />

                  <div className="text-[10px] font-mono text-slate-500 uppercase px-2 py-1 tracking-wider">
                    Autonomous Capabilities
                  </div>
                  <div className="px-2.5 py-1 text-[11px] text-slate-600 leading-snug">
                    OpenBot Browser Screencast, Forensic Ledger CPA, Shell Sandbox, & Graph RAG.
                  </div>
                </div>
              )}
            </div>

            {/* Solo Agent vs Swarm Toggle */}
            <button
              type="button"
              onClick={() => onChangeMode(operationMode === "DIRECT" ? "SWARM" : "DIRECT")}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-all border",
                operationMode === "SWARM"
                  ? "bg-[#f0f9ff] text-[#0284c7] border-[#bae6fd] shadow-sm font-semibold"
                  : "bg-[#f1f5f9] text-slate-700 border-[#cbd5e1] hover:bg-[#e2e8f0]"
              )}
              title={
                operationMode === "SWARM"
                  ? "Swarm Mode Active (6 Specialized Autonomous Bots)"
                  : "Solo Agent Mode Active (Fast Single-Turn Execution)"
              }
            >
              <Bot
                className={cn(
                  "w-3.5 h-3.5",
                  operationMode === "SWARM" ? "text-[#0284c7]" : "text-slate-600"
                )}
              />
              <span>{operationMode === "SWARM" ? "Swarm (6 Bots)" : "Solo Agent"}</span>
            </button>

            {/* Prompt Optimizer On/Off Toggle */}
            <button
              type="button"
              onClick={onToggleOptimizePrompt}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-all border",
                optimizePrompt
                  ? "bg-[#f0f9ff] text-[#0284c7] border-[#bae6fd] shadow-sm font-semibold"
                  : "bg-[#f1f5f9] text-slate-700 border-[#cbd5e1] hover:bg-[#e2e8f0]"
              )}
              title="Toggle Ultron Prompt Optimizer (Enhances input clarity & tool adherence)"
            >
              <Zap
                className={cn(
                  "w-3.5 h-3.5",
                  optimizePrompt ? "text-[#0284c7]" : "text-slate-500"
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
                  "flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-all border",
                  showModelDropdown
                    ? "bg-[#f0f9ff] text-[#0284c7] border-[#bae6fd]"
                    : "bg-[#f1f5f9] text-slate-700 border-[#cbd5e1] hover:bg-[#e2e8f0]"
                )}
                title="Shift Active LLM Inference Engine"
              >
                <Cpu className="w-3.5 h-3.5 text-[#0284c7]" />
                <span className="max-w-[85px] truncate font-semibold text-[#0f172a]">{currentModelObj.name}</span>
                <ChevronDown className="w-3.5 h-3.5 opacity-60" />
              </button>

              {/* LLM Shift Dropdown Menu */}
              {showModelDropdown && (
                <div className="absolute left-0 bottom-full mb-2 w-64 rounded-2xl bg-white border border-[#cbd5e1] shadow-2xl p-2 z-50 animate-in fade-in slide-in-from-bottom-2 text-[#0f172a]">
                  <div className="text-[10px] font-mono text-slate-500 uppercase px-2.5 py-1 tracking-wider">
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
                          ? "bg-sky-50 border border-sky-200"
                          : "hover:bg-[#f1f5f9] border border-transparent"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-[#0f172a]">
                          {model.name}
                        </span>
                        <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-100 text-[#0284c7]">
                          {model.badge}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-500 mt-0.5 leading-snug line-clamp-1">
                        {model.tagline}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* Skills Button with Sky Blue Accent */}
            <button
              type="button"
              onClick={onOpenSkills}
              className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-[#f0f9ff] hover:bg-[#e0f2fe] text-[#0284c7] border border-[#bae6fd] transition-all"
              title="Open Ultron Skills Matrix (View & Install Skills)"
            >
              <Sparkles className="w-3.5 h-3.5 text-[#0284c7]" />
              <span>Skills</span>
            </button>

            {/* Memories Button with Sky Blue Accent */}
            {onOpenMemories && (
              <button
                type="button"
                onClick={onOpenMemories}
                className="flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-[#f0f9ff] hover:bg-[#e0f2fe] text-[#0284c7] border border-[#bae6fd] transition-all"
                title="Open Ultron Vector Memories (Long-Term Knowledge)"
              >
                <Brain className="w-3.5 h-3.5 text-[#0284c7]" />
                <span>Memories</span>
              </button>
            )}
          </div>

          {/* Right Controls: Voice & High-Contrast Black Send Button */}
          <div className="flex items-center gap-2">
            {/* Voice Microphone Pill */}
            <button
              type="button"
              onClick={handleToggleVoice}
              className={cn(
                "flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-all border",
                isRecording
                  ? "bg-rose-50 text-rose-600 border-rose-300 animate-pulse font-semibold"
                  : "bg-[#f1f5f9] text-slate-700 border-[#cbd5e1] hover:bg-[#e2e8f0]"
              )}
              title="Voice Input"
            >
              {isRecording ? (
                <MicOff className="w-3.5 h-3.5 text-rose-500" />
              ) : (
                <Mic className="w-3.5 h-3.5 text-slate-600" />
              )}
              <span>Voice</span>
            </button>

            {/* High-Contrast Send Button (Dark background with white arrow) */}
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
                "flex items-center justify-center w-8 h-8 rounded-full font-bold transition-all shadow-md flex-shrink-0",
                (value.trim() || attachedFiles.length > 0) && !isLoading
                  ? "bg-[#0f172a] text-white hover:bg-black hover:scale-105 shadow-md"
                  : "bg-slate-200 text-slate-400 cursor-not-allowed"
              )}
              title="Send Prompt"
            >
              {isLoading ? (
                <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <ArrowUp className="w-4 h-4 stroke-[3]" />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

