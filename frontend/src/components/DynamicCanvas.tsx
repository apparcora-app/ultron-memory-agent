/**
 * DynamicCanvas.tsx — Kimi/ChatGPT Canvas Style Split-Pane Workspace for Ultron.
 *
 * Implements a 2-column cybernetic layout:
 *   - Left Pane (40% default, resizable): Agent Telemetry, Reasoning Stream, and Audit Ledger.
 *   - Right Pane (60% default): Embedded 60 FPS WebRTC Canvas Player.
 */

import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Activity,
  Bot,
  BrainCircuit,
  ChevronLeft,
  ChevronRight,
  Cpu,
  Layers,
  Radio,
  ScrollText,
  Send,
  Shield,
  ShieldAlert,
  Sparkles,
  Terminal,
  Zap,
} from "lucide-react";
import { useWebRTCStream } from "../hooks/useWebRTCStream";
import { WebRTCPlayer } from "./WebRTCPlayer";
import { cn } from "../lib/utils";

interface LogEntry {
  id: string;
  timestamp: string;
  type: "thought" | "tool" | "audit" | "system" | "error";
  title: string;
  content: string;
  status?: "pending" | "running" | "completed" | "refused";
}

const INITIAL_LOGS: LogEntry[] = [
  {
    id: "log-1",
    timestamp: "12:00:01",
    type: "system",
    title: "CYBERNETIC PROTOCOL ONLINE",
    content: "Ultron memory agent core initialized. WebRTC streaming bridge ready.",
    status: "completed",
  },
  {
    id: "log-2",
    timestamp: "12:00:04",
    type: "thought",
    title: "HEURISTIC REASONING",
    content: "Observing browser viewport state. No security anomalies detected.",
    status: "completed",
  },
  {
    id: "log-3",
    timestamp: "12:00:08",
    type: "tool",
    title: "TOOL CALL: browser_navigate",
    content: "target: 'https://duckduckgo.com' [ARIA token compaction: active]",
    status: "completed",
  },
];

