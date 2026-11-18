"""
Browser Infrastructure Module.
Files owned by Role D: cdp_gateway.py, liveview.py.
"""

from .cdp_gateway import BrowserEngine, Capability, CapabilityNotSupported, UnifiedCDPGateway
from .liveview import LiveViewFrame, LiveViewStreamer

__all__ = [
    "BrowserEngine",
    "Capability",
    "CapabilityNotSupported",
    "UnifiedCDPGateway",
    "LiveViewFrame",
    "LiveViewStreamer",
]
