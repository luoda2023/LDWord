import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.modules.base import BaseModule, ModuleMeta
from src.modules.registry import create_all_modules
from src.pipeline.scheduler import compute_dirty_modules, topological_sort, validate_data_flow


class StubHeadingRecognition(BaseModule):
    meta = ModuleMeta(
        name="heading_recognition",
        description="Heading recognition",
        category="structure",
        provides=("doc_tree", "heading_map"),
        execution_phase="semantics",
    )

    def apply(self, doc, config, tracker, context):
        return None


class StubSoftConsumer(BaseModule):
    meta = ModuleMeta(
        name="soft_consumer",
        description="Optional doc tree consumer",
        category="basic",
        soft_after=("heading_recognition",),
        soft_consumes=("doc_tree",),
        scope_behavior="document_level",
        execution_phase="semantics",
    )

    def apply(self, doc, config, tracker, context):
        return None


def test_validate_data_flow_ignores_soft_consumes_without_provider():
    ordered = topological_sort([StubSoftConsumer()])
    assert not validate_data_flow(ordered)


def test_compute_dirty_modules_propagates_soft_consumes_from_seed_dirty_modules():
    modules = topological_sort([StubHeadingRecognition(), StubSoftConsumer()])

    dirty = compute_dirty_modules(set(), modules, seed_dirty_modules={"heading_recognition"})

    assert dirty == {"heading_recognition", "soft_consumer"}


def test_registry_modules_mark_optional_context_consumers_dirty_when_heading_recognition_changes():
    modules = topological_sort(create_all_modules())

    dirty = compute_dirty_modules(set(), modules, seed_dirty_modules={"heading_recognition"})

    assert "paragraph_style" in dirty
    assert "caption" in dirty
    assert "header_footer" in dirty
    assert "reference_format" in dirty
    assert "table_format" in dirty


def test_registry_orders_section_format_before_header_footer():
    modules = topological_sort(create_all_modules())
    ordered_names = [mod.meta.name for mod in modules]

    assert ordered_names.index("section_format") < ordered_names.index("header_footer")
