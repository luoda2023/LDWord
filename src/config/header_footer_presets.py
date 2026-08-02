"""Header/footer preset catalog.

Built-in presets are read-only. User presets are stored as JSON files under
``header_footer_presets/`` and contain only ``HeaderFooterConfig`` data.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import TypedDict

from src.config.dataclass_utils import dict_to_dataclass
from src.config.feature_configs import (
    HeaderFooterConfig,
    PageNumberPhaseConfig,
    default_continuous_page_number_phases,
)
from src.config.migration import (
    normalize_header_footer_payload,
    normalize_page_scope_selectors,
)


class HeaderFooterPresetEntry(TypedDict):
    label: str
    header_footer: HeaderFooterConfig
    source: str
    description: str


PROJECT_ROOT = Path(__file__).resolve().parents[2]
USER_PRESET_DIR = PROJECT_ROOT / "header_footer_presets"
BUILTIN_SOURCE = "builtin"
USER_SOURCE = "user"


def split_page_number_phases(*, continue_body: bool) -> list[PageNumberPhaseConfig]:
    return [
        PageNumberPhaseConfig(
            phase_id="pre_numbering",
            selectors=["cover"],
            visible=False,
            number_format="decimal",
            start_mode="restart",
            start_value=1,
        ),
        PageNumberPhaseConfig(
            phase_id="front",
            selectors=["abstract_cn", "abstract_en", "toc"],
            visible=True,
            number_format="upperRoman",
            start_mode="restart",
            start_value=1,
        ),
        PageNumberPhaseConfig(
            phase_id="body",
            selectors=[
                "body",
                "references",
                "errata",
                "appendix",
                "acknowledgment",
                "resume",
            ],
            visible=True,
            number_format="decimal",
            start_mode="continue" if continue_body else "restart",
            start_value=1,
        ),
    ]


def toc_roman_body_decimal_phases() -> list[PageNumberPhaseConfig]:
    """Hide abstract numbers; restart the TOC at Roman I and body at decimal 1."""

    return [
        PageNumberPhaseConfig(
            phase_id="pre_numbering",
            selectors=["cover"],
            visible=False,
            number_format="decimal",
            start_mode="restart",
            start_value=1,
        ),
        PageNumberPhaseConfig(
            phase_id="front_hidden",
            selectors=["abstract_cn", "abstract_en"],
            visible=False,
            number_format="upperRoman",
            start_mode="restart",
            start_value=1,
        ),
        PageNumberPhaseConfig(
            phase_id="toc",
            selectors=["toc"],
            visible=True,
            number_format="upperRoman",
            start_mode="restart",
            start_value=1,
        ),
        PageNumberPhaseConfig(
            phase_id="body",
            selectors=[
                "body",
                "references",
                "errata",
                "appendix",
                "acknowledgment",
                "resume",
            ],
            visible=True,
            number_format="decimal",
            start_mode="restart",
            start_value=1,
        ),
    ]


def _thesis_preset() -> HeaderFooterConfig:
    cfg = HeaderFooterConfig()
    cfg.footer.content_mode = "none"
    cfg.header.hidden_selectors = ["cover"]
    cfg.footer.hidden_selectors = ["cover"]
    cfg.page_number_plan.phases = split_page_number_phases(continue_body=False)
    return cfg


def _continuous_preset() -> HeaderFooterConfig:
    cfg = HeaderFooterConfig()
    cfg.footer.content_mode = "none"
    cfg.header.hidden_selectors = []
    cfg.footer.hidden_selectors = []
    cfg.page_number_plan.phases = default_continuous_page_number_phases()
    return cfg


def _no_page_number_preset() -> HeaderFooterConfig:
    cfg = HeaderFooterConfig()
    cfg.footer.content_mode = "none"
    cfg.page_number_plan.enabled = False
    cfg.header.hidden_selectors = []
    cfg.footer.hidden_selectors = []
    cfg.page_number_plan.phases = default_continuous_page_number_phases()
    return cfg


BUILTIN_PRESET_CATALOG: dict[str, HeaderFooterPresetEntry] = {
    "thesis": {
        "label": "论文默认",
        "header_footer": _thesis_preset(),
        "source": BUILTIN_SOURCE,
        "description": "封面隐藏三类输出；前置罗马，正文阿拉伯。",
    },
    "continuous": {
        "label": "可编号内容连续页码",
        "header_footer": _continuous_preset(),
        "source": BUILTIN_SOURCE,
        "description": "所有可编号内容使用阿拉伯数字从 1 连续。",
    },
    "no_page_number": {
        "label": "不显示页码",
        "header_footer": _no_page_number_preset(),
        "source": BUILTIN_SOURCE,
        "description": "仅关闭页码，页眉和页脚文字保持独立配置。",
    },
}


def _safe_preset_id(label: str) -> str:
    raw = str(label or "").strip().lower()
    safe = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "_", raw).strip("_")
    return safe or "header_footer_preset"


def _normalize_label(label: str) -> str:
    return re.sub(r"\s+", " ", str(label or "").strip())


def preset_label_exists(label: str, *, exclude_preset_id: str | None = None) -> bool:
    normalized = _normalize_label(label)
    if not normalized:
        return False
    for preset_id, entry in get_preset_catalog().items():
        if exclude_preset_id and preset_id == exclude_preset_id:
            continue
        if _normalize_label(str(entry.get("label") or "")) == normalized:
            return True
    return False


def _user_preset_path(preset_id: str) -> Path:
    bare = str(preset_id or "").strip()
    if bare.startswith("user."):
        bare = bare[5:]
    return USER_PRESET_DIR / f"user.{_safe_preset_id(bare)}.json"


def _load_user_presets() -> dict[str, HeaderFooterPresetEntry]:
    if not USER_PRESET_DIR.exists():
        return {}

    presets: dict[str, HeaderFooterPresetEntry] = {}
    used_labels = {
        _normalize_label(str(entry.get("label") or ""))
        for entry in BUILTIN_PRESET_CATALOG.values()
    }
    for path in sorted(USER_PRESET_DIR.glob("user.*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        preset_id = str(payload.get("preset_id") or path.stem).strip()
        if not preset_id.startswith("user."):
            preset_id = f"user.{_safe_preset_id(preset_id)}"

        label = str(payload.get("name") or payload.get("label") or path.stem).strip() or path.stem
        normalized_label = _normalize_label(label)
        if not normalized_label or normalized_label in used_labels:
            continue

        config_payload = payload.get("header_footer")
        if not isinstance(config_payload, dict):
            continue
        config_payload = deepcopy(config_payload)
        page_number_plan = config_payload.get("page_number_plan")
        has_current_variant_schema = (
            isinstance(page_number_plan, dict)
            and isinstance(page_number_plan.get("first"), dict)
            and isinstance(page_number_plan.get("even"), dict)
        )
        if has_current_variant_schema:
            for channel_name in ("header", "footer"):
                channel = config_payload.get(channel_name)
                if isinstance(channel, dict):
                    channel["hidden_selectors"] = normalize_page_scope_selectors(
                        channel.get("hidden_selectors")
                    )
            phases = page_number_plan.get("phases")
            if isinstance(phases, list):
                for phase in phases:
                    if isinstance(phase, dict):
                        phase["selectors"] = normalize_page_scope_selectors(
                            phase.get("selectors")
                        )
        else:
            config_payload = normalize_header_footer_payload(config_payload)

        used_labels.add(normalized_label)
        presets[preset_id] = {
            "label": label,
            "header_footer": dict_to_dataclass(HeaderFooterConfig, config_payload),
            "source": USER_SOURCE,
            "description": str(payload.get("description") or ""),
        }
    return presets


def get_preset_catalog(*, include_user: bool = True) -> dict[str, HeaderFooterPresetEntry]:
    catalog = {key: deepcopy(value) for key, value in BUILTIN_PRESET_CATALOG.items()}
    if include_user:
        catalog.update(_load_user_presets())
    return catalog


def get_preset_config(preset_id: str) -> HeaderFooterConfig | None:
    entry = get_preset_catalog().get(str(preset_id or ""))
    if entry is None:
        return None
    return deepcopy(entry["header_footer"])


def get_preset_source(preset_id: str) -> str:
    entry = get_preset_catalog().get(str(preset_id or ""))
    if entry is None:
        return ""
    return str(entry.get("source") or "")


def is_user_preset(preset_id: str) -> bool:
    return get_preset_source(preset_id) == USER_SOURCE


def configs_equal(left: HeaderFooterConfig | None, right: HeaderFooterConfig | None) -> bool:
    if left is None or right is None:
        return False
    return asdict(left) == asdict(right)


def detect_matching_preset(config: HeaderFooterConfig | None) -> str | None:
    if config is None:
        return None
    for preset_id, entry in get_preset_catalog().items():
        if configs_equal(config, entry["header_footer"]):
            return preset_id
    return None


def save_user_preset(
    label: str,
    config: HeaderFooterConfig,
    *,
    preset_id: str | None = None,
    description: str = "",
) -> str:
    USER_PRESET_DIR.mkdir(parents=True, exist_ok=True)
    normalized_label = _normalize_label(label)
    if preset_id and is_user_preset(preset_id):
        target_id = preset_id
    else:
        if preset_label_exists(normalized_label):
            raise ValueError("页眉页脚方案名称已存在")
        target_id = f"user.{_safe_preset_id(normalized_label)}"
        existing = get_preset_catalog()
        suffix = 2
        base_id = target_id
        while target_id in existing:
            target_id = f"{base_id}_{suffix}"
            suffix += 1

    payload = {
        "preset_id": target_id,
        "name": normalized_label or target_id.replace("user.", ""),
        "source": USER_SOURCE,
        "description": str(description or ""),
        "header_footer": asdict(config),
    }
    _user_preset_path(target_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target_id


def delete_user_preset(preset_id: str) -> bool:
    if not is_user_preset(preset_id):
        return False
    path = _user_preset_path(preset_id)
    if not path.exists():
        return False
    path.unlink()
    return True


__all__ = [
    "BUILTIN_PRESET_CATALOG",
    "USER_PRESET_DIR",
    "HeaderFooterPresetEntry",
    "configs_equal",
    "delete_user_preset",
    "detect_matching_preset",
    "get_preset_catalog",
    "get_preset_config",
    "get_preset_source",
    "is_user_preset",
    "preset_label_exists",
    "save_user_preset",
    "split_page_number_phases",
]
