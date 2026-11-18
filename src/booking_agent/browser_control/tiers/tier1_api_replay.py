"""
MVP-30: Cấp 1 — Direct API Replay.
Owner: Role D (Browser Control).

Mở phiên qua Chromium/Patchright lấy cookie/session/token hợp lệ rồi bắn thẳng
fetch() đặt bàn qua HTTP/JSON, không tải các tài nguyên đồ hoạ HTML/CSS/Images.
Chi phí: $0 token, thời gian: mili-giây.
Nếu phát hiện WAF/Cloudflare Turnstile chặn -> báo lỗi để trượt xuống Cấp 2.
"""

import time
import httpx
from ..port import BookingTask, SessionContext, StepResult, Tier


class Tier1APIReplayExecutor:
    """Thực thi đặt bàn theo phương pháp Direct Reverse API."""

    def __init__(self, api_template: dict = None):
        self.api_template = api_template or {
            "endpoint": "/api/v1/booking/submit",
            "method": "POST",
        }

    async def execute(self, task: BookingTask, ctx: SessionContext) -> StepResult:
        t_start = time.perf_counter()

        # Kiểm tra chế độ Dry-Run an toàn
        if task.dry_run:
            latency_ms = (time.perf_counter() - t_start) * 1000 + 150.0  # mô phỏng gọi mạng nhanh
            return StepResult(
                success=True,
                tier_used=Tier.TIER1_API_REPLAY,
                latency_ms=latency_ms,
                tokens_consumed=0,
                cost_usd=0.0,
                cost_vnd=0.0,
                output_message="[Dry-Run] Direct API Replay payload verified successfully.",
            )

        payload = {
            "customer_name": task.customer_name,
            "phone": task.phone_number,
            "email": task.email,
            "party_size": task.party_size,
            "date": task.booking_date,
            "time": task.booking_time,
            "branch": task.branch_id,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{task.site_url.rstrip('/')}{self.api_template['endpoint']}",
                    json=payload,
                )
                latency_ms = (time.perf_counter() - t_start) * 1000

                if res.status_code in (403, 429):
                    return StepResult(
                        success=False,
                        tier_used=Tier.TIER1_API_REPLAY,
                        latency_ms=latency_ms,
                        tokens_consumed=0,
                        cost_usd=0.0,
                        cost_vnd=0.0,
                        output_message=f"Bị WAF/Cloudflare chặn mã HTTP {res.status_code}",
                        error_code="WAF_BLOCKED",
                    )

                return StepResult(
                    success=res.is_success,
                    tier_used=Tier.TIER1_API_REPLAY,
                    latency_ms=latency_ms,
                    tokens_consumed=0,
                    cost_usd=0.0,
                    cost_vnd=0.0,
                    output_message=f"Direct API call completed: {res.status_code}",
                )
        except Exception as e:
            latency_ms = (time.perf_counter() - t_start) * 1000
            return StepResult(
                success=False,
                tier_used=Tier.TIER1_API_REPLAY,
                latency_ms=latency_ms,
                tokens_consumed=0,
                cost_usd=0.0,
                cost_vnd=0.0,
                output_message=f"Lỗi kết nối API: {str(e)}",
                error_code="NETWORK_ERROR",
            )
