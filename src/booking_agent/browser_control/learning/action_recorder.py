"""
Stagehand Action Recorder.
Owner: Role D (Browser Control).

Ghi nhận các selector và thao tác mà Stagehand (Cấp 3) tìm thấy trong lượt chạy đầu tiên,
sau đó biên dịch thành kịch bản Playwright (Cấp 2) để tái sử dụng với chi phí 0đ từ lần 2.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class RecordedAction:
    step_name: str
    selector: str
    action_type: str  # "fill" | "click" | "select"
    variable_binding: Optional[str] = None  # e.g. "customer_name"


class ActionRecorder:
    """Biên dịch các phát hiện từ Stagehand sang Playwright Workflow."""

    def __init__(self):
        self._actions: List[RecordedAction] = []

    def record_step(
        self,
        step_name: str,
        selector: str,
        action_type: str = "fill",
        variable_binding: Optional[str] = None,
    ) -> None:
        self._actions.append(
            RecordedAction(
                step_name=step_name,
                selector=selector,
                action_type=action_type,
                variable_binding=variable_binding,
            )
        )

    def export_playwright_selectors(self) -> Dict[str, str]:
        """Xuất map selector theo tên trường để lưu vào Registry."""
        return {
            action.variable_binding or action.step_name: action.selector
            for action in self._actions
        }
