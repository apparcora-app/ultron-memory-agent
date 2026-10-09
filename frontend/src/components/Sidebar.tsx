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
} from "lucide-react";
import { OrbAvatar } from "./OrbAvatar";
import type { ChatSessionItem } from "../types/chat";
import { cn } from "../lib/utils";

interface SidebarProps {
  sessions: ChatSessionItem[];
  currentSessionId: string;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onDeleteSession?: (sessionId: string) => void;
  onSelectFeature?: (feature: string) => void;
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
  isCollapsed,
  onToggleCollapse,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [showSearch, setShowSearch] = useState(false);

  const FEATURES = [
    { id: "images", label: "Images", icon: ImageIcon, prompt: "Generate high-definition imagery and analyze visual assets." },
    { id: "videos", label: "Videos", icon: Video, prompt: "Create cinematic video generation scripts and production storyboards." },
    { id: "codex", label: "Codex", icon: Code2, prompt: "Open Codex engineering mode: review, refactor, and write clean production code." },
    { id: "apps", label: "Apps", icon: LayoutGrid, prompt: "Explore and orchestrate full-stack applications and local tool bridges." },
    { id: "projects", label: "Projects", icon: FolderKanban, prompt: "Manage multi-step project initiatives, goal DAGs, and knowledge graphs." },
  ];

  const filteredSessions = sessions.filter((s) =>
    (s.title || "Untitled Directive").toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <aside
      className={cn(
        "relative flex flex-col h-full bg-[#0f1217] border-r border-[#1e232d] transition-all duration-300 z-30 select-none",
        isCollapsed ? "w-16" : "w-64"
      )}
    >
      {/* ── Brand Header (Syntrix Style) ── */}
      <div className="flex items-center justify-between p-4 border-b border-[#1e232d]">
        {!isCollapsed ? (
          <div className="flex items-center gap-2.5">
            <OrbAvatar size={28} glow={false} />
            <span className="font-sans text-base font-bold tracking-tight text-white">
              Ultron
            </span>
          </div>
        ) : (
          <div className="w-full flex justify-center">
            <OrbAvatar size={28} glow={false} />
          </div>
        )}

        <div className="flex items-center gap-1">
          {!isCollapsed && (
            <button
              onClick={() => setShowSearch(!showSearch)}
              className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-[#1a1f29] transition-colors"
              title="Search Sessions"
            >
              <Search className="w-4 h-4" />
            </button>
          )}

          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-[#1a1f29] transition-colors"
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
            className="w-full px-3 py-1.5 rounded-xl bg-[#161a22] border border-white/10 text-xs text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-cyan-500/50"
          />
        </div>
      )}

      {/* ── New Chat Glowing Pill Button ── */}
      <div className="p-3">
        <button
          onClick={onNewSession}
          className={cn(
            "flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded-full bg-[#181d26] border border-[#2b3342] text-zinc-100 hover:border-cyan-500/60 hover:text-cyan-300 hover:bg-[#1f2633] transition-all text-xs font-semibold shadow-[0_0_12px_rgba(0,0,0,0.4)] group",
            isCollapsed && "px-2"
          )}
        >
          <div className="flex items-center justify-center w-4 h-4 rounded-full bg-cyan-500/20 text-cyan-400 group-hover:rotate-90 transition-transform">
            <Plus className="w-3 h-3 stroke-[3]" />
          </div>
          {!isCollapsed && <span>New Chat</span>}
        </button>
      </div>

      {/* ── FEATURES Section (Exact from Syntrix) ── */}
      {!isCollapsed && (
        <div className="px-3 py-2 space-y-1">
          <div className="px-2 mb-1.5 text-[10px] font-semibold text-zinc-500 uppercase tracking-widest">
            FEATURES
          </div>
          {FEATURES.map((feat) => {
            const Icon = feat.icon;
            return (
              <button
                key={feat.id}
                onClick={() => onSelectFeature && onSelectFeature(feat.prompt)}
                className="flex items-center gap-3 w-full px-3 py-2 rounded-xl text-xs text-zinc-300 hover:text-white hover:bg-[#1a202c] transition-colors text-left"
              >
                <Icon className="w-4 h-4 text-zinc-400" />
                <span>{feat.label}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* ── Separator ── */}
      {!isCollapsed && <div className="h-px bg-[#1e232d] mx-3 my-1" />}

      {/* ── YOUR CHATS Section (Exact from Syntrix) ── */}
      <div className="flex-1 overflow-y-auto px-2 py-2 space-y-1">
        {!isCollapsed && (
          <div className="px-3 mb-2 flex items-center justify-between text-[10px] font-semibold text-zinc-500 uppercase tracking-widest">
            <span>YOUR CHATS</span>
            <span>{filteredSessions.length}</span>
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
                  ? "bg-[#1d2330] text-cyan-300 font-medium border border-cyan-500/30 shadow-[0_0_10px_rgba(0,240,255,0.15)]"
                  : "text-zinc-400 hover:bg-[#161a22] hover:text-zinc-200 border border-transparent"
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
                    isActive ? "text-cyan-400" : "text-zinc-500 group-hover:text-zinc-300"
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

      {/* ── User Profile Footer (Replaces obsolete Upgrade Card) ── */}
      <div className="p-3 border-t border-[#1e232d] bg-[#0d0f14]">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-8 h-8 rounded-full bg-gradient-to-tr from-cyan-600 to-emerald-500 text-white font-bold text-xs shadow-[0_0_10px_rgba(0,240,255,0.3)]">
            H
            <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-emerald-400 ring-2 ring-[#0d0f14]" />
          </div>
          {!isCollapsed && (
            <div className="overflow-hidden">
              <p className="text-xs font-semibold text-zinc-200 truncate">
                Hanzla Rehman
              </p>
              <p className="text-[10px] text-zinc-500 truncate">
                Ultron Core • Lvl 5
              </p>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