export const DynamicCanvas: React.FC = () => {
  const [sessionId, setSessionId] = useState("default");
  const [splitRatio, setSplitRatio] = useState(40); // 40% left, 60% right
  const [isDragging, setIsDragging] = useState(false);
  const [isLeftCollapsed, setIsLeftCollapsed] = useState(false);
  const [activeTab, setActiveTab] = useState<"stream" | "audit" | "system">("stream");
  const [commandInput, setCommandInput] = useState("");
  const [logs, setLogs] = useState<LogEntry[]>(INITIAL_LOGS);
  const [systemLocked, setSystemLocked] = useState(false);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const logsEndRef = useRef<HTMLDivElement | null>(null);

  // Initialize WebRTC stream
  const {
    mediaStream,
    isConnected,
    isConnecting,
    error,
    agentCursor,
    sendControlEvent,
    reconnect,
  } = useWebRTCStream("", {
    sessionId,
    autoConnect: true,
    fps: 60,
    pixelFormat: "yuv420p",
  });

  // Handle splitter resizing
  const handleMouseDown = useCallback(() => {
    setIsDragging(true);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const newRatio = ((e.clientX - rect.left) / rect.width) * 100;
      if (newRatio >= 20 && newRatio <= 70) {
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

  // Auto-scroll log console
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  // Dispatch command to agent
  const handleSendCommand = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commandInput.trim()) return;

    const newLog: LogEntry = {
      id: `log-${Date.now()}`,
      timestamp: new Date().toLocaleTimeString(),
      type: "thought",
      title: "OPERATOR DISPATCH",
      content: commandInput,
      status: "running",
    };

    setLogs((prev) => [...prev, newLog]);
    setCommandInput("");

    // Simulate agent response & tool invocation
    setTimeout(() => {
      setLogs((prev) => [
        ...prev,
        {
          id: `log-${Date.now() + 1}`,
          timestamp: new Date().toLocaleTimeString(),
          type: "tool",
          title: "AUTONOMOUS AGENT ACTION",
          content: `Ingested operator prompt. Emitting control events to WebRTC browser controller.`,
          status: "completed",
        },
      ]);
    }, 1200);
  };

  return (
    <div
      ref={containerRef}
      className="flex flex-col w-screen h-screen overflow-hidden bg-zinc-950 text-zinc-100 font-sans select-none"
    >
      {/* ── Top Global Cybernetic Navigation Bar ── */}
      <header className="flex items-center justify-between px-5 py-2.5 bg-zinc-900/90 backdrop-blur-md border-b border-zinc-800/80 z-30">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/40 text-cyan-400 shadow-[0_0_12px_rgba(0,240,255,0.3)]">
            <BrainCircuit className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold tracking-wider text-zinc-100">
                ULTRON // CYBERNETIC HUD
              </span>
              <span className="px-1.5 py-0.2 rounded bg-cyan-950 border border-cyan-500/40 text-[9px] font-mono text-cyan-300">
                v2.4 OPENBOT
              </span>
            </div>
            <p className="text-[10px] font-mono text-zinc-500 leading-none">
              WebRTC Screencast Bridge & Autonomous Agent Mesh
            </p>
          </div>
        </div>

        {/* Center Indicators */}
        <div className="hidden md:flex items-center gap-3 px-3 py-1 rounded-full bg-zinc-950/80 border border-zinc-800/80 font-mono text-xs">
          <div className="flex items-center gap-1.5">
            <Radio
              className={cn(
                "w-3.5 h-3.5",
                isConnected ? "text-emerald-400 animate-pulse" : "text-zinc-600"
              )}
            />
            <span className={isConnected ? "text-emerald-400 font-semibold" : "text-zinc-500"}>
              {isConnected ? "RTC P2P LIVE" : isConnecting ? "CONNECTING..." : "DISCONNECTED"}
            </span>
          </div>

          <div className="h-3 w-px bg-zinc-800" />

          <div className="flex items-center gap-1.5 text-zinc-400 text-[11px]">
            <Activity className="w-3 h-3 text-cyan-400" />
            <span>60 FPS CAP</span>
          </div>

          <div className="h-3 w-px bg-zinc-800" />

          <div className="flex items-center gap-1.5 text-zinc-400 text-[11px]">
            <Cpu className="w-3 h-3 text-amber-400" />
            <span>SESSION:</span>
            <input
              type="text"
              value={sessionId}
              onChange={(e) => setSessionId(e.target.value)}
              className="w-20 px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-700/60 text-amber-300 font-mono text-[10px] focus:outline-none focus:border-amber-400"
              title="Target Computer Session ID"
            />
          </div>
        </div>

        {/* Right Header Actions */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setSystemLocked(!systemLocked)}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-mono font-medium transition-all duration-200 border",
              systemLocked
                ? "bg-rose-500/20 text-rose-300 border-rose-500/60 shadow-[0_0_12px_rgba(244,63,94,0.4)]"
                : "bg-zinc-800/60 text-zinc-400 border-zinc-700/60 hover:bg-zinc-800 hover:text-zinc-200"
            )}
            title="Emergency Agent Lockdown"
          >
            {systemLocked ? (
              <>
                <ShieldAlert className="w-3.5 h-3.5 text-rose-400 animate-bounce" />
                <span>KILLSWITCH ACTIVE</span>
              </>
            ) : (
              <>
                <Shield className="w-3.5 h-3.5 text-emerald-400" />
                <span>SAFETY ARMED</span>
              </>
            )}
          </button>
        </div>
      </header>

      {/* ── Main 2-Column Split Workspace ── */}
      <div className="flex-1 flex w-full h-[calc(100vh-53px)] overflow-hidden relative">
        {/* ── Left Pane: Agent Telemetry & Log Console (40% default) ── */}
        <div
          style={{ width: isLeftCollapsed ? "0%" : `${splitRatio}%` }}
          className={cn(
            "flex flex-col h-full bg-zinc-950 border-r border-zinc-800/80 transition-all duration-75 overflow-hidden",
            isLeftCollapsed && "w-0 p-0 border-r-0"
          )}
        >
          {/* Console Header Tabs */}
          <div className="flex items-center justify-between px-3 py-2 bg-zinc-900/60 border-b border-zinc-800/80">
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setActiveTab("stream")}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono transition-colors",
                  activeTab === "stream"
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                    : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
                )}
              >
                <Sparkles className="w-3 h-3 text-cyan-400" />
                <span>THOUGHT STREAM</span>
              </button>

              <button
                onClick={() => setActiveTab("audit")}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono transition-colors",
                  activeTab === "audit"
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                    : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
                )}
              >
                <ScrollText className="w-3 h-3 text-amber-400" />
                <span>AUDIT LEDGER</span>
              </button>

              <button
                onClick={() => setActiveTab("system")}
                className={cn(
                  "flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono transition-colors",
                  activeTab === "system"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                    : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
                )}
              >
                <Layers className="w-3 h-3 text-emerald-400" />
                <span>SUBSYSTEMS</span>
              </button>
            </div>

            <span className="text-[10px] font-mono text-zinc-500">
              {logs.length} EVENTS
            </span>
          </div>

          {/* Telemetry Log Stream */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2 font-mono text-xs cyber-grid">
            {logs.map((log) => (
              <div
                key={log.id}
                className={cn(
                  "p-2.5 rounded-lg border backdrop-blur-sm transition-all",
                  log.type === "thought" && "bg-cyan-950/20 border-cyan-500/30 text-cyan-100",
                  log.type === "tool" && "bg-amber-950/20 border-amber-500/30 text-amber-100",
                  log.type === "system" && "bg-zinc-900/60 border-zinc-800 text-zinc-300",
                  log.type === "error" && "bg-rose-950/20 border-rose-500/40 text-rose-200"
                )}
              >
                <div className="flex items-center justify-between mb-1 text-[10px]">
                  <div className="flex items-center gap-1.5">
                    {log.type === "thought" && <Zap className="w-3 h-3 text-cyan-400" />}
                    {log.type === "tool" && <Terminal className="w-3 h-3 text-amber-400" />}
                    {log.type === "system" && <Bot className="w-3 h-3 text-emerald-400" />}
                    <span className="font-semibold tracking-wider">{log.title}</span>
                  </div>
                  <span className="text-zinc-500">{log.timestamp}</span>
                </div>
                <p className="text-xs text-zinc-300 break-words leading-relaxed pl-4 border-l border-zinc-800">
                  {log.content}
                </p>
              </div>
            ))}
            <div ref={logsEndRef} />
          </div>

          {/* Bottom Prompt / Command Dispatcher */}
          <form
            onSubmit={handleSendCommand}
            className="flex items-center gap-2 p-2.5 bg-zinc-900/90 border-t border-zinc-800/80"
          >
            <input
              type="text"
              value={commandInput}
              onChange={(e) => setCommandInput(e.target.value)}
              placeholder="Inject command or operator prompt into Ultron mesh..."
              className="flex-1 px-3 py-1.5 rounded-lg bg-zinc-950 border border-zinc-800 text-xs font-mono text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-cyan-500/60"
            />
            <button
              type="submit"
              className="p-1.5 rounded-lg bg-cyan-500/20 border border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/30 transition-colors"
              title="Dispatch to Agent"
            >
              <Send className="w-3.5 h-3.5" />
            </button>
          </form>
        </div>

        {/* ── Central Resizable Divider Bar ── */}
        <div
          onMouseDown={handleMouseDown}
          className={cn(
            "relative flex items-center justify-center w-1.5 hover:w-2 bg-zinc-900 hover:bg-cyan-500/50 cursor-col-resize transition-colors z-20 group",
            isDragging && "bg-cyan-500 w-2"
          )}
        >
          {/* Collapse/Expand Toggle Button */}
          <button
            onClick={() => setIsLeftCollapsed(!isLeftCollapsed)}
            className="absolute top-1/2 -translate-y-1/2 -left-2.5 w-5 h-8 rounded bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-400 hover:text-cyan-400 opacity-0 group-hover:opacity-100 transition-opacity z-30"
          >
            {isLeftCollapsed ? (
              <ChevronRight className="w-3 h-3" />
            ) : (
              <ChevronLeft className="w-3 h-3" />
            )}
          </button>
        </div>

        {/* ── Right Pane: Active WebRTC Screencast Canvas (60% default) ── */}
        <div
          style={{ width: isLeftCollapsed ? "100%" : `${100 - splitRatio}%` }}
          className="flex-1 flex flex-col h-full bg-zinc-950 p-3 overflow-hidden"
        >
          <WebRTCPlayer
            mediaStream={mediaStream}
            isConnected={isConnected}
            isConnecting={isConnecting}
            error={error}
            agentCursor={agentCursor}
            sendControlEvent={sendControlEvent}
            onReconnect={reconnect}
            botName="OpenBot Playwright Node"
            className="flex-1"
          />
        </div>
      </div>
    </div>
  );
};
