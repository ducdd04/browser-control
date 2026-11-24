"""Tích hợp CaptchaSolver vào browser-use dưới dạng custom tool.

Agent chỉ cần gọi solve_captcha() một lần — toàn bộ pipeline
3 tầng (OCR → VLM → Human) chạy bên trong tool.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

# ── browser-use imports ───────────────────────────────────────────
# Điều chỉnh import theo phiên bản browser-use bạn đang dùng.
# Phiên bản mới có thể đổi tên class.
try:
    from browser_use import Agent, Browser, BrowserConfig
    from browser_use.agent.views import ActionResult
    from browser_use.controller.service import Controller
except ImportError:
    # Fallback nếu chưa cài browser-use
    Agent = None  # type: ignore[assignment, misc]
    Browser = None  # type: ignore[assignment, misc]
    BrowserConfig = None  # type: ignore[assignment, misc]
    ActionResult = None  # type: ignore[assignment, misc]
    Controller = None  # type: ignore[assignment, misc]

from src.captcha.solver import CaptchaSolver

logger = logging.getLogger(__name__)

# ── Cấu hình ──────────────────────────────────────────────────────
SCREENSHOT_DIR = "receipts"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def create_captcha_controller(
    tier1_retries: int = 2,
    tier2_retries: int = 3,
    human_timeout: float = 300.0,
) -> Controller:
    """Tạo Controller có đăng ký tool solve_captcha.

    Returns:
        Controller instance với action solve_captcha.
    """
    controller = Controller()
    solver = CaptchaSolver(
        tier1_max_retries=tier1_retries,
        tier2_max_retries=tier2_retries,
        human_timeout=human_timeout,
        screenshot_dir=SCREENSHOT_DIR,
    )

    @controller.action(
        description=(
            "Giải captcha đang hiện trên trang. Tự động thử OCR local → "
            "VLM phân tích ảnh → chuyển cho người xử lý nếu thất bại. "
            "Gọi khi agent gặp captcha chặn thao tác."
        ),
    )
    async def solve_captcha(browser) -> ActionResult:
        """Custom tool: giải captcha 3 tầng.

        browser-use sẽ tự inject tham số `browser` (BrowserContext).
        """
        try:
            # Lấy page hiện tại
            page = await browser.get_current_page()
            context_msg = f"URL: {page.url} | Time: {datetime.now().isoformat()}"

            # Chạy pipeline 3 tầng
            result = await solver.solve(page, context_message=context_msg)

            # Trả kết quả cho agent
            msg = (
                f"Captcha solver kết quả: {result.status.value}\n"
                f"Tầng xử lý: {result.tier_used}\n"
                f"Số lần thử: {result.attempts}\n"
                f"Chi tiết: {result.message}"
            )

            if result.status.value == "solved":
                return ActionResult(extracted_content=msg)
            else:
                return ActionResult(error=msg)

        except Exception as e:
            logger.exception("Lỗi trong solve_captcha tool")
            return ActionResult(error=f"Lỗi solve_captcha: {e}")

    return controller


# ══════════════════════════════════════════════════════════════════
# Ví dụ chạy agent với captcha solver
# ══════════════════════════════════════════════════════════════════

async def run_agent_with_captcha(
    task: str,
    start_url: str,
    llm_model: str = "gpt-4o",
    headless: bool = False,
):
    """Khởi chạy browser-use agent có tích hợp captcha solver.

    Args:
        task: Mô tả task cho agent (ví dụ: "Đặt bàn Poseidon...").
        start_url: URL bắt đầu.
        llm_model: Model LLM cho agent chính.
        headless: Chạy browser ẩn hay hiện.
    """
    if Agent is None:
        logger.error("browser-use chưa được cài đặt. Chạy: pip install browser-use")
        return

    # Tạo controller với captcha tool
    controller = create_captcha_controller(
        tier1_retries=2,
        tier2_retries=3,
        human_timeout=300,
    )

    # Cấu hình browser
    browser = Browser(
        config=BrowserConfig(
            headless=headless,
            # Thêm cấu hình anti-detect nếu cần
        )
    )

    # Tạo agent
    agent = Agent(
        task=task,
        llm=llm_model,
        browser=browser,
        controller=controller,
    )

    # Chạy agent
    result = await agent.run()
    logger.info("Agent hoàn thành: %s", result)
    return result


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s │ %(name)-25s │ %(levelname)-7s │ %(message)s",
    )

    asyncio.run(
        run_agent_with_captcha(
            task="Mở trang và xử lý captcha nếu gặp",
            start_url="https://example.com",
            headless=False,
        )
    )
