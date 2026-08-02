from __future__ import annotations

import json
from dataclasses import asdict

import pytest

from src.config.loader import ConfigLoadError, load_template
from src.config.template import TemplateConfig
from src.shared.ui import Toast
from src.ui.template_close_transaction import (
    TEMPLATE_EDIT_DISCARD,
    TemplateCloseTransaction,
)
from src.ui.template_edit_session import TemplateDraftStore


class _Bridge:
    def __init__(self) -> None:
        self.restore_calls: list[bool] = []

    def capture_state_snapshot(self) -> object:
        return {"template": "committed"}

    def restore_state_snapshot(
        self,
        snapshot: object,
        *,
        emit_signal: bool,
    ) -> None:
        assert snapshot == {"template": "committed"}
        self.restore_calls.append(emit_signal)


class _CloseHost:
    def __init__(self) -> None:
        self.bridge = _Bridge()
        self._draft_store = TemplateDraftStore()
        self._draft_context = self._draft_store.activate(
            TemplateConfig(),
            mode_id="custom",
            template_id="default",
            source="library",
            source_type="builtin",
        )
        self._edit_session = self._draft_context.session
        self._edit_session.draft.name = "关闭前草稿"
        self._current_template_id = "default"
        self._current_template_path = ""
        self._current_template_source = "library"
        self._current_template_source_type = "builtin"
        self._current_template = self._edit_session.draft
        self.projection_calls: list[str] = []

    def _prompt_close_template_draft_action(self, count: int) -> str:
        assert count == 1
        return TEMPLATE_EDIT_DISCARD

    def _set_detail_templates(self, template: TemplateConfig) -> None:
        self.projection_calls.append(f"detail:{template.name}")

    def _set_detail_save_enabled(self, enabled: bool) -> None:
        self.projection_calls.append(f"save:{enabled}")

    def _refresh_template_selector_options(self) -> None:
        raise ConfigLoadError("旧进程无法识别较新的模板字段")

    def _sync_template_file_status(self) -> None:
        self.projection_calls.append("file-status")

    def _refresh_overview_projection(self, *, reason: str) -> None:
        self.projection_calls.append(reason)


def test_unknown_canonical_fields_explain_runtime_schema_drift(tmp_path) -> None:
    payload = asdict(TemplateConfig())
    payload["section"]["future_field"] = True
    path = tmp_path / "future-template.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ConfigLoadError) as captured:
        load_template(path)

    message = str(captured.value)
    assert "存在未支持字段" in message
    assert "应用在代码更新前已经启动" in message
    assert "不要用旧窗口覆盖保存" in message


def test_rollback_keeps_recovered_draft_when_selector_projection_fails(
    monkeypatch,
) -> None:
    host = _CloseHost()
    transaction = TemplateCloseTransaction(host)
    warnings: list[str] = []
    monkeypatch.setattr(Toast, "show_warning", warnings.append)

    assert transaction.prepare() is True
    host._edit_session.draft.name = "快照之后的临时状态"

    assert transaction.rollback() is True
    assert host._edit_session.draft.name == "关闭前草稿"
    assert host.bridge.restore_calls == [False, True]
    assert "file-status" in host.projection_calls
    assert "template_close_rolled_back" in host.projection_calls
    assert len(warnings) == 1
    assert "模板列表" in warnings[0]
    assert "草稿状态已恢复" in warnings[0]
