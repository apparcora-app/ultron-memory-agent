/**
 * useWebRTCStream.ts — WebRTC Streaming & Remote Control Hook for Ultron Cybernetic HUD.
 *
 * Encapsulates the complete WebRTC peer connection lifecycle:
 *   - SDP offer generation with recvonly video transceiver
 *   - Negotiation via POST /api/webrtc/offer
 *   - Trickle ICE candidate forwarding via POST /api/webrtc/ice
 *   - "control" RTCDataChannel for remote inputs (CLICK, KEY_DOWN, etc.)
 *   - Ingestion and parsing of AGENT_CURSOR telemetry for live HUD visualization
 */

import { useCallback, useEffect, useRef, useState } from "react";

export interface AgentCursorState {
  x: number;
  y: number;
  active: boolean;
  label?: string;
  timestamp?: number;
}

export interface UseWebRTCStreamOptions {
  sessionId?: string;
  autoConnect?: boolean;
  fps?: number;
  pixelFormat?: string;
}

export interface UseWebRTCStreamReturn {
  videoTrack: MediaStreamTrack | null;
  mediaStream: MediaStream | null;
  isConnected: boolean;
  isConnecting: boolean;
  connectionState: RTCPeerConnectionState;
  error: string | null;
  agentCursor: AgentCursorState | null;
  sendControlEvent: (payload: Record<string, unknown>) => void;
  reconnect: () => void;
  disconnect: () => void;
}

const DEFAULT_STUN_SERVERS = [
  { urls: "stun:stun.l.google.com:19302" },
  { urls: "stun:stun1.l.google.com:19302" },
];

