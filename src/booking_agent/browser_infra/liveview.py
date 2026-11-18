"""
MVP-27 & MVP-28: Live View HITL mức tối giản & UI Khách.
Owner: Role D (Browser Control).

Dùng để stream ảnh màn hình (1–2 ảnh/giây) qua WebSocket hoặc SSE khi agent gặp
tình huống nhạy cảm (nhập OTP, quét mã QR cọc tiền) để khách hàng tự tương tác
trực tiếp (Human-in-the-loop - HITL) mà không làm lộ profile hay môi trường kỹ thuật.
"""

import asyncio
import base64
import time
from dataclasses import dataclass
from typing import AsyncGenerator, Callable, Dict, Optional


@dataclass
class LiveViewFrame:
    session_id: str
    timestamp_ms: int
    image_base64: str
    width: int
    height: int
    hitl_required: bool = False
    hitl_reason: Optional[str] = None  # "OTP_REQUIRED" | "QR_DEPOSIT_REQUIRED"


class LiveViewStreamer:
    """Stream ảnh màn hình định kỳ cho giao diện khách hàng (MVP-27/28)."""

    def __init__(self, session_id: str, fps: float = 1.5):
        self.session_id = session_id
        self.interval = 1.0 / fps
        self._is_running = False
        self._last_frame: Optional[LiveViewFrame] = None

    async def stream_frames(
        self,
        capture_fn: Callable[[], asyncio.Future],
        hitl_checker: Optional[Callable[[], Optional[str]]] = None,
    ) -> AsyncGenerator[LiveViewFrame, None]:
        """Tạo generator phát ảnh màn hình liên tục với độ trễ thấp (< 200 ms)."""
        self._is_running = True
        while self._is_running:
            t_start = time.perf_counter()
            try:
                # Chụp ảnh viewport (bytes PNG/JPEG)
                raw_bytes = await capture_fn()
                b64_data = base64.b64encode(raw_bytes).decode("ascii")

                # Kiểm tra xem có cần khách can thiệp (OTP/QR) không
                hitl_reason = hitl_checker() if hitl_checker else None

                frame = LiveViewFrame(
                    session_id=self.session_id,
                    timestamp_ms=int(time.time() * 1000),
                    image_base64=b64_data,
                    width=1280,
                    height=720,
                    hitl_required=hitl_reason is not None,
                    hitl_reason=hitl_reason,
                )
                self._last_frame = frame
                yield frame
            except Exception:
                pass

            # Đảm bảo đúng nhịp FPS không gây nghẽn CPU
            elapsed = time.perf_counter() - t_start
            sleep_time = max(0.05, self.interval - elapsed)
            await asyncio.sleep(sleep_time)

    def stop(self) -> None:
        self._is_running = False
