"""
MVP-36: CDP Network Sniffer (Seam tự học).
Owner: Role D (Browser Control).

Listener bắt các request XHR / Fetch tại thời điểm người dùng hoặc AI bấm "Xác nhận đặt bàn".
Ghi lại URL endpoint, phương thức HTTP, headers và payload JSON thô.
Dữ liệu này được lưu trữ để sau này LLM biên dịch ngược thành API Template (Cấp 1).
Trong MVP: chỉ ghi nhận dữ liệu thô, không biên dịch tự động.
"""

from dataclasses import dataclass, field
import json
import time
from typing import Any, Dict, List, Optional


@dataclass
class SniffedNetworkCall:
    url: str
    method: str
    request_headers: Dict[str, str]
    post_data: Optional[str]
    timestamp_ms: int
    status_code: Optional[int] = None
    response_body: Optional[str] = None


class CDPNetworkSniffer:
    """Lắng nghe và ghi nhận các cuộc gọi API đặt bàn qua CDP Network domain."""

    def __init__(self):
        self.captured_calls: List[SniffedNetworkCall] = []
        self._is_active = False

    def start_capture(self) -> None:
        self._is_active = True
        self.captured_calls.clear()

    def record_request(
        self,
        url: str,
        method: str,
        headers: Dict[str, str],
        post_data: Optional[str] = None,
    ) -> None:
        if not self._is_active:
            return

        # Lọc các request liên quan đến đặt bàn / booking API
        keywords = ["dat-ban", "booking", "reserve", "api", "order"]
        if any(kw in url.lower() for kw in keywords):
            call = SniffedNetworkCall(
                url=url,
                method=method,
                request_headers=headers,
                post_data=post_data,
                timestamp_ms=int(time.time() * 1000),
            )
            self.captured_calls.append(call)

    def stop_capture(self) -> List[SniffedNetworkCall]:
        self._is_active = False
        return list(self.captured_calls)

    def export_raw_template(self) -> Optional[Dict[str, Any]]:
        """Xuất payload thô để lưu vào Registry."""
        if not self.captured_calls:
            return None

        # Lấy call dạng POST gần nhất
        for call in reversed(self.captured_calls):
            if call.method.upper() == "POST":
                return {
                    "endpoint": call.url,
                    "method": call.method,
                    "sample_payload": call.post_data,
                    "captured_at": call.timestamp_ms,
                }
        return None
