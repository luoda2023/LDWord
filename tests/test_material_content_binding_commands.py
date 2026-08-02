from __future__ import annotations

from content_artifact_test_utils import dummy_content_binding
from src.services.material_content.bindings import (
    clear_content_binding,
    rename_content_binding,
    replace_content_binding,
)


def test_content_binding_commands_replace_rename_and_clear_whole_identity() -> None:
    route = dummy_content_binding(
        content_id="technical_route",
        label="Technical route",
    )
    replacement = dummy_content_binding(
        content_id="technical_route",
        label="Updated route",
    )

    bindings = replace_content_binding({}, route)
    bindings = replace_content_binding(bindings, replacement)
    assert bindings["technical_route"].label == "Updated route"

    bindings = rename_content_binding(
        bindings,
        content_id="technical_route",
        new_content_id="project_route",
    )
    assert set(bindings) == {"project_route"}
    assert bindings["project_route"].content_id == "project_route"

    assert clear_content_binding(bindings, "project_route") == {}
