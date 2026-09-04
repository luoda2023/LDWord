"""Plan-selector host for exam and official modes."""

from __future__ import annotations

from src.config.scene import ExamPaperConfig, SceneWorkspace, coerce_exam_paper_config
from src.qt_api import QSizePolicy, QVBoxLayout, QWidget
from src.shared.ui.theme import bind_theme, get_theme


def ensure_exam_paper_config(scene: SceneWorkspace) -> ExamPaperConfig:
    config = coerce_exam_paper_config(getattr(scene, "exam_paper", None))
    scene.exam_paper = config
    return config


class ExamPaperDetail(QWidget):
    """Host the canonical plan selector without adding a duplicate summary."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._attached_plan_card: QWidget | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(get_theme().template_detail_section_gap)
        layout.addStretch(1)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        bind_theme(self, self.apply_theme)

    def apply_theme(self) -> None:
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.setSpacing(get_theme().template_detail_section_gap)

    def attach_plan_card(self, card: QWidget) -> None:
        if self._attached_plan_card is card:
            return
        self.detach_plan_card()
        layout = self.layout()
        if not isinstance(layout, QVBoxLayout):
            return
        self._attached_plan_card = card
        card.setParent(self)
        layout.insertWidget(0, card)
        card.setVisible(True)

    def detach_plan_card(self) -> QWidget | None:
        card = self._attached_plan_card
        if card is None:
            return None
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.removeWidget(card)
        card.hide()
        card.setParent(None)
        self._attached_plan_card = None
        return card


__all__ = ["ExamPaperDetail", "ensure_exam_paper_config"]
