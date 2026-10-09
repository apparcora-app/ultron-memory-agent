"""
browser_stream_track.py — WebRTC VideoStreamTrack for Browser Screencast Streaming.

Subclasses aiortc.VideoStreamTrack to ingest Playwright CDP screencast frame buffers,
maintain low latency via a bounded queue with stale-frame dropping, and decode
frames into av.VideoFrame (yuv420p / bgr24) with monotonic timestamps up to 60 FPS.
"""

from __future__ import annotations

import asyncio
import base64
import fractions
import io
import logging
import time
from typing import Any, Dict, Optional, Tuple, Union

import av
import PIL.Image
from aiortc import VideoStreamTrack
from aiortc.mediastreams import MediaStreamError, VIDEO_CLOCK_RATE

logger = logging.getLogger(__name__)

DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720
DEFAULT_FPS = 30
MAX_FPS = 60
QUEUE_MAXSIZE = 2


class BrowserStreamTrack(VideoStreamTrack):
    """
    Subclasses aiortc.VideoStreamTrack to stream live browser execution over WebRTC.

    Key Features:
      - Low-latency queue with maxsize=2 dropping stale frames.
      - Paces frame output up to 60 FPS with monotonic timestamps.
      - Converts JPEG/PNG CDP screencast buffers into av.VideoFrame (yuv420p / bgr24).
      - Integrates with Playwright CDP session (Page.startScreencast / Page.screencastFrameAck).
    """

    kind = "video"

    def __init__(
        self,
        fps: int = DEFAULT_FPS,
        pixel_format: str = "yuv420p",
        queue_maxsize: int = QUEUE_MAXSIZE,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> None:
        super().__init__()
        self.fps = min(max(1, int(fps)), MAX_FPS)
        self.pixel_format = pixel_format.lower()
        if self.pixel_format not in ("yuv420p", "bgr24", "rgb24"):
            self.pixel_format = "yuv420p"

        self.width = width
        self.height = height
        self._queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=queue_maxsize)
        self._last_frame: Optional[av.VideoFrame] = None
        self._page: Any = None
        self._cdp_session: Any = None
        self._running: bool = True
        self._timestamp: int = 0
        self._start: Optional[float] = None

    def push_frame(self, frame_buffer: Union[bytes, str]) -> None:
        """
        Ingest a screencast frame buffer (raw bytes or base64 string).
        Maintains queue maxsize=2, dropping the oldest frame if full to prevent playback delay.
        """
        if not self._running:
            return

        if isinstance(frame_buffer, str):
            try:
                raw_bytes = base64.b64decode(frame_buffer)
            except Exception as exc:
                logger.warning("Failed to decode base64 screencast frame buffer: %s", exc)
                return
        else:
            raw_bytes = frame_buffer

        # If queue is full, drop oldest stale frame immediately to maintain near-zero latency
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass

        try:
            self._queue.put_nowait(raw_bytes)
        except asyncio.QueueFull:
            pass

    async def next_timestamp(self) -> Tuple[int, fractions.Fraction]:
        """
        Paces frames and returns (pts, time_base) with monotonic timestamps
        calibrated for up to 60 FPS WebRTC streaming.
        """
        if self.readyState != "live":
            raise MediaStreamError

        ptime = 1.0 / self.fps
        step = int(ptime * VIDEO_CLOCK_RATE)
        now = time.time()

        if self._start is None:
            self._start = now
            self._timestamp = 0
        else:
            self._timestamp += step
            wait = self._start + (self._timestamp / VIDEO_CLOCK_RATE) - now
            if wait > 0:
                await asyncio.sleep(wait)

        return self._timestamp, fractions.Fraction(1, VIDEO_CLOCK_RATE)

    def _decode_buffer_to_frame(self, raw_bytes: bytes) -> av.VideoFrame:
        """Decode JPEG/PNG bytes into an av.VideoFrame formatted to target pixel_format."""
        img = PIL.Image.open(io.BytesIO(raw_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        vf = av.VideoFrame.from_image(img)
        if vf.format.name != self.pixel_format:
            vf = vf.reformat(format=self.pixel_format)
        return vf

    def _create_blank_frame(self) -> av.VideoFrame:
        """Generate a standby frame if no screencast frame has arrived yet."""
        img = PIL.Image.new("RGB", (self.width, self.height), color=(18, 24, 38))
        vf = av.VideoFrame.from_image(img)
        if vf.format.name != self.pixel_format:
            vf = vf.reformat(format=self.pixel_format)
        return vf

    async def recv(self) -> av.VideoFrame:
        """
        Produce and return the next av.VideoFrame at up to self.fps (up to 60 FPS)
        with monotonic presentation timestamps.
        """
        if not self._running:
            raise MediaStreamError

        pts, time_base = await self.next_timestamp()

        # Check for new screencast frame
        try:
            raw_bytes = self._queue.get_nowait()
            video_frame = self._decode_buffer_to_frame(raw_bytes)
            self._last_frame = video_frame
        except asyncio.QueueEmpty:
            # If idle (e.g. static webpage), re-serve the last frame or standby canvas
            if self._last_frame is not None:
                video_frame = self._last_frame
            else:
                video_frame = self._create_blank_frame()
                self._last_frame = video_frame
        except Exception as exc:
            logger.warning("Error decoding screencast frame: %s", exc)
            if self._last_frame is not None:
                video_frame = self._last_frame
            else:
                video_frame = self._create_blank_frame()

        if video_frame.format.name != self.pixel_format:
            frame = video_frame.reformat(format=self.pixel_format)
        else:
            frame = av.VideoFrame.from_ndarray(
                video_frame.to_ndarray(format=self.pixel_format),
                format=self.pixel_format,
            )

        frame.pts = pts
        frame.time_base = time_base
        return frame

    async def attach_page(self, page: Any) -> None:
        """
        Attach to a Playwright Page instance, starting CDP screencasting.
        """
        self._page = page
        context = getattr(page, "context", None)
        if context is None or not hasattr(context, "new_cdp_session"):
            logger.warning("Provided page does not support new_cdp_session.")
            return

        self._cdp_session = await context.new_cdp_session(page)

        async def on_screencast_frame(payload: Dict[str, Any]) -> None:
            data = payload.get("data")
            session_id = payload.get("sessionId")
            if data:
                self.push_frame(data)
            if session_id is not None and self._cdp_session is not None:
                try:
                    await self._cdp_session.send(
                        "Page.screencastFrameAck",
                        {"sessionId": session_id},
                    )
                except Exception:
                    pass

        self._cdp_session.on("Page.screencastFrame", on_screencast_frame)
        await self._cdp_session.send(
            "Page.startScreencast",
            {
                "format": "jpeg",
                "quality": 80,
                "maxWidth": self.width,
                "maxHeight": self.height,
                "everyNthFrame": 1,
            },
        )
        logger.info("CDP Screencast started for WebRTC BrowserStreamTrack.")

    async def stop_screencast(self) -> None:
        """Stop CDP screencast and release resources."""
        self._running = False
        if self._cdp_session is not None:
            try:
                await self._cdp_session.send("Page.stopScreencast")
                await self._cdp_session.detach()
            except Exception:
                pass
            self._cdp_session = None
        self._page = None