export function useWebRTCStream(
  backendUrl: string = "",
  options: UseWebRTCStreamOptions = {}
): UseWebRTCStreamReturn {
  const {
    sessionId = "default",
    autoConnect = true,
    fps = 60,
    pixelFormat = "yuv420p",
  } = options;

  const [videoTrack, setVideoTrack] = useState<MediaStreamTrack | null>(null);
  const [mediaStream, setMediaStream] = useState<MediaStream | null>(null);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isConnecting, setIsConnecting] = useState<boolean>(false);
  const [connectionState, setConnectionState] = useState<RTCPeerConnectionState>("new");
  const [error, setError] = useState<string | null>(null);
  const [agentCursor, setAgentCursor] = useState<AgentCursorState | null>(null);

  const pcRef = useRef<RTCPeerConnection | null>(null);
  const dcRef = useRef<RTCDataChannel | null>(null);
  const pendingCandidatesRef = useRef<RTCIceCandidateInit[]>([]);
  const isDestroyedRef = useRef<boolean>(false);

  // Normalize base API URL (handles relative path or custom host)
  const baseUrl = backendUrl.replace(/\/+$/, "");

  const bindDataChannel = useCallback((channel: RTCDataChannel) => {
    dcRef.current = channel;

    channel.onopen = () => {
      if (!isDestroyedRef.current) {
        setIsConnected(true);
        setIsConnecting(false);
        setError(null);
      }
    };

    channel.onclose = () => {
      if (!isDestroyedRef.current) {
        setIsConnected(false);
      }
    };

    channel.onerror = (err) => {
      console.warn("[WebRTC] Control data channel error:", err);
    };

    channel.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data && data.type === "AGENT_CURSOR") {
          setAgentCursor({
            x: typeof data.x === "number" ? data.x : 0.5,
            y: typeof data.y === "number" ? data.y : 0.5,
            active: Boolean(data.active),
            label: data.label || "Ultron Agent",
            timestamp: data.timestamp || Date.now(),
          });
        }
      } catch (err) {
        console.warn("[WebRTC] Failed to parse message from control channel:", err);
      }
    };
  }, []);

  const sendControlEvent = useCallback((payload: Record<string, unknown>) => {
    const dc = dcRef.current;
    if (dc && dc.readyState === "open") {
      try {
        dc.send(JSON.stringify(payload));
      } catch (err) {
        console.warn("[WebRTC] Error sending control event:", err);
      }
    } else {
      console.debug("[WebRTC] Control channel not open, drop event:", payload.type);
    }
  }, []);

  const disconnect = useCallback(() => {
    if (dcRef.current) {
      try {
        dcRef.current.close();
      } catch {
        /* no-op */
      }
      dcRef.current = null;
    }

    if (pcRef.current) {
      try {
        pcRef.current.close();
      } catch {
        /* no-op */
      }
      pcRef.current = null;
    }

    setVideoTrack(null);
    setMediaStream(null);
    setIsConnected(false);
    setIsConnecting(false);
    setConnectionState("closed");
    setAgentCursor(null);
  }, []);

  const connect = useCallback(async () => {
    if (isDestroyedRef.current) return;
    disconnect();

    setIsConnecting(true);
    setError(null);

    try {
      // 1. Initialize RTCPeerConnection with STUN
      const pc = new RTCPeerConnection({
        iceServers: DEFAULT_STUN_SERVERS,
      });
      pcRef.current = pc;

      // 2. Proactively create "control" RTCDataChannel
      const dc = pc.createDataChannel("control", {
        ordered: true,
      });
      bindDataChannel(dc);

      // Listen for data channels opened by remote
      pc.ondatachannel = (event) => {
        if (event.channel.label === "control" || !dcRef.current) {
          bindDataChannel(event.channel);
        }
      };

      // 3. Add recvonly video transceiver for screencast video
      pc.addTransceiver("video", { direction: "recvonly" });

      // Handle incoming video track
      pc.ontrack = (event) => {
        if (event.track.kind === "video") {
          setVideoTrack(event.track);
          const stream = event.streams[0] || new MediaStream([event.track]);
          setMediaStream(stream);
        }
      };

      // Track connection state transitions
      pc.onconnectionstatechange = () => {
        if (isDestroyedRef.current) return;
        setConnectionState(pc.connectionState);
        if (pc.connectionState === "connected") {
          setIsConnected(true);
          setIsConnecting(false);
        } else if (pc.connectionState === "disconnected" || pc.connectionState === "failed") {
          setIsConnected(false);
          setIsConnecting(false);
          setError(`Connection ${pc.connectionState}`);
        }
      };

      // 4. Handle trickle ICE candidates
      pc.onicecandidate = async (event) => {
        if (!event.candidate) {
          // End of candidate gathering
          return;
        }

        const candidatePayload = {
          session_id: sessionId,
          candidate: {
            candidate: event.candidate.candidate,
            sdpMid: event.candidate.sdpMid,
            sdpMLineIndex: event.candidate.sdpMLineIndex,
            usernameFragment: event.candidate.usernameFragment,
          },
        };

        try {
          await fetch(`${baseUrl}/api/webrtc/ice`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(candidatePayload),
          });
        } catch (err) {
          console.warn("[WebRTC] Failed to forward ICE candidate to backend:", err);
        }
      };

      // 5. Create local offer and set local description
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);

      // 6. Negotiate SDP with FastAPI backend
      const offerResponse = await fetch(`${baseUrl}/api/webrtc/offer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          sdp: offer.sdp,
          type: offer.type,
          fps,
          pixel_format: pixelFormat,
        }),
      });

      if (!offerResponse.ok) {
        const errorText = await offerResponse.text();
        throw new Error(`SDP negotiation failed (${offerResponse.status}): ${errorText}`);
      }

      const answer = await offerResponse.json();

      if (!answer.sdp || !answer.type) {
        throw new Error("Invalid SDP answer payload returned by backend.");
      }

      // 7. Set remote description
      await pc.setRemoteDescription(
        new RTCSessionDescription({
          type: answer.type,
          sdp: answer.sdp,
        })
      );

      // Flush any queued ICE candidates if needed
      while (pendingCandidatesRef.current.length > 0) {
        const cand = pendingCandidatesRef.current.shift();
        if (cand) {
          await pc.addIceCandidate(new RTCIceCandidate(cand));
        }
      }
    } catch (err) {
      if (isDestroyedRef.current) return;
      const message = err instanceof Error ? err.message : String(err);
      console.error("[WebRTC] Connection failed:", message);
      setError(message);
      setIsConnecting(false);
      setIsConnected(false);
    }
  }, [baseUrl, sessionId, fps, pixelFormat, bindDataChannel, disconnect]);

  const reconnect = useCallback(() => {
    connect();
  }, [connect]);

  useEffect(() => {
    isDestroyedRef.current = false;
    if (autoConnect) {
      connect();
    }

    return () => {
      isDestroyedRef.current = true;
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    videoTrack,
    mediaStream,
    isConnected,
    isConnecting,
    connectionState,
    error,
    agentCursor,
    sendControlEvent,
    reconnect,
    disconnect,
  };
}
