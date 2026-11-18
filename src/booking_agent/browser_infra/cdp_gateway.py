"""
MVP-02: Unified CDP/WebSocket Gateway.
Owner: Role D (Browser Control).

Cổng giao tiếp duy nhất (Unified Gateway) kết nối qua Chrome DevTools Protocol (CDP) / WebSocket
giúp tầng điều khiển (Browser Control) giao tiếp trong suốt với cả 2 engine:
- Chromium / Patchright (Engine tiêu chuẩn)
- Camoufox (Engine chống phát hiện vân tay bot)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Set
import asyncio


class BrowserEngine(str, Enum):
    CHROMIUM = "chromium"
    PATCHRIGHT = "patchright"
    CAMOUFOX = "camoufox"


class Capability(str, Enum):
    CDP_ACCESSIBILITY = "cdp_accessibility"
    CDP_NETWORK_INSPECT = "cdp_network_inspect"
    SCREENSHOT = "screenshot"
    STEALTH_FINGERPRINT = "stealth_fingerprint"
    NATIVE_FIREFOX_BIDI = "native_firefox_bidi"


class CapabilityNotSupported(Exception):
    """Ném ra khi adapter không hỗ trợ tính năng được yêu cầu."""
    pass


@dataclass
class EngineCapabilityDeclaration:
    engine: BrowserEngine
    supported_capabilities: Set[Capability]
    max_resolution: str = "1920x1080"
    supports_screencast: bool = True


ENGINE_CAPABILITIES: Dict[BrowserEngine, EngineCapabilityDeclaration] = {
    BrowserEngine.CHROMIUM: EngineCapabilityDeclaration(
        engine=BrowserEngine.CHROMIUM,
        supported_capabilities={
            Capability.CDP_ACCESSIBILITY,
            Capability.CDP_NETWORK_INSPECT,
            Capability.SCREENSHOT,
        },
    ),
    BrowserEngine.PATCHRIGHT: EngineCapabilityDeclaration(
        engine=BrowserEngine.PATCHRIGHT,
        supported_capabilities={
            Capability.CDP_ACCESSIBILITY,
            Capability.CDP_NETWORK_INSPECT,
            Capability.SCREENSHOT,
            Capability.STEALTH_FINGERPRINT,
        },
    ),
    BrowserEngine.CAMOUFOX: EngineCapabilityDeclaration(
        engine=BrowserEngine.CAMOUFOX,
        supported_capabilities={
            Capability.SCREENSHOT,
            Capability.STEALTH_FINGERPRINT,
            Capability.CDP_NETWORK_INSPECT,
        },
    ),
}


@dataclass
class CDPConnection:
    endpoint_url: str
    engine: BrowserEngine
    session_id: str
    capabilities: Set[Capability]
    is_active: bool = True

    def verify_capability(self, required: Capability) -> None:
        """Kiểm tra capability lúc định tuyến (0 ms) để tránh lỗi giữa chừng."""
        if required not in self.capabilities:
            raise CapabilityNotSupported(
                f"Engine '{self.engine.value}' không hỗ trợ capability '{required.value}'. "
                f"Các capability được hỗ trợ: {[c.value for c in self.capabilities]}"
            )


class UnifiedCDPGateway:
    """Gateway duy nhất quản lý các kết nối CDP endpoint cho tầng điều khiển."""

    def __init__(self):
        self._connections: Dict[str, CDPConnection] = {}

    def register_endpoint(
        self,
        session_id: str,
        endpoint_url: str,
        engine: BrowserEngine,
    ) -> CDPConnection:
        """Đăng ký một trình duyệt đang chạy vào Gateway."""
        declaration = ENGINE_CAPABILITIES.get(engine)
        caps = declaration.supported_capabilities if declaration else set()

        conn = CDPConnection(
            endpoint_url=endpoint_url,
            engine=engine,
            session_id=session_id,
            capabilities=caps,
        )
        self._connections[session_id] = conn
        return conn

    def get_connection(self, session_id: str) -> CDPConnection:
        if session_id not in self._connections:
            raise KeyError(f"Không tìm thấy kết nối CDP cho session '{session_id}'")
        return self._connections[session_id]

    def close_connection(self, session_id: str) -> None:
        if session_id in self._connections:
            self._connections[session_id].is_active = False
            del self._connections[session_id]
