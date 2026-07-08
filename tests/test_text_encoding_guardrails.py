from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

MOJIBAKE_MARKERS = (
    "璧勬",
    "瀵煎",
    "鐢熸",
    "鏂板",
    "鍒犻",
    "鎵撳",
    "缂╃",
    "棰勮",
    "妯℃澘",
    "閫夋",
    "鍥剧",
    "锛",
    "銆",
    "€",
)


def _python_sources(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def test_python_sources_do_not_contain_common_mojibake_markers() -> None:
    offenders: list[str] = []
    for path in [*_python_sources(PROJECT_ROOT / "src"), *_python_sources(PROJECT_ROOT / "tests")]:
        if path == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8")
        for marker in MOJIBAKE_MARKERS:
            if marker in text:
                offenders.append(f"{path.relative_to(PROJECT_ROOT)} contains {marker!r}")
    assert offenders == []


def test_runtime_sources_do_not_contain_replacement_question_runs() -> None:
    offenders: list[str] = []
    for path in _python_sources(PROJECT_ROOT / "src"):
        text = path.read_text(encoding="utf-8")
        if "???" in text:
            offenders.append(str(path.relative_to(PROJECT_ROOT)))
    assert offenders == []
