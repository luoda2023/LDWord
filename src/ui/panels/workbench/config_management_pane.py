from __future__ import annotations

from src.qt_api import QLabel, QVBoxLayout, QWidget


class ConfigManagementPane(QWidget):
    def __init__(self, strategy_card: QWidget | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("wb_config_management_pane")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        self._title = QLabel("\u914d\u7f6e\u7ba1\u7406")
        self._title.setObjectName("wb_config_management_title")
        self._description = QLabel(
            "\u5f53\u524d\u5148\u627f\u63a5\u6a21\u677f\u3001\u573a\u666f\u4e0e\u6267\u884c\u7b56\u7565\u6458\u8981\uff0c\u540e\u7eed\u52a8\u6001\u529f\u80fd\u5361\u4f1a\u7ee7\u7eed\u6302\u63a5\u5230\u8fd9\u4e2a\u533a\u57df\u3002"
        )
        self._description.setWordWrap(True)
        self._description.setObjectName("wb_config_management_description")

        layout.addWidget(self._title)
        layout.addWidget(self._description)
        if strategy_card is not None:
            layout.addWidget(strategy_card)
        layout.addStretch(1)
