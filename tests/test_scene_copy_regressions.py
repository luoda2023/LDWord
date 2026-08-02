from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCENE_COPY_SOURCES = (
    ROOT / "src" / "ui" / "panels" / "scene_scope_sections.py",
    ROOT / "src" / "ui" / "panels" / "scene_input_cleanup_rules.py",
)

REMOVED_EXPLANATORY_COPY = (
    "只处理识别为正文的内容，其他已识别区域保持原样。",
    "只处理实际输入中适用的文本。",
    "Markdown 规则仅对 Markdown 来源生效",
    "对象安全预检和生成后验收由执行链自动完成",
)

REMOVED_EXPLANATORY_WIDGETS = (
    "scn_document_scope_mode_help",
    "scn_input_cleanup_hint",
)


def test_removed_scene_explanatory_copy_stays_out_of_the_ui() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in SCENE_COPY_SOURCES
    )

    for text in (*REMOVED_EXPLANATORY_COPY, *REMOVED_EXPLANATORY_WIDGETS):
        assert text not in source
