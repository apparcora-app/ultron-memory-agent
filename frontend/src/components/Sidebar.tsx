import React, { useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Code2,
  FolderKanban,
  Image as ImageIcon,
  LayoutGrid,
  MessageSquare,
  Plus,
  Search,
  Trash2,
  Video,
  Brain,
} from "lucide-react";
import type { ChatSessionItem } from "../types/chat";
import { cn } from "../lib/utils";

interface SidebarProps {
  sessions: ChatSessionItem[];
  currentSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession?: (sessionId: string) => void;
  onSelectFeature?: (feature: string) => void;
  onOpenMemories?: () => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  onSelectFeature,
  onOpenMemories,
  isCollapsed,
  onToggleCollapse,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [showSearch, setShowSearch] = useState(false);

  const FEATURES = [
    { id: "memories", label: "Memories", icon: Brain, color: "text-[#38bdf8]", prompt: "" },
    { id: "images", label: "Images", icon: ImageIcon, color: "text-[#38bdf8]", prompt: "Generate high-definition imagery and analyze visual assets." },
    { id: "videos", label: "Videos", icon: Video, color: "text-[#c084fc]", prompt: "Create cinematic video generation scripts and production storyboards." },
    { id: "codex", label: "Codex", icon: Code2, color: "text-[#38bdf8]", prompt: "Open Codex engineering mode: review, refactor, and write clean production code." },
    { id: "apps", label: "Apps", icon: LayoutGrid, color: "text-[#38bdf8]", prompt: "Explore and orchestrate full-stack applications and local tool bridges." },
    { id: "projects", label: "Projects", icon: FolderKanban, color: "text-[#818cf8]", prompt: "Manage multi-step project initiatives, goal DAGs, and knowledge graphs." },
  ];

