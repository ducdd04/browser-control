"""
MVP-34: Hot-Swap Fallback không gián đoạn & Hợp đồng BrowserControlPort.
Owner: Role D (Browser Control).

Hợp đồng chính thức theo System Design v2.1 (Mục 3) kết nối Agent điều phối (Role C)
với tầng điều khiển trình duyệt (Role D), đồng thời tích hợp cơ chế trượt cấp
thông minh (Waterfall Fallback) giữa 4 cấp độ tự động hoá.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol
import time


class Tier(str, Enum):
    TIER1_API_REPLAY = "tier1_api_replay"      # Cấp 1: Direct API Replay
    TIER2_PLAYWRIGHT = "tier2_playwright"      # Cấp 2: Playwright Workflow tham số hóa
    TIER3_STAGEHAND = "tier3_stagehand"        # Cấp 3: Stagehand AI DOM Semantic
    TIER4_VISION = "tier4_vision"              # Cấp 4: Browser-Use + Multimodal Vision API


@dataclass
class BookingTask:
    site_url: str
    customer_name: str
    phone_number: str
    email: str
    party_size: int = 2
    booking_date: str = "2026-11-20"
    booking_time: str = "19:00"
    branch_id: Optional[str] = "2"
    dry_run: bool = True                       # Tuyệt đối không bấm nút gửi đặt bàn nếu dry_run=True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionContext:
    session_id: str
    cdp_url: str
    engine_name: str = "chromium"              # "chromium" hoặc "camoufox"
    page_instance: Optional[Any] = None        # Page object hiện tại (để hot-swap không reload)
    trace_id: Optional[str] = None
    artifacts_dir: Optional[str] = None


@dataclass
class StepResult:
    success: bool
    tier_used: Tier
    latency_ms: float
    tokens_consumed: int
    cost_usd: float
    cost_vnd: float
    output_message: str
    discovered_selectors: Optional[Dict[str, str]] = None
    screenshot_path: Optional[str] = None
    hitl_required: bool = False
    hitl_reason: Optional[str] = None
    error_code: Optional[str] = None


class BrowserControlPort(Protocol):
    """Protocol chuẩn giao tiếp giữa Agent (Role C) và Browser Control (Role D)."""

    async def execute(
        self,
        tier: Tier,
        task: BookingTask,
        ctx: SessionContext,
    ) -> StepResult:
        """Thực thi tác vụ theo cấp chỉ định."""
        ...


class AdaptiveFallbackOrchestrator:
    """
    MVP-34: Bộ điều phối Hot-Swap Fallback không gián đoạn.
    Khi cấp trên gặp lỗi giữa task, KHÔNG tắt trình duyệt làm lại từ đầu.
    Giữ nguyên trang ở bước hiện tại và trao quyền cho cấp dưới (T1 -> T2 -> T3 -> T4).
    """

    def __init__(self, tier_executors: Dict[Tier, Any]):
        self.executors = tier_executors

    async def execute_with_fallback(
        self,
        task: BookingTask,
        ctx: SessionContext,
        initial_tier: Tier = Tier.TIER2_PLAYWRIGHT,
    ) -> StepResult:
        tiers_order = [
            Tier.TIER1_API_REPLAY,
            Tier.TIER2_PLAYWRIGHT,
            Tier.TIER3_STAGEHAND,
            Tier.TIER4_VISION,
        ]
        start_index = tiers_order.index(initial_tier) if initial_tier in tiers_order else 1
        t_start = time.perf_counter()

        last_error = None
        for current_tier in tiers_order[start_index:]:
            executor = self.executors.get(current_tier)
            if not executor:
                continue

            try:
                res = await executor.execute(task, ctx)
                if res.success:
                    return res
                last_error = res.error_code or "Action failed"
            except Exception as e:
                last_error = str(e)

        total_latency = (time.perf_counter() - t_start) * 1000
        return StepResult(
            success=False,
            tier_used=tiers_order[-1],
            latency_ms=total_latency,
            tokens_consumed=0,
            cost_usd=0.0,
            cost_vnd=0.0,
            output_message=f"Toàn bộ các cấp đều thất bại. Lỗi cuối: {last_error}",
            error_code="ALL_TIERS_EXHAUSTED",
        )
