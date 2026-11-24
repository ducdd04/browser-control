"""Captcha Detector – phát hiện và phân loại captcha trên trang."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.captcha.models import BoundingBox, CaptchaType

if TYPE_CHECKING:
    from playwright.async_api import Page

logger = logging.getLogger(__name__)

# ── Các selector phổ biến cho từng loại captcha ────────────────────────
# Thêm/sửa selector tùy website cụ thể
CAPTCHA_SELECTORS: dict[CaptchaType, list[str]] = {
    CaptchaType.TEXT_OCR: [
        'img.captcha-image',
        'img[alt*="captcha"]',
        'img[src*="captcha"]',
        '#captcha-img',
        '.captcha img',
    ],
    CaptchaType.IMAGE_GRID: [
        'iframe[src*="recaptcha"]',
        'iframe[src*="hcaptcha"]',
        '.rc-imageselect',
        '#captcha-verify-image',
    ],
    CaptchaType.SLIDER: [
        '.slider-captcha',
        '.geetest_slider',
        '.captcha-slider',
    ],
    CaptchaType.IMAGE_CLICK: [
        '.click-captcha',
        '.geetest_item_img',
    ],
}


async def detect_captcha(page: Page) -> tuple[CaptchaType, BoundingBox | None]:
    """Quét trang để tìm captcha.

    Returns:
        (CaptchaType, BoundingBox | None) — loại captcha và vùng bao,
        hoặc (UNKNOWN, None) nếu không tìm thấy.
    """
    for ctype, selectors in CAPTCHA_SELECTORS.items():
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1_000):
                    box = await el.bounding_box()
                    if box:
                        logger.info("Phát hiện captcha %s qua selector '%s'", ctype.value, sel)
                        return ctype, BoundingBox(
                            x=box["x"], y=box["y"],
                            width=box["width"], height=box["height"],
                        )
            except Exception:
                continue

    # Kiểm tra Cloudflare Turnstile
    try:
        turnstile = page.locator('iframe[src*="challenges.cloudflare.com"]').first
        if await turnstile.is_visible(timeout=1_000):
            box = await turnstile.bounding_box()
            if box:
                logger.info("Phát hiện Cloudflare Turnstile")
                return CaptchaType.UNKNOWN, BoundingBox(
                    x=box["x"], y=box["y"],
                    width=box["width"], height=box["height"],
                )
    except Exception:
        pass

    return CaptchaType.UNKNOWN, None


async def capture_captcha_screenshot(
    page: Page, box: BoundingBox, save_path: str,
) -> str:
    """Chụp riêng vùng captcha (không chụp cả trang).

    Args:
        page: Playwright page.
        box: Vùng bao captcha.
        save_path: Đường dẫn lưu ảnh PNG.

    Returns:
        Đường dẫn file ảnh đã lưu.
    """
    # Tính device pixel ratio để clip chính xác
    dpr = await page.evaluate("window.devicePixelRatio || 1")

    await page.screenshot(
        path=save_path,
        clip={
            "x": box.x,
            "y": box.y,
            "width": box.width,
            "height": box.height,
        },
    )
    logger.info("Đã chụp captcha → %s (dpr=%.1f)", save_path, dpr)
    return save_path
