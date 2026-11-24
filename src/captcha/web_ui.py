"""Web Chat & Pipeline Telemetry UI cho Agent 3 tầng.

Giao diện FastAPI cho phép:
- Nhập tên web / URL vào khung chat để agent mở trình duyệt
- Theo dõi trực quan agent đang chạy ở tầng nào (Detect → Tầng 1 → Tầng 2 → Tầng 3)
- Xem thời gian xử lý (latency), chi phí ước tính (cost), log trực tiếp và ảnh chụp màn hình

Chạy:
    cd foxprofile
    source .venv/bin/activate
    python src/captcha/web_ui.py
Mở trình duyệt tại: http://127.0.0.1:8765
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.captcha.models import SolveStatus  # noqa: E402
from src.captcha.solver import CaptchaSolver  # noqa: E402

SCREENSHOT_DIR = os.path.abspath("receipts/web_ui")
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

app = FastAPI(title="Agent 3-Tier Pipeline Monitor")


# ═══════════════════════════════════════════════════════════════════════
# State & Log Capture
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class RunState:
    run_id: str
    target_input: str
    url: str
    status: str = "running"          # running | completed | error
    current_stage: str = "init"      # init | navigate | detect | tier1 | tier2 | tier3 | done
    tier_used: int = 0
    captcha_type: str = "-"
    attempts: int = 0
    started_at: float = field(default_factory=time.perf_counter)
    elapsed_s: float = 0.0
    estimated_cost_usd: float = 0.0
    result_status: str = "-"
    result_message: str = ""
    screenshot_file: str = ""
    logs: list[dict[str, str]] = field(default_factory=list)


RUNS: dict[str, RunState] = {}
ACTIVE_LOCK = asyncio.Lock()


class RunLogHandler(logging.Handler):
    """Bắt log từ src.captcha.* để cập nhật stage & hiển thị lên UI."""

    def __init__(self, run: RunState):
        super().__init__()
        self.run = run

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        ts = datetime.now().strftime("%H:%M:%S")
        self.run.logs.append({
            "time": ts,
            "level": record.levelname,
            "logger": record.name.replace("src.captcha.", ""),
            "message": msg,
        })

        # Suy luận stage hiện tại từ log của pipeline
        if "Tầng 1" in msg:
            self.run.current_stage = "tier1"
            self.run.tier_used = 1
        elif "Tầng 2" in msg:
            self.run.current_stage = "tier2"
            self.run.tier_used = 2
            if "Gọi VLM" in msg:
                # Ước tính chi phí tham khảo mỗi lần gọi VLM (~$0.002/call)
                self.run.estimated_cost_usd = round(self.run.estimated_cost_usd + 0.002, 4)
        elif "Tầng 3" in msg:
            self.run.current_stage = "tier3"
            self.run.tier_used = 3
        elif "Phát hiện captcha:" in msg:
            self.run.current_stage = "detect"
            if "type=" in msg:
                self.run.captcha_type = msg.split("type=")[1].split(",")[0].strip()


def _normalize_url(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    # Nếu người dùng gõ tên web ngắn gọn như "buffetposeidon.com" hoặc "google.com"
    if "." in text and " " not in text:
        return f"https://{text}"
    # Fallback tìm kiếm Google nếu nhập tên thương hiệu có dấu cách
    from urllib.parse import quote_plus
    return f"https://www.google.com/search?q={quote_plus(text)}"


def _latest_screenshot(run_dir: str) -> str:
    if not os.path.isdir(run_dir):
        return ""
    pngs = [
        os.path.join(run_dir, f)
        for f in os.listdir(run_dir)
        if f.lower().endswith(".png")
    ]
    if not pngs:
        return ""
    latest = max(pngs, key=os.path.getmtime)
    return os.path.relpath(latest, SCREENSHOT_DIR)


async def _execute_run(run: RunState) -> None:
    run_dir = os.path.join(SCREENSHOT_DIR, run.run_id)
    os.makedirs(run_dir, exist_ok=True)

    handler = RunLogHandler(run)
    captcha_logger = logging.getLogger("src.captcha")
    captcha_logger.setLevel(logging.INFO)
    captcha_logger.addHandler(handler)

    try:
        from camoufox.async_api import AsyncCamoufox
    except ImportError:
        run.status = "error"
        run.current_stage = "done"
        run.result_message = "Chưa cài camoufox trong .venv"
        run.logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": "ERROR",
            "logger": "web_ui",
            "message": run.result_message,
        })
        captcha_logger.removeHandler(handler)
        return

    solver = CaptchaSolver(
        tier1_max_retries=2,
        tier2_max_retries=2,
        human_timeout=60.0,
        screenshot_dir=run_dir,
    )

    try:
        async with ACTIVE_LOCK:
            run.current_stage = "navigate"
            run.logs.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "level": "INFO",
                "logger": "web_ui",
                "message": f"Đang mở trình duyệt tới {run.url}",
            })

            async with AsyncCamoufox(headless=False, humanize=True) as browser:
                page = await browser.new_page()
                await page.goto(run.url, wait_until="domcontentloaded", timeout=30_000)
                await asyncio.sleep(2.5)

                initial_ss = os.path.join(run_dir, "00_page_loaded.png")
                await page.screenshot(path=initial_ss)
                run.screenshot_file = _latest_screenshot(run_dir)

                run.current_stage = "detect"
                result = await solver.solve(
                    page,
                    context_message=f"Chat UI target: {run.target_input}",
                )

                run.result_status = result.status.value
                run.result_message = result.message
                run.attempts = result.attempts
                if result.tier_used:
                    run.tier_used = result.tier_used
                elif result.status == SolveStatus.NO_CAPTCHA:
                    run.tier_used = 0

                final_ss = os.path.join(run_dir, "99_final.png")
                await page.screenshot(path=final_ss)
                run.screenshot_file = _latest_screenshot(run_dir)
                run.elapsed_s = round(time.perf_counter() - run.started_at, 2)
                run.current_stage = "done"
                run.status = "completed"
    except Exception as exc:
        run.status = "error"
        run.current_stage = "done"
        run.result_status = "error"
        run.result_message = str(exc)
        run.logs.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "level": "ERROR",
            "logger": "web_ui",
            "message": f"Lỗi thực thi: {exc}",
        })
    finally:
        run.elapsed_s = round(time.perf_counter() - run.started_at, 2)
        captcha_logger.removeHandler(handler)


# ═══════════════════════════════════════════════════════════════════════
# API Endpoints
# ═══════════════════════════════════════════════════════════════════════

class ChatRunRequest(BaseModel):
    target: str


@app.post("/api/run")
async def start_run(req: ChatRunRequest) -> dict[str, Any]:
    url = _normalize_url(req.target)
    if not url:
        raise HTTPException(status_code=400, detail="Vui lòng nhập tên web hoặc URL")

    run_id = uuid.uuid4().hex[:8]
    run = RunState(run_id=run_id, target_input=req.target.strip(), url=url)
    RUNS[run_id] = run
    asyncio.create_task(_execute_run(run))
    return {"run_id": run_id, "url": url}


@app.get("/api/run/{run_id}")
async def get_run_status(run_id: str) -> dict[str, Any]:
    run = RUNS.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Không tìm thấy run")

    elapsed = run.elapsed_s if run.status != "running" else round(time.perf_counter() - run.started_at, 2)
    run_dir = os.path.join(SCREENSHOT_DIR, run.run_id)
    latest = _latest_screenshot(run_dir)
    if latest:
        run.screenshot_file = latest

    return {
        "run_id": run.run_id,
        "target_input": run.target_input,
        "url": run.url,
        "status": run.status,
        "current_stage": run.current_stage,
        "tier_used": run.tier_used,
        "captcha_type": run.captcha_type,
        "attempts": run.attempts,
        "elapsed_s": elapsed,
        "estimated_cost_usd": run.estimated_cost_usd,
        "result_status": run.result_status,
        "result_message": run.result_message,
        "screenshot_url": f"/api/screenshot/{run.screenshot_file}" if run.screenshot_file else "",
        "logs": run.logs[-80:],
    }


@app.get("/api/screenshot/{file_path:path}")
async def serve_screenshot(file_path: str):
    full_path = os.path.abspath(os.path.join(SCREENSHOT_DIR, file_path))
    if not full_path.startswith(SCREENSHOT_DIR) or not os.path.isfile(full_path):
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh")
    return FileResponse(full_path, media_type="image/png")


# ═══════════════════════════════════════════════════════════════════════
# Single-Page Chat + Pipeline Dashboard UI
# ═══════════════════════════════════════════════════════════════════════

HTML_UI = """<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent 3-Tier Monitor</title>
<style>
  :root {
    --bg: #0b1220; --panel: #111a2e; --border: #23314d;
    --ink: #e2e8f0; --muted: #94a3b8; --accent: #38bdf8;
    --ok: #22c55e; --warn: #f59e0b; --err: #ef4444;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font: 14px/1.5 system-ui, -apple-system, sans-serif;
    height: 100vh; display: flex; flex-direction: column;
  }
  header {
    padding: 12px 20px; border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
    background: var(--panel);
  }
  header h1 { margin: 0; font-size: 16px; font-weight: 700; }
  header span { color: var(--muted); font-size: 12px; }
  .layout {
    flex: 1; display: grid; grid-template-columns: 380px 1fr;
    min-height: 0;
  }
  .chat-col {
    border-right: 1px solid var(--border); display: flex;
    flex-direction: column; background: var(--panel); min-height: 0;
  }
  .messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
  .msg { padding: 10px 12px; border-radius: 10px; max-width: 92%; font-size: 13px; }
  .msg.user { align-self: flex-end; background: #1d4ed8; color: #fff; }
  .msg.bot { align-self: flex-start; background: #1e293b; border: 1px solid var(--border); }
  .presets { padding: 8px 14px; display: flex; flex-wrap: wrap; gap: 6px; border-top: 1px solid var(--border); }
  .preset {
    background: #1e293b; color: var(--muted); border: 1px solid var(--border);
    border-radius: 999px; padding: 4px 10px; font-size: 12px; cursor: pointer;
  }
  .preset:hover { color: var(--ink); border-color: var(--accent); }
  .input-bar {
    padding: 12px; border-top: 1px solid var(--border);
    display: flex; gap: 8px;
  }
  .input-bar input {
    flex: 1; background: var(--bg); color: var(--ink);
    border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; outline: none;
  }
  .input-bar input:focus { border-color: var(--accent); }
  .input-bar button {
    background: var(--accent); color: #062033; font-weight: 700;
    border: none; border-radius: 8px; padding: 0 16px; cursor: pointer;
  }
  .main-col { padding: 16px; overflow-y: auto; display: flex; flex-direction: column; gap: 14px; }
  .stages { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
  .stage {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 8px; padding: 10px; text-align: center; font-size: 12px; color: var(--muted);
  }
  .stage.active { border-color: var(--accent); color: var(--accent); background: #0f253e; font-weight: 700; }
  .stage.done { border-color: var(--ok); color: var(--ok); }
  .stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }
  .stat { background: var(--panel); border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; }
  .stat small { display: block; color: var(--muted); font-size: 11px; }
  .stat b { font-size: 15px; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; min-height: 320px; }
  .card {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 10px; display: flex; flex-direction: column; overflow: hidden;
  }
  .card h3 { margin: 0; padding: 10px 12px; font-size: 13px; border-bottom: 1px solid var(--border); }
  .log-box {
    flex: 1; padding: 10px 12px; overflow-y: auto;
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px;
    max-height: 360px;
  }
  .log-line { margin-bottom: 4px; color: #cbd5e1; }
  .log-line .t { color: var(--muted); }
  .log-line.ERROR { color: var(--err); }
  .log-line.WARNING { color: var(--warn); }
  .shot-box { flex: 1; display: flex; align-items: center; justify-content: center; padding: 10px; background: #070c16; }
  .shot-box img { max-width: 100%; max-height: 340px; border-radius: 6px; border: 1px solid var(--border); }
  @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } .grid-2, .stages, .stats { grid-template-columns: 1fr 1fr; } }
</style>
</head>
<body>
<header>
  <h1>🤖 Agent 3-Tier Chat &amp; Pipeline Monitor</h1>
  <span>Detect → Tầng 1 (OCR) → Tầng 2 (VLM) → Tầng 3 (Human Handoff)</span>
</header>
<div class="layout">
  <div class="chat-col">
    <div class="messages" id="messages">
      <div class="msg bot">Nhập tên website hoặc URL bên dưới. Agent sẽ mở trình duyệt, phát hiện lớp xác minh, báo rõ đang chạy tầng nào, thời gian và chi phí ước tính.</div>
    </div>
    <div class="presets">
      <button class="preset" onclick="quickSend('https://www.google.com/recaptcha/api2/demo')">reCAPTCHA Demo</button>
      <button class="preset" onclick="quickSend('https://buffetposeidon.com/dat-ban?action=form&branch=1')">Poseidon Booking</button>
    </div>
    <form class="input-bar" onsubmit="sendChat(event)">
      <input id="targetInput" placeholder="VD: buffetposeidon.com hoặc URL đầy đủ..." autocomplete="off" />
      <button type="submit">Chạy</button>
    </form>
  </div>
  <div class="main-col">
    <div class="stages">
      <div class="stage" id="st-navigate">1. Mở trang</div>
      <div class="stage" id="st-detect">2. Detect</div>
      <div class="stage" id="st-tier1">3. Tầng 1 (OCR)</div>
      <div class="stage" id="st-tier2">4. Tầng 2 (VLM)</div>
      <div class="stage" id="st-tier3">5. Tầng 3 (Human)</div>
    </div>
    <div class="stats">
      <div class="stat"><small>Trạng thái</small><b id="val-status">Chờ lệnh</b></div>
      <div class="stat"><small>Tầng xử lý</small><b id="val-tier">-</b></div>
      <div class="stat"><small>Loại phát hiện</small><b id="val-type">-</b></div>
      <div class="stat"><small>Thời gian (Latency)</small><b id="val-time">0.0s</b></div>
      <div class="stat"><small>Chi phí ước tính (Cost)</small><b id="val-cost">$0.0000</b></div>
    </div>
    <div class="grid-2">
      <div class="card">
        <h3>📋 Log trực tiếp theo từng tầng</h3>
        <div class="log-box" id="logBox"></div>
      </div>
      <div class="card">
        <h3>📸 Ảnh chụp trình duyệt mới nhất</h3>
        <div class="shot-box" id="shotBox"><span style="color:var(--muted)">Chưa có ảnh chụp</span></div>
      </div>
    </div>
  </div>
</div>
<script>
let pollTimer = null;
const order = ['navigate', 'detect', 'tier1', 'tier2', 'tier3'];

function addMsg(text, cls) {
  const box = document.getElementById('messages');
  const div = document.createElement('div');
  div.className = 'msg ' + cls;
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

function quickSend(url) {
  document.getElementById('targetInput').value = url;
  sendChat(new Event('submit'));
}

async function sendChat(e) {
  e.preventDefault();
  const input = document.getElementById('targetInput');
  const target = input.value.trim();
  if (!target) return;
  input.value = '';
  addMsg(target, 'user');

  const res = await fetch('/api/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({target}),
  });
  const data = await res.json();
  if (!res.ok) {
    addMsg('Lỗi: ' + (data.detail || 'Không rõ'), 'bot');
    return;
  }
  addMsg('Đang chạy agent tới: ' + data.url + ' (run #' + data.run_id + ')', 'bot');
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(() => pollRun(data.run_id), 600);
  pollRun(data.run_id);
}

async function pollRun(runId) {
  const res = await fetch('/api/run/' + runId);
  if (!res.ok) return;
  const d = await res.json();

  document.getElementById('val-status').textContent = d.status === 'running' ? d.current_stage : d.result_status;
  document.getElementById('val-tier').textContent = d.tier_used ? ('Tầng ' + d.tier_used) : '-';
  document.getElementById('val-type').textContent = d.captcha_type;
  document.getElementById('val-time').textContent = d.elapsed_s + 's';
  document.getElementById('val-cost').textContent = '$' + d.estimated_cost_usd.toFixed(4);

  const curIdx = order.indexOf(d.current_stage);
  order.forEach((st, idx) => {
    const el = document.getElementById('st-' + st);
    el.classList.remove('active', 'done');
    if (d.status !== 'running' && idx <= curIdx) el.classList.add('done');
    else if (st === d.current_stage) el.classList.add('active');
    else if (curIdx > idx) el.classList.add('done');
  });

  const logBox = document.getElementById('logBox');
  logBox.innerHTML = d.logs.map(l =>
    `<div class="log-line ${l.level}"><span class="t">[${l.time}]</span> [${l.logger}] ${escapeHtml(l.message)}</div>`
  ).join('');
  logBox.scrollTop = logBox.scrollHeight;

  if (d.screenshot_url) {
    document.getElementById('shotBox').innerHTML = `<img src="${d.screenshot_url}?t=${Date.now()}" alt="screenshot">`;
  }

  if (d.status !== 'running') {
    clearInterval(pollTimer);
    pollTimer = null;
    addMsg(`Hoàn tất (${d.result_status}) · Tầng ${d.tier_used || 0} · ${d.elapsed_s}s · $${d.estimated_cost_usd.toFixed(4)} — ${d.result_message}`, 'bot');
  }
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
}
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return HTML_UI


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765)
