"""5 Tiers of Browser Control Architecture."""

from .tier1_api_replay import Tier1APIReplayExecutor
from .tier2_playwright import Tier2PlaywrightExecutor
from .tier3_stagehand import Tier3StagehandExecutor
from .tier4_vision import Tier4VisionExecutor
from .tier5_typesafe_jev import Tier5TypeSafeJevExecutor

__all__ = [
    "Tier1APIReplayExecutor",
    "Tier2PlaywrightExecutor",
    "Tier3StagehandExecutor",
    "Tier4VisionExecutor",
    "Tier5TypeSafeJevExecutor",
]
