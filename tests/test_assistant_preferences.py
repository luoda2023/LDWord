from __future__ import annotations

from types import SimpleNamespace

from src.assistant.application.session_coordinator import AssistantSessionCoordinator
from src.assistant.runtime.providers.profiles import ProviderProfile, ProviderProfileStore
from src.assistant.runtime.providers.router import ProviderRouter
from src.assistant.runtime.providers.secrets import MemorySecretStore
from src.assistant.storage.session_store import AssistantSessionStore
from src.assistant.ui.assistant_panel import AssistantPanel
from src.ui.bridge import PanelBridge
from src.ui.panels.preferences_panel import PreferencesPanel
from PySide6.QtTest import QTest


def test_ai_preferences_store_profile_and_secret_separately(qapp, tmp_path):
    profiles = ProviderProfileStore(tmp_path / "providers.json")
    secrets = MemorySecretStore()
    bridge = PanelBridge()
    changes = []
    bridge.assistant_provider_profiles_changed.connect(lambda: changes.append(True))
    panel = PreferencesPanel(
        bridge,
        provider_profiles=profiles,
        provider_secrets=secrets,
    )
    try:
        panel._nav_rail.select_card("ai")
        panel._ai_new_button.click()
        panel._ai_label_input.setText("公司模型")
        panel._ai_url_input.setText("https://example.invalid/v1")
        panel._ai_model_input.setText("example-model")
        panel._ai_key_input.setText("super-secret")

        panel._save_ai_profile()

        saved = [item for item in profiles.list_profiles() if item.kind != "mock"]
        assert len(saved) == 1
        assert saved[0].label == "公司模型"
        assert secrets.get(saved[0].profile_id) == "super-secret"
        assert "super-secret" not in (tmp_path / "providers.json").read_text(encoding="utf-8")
        assert changes == [True]
        assert "正文仍需" in panel._ai_status.text()
    finally:
        panel.close()


def test_ai_preferences_mock_profile_needs_no_key(qapp, tmp_path):
    panel = PreferencesPanel(
        PanelBridge(),
        provider_profiles=ProviderProfileStore(tmp_path / "providers.json"),
        provider_secrets=MemorySecretStore(),
    )
    try:
        panel._nav_rail.select_card("ai")
        assert panel._ai_profile_combo.currentData() == "mock-default"
        assert not panel._ai_key_input.isEnabled()
        panel._check_ai_profile()
        for _attempt in range(50):
            qapp.processEvents()
            if panel._provider_probe_worker is None:
                break
            QTest.qWait(10)
        assert "连接测试成功" in panel._ai_status.text()
        assert "不包含文档内容" in panel._ai_status.text()
        assert panel._ai_profile_combo.isEnabled()
        assert panel._ai_new_button.isEnabled()
    finally:
        panel.close()


def test_ai_preferences_refuses_incomplete_cloud_profile(qapp, tmp_path):
    profiles = ProviderProfileStore(tmp_path / "providers.json")
    panel = PreferencesPanel(
        PanelBridge(),
        provider_profiles=profiles,
        provider_secrets=MemorySecretStore(),
    )
    try:
        panel._ai_new_button.click()
        panel._ai_label_input.setText("缺少密钥的模型")
        panel._ai_url_input.setText("https://example.invalid/v1")
        panel._ai_model_input.setText("example-model")

        panel._save_ai_profile()

        assert [item for item in profiles.list_profiles() if item.kind != "mock"] == []
        assert "API Key" in panel._ai_status.text()
        assert panel._ai_form_dirty is True
    finally:
        panel.close()


def test_ai_preferences_unsaved_edit_cannot_test_stale_profile(qapp, tmp_path):
    profiles = ProviderProfileStore(tmp_path / "providers.json")
    secrets = MemorySecretStore()
    panel = PreferencesPanel(
        PanelBridge(),
        provider_profiles=profiles,
        provider_secrets=secrets,
    )
    try:
        assert panel._ai_check_button.isEnabled()
        panel._ai_label_input.setText("被修改的名称")

        assert panel._ai_form_dirty is True
        assert not panel._ai_check_button.isEnabled()
        assert "先保存" in panel._ai_check_button.toolTip()
        panel._check_ai_profile()
        assert "先保存修改" in panel._ai_status.text()
    finally:
        panel.close()


def test_ai_preferences_rolls_back_secret_when_profile_save_fails(qapp, tmp_path):
    class FailingProfileStore(ProviderProfileStore):
        def upsert(self, profile):
            raise OSError("disk unavailable")

    profiles = FailingProfileStore(tmp_path / "providers.json")
    secrets = MemorySecretStore()
    panel = PreferencesPanel(
        PanelBridge(),
        provider_profiles=profiles,
        provider_secrets=secrets,
    )
    try:
        panel._ai_new_button.click()
        panel._ai_label_input.setText("公司模型")
        panel._ai_url_input.setText("https://example.invalid/v1")
        panel._ai_model_input.setText("example-model")
        panel._ai_key_input.setText("temporary-secret")

        panel._save_ai_profile()

        assert secrets._values == {}
        assert "原配置已恢复" in panel._ai_status.text()
    finally:
        panel.close()


