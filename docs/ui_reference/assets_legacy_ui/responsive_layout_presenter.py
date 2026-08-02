"""Presenter mixin for responsive assets panel layout behavior."""

from __future__ import annotations

from src.qt_api import QEvent, QSize
from src.shared.ui.button_style import build_button_stylesheet
from src.shared.ui.icon_button import apply_icon_button_style
from src.shared.ui.theme import get_theme


class ResponsiveLayoutPresenterMixin:
    """Adjust section layout and action buttons for narrow widths."""

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._apply_responsive_layout()

    def eventFilter(self, watched, event) -> bool:
        role = (
            str(watched.property("asset_role") or "")
            if hasattr(watched, "property")
            else ""
        )
        if (
            role
            and event.type() == QEvent.MouseButtonRelease
            and str(watched.objectName() or "") == "asset_slot_thumbnail"
        ):
            self._show_asset_slot_path(role)
            return True
        group_role = (
            str(watched.property("asset_group_role") or "")
            if hasattr(watched, "property")
            else ""
        )
        if group_role and event.type() == QEvent.MouseButtonRelease:
            self._preview_asset_group_first_item(group_role)
            if getattr(self, "_current_image_preview_path", ""):
                self._open_current_image_preview_dialog()
            return True
        return super().eventFilter(watched, event)

    def _apply_responsive_layout(self) -> None:
        if not hasattr(self, "_section_nav") or not hasattr(self, "_detail_layout"):
            return
        theme = get_theme()
        panel_width = max(0, self.width())
        nav_width = theme.master_detail_nav_width
        margin_x = theme.master_detail_margin_x
        if panel_width and panel_width < 760:
            nav_width = min(nav_width, max(176, int(panel_width * 0.42)))
            margin_x = 16
        elif panel_width and panel_width < 960:
            nav_width = min(nav_width, 230)
            margin_x = 22
        self._section_nav.setFixedWidth(nav_width)
        self._detail_layout.setContentsMargins(
            margin_x,
            theme.master_detail_margin_top,
            margin_x,
            theme.master_detail_margin_bottom,
        )
        self._sync_generate_action_button_mode(compact=bool(panel_width and panel_width < 560))
        self._sync_archive_action_button_mode(compact=bool(panel_width and panel_width < 560))
        compact_asset_headers = bool(panel_width and panel_width < 900)
        for hint in (
            getattr(self, "_single_assets_hint", None),
            getattr(self, "_asset_groups_hint", None),
            getattr(self, "_image_preview_hint", None),
        ):
            if hint is not None:
                hint.setVisible(not compact_asset_headers)

    def _sync_generate_action_button_mode(self, *, compact: bool) -> None:
        if not hasattr(self, "_fill_missing_btn"):
            return
        theme = get_theme()
        actions = (
            (self._fill_missing_btn, "填写资料"),
            (
                self._overview_preview_refresh_btn,
                str(
                    self._overview_preview_refresh_btn.property(
                        "responsive_full_text"
                    )
                    or "重新读取模板"
                ),
            ),
            (
                self._apply_btn,
                str(self._apply_btn.property("responsive_full_text") or "生成文档"),
            ),
        )
        for button, label in actions:
            button.setToolTip(label)
            button.setAccessibleName(label)
            if compact:
                button.setText("")
                variant = str(button.property("variant") or "secondary")
                apply_icon_button_style(
                    button,
                    variant=variant,
                    size=34,
                    icon_size=16,
                )
            else:
                button.setText(label)
                button.setProperty("iconButton", False)
                button.setMinimumSize(0, 0)
                button.setMaximumSize(16777215, 16777215)
                button.setIconSize(QSize(16, 16))
                button.setStyleSheet(build_button_stylesheet(theme))

    def _sync_archive_action_button_mode(self, *, compact: bool) -> None:
        if not hasattr(self, "_new_archive_btn"):
            return
        theme = get_theme()
        actions = (
            (self._new_archive_btn, "新建资料包"),
            (self._duplicate_archive_btn, "创建副本"),
            (self._rename_archive_btn, "重命名资料包"),
            (self._open_archive_folder_btn, "打开资料包文件夹"),
            (self._delete_archive_btn, "删除资料包"),
        )
        for button, label in actions:
            button.setToolTip(label)
            button.setAccessibleName(label)
            if compact:
                button.setText("")
                variant = str(button.property("variant") or "secondary")
                apply_icon_button_style(
                    button,
                    variant=variant,
                    size=34,
                    icon_size=16,
                )
            else:
                button.setText(label)
                button.setProperty("iconButton", False)
                button.setMinimumSize(0, 0)
                button.setMaximumSize(16777215, 16777215)
                button.setIconSize(QSize(16, 16))
                button.setStyleSheet(build_button_stylesheet(theme))


__all__ = ["ResponsiveLayoutPresenterMixin"]
