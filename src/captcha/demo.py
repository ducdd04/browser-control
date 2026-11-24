"""Demo chạy CaptchaSolver 3 tầng trên poseidon_booking.

Chạy:
    python -m src.captcha.demo

Hoặc:
    python src/captcha/demo.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

# Đảm bảo import từ root project
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.captcha.models import SolveStatus
from src.captcha.solver import CaptchaSolver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-30s │ %(levelname)-7s │ %(message)s",
)
logger = logging.getLogger(__name__)


async def demo_with_camoufox():
    """Demo: mở trang Poseidon bằng Camoufox, gặp captcha thì solver xử lý."""
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError:
        logger.error("Cần cài camoufox: pip install camoufox[geoip]")
        return

    solver = CaptchaSolver(
        tier1_max_retries=2,
        tier2_max_retries=3,
        human_timeout=120,  # 2 phút cho demo
        screenshot_dir="receipts",
    )

    url = "https://buffetposeidon.com/dat-ban?action=form&branch=1"

    print("\n" + "=" * 64)
    print("🤖  DEMO CAPTCHA SOLVER 3 TẦNG")
    print("=" * 64)
    print(f"  🌐  URL: {url}")
    print("  📋  Pipeline: OCR → VLM → Human Handoff")
    print("=" * 64 + "\n")

    async with AsyncCamoufox(headless=False, humanize=True) as browser:
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        await asyncio.sleep(2)

        # Chạy solver
        result = await solver.solve(
            page,
            context_message="Demo đặt bàn Poseidon — bước captcha",
        )

        # In kết quả
        print("\n" + "=" * 64)
        print("📊  KẾT QUẢ SOLVER")
        print("=" * 64)
        print(f"  Status    : {result.status.value}")
        print(f"  Tầng      : {result.tier_used}")
        print(f"  Lần thử   : {result.attempts}")
        print(f"  Message   : {result.message}")
        print(f"  Screenshot: {result.screenshot_path}")
        print("=" * 64)

        if result.status == SolveStatus.SOLVED:
            print("\n✅  Captcha đã qua! Tiếp tục điền form...\n")
            # Ở đây có thể gọi tiếp logic điền form của poseidon_booking
        elif result.status == SolveStatus.NO_CAPTCHA:
            print("\n✅  Không có captcha, trang sẵn sàng!\n")
        else:
            print(f"\n❌  Solver kết thúc với: {result.status.value}\n")

        # Giữ browser mở 5 giây để xem
        await asyncio.sleep(5)


async def demo_standalone_tiers():
    """Demo đơn giản: test từng tầng riêng lẻ (không cần browser)."""

    print("\n" + "=" * 64)
    print("🧪  TEST TỪNG TẦNG RIÊNG LẺ")
    print("=" * 64)

    # ── Test Tầng 1: OCR ──────────────────────────────────────
    print("\n--- Tầng 1: Text/OCR (stub) ---")
    from src.captcha.tier1_text import solve_text_captcha
    plan1 = await solve_text_captcha("test_image.png")
    print(f"  Kết quả OCR: '{plan1.text_answer}' (confidence={plan1.confidence})")
    print(f"  → Đây là STUB, cần team điền logic nhận dạng thực tế")

    # ── Test Tầng 2: VLM ──────────────────────────────────────
    print("\n--- Tầng 2: VLM (stub) ---")
    from src.captcha.models import CaptchaType
    from src.captcha.tier2_vlm import VLM_CONFIG
    print(f"  VLM endpoint: {VLM_CONFIG['base_url']}")
    print(f"  VLM model   : {VLM_CONFIG['model']}")
    print(f"  API key set : {'✅' if VLM_CONFIG['api_key'] else '❌ chưa set'}")
    print(f"  → Cần cấu hình API key và test endpoint")

    # ── Test Tầng 3: Human Handoff ────────────────────────────
    print("\n--- Tầng 3: Human Handoff ---")
    from src.captcha.tier3_human import HumanHandoff
    hh = HumanHandoff(timeout=10, poll_interval=2)
    print(f"  Timeout     : {hh.timeout}s")
    print(f"  Poll interval: {hh.poll_interval}s")
    print(f"  → Hoàn chỉnh, sẵn sàng hoạt động")

    print("\n" + "=" * 64)
    print("✅  Test cấu trúc module hoàn tất!")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "standalone"

    if mode == "browser":
        asyncio.run(demo_with_camoufox())
    else:
        asyncio.run(demo_standalone_tiers())
