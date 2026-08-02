"""Best-effort UI projection refresh after template-close rollback."""

from __future__ import annotations

import logging
from typing import Any


_LOGGER = logging.getLogger(__name__)


def refresh_template_close_rollback_projections(
    host: Any,
    *,
    bridge_state: object,
) -> tuple[str, ...]:
    """Refresh non-authoritative views without invalidating recovered drafts."""

    projection_steps = (
        (
            "模板编辑区",
            lambda: host._set_detail_templates(host._current_template),
        ),
        (
            "保存状态",
            lambda: host._set_detail_save_enabled(host._edit_session.is_dirty()),
        ),
        ("模板列表", host._refresh_template_selector_options),
        ("模板文件状态", host._sync_template_file_status),
        (
            "模板概览",
            lambda: host._refresh_overview_projection(
                reason="template_close_rolled_back"
            ),
        ),
        (
            "跨面板通知",
            lambda: host.bridge.restore_state_snapshot(
                bridge_state,
                emit_signal=True,
            ),
        ),
    )
    errors: list[str] = []
    for label, refresh in projection_steps:
        try:
            refresh()
        except Exception:
            errors.append(label)
            _LOGGER.exception(
                "template rollback restored authoritative state, "
                "but projection refresh failed: %s",
                label,
            )
    return tuple(errors)
