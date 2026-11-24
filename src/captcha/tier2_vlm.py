"""Tầng 2 – Image Captcha Solver qua VLM (STUB).

╔══════════════════════════════════════════════════════════════╗
║  STUB — Khung kiến trúc gọi VLM phân tích captcha ảnh.    ║
║  Logic nhận dạng thực tế cần được team bổ sung.            ║
║  Interface, prompt template và luồng xử lý đã hoàn chỉnh.  ║
╚══════════════════════════════════════════════════════════════╝
"""

from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import aiohttp

from src.captcha.models import CaptchaPlan, CaptchaType

logger = logging.getLogger(__name__)

# ── Cấu hình VLM ──────────────────────────────────────────────────────
# Team cập nhật theo API endpoint thực tế
VLM_CONFIG = {
    "base_url": "https://vllm.anm05.com",   # Base URL của VLM API
    "model": "qwen-3.6-35b-a3b",            # Model name
    "api_key": "sk-1ca0e61277cf6d63d758b6597d27602511aa48c22b",                           # ← Điền API key khi deploy
    "timeout": 30,                           # Timeout (giây)
    "max_tokens": 512,
}


# ── Prompt templates ───────────────────────────────────────────────────

PROMPT_IMAGE_GRID = """Bạn đang nhìn ảnh chụp một captcha dạng lưới (grid).
Hãy xác định các ô chứa đối tượng được yêu cầu.

Trả về JSON duy nhất, không giải thích:
{
  "type": "image_grid",
  "cells": [1, 4, 7],
  "instruction_detected": "Select all images with traffic lights"
}

Quy ước: ô được đánh số từ 1, trái→phải, trên→dưới."""

PROMPT_IMAGE_CLICK = """Bạn đang nhìn ảnh chụp một captcha yêu cầu click vào điểm cụ thể.
Xác định tọa độ các điểm cần click.

Trả về JSON duy nhất, không giải thích:
{
  "type": "image_click",
  "points": [[x1, y1], [x2, y2]],
  "instruction_detected": "Click on the center of the star"
}

Tọa độ chuẩn hóa 0-1000 theo kích thước ảnh (0,0 = góc trái trên)."""

PROMPT_SLIDER = """Bạn đang nhìn ảnh chụp một captcha dạng slider (kéo ghép hình).
Xác định vị trí lỗ khuyết mà miếng ghép cần được kéo đến.

Trả về JSON duy nhất, không giải thích:
{
  "type": "slider",
  "offset_ratio": 0.65,
  "description": "Lỗ khuyết ở khoảng 65% chiều rộng ảnh"
}

offset_ratio: tỷ lệ 0.0 → 1.0 theo chiều rộng ảnh."""

PROMPT_TEXT = """Bạn đang nhìn ảnh chụp một captcha dạng text/OCR.
Hãy đọc các ký tự trong ảnh.

Trả về JSON duy nhất, không giải thích:
{
  "type": "text_ocr",
  "text": "abc123"
}"""

PROMPTS = {
    CaptchaType.IMAGE_GRID: PROMPT_IMAGE_GRID,
    CaptchaType.IMAGE_CLICK: PROMPT_IMAGE_CLICK,
    CaptchaType.SLIDER: PROMPT_SLIDER,
    CaptchaType.TEXT_OCR: PROMPT_TEXT,
    CaptchaType.UNKNOWN: PROMPT_IMAGE_GRID,  # Fallback
}


def _encode_image(image_path: str) -> str:
    """Encode ảnh thành base64 để gửi qua API."""
    data = Path(image_path).read_bytes()
    return base64.b64encode(data).decode("utf-8")


async def ask_vlm(image_path: str, captcha_type: CaptchaType) -> CaptchaPlan:
    """Gọi VLM API để phân tích ảnh captcha.

    Luồng xử lý:
    ─────────────
    1. Encode ảnh captcha thành base64.
    2. Chọn prompt template phù hợp loại captcha.
    3. Gọi VLM API (OpenAI-compatible) với ảnh + prompt.
    4. Parse JSON response → CaptchaPlan.

    Args:
        image_path: Đường dẫn file ảnh captcha (PNG).
        captcha_type: Loại captcha đã phát hiện.

    Returns:
        CaptchaPlan với thông tin giải captcha.
    """
    logger.info("[Tầng 2] Gọi VLM để phân tích captcha %s", captcha_type.value)

    # ┌─────────────────────────────────────────────────────────┐
    # │  STUB: Đoạn dưới là khung gọi API hoàn chỉnh.         │
    # │  Team cần cấu hình VLM_CONFIG và test endpoint.        │
    # └─────────────────────────────────────────────────────────┘

    image_b64 = _encode_image(image_path)
    prompt = PROMPTS.get(captcha_type, PROMPT_IMAGE_GRID)

    # Payload chuẩn OpenAI Vision API format
    payload = {
        "model": VLM_CONFIG["model"],
        "max_tokens": VLM_CONFIG["max_tokens"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}",
                        },
                    },
                ],
            }
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {VLM_CONFIG['api_key']}",
    }

    try:
        async with aiohttp.ClientSession() as session:
            url = f"{VLM_CONFIG['base_url']}/v1/chat/completions"
            async with session.post(
                url, json=payload, headers=headers,
                timeout=aiohttp.ClientTimeout(total=VLM_CONFIG["timeout"]),
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error("[Tầng 2] VLM API lỗi %d: %s", resp.status, error_text)
                    return CaptchaPlan(captcha_type=captcha_type)

                data = await resp.json()
                content = data["choices"][0]["message"]["content"]
                logger.info("[Tầng 2] VLM trả về: %s", content[:200])

    except Exception as e:
        logger.error("[Tầng 2] Lỗi kết nối VLM: %s", e)
        return CaptchaPlan(captcha_type=captcha_type)

    # Parse JSON từ VLM response
    return _parse_vlm_response(content, captcha_type)


def _parse_vlm_response(content: str, captcha_type: CaptchaType) -> CaptchaPlan:
    """Parse JSON response từ VLM thành CaptchaPlan.

    VLM có thể trả JSON trong markdown code block hoặc raw.
    """
    # Loại bỏ markdown code block nếu có
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        # Bỏ dòng đầu (```json) và dòng cuối (```)
        cleaned = "\n".join(lines[1:-1])

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("[Tầng 2] Không parse được JSON từ VLM: %s", content[:200])
        return CaptchaPlan(captcha_type=captcha_type, raw_response={"raw": content})

    plan = CaptchaPlan(captcha_type=captcha_type, raw_response=parsed)

    response_type = parsed.get("type", "")

    if response_type == "image_grid":
        plan.captcha_type = CaptchaType.IMAGE_GRID
        plan.grid_cells = parsed.get("cells", [])

    elif response_type == "image_click":
        plan.captcha_type = CaptchaType.IMAGE_CLICK
        raw_points = parsed.get("points", [])
        # Chuẩn hóa từ 0-1000 → 0-1
        plan.click_points = [(p[0] / 1000, p[1] / 1000) for p in raw_points if len(p) >= 2]

    elif response_type == "slider":
        plan.captcha_type = CaptchaType.SLIDER
        plan.slider_offset = parsed.get("offset_ratio", 0.0)

    elif response_type == "text_ocr":
        plan.captcha_type = CaptchaType.TEXT_OCR
        plan.text_answer = parsed.get("text", "")

    return plan
