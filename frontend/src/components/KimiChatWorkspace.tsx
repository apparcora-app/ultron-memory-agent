/**
 * KimiChatWorkspace.tsx — Syntrix-Style Autonomous AI Workspace with Dynamic WebRTC Canvas.
 *
 * Implements the Syntrix interface:
 *   - Dark aesthetic (Obsidian Cyber) or Crisp Laboratory theme with dynamic CSS variables.
 *   - 3D glowing iridescent sphere avatar in Welcome Hero.
 *   - Centered floating ChatInput card with:
 *       • Solo Agent vs Swarm Agent toggle
 *       • Prompt Optimizer on/off toggle
 *       • LLM Shift dropdown in chat bar
 *       • Skills Matrix modal launcher
 *       • Voice recognition & circular Send button
 *   - Telemetry strip replacing legacy AI slop cards.
 *   - Collapsible left sidebar with off-canvas mobile drawer and 5-state empty handling.
 *   - Top bar with theme toggle (Sun/Moon), version pill, Dashboard, and mobile hamburger.
 *   - Resizable 50/50 WebRTC Browser screencast canvas with mobile tab toggling.
 *   - Global keyboard shortcuts: Ctrl+K / Cmd+K (new chat) and Escape (dismiss).
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import { BrainCircuit } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { WelcomeHero } from "./WelcomeHero";
import { ChatMessageItem } from "./ChatMessageItem";
import { ChatInput } from "./ChatInput";
import { CanvasPane } from "./CanvasPane";
import { SkillsModal } from "./SkillsModal";
import { MemoriesModal } from "./MemoriesModal";
import { useWebRTCStream } from "../hooks/useWebRTCStream";
import type { ChatMessage, ChatSessionItem } from "../types/chat";
import { cn } from "../lib/utils";

export const KimiChatWorkspace: React.FC = () => {
  const [sessions, setSessions] = useState<ChatSessionItem[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string>("");
  const [sessionTitle, setSessionTitle] = useState<string>("New Directive");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputVal, setInputVal] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);
  const [isCanvasOpen, setIsCanvasOpen] = useState<boolean>(false);
  const [mobileViewTab, setMobileViewTab] = useState<"chat" | "canvas">("chat");
  const [operationMode, setOperationMode] = useState<"DIRECT" | "SWARM">("DIRECT");
  const [selectedModel, setSelectedModel] = useState<string>("auto");
  const [optimizePrompt, setOptimizePrompt] = useState<boolean>(false);
  const [isSkillsModalOpen, setIsSkillsModalOpen] = useState<boolean>(false);
  const [isMemoriesModalOpen, setIsMemoriesModalOpen] = useState<boolean>(false);
  const [splitRatio, setSplitRatio] = useState<number>(50); // 50% chat, 50% canvas
  const [isDragging, setIsDragging] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Initialize WebRTC hook
  const {
    mediaStream,
    isConnected,
    isConnecting,
    error: rtcError,
    agentCursor,
    sendControlEvent,
    reconnect,
  } = useWebRTCStream("", {
    sessionId: currentSessionId || "default",
    autoConnect: true,
    fps: 60,
    pixelFormat: "yuv420p",
  });


  // Create new session: lazy draft mode (zero eager backend POST)
  const handleNewSession = () => {
    setCurrentSessionId("");
    setSessionTitle("New Directive");
    setMessages([]);
    setIsMobileSidebarOpen(false);
  };

  // Global Keyboard Shortcuts (Ctrl+K: New Chat, Escape: Hierarchical Dismissal)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        handleNewSession();
      }
      if (e.key === "Escape") {
        // Layered dismissal: close top-level modals first before dismissing canvas
        if (isSkillsModalOpen) {
          setIsSkillsModalOpen(false);
          return;
        }
        if (isMemoriesModalOpen) {
          setIsMemoriesModalOpen(false);
          return;
        }
        if (isMobileSidebarOpen) {
          setIsMobileSidebarOpen(false);
          return;
        }
        if (isCanvasOpen) {
          setIsCanvasOpen(false);
          return;
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isCanvasOpen, isSkillsModalOpen, isMemoriesModalOpen, isMobileSidebarOpen]);

  // Fetch sessions on mount
  const fetchSessions = async () => {
    try {
      const res = await fetch("/api/sessions?user_id=boss");
      if (res.ok) {
        const data = await res.json();
        if (data.sessions && Array.isArray(data.sessions)) {
          setSessions(data.sessions);
          if (data.sessions.length > 0 && !currentSessionId) {
            setCurrentSessionId(data.sessions[0].id);
            setSessionTitle(data.sessions[0].title || "Directive Thread");
          }
        }
      }
    } catch (err) {
      console.debug("Could not fetch sessions from backend:", err);
    }
  };

  useEffect(() => {
    fetchSessions();
  }, []);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  // Handle splitter resizing
  const handleMouseDown = useCallback(() => {
    setIsDragging(true);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const newRatio = ((e.clientX - rect.left) / rect.width) * 100;
      if (newRatio >= 25 && newRatio <= 75) {
        setSplitRatio(newRatio);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseup", handleMouseUp);
    }
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging]);


  // Select session & load its history if available
  const handleSelectSession = async (sessionId: string) => {
    if (!sessionId) {
      setCurrentSessionId("");
      setSessionTitle("New Directive");
      setMessages([]);
      return;
    }
    setCurrentSessionId(sessionId);
    const found = sessions.find((s) => s.id === sessionId);
    if (found) {
      setSessionTitle(found.title);
    }
    try {
      const res = await fetch(`/api/sessions/${sessionId}?user_id=boss`);
      if (res.ok) {
        const data = await res.json();
        if (data.session && Array.isArray(data.session.raw_history)) {
          const formatted: ChatMessage[] = data.session.raw_history.map(
            (turn: any, i: number) => ({
              id: `msg-${sessionId}-${i}`,
              role: turn.role === "user" ? "user" : "assistant",
              content: turn.content || turn.text || "",
              timestamp: new Date().toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              }),
            })
          );
          setMessages(formatted);
        }
      }
    } catch (err) {
      console.debug("Could not load session details:", err);
    }
  };

  // Delete session: seamless handover without ghost directive creation
  const handleDeleteSession = async (sessionId: string) => {
    try {
      await fetch(`/api/sessions/${sessionId}?user_id=boss`, {
        method: "DELETE",
      });
      const remaining = sessions.filter((s) => s.id !== sessionId);
      setSessions(remaining);
      if (currentSessionId === sessionId) {
        if (remaining.length > 0) {
          await handleSelectSession(remaining[0].id);
        } else {
          setCurrentSessionId("");
          setSessionTitle("New Directive");
          setMessages([]);
        }
      }
    } catch (err) {
      console.error("Failed to delete session:", err);
    }
  };

  // Dispatch message to agent with optional files
  const handleSendMessage = async (textToSend?: string, attachedFiles?: File[]) => {
    const messageText = (textToSend || inputVal).trim();
    if ((!messageText && (!attachedFiles || attachedFiles.length === 0)) || isLoading) return;

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: messageText || (attachedFiles && attachedFiles.length > 0 ? `[Attached ${attachedFiles.length} file(s)]` : ""),
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputVal("");
    setIsLoading(true);

    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), 60000);

    try {
      const formData = new FormData();
      formData.append("user_id", "boss");
      formData.append("session_id", currentSessionId);
      formData.append("message", messageText);
      formData.append("operation_mode", operationMode);
      formData.append("module_id", "ultron_prime");
      formData.append("model_override", selectedModel);
      formData.append("optimize_prompt", optimizePrompt ? "true" : "false");

      if (attachedFiles && attachedFiles.length > 0) {
        attachedFiles.forEach((file) => {
          formData.append("files", file);
        });
      }

      const response = await fetch("/api/chat", {
        method: "POST",
        body: formData,
        signal: abortController.signal,
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`Chat API error (${response.status})`);
      }

      const data = await response.json();

      if (data.session_id && data.session_id !== currentSessionId) {
        setCurrentSessionId(data.session_id);
      }
      if (data.session_title) {
        setSessionTitle(data.session_title);
      }

      // Check if browser or computer tools were invoked
      const hasBrowserTool =
        data.tool_actions &&
        data.tool_actions.some((a: any) =>
          typeof a.tool === "string" && (a.tool.includes("browser") || a.tool.includes("computer"))
        );

      // Automatically open the Canvas when a browser or computer tool is used
      if (hasBrowserTool) {
        setIsCanvasOpen(true);
        setMobileViewTab("canvas");
      }

      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now() + 1}`,
        role: "assistant",
        content: data.reply || "Directive received and executed.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        model_display: data.model_display || data.model_used || "Ultron Core",
        route_reason: data.route_reason,
        tool_actions: data.tool_actions,
        skills_used: data.skills_used,
        is_swarm: Boolean(data.is_swarm),
      };

      setMessages((prev) => [...prev, assistantMessage]);
      fetchSessions();
    } catch (err) {
      clearTimeout(timeoutId);
      const isAbort = (err as Error)?.name === "AbortError";
      const errMsg = isAbort
        ? "Network request timed out after 60s"
        : err instanceof Error
        ? err.message
        : String(err);
      setMessages((prev) => [
        ...prev,
        {
          id: `msg-${Date.now() + 2}`,
          role: "assistant",
          content: `⚠️ **Execution Notice**: Could not complete network round-trip (${errMsg}). You can still interact directly with the WebRTC Player on the right.`,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          error: true,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // User prompts browser to navigate via Canvas address bar
  const handleNavigateUrl = (url: string) => {
    setIsCanvasOpen(true);
    setMobileViewTab("canvas");
    handleSendMessage(`Navigate to ${url} and summarize the page content.`);
  };

  return (
    <div className="flex w-screen h-screen overflow-hidden bg-theme-ground text-theme-main font-sans select-none relative transition-colors">
      {/* Ambient sky-blue / cyan backglow */}
      <div className="absolute top-0 right-0 w-[550px] h-[450px] bg-gradient-to-b from-theme-accent/10 via-transparent to-transparent blur-3xl pointer-events-none z-0" />

      {/* ── Left Sidebar (Desktop + Mobile Drawer) ── */}
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        onSelectFeature={(prompt) => handleSendMessage(prompt)}
        onOpenMemories={() => setIsMemoriesModalOpen(true)}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
        isMobileOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* ── Main Content Area ── */}
      <div className="flex-1 flex flex-col h-full overflow-hidden p-1.5 sm:p-3 relative z-10 bg-theme-ground">
        <div
          ref={containerRef}
          className="flex-1 flex flex-col md:flex-row h-full overflow-hidden rounded-2xl sm:rounded-3xl bg-theme-panel border border-theme-border shadow-xl relative"
        >
          {/* ── Mobile Tab Switcher (When Canvas is Active on Mobile Viewports) ── */}
          {isCanvasOpen && (
            <div className="flex md:hidden items-center justify-between px-3 py-2 bg-theme-dock border-b border-theme-border gap-2 shrink-0 z-20">
              <div className="flex items-center gap-1.5 flex-1">
                <button
                  type="button"
                  onClick={() => setMobileViewTab("chat")}
                  className={cn(
                    "flex-1 py-1.5 px-3 rounded-xl text-xs font-semibold transition-all min-h-[38px]",
                    mobileViewTab === "chat"
                      ? "bg-theme-panel text-theme-main shadow-xs border border-theme-border"
                      : "text-theme-muted hover:text-theme-main"
                  )}
                >
                  Directives Chat
                </button>
                <button
                  type="button"
                  onClick={() => setMobileViewTab("canvas")}
                  className={cn(
                    "flex-1 py-1.5 px-3 rounded-xl text-xs font-semibold transition-all min-h-[38px] flex items-center justify-center gap-1.5",
                    mobileViewTab === "canvas"
                      ? "bg-theme-panel text-theme-accent shadow-xs border border-theme-border"
                      : "text-theme-muted hover:text-theme-main"
                  )}
                >
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                  Browser Canvas
                </button>
              </div>
              <button
                type="button"
                onClick={() => setIsCanvasOpen(false)}
                className="text-xs text-theme-muted hover:text-rose-400 p-1.5"
                title="Close Canvas"
              >
                Close
              </button>
            </div>
          )}

          {/* ── Chat Column ── */}
          <div
            style={{ width: isCanvasOpen ? `${splitRatio}%` : "100%" }}
            className={cn(
              "flex-col h-full bg-theme-panel overflow-hidden transition-all duration-75 relative",
              isCanvasOpen && mobileViewTab === "canvas" ? "hidden md:flex" : "flex",
              !isCanvasOpen && "w-full"
            )}
          >
            {/* Top Navigation Bar */}
            <TopBar
              operationMode={operationMode}
              selectedModel={selectedModel}
              sessionTitle={sessionTitle}
              isCanvasOpen={isCanvasOpen}
              onToggleCanvas={() => setIsCanvasOpen(!isCanvasOpen)}
              isStreamConnected={isConnected}
              onOpenSettings={() => setIsSkillsModalOpen(true)}
              onOpenMemories={() => setIsMemoriesModalOpen(true)}
              onToggleMobileSidebar={() => setIsMobileSidebarOpen(!isMobileSidebarOpen)}
            />

            {/* ── Center Content: Welcome Hero OR Chat Stream ── */}
            <div className="flex-1 overflow-y-auto px-4 py-2 relative bg-theme-panel">
              {messages.length === 0 ? (
                /* Welcome Hero Screen */
                <WelcomeHero
                  inputVal={inputVal}
                  onChangeInput={setInputVal}
                  onSend={(files) => handleSendMessage(undefined, files)}
                  isLoading={isLoading}
                  isCanvasOpen={isCanvasOpen}
                  onToggleCanvas={() => setIsCanvasOpen(!isCanvasOpen)}
                  isStreamConnected={isConnected}
                  operationMode={operationMode}
                  onChangeMode={setOperationMode}
                  selectedModel={selectedModel}
                  onChangeModel={setSelectedModel}
                  optimizePrompt={optimizePrompt}
                  onToggleOptimizePrompt={() => setOptimizePrompt(!optimizePrompt)}
                  onOpenSkills={() => setIsSkillsModalOpen(true)}
                  onOpenMemories={() => setIsMemoriesModalOpen(true)}
                  onSelectPrompt={(p) => handleSendMessage(p)}
                />
              ) : (
                /* Active Conversation Feed */
                <div className="max-w-3xl mx-auto py-6">
                  {messages.map((msg) => (
                    <ChatMessageItem
                      key={msg.id}
                      message={msg}
                      onOpenCanvas={() => {
                        setIsCanvasOpen(true);
                        setMobileViewTab("canvas");
                      }}
                    />
                  ))}

                  {/* Thinking / Processing Pulse */}
                  {isLoading && (
                    <div className="flex items-center gap-3 mb-6">
                      <div className="w-8 h-8 rounded-xl bg-theme-dock border border-theme-focus/40 flex items-center justify-center text-theme-accent shrink-0 shadow-xs robot-idle">
                        <BrainCircuit className="w-4 h-4 animate-spin text-theme-accent" />
                      </div>
                      <div className="px-4 py-2.5 rounded-2xl bg-theme-card border border-theme-border text-xs font-mono text-theme-accent flex items-center gap-2 shadow-xs">
                        <span className="w-2 h-2 rounded-full bg-theme-accent animate-ping" />
                        <span>Ultron is reasoning and executing tools...</span>
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* ── Floating Input Card (in active chat mode) ── */}
            {messages.length > 0 && (
              <div className="pt-2 pb-1 bg-gradient-to-t from-theme-panel via-theme-panel/95 to-transparent">
                <ChatInput
                  value={inputVal}
                  onChange={setInputVal}
                  onSend={(files) => handleSendMessage(undefined, files)}
                  isLoading={isLoading}
                  isCanvasOpen={isCanvasOpen}
                  onToggleCanvas={() => {
                    const next = !isCanvasOpen;
                    setIsCanvasOpen(next);
                    if (next) setMobileViewTab("canvas");
                  }}
                  isStreamConnected={isConnected}
                  operationMode={operationMode}
                  onChangeMode={setOperationMode}
                  selectedModel={selectedModel}
                  onChangeModel={setSelectedModel}
                  optimizePrompt={optimizePrompt}
                  onToggleOptimizePrompt={() => setOptimizePrompt(!optimizePrompt)}
                  onOpenSkills={() => setIsSkillsModalOpen(true)}
                  onOpenMemories={() => setIsMemoriesModalOpen(true)}
                />
              </div>
            )}
          </div>

          {/* ── Resizable Splitter Divider Bar (Desktop) ── */}
          {isCanvasOpen && (
            <div
              onMouseDown={handleMouseDown}
              className={cn(
                "hidden md:flex relative items-center justify-center w-1.5 hover:w-2 bg-theme-border hover:bg-theme-focus/50 cursor-col-resize transition-colors z-20 group shrink-0",
                isDragging && "bg-theme-focus w-2"
              )}
            />
          )}

          {/* ── Right Canvas Pane (WebRTC Player) ── */}
          {isCanvasOpen && (
            <div
              style={{ width: `${100 - splitRatio}%` }}
              className={cn(
                "h-full overflow-hidden bg-theme-panel",
                mobileViewTab === "chat" ? "hidden md:block" : "w-full md:block"
              )}
            >
              <CanvasPane
                mediaStream={mediaStream}
                isConnected={isConnected}
                isConnecting={isConnecting}
                error={rtcError}
                agentCursor={agentCursor}
                sendControlEvent={sendControlEvent}
                onReconnect={reconnect}
                onClose={() => setIsCanvasOpen(false)}
                onNavigateUrl={handleNavigateUrl}
                className="h-full"
              />
            </div>
          )}
        </div>
      </div>

      {/* ── Skills Matrix Modal ── */}
      <SkillsModal
        isOpen={isSkillsModalOpen}
        onClose={() => setIsSkillsModalOpen(false)}
        onSelectSkill={(skill) => {
          handleSendMessage(`Activate and execute capability skill: ${skill.name} (${skill.id || skill.skill_id}).`);
        }}
      />

      {/* ── Neural Memories Matrix Modal ── */}
      <MemoriesModal
        isOpen={isMemoriesModalOpen}
        onClose={() => setIsMemoriesModalOpen(false)}
      />
    </div>
  );
};
