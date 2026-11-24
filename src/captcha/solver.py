"""Captcha Solver – Orchestrator 3 tầng.

Pipeline giải captcha theo thứ tự ưu tiên:
  Tầng 1 (Text/OCR)  → nhanh, miễn phí, local
  Tầng 2 (VLM)       → chính xác hơn, tốn API call
  Tầng 3 (Human)     → fallback bắt buộc, 100% chính xác

Mỗi tầng có số lần retry riêng. Nếu tầng trước thất bại
→ chuyển xuống tầng sau.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING

from src.captcha.detector import capture_captcha_screenshot, detect_captcha
from src.captcha.models import (
    BoundingBox,
    CaptchaPlan,
    CaptchaType,
    SolveResult,
    SolveStatus,
)
from src.captcha.tier1_text import solve_text_captcha
from src.captcha.tier2_vlm import ask_vlm
from src.captcha.tier3_human import HumanHandoff

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)


class CaptchaSolver:
    """Orchestrator giải captcha 3 tầng.

    Sử dụng:
    ────────
    ```python
    solver = CaptchaSolver()
    result = await solver.solve(page)
    if result.status == SolveStatus.SOLVED:
        print("Captcha đã qua!")
    ```
    """

    def __init__(
        self,
        tier1_max_retries: int = 2,
        tier2_max_retries: int = 3,
        human_timeout: float = 300.0,
        screenshot_dir: str = "receipts",
    ):
        self.tier1_max_retries = tier1_max_retries
        self.tier2_max_retries = tier2_max_retries
        self.screenshot_dir = screenshot_dir
        os.makedirs(screenshot_dir, exist_ok=True)

        # Human handoff
        self.human_handoff = HumanHandoff(
            timeout=human_timeout,
            screenshot_dir=screenshot_dir,
        )

    async def solve(
        self,
        page: Page,
        context_message: str = "",
    ) -> SolveResult:
        """Pipeline chính: phát hiện → phân loại → giải theo tầng.

        Args:
            page: Playwright page đang có captcha.
            context_message: Thông tin về task đang thực hiện (cho thông báo).

        Returns:
            SolveResult với trạng thái cuối cùng.
        """
        logger.info("=" * 60)
        logger.info("🔍 Bắt đầu pipeline giải captcha")
        logger.info("=" * 60)

        # ── Bước 0: Phát hiện captcha ──────────────────────────────
        captcha_type, box = await detect_captcha(page)

        if box is None:
            logger.info("✅ Không phát hiện captcha trên trang")
            return SolveResult(
                status=SolveStatus.NO_CAPTCHA,
                message="Không phát hiện captcha",
            )

        logger.info("📋 Phát hiện captcha: type=%s, box=(%s)", captcha_type.value, box)

        # ── Chọn luồng xử lý dựa trên loại captcha ───────────────

        if captcha_type == CaptchaType.TEXT_OCR:
            # Tầng 1 trước → Tầng 2 nếu thất bại → Tầng 3
            result = await self._try_tier1(page, box)
            if result.status == SolveStatus.SOLVED:
                return result

            result = await self._try_tier2(page, box, captcha_type)
            if result.status == SolveStatus.SOLVED:
                return result

        elif captcha_type in (
            CaptchaType.IMAGE_GRID,
            CaptchaType.IMAGE_CLICK,
            CaptchaType.SLIDER,
            CaptchaType.ROTATE,
        ):
            # Tầng 2 trước (VLM phù hợp hơn cho ảnh) → Tầng 3
            result = await self._try_tier2(page, box, captcha_type)
            if result.status == SolveStatus.SOLVED:
                return result

        else:
            logger.warning("⚠️ Loại captcha không xác định, chuyển thẳng tầng 3")

        # ── Tầng 3: Human handoff ────────────────────────────────
        logger.info("👤 Chuyển sang Tầng 3: Human handoff")
        return await self.human_handoff.request_human_help(
            page=page,
            context_message=context_message,
        )

    # ══════════════════════════════════════════════════════════════
    # Tầng 1: Text/OCR
    # ══════════════════════════════════════════════════════════════

    async def _try_tier1(self, page: Page, box: BoundingBox) -> SolveResult:
        """Thử giải bằng OCR local."""
        logger.info("🔤 Tầng 1: Giải text captcha bằng OCR local")

        for attempt in range(1, self.tier1_max_retries + 1):
            logger.info("  Lần thử %d/%d", attempt, self.tier1_max_retries)

            # Chụp vùng captcha
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            img_path = os.path.join(self.screenshot_dir, f"captcha_t1_{ts}.png")
            await capture_captcha_screenshot(page, box, img_path)

            # Gọi OCR
            plan = await solve_text_captcha(img_path)

            if not plan.text_answer:
                logger.warning("  OCR không nhận dạng được text")
                continue

            # Điền kết quả vào ô input captcha
            submitted = await self._submit_text_answer(page, plan.text_answer)
            if not submitted:
                continue

            # Chờ và kiểm tra
            await asyncio.sleep(2)
            new_type, new_box = await detect_captcha(page)
            if new_box is None:
                logger.info("  ✅ Tầng 1 thành công!")
                return SolveResult(
                    status=SolveStatus.SOLVED,
                    tier_used=1,
                    attempts=attempt,
                    screenshot_path=img_path,
                    message=f"OCR giải thành công: '{plan.text_answer}'",
                    plan=plan,
                )
            else:
                logger.info("  ❌ Captcha vẫn còn sau khi điền, thử lại...")

        logger.info("  Tầng 1 thất bại sau %d lần", self.tier1_max_retries)
        return SolveResult(status=SolveStatus.FAILED, tier_used=1, attempts=self.tier1_max_retries)

    async def _submit_text_answer(self, page: Page, answer: str) -> bool:
        """Điền đáp án text captcha vào ô input.

        STUB: Selector cần tùy chỉnh theo website cụ thể.
        """
        text_input_selectors = [
            'input[name="captcha"]',
            'input[name="captcha_code"]',
            'input[name="verify_code"]',
            'input#captcha',
            'input.captcha-input',
            'input[placeholder*="captcha" i]',
            'input[placeholder*="mã" i]',
        ]
        for sel in text_input_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1_000):
                    await el.fill(answer)
                    logger.info("  Đã điền '%s' vào %s", answer, sel)

                    # Thử submit
                    await el.press("Enter")
                    return True
            except Exception:
                continue

        logger.warning("  Không tìm được ô input captcha để điền")
        return False

    # ══════════════════════════════════════════════════════════════
    # Tầng 2: VLM
    # ══════════════════════════════════════════════════════════════

    async def _try_tier2(
        self, page: Page, box: BoundingBox, captcha_type: CaptchaType,
    ) -> SolveResult:
        """Thử giải bằng VLM.

        STUB: Phần perform_action cần team bổ sung logic
        tương tác (click grid, kéo slider…) phù hợp website.
        """
        logger.info("🖼️ Tầng 2: Giải captcha bằng VLM")

        for attempt in range(1, self.tier2_max_retries + 1):
            logger.info("  Lần thử %d/%d", attempt, self.tier2_max_retries)

            # Chụp vùng captcha
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            img_path = os.path.join(self.screenshot_dir, f"captcha_t2_{ts}.png")
            await capture_captcha_screenshot(page, box, img_path)

            # Gọi VLM
            plan = await ask_vlm(img_path, captcha_type)

            if not self._plan_has_data(plan):
                logger.warning("  VLM không trả kết quả hữu ích")
                continue

            # ┌──────────────────────────────────────────────────────┐
            # │  STUB: Thực hiện hành động trên browser.            │
            # │  Team bổ sung logic click/kéo/xoay phù hợp.        │
            # └──────────────────────────────────────────────────────┘
            await self._perform_action(page, box, plan)

            # Chờ và kiểm tra
            await asyncio.sleep(2)
            new_type, new_box = await detect_captcha(page)
            if new_box is None:
                logger.info("  ✅ Tầng 2 thành công!")
                return SolveResult(
                    status=SolveStatus.SOLVED,
                    tier_used=2,
                    attempts=attempt,
                    screenshot_path=img_path,
                    message="VLM giải thành công",
                    plan=plan,
                )
            else:
                logger.info("  ❌ Captcha vẫn còn, thử lại...")

        logger.info("  Tầng 2 thất bại sau %d lần", self.tier2_max_retries)
        return SolveResult(status=SolveStatus.FAILED, tier_used=2, attempts=self.tier2_max_retries)

    @staticmethod
    def _plan_has_data(plan: CaptchaPlan) -> bool:
        """Kiểm tra plan có dữ liệu hữu ích không."""
        return bool(
            plan.text_answer
            or plan.grid_cells
            or plan.click_points
            or plan.slider_offset > 0
        )

    async def _perform_action(
        self, page: Page, box: BoundingBox, plan: CaptchaPlan,
    ) -> None:
        """Thực hiện hành động trên browser dựa trên plan từ VLM.

        STUB: Logic tương tác cần team bổ sung cho từng loại.
        Khung bên dưới minh họa cách chuyển tọa độ và gọi action.
        """
        if plan.captcha_type == CaptchaType.TEXT_OCR:
            await self._submit_text_answer(page, plan.text_answer)

        elif plan.captcha_type == CaptchaType.IMAGE_GRID:
            # ┌────────────────────────────────────────────────────┐
            # │  STUB: Click từng ô trong grid.                   │
            # │  Cần biết grid size (3×3, 4×4) để tính tâm ô.    │
            # │  Team bổ sung logic xác định grid layout.         │
            # └────────────────────────────────────────────────────┘
            logger.info("  Grid cells cần click: %s", plan.grid_cells)
            # Ví dụ cho grid 3×3:
            grid_cols, grid_rows = 3, 3
            cell_w = box.width / grid_cols
            cell_h = box.height / grid_rows
            for cell_idx in plan.grid_cells:
                row = (cell_idx - 1) // grid_cols
                col = (cell_idx - 1) % grid_cols
                cx = box.x + col * cell_w + cell_w / 2
                cy = box.y + row * cell_h + cell_h / 2
                await page.mouse.click(cx, cy)
            #     await asyncio.sleep(0.3)

        elif plan.captcha_type == CaptchaType.IMAGE_CLICK:
            # ┌────────────────────────────────────────────────────┐
            # │  STUB: Click vào tọa độ trên ảnh captcha.         │
            # │  Chuyển tọa độ chuẩn hóa (0-1) → viewport.       │
            # └────────────────────────────────────────────────────┘
            for px, py in plan.click_points:
                x_page = box.x + px * box.width
                y_page = box.y + py * box.height
                logger.info("  Click tại (%.0f, %.0f)", x_page, y_page)
                await page.mouse.click(x_page, y_page)
                # await asyncio.sleep(0.3)

        elif plan.captcha_type == CaptchaType.SLIDER:
            # ┌────────────────────────────────────────────────────┐
            # │  STUB: Kéo slider đến vị trí offset.              │
            # │  Team bổ sung: tìm nút slider, nhấn-giữ-kéo-thả. │
            # └────────────────────────────────────────────────────┘
            target_x = box.x + plan.slider_offset * box.width
            logger.info("  Slider target offset: %.2f → x=%.0f", plan.slider_offset, target_x)
            # slider_handle = page.locator('.slider-handle').first
            # handle_box = await slider_handle.bounding_box()
            # start_x = handle_box['x'] + handle_box['width'] / 2
            # start_y = handle_box['y'] + handle_box['height'] / 2
            # await page.mouse.move(start_x, start_y)
            # await page.mouse.down()
            # await page.mouse.move(target_x, start_y, steps=20)
            # await page.mouse.up()

        else:
            logger.warning("  Loại captcha '%s' chưa có handler", plan.captcha_type.value)
