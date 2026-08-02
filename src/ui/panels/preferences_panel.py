"""Settings surface containing the single, user-facing About page."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from src.app_meta import APP_DISPLAY_NAME, APP_VERSION
from src.qt_api import (
    QDesktopServices,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSize,
    QSizePolicy,
    QUrl,
    QVBoxLayout,
    QWidget,
    Qt,
)
from src.services.problem_report import (
    build_problem_report,
    resolve_log_path,
)
from src.services.license_catalog import (
    LicenseCatalogError,
    load_license_catalog,
    read_project_license,
)
from src.shared.ui.badge import Badge
from src.shared.ui.button_style import apply_button_variant, build_button_stylesheet
from src.shared.ui.design_system_card import DesignSystemCard
from src.shared.ui.dialogs import confirm
from src.shared.ui.form_row import FormRow
from src.shared.ui.input_style import build_text_input_stylesheet
from src.shared.ui.master_detail_shell import MasterDetailShell
from src.shared.ui.navigation_card import NavigationCard
from src.shared.ui.license_dialog import LicenseDialog
from src.shared.ui.sizing import apply_size_class
from src.shared.ui.styled_combo_box import StyledComboBox
from src.shared.ui.theme import bind_theme, get_theme
from src.shared.ui.toast import Toast
from src.shared.ui.typography_policy import TextRole, apply_text_role, brand_font
from src.ui.base_panel import BasePanel
from src.shared.ui.icons.catalog import get_app_logo, get_icon
from src.assistant.provider_settings_facade import (
    HybridSecretStore,
    ProviderProbeWorker,
    ProviderProfile,
    ProviderProfileStore,
    ProviderResolutionError,
    ProviderRouter,
    ProviderSecretStore,
    provider_connection_badge,
    provider_connection_status_text,
    provider_error_text,
)


class _LicenseNavigationItem(QPushButton):
    """A low-emphasis navigation cell inside the surrounding license card."""

    def __init__(self, title: str, subtitle: str, *, icon_name: str, parent=None):
        super().__init__(parent)
        self.setObjectName("license_navigation_item")
        self.setText("")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setAccessibleName(f"{title}，{subtitle}")
        self._icon_name = icon_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 12, 8)
        layout.setSpacing(11)
        self._icon = QLabel(self)
        self._icon.setObjectName("license_navigation_icon")
        self._icon.setFixedSize(24, 24)
        self._icon.setAlignment(Qt.AlignCenter)
        self._icon.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(self._icon, 0, Qt.AlignVCenter)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)
        self._title = QLabel(title, self)
        self._title.setObjectName("license_navigation_title")
        self._title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        apply_text_role(self._title, TextRole.NAVIGATION_TITLE_ACTIVE)
        self._subtitle = QLabel(subtitle, self)
        self._subtitle.setObjectName("license_navigation_subtitle")
        self._subtitle.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        apply_text_role(self._subtitle, TextRole.CAPTION)
        text_layout.addWidget(self._title)
        text_layout.addWidget(self._subtitle)
        layout.addLayout(text_layout, 1)

        self._chevron = QLabel("›", self)
        self._chevron.setObjectName("license_navigation_chevron")
        self._chevron.setAlignment(Qt.AlignCenter)
        self._chevron.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        apply_text_role(self._chevron, TextRole.TITLE)
        layout.addWidget(self._chevron, 0, Qt.AlignVCenter)

        bind_theme(self, self._apply_theme)
        self._apply_theme()

    def set_subtitle(self, subtitle: str) -> None:
        normalized = str(subtitle or "").strip()
        self._subtitle.setText(normalized)
        self.setAccessibleName(f"{self._title.text()}，{normalized}")

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._icon.setPixmap(get_icon(self._icon_name, 18, theme.icon_primary).pixmap(18, 18))
        self.setStyleSheet(
            f"""
            QPushButton#license_navigation_item {{
                background: transparent;
                border: 1px solid transparent;
                border-radius: {theme.radius_md}px;
                padding: 0;
                text-align: left;
            }}
            QPushButton#license_navigation_item:hover {{
                background: {theme.bg_hover};
            }}
            QPushButton#license_navigation_item:pressed {{
                background: {theme.bg_selected};
            }}
            QPushButton#license_navigation_item:focus {{
                border-color: {theme.border_focus};
            }}
            QLabel#license_navigation_title {{
                color: {theme.text_primary};
                background: transparent;
            }}
            QLabel#license_navigation_subtitle {{
                color: {theme.text_secondary};
                background: transparent;
            }}
            QLabel#license_navigation_icon,
            QLabel#license_navigation_chevron {{
                color: {theme.primary};
                background: transparent;
                border: none;
            }}
            """
        )


class PreferencesPanel(BasePanel):
    """Application information and explicit AI provider configuration."""

    panel_title = "偏好设置"
    panel_icon = "settings"

    def __init__(
        self,
        bridge,
        parent=None,
        *,
        provider_profiles: ProviderProfileStore | None = None,
        provider_secrets: ProviderSecretStore | None = None,
    ) -> None:
        self._provider_profiles = provider_profiles or ProviderProfileStore()
        self._provider_secrets = provider_secrets or HybridSecretStore()
        self._provider_probe_worker: ProviderProbeWorker | None = None
        self._provider_probe_profile_id = ""
        self._loading_ai_form = False
        self._ai_form_dirty = False
        self._ai_loaded_profile_id = ""
        super().__init__(bridge, parent)

    def _setup_ui(self) -> None:
        self.setObjectName("PreferencesPanel")
        self.setAttribute(Qt.WA_StyledBackground, True)

        self._shell = MasterDetailShell(
            self,
            panel_name="PreferencesPanel",
            nav_object_name="preferences_navigation",
            detail_object_name="preferences_detail",
            detail_content_object_name="preferences_detail_content",
        )
        self._nav_rail = self._shell.nav_rail
        self._detail_layout = self._shell.detail_layout

        self._about_nav = NavigationCard(
            "about",
            "关于软件",
            icon_name="info",
            parent=self._nav_rail,
        )
        self._about_nav.set_subtitle("版本、问题处理和许可")
        self._about_nav.set_badge(APP_VERSION, "info")
        self._nav_rail.add_card("about", self._about_nav)
        self._ai_nav = NavigationCard(
            "ai",
            "AI 模型",
            icon_name="sparkles",
            parent=self._nav_rail,
        )
        self._ai_nav.set_subtitle("Provider、模型和密钥")
        self._nav_rail.add_card("ai", self._ai_nav)
        self._nav_rail.select_card("about")

        self._content = QWidget(self._shell.detail_container)
        self._content.setObjectName("preferences_about_content")
        self._content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 8, 0, 8)
        content_layout.setSpacing(16)

        self._page_title = QLabel("关于软件", self._content)
        self._page_title.setObjectName("preferences_page_title")
        apply_text_role(self._page_title, TextRole.PAGE_TITLE)
        content_layout.addWidget(self._page_title)

        self._identity_card = self._build_identity_card()
        self._support_card = self._build_support_card()
        self._license_card = self._build_license_card()
        for card in (
            self._identity_card,
            self._support_card,
            self._license_card,
        ):
            content_layout.addWidget(card)

        content_layout.addStretch(1)
        self._ai_content = self._build_ai_content()
        self._ai_content.hide()
        self._detail_layout.addWidget(self._content, 0, Qt.AlignTop)
        self._detail_layout.addWidget(self._ai_content, 0, Qt.AlignTop)
        self._detail_layout.addStretch(1)

        preferred_page = getattr(self.bridge, "preferred_preferences_page", lambda: "about")()
        if preferred_page == "ai":
            self._nav_rail.select_card("ai")
            self._select_settings_page("ai")

        self._apply_theme()
        bind_theme(self, self._apply_theme)

    def _connect_signals(self) -> None:
        self._open_log_button.clicked.connect(self._open_log_file)
        self._export_report_button.clicked.connect(self._export_problem_report)
        self._license_button.clicked.connect(self._show_project_license)
        self._third_party_button.clicked.connect(self._show_third_party_licenses)
        self._nav_rail.card_selected.connect(self._select_settings_page)
        self._ai_profile_combo.currentIndexChanged.connect(
            self._on_ai_profile_selection_changed
        )
        for field in (
            self._ai_label_input,
            self._ai_url_input,
            self._ai_model_input,
            self._ai_key_input,
        ):
            field.textChanged.connect(self._mark_ai_form_dirty)
        self._ai_save_button.clicked.connect(self._save_ai_profile)
        self._ai_delete_button.clicked.connect(self._delete_ai_profile)
        self._ai_check_button.clicked.connect(self._check_ai_profile)
        self._ai_new_button.clicked.connect(self._start_new_ai_profile)
        self.bridge.preferences_page_requested.connect(self.show_preferences_page)

    def _build_identity_card(self) -> DesignSystemCard:
        card = DesignSystemCard(parent=self._content)
        row = QHBoxLayout()
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(16)

        self._logo = QLabel(card)
        self._logo.setFixedSize(56, 56)
        self._logo.setAlignment(Qt.AlignCenter)
        row.addWidget(self._logo, 0, Qt.AlignVCenter)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(6)
        self._app_name = QLabel(APP_DISPLAY_NAME, card)
        self._app_name.setFont(
            brand_font(
                pixel_size=get_theme().font_size_xxl,
                weight=get_theme().font_weight_emphasis,
            )
        )
        version_row = QHBoxLayout()
        version_row.setContentsMargins(0, 0, 0, 0)
        version_row.setSpacing(8)
        self._version_label = QLabel("当前版本", card)
        self._version_badge = Badge(APP_VERSION, "info", parent=card)
        version_row.addWidget(self._version_label)
        version_row.addWidget(self._version_badge)
        version_row.addStretch(1)
        text_column.addWidget(self._app_name)
        text_column.addLayout(version_row)
        self._local_processing_note = QLabel(
            "文档仅在本机处理，不会自动上传。",
            card,
        )
        self._local_processing_note.setWordWrap(True)
        apply_text_role(self._local_processing_note, TextRole.BODY)
        text_column.addWidget(self._local_processing_note)
        row.addLayout(text_column, 1)

        card.add_layout(row)
        return card

    def _build_support_card(self) -> DesignSystemCard:
        card = DesignSystemCard("问题处理", parent=self._content)
        card.set_header("问题处理", icon_name="circle-help")

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(10)
        self._open_log_button = self._make_button(
            "打开日志文件",
            icon_name="folder-open",
        )
        self._export_report_button = self._make_button(
            "导出问题报告",
            icon_name="download",
            primary=True,
        )
        report_privacy = "报告不包含文档内容；用户名和本地路径会被隐藏。"
        self._export_report_button.setToolTip(report_privacy)
        self._export_report_button.setAccessibleDescription(report_privacy)
        actions.addWidget(self._open_log_button)
        actions.addWidget(self._export_report_button)
        actions.addStretch(1)
        card.add_layout(actions)

        return card

    def _build_license_card(self) -> DesignSystemCard:
        card = DesignSystemCard("软件许可", parent=self._content)
        card.set_header("软件许可", icon_name="file-text")

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(0)
        self._license_button = _LicenseNavigationItem(
            "本软件",
            "MIT License",
            icon_name="file-text",
            parent=card,
        )
        try:
            self._license_catalog = load_license_catalog()
            third_party_subtitle = f"{self._license_catalog.component_count} 个组件"
        except LicenseCatalogError:
            self._license_catalog = None
            third_party_subtitle = "查看使用到的组件"
        self._third_party_button = _LicenseNavigationItem(
            "第三方组件",
            third_party_subtitle,
            icon_name="boxes",
            parent=card,
        )
        divider = QFrame(card)
        divider.setObjectName("license_navigation_divider")
        divider.setFrameShape(QFrame.VLine)
        divider.setFrameShadow(QFrame.Plain)
        divider.setFixedWidth(1)
        actions.addWidget(self._license_button, 1)
        actions.addWidget(divider, 0)
        actions.addWidget(self._third_party_button, 1)
        card.add_layout(actions)
        return card

    def _build_ai_content(self) -> QWidget:
        content = QWidget(self._shell.detail_container)
        content.setObjectName("preferences_ai_content")
        content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        content.setMaximumWidth(960)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(16)

        self._ai_page_title = QLabel("AI 模型", content)
        self._ai_page_title.setObjectName("preferences_ai_page_title")
        apply_text_role(self._ai_page_title, TextRole.PAGE_TITLE)
        layout.addWidget(self._ai_page_title)

        self._ai_privacy_callout = QFrame(content)
        self._ai_privacy_callout.setObjectName("preferences_ai_privacy_callout")
        self._ai_privacy_callout.setAttribute(Qt.WA_StyledBackground, True)
        privacy_layout = QHBoxLayout(self._ai_privacy_callout)
        privacy_layout.setContentsMargins(12, 9, 12, 9)
        privacy_layout.setSpacing(10)
        self._ai_privacy_icon = QLabel(self._ai_privacy_callout)
        self._ai_privacy_icon.setFixedSize(18, 18)
        self._ai_privacy_icon.setAlignment(Qt.AlignCenter)
        privacy_layout.addWidget(self._ai_privacy_icon, 0, Qt.AlignTop)
        privacy_text = QVBoxLayout()
        privacy_text.setContentsMargins(0, 0, 0, 0)
        privacy_text.setSpacing(2)
        self._ai_privacy_title = QLabel("隐私与数据", self._ai_privacy_callout)
        apply_text_role(self._ai_privacy_title, TextRole.BODY)
        self._ai_privacy_note = QLabel(
            "密钥安全保存；文件不会自动上传，正文、图片和素材发送前会在 AI 助手中逐次确认。",
            self._ai_privacy_callout,
        )
        self._ai_privacy_note.setWordWrap(True)
        apply_text_role(self._ai_privacy_note, TextRole.CAPTION)
        privacy_detail = (
            "密钥优先从环境变量读取，手动保存时写入 Windows 凭据管理器。"
            "选择文件不会自动上传；正文、图片和素材发送前会在 AI 助手中逐次确认。"
        )
        self._ai_privacy_callout.setToolTip(privacy_detail)
        self._ai_privacy_callout.setAccessibleDescription(privacy_detail)
        privacy_text.addWidget(self._ai_privacy_title)
        privacy_text.addWidget(self._ai_privacy_note)
        privacy_layout.addLayout(privacy_text, 1)
        layout.addWidget(self._ai_privacy_callout)

        card = DesignSystemCard("模型配置", parent=content)
        card.set_header("模型配置", icon_name="sparkles")
        profile_selector = QWidget(card)
        profile_selector.setObjectName("preferences_ai_profile_selector")
        profile_selector_layout = QHBoxLayout(profile_selector)
        profile_selector_layout.setContentsMargins(0, 0, 0, 0)
        profile_selector_layout.setSpacing(8)
        self._ai_profile_combo = StyledComboBox(profile_selector)
        self._ai_profile_combo.setObjectName("preferences_ai_profile_combo")
        self._ai_profile_combo.set_full_width_mode(True)
        self._ai_profile_combo.setAccessibleName("当前模型配置")
        self._ai_new_button = QPushButton("新增配置", profile_selector)
        self._ai_new_button.setProperty("aboutIcon", "plus")
        self._ai_new_button.setAccessibleName("新增 AI 模型配置")
        apply_size_class(self._ai_new_button, "md")
        apply_button_variant(self._ai_new_button, "secondary")
        profile_selector_layout.addWidget(self._ai_profile_combo, 1)
        profile_selector_layout.addWidget(self._ai_new_button)
        card.add_widget(FormRow("当前配置", profile_selector, parent=card))

        self._ai_label_input = QLineEdit(card)
        self._ai_label_input.setPlaceholderText("例如：公司模型")
        self._ai_label_input.setAccessibleName("显示名称")
        apply_size_class(self._ai_label_input, "md")
        card.add_widget(FormRow("显示名称", self._ai_label_input, parent=card))
        self._ai_url_input = QLineEdit(card)
        self._ai_url_input.setPlaceholderText("https://api.example.com/v1")
        self._ai_url_input.setAccessibleName("API 地址")
        apply_size_class(self._ai_url_input, "md")
        card.add_widget(FormRow("API 地址", self._ai_url_input, parent=card))
        self._ai_model_input = QLineEdit(card)
        self._ai_model_input.setPlaceholderText("模型 ID")
        self._ai_model_input.setAccessibleName("模型 ID")
        apply_size_class(self._ai_model_input, "md")
        card.add_widget(FormRow("模型 ID", self._ai_model_input, parent=card))

        key_field = QWidget(card)
        key_field.setObjectName("preferences_ai_key_field")
        key_layout = QVBoxLayout(key_field)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.setSpacing(3)
        self._ai_key_input = QLineEdit(card)
        self._ai_key_input.setEchoMode(QLineEdit.Password)
        self._ai_key_input.setPlaceholderText("留空表示不修改已保存密钥")
        self._ai_key_input.setAccessibleName("API Key")
        apply_size_class(self._ai_key_input, "md")
        key_layout.addWidget(self._ai_key_input)
        self._ai_key_status = QLabel("", key_field)
        self._ai_key_status.setObjectName("preferences_ai_key_status")
        self._ai_key_status.setWordWrap(True)
        apply_text_role(self._ai_key_status, TextRole.CAPTION)
        key_layout.addWidget(self._ai_key_status)
        card.add_widget(FormRow("API Key", key_field, parent=card))

        connection_row = QWidget(card)
        connection_row.setObjectName("preferences_ai_connection_row")
        self._ai_connection_layout = QHBoxLayout(connection_row)
        self._ai_connection_layout.setContentsMargins(0, 6, 0, 2)
        self._ai_connection_layout.setSpacing(8)
        self._ai_state_badge = Badge("", "neutral", parent=connection_row)
        self._ai_connection_layout.addWidget(self._ai_state_badge, 0, Qt.AlignVCenter)
        self._ai_connection_status = QLabel("", connection_row)
        self._ai_connection_status.setObjectName("preferences_ai_connection_status")
        self._ai_connection_status.setWordWrap(True)
        apply_text_role(self._ai_connection_status, TextRole.CAPTION)
        self._ai_connection_layout.addWidget(self._ai_connection_status, 1)
        card.add_widget(connection_row)

        self._ai_actions_row = QWidget(card)
        self._ai_actions_row.setObjectName("preferences_ai_actions_row")
        self._ai_actions_row.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._ai_actions_layout = QHBoxLayout(self._ai_actions_row)
        self._ai_actions_layout.setContentsMargins(0, 6, 0, 0)
        self._ai_actions_layout.setSpacing(8)
        self._ai_save_button = QPushButton("保存配置", card)
        self._ai_check_button = QPushButton("连接测试", card)
        self._ai_delete_button = QPushButton("删除配置", card)
        apply_button_variant(self._ai_save_button, "primary")
        apply_button_variant(self._ai_check_button, "secondary")
        apply_button_variant(self._ai_delete_button, "ghost-danger")
        for button in (
            self._ai_save_button,
            self._ai_check_button,
            self._ai_delete_button,
        ):
            apply_size_class(button, "md")
        self._ai_actions_layout.addWidget(self._ai_save_button)
        self._ai_actions_layout.addWidget(self._ai_check_button)
        self._ai_actions_layout.addStretch(1)
        self._ai_actions_layout.addWidget(self._ai_delete_button)
        card.add_widget(self._ai_actions_row)

        self._ai_status = QLabel("", card)
        self._ai_status.setObjectName("preferences_ai_status")
        self._ai_status.setWordWrap(True)
        apply_text_role(self._ai_status, TextRole.CAPTION)
        card.add_widget(self._ai_status)
        layout.addWidget(card)
        layout.addStretch(1)
        self._reload_ai_profiles()
        return content

    def _select_settings_page(self, card_id: str) -> None:
        ai_selected = card_id == "ai"
        self._content.setVisible(not ai_selected)
        self._ai_content.setVisible(ai_selected)

    def show_preferences_page(self, page_id: str) -> None:
        target = "ai" if str(page_id or "").strip() == "ai" else "about"
        self._nav_rail.select_card(target)
        self._select_settings_page(target)

    def _reload_ai_profiles(self, selected_profile_id: str = "") -> None:
        self._ai_profile_combo.blockSignals(True)
        self._ai_profile_combo.clear()
        try:
            profiles = self._provider_profiles.list_profiles()
        except (OSError, ValueError, TypeError):
            profiles = ()
        for profile in profiles:
            readiness = ProviderRouter(
                profiles=self._provider_profiles,
                secrets=self._provider_secrets,
            ).readiness(profile.profile_id)
            suffix = provider_connection_badge(
                profile,
                ready=readiness.ready,
                show_unready=True,
            )
            label = profile.label if not suffix else f"{profile.label} · {suffix}"
            self._ai_profile_combo.addItem(label, profile.profile_id)
        target = selected_profile_id or "mock-default"
        selected_index = -1
        for index in range(self._ai_profile_combo.count()):
            if str(self._ai_profile_combo.itemData(index) or "") == target:
                selected_index = index
                break
        if selected_index < 0 and self._ai_profile_combo.count():
            selected_index = 0
        self._ai_profile_combo.setCurrentIndex(selected_index)
        self._ai_profile_combo.blockSignals(False)
        if selected_index >= 0:
            self._load_ai_profile_form(selected_index)
        else:
            self._load_ai_profile_form(-1, profile_id="__new__")

    def _load_ai_profile_form(
        self,
        _index: int,
        *,
        profile_id: str | None = None,
    ) -> None:
        profile_id = profile_id or str(self._ai_profile_combo.currentData() or "__new__")
        self._loading_ai_form = True
        try:
            self._ai_profile_combo.set_display_text_override(
                "新配置（尚未保存）" if profile_id == "__new__" else None
            )
            if profile_id == "__new__":
                self._ai_url_input.setPlaceholderText("https://api.example.com/v1")
                self._ai_key_input.setPlaceholderText("填写 API Key")
                self._ai_label_input.setText("")
                self._ai_url_input.setText("https://api.openai.com/v1")
                self._ai_model_input.setText("")
                self._ai_key_input.clear()
                self._ai_key_status.setText(
                    "新配置必须填写 API Key；密钥不会写入普通设置文件。"
                )
                self._set_ai_connection_state(
                    "未保存",
                    "warning",
                    "填写完整信息并保存后，可以执行连接测试。",
                )
                editable = True
                ready = False
                readiness_message = "请保存完整配置后再测试连接"
            else:
                try:
                    profile = self._provider_profiles.get(profile_id)
                except KeyError:
                    return
                self._ai_label_input.setText(profile.label)
                self._ai_url_input.setPlaceholderText("https://api.example.com/v1")
                self._ai_key_input.setPlaceholderText("留空表示不修改已保存密钥")
                self._ai_url_input.setText(
                    profile.base_url if profile.requires_secret else "不使用网络"
                )
                self._ai_model_input.setText(profile.model_id)
                self._ai_key_input.clear()
                readiness = ProviderRouter(
                    profiles=self._provider_profiles,
                    secrets=self._provider_secrets,
                ).readiness(profile_id)
                ready = readiness.ready
                readiness_message = readiness.message
                if profile.requires_secret:
                    self._ai_key_status.setText(
                        "API Key 已可用（环境变量或 Windows 凭据）"
                        if ready
                        else readiness_message
                    )
                else:
                    self._ai_key_input.setPlaceholderText("不需要 API Key")
                    self._ai_key_status.setText(
                        "内置本地演示配置，不使用网络或 API Key。"
                    )
                self._set_ai_connection_state(
                    *self._ai_connection_state_for_profile(
                        profile,
                        ready=ready,
                        readiness_message=readiness_message,
                    ),
                )
                editable = profile.kind != "mock"
            for field in (
                self._ai_label_input,
                self._ai_url_input,
                self._ai_model_input,
                self._ai_key_input,
            ):
                field.setEnabled(editable)
            self._ai_profile_combo.setEnabled(True)
            self._ai_new_button.setEnabled(True)
            self._ai_save_button.setEnabled(editable)
            self._ai_delete_button.setEnabled(editable and profile_id != "__new__")
            self._ai_check_button.setEnabled(profile_id != "__new__" and ready)
            self._ai_check_button.setToolTip(
                "发送固定的 OK 测试，不包含文档内容"
                if ready
                else readiness_message
            )
            self._ai_status.setText("")
        finally:
            self._loading_ai_form = False
        self._ai_form_dirty = False
        self._ai_loaded_profile_id = profile_id

    @staticmethod
    def _ai_connection_state_for_profile(
        profile: ProviderProfile,
        *,
        ready: bool,
        readiness_message: str,
    ) -> tuple[str, str, str]:
        detail = provider_connection_status_text(
            profile,
            ready=ready,
            readiness_message=readiness_message,
        )
        detail = detail.removeprefix("连接状态：")
        if not ready:
            return "未就绪", "error", detail
        if profile.kind == "mock":
            return "本地可用", "info", detail
        if profile.connection_status == "success":
            return "已验证", "success", detail
        if profile.connection_status == "failed":
            return "上次失败", "error", detail
        return "尚未测试", "warning", detail

    def _set_ai_connection_state(
        self,
        text: str,
        variant: str,
        detail: str,
    ) -> None:
        self._ai_state_badge.set_variant(variant)
        self._ai_state_badge.set_text(text)
        self._ai_connection_status.setText(detail)
        self._apply_ai_state_badge_contrast()

    def _apply_ai_state_badge_contrast(self) -> None:
        theme = get_theme()
        variant_backgrounds = {
            "neutral": theme.bg_hover,
            "info": theme.info_bg,
            "success": theme.success_bg,
            "warning": theme.warning_bg,
            "error": theme.error_bg,
            "danger": theme.error_bg,
        }
        background = variant_backgrounds.get(
            self._ai_state_badge.variant(),
            theme.bg_hover,
        )
        self._ai_state_badge._label.setStyleSheet(
            f"""
            background: {background};
            color: {theme.text_primary};
            border: none;
            border-radius: {theme.radius_sm}px;
            padding: 1px 8px;
            font-size: {max(theme.font_size_sm - 1, 11)}px;
            font-weight: {theme.font_weight_medium};
            """
        )

    def _start_new_ai_profile(self) -> None:
        if self._ai_form_dirty:
            if not confirm(
                "放弃未保存修改？",
                "当前模型配置有未保存修改。新建配置会丢失这些修改，是否继续？",
                confirm_text="放弃修改并新建",
                destructive=True,
                parent=self,
            ):
                return
        blocked = self._ai_profile_combo.blockSignals(True)
        try:
            self._ai_profile_combo.setCurrentIndex(-1)
        finally:
            self._ai_profile_combo.blockSignals(blocked)
        self._load_ai_profile_form(-1, profile_id="__new__")
        self._ai_label_input.setFocus()

    def _on_ai_profile_selection_changed(self, index: int) -> None:
        target = str(self._ai_profile_combo.itemData(index) or "__new__")
        if (
            self._ai_form_dirty
            and self._ai_loaded_profile_id
            and target != self._ai_loaded_profile_id
        ):
            if not confirm(
                "放弃未保存修改？",
                "当前模型配置有未保存修改。切换配置会丢失这些修改，是否继续？",
                confirm_text="放弃修改并切换",
                destructive=True,
                parent=self,
            ):
                blocked = self._ai_profile_combo.blockSignals(True)
                try:
                    if self._ai_loaded_profile_id == "__new__":
                        self._ai_profile_combo.setCurrentIndex(-1)
                    else:
                        for candidate in range(self._ai_profile_combo.count()):
                            if (
                                str(self._ai_profile_combo.itemData(candidate) or "")
                                == self._ai_loaded_profile_id
                            ):
                                self._ai_profile_combo.setCurrentIndex(candidate)
                                break
                finally:
                    self._ai_profile_combo.blockSignals(blocked)
                return
        self._load_ai_profile_form(index)

    def _mark_ai_form_dirty(self, *_args) -> None:
        if self._loading_ai_form:
            return
        self._ai_form_dirty = True
        self._ai_check_button.setEnabled(False)
        self._ai_check_button.setToolTip("请先保存修改，再测试实际生效的配置")
        self._set_ai_connection_state(
            "未保存",
            "warning",
            "保存修改后，才能测试 AI 助手实际使用的配置。",
        )
        self._ai_status.setText("有未保存修改；保存后才会同步到 AI 文档助手。")

    def _save_ai_profile(self) -> None:
        selected = str(self._ai_profile_combo.currentData() or "__new__")
        profile_id = selected if selected != "__new__" else f"cloud-{uuid4().hex[:12]}"
        label = self._ai_label_input.text().strip()
        base_url = self._ai_url_input.text().strip()
        model_id = self._ai_model_input.text().strip()
        if not label or not base_url or not model_id:
            self._ai_status.setText("请完整填写显示名称、API 地址和模型 ID。")
            return
        previous_profile = None
        previous_secret = ""
        if selected != "__new__":
            try:
                previous_profile = self._provider_profiles.get(profile_id)
                previous_secret = self._provider_secrets.get(profile_id)
            except (KeyError, OSError, RuntimeError, ValueError) as exc:
                self._ai_status.setText(f"无法读取原配置：{provider_error_text(exc)}")
                return
        secret = self._ai_key_input.text().strip()
        if not secret and not previous_secret:
            self._ai_status.setText("请填写 API Key；缺少密钥的配置不会进入可用模型列表。")
            return
        try:
            connection_unchanged = bool(
                previous_profile is not None
                and not secret
                and previous_profile.base_url == base_url
                and previous_profile.model_id == model_id
            )
            profile = ProviderProfile(
                profile_id=profile_id,
                label=label,
                kind="openai_compatible",
                model_id=model_id,
                base_url=base_url,
                timeout_seconds=(
                    previous_profile.timeout_seconds
                    if previous_profile is not None
                    else 60.0
                ),
                enabled=(
                    previous_profile.enabled
                    if previous_profile is not None
                    else True
                ),
                extra_body=(
                    previous_profile.extra_body
                    if previous_profile is not None
                    else {}
                ),
                connection_status=(
                    previous_profile.connection_status
                    if connection_unchanged and previous_profile is not None
                    else "untested"
                ),
                last_checked_at=(
                    previous_profile.last_checked_at
                    if connection_unchanged and previous_profile is not None
                    else ""
                ),
                last_check_message=(
                    previous_profile.last_check_message
                    if connection_unchanged and previous_profile is not None
                    else ""
                ),
            )
            if secret:
                self._provider_secrets.set(profile_id, secret)
            self._provider_profiles.upsert(profile)
        except (OSError, RuntimeError, ValueError) as exc:
            rollback_ok = self._rollback_ai_profile_save(
                profile_id,
                previous_profile=previous_profile,
                previous_secret=previous_secret,
                secret_changed=bool(secret),
            )
            suffix = "，原配置已恢复" if rollback_ok else "，自动回滚未完全成功"
            self._ai_status.setText(
                f"保存失败：{provider_error_text(exc)}{suffix}。"
            )
            return
        self._ai_key_input.clear()
        self._reload_ai_profiles(profile_id)
        self._ai_status.setText(
            "配置已保存并同步到 AI 文档助手。建议先执行连接测试；正文仍需明确授权后才能发送。"
        )
        self.bridge.assistant_provider_profiles_changed.emit()

    def _rollback_ai_profile_save(
        self,
        profile_id: str,
        *,
        previous_profile: ProviderProfile | None,
        previous_secret: str,
        secret_changed: bool,
    ) -> bool:
        try:
            if previous_profile is None:
                self._provider_profiles.delete(profile_id)
            else:
                self._provider_profiles.upsert(previous_profile)
            if secret_changed:
                if previous_secret:
                    self._provider_secrets.set(profile_id, previous_secret)
                else:
                    self._provider_secrets.delete(profile_id)
        except (OSError, RuntimeError, ValueError):
            return False
        return True

    def _delete_ai_profile(self) -> None:
        profile_id = str(self._ai_profile_combo.currentData() or "")
        if not profile_id or profile_id in {"mock-default", "__new__"}:
            return
        if not confirm(
            "删除模型配置？",
            "删除后，使用该配置的历史会话将无法继续请求，直到重新配置。是否继续？",
            confirm_text="删除配置",
            destructive=True,
            parent=self,
        ):
            return
        try:
            previous_profile = self._provider_profiles.get(profile_id)
            deleted = self._provider_profiles.delete(profile_id)
            try:
                self._provider_secrets.delete(profile_id)
            except (OSError, RuntimeError, ValueError):
                self._provider_profiles.upsert(previous_profile)
                raise
        except (OSError, RuntimeError, ValueError) as exc:
            self._ai_status.setText(
                f"删除失败：{provider_error_text(exc)}；配置已尽量恢复。"
            )
            return
        if deleted:
            self._reload_ai_profiles("mock-default")
            self._ai_status.setText("配置已删除。")
            self.bridge.assistant_provider_profiles_changed.emit()

    def _check_ai_profile(self) -> None:
        if self._ai_form_dirty:
            self._ai_status.setText("请先保存修改，再测试实际会被 AI 助手使用的配置。")
            return
        if self._provider_probe_worker is not None and self._provider_probe_worker.is_running:
            return
        profile_id = str(self._ai_profile_combo.currentData() or "")
        try:
            gateway = ProviderRouter(
                profiles=self._provider_profiles,
                secrets=self._provider_secrets,
            ).resolve(profile_id, timeout_seconds=10.0)
            profile = self._provider_profiles.get(profile_id)
        except (ProviderResolutionError, OSError, RuntimeError, ValueError) as exc:
            self._ai_status.setText(
                f"配置不可用：{provider_error_text(exc)}"
            )
            return
        worker = ProviderProbeWorker(gateway, model_id=profile.model_id, parent=self)
        self._provider_probe_worker = worker
        self._provider_probe_profile_id = profile.profile_id
        self._ai_profile_combo.setEnabled(False)
        self._ai_new_button.setEnabled(False)
        for field in (
            self._ai_label_input,
            self._ai_url_input,
            self._ai_model_input,
            self._ai_key_input,
        ):
            field.setEnabled(False)
        self._ai_save_button.setEnabled(False)
        self._ai_delete_button.setEnabled(False)
        self._ai_check_button.setEnabled(False)
        self._set_ai_connection_state(
            "正在测试",
            "info",
            "仅发送固定的 OK，不包含文档内容。",
        )
        self._ai_status.setText("正在测试模型连接；不会发送文档内容…")
        worker.finished.connect(self._on_provider_probe_finished)
        worker.start()

    def _on_provider_probe_finished(self, result) -> None:
        worker = self._provider_probe_worker
        profile_id = self._provider_probe_profile_id
        success = bool(getattr(result, "success", False))
        raw_message = getattr(result, "message", "provider_connection_failed")
        friendly_message = provider_error_text(raw_message)
        timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
        persistence_error = ""
        try:
            profile = self._provider_profiles.get(profile_id)
            if profile.kind != "mock":
                self._provider_profiles.upsert(
                    replace(
                        profile,
                        connection_status="success" if success else "failed",
                        last_checked_at=timestamp,
                        last_check_message=("" if success else friendly_message),
                    )
                )
                self.bridge.assistant_provider_profiles_changed.emit()
        except (KeyError, OSError, RuntimeError, ValueError) as exc:
            persistence_error = provider_error_text(exc)
        if worker is not None:
            worker.deleteLater()
        self._provider_probe_worker = None
        self._provider_probe_profile_id = ""
        self._reload_ai_profiles(profile_id)
        if success:
            message = "连接测试成功。测试仅发送了固定的 OK，不包含文档内容。"
        else:
            message = f"连接测试失败：{friendly_message}。未发送文档内容。"
        if persistence_error:
            message += f" 但测试状态保存失败：{persistence_error}。"
        self._ai_status.setText(message)

    def shutdown_active_execution(self, timeout_ms: int | None = None) -> bool:
        timeout = 3000 if timeout_ms is None else max(0, int(timeout_ms))
        return bool(
            self._provider_probe_worker is None
            or self._provider_probe_worker.shutdown(timeout)
        )

    def _make_button(
        self,
        text: str,
        *,
        icon_name: str,
        primary: bool = False,
    ) -> QPushButton:
        button = QPushButton(text, self._content)
        button.setCursor(Qt.PointingHandCursor)
        apply_size_class(button, "md")
        apply_button_variant(button, "primary" if primary else "secondary")
        button.setProperty("aboutIcon", icon_name)
        return button

    def _open_log_file(self) -> None:
        log_path = resolve_log_path()
        if not log_path.is_file():
            Toast.show_info("暂时没有日志：软件尚未记录错误")
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path.resolve()))):
            Toast.show_error("无法打开日志文件")

    def _export_problem_report(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        desktop = Path.home() / "Desktop"
        target_dir = desktop if desktop.is_dir() else Path.home()
        suggested = target_dir / f"Alavette-Form_问题报告_{timestamp}.txt"
        selected, _filter = QFileDialog.getSaveFileName(
            self,
            "导出问题报告",
            str(suggested),
            "文本文件 (*.txt)",
        )
        if not selected:
            return
        target = Path(selected)
        if target.suffix.casefold() != ".txt":
            target = target.with_suffix(".txt")
        try:
            target.write_text(
                build_problem_report(log_path=resolve_log_path()),
                encoding="utf-8-sig",
            )
        except OSError:
            Toast.show_error("问题报告保存失败，请换一个位置重试")
            return
        Toast.show_success(f"问题报告已保存：{target.name}")

    def _show_project_license(self) -> None:
        try:
            text = read_project_license()
        except LicenseCatalogError as exc:
            Toast.show_error(str(exc))
            return
        dialog = LicenseDialog.for_project(text, parent=self)
        dialog.exec()

    def _show_third_party_licenses(self) -> None:
        try:
            catalog = self._license_catalog or load_license_catalog()
        except LicenseCatalogError as exc:
            Toast.show_error(str(exc))
            return
        dialog = LicenseDialog.for_third_party(catalog, parent=self)
        dialog.exec()

    def _apply_theme(self) -> None:
        theme = get_theme()
        self._page_title.setStyleSheet(
            f"color: {theme.text_primary}; background: transparent;"
        )
        self._logo.setPixmap(get_app_logo(52).pixmap(52, 52))
        self._app_name.setFont(
            brand_font(
                pixel_size=theme.font_size_xxl,
                weight=theme.font_weight_emphasis,
            )
        )
        self._app_name.setStyleSheet(
            f"color: {theme.text_primary}; background: transparent;"
        )
        self._version_label.setStyleSheet(
            f"color: {theme.text_secondary}; background: transparent;"
        )
        self._local_processing_note.setStyleSheet(
            f"color: {theme.text_secondary}; background: transparent;"
        )
        self._ai_page_title.setStyleSheet(
            f"color: {theme.text_primary}; background: transparent;"
        )
        self._ai_privacy_callout.setStyleSheet(
            f"""
            QFrame#preferences_ai_privacy_callout {{
                background: {theme.info_bg};
                border: 1px solid {theme.border_light};
                border-radius: {theme.radius_md}px;
            }}
            """
        )
        self._ai_privacy_icon.setPixmap(
            get_icon("circle-help", 16, theme.info).pixmap(16, 16)
        )
        self._ai_privacy_title.setStyleSheet(
            f"color: {theme.text_primary}; background: transparent; "
            f"font-weight: {theme.font_weight_emphasis};"
        )
        self._ai_privacy_note.setStyleSheet(
            f"color: {theme.text_secondary}; background: transparent;"
        )
        self._ai_key_status.setStyleSheet(
            f"color: {theme.text_secondary}; background: transparent;"
        )
        self._ai_connection_status.setStyleSheet(
            f"color: {theme.text_secondary}; background: transparent;"
        )
        self._ai_status.setStyleSheet(
            f"color: {theme.text_secondary}; background: transparent;"
        )
        self._apply_ai_state_badge_contrast()
        form_content_indent = theme.form_row_label_width + 4
        self._ai_connection_layout.setContentsMargins(
            form_content_indent,
            6,
            0,
            2,
        )
        self._ai_actions_layout.setContentsMargins(
            form_content_indent,
            6,
            0,
            0,
        )
        input_style = build_text_input_stylesheet(theme) + f"""
            QLineEdit:disabled {{
                color: {theme.text_secondary};
            }}
            QLineEdit::placeholder {{
                color: {theme.text_secondary};
            }}
        """
        for field in (
            self._ai_label_input,
            self._ai_url_input,
            self._ai_model_input,
            self._ai_key_input,
        ):
            field.setStyleSheet(input_style)
        button_style = build_button_stylesheet(theme)
        for button in (
            self._open_log_button,
            self._export_report_button,
        ):
            button.setStyleSheet(button_style)
        ai_button_style = button_style + f"""
            QPushButton:disabled {{
                background: {theme.bg_input};
                color: {theme.text_secondary};
                border: 1px solid {theme.border_light};
            }}
            QPushButton[variant="ghost-danger"]:disabled {{
                background: transparent;
                color: {theme.text_secondary};
                border: 1px solid transparent;
            }}
        """
        for button in (
            self._ai_new_button,
            self._ai_save_button,
            self._ai_check_button,
            self._ai_delete_button,
        ):
            button.setStyleSheet(ai_button_style)
        for button in (
            self._open_log_button,
            self._export_report_button,
            self._ai_new_button,
            self._ai_save_button,
            self._ai_check_button,
            self._ai_delete_button,
        ):
            icon_name = str(button.property("aboutIcon") or "")
            icon_color = (
                theme.text_on_primary
                if button.property("variant") == "primary"
                else theme.icon_primary
            )
            button.setIcon(get_icon(icon_name, 16, icon_color))
            button.setIconSize(QSize(16, 16))
        divider = self.findChild(QFrame, "license_navigation_divider")
        if divider is not None:
            divider.setStyleSheet(
                f"background: {theme.divider}; border: none;"
            )


__all__ = ["PreferencesPanel"]
