"""Scheduler helpers for module ordering, contracts and dirty propagation."""

from __future__ import annotations

from collections import defaultdict, deque
from src.config.resolved import ResolvedConfig
from src.pipeline.context import PipelineContext


def topological_sort(modules: list) -> list:
    """Sort modules by depends_on / soft_after."""
    name_to_mod = {m.meta.name: m for m in modules}
    present_names = set(name_to_mod.keys())

    graph: dict[str, list[str]] = defaultdict(list)
    in_degree: dict[str, int] = {m.meta.name: 0 for m in modules}

    for mod in modules:
        for dep in mod.meta.depends_on:
            if dep not in present_names:
                raise ValueError(
                    f"Module '{mod.meta.name}' has missing dependency '{dep}' in the selected module set."
                )
            graph[dep].append(mod.meta.name)
            in_degree[mod.meta.name] += 1

        for dep in mod.meta.soft_after:
            if dep in present_names:
                graph[dep].append(mod.meta.name)
                in_degree[mod.meta.name] += 1

    queue: deque[str] = deque(name for name, deg in in_degree.items() if deg == 0)
    sorted_names: list[str] = []

    while queue:
        queue = deque(sorted(queue))
        name = queue.popleft()
        sorted_names.append(name)
        for neighbor in graph[name]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_names) != len(modules):
        remaining = present_names - set(sorted_names)
        raise ValueError(
            f"Cycle detected in module dependency graph: {', '.join(sorted(remaining))}"
        )

    return [name_to_mod[n] for n in sorted_names]


def validate_schema_contract(
    modules: list,
    *,
    config_cls=ResolvedConfig,
    context_cls=PipelineContext,
) -> list[str]:
    """Validate ModuleMeta keys against declared config/context schema."""
    errors: list[str] = []
    config_fields = set(getattr(config_cls, '__dataclass_fields__', {}).keys())
    context_fields = set(getattr(context_cls, '__dataclass_fields__', {}).keys())

    for mod in modules:
        for key in mod.meta.requires_config:
            if key not in config_fields:
                errors.append(
                    f"Module '{mod.meta.name}' requires_config key '{key}' is not declared on the resolved config schema."
                )
        for key in mod.meta.consumes:
            if key not in context_fields:
                errors.append(
                    f"Module '{mod.meta.name}' consumes context key '{key}' that is not declared on PipelineContext."
                )
        for key in mod.meta.soft_consumes:
            if key not in context_fields:
                errors.append(
                    f"Module '{mod.meta.name}' soft-consumes context key '{key}' that is not declared on PipelineContext."
                )
        for key in mod.meta.provides:
            if key not in context_fields:
                errors.append(
                    f"Module '{mod.meta.name}' provides context key '{key}' that is not declared on PipelineContext."
                )

    return errors


def validate_data_flow(modules: list) -> list[str]:
    """Validate consumes/provides data-flow integrity."""
    errors: list[str] = []
    available: set[str] = {
        "source_doc_path",
        "source_doc_dir",
        "document_scope",
        "document_structure_evidence",
        "document_scope_decisions",
    }

    for mod in modules:
        for key in mod.meta.consumes:
            if key not in available:
                errors.append(
                    f"Module '{mod.meta.name}' consumes key '{key}' before any earlier module provides it."
                )
        available.update(mod.meta.provides)

    return errors


def compute_dirty_modules(
    changed_config_sections: set[str],
    modules: list,
    *,
    seed_dirty_modules: set[str] | None = None,
) -> set[str]:
    """Compute dirty modules from config changes and optional dirty-module seeds."""
    if not changed_config_sections and not seed_dirty_modules:
        return set()

    name_to_mod = {m.meta.name: m for m in modules}

    dirty: set[str] = {
        name for name in (seed_dirty_modules or set())
        if name in name_to_mod
    }
    for mod in modules:
        if any(section in changed_config_sections for section in mod.meta.requires_config):
            dirty.add(mod.meta.name)

    changed = True
    while changed:
        changed = False
        dirty_provides: set[str] = set()
        for name in dirty:
            dirty_provides.update(name_to_mod[name].meta.provides)

        for mod in modules:
            if mod.meta.name in dirty:
                continue
            consumed = tuple(mod.meta.consumes) + tuple(mod.meta.soft_consumes)
            if any(key in dirty_provides for key in consumed):
                dirty.add(mod.meta.name)
                changed = True

    return dirty
