# Module `src/captcha` — Hệ thống xử lý CAPTCHA 3 tầng & Web Chat UI

## 1. Danh sách file trong `src/captcha/`

| File | Chức năng |
|---|---|
| `__init__.py` | Export `CaptchaSolver` |
| `models.py` | Các data model (`CaptchaType`, `SolveStatus`, `BoundingBox`, `CaptchaPlan`, `SolveResult`) |
| `detector.py` | Phát hiện, phân loại CAPTCHA trên trang và chụp ảnh vùng CAPTCHA |
| `tier1_text.py` | **Tầng 1:** Giải CAPTCHA chữ/số local bằng `ddddocr` |
| `tier2_vlm.py` | **Tầng 2:** Gọi VLM API phân tích CAPTCHA hình ảnh (grid, click, slider) |
| `tier3_human.py` | **Tầng 3:** Human-in-the-loop — chụp ảnh, thông báo console và chờ người xử lý trên trình duyệt |
| `solver.py` | Orchestrator điều phối luồng 3 tầng (`Tầng 1 → Tầng 2 → Tầng 3`) |
| `browser_use_integration.py` | Custom tool `solve_captcha` tích hợp vào `browser-use` |
| `web_ui.py` | Giao diện Web Chat & Pipeline Monitor (FastAPI) |
| `demo.py` | Script demo cấu trúc từng tầng |
| `test_demo_pages.py` | Script chạy thử trên các trang demo công khai |

---

## 2. Cài đặt môi trường (cho máy mới pull về)

Yêu cầu **Python 3.11** (không nên dùng 3.14 vì `onnxruntime` chưa hỗ trợ wheel).

```bash
git checkout captcha
git pull origin captcha

python3.11 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
pip install "opencv-python<5" --only-binary=:all:
pip install ddddocr
```

> **Lưu ý trên macOS:** Cần cài `"opencv-python<5" --only-binary=:all:` trước để tránh `pip` tải mã nguồn C++ của OpenCV 5.x về build rất lâu.

Tải trình duyệt Camoufox (nếu chạy lần đầu):
```bash
python -m camoufox fetch
```

---

## 3. Cấu hình Tầng 2 (VLM API)

Mở file `src/captcha/tier2_vlm.py` và kiểm tra `VLM_CONFIG`:
- `base_url`: URL endpoint OpenAI-compatible
- `model`: tên model VLM
- `api_key`: API key hợp lệ

---

## 4. Cách chạy và dùng Web Chat UI

Khởi động server giao diện web:
```bash
source .venv/bin/activate
python src/captcha/web_ui.py
```

Mở trình duyệt tại: **http://127.0.0.1:8765**

### Hướng dẫn sử dụng giao diện:
1. **Khung chat (bên trái):** Nhập tên website (ví dụ `buffetposeidon.com`) hoặc URL đầy đủ rồi bấm **Chạy**, hoặc bấm các nút preset bên dưới (`reCAPTCHA Demo`, `Poseidon Booking`).
2. **Thanh tiến trình (phía trên):** Theo dõi bước đang chạy (`1. Mở trang` → `2. Detect` → `3. Tầng 1 (OCR)` → `4. Tầng 2 (VLM)` → `5. Tầng 3 (Human)`).
3. **Bảng thông số:** Xem trạng thái hiện tại, tầng xử lý, loại phát hiện, thời gian chạy (`Latency`) và chi phí ước tính (`Cost`).
4. **Log trực tiếp & Ảnh chụp:** Theo dõi log từng tầng theo thời gian thực và xem ảnh chụp màn hình trình duyệt mới nhất (ảnh lưu trong `receipts/web_ui/`).

---

## 5. Chạy thử bằng dòng lệnh (CLI)

```bash
source .venv/bin/activate

# Kiểm tra các tầng độc lập
python src/captcha/demo.py

# Chạy test trên trang demo công khai
python src/captcha/test_demo_pages.py
```
