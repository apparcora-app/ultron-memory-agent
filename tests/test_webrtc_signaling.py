"""
test_webrtc_signaling.py — Verification Test Suite for WebRTC Streaming Bridge.

Tests:
  1. SDP offer/answer negotiation via POST /api/webrtc/offer (valid SDP answer + client remote desc).
  2. Trickle ICE candidate ingestion via POST /api/webrtc/ice (success and 404 non-existent session).
  3. BrowserStreamTrack frame ingestion, base64 decoding, bounded queue frame dropping (maxsize=2).
  4. BrowserStreamTrack frame decoding to av.VideoFrame (yuv420p) with monotonic timestamps.
  5. Standby fallback frame generation on idle BrowserStreamTrack.
  6. RTCDataChannel 'control' message parsing and normalized coordinate mapping to Playwright Page.
  7. Agent cursor telemetry (AGENT_CURSOR) broadcasting over 'control' RTCDataChannel.
  8. Session lifecycle teardown and resource cleanup.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
from pathlib import Path
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import av
from aiortc import RTCPeerConnection, RTCSessionDescription
from fastapi.testclient import TestClient
import PIL.Image
import pytest

# Ensure ultron-memory-agent root is in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import app
from ultron.streaming.browser_stream_track import BrowserStreamTrack
from ultron.streaming.webrtc_bridge import WebRTCBridgeManager, webrtc_bridge_manager


def _create_sample_jpeg_bytes(width: int = 100, height: int = 100, color: tuple[int, int, int] = (255, 0, 0)) -> bytes:
    """Helper to generate in-memory JPEG bytes for testing screencast frames."""
    img = PIL.Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def cleanup_webrtc_sessions():
    """Ensure all WebRTC sessions are cleanly closed before and after each test."""
    yield
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(webrtc_bridge_manager.close_all())
        loop.close()
    except Exception:
        pass


# ── Test 1: WebRTC Offer/Answer Signaling via FastAPI ────────────────────────

def test_webrtc_offer_and_answer_signaling():
    """Test full SDP offer/answer negotiation over HTTP endpoint POST /api/webrtc/offer."""
    client = TestClient(app); client.headers.update({"X-API-Key": os.environ.get("TEST_API_KEY", "")})

    async def _negotiate():
        client_pc = RTCPeerConnection()
        client_pc.addTransceiver("video", direction="recvonly")
        client_pc.createDataChannel("control")
        offer = await client_pc.createOffer()
        await client_pc.setLocalDescription(offer)

        # POST /api/webrtc/offer
        resp = client.post(
            "/api/webrtc/offer",
            json={
                "session_id": "test_sig_session_01",
                "sdp": offer.sdp,
                "type": offer.type,
                "fps": 30,
                "pixel_format": "yuv420p",
            },
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()

        assert "sdp" in data
        assert data["type"] == "answer"
        assert "v=0" in data["sdp"]
        assert "m=video" in data["sdp"]

        # Client accepts answer and sets remote description
        answer_desc = RTCSessionDescription(sdp=data["sdp"], type=data["type"])
        await client_pc.setRemoteDescription(answer_desc)

        assert client_pc.remoteDescription is not None
        assert client_pc.remoteDescription.type == "answer"

        await asyncio.sleep(0.05)
        await client_pc.close()
        await webrtc_bridge_manager.close_session("test_sig_session_01")

    asyncio.run(_negotiate())


# ── Test 2: Trickle ICE Candidate Routing ────────────────────────────────────

def test_webrtc_ice_trickle_exchange():
    """Test ICE candidate ingestion via POST /api/webrtc/ice."""
    client = TestClient(app); client.headers.update({"X-API-Key": os.environ.get("TEST_API_KEY", "")})

    async def _setup_session():
        client_pc = RTCPeerConnection()
        client_pc.addTransceiver("video", direction="recvonly")
        client_pc.createDataChannel("control")
        offer = await client_pc.createOffer()
        await client_pc.setLocalDescription(offer)

        resp = client.post(
            "/api/webrtc/offer",
            json={
                "session_id": "test_ice_session_02",
                "sdp": offer.sdp,
                "type": offer.type,
            },
        )
        assert resp.status_code == 200
        await client_pc.close()

    asyncio.run(_setup_session())

    # Send a valid candidate
    resp_ice = client.post(
        "/api/webrtc/ice",
        json={
            "session_id": "test_ice_session_02",
            "candidate": {
                "candidate": "candidate:1 1 UDP 2130706431 127.0.0.1 50000 typ host",
                "sdpMid": "0",
                "sdpMLineIndex": 0,
            },
        },
    )
    assert resp_ice.status_code == 200
    assert resp_ice.json() == {"status": "ok", "session_id": "test_ice_session_02"}

    # Send an end-of-candidates notification
    resp_end = client.post(
        "/api/webrtc/ice",
        json={
            "session_id": "test_ice_session_02",
            "candidate": {"candidate": ""},
        },
    )
    assert resp_end.status_code == 200

    # Send to a non-existent session -> 404
    resp_404 = client.post(
        "/api/webrtc/ice",
        json={
            "session_id": "non_existent_session_999",
            "candidate": {"candidate": "candidate:1 1 UDP 2130706431 127.0.0.1 50000 typ host"},
        },
    )
    assert resp_404.status_code == 404


# ── Test 3: BrowserStreamTrack Frame Queue & Stale Dropping ──────────────────

def test_browser_stream_track_frame_queue_and_drop():
    """Verify that BrowserStreamTrack drops stale frames when queue exceeds maxsize=2."""
    track = BrowserStreamTrack(fps=30, queue_maxsize=2)
    assert track._queue.qsize() == 0

    frame1 = _create_sample_jpeg_bytes(50, 50, (255, 0, 0))
    frame2 = _create_sample_jpeg_bytes(50, 50, (0, 255, 0))
    frame3 = _create_sample_jpeg_bytes(50, 50, (0, 0, 255))
    frame4 = _create_sample_jpeg_bytes(50, 50, (255, 255, 255))

    # Push 4 frames into queue of maxsize=2
    track.push_frame(frame1)
    track.push_frame(frame2)
    assert track._queue.qsize() == 2

    # Pushing 3rd and 4th frames drops older frames without error or blocking
    track.push_frame(frame3)
    track.push_frame(frame4)
    assert track._queue.qsize() == 2

    # Verify base64 string ingestion
    b64_frame = base64.b64encode(frame1).decode("utf-8")
    track.push_frame(b64_frame)
    assert track._queue.qsize() == 2


# ── Test 4: BrowserStreamTrack Frame Production & Standby ────────────────────

def test_browser_stream_track_recv_and_standby():
    """Verify recv() returns av.VideoFrame formatted to yuv420p with monotonic timestamps."""
    async def _test_recv():
        track = BrowserStreamTrack(fps=60, pixel_format="yuv420p", width=640, height=480)

        # 1. Without pushing frames, recv() produces a valid standby frame
        standby_frame = await track.recv()
        assert isinstance(standby_frame, av.VideoFrame)
        assert standby_frame.format.name == "yuv420p"
        assert standby_frame.pts == 0
        assert standby_frame.time_base.denominator == 90000

        # 2. Push a frame and verify decoding
        sample_jpeg = _create_sample_jpeg_bytes(640, 480, (120, 200, 255))
        track.push_frame(sample_jpeg)

        decoded_frame = await track.recv()
        assert isinstance(decoded_frame, av.VideoFrame)
        assert decoded_frame.format.name == "yuv420p"
        assert decoded_frame.width == 640
        assert decoded_frame.height == 480
        assert decoded_frame.pts > standby_frame.pts  # Monotonically increasing PTS

        # 3. Stop screencast
        await track.stop_screencast()
        assert not track._running

    asyncio.run(_test_recv())


# ── Test 5: RTCDataChannel Control Message Routing to Playwright Page ────────

def test_control_channel_remote_control_events():
    """Verify CLICK, MOUSE_MOVE, KEY_DOWN, KEY_UP, TYPE events are mapped to Playwright Page."""
    manager = WebRTCBridgeManager()
    session_id = "test_ctrl_session_03"

    mock_page = MagicMock()
    mock_page.viewport_size = {"width": 1000, "height": 800}
    mock_page.mouse.click = AsyncMock()
    mock_page.mouse.move = AsyncMock()
    mock_page.mouse.down = AsyncMock()
    mock_page.mouse.up = AsyncMock()
    mock_page.mouse.wheel = AsyncMock()
    mock_page.keyboard.down = AsyncMock()
    mock_page.keyboard.up = AsyncMock()
    mock_page.keyboard.type = AsyncMock()

    manager.pages[session_id] = mock_page

    async def _dispatch_events():
        # 1. CLICK event at normalized (0.5, 0.25) -> (500.0, 200.0)
        await manager._process_control_message(
            session_id,
            json.dumps({"type": "CLICK", "x": 0.5, "y": 0.25, "button": "left"}),
        )
        mock_page.mouse.click.assert_awaited_once_with(500.0, 200.0, button="left", click_count=1)

        # 2. MOUSE_MOVE at normalized (0.8, 0.1) -> (800.0, 80.0)
        await manager._process_control_message(
            session_id,
            json.dumps({"type": "MOUSE_MOVE", "x": 0.8, "y": 0.1}),
        )
        mock_page.mouse.move.assert_awaited_once_with(800.0, 80.0)

        # 3. KEY_DOWN & KEY_UP
        await manager._process_control_message(
            session_id,
            json.dumps({"type": "KEY_DOWN", "key": "Enter"}),
        )
        mock_page.keyboard.down.assert_awaited_once_with("Enter")

        await manager._process_control_message(
            session_id,
            json.dumps({"type": "KEY_UP", "key": "Enter"}),
        )
        mock_page.keyboard.up.assert_awaited_once_with("Enter")

        # 4. TYPE
        await manager._process_control_message(
            session_id,
            json.dumps({"type": "TYPE", "text": "Deploy Ultron"}),
        )
        mock_page.keyboard.type.assert_awaited_once_with("Deploy Ultron")

        # 5. SCROLL / WHEEL
        await manager._process_control_message(
            session_id,
            json.dumps({"type": "SCROLL", "delta_x": 0.0, "delta_y": 120.0}),
        )
        mock_page.mouse.wheel.assert_awaited_once_with(0.0, 120.0)

    asyncio.run(_dispatch_events())


# ── Test 6: Agent Cursor Telemetry Broadcast ─────────────────────────────────

def test_agent_cursor_telemetry_broadcast():
    """Verify AGENT_CURSOR telemetry packets are sent across the control RTCDataChannel."""
    manager = WebRTCBridgeManager()
    session_id = "test_telemetry_session_04"

    mock_dc = MagicMock()
    mock_dc.readyState = "open"
    mock_dc.send = MagicMock()

    manager.data_channels[session_id] = mock_dc

    success = manager.broadcast_agent_cursor(
        session_id=session_id,
        x=0.45,
        y=0.65,
        active=True,
        label="Autonomous Planner",
    )
    assert success is True
    mock_dc.send.assert_called_once()

    sent_payload = json.loads(mock_dc.send.call_args[0][0])
    assert sent_payload["type"] == "AGENT_CURSOR"
    assert sent_payload["x"] == 0.45
    assert sent_payload["y"] == 0.65
    assert sent_payload["active"] is True
    assert sent_payload["label"] == "Autonomous Planner"
    assert "timestamp" in sent_payload


# ── Test 7: WebRTC Bridge Session Teardown & Cleanup ─────────────────────────

def test_webrtc_session_cleanup():
    """Verify close_session cleanly tears down connections, tracks, and channels."""
    async def _test_teardown():
        manager = WebRTCBridgeManager()
        session_id = "test_cleanup_session_05"

        client_pc = RTCPeerConnection()
        client_pc.addTransceiver("video", direction="recvonly")
        client_pc.createDataChannel("control")
        offer = await client_pc.createOffer()
        await client_pc.setLocalDescription(offer)

        ans = await manager.handle_offer(session_id, sdp=offer.sdp, sdp_type=offer.type)
        assert session_id in manager.pcs
        assert session_id in manager.tracks
        assert session_id in manager.data_channels

        # Close session
        await manager.close_session(session_id)
        assert session_id not in manager.pcs
        assert session_id not in manager.tracks
        assert session_id not in manager.data_channels
        assert session_id not in manager.pages

        await client_pc.close()

    asyncio.run(_test_teardown())
