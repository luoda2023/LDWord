"""
cli_runner — CLI 模式执行入口

从 main.py 中拆分出来的核心 CLI 执行逻辑。
"""

from __future__ import annotations

import time
from pathlib import Path

from src.config.loader import load_template, load_scene
from src.config.template import TemplateConfig
from src.config.scene import SceneWorkspace
from src.config.resolver import resolve_config
from src.modules.registry import create_all_modules
from src.pipeline.runner import Pipeline
from src.pipeline.scheduler import select_enabled_modules
from src.report_writer import write_json_report, write_markdown_report


def run(
    input_path: Path,
    *,
    template_path: str | None = None,
    scene_path: str | None = None,
    output_dir: Path | None = None,
    project_root: Path | None = None,
) -> int:
    """执行 CLI 模式排版管线，返回退出码。"""
    root = project_root or Path(__file__).resolve().parent.parent

    # ── 输出目录 ──
    if output_dir is None:
        output_dir = input_path.parent / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    # ── 安全检查: 输出路径 ≠ 输入路径 ──
    output_docx = output_dir / f"{input_path.stem}_formatted.docx"
    if output_docx.resolve() == input_path.resolve():
        print("❌ 输出路径与输入路径相同，会覆盖源文件！请指定不同的输出目录。")
        return 1

    # ── 加载配置 ──
    template = _load_template(template_path, root)
    scene = _load_scene(scene_path)
    config = resolve_config(template, scene)

    # ── 创建模块 ──
    modules = create_all_modules()
    enabled, auto_pruned = select_enabled_modules(
        modules,
        config.is_module_enabled,
    )
    skipped = len(modules) - len(enabled)

    print(
        f"🔧 模块: 启用 {len(enabled)} / 总共 {len(modules)}"
        + (f" (跳过 {skipped})" if skipped else "")
    )
    if auto_pruned:
        print("⚠️ 因硬依赖未满足，已自动跳过以下模块：")
        for name in sorted(auto_pruned):
            missing = ", ".join(auto_pruned[name])
            print(f"   - {name} (缺少: {missing})")

    # ── 执行管线 ──
    print(f"📄 处理: {input_path.name}")
    t0 = time.perf_counter()

    pipeline = Pipeline(
        modules=enabled,
        config=config,
        output_dir=str(output_dir),
        output_suffix="_formatted",
    )
    result = pipeline.execute(str(input_path))
    elapsed = time.perf_counter() - t0

    if not result.success:
        print(f"❌ 管线执行失败: {result.error}")
        return 1

    # ── 输出结果 ──
    final_output = Path(result.output_paths.get("final", str(output_docx)))
    if result.output_paths.get("final"):
        print(f"✅ 输出: {final_output}")

    # ── 报告 ──
    report_json = output_dir / f"{input_path.stem}_changes.json"
    write_json_report(
        result,
        input_path=input_path,
        output_path=final_output,
        report_path=report_json,
        elapsed=elapsed,
        modules_enabled=len(enabled),
        modules_total=len(modules),
    )
    print(f"📊 报告: {report_json}")

    report_md = output_dir / f"{input_path.stem}_changes.md"
    write_markdown_report(
        result,
        input_path=input_path,
        report_path=report_md,
        elapsed=elapsed,
        modules_enabled=len(enabled),
        modules_total=len(modules),
    )
    print(f"📝 报告: {report_md}")

    # ── 汇总 ──
    print(f"\n{'='*50}")
    print(f"✅ 完成！耗时 {elapsed:.2f}s, 状态: {result.status}")
    if result.failed_items:
        print(f"⚠️  {len(result.failed_items)} 个非关键失败")
    print(f"{'='*50}")

    return 0


def _load_template(template_path: str | None, root: Path) -> TemplateConfig:
    if template_path:
        print(f"📋 加载模板: {template_path}")
        return load_template(template_path)

    default_tpl = root / "defaults" / "thesis.yaml"
    if default_tpl.exists():
        print(f"📋 使用默认模板: {default_tpl.name}")
        return load_template(default_tpl)

    print("📋 使用内置默认参数")
    return TemplateConfig()


def _load_scene(scene_path: str | None) -> SceneWorkspace:
    if scene_path:
        print(f"🎬 加载场景: {scene_path}")
        return load_scene(scene_path)
    return SceneWorkspace()
