"""
heading_numbering_adapter — 标题编号 UI 数据适配层

UI 层通过此 adapter 读写 heading_numbering 配置，
不直接触碰 config 对象。
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from typing import TYPE_CHECKING

from src.qt_api import QObject, Signal
from src.ui.heading_numbering_logic import default_chain_value

if TYPE_CHECKING:
    from src.config.template import (
        HeadingLevelBindingConfig,
        HeadingModelConfig,
        TemplateConfig,
    )


class HeadingNumberingAdapter(QObject):
    """标题编号配置的 UI 适配器。

    职责:
    - 读取当前 level_bindings / heading_model
    - 写入单个字段并发出变更信号
    - 生成编号预览文本
    - 应用预设 (批量写入所有级别)
    """

    # 任何编号配置变更后触发, 参数: ()
    numbering_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._template: TemplateConfig | None = None

    # ── 生命周期 ──────────────────────────────────

    def set_template(self, template: TemplateConfig) -> None:
        """绑定当前模板。由面板的 on_template_changed 调用。"""
        self._template = template
        self.numbering_changed.emit()

    @property
    def template(self) -> TemplateConfig:
        if self._template is None:
            raise RuntimeError("Adapter 未绑定 template")
        return self._template

    @property
    def has_template(self) -> bool:
        return self._template is not None

    # ── 预设检测 ─────────────────────────────────

    def detect_active_preset(self) -> str | None:
        """比对当前 bindings 和所有预设, 完全匹配则返回 key, 否则 None。"""
        from src.config.heading_presets import PRESET_CATALOG

        bindings = self.template.heading_numbering.level_bindings
        for preset_key, entry in PRESET_CATALOG.items():
            if self._bindings_match(bindings, entry["bindings"]):
                return preset_key
        return None

    def _bindings_match(
        self,
        current: dict,
        preset: dict,
    ) -> bool:
        from src.config.template import HeadingLevelBindingConfig as BindingConfig

        for level in range(1, self.max_levels + 1):
            key = f"heading{level}"
            c_bind = current.get(key) or BindingConfig()
            p_bind = preset.get(key) or BindingConfig()
            if asdict(c_bind) != asdict(p_bind):
                return False
        return True

    # ── 读取 ─────────────────────────────────────


    @property
    def max_levels(self) -> int:
        return self.template.heading_model.max_heading_levels

    def get_binding(self, level: int) -> HeadingLevelBindingConfig:
        """获取某一级的 binding 配置 (只读副本)。"""
        key = f"heading{level}"
        bindings = self.template.heading_numbering.level_bindings
        if key in bindings:
            return deepcopy(bindings[key])
        from src.config.template import HeadingLevelBindingConfig as Cls
        return Cls()

    def get_non_numbered_texts(self) -> list[str]:
        return list(self.template.heading_model.non_numbered_title_texts or [])

    def get_non_numbered_prefixes(self) -> list[str]:
        return list(self.template.heading_model.non_numbered_prefixes or [])

    # ── 写入 ─────────────────────────────────────

    def set_max_levels(self, value: int) -> None:
        value = max(1, min(value, 8))
        self.template.heading_model.max_heading_levels = value
        self._ensure_bindings_exist(value)
        self.numbering_changed.emit()

    def _ensure_bindings_exist(self, max_levels: int) -> None:
        """确保 1~max_levels 的 binding 都存在, 缺失的自动补默认。"""
        from src.config.template import HeadingLevelBindingConfig as Cls

        bindings = self.template.heading_numbering.level_bindings
        for lv in range(1, max_levels + 1):
            key = f"heading{lv}"
            if key not in bindings:
                # 默认: arabic 样式, 承接上级 chain
                bindings[key] = Cls(
                    enabled=True,
                    display_core_style="arabic",
                    reference_core_style="arabic",
                    chain=default_chain_value(lv),
                    chain_separator=".",
                )

    def set_binding_field(self, level: int, field_name: str, value) -> None:
        """修改某一级 binding 的某个字段。"""
        key = f"heading{level}"
        bindings = self.template.heading_numbering.level_bindings
        if key not in bindings:
            from src.config.template import HeadingLevelBindingConfig as Cls
            bindings[key] = Cls()
        binding = bindings[key]
        if hasattr(binding, field_name):
            setattr(binding, field_name, value)
            self.numbering_changed.emit()

    def set_non_numbered_texts(self, texts: list[str]) -> None:
        self.template.heading_model.non_numbered_title_texts = list(texts)
        self.numbering_changed.emit()

    def set_non_numbered_prefixes(self, prefixes: list[str]) -> None:
        self.template.heading_model.non_numbered_prefixes = list(prefixes)
        self.numbering_changed.emit()

    # ── 预览 ─────────────────────────────────────

    def preview_number(self, level: int, counter_value: int = 1) -> str:
        """生成某一级的编号预览文本。

        例: level=1, counter=1 → "第一章　"
            level=2, counter=1 → "1.1　"
        """
        from src.modules.structure.heading_numbering import _format_level_number

        binding = self.get_binding(level)
        if not binding.enabled:
            return ""

        # 构建模拟 counters: 所有上级 counter = 1, 当前级 = counter_value
        counters = [0] * 10
        for lv in range(1, level):
            counters[lv] = 1
        counters[level] = counter_value

        level_bindings = self.template.heading_numbering.level_bindings
        return _format_level_number(level, counters, binding, level_bindings)

    def preview_all(self) -> list[tuple[int, str]]:
        """预览所有级别的编号。返回 [(level, preview_text), ...]。"""
        result = []
        for level in range(1, self.max_levels + 1):
            text = self.preview_number(level)
            result.append((level, text))
        return result

    # ── 预设 ─────────────────────────────────────

    def apply_preset(self, preset_key: str) -> None:
        """应用预设, 批量覆盖所有级别的 binding。

        先清除所有已有 heading 级别, 再写入预设, 防止旧配置残留。
        """
        from src.config.heading_presets import get_preset_bindings

        preset_bindings = get_preset_bindings(preset_key)
        if preset_bindings is None:
            return

        bindings = self.template.heading_numbering.level_bindings
        # 清除所有 headingN 旧条目
        for key in [k for k in bindings if k.startswith("heading")]:
            del bindings[key]
        # 写入预设
        for key, binding in preset_bindings.items():
            bindings[key] = deepcopy(binding)

        self.numbering_changed.emit()
