"""Tầng 3 – Human-in-the-loop Handoff (HOÀN CHỈNH).

Khi tầng 1 và 2 thất bại, tầng 3 sẽ:
1. Chụp screenshot trạng thái captcha.
2. Log cảnh báo ra console + lưu ảnh.
3. Tạm dừng agent, chờ người xử lý captcha trực tiếp trên browser.
4. Poll kiểm tra captcha mỗi N giây → nếu biến mất → resume agent.
5. Hết timeout → trả TIMEOUT.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING

from src.captcha.models import SolveResult, SolveStatus

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


class HumanHandoff:
    """Điều phối chuyển giao cho người xử lý khi AI thất bại.

    Luồng:
    ──────
    1. Chụp ảnh trạng thái hiện tại.
    2. In cảnh báo ra console (operator đang xem terminal).
    3. Poll kiểm tra captcha mỗi N giây.
    4. Nếu captcha biến mất (người đã xử lý) → resume.
    5. Nếu hết timeout → trả TIMEOUT.
    """

    def __init__(
        self,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
        screenshot_dir: str = "receipts",
    ):
        self.poll_interval = poll_interval
        self.timeout = timeout
        self.screenshot_dir = screenshot_dir
        os.makedirs(screenshot_dir, exist_ok=True)

    async def request_human_help(
        self,
        page: Page,
        captcha_selector: str = "",
        context_message: str = "",
    ) -> SolveResult:
        """Tạm dừng agent và chờ người xử lý captcha trên browser.

        Args:
            page: Playwright page đang có captcha.
            captcha_selector: CSS selector captcha (để kiểm tra biến mất chưa).
            context_message: Thông tin bổ sung (URL, task đang làm…).

        Returns:
            SolveResult với status SOLVED hoặc TIMEOUT.
        """
        # 1. Chụp screenshot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = os.path.join(
            self.screenshot_dir, f"captcha_handoff_{timestamp}.png",
        )
        await page.screenshot(path=screenshot_path)
        logger.info("[Tầng 3] Đã chụp ảnh captcha → %s", screenshot_path)

        # 2. In cảnh báo rõ ràng ra console
        url = page.url
        print()
        print("=" * 64)
        print("🚨  CAPTCHA CẦN NGƯỜI XỬ LÝ")
        print("=" * 64)
        print(f"  🌐  URL       : {url}")
        print(f"  ⏰  Thời gian : {datetime.now().strftime('%H:%M:%S %d/%m/%Y')}")
        print(f"  📸  Screenshot: {screenshot_path}")
        if context_message:
            print(f"  📝  Ngữ cảnh : {context_message}")
        print()
        print("  👉  Hãy mở browser và giải captcha thủ công.")
        print(f"  ⏳  Agent sẽ tự resume khi captcha biến mất (timeout {self.timeout:.0f}s)")
        print("=" * 64)
        print()

        # 3. Poll chờ captcha biến mất
        elapsed = 0.0
        while elapsed < self.timeout:
            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval

            if await self._is_captcha_gone(page, captcha_selector):
                print(f"\n✅  Captcha đã được giải! Agent tiếp tục. (sau {elapsed:.0f}s)\n")
                logger.info("[Tầng 3] ✅ Captcha đã được người xử lý! (sau %.0fs)", elapsed)

                return SolveResult(
                    status=SolveStatus.SOLVED,
                    tier_used=3,
                    attempts=0,
                    screenshot_path=screenshot_path,
                    message=f"Người xử lý đã giải captcha sau {elapsed:.0f}s",
                )

            # Log tiến trình mỗi 30 giây
            if elapsed % 30 < self.poll_interval:
                remaining = self.timeout - elapsed
                print(f"  ⏳  Chờ người xử lý... ({elapsed:.0f}s đã qua, còn {remaining:.0f}s)")

        # 4. Hết timeout
        print(f"\n⏰  Timeout {self.timeout:.0f}s — không ai xử lý captcha. Agent dừng task.\n")
        logger.warning("[Tầng 3] ⏰ Timeout — không có người xử lý trong %.0fs", self.timeout)

        return SolveResult(
            status=SolveStatus.TIMEOUT,
            tier_used=3,
            attempts=0,
            screenshot_path=screenshot_path,
            message=f"Timeout {self.timeout:.0f}s, cần xử lý thủ công",
        )

    async def _is_captcha_gone(self, page: Page, selector: str) -> bool:
        """Kiểm tra captcha đã biến mất khỏi trang chưa."""
        if not selector:
            from src.captcha.detector import detect_captcha

            _, box = await detect_captcha(page)
            return box is None
        else:
            try:
                el = page.locator(selector).first
                visible = await el.is_visible(timeout=500)
                return not visible
            except Exception:
                return True
