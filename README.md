# Module Browser Control (Role D) — vb-browser-use

Dự án tự động hoá điều khiển trình duyệt (Browser Automation & AI Agents) cho hệ thống đặt bàn đa kênh theo tài liệu kiến trúc **System Design v2.1** và phân vùng **Role D** trong `folder-structure-team.md`.

---

## 1. Cấu trúc thư mục phân vùng Role D

```text
vb-browser-use/
├── src/booking_agent/
│   ├── browser_control/                  # Vùng sở hữu chính của Role D (EPIC-3)
│   │   ├── __init__.py
│   │   ├── port.py                       # Hợp đồng BrowserControlPort & Adaptive Fallback (MVP-34)
│   │   ├── detector.py                   # Settle strategy (MVP-35) & Success/Failure Detector (MVP-38)
│   │   ├── tiers/                        # 4 Cấp điều khiển thác đổ
│   │   │   ├── __init__.py
│   │   │   ├── tier1_api_replay.py       # MVP-30: Cấp 1 — Direct API Replay
│   │   │   ├── tier2_playwright.py       # MVP-31: Cấp 2 — Playwright Workflow tham số hóa
│   │   │   ├── tier3_stagehand.py        # MVP-32: Cấp 3 — Stagehand AI DOM Discovery
│   │   │   └── tier4_vision.py           # MVP-33: Cấp 4 — Browser-Use Multimodal Vision & Jev Mode
│   │   └── learning/
│   │       ├── __init__.py
│   │       ├── network_sniffer.py        # MVP-36: CDP Network Sniffer
│   │       └── action_recorder.py        # Stagehand Action Recorder
│   │
│   └── browser_infra/                    # Các file do Role D phụ trách trong infra
│       ├── cdp_gateway.py                # MVP-02: Unified CDP/WebSocket Gateway
│       └── liveview.py                   # MVP-27 & MVP-28: Live View HITL mức tối giản
│
└── tests/unit/
    └── test_browser_control.py           # Bộ unit tests cho toàn bộ các task Role D
```

---

## 2. Bảng ánh xạ mã Task Jira (Backlog Checklist)

| Mã Task Jira | File mã nguồn | Mô tả nghiệm thu | Trạng thái |
| :--- | :--- | :--- | :---: |
| **MVP-02** | `browser_infra/cdp_gateway.py` | Unified CDP/WS Gateway, kiểm tra capability Chromium & Camoufox | ✅ Xong |
| **MVP-27 / 28** | `browser_infra/liveview.py` | Live View stream 1-2 FPS qua WebSocket cho khách nhập OTP | ✅ Xong |
| **MVP-30** | `browser_control/tiers/tier1_api_replay.py` | Cấp 1 Direct API Replay, $0 token, đo đếm WAF block | ✅ Xong |
| **MVP-31** | `browser_control/tiers/tier2_playwright.py` | Cấp 2 Playwright Workflow tham số hoá, 0 token, < 1s | ✅ Xong |
| **MVP-32** | `browser_control/tiers/tier3_stagehand.py` | Cấp 3 Stagehand DOM Pruning + Gemini AI, bóc tách selector | ✅ Xong |
| **MVP-33** | `browser_control/tiers/tier4_vision.py` | Cấp 4 Browser-Use + Multimodal Vision API & Jev Mode | ✅ Xong |
| **MVP-34** | `browser_control/port.py` | Hot-Swap Fallback không gián đoạn giữa 4 cấp | ✅ Xong |
| **MVP-35 / 38** | `browser_control/detector.py` | Settle Strategy chuẩn hoá & Bộ phân loại kết quả đặt bàn | ✅ Xong |
| **MVP-36** | `browser_control/learning/network_sniffer.py` | CDP Network Sniffer bắt request API thô | ✅ Xong |
| **MVP-37** | *(Bị huỷ)* | Theo quyết định chính thức ngày 18/11: Bỏ kênh MXH | ❌ Huỷ |

---

## 3. Chạy kiểm thử tự động (Unit Tests)

```bash
PYTHONPATH=src pytest tests/unit/test_browser_control.py
```
*(Kết quả: 8/8 tests pass 100%)*