def test_saved_ai_profile_hot_syncs_into_assistant_home(qapp, tmp_path):
    profiles = ProviderProfileStore(tmp_path / "providers.json")
    secrets = MemorySecretStore()
    bridge = PanelBridge()
    assistant = AssistantPanel(
        bridge,
        coordinator=AssistantSessionCoordinator(
            AssistantSessionStore(tmp_path / "assistant")
        ),
        provider_router=ProviderRouter(profiles=profiles, secrets=secrets),
        first_level=True,
    )
    preferences = PreferencesPanel(
        bridge,
        provider_profiles=profiles,
        provider_secrets=secrets,
    )
    try:
        preferences._ai_new_button.click()
        preferences._ai_label_input.setText("公司模型")
        preferences._ai_url_input.setText("https://example.invalid/v1")
        preferences._ai_model_input.setText("example-model")
        preferences._ai_key_input.setText("secret-value")
        preferences._save_ai_profile()
        qapp.processEvents()

        saved = [item for item in profiles.list_profiles() if item.kind != "mock"]
        assert len(saved) == 1
        combo = assistant._creative_home.composer._model_combo
        cloud_index = next(
            index
            for index in range(combo.count())
            if combo.itemData(index) == saved[0].profile_id
        )
        assert combo.itemText(cloud_index).startswith("公司模型")
        assert "未测试" in combo.itemText(cloud_index)
        assert combo.model().item(cloud_index).isEnabled()
        assistant._creative_home.composer.select_provider(saved[0].profile_id)
        assistant._creative_home.composer.set_text("生成一份报告")
        assert assistant._creative_home.composer._send_btn.isEnabled()
    finally:
        preferences.close()
        assistant.close()


def test_provider_connection_result_is_persisted_and_projected(qapp, tmp_path):
    profiles = ProviderProfileStore(tmp_path / "providers.json")
    secrets = MemorySecretStore()
    bridge = PanelBridge()
    panel = PreferencesPanel(
        bridge,
        provider_profiles=profiles,
        provider_secrets=secrets,
    )
    try:
        panel._ai_new_button.click()
        panel._ai_label_input.setText("公司模型")
        panel._ai_url_input.setText("https://example.invalid/v1")
        panel._ai_model_input.setText("example-model")
        panel._ai_key_input.setText("secret-value")
        panel._save_ai_profile()
        profile = next(item for item in profiles.list_profiles() if item.kind != "mock")

        panel._provider_probe_profile_id = profile.profile_id
        panel._on_provider_probe_finished(
            SimpleNamespace(success=True, message="provider_connection_ok")
        )

        verified = profiles.get(profile.profile_id)
        assert verified.connection_status == "success"
        assert verified.last_checked_at
        assert verified.last_check_message == ""
        assert "已验证" in panel._ai_profile_combo.currentText()
        assert "连接测试成功" in panel._ai_status.text()
    finally:
        panel.close()


def test_editing_profile_preserves_hidden_fields_and_only_invalidates_changed_connection(
    qapp,
    tmp_path,
):
    profiles = ProviderProfileStore(tmp_path / "providers.json")
    profile = ProviderProfile(
        profile_id="cloud-main",
        label="公司模型",
        kind="openai_compatible",
        model_id="model-v1",
        base_url="https://example.invalid/v1",
        timeout_seconds=17.0,
        enabled=False,
        extra_body={"temperature": 0.2},
        connection_status="success",
        last_checked_at="2026-07-16T20:00:00+08:00",
    )
    profiles.upsert(profile)
    panel = PreferencesPanel(
        PanelBridge(),
        provider_profiles=profiles,
        provider_secrets=MemorySecretStore({"cloud-main": "secret-value"}),
    )
    try:
        cloud_index = next(
            index
            for index in range(panel._ai_profile_combo.count())
            if panel._ai_profile_combo.itemData(index) == "cloud-main"
        )
        panel._ai_profile_combo.setCurrentIndex(cloud_index)
        panel._ai_label_input.setText("公司主模型")
        panel._save_ai_profile()

        renamed = profiles.get("cloud-main")
        assert renamed.timeout_seconds == 17.0
        assert renamed.enabled is False
        assert renamed.extra_body == {"temperature": 0.2}
        assert renamed.connection_status == "success"
        assert renamed.last_checked_at == "2026-07-16T20:00:00+08:00"

        panel._ai_model_input.setText("model-v2")
        panel._save_ai_profile()
        changed = profiles.get("cloud-main")
        assert changed.connection_status == "untested"
        assert changed.last_checked_at == ""
    finally:
        panel.close()


def test_model_settings_entry_navigates_directly_to_ai_page(qapp, tmp_path):
    bridge = PanelBridge()
    destinations = []
    bridge.navigate_to_panel.connect(destinations.append)
    preferences = PreferencesPanel(
        bridge,
        provider_profiles=ProviderProfileStore(tmp_path / "providers.json"),
        provider_secrets=MemorySecretStore(),
    )
    assistant = AssistantPanel(
        bridge,
        coordinator=AssistantSessionCoordinator(
            AssistantSessionStore(tmp_path / "assistant-settings-route")
        ),
        first_level=True,
    )
    try:
        assistant._creative_home.composer._model_settings_button.click()
        qapp.processEvents()

        assert bridge.preferred_preferences_page() == "ai"
        assert destinations
        assert not preferences._ai_content.isHidden()
        assert preferences._content.isHidden()
    finally:
        assistant.close()
        preferences.close()
