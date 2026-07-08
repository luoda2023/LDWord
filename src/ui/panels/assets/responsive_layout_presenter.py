"""Presenter mixin for responsive assets panel layout behavior."""

from __future__ import annotations

from src.qt_api import QEvent, QSize
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
        if role and event.type() in {QEvent.DragEnter, QEvent.Drop}:
            return self._handle_asset_drag_event(role, event)
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

    def _sync_generate_action_button_mode(self, *, compact: bool) -> None:
        if not hasattr(self, "_fill_missing_btn"):
            return
        actions = (
            (self._fill_missing_btn, "补齐资料"),
            (self._apply_btn, "生成文档"),
            (self._batch_generate_btn, "批量生成"),
        )
        for button, label in actions:
            button.setToolTip(label)
            button.setAccessibleName(label)
            if compact:
                button.setText("")
                button.setFixedSize(34, 34)
                button.setIconSize(QSize(16, 16))
            else:
                button.setText(label)
                button.setMinimumSize(0, 0)
                button.setMaximumSize(16777215, 16777215)

    def _sync_archive_action_button_mode(self, *, compact: bool) -> None:
        if not hasattr(self, "_new_archive_btn"):
            return
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
                button.setFixedSize(34, 34)
                button.setIconSize(QSize(16, 16))
            else:
                button.setText(label)
                button.setMinimumSize(0, 0)
                button.setMaximumSize(16777215, 16777215)


__all__ = ["ResponsiveLayoutPresenterMixin"]
