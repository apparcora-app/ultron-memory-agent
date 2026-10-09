/**
 * KimiChatWorkspace.tsx — Syntrix-Style Autonomous AI Workspace with Dynamic WebRTC Canvas.
 *
 * Implements the Syntrix interface:
 *   - Dark aesthetic with ambient cyan/teal radial backglow.
 *   - 3D glowing iridescent sphere avatar in Welcome Hero.
 *   - Centered floating ChatInput card with:
 *       • Solo Agent vs Swarm Agent toggle
 *       • Prompt Optimizer on/off toggle
 *       • LLM Shift dropdown in chat bar
 *       • Skills Matrix modal launcher
 *       • Voice recognition & circular Send button
 *   - 3 Syntrix starter cards: Image Generator, Video Generator, Dev Assistant.
 *   - Collapsible left sidebar with FEATURES, YOUR CHATS, and user profile (NO $49 Upgrade card).
 *   - Top bar with version pill, Dashboard, Settings, Help & Support, and user avatar.
 *   - Parallel 50/50 WebRTC Browser screencast canvas on browser/computer execution.
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
  const [isCanvasOpen, setIsCanvasOpen] = useState<boolean>(false);
  const [operationMode, setOperationMode] = useState<"DIRECT" | "SWARM">("DIRECT");
  const [selectedModel, setSelectedModel] = useState<string>("auto");
  const [optimizePrompt, setOptimizePrompt] = useState<boolean>(false);
  const [isSkillsModalOpen, setIsSkillsModalOpen] = useState<boolean>(false);
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

  // Create new session
  const handleNewSession = async () => {
    try {
      const formData = new FormData();
      formData.append("user_id", "boss");
      formData.append("module_id", "ultron_prime");
      formData.append("title", "New Directive");

      const res = await fetch("/api/sessions/new", {
        method: "POST",
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        if (data.session) {
          setCurrentSessionId(data.session.id);
          setSessionTitle(data.session.title || "New Directive");
          setMessages([]);
          setSessions((prev) => [data.session, ...prev]);
        }
      } else {
        const newId = `sess_${Date.now()}`;
        setCurrentSessionId(newId);
        setSessionTitle("New Directive");
        setMessages([]);
      }
    } catch {
      const newId = `sess_${Date.now()}`;
      setCurrentSessionId(newId);
      setSessionTitle("New Directive");
      setMessages([]);
    }
  };

  // Select session & load its history if available
  const handleSelectSession = async (sessionId: string) => {
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

  // Delete session
  const handleDeleteSession = async (sessionId: string) => {
    try {
      await fetch(`/api/sessions/${sessionId}?user_id=boss`, {
        method: "DELETE",
      });
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      if (currentSessionId === sessionId) {
        handleNewSession();
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
      });

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

      // Automatically open the Canvas when a browser or computer tool is used!
      if (hasBrowserTool) {
        setIsCanvasOpen(true);
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
      const errMsg = err instanceof Error ? err.message : String(err);
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
    handleSendMessage(`Navigate to ${url} and summarize the page content.`);
  };

  return (
    <div className="flex w-screen h-screen overflow-hidden bg-[#0a0c10] text-zinc-100 font-sans select-none relative">
      {/* Ambient Radial Glowing Aurora in Top-Right (Syntrix Aesthetic) */}
      <div className="absolute top-0 right-0 w-[600px] h-[500px] bg-gradient-to-b from-teal-500/10 via-cyan-500/5 to-transparent blur-3xl pointer-events-none z-0" />
      <div className="absolute bottom-0 left-1/3 w-[500px] h-[400px] bg-gradient-to-t from-cyan-500/5 to-transparent blur-3xl pointer-events-none z-0" />

      {/* ── Left Sidebar (Syntrix Style) ── */}
      <Sidebar
        sessions={sessions}
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onDeleteSession={handleDeleteSession}
        onSelectFeature={(prompt) => handleSendMessage(prompt)}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
      />

      {/* ── Main Content Area (Rounded Dark Viewport with Ambient Edge) ── */}
      <div className="flex-1 flex flex-col h-full overflow-hidden p-2 sm:p-3 relative z-10">
        <div
          ref={containerRef}
          className="flex-1 flex h-full overflow-hidden rounded-2xl sm:rounded-3xl bg-[#12151b]/95 border border-[#1f242d] shadow-2xl relative"
        >
          {/* ── Chat Column ── */}
          <div
            style={{ width: isCanvasOpen ? `${splitRatio}%` : "100%" }}
            className="flex flex-col h-full bg-[#12151b] overflow-hidden transition-all duration-75 relative"
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
            />

            {/* ── Center Content: Welcome Hero OR Chat Stream ── */}
            <div className="flex-1 overflow-y-auto px-4 py-2 relative">
              {messages.length === 0 ? (
                /* Welcome Hero Screen (Exact Syntrix View) */
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
                  onSelectPrompt={(p) => handleSendMessage(p)}
                />
              ) : (
                /* Active Conversation Feed */
                <div className="max-w-4xl mx-auto py-6">
                  {messages.map((msg) => (
                    <ChatMessageItem
                      key={msg.id}
                      message={msg}
                      onOpenCanvas={() => setIsCanvasOpen(true)}
                    />
                  ))}

                  {/* Thinking / Processing Pulse */}
                  {isLoading && (
                    <div className="flex items-center gap-3 mb-6">
                      <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
                        <BrainCircuit className="w-4 h-4 animate-spin" />
                      </div>
                      <div className="px-4 py-2.5 rounded-2xl bg-[#181c24] border border-[#272e3b] text-xs font-mono text-cyan-300 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                        <span>Ultron is reasoning and executing tools...</span>
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>
              )}
            </div>

            {/* ── Floating Input Card (Only rendered here if chat has messages) ── */}
            {messages.length > 0 && (
              <div className="pt-2 pb-1 bg-gradient-to-t from-[#12151b] via-[#12151b]/90 to-transparent">
                <ChatInput
                  value={inputVal}
                  onChange={setInputVal}
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
                />
              </div>
            )}
          </div>

          {/* ── Resizable Splitter Divider Bar ── */}
          {isCanvasOpen && (
            <div
              onMouseDown={handleMouseDown}
              className={cn(
                "relative flex items-center justify-center w-1.5 hover:w-2 bg-[#1c222e] hover:bg-cyan-500/50 cursor-col-resize transition-colors z-20 group",
                isDragging && "bg-cyan-500 w-2"
              )}
            />
          )}

          {/* ── Right Canvas Pane (60 FPS WebRTC Player & Screencast) ── */}
          {isCanvasOpen && (
            <div
              style={{ width: `${100 - splitRatio}%` }}
              className="h-full overflow-hidden bg-[#0c0e12]"
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
    </div>
  );
};
