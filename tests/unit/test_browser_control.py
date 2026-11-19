"""
Unit Tests for Role D (Browser Control Module).
Testing all tasks: MVP-02, MVP-27, MVP-30, MVP-31, MVP-32, MVP-33, MVP-34, MVP-35, MVP-36, MVP-38.
"""

import pytest
import asyncio
from booking_agent.browser_control.port import (
    AdaptiveFallbackOrchestrator,
    BookingTask,
    SessionContext,
    Tier,
)
from booking_agent.browser_control.tiers import (
    Tier1APIReplayExecutor,
    Tier2PlaywrightExecutor,
    Tier3StagehandExecutor,
    Tier4VisionExecutor,
    Tier5TypeSafeJevExecutor,
)
from booking_agent.browser_control.detector import BookingResultDetector
from booking_agent.browser_control.learning import ActionRecorder, CDPNetworkSniffer
from booking_agent.browser_infra.cdp_gateway import (
    BrowserEngine,
    Capability,
    CapabilityNotSupported,
    UnifiedCDPGateway,
)


@pytest.fixture
def sample_task():
    return BookingTask(
        site_url="https://buffetposeidon.com/dat-ban",
        customer_name="Nguyễn Văn Test",
        phone_number="0912345678",
        email="testbooking@gmail.com",
        party_size=2,
        booking_date="2026-11-20",
        booking_time="19:00",
        dry_run=True,
    )


@pytest.fixture
def sample_context():
    return SessionContext(
        session_id="test_session_01",
        cdp_url="ws://127.0.0.1:9222/devtools/browser/test",
        engine_name="chromium",
    )


# --- TEST MVP-30 (TIER 1 API REPLAY) ---
@pytest.mark.asyncio
async def test_tier1_api_replay(sample_task, sample_context):
    executor = Tier1APIReplayExecutor()
    result = await executor.execute(sample_task, sample_context)

    assert result.success is True
    assert result.tier_used == Tier.TIER1_API_REPLAY
    assert result.tokens_consumed == 0
    assert result.cost_usd == 0.0


# --- TEST MVP-31 (TIER 2 PLAYWRIGHT REPLAY) ---
@pytest.mark.asyncio
async def test_tier2_playwright_cached(sample_task, sample_context):
    executor = Tier2PlaywrightExecutor()
    result = await executor.execute(sample_task, sample_context)

    assert result.success is True
    assert result.tier_used == Tier.TIER2_PLAYWRIGHT
    assert result.tokens_consumed == 0
    assert result.cost_usd == 0.0
    assert result.latency_ms < 1000.0  # Dưới 1 giây


# --- TEST MVP-32 (TIER 3 STAGEHAND DISCOVERY) ---
@pytest.mark.asyncio
async def test_tier3_stagehand_discovery(sample_task, sample_context):
    executor = Tier3StagehandExecutor()
    result = await executor.execute(sample_task, sample_context)

    assert result.success is True
    assert result.tier_used == Tier.TIER3_STAGEHAND
    assert result.tokens_consumed > 0
    assert result.discovered_selectors is not None
    assert "name" in result.discovered_selectors


# --- TEST MVP-33 (TIER 4 BROWSER-USE VISION & BUILT-IN JEV) ---
@pytest.mark.asyncio
async def test_tier4_vision_ultrafast(sample_task, sample_context):
    executor = Tier4VisionExecutor(mode="ultrafast")
    result = await executor.execute(sample_task, sample_context)

    assert result.success is True
    assert result.tier_used == Tier.TIER4_VISION
    assert result.latency_ms < 35000.0  # Ultrafast dưới 35s (~29.13s)


# --- TEST MVP-33-PLUS (TIER 5 NATIVE TYPESAFE JEV ULTRAFAST) ---
@pytest.mark.asyncio
async def test_tier5_typesafe_jev_ultrafast(sample_task, sample_context):
    executor = Tier5TypeSafeJevExecutor()
    result = await executor.execute(sample_task, sample_context)

    assert result.success is True
    assert result.tier_used == Tier.TIER5_TYPESAFE_JEV
    assert result.latency_ms < 20000.0  # Siêu tốc dưới 20 giây (16.76s thực tế)
    assert result.cost_vnd < 150.0      # Tiết kiệm dưới 150 VNĐ (~105.68 VNĐ)


# --- TEST MVP-34 (HOT-SWAP FALLBACK ORCHESTRATOR) ---
@pytest.mark.asyncio
async def test_fallback_orchestrator(sample_task, sample_context):
    # Giả lập Cấp 1 và Cấp 2 bị fail
    class FailingExecutor:
        async def execute(self, task, ctx):
            from booking_agent.browser_control.port import StepResult
            return StepResult(
                success=False,
                tier_used=Tier.TIER1_API_REPLAY,
                latency_ms=100.0,
                tokens_consumed=0,
                cost_usd=0.0,
                cost_vnd=0.0,
                output_message="Fail",
                error_code="WAF_BLOCKED",
            )

    orchestrator = AdaptiveFallbackOrchestrator({
        Tier.TIER1_API_REPLAY: FailingExecutor(),
        Tier.TIER2_PLAYWRIGHT: FailingExecutor(),
        Tier.TIER3_STAGEHAND: Tier3StagehandExecutor(),
    })

    result = await orchestrator.execute_with_fallback(sample_task, sample_context, initial_tier=Tier.TIER1_API_REPLAY)
    assert result.success is True
    assert result.tier_used == Tier.TIER3_STAGEHAND  # Tự trượt xuống Tầng 3 thành công


# --- TEST MVP-02 (CDP GATEWAY CAPABILITY CHECK) ---
def test_cdp_gateway():
    gateway = UnifiedCDPGateway()
    conn = gateway.register_endpoint(
        session_id="sess_01",
        endpoint_url="ws://127.0.0.1:9222",
        engine=BrowserEngine.CHROMIUM,
    )
    assert conn.is_active is True
    # Chromium hỗ trợ SCREENSHOT
    conn.verify_capability(Capability.SCREENSHOT)

    # Chromium không có NATIVE_FIREFOX_BIDI
    with pytest.raises(CapabilityNotSupported):
        conn.verify_capability(Capability.NATIVE_FIREFOX_BIDI)


# --- TEST MVP-38 (DETECTOR) ---
def test_booking_detector():
    success_html = "<div>Cảm ơn quý khách đã đặt bàn thành công tại Buffet Poseidon! Mã: POS123</div>"
    result = BookingResultDetector.evaluate_page_content(success_html)
    assert result["is_success"] is True

    fail_html = "<div>Xin lỗi, khung giờ này nhà hàng đã hết bàn.</div>"
    result_fail = BookingResultDetector.evaluate_page_content(fail_html)
    assert result_fail["is_success"] is False
    assert result_fail["error_code"] == "SITE_REJECTED"


# --- TEST MVP-36 (SNIFFER & ACTION RECORDER) ---
def test_sniffer_and_recorder():
    sniffer = CDPNetworkSniffer()
    sniffer.start_capture()
    sniffer.record_request(
        url="https://buffetposeidon.com/api/booking/submit",
        method="POST",
        headers={"Content-Type": "application/json"},
        post_data='{"name": "Test"}',
    )
    calls = sniffer.stop_capture()
    assert len(calls) == 1
    template = sniffer.export_raw_template()
    assert template["method"] == "POST"

    recorder = ActionRecorder()
    recorder.record_step("fill_name", "xpath=//input[@name='name']", "fill", "customer_name")
    selectors = recorder.export_playwright_selectors()
    assert "customer_name" in selectors
