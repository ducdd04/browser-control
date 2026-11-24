"""Tầng 1 – Text/OCR Captcha Solver (STUB).

╔══════════════════════════════════════════════════════════════╗
║  STUB — Khung kiến trúc cho giải captcha text/OCR.         ║
║  Logic nhận dạng thực tế cần được team bổ sung.            ║
║  Interface và luồng xử lý đã hoàn chỉnh.                   ║
╚══════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.captcha.models import CaptchaPlan, CaptchaType

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


async def solve_text_captcha(image_path: str) -> CaptchaPlan:
    """Giải captcha chữ/số từ ảnh.

    Khung thiết kế:
    ───────────────
    1. Đọc ảnh captcha từ image_path.
    2. Tiền xử lý: grayscale, threshold, denoise.
    3. Chạy model nhận dạng (ddddocr / PaddleOCR / Tesseract / custom model).
    4. Trả về CaptchaPlan với text_answer.

    Ví dụ tích hợp ddddocr (team bổ sung):
    ────────────────────────────────────────
    ```python
    import ddddocr
    ocr = ddddocr.DdddOcr(show_ad=False)
    with open(image_path, "rb") as f:
        result = ocr.classification(f.read())
    return CaptchaPlan(
        captcha_type=CaptchaType.TEXT_OCR,
        text_answer=result,
        confidence=0.85,
    )
    ```

    Ví dụ train model riêng (nếu sai nhiều):
    ──────────────────────────────────────────
    ```python
    # Dùng dddd_trainer để train trên dataset captcha cụ thể
    # https://github.com/sml2h3/dddd_trainer
    ocr = ddddocr.DdddOcr(show_ad=False, import_onnx="custom_model.onnx",
                           charsets_path="charsets.json")
    ```

    Args:
        image_path: Đường dẫn file ảnh captcha (PNG).

    Returns:
        CaptchaPlan với text_answer đã nhận dạng.
    """
    logger.info("[Tầng 1] Đang giải text captcha từ: %s", image_path)

    # ┌─────────────────────────────────────────────────────────┐
    # │  STUB: Thay thế đoạn dưới bằng logic nhận dạng thực   │
    # └─────────────────────────────────────────────────────────┘
        # ┌─────────────────────────────────────────────────────────┐
    # │  Nhận dạng bằng ddddocr                                │
    # └─────────────────────────────────────────────────────────┘
    import ddddocr
    ocr = ddddocr.DdddOcr(show_ad=False)
    with open(image_path, "rb") as f:
        recognized_text = ocr.classification(f.read())

    logger.info("[Tầng 1] Kết quả nhận dạng: '%s'", recognized_text)
    return CaptchaPlan(
        captcha_type=CaptchaType.TEXT_OCR,
        text_answer=recognized_text,
        confidence=0.85,
    )