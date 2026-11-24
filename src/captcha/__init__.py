"""Captcha Solver – kiến trúc 3 tầng.

Tầng 1: Text/OCR captcha  → giải local (stub – cần điền logic nhận dạng)
Tầng 2: Image captcha      → gọi VLM qua API (stub – cần điền logic nhận dạng)
Tầng 3: Human handoff       → gửi Telegram / webhook, chờ người xử lý
"""

from src.captcha.solver import CaptchaSolver  # noqa: F401
