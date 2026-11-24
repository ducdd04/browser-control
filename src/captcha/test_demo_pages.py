"""Test CaptchaSolver trên các trang demo công khai.

Trang demo chính thức của nhà cung cấp:
  - Google reCAPTCHA v2: https://www.google.com/recaptcha/api2/demo
  - hCaptcha:            https://dashboard.hcaptcha.com/#/signup

Chạy:
    cd foxprofile
    source .venv/bin/activate
    python src/captcha/test_demo_pages.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.captcha.detector import detect_captcha, capture_captcha_screenshot
from src.captcha.models import CaptchaType, SolveStatus
from src.captcha.solver import CaptchaSolver

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(name)-30s │ %(levelname)-7s │ %(message)s",
)
logger = logging.getLogger(__name__)

DEMO_PAGES = [
    {
        "name": "Google reCAPTCHA v2 Demo",
        "url": "https://www.google.com/recaptcha/api2/demo",
        "description": "Trang demo chính thức của Google cho reCAPTCHA v2 checkbox",
    },
    {
        "name": "hCaptcha Signup (demo)",
        "url": "https://dashboard.hcaptcha.com/#/signup",
        "description": "Trang đăng ký hCaptcha có widget hCaptcha thật",
    },
]

SCREENSHOT_DIR = "receipts/demo_test"


async def test_single_page(browser, page_info: dict, solver: CaptchaSolver):
    """Test solver trên 1 trang demo."""
    name = page_info["name"]
    url = page_info["url"]

    print()
    print("─" * 64)
    print(f"🌐  {name}")
    print(f"    {url}")
    print(f"    {page_info['description']}")
    print("─" * 64)

    page = await browser.new_page()

    try:
        # 1. Mở trang
        print(f"  ➡️  Đang mở trang...")
        await page.goto(url, wait_until="networkidle", timeout=30_000)
        await asyncio.sleep(3)  # Chờ captcha widget load

        # 2. Chụp toàn trang
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        safe_name = name.replace(" ", "_").lower()
        full_ss = os.path.join(SCREENSHOT_DIR, f"{safe_name}_full.png")
        await page.screenshot(path=full_ss)
        print(f"  📸  Screenshot toàn trang → {full_ss}")

        # 3. Phát hiện captcha
        print(f"  🔍  Đang quét tìm captcha...")
        captcha_type, box = await detect_captcha(page)

        if box is None:
            print(f"  ⚠️  Không phát hiện captcha widget trên trang")
            print(f"      (Có thể captcha chưa render hoặc selector chưa match)")
            return {"name": name, "detected": False, "type": None}

        print(f"  ✅  Phát hiện captcha!")
        print(f"      Loại    : {captcha_type.value}")
        print(f"      Vị trí  : x={box.x:.0f}, y={box.y:.0f}")
        print(f"      Kích thước: {box.width:.0f} × {box.height:.0f}")

        # 4. Chụp riêng vùng captcha
        captcha_ss = os.path.join(SCREENSHOT_DIR, f"{safe_name}_captcha.png")
        await capture_captcha_screenshot(page, box, captcha_ss)
        print(f"  📸  Screenshot captcha → {captcha_ss}")

        # 5. Chạy solver pipeline (sẽ đến tầng 3 human handoff vì tầng 1,2 là stub)
        print(f"\n  🤖  Chạy solver pipeline 3 tầng...")
        result = await solver.solve(
            page,
            context_message=f"Test trên {name}",
        )

        print(f"\n  📊  Kết quả solver:")
        print(f"      Status : {result.status.value}")
        print(f"      Tầng   : {result.tier_used}")
        print(f"      Message: {result.message}")

        return {
            "name": name,
            "detected": True,
            "type": captcha_type.value,
            "solver_status": result.status.value,
            "tier_used": result.tier_used,
        }

    except Exception as e:
        print(f"  ❌  Lỗi: {e}")
        return {"name": name, "detected": False, "error": str(e)}

    finally:
        await page.close()


async def main():
    """Chạy test trên tất cả trang demo."""
    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError:
        print("❌  Cần cài camoufox: pip install 'camoufox[geoip]'")
        return

    print()
    print("=" * 64)
    print("🧪  TEST CAPTCHA SOLVER TRÊN TRANG DEMO CÔNG KHAI")
    print("=" * 64)
    print(f"  📋  Số trang test: {len(DEMO_PAGES)}")
    print(f"  📂  Screenshot  : {SCREENSHOT_DIR}/")
    print(f"  🔧  Pipeline    : OCR(stub) → VLM(stub) → Human Handoff")
    print()
    print("  ⚠️  Vì tầng 1 & 2 là stub, solver sẽ rơi xuống tầng 3")
    print("      (Human Handoff) — đây là hành vi đúng thiết kế.")
    print("      Mục đích: kiểm tra detector + luồng pipeline hoạt động.")

    solver = CaptchaSolver(
        tier1_max_retries=1,     # Giảm retry cho demo nhanh
        tier2_max_retries=1,
        human_timeout=30,        # 30s timeout cho demo (không chờ lâu)
        screenshot_dir=SCREENSHOT_DIR,
    )

    results = []

    async with AsyncCamoufox(headless=False, humanize=True) as browser:
        for page_info in DEMO_PAGES:
            result = await test_single_page(browser, page_info, solver)
            results.append(result)

    # Tổng kết
    print()
    print("=" * 64)
    print("📊  TỔNG KẾT")
    print("=" * 64)
    for r in results:
        icon = "✅" if r.get("detected") else "⚠️"
        ctype = r.get("type", "N/A")
        status = r.get("solver_status", "N/A")
        print(f"  {icon}  {r['name']}")
        print(f"      Detected: {r.get('detected', False)} | Type: {ctype} | Solver: {status}")
    print("=" * 64)
    print()


if __name__ == "__main__":
    asyncio.run(main())
