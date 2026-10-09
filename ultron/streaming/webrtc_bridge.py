"""
webrtc_bridge.py — WebRTC PeerConnection & DataChannel Manager for Browser Streaming.

Manages SDP offer/answer negotiation, ICE candidate lifecycle, track attachment,
and remote control over an RTCDataChannel ("control") mapping normalized user input
events (CLICK, KEY_DOWN, etc.) directly into Playwright page actions. Emits agent
cursor telemetry (AGENT_CURSOR) back to client for real-time visualization.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional

from aiortc import (
    RTCConfiguration,
    RTCDataChannel,
    RTCIceCandidate,
    RTCIceServer,
    RTCPeerConnection,
    RTCSessionDescription,
)
from aiortc.sdp import candidate_from_sdp

from ultron.streaming.browser_stream_track import BrowserStreamTrack

logger = logging.getLogger(__name__)

DEFAULT_ICE_SERVERS = ["stun:stun.l.google.com:19302"]


class WebRTCBridgeManager:
    """
    Manages WebRTC PeerConnections, BrowserStreamTracks, and RTCDataChannels
    for low-latency screencast streaming and bidirectional remote control.
    """

    def __init__(self, ice_servers: Optional[List[str]] = None) -> None:
        urls = ice_servers or DEFAULT_ICE_SERVERS
        self.ice_servers = [RTCIceServer(urls=urls)]
        self.pcs: Dict[str, RTCPeerConnection] = {}
        self.tracks: Dict[str, BrowserStreamTrack] = {}
        self.data_channels: Dict[str, RTCDataChannel] = {}
        self.pages: Dict[str, Any] = {}
        self._lock: Optional[asyncio.Lock] = None
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = None

    def _get_lock(self) -> asyncio.Lock:
        """Retrieve or initialize an asyncio.Lock bound to the currently running event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self._lock is None or self._lock_loop is not current_loop:
            self._lock = asyncio.Lock()
            self._lock_loop = current_loop
        return self._lock

    async def handle_offer(
        self,
        session_id: str,
        sdp: str,
        sdp_type: str = "offer",
        page: Optional[Any] = None,
        fps: int = 30,
        pixel_format: str = "yuv420p",
    ) -> Dict[str, str]:
        """
        Negotiate SDP offer/answer for session_id.
        Creates RTCPeerConnection, attaches a BrowserStreamTrack, creates/binds
        the 'control' data channel, and returns the SDP answer.
        """
        async with self._get_lock():
            # Clean up any existing connection for this session before re-negotiating
            if session_id in self.pcs:
                await self._close_session_unlocked(session_id)

            config = RTCConfiguration(iceServers=self.ice_servers)
            pc = RTCPeerConnection(configuration=config)
            self.pcs[session_id] = pc

            # Attach page if provided
            if page is not None:
                self.pages[session_id] = page

            # Instantiate track
            track = BrowserStreamTrack(fps=fps, pixel_format=pixel_format)
            self.tracks[session_id] = track

            if page is not None:
                try:
                    await track.attach_page(page)
                except Exception as exc:
                    logger.warning("Failed to attach track to page for session '%s': %s", session_id, exc)

            # Proactively create server-side 'control' data channel
            dc = pc.createDataChannel("control")
            self.setup_control_channel(session_id, dc)

            # Listen for client-created data channels
            @pc.on("datachannel")
            def on_datachannel(channel: RTCDataChannel) -> None:
                if channel.label == "control" or session_id not in self.data_channels:
                    self.setup_control_channel(session_id, channel)

            # Handle peer connection state transitions
            @pc.on("connectionstatechange")
            async def on_connectionstatechange() -> None:
                logger.info("Session '%s' WebRTC connection state changed to: %s", session_id, pc.connectionState)
                if pc.connectionState in ("failed", "closed"):
                    await self.close_session(session_id)

            # Negotiate SDP: set remote description first
            remote_desc = RTCSessionDescription(sdp=sdp, type=sdp_type)
            await pc.setRemoteDescription(remote_desc)

            # Attach video track to matched video transceiver if present
            video_transceivers = [t for t in pc.getTransceivers() if t.kind == "video"]
            if video_transceivers:
                video_transceivers[0].sender.replaceTrack(track)
                video_transceivers[0].direction = "sendonly"
            elif "m=video" in sdp:
                pc.addTrack(track)

            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)

            return {
                "sdp": pc.localDescription.sdp,
                "type": pc.localDescription.type,
            }

    def setup_control_channel(self, session_id: str, channel: RTCDataChannel) -> None:
        """
        Configure event handlers on the 'control' RTCDataChannel.
        Ingests mouse and keyboard events and forwards them to the Playwright page.
        """
        self.data_channels[session_id] = channel

        @channel.on("open")
        def on_open() -> None:
            logger.info("WebRTC 'control' RTCDataChannel open for session '%s'", session_id)

        @channel.on("close")
        def on_close() -> None:
            logger.info("WebRTC 'control' RTCDataChannel closed for session '%s'", session_id)
            if self.data_channels.get(session_id) is channel:
                self.data_channels.pop(session_id, None)

        @channel.on("message")
        def on_message(message: Any) -> None:
            asyncio.create_task(self._process_control_message(session_id, message))

    async def _process_control_message(self, session_id: str, raw_msg: Any) -> None:
        """Parse incoming JSON payload and dispatch remote control events to Playwright page."""
        try:
            if isinstance(raw_msg, bytes):
                text = raw_msg.decode("utf-8")
            else:
                text = str(raw_msg)
            payload = json.loads(text)
        except Exception as exc:
            logger.warning("Failed to parse control channel JSON message for session '%s': %s", session_id, exc)
            return

        msg_type = str(payload.get("type", "")).upper()
        page = self.pages.get(session_id)
        if page is None:
            logger.debug("Received '%s' but no page attached for session '%s'", msg_type, session_id)
            return

        # Viewport dimensions for mapping normalized [0.0, 1.0] coordinates
        width = 1280
        height = 720
        vp = getattr(page, "viewport_size", None)
        if callable(vp):
            try:
                vp_val = vp()
                if isinstance(vp_val, dict):
                    width = vp_val.get("width", width)
                    height = vp_val.get("height", height)
            except Exception:
                pass
        elif isinstance(vp, dict):
            width = vp.get("width", width)
            height = vp.get("height", height)

        try:
            if msg_type == "CLICK":
                x = float(payload.get("x", 0.0)) * width
                y = float(payload.get("y", 0.0)) * height
                button = payload.get("button", "left")
                click_count = int(payload.get("click_count", 1))
                mouse = getattr(page, "mouse", None)
                if mouse and hasattr(mouse, "click"):
                    await mouse.click(x, y, button=button, click_count=click_count)

            elif msg_type == "MOUSE_MOVE":
                x = float(payload.get("x", 0.0)) * width
                y = float(payload.get("y", 0.0)) * height
                mouse = getattr(page, "mouse", None)
                if mouse and hasattr(mouse, "move"):
                    await mouse.move(x, y)

            elif msg_type == "MOUSE_DOWN":
                x = float(payload.get("x", 0.0)) * width
                y = float(payload.get("y", 0.0)) * height
                button = payload.get("button", "left")
                mouse = getattr(page, "mouse", None)
                if mouse:
                    if hasattr(mouse, "move"):
                        await mouse.move(x, y)
                    if hasattr(mouse, "down"):
                        await mouse.down(button=button)

            elif msg_type == "MOUSE_UP":
                x = float(payload.get("x", 0.0)) * width
                y = float(payload.get("y", 0.0)) * height
                button = payload.get("button", "left")
                mouse = getattr(page, "mouse", None)
                if mouse:
                    if hasattr(mouse, "move"):
                        await mouse.move(x, y)
                    if hasattr(mouse, "up"):
                        await mouse.up(button=button)

            elif msg_type == "KEY_DOWN":
                key = payload.get("key")
                keyboard = getattr(page, "keyboard", None)
                if key and keyboard and hasattr(keyboard, "down"):
                    await keyboard.down(key)

            elif msg_type == "KEY_UP":
                key = payload.get("key")
                keyboard = getattr(page, "keyboard", None)
                if key and keyboard and hasattr(keyboard, "up"):
                    await keyboard.up(key)

            elif msg_type == "TYPE":
                text_to_type = payload.get("text", "")
                keyboard = getattr(page, "keyboard", None)
                if text_to_type and keyboard and hasattr(keyboard, "type"):
                    await keyboard.type(text_to_type)

            elif msg_type in ("SCROLL", "WHEEL"):
                dx = float(payload.get("delta_x", 0.0))
                dy = float(payload.get("delta_y", 0.0))
                mouse = getattr(page, "mouse", None)
                if mouse and hasattr(mouse, "wheel"):
                    await mouse.wheel(dx, dy)

            else:
                logger.debug("Unknown control message type '%s' for session '%s'", msg_type, session_id)

        except Exception as exc:
            logger.warning("Error executing control action '%s' for session '%s': %s", msg_type, session_id, exc)

    async def handle_ice_candidate(self, session_id: str, candidate_dict: Dict[str, Any]) -> bool:
        """
        Process trickle ICE candidate for session_id.
        Parses candidate string, applies sdpMid / sdpMLineIndex, and attaches to peer connection.
        """
        pc = self.pcs.get(session_id)
        if pc is None:
            logger.warning("Cannot add ICE candidate: no active connection for session '%s'", session_id)
            return False

        raw_cand = candidate_dict.get("candidate")
        if not raw_cand:
            # End of candidate gathering indicator
            return True

        if isinstance(raw_cand, str):
            if raw_cand.startswith("candidate:"):
                cand_str = raw_cand[len("candidate:"):]
            else:
                cand_str = raw_cand
        else:
            return True

        try:
            cand = candidate_from_sdp(cand_str)
            cand.sdpMid = candidate_dict.get("sdpMid")
            cand.sdpMLineIndex = candidate_dict.get("sdpMLineIndex")
            await pc.addIceCandidate(cand)
            return True
        except Exception as exc:
            logger.warning("Failed to add ICE candidate for session '%s': %s", session_id, exc)
            return False

    def broadcast_agent_cursor(
        self,
        session_id: str,
        x: float,
        y: float,
        active: bool = True,
        label: Optional[str] = None,
    ) -> bool:
        """
        Emit agent cursor telemetry (AGENT_CURSOR) over the 'control' RTCDataChannel
        to render autonomous agent cursor movements on the client HUD.
        """
        payload = {
            "type": "AGENT_CURSOR",
            "x": float(x),
            "y": float(y),
            "active": bool(active),
            "label": label or "Ultron Agent",
            "timestamp": time.time(),
        }
        return self.send_control_message(session_id, payload)

    def send_control_message(self, session_id: str, message: Dict[str, Any]) -> bool:
        """Send an arbitrary JSON message across the session's 'control' RTCDataChannel."""
        dc = self.data_channels.get(session_id)
        if dc and dc.readyState == "open":
            try:
                dc.send(json.dumps(message))
                return True
            except Exception as exc:
                logger.warning("Error sending message on control channel for session '%s': %s", session_id, exc)
                return False
        return False

    async def attach_page(self, session_id: str, page: Any) -> None:
        """Attach a Playwright page to an existing WebRTC session and begin screencasting."""
        self.pages[session_id] = page
        track = self.tracks.get(session_id)
        if track is not None:
            await track.attach_page(page)

    def get_track(self, session_id: str) -> Optional[BrowserStreamTrack]:
        """Return the active BrowserStreamTrack for session_id."""
        return self.tracks.get(session_id)

    def get_peer_connection(self, session_id: str) -> Optional[RTCPeerConnection]:
        """Return the active RTCPeerConnection for session_id."""
        return self.pcs.get(session_id)

    async def _close_session_unlocked(self, session_id: str) -> None:
        """Internal helper to close a session without locking self._lock."""
        track = self.tracks.pop(session_id, None)
        if track is not None:
            try:
                await track.stop_screencast()
            except Exception:
                pass

        dc = self.data_channels.pop(session_id, None)
        if dc is not None:
            try:
                dc.close()
            except Exception:
                pass

        pc = self.pcs.pop(session_id, None)
        if pc is not None:
            try:
                await pc.close()
            except Exception:
                pass

        self.pages.pop(session_id, None)
        logger.info("WebRTC session '%s' closed and cleaned up.", session_id)

    async def close_session(self, session_id: str) -> None:
        """Clean up and close WebRTC peer connection, track, and data channel for session_id."""
        async with self._get_lock():
            await self._close_session_unlocked(session_id)

    async def close_all(self) -> None:
        """Tear down all active WebRTC sessions."""
        async with self._get_lock():
            session_ids = list(self.pcs.keys())
            for session_id in session_ids:
                await self._close_session_unlocked(session_id)


# Module-level default singleton instance
webrtc_bridge_manager = WebRTCBridgeManager()
