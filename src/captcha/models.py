"""Data models cho captcha solver pipeline."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class CaptchaType(enum.Enum):
    """Phân loại CAPTCHA theo cơ chế."""
    TEXT_OCR = "text_ocr"           # Chữ / số biến dạng
    IMAGE_GRID = "image_grid"       # Grid chọn ảnh (reCAPTCHA v2 style)
    IMAGE_CLICK = "image_click"     # Click vào điểm trên ảnh
    SLIDER = "slider"               # Kéo slider ghép hình
    ROTATE = "rotate"               # Xoay hình
    UNKNOWN = "unknown"


class SolveStatus(enum.Enum):
    """Trạng thái sau khi thử giải."""
    SOLVED = "solved"               # Captcha đã qua
    FAILED = "failed"               # Giải sai, còn captcha mới
    NEED_HUMAN = "need_human"       # Hết retry, cần người xử lý
    NO_CAPTCHA = "no_captcha"       # Không phát hiện captcha trên trang
    TIMEOUT = "timeout"             # Hết thời gian chờ


@dataclass
class BoundingBox:
    """Vùng captcha trên viewport."""
    x: float
    y: float
    width: float
    height: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)


@dataclass
class CaptchaPlan:
    """Kế hoạch hành động trả về từ model nhận dạng.

    Với mỗi loại captcha, các trường được dùng khác nhau:
    - TEXT_OCR:    text_answer = "abc123"
    - IMAGE_GRID:  grid_cells = [2, 5, 8]  (index ô cần click)
    - IMAGE_CLICK: click_points = [(0.35, 0.72), ...]  (tọa độ chuẩn hóa 0-1)
    - SLIDER:      slider_offset = 0.65  (tỷ lệ chiều rộng)
    """
    captcha_type: CaptchaType
    text_answer: str = ""
    grid_cells: list[int] = field(default_factory=list)
    click_points: list[tuple[float, float]] = field(default_factory=list)
    slider_offset: float = 0.0
    confidence: float = 0.0
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass
class SolveResult:
    """Kết quả cuối cùng của pipeline giải captcha."""
    status: SolveStatus
    tier_used: int = 0              # 1, 2, 3 — tầng nào đã xử lý
    attempts: int = 0               # Số lần thử
    screenshot_path: str = ""       # Ảnh chụp trạng thái cuối
    message: str = ""
    plan: CaptchaPlan | None = None
