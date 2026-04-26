from __future__ import annotations

from src.qt_api import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget, Qt

from src.shared.ui.dynamic_navigation_rail import DynamicNavigationRail
from src.shared.ui.theme import AppTheme, bind_theme, get_theme


def apply_master_detail_shell_theme(
    panel: QWidget,
    nav_rail: DynamicNavigationRail,
    detail_scroll: QScrollArea,
    detail_container: QWidget,
    *,
    theme: AppTheme,
    panel_name: str,
    nav_background: str | None = None,
) -> None:
    radius = theme.shell_radius
    nav_color = nav_background or theme.bg_nav_rail
    panel.setStyleSheet(
        f"#{panel_name} {{ background: {theme.bg_window}; border-bottom-right-radius: {radius}px; }}"
    )
    nav_rail.setStyleSheet(
        f"#{nav_rail.objectName()} {{ background: {nav_color}; }}"
    )
    detail_scroll.setStyleSheet(
        f"#{detail_scroll.objectName()} {{ border: none; background: {theme.bg_window}; "
        f"border-bottom-right-radius: {radius}px; }}"
    )
    detail_container.setStyleSheet(
        f"#{detail_container.objectName()} {{ background: {theme.bg_window}; "
        f"border-bottom-right-radius: {radius}px; }}"
    )
    viewport = detail_scroll.viewport()
    if viewport:
        viewport.setObjectName(f"{detail_scroll.objectName()}_viewport")
        viewport.setStyleSheet(
            f"#{viewport.objectName()} {{ background: {theme.bg_window}; "
            f"border-bottom-right-radius: {radius}px; }}"
        )


class MasterDetailShell:
    """Shared master-detail shell: nav rail on the left, scrollable detail on the right."""

    def __init__(
        self,
        host: QWidget,
        *,
        panel_name: str,
        nav_object_name: str,
        detail_object_name: str,
        detail_content_object_name: str,
        nav_background_role: str = "nav",
    ):
        self.host = host
        self.panel_name = panel_name
        self.nav_background_role = nav_background_role

        self.layout = QHBoxLayout(host)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.nav_rail = DynamicNavigationRail(parent=host)
        self.nav_rail.setObjectName(nav_object_name)
        self.layout.addWidget(self.nav_rail)

        self.detail_scroll = QScrollArea(host)
        self.detail_scroll.setObjectName(detail_object_name)
        self.detail_scroll.setWidgetResizable(True)
        self.detail_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.detail_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.detail_scroll.setFrameShape(QFrame.NoFrame)

        self.detail_container = QWidget(self.detail_scroll)
        self.detail_container.setObjectName(detail_content_object_name)
        self.detail_layout = QVBoxLayout(self.detail_container)
        self.detail_scroll.setWidget(self.detail_container)
        self.layout.addWidget(self.detail_scroll, 1)

        self.apply_theme(get_theme())
        bind_theme(host, lambda: self.apply_theme(get_theme()))

    def apply_theme(self, theme: AppTheme) -> None:
        self.nav_rail.setFixedWidth(theme.master_detail_nav_width)
        self.detail_layout.setContentsMargins(
            theme.master_detail_margin_x,
            theme.master_detail_margin_top,
            theme.master_detail_margin_x,
            theme.master_detail_margin_bottom,
        )
        self.detail_layout.setSpacing(theme.master_detail_detail_spacing)

        nav_background = theme.bg_nav_rail
        if self.nav_background_role == "sidebar" and (not nav_background or nav_background == theme.bg_card):
            nav_background = theme.bg_sidebar
        apply_master_detail_shell_theme(
            self.host,
            self.nav_rail,
            self.detail_scroll,
            self.detail_container,
            theme=theme,
            panel_name=self.panel_name,
            nav_background=nav_background,
        )


__all__ = ["MasterDetailShell", "apply_master_detail_shell_theme"]
