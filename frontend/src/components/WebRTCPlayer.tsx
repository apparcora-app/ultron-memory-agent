/**
 * WebRTCPlayer.tsx — 60 FPS Hardware-Accelerated Video Player & Canvas Interface.
 *
 * Renders the live Playwright browser screencast via WebRTC MediaStream, maps
 * normalized user clicks and keystrokes back to the backend ("Take the Wheel"),
 * and displays a spring-animated ghost cursor overlay for agent telemetry.
 */

import React, { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Activity,
  AlertCircle,
  Eye,
  Hand,
  Maximize2,
  Minimize2,
  RefreshCw,
  Terminal,
  Wifi,
  WifiOff,
} from "lucide-react";
import type { AgentCursorState } from "../hooks/useWebRTCStream";
import { cn } from "../lib/utils";

export interface WebRTCPlayerProps {
  mediaStream: MediaStream | null;
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
  agentCursor: AgentCursorState | null;
  sendControlEvent: (payload: Record<string, unknown>) => void;
  onReconnect?: () => void;
  className?: string;
  botName?: string;
}

export const WebRTCPlayer: React.FC<WebRTCPlayerProps> = ({
  mediaStream,
  isConnected,
  isConnecting,
  error,
  agentCursor,
  sendControlEvent,
  onReconnect,
  className,
  botName = "Ultron Core",
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [takeWheelActive, setTakeWheelActive] = useState(false);
  const [userCursorPos, setUserCursorPos] = useState<{ x: number; y: number } | null>(null);

  // Bind MediaStream to HTML5 video element
  useEffect(() => {
    const video = videoRef.current;
    if (video) {
      if (mediaStream) {
        video.srcObject = mediaStream;
        video.play().catch((err) => {
          console.debug("[WebRTCPlayer] Video autoPlay waiting for user interaction:", err);
        });
      } else {
        video.srcObject = null;
      }
    }
  }, [mediaStream]);

  // Compute normalized [0.0, 1.0] coordinates from mouse event
  const getNormalizedCoordinates = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const target = videoRef.current || containerRef.current;
      if (!target) return null;

      const rect = target.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return null;

      const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
      return { x, y };
    },
    []
  );

  // Handle click events (Take the Wheel / remote control)
  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const coords = getNormalizedCoordinates(e);
      if (!coords) return;

      const button = e.button === 2 ? "right" : e.button === 1 ? "middle" : "left";
      sendControlEvent({
        type: "CLICK",
        x: coords.x,
        y: coords.y,
        button,
      });

      // Visual feedback ripple for user interaction
      setUserCursorPos(coords);
      setTimeout(() => setUserCursorPos(null), 300);
    },
    [getNormalizedCoordinates, sendControlEvent]
  );

  // Handle mouse move
  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!takeWheelActive) return;
      const coords = getNormalizedCoordinates(e);
      if (coords) {
        sendControlEvent({
          type: "MOUSE_MOVE",
          x: coords.x,
          y: coords.y,
        });
      }
    },
    [takeWheelActive, getNormalizedCoordinates, sendControlEvent]
  );

  // Keyboard navigation & typing
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      // Prevent scrolling page when interacting with player
      if (["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Tab"].includes(e.key)) {
        e.preventDefault();
      }

      sendControlEvent({
        type: "KEY_DOWN",
        key: e.key,
      });
    },
    [sendControlEvent]
  );

  const handleKeyUp = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      sendControlEvent({
        type: "KEY_UP",
        key: e.key,
      });
    },
    [sendControlEvent]
  );

  // Fullscreen toggle
  const toggleFullscreen = useCallback(() => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch((err) => {
        console.warn("Fullscreen request error:", err);
      });
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  }, []);

  return (
    <div
      ref={containerRef}
      tabIndex={0}
      onKeyDown={handleKeyDown}
      onKeyUp={handleKeyUp}
      className={cn(
        "relative flex flex-col w-full h-full overflow-hidden rounded-xl bg-zinc-950 border border-zinc-800/80 shadow-2xl focus:outline-none focus:ring-1 focus:ring-cyan-500/40 select-none",
        className
      )}
    >
      {/* ── Top HUD Bezel Header ── */}
      <div className="flex items-center justify-between px-4 py-2 bg-zinc-900/80 backdrop-blur-md border-b border-zinc-800/80 z-20">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span
              className={cn(
                "h-2 w-2 rounded-full",
                isConnected
                  ? "bg-emerald-400 shadow-[0_0_8px_#34d399]"
                  : isConnecting
                  ? "bg-amber-400 animate-ping"
                  : "bg-rose-500"
              )}
            />
            <span className="font-mono text-xs text-zinc-300 font-semibold tracking-wide">
              {isConnected ? "LIVE STREAM" : isConnecting ? "NEGOTIATING" : "OFFLINE"}
            </span>
          </div>

          <div className="hidden sm:flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-800/60 border border-zinc-700/40 text-[10px] font-mono text-zinc-400">
            <Activity className="w-3 h-3 text-cyan-400" />
            <span>60 FPS</span>
          </div>

          <div className="hidden md:flex items-center gap-1.5 px-2 py-0.5 rounded bg-zinc-800/60 border border-zinc-700/40 text-[10px] font-mono text-zinc-400">
            <Terminal className="w-3 h-3 text-amber-400" />
            <span>{botName}</span>
          </div>
        </div>

        {/* Right Action Controls */}
        <div className="flex items-center gap-2">
          {/* Take the Wheel Toggle Button */}
          <button
            onClick={() => setTakeWheelActive(!takeWheelActive)}
            className={cn(
              "flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-medium transition-all duration-200 border",
              takeWheelActive
                ? "bg-amber-500/20 text-amber-300 border-amber-500/60 shadow-[0_0_12px_rgba(245,158,11,0.3)]"
                : "bg-zinc-800/60 text-zinc-400 border-zinc-700/50 hover:bg-zinc-800 hover:text-zinc-200"
            )}
            title="Take manual control over the browser session"
          >
            <Hand className="w-3.5 h-3.5" />
            <span>{takeWheelActive ? "WHEEL ACTIVE" : "TAKE WHEEL"}</span>
          </button>

          {/* Reconnect Button */}
          {onReconnect && (
            <button
              onClick={onReconnect}
              disabled={isConnecting}
              className="p-1 rounded bg-zinc-800/60 text-zinc-400 border border-zinc-700/50 hover:bg-zinc-800 hover:text-zinc-200 transition-colors disabled:opacity-50"
              title="Reconnect WebRTC stream"
            >
              <RefreshCw className={cn("w-3.5 h-3.5", isConnecting && "animate-spin text-cyan-400")} />
            </button>
          )}

          {/* Fullscreen Button */}
          <button
            onClick={toggleFullscreen}
            className="p-1 rounded bg-zinc-800/60 text-zinc-400 border border-zinc-700/50 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
            title="Toggle fullscreen"
          >
            {isFullscreen ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* ── Viewport & Interactive Surface ── */}
      <div
        className="relative flex-1 flex items-center justify-center bg-black overflow-hidden cursor-crosshair"
        onClick={handleClick}
        onMouseMove={handleMouseMove}
      >
        {/* Hardware-Accelerated Video Surface */}
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-contain pointer-events-auto"
          style={{
            transform: "translateZ(0)",
            WebkitTransform: "translateZ(0)",
            backfaceVisibility: "hidden",
          }}
        />

        {/* ── User Click Indicator Ripple ── */}
        <AnimatePresence>
          {userCursorPos && (
            <motion.div
              initial={{ scale: 0, opacity: 1 }}
              animate={{ scale: 2.5, opacity: 0 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.35, ease: "easeOut" }}
              className="absolute pointer-events-none w-6 h-6 -ml-3 -mt-3 rounded-full border-2 border-amber-400 bg-amber-400/20 z-40"
              style={{
                left: `${userCursorPos.x * 100}%`,
                top: `${userCursorPos.y * 100}%`,
              }}
            />
          )}
        </AnimatePresence>

        {/* ── Ghost Agent Cursor Overlay ── */}
        <AnimatePresence>
          {agentCursor && agentCursor.active && (
            <motion.div
              className="pointer-events-none absolute z-30 flex flex-col items-start"
              initial={false}
              animate={{
                left: `${agentCursor.x * 100}%`,
                top: `${agentCursor.y * 100}%`,
              }}
              transition={{
                type: "spring",
                damping: 24,
                stiffness: 300,
                mass: 0.4,
              }}
            >
              {/* Glowing Cybernetic SVG Cursor */}
              <div className="relative -ml-1 -mt-1 flex items-center">
                <svg
                  className="w-7 h-7 text-cyan-400 drop-shadow-[0_0_10px_rgba(0,240,255,0.9)] animate-pulse"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <polygon
                    points="3 3 10 21 14 14 21 10 3 3"
                    fill="rgba(0, 240, 255, 0.4)"
                    stroke="rgba(0, 240, 255, 1)"
                  />
                </svg>

                {/* Agent Tag Label */}
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="ml-2 flex items-center gap-1 px-1.5 py-0.5 rounded bg-cyan-950/90 border border-cyan-500/60 shadow-lg backdrop-blur-sm"
                >
                  <Eye className="w-2.5 h-2.5 text-cyan-400" />
                  <span className="text-[10px] font-mono font-medium text-cyan-300 tracking-wider">
                    {agentCursor.label || "ULTRON AUTONOMOUS"}
                  </span>
                </motion.div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Standby / Negotiating / Error Overlays ── */}
        {!isConnected && !isConnecting && !error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-950/90 backdrop-blur-sm text-center p-6 z-10">
            <WifiOff className="w-12 h-12 text-zinc-600 mb-3" />
            <h3 className="font-mono text-sm font-semibold text-zinc-300">STREAM STANDBY</h3>
            <p className="text-xs text-zinc-500 mt-1 max-w-sm">
              Waiting for autonomous bot execution or manual connect signal.
            </p>
            {onReconnect && (
              <button
                onClick={onReconnect}
                className="mt-4 px-4 py-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/40 text-cyan-400 font-mono text-xs hover:bg-cyan-500/20 transition-all"
              >
                Connect Stream
              </button>
            )}
          </div>
        )}

        {isConnecting && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-950/80 backdrop-blur-sm text-center p-6 z-10">
            <div className="relative w-12 h-12 mb-4">
              <div className="absolute inset-0 rounded-full border-2 border-cyan-500/20" />
              <div className="absolute inset-0 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
            </div>
            <h3 className="font-mono text-sm font-semibold text-cyan-300 tracking-wider">
              ESTABLISHING WEBRTC MESH
            </h3>
            <p className="text-xs text-zinc-400 mt-1">
              SDP Handshake & ICE Candidate Gathering...
            </p>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-zinc-950/90 backdrop-blur-sm text-center p-6 z-10">
            <AlertCircle className="w-12 h-12 text-rose-500 mb-3" />
            <h3 className="font-mono text-sm font-semibold text-rose-400">STREAM NEGOTIATION ERROR</h3>
            <p className="text-xs text-zinc-400 mt-1 max-w-sm">{error}</p>
            {onReconnect && (
              <button
                onClick={onReconnect}
                className="mt-4 px-4 py-1.5 rounded-lg bg-rose-500/10 border border-rose-500/40 text-rose-300 font-mono text-xs hover:bg-rose-500/20 transition-all"
              >
                Retry Connection
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Bottom HUD Footer Bar ── */}
      <div className="flex items-center justify-between px-3 py-1 bg-zinc-950 border-t border-zinc-800/80 text-[10px] font-mono text-zinc-500 z-20">
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-1">
            <Wifi className="w-3 h-3 text-zinc-600" />
            <span>WebRTC (P2P Low-Latency)</span>
          </span>
          <span>Resolution: 1280x720</span>
        </div>
        <div className="flex items-center gap-2">
          {takeWheelActive ? (
            <span className="text-amber-400 font-semibold animate-pulse">
              ● MANUAL OVERRIDE (CLICK / KEYBOARD ACTIVE)
            </span>
          ) : (
            <span className="text-zinc-600">● AGENT AUTOPILOT ACTIVE</span>
          )}
        </div>
      </div>
    </div>
  );
};