  const filteredSessions = sessions.filter((s) =>
    (s.title || "Untitled Directive").toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <aside
      className={cn(
        "relative flex flex-col h-full bg-[#0f0f11] border-r border-[#232328] transition-all duration-300 z-30 select-none shrink-0 text-zinc-100 dark-scrollbar",
        isCollapsed ? "w-16" : "w-64"
      )}
    >
      {/* ── Brand Header (Stitch Style) ── */}
      <div className="flex items-center justify-between p-4 border-b border-[#232328]">
        {!isCollapsed ? (
          <div className="flex items-center gap-2.5">
            {/* Mini Agent Orb with Sky Blue Theme */}
            <div className="w-7 h-7 relative flex items-center justify-center group/orb shrink-0">
              <div className="absolute -inset-1 rounded-full pointer-events-none border border-[#38bdf8]/50 opacity-80 animate-pulse" />
              <svg
                className="w-full h-full cursor-pointer transition-transform duration-300 group-hover/orb:scale-110 relative z-0 sidebar-orb-animated"
                viewBox="0 0 100 100"
              >
                <defs>
                  <radialGradient cx="35%" cy="30%" id="sidebarOrbBase" r="65%">
                    <stop offset="0%" stopColor="#ffffff" />
                    <stop offset="25%" stopColor="#38bdf8" />
                    <stop offset="60%" stopColor="#0284c7" />
                    <stop offset="100%" stopColor="#071926" />
                  </radialGradient>
                  <radialGradient cx="65%" cy="70%" id="sidebarOrbSwirl" r="60%">
                    <stop offset="0%" stopColor="#7dd3fc" stopOpacity="0.95" />
                    <stop offset="40%" stopColor="#0ea5e9" stopOpacity="0.85" />
                    <stop offset="100%" stopColor="#0c2338" stopOpacity="0.3" />
                  </radialGradient>
                </defs>
                <circle cx="50" cy="50" fill="url(#sidebarOrbBase)" r="45" />
                <circle cx="50" cy="50" fill="url(#sidebarOrbSwirl)" r="45" />
                <circle cx="36" cy="26" fill="#ffffff" opacity="0.9" r="4" />
                <circle cx="42" cy="22" fill="#38bdf8" opacity="0.95" r="1.5" />
              </svg>
            </div>
            <span className="font-sans text-base font-bold tracking-tight text-white flex items-center gap-1.5">
              Ultron
            </span>
          </div>
        ) : (
          <div className="w-full flex justify-center">
            <div className="w-7 h-7 relative flex items-center justify-center group/orb shrink-0">
              <div className="absolute -inset-1 rounded-full pointer-events-none border border-[#38bdf8]/50 opacity-80 animate-pulse" />
              <svg
                className="w-full h-full cursor-pointer transition-transform duration-300 group-hover/orb:scale-110 relative z-0 sidebar-orb-animated"
                viewBox="0 0 100 100"
              >
                <defs>
                  <radialGradient cx="35%" cy="30%" id="sidebarOrbBaseSmall" r="65%">
                    <stop offset="0%" stopColor="#ffffff" />
                    <stop offset="25%" stopColor="#38bdf8" />
                    <stop offset="60%" stopColor="#0284c7" />
                    <stop offset="100%" stopColor="#071926" />
                  </radialGradient>
                  <radialGradient cx="65%" cy="70%" id="sidebarOrbSwirlSmall" r="60%">
                    <stop offset="0%" stopColor="#7dd3fc" stopOpacity="0.95" />
                    <stop offset="40%" stopColor="#0ea5e9" stopOpacity="0.85" />
                    <stop offset="100%" stopColor="#0c2338" stopOpacity="0.3" />
                  </radialGradient>
                </defs>
                <circle cx="50" cy="50" fill="url(#sidebarOrbBaseSmall)" r="45" />
                <circle cx="50" cy="50" fill="url(#sidebarOrbSwirlSmall)" r="45" />
                <circle cx="36" cy="26" fill="#ffffff" opacity="0.9" r="4" />
                <circle cx="42" cy="22" fill="#38bdf8" opacity="0.95" r="1.5" />
              </svg>
            </div>
          </div>
        )}

        <div className="flex items-center gap-1">
          {!isCollapsed && (
            <button
              onClick={() => setShowSearch(!showSearch)}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-[#1c1c21] transition-colors"
              title="Search Sessions"
            >
              <Search className="w-4 h-4" />
            </button>
          )}

          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-[#1c1c21] transition-colors"
            title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          >
            {isCollapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* ── Search Input (Toggled) ── */}
      {!isCollapsed && showSearch && (
        <div className="px-3 pt-2">
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search chats..."
            className="w-full px-3 py-1.5 rounded-xl bg-[#18181c] border border-[#2d2d35] text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-[#38bdf8]/70"
          />
        </div>
      )}

      {/* ── New Chat Pill Button ── */}
      <div className="p-3">
        <button
          onClick={onNewSession}
          className={cn(
            "flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-full bg-[#18181c] border border-[#2d2d35] text-zinc-100 hover:border-[#38bdf8]/70 hover:text-[#38bdf8] hover:bg-[#202026] transition-all text-xs font-semibold shadow-sm group",
            isCollapsed && "px-2"
          )}
        >
          <div className="flex items-center justify-center w-4 h-4 rounded-full bg-[#0284c7]/20 text-[#38bdf8] group-hover:rotate-90 transition-transform">
            <Plus className="w-3 h-3 stroke-[3]" />
          </div>
          {!isCollapsed && <span>New Chat</span>}
        </button>
      </div>

      {/* ── FEATURES Section ── */}
      {!isCollapsed && (
        <div className="px-3 py-2 space-y-1">
          <div className="px-2 mb-1.5 text-[10px] font-semibold text-zinc-400 uppercase tracking-widest font-mono">
            FEATURES
          </div>
          {FEATURES.map((feat) => {
            const Icon = feat.icon;
            return (
              <button
                key={feat.id}
                onClick={() => (feat.id === "memories" ? onOpenMemories?.() : onSelectFeature?.(feat.prompt))}
                className="flex items-center gap-3 w-full px-3 py-2 rounded-xl text-xs text-zinc-300 hover:text-white hover:bg-[#1a1a20] transition-colors text-left"
              >
                <Icon className={cn("w-4 h-4", feat.color)} />
                <span>{feat.label}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* ── Separator ── */}
      {!isCollapsed && <div className="h-px bg-[#232328] mx-3 my-1" />}

      {/* ── YOUR CHATS Section ── */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1 dark-scrollbar">
        {!isCollapsed && (
          <div className="px-3 mb-2 flex items-center justify-between text-[10px] font-semibold text-zinc-400 uppercase tracking-widest font-mono">
            <span>YOUR CHATS</span>
            <span className="text-zinc-500">{filteredSessions.length}</span>
          </div>
        )}

        {filteredSessions.map((sess) => {
          const isActive = sess.id === currentSessionId;
          return (
            <div
              key={sess.id}
              className={cn(
                "group relative flex items-center justify-between w-full px-3 py-2 rounded-xl text-left text-xs transition-all",
                isActive
                  ? "bg-[#0d2238] text-[#38bdf8] font-medium border border-[#0ea5e9]/50 shadow-[0_0_12px_rgba(14,165,233,0.15)]"
                  : "text-zinc-400 hover:bg-[#18181c] hover:text-zinc-200 border border-transparent"
              )}
            >
              <button
                type="button"
                onClick={() => onSelectSession(sess.id)}
                className="flex items-center gap-2.5 flex-1 truncate text-left"
                title={sess.title}
              >
                <MessageSquare
                  className={cn(
                    "w-3.5 h-3.5 flex-shrink-0",
                    isActive ? "text-[#38bdf8]" : "text-zinc-500 group-hover:text-zinc-300"
                  )}
                />
                {!isCollapsed && (
                  <span className="truncate flex-1">
                    {sess.title || "Untitled Directive"}
                  </span>
                )}
              </button>

              {!isCollapsed && onDeleteSession && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDeleteSession(sess.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 p-1 text-zinc-500 hover:text-rose-400 transition-opacity ml-1"
                  title="Delete Session"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* ── User Profile Footer ── */}
      <div className="p-3 border-t border-[#232328] bg-[#0f0f11]">
        <div className="flex items-center justify-between p-2 rounded-2xl bg-[#16161a] border border-[#2a2a30]">
          <div className="flex items-center gap-2.5 overflow-hidden">
            <div className="relative flex items-center justify-center w-8 h-8 rounded-full bg-[#0284c7] text-white font-bold text-xs shadow-sm shrink-0">
              H
              <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-[#38bdf8] ring-2 ring-[#16161a] shadow-[0_0_6px_#38bdf8]" />
            </div>
            {!isCollapsed && (
              <div className="overflow-hidden">
                <p className="text-xs font-semibold text-white truncate">
                  Hanzla Rehman
                </p>
                <p className="text-[10px] text-zinc-400 truncate">
                  Ultron Core • Lvl 5
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
};

