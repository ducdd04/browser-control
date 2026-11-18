"""
MVP-35 & MVP-38: Chuẩn hóa Cách Chờ Xong & Bộ Nhận Diện Success/Failure.
Owner: Role D (Browser Control).

- MVP-35: Chuẩn hóa định nghĩa chờ xong (Settle Strategy) thống nhất giữa các engine
  (Network Idle / DOM Stable / Visual Stable) để đảm bảo độ trễ đo được đồng nhất.
- MVP-38: Nhận diện tự động đặt bàn thành công hay thất bại từ artifact (ảnh, HAR, HTML)
  và định nghĩa đường thoát rõ ràng khi cả 4 cấp fail, không bao giờ để treo phiên.
"""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Any, Dict, Optional


class SettleStrategy(str, Enum):
    NETWORK_IDLE = "network_idle"        # Chờ không còn request HTTP bay đi (> 500ms)
    DOM_STABLE = "dom_stable"            # Chờ MutationObserver không còn node thay đổi
    VISUAL_STABLE = "visual_stable"      # Chờ pixel màn hình không đổi giữa 2 frame


class FailureReason(str, Enum):
    WAF_BLOCKED = "WAF_BLOCKED"                  # Cloudflare / WAF chặn IP/captcha
    SELECTOR_NOT_FOUND = "SELECTOR_NOT_FOUND"    # DOM đổi, kịch bản cũ không khớp
    OTP_REQUIRED = "OTP_REQUIRED"                # Yêu cầu nhập OTP (cần HITL)
    TIMEOUT = "TIMEOUT"                          # Hết thời gian chờ phản hồi
    ALL_TIERS_EXHAUSTED = "ALL_TIERS_EXHAUSTED"  # Cả 4 cấp đều không thể xử lý


@dataclass
class SettleConfig:
    strategy: SettleStrategy = SettleStrategy.DOM_STABLE
    timeout_ms: int = 5000
    poll_interval_ms: int = 100


class BookingResultDetector:
    """MVP-38: Bộ phân loại tự động thành công/thất bại dựa trên artifacts."""

    SUCCESS_KEYWORDS = [
        "đặt bàn thành công",
        "cảm ơn quý khách",
        "mã đặt bàn",
        "booking confirmed",
        "thông tin đặt bàn của bạn đã được gửi",
    ]

    FAILURE_KEYWORDS = [
        "hết bàn",
        "đã kín chỗ",
        "vui lòng chọn giờ khác",
        "lỗi hệ thống",
        "số điện thoại không hợp lệ",
    ]

    @classmethod
    def evaluate_page_content(cls, html_content: str) -> Dict[str, Any]:
        """Phân tích nội dung trang sau khi bấm gửi để xác định trạng thái."""
        content_lower = html_content.lower()

        # Kiểm tra thành công
        for kw in cls.SUCCESS_KEYWORDS:
            if kw in content_lower:
                return {
                    "is_success": True,
                    "confidence": 0.95,
                    "reason": f"Phát hiện tín hiệu thành công: '{kw}'",
                }

        # Kiểm tra thất bại
        for kw in cls.FAILURE_KEYWORDS:
            if kw in content_lower:
                return {
                    "is_success": False,
                    "confidence": 0.90,
                    "reason": f"Phát hiện tín hiệu hết bàn / lỗi: '{kw}'",
                    "error_code": "SITE_REJECTED",
                }

        # Nếu không có tín hiệu rõ ràng
        return {
            "is_success": False,
            "confidence": 0.50,
            "reason": "Không tìm thấy thông điệp xác nhận rõ ràng trên trang.",
            "error_code": "UNCERTAIN_OUTCOME",
        }
