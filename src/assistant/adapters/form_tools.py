"""Register narrow Form capabilities in the neutral assistant tool registry."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from docx import Document

from src.application.exam_user_plan_creation import (
    PlanActivator,
    create_exam_user_plan_from_docx,
)
from src.assistant.adapters.production_adapter import (
    AssistantProductionAdapter,
    file_sha256,
)
from src.assistant.adapters.workspace_state_adapter import WorkspaceSnapshot
from src.assistant.contracts.permissions import ToolRiskLevel
from src.assistant.domain.docx_format_evidence import (
    extract_docx_format_evidence,
)
from src.assistant.tools.registry import ToolDefinition, ToolRegistry
from src.config.library import list_scene_descriptors, list_template_entries
from src.config.scene_natural_request_router import (
    natural_request_route_payload,
    route_natural_scene_request,
)
from src.config.work_mode import list_work_modes

SnapshotProvider = Callable[[], WorkspaceSnapshot]


def build_form_tool_registry(
    snapshot: WorkspaceSnapshot | SnapshotProvider,
    *,
    production: AssistantProductionAdapter | None = None,
    plan_activator: PlanActivator | None = None,
) -> ToolRegistry:
    snapshot_provider = snapshot if callable(snapshot) else (lambda: snapshot)
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            "get_current_workspace_state",
            "读取当前工作模式、方案、模板和非敏感资料摘要",
            ToolRiskLevel.LOCAL_METADATA_READ,
            lambda _args: snapshot_provider().to_dict(include_local_path=False),
            {"type": "object", "properties": {}, "additionalProperties": False},
        )
    )
    registry.register(
        ToolDefinition(
            "list_work_modes",
            "列出可用文档工作模式",
            ToolRiskLevel.LOCAL_METADATA_READ,
            _list_work_modes,
            {"type": "object", "properties": {}, "additionalProperties": False},
        )
    )
    registry.register(
        ToolDefinition(
            "match_scene_request",
            "使用 Form 的确定性路由器匹配自然语言文档需求",
            ToolRiskLevel.LOCAL_METADATA_READ,
            _match_scene_request,
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
        )
    )
    registry.register(
        ToolDefinition(
            "list_scene_candidates",
            "列出一个工作模式中的可用方案",
            ToolRiskLevel.LOCAL_METADATA_READ,
            lambda args: _list_scenes(args, snapshot_provider),
            _mode_schema(),
        )
    )
    registry.register(
        ToolDefinition(
            "list_template_candidates",
            "列出一个工作模式中的可用模板",
            ToolRiskLevel.LOCAL_METADATA_READ,
            lambda args: _list_templates(args, snapshot_provider),
            _mode_schema(),
        )
    )
    registry.register(
        ToolDefinition(
            "list_material_candidates",
            "读取当前资料包的非敏感可用性摘要",
            ToolRiskLevel.LOCAL_METADATA_READ,
            lambda _args: {"current": snapshot_provider().material_summary},
            {"type": "object", "properties": {}, "additionalProperties": False},
        )
    )
    registry.register(
        ToolDefinition(
            "list_output_presets",
            "列出安全的文档输出策略",
            ToolRiskLevel.LOCAL_METADATA_READ,
            lambda _args: {
                "presets": [
                    {"id": "sibling_formatted", "suffix": "_formatted", "overwrite": False},
                    {"id": "sibling_final", "suffix": "_final", "overwrite": False},
                ]
            },
            {"type": "object", "properties": {}, "additionalProperties": False},
        )
    )
    registry.register(
        ToolDefinition(
            "inspect_input_document",
            "读取本地 DOCX 的结构、字符数量和可选正文",
            ToolRiskLevel.LOCAL_CONTENT_READ,
            _inspect_input_document,
            {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "include_text": {"type": "boolean"},
                    "include_format_evidence": {"type": "boolean"},
                    "max_characters": {"type": "integer", "minimum": 1, "maximum": 100000},
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        )
    )
    registry.register(
        ToolDefinition(
            "create_exam_user_plan_from_docx",
            "把现用完整试卷改造成可复用卷面，并创建仅属于当前用户的试卷方案",
            ToolRiskLevel.DURABLE_WORKSPACE_WRITE,
            lambda args: _create_exam_user_plan(args, plan_activator),
            {
                "type": "object",
                "properties": {
                    "source_path": {"type": "string"},
                    "plan_name": {"type": "string", "maxLength": 120},
                },
                "required": ["source_path"],
                "additionalProperties": False,
            },
        )
    )
    for name, description in (
        ("select_work_mode_draft", "在会话计划中选择工作模式，不修改工作台"),
        ("bind_scene_draft", "在会话计划中绑定方案，不修改工作台"),
        ("bind_template_draft", "在会话计划中绑定模板，不修改工作台"),
        ("bind_materials_draft", "在会话计划中绑定资料引用，不修改工作台"),
        ("set_output_policy_draft", "在会话计划中设置输出策略，不生成文件"),
        ("draft_document_outline", "生成结构化文档大纲草稿"),
        ("generate_document_fragments", "生成类型化内容片段草稿"),
        ("update_document_fragment", "修改一个类型化内容片段草稿"),
    ):
        registry.register(
            ToolDefinition(
                name,
                description,
                ToolRiskLevel.SESSION_DRAFT_WRITE,
                lambda args, tool_name=name: {"draft_operation": tool_name, "arguments": dict(args)},
                {"type": "object", "additionalProperties": True},
            )
        )
    if production is not None:
        registry.register(
            ToolDefinition(
                "build_preflight_preview",
                "读取输入及配置并生成确定性执行前检查",
                ToolRiskLevel.LOCAL_CONTENT_READ,
                lambda _args: {"available": True, "adapter": "form_production"},
                {"type": "object", "additionalProperties": True},
            )
        )
    return registry


def _list_work_modes(_args: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "work_modes": [
            {
                "id": item.mode_id,
                "label": item.label,
                "description": item.description,
                "default_scene_id": item.default_scene_id,
                "default_template_id": item.default_template_id,
            }
            for item in list_work_modes()
        ]
    }


def _match_scene_request(args: Mapping[str, Any]) -> dict[str, Any]:
    query = str(args.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    return natural_request_route_payload(route_natural_scene_request(query))


def _list_scenes(args: Mapping[str, Any], snapshot: SnapshotProvider) -> dict[str, Any]:
    mode_id = str(args.get("mode_id") or snapshot().mode_id or "custom")
    return {
        "mode_id": mode_id,
        "scenes": [
            {
                "id": item.config_id,
                "scene_id": item.scene_id,
                "name": item.name,
                "description": item.description,
                "template_id": item.template_id,
                "source_type": item.source_type,
                "available": item.is_available,
            }
            for item in list_scene_descriptors(mode_id=mode_id)
        ],
    }


def _list_templates(args: Mapping[str, Any], snapshot: SnapshotProvider) -> dict[str, Any]:
    mode_id = str(args.get("mode_id") or snapshot().mode_id or "custom")
    return {
        "mode_id": mode_id,
        "templates": [
            {
                "id": item.config_id,
                "name": item.name,
                "source_type": item.source_type,
                "available": item.is_available,
            }
            for item in list_template_entries(mode_id=mode_id)
        ],
    }


def _inspect_input_document(args: Mapping[str, Any]) -> dict[str, Any]:
    path = Path(str(args.get("path") or "")).expanduser()
    if not path.is_file():
        raise FileNotFoundError("Input document does not exist")
    if path.suffix.casefold() != ".docx":
        raise ValueError("Only DOCX input is supported")
    document = Document(str(path))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    character_count = sum(len(text) for text in paragraphs)
    heading_count = sum(
        1
        for paragraph in document.paragraphs
        if str(getattr(paragraph.style, "name", "") or "").casefold().startswith("heading")
    )
    result: dict[str, Any] = {
        "name": path.name,
        "sha256": file_sha256(path),
        "paragraph_count": len(document.paragraphs),
        "heading_count": heading_count,
        "table_count": len(document.tables),
        "character_count": character_count,
    }
    if bool(args.get("include_text", False)):
        max_characters = max(1, min(int(args.get("max_characters") or 40000), 100000))
        text = "\n".join(paragraphs)
        result["text"] = text[:max_characters]
        result["text_truncated"] = len(text) > max_characters
    if bool(args.get("include_format_evidence", False)):
        result["format_evidence"] = extract_docx_format_evidence(path)
    return result


def _create_exam_user_plan(
    args: Mapping[str, Any],
    plan_activator: PlanActivator | None,
) -> dict[str, Any]:
    source_path = str(args.get("source_path") or "").strip()
    if not source_path:
        raise ValueError("source_path is required")
    plan_name = str(args.get("plan_name") or "").strip() or None
    result = create_exam_user_plan_from_docx(
        source_path,
        plan_name=plan_name,
        activate=plan_activator,
    )
    return {
        "plan_id": result.plan_id,
        "plan_name": result.plan_name,
        "plan_file_name": result.plan_path.name,
        "master_id": result.master_id,
        "master_file_name": result.master_path.name,
        "source_sha256": result.source_sha256,
        "master_sha256": result.master_sha256,
        "preflight_status": result.preflight_status,
        "activation_attempted": result.activation_attempted,
        "activation_succeeded": result.activation_succeeded,
        "activation_error": result.activation_error,
    }


def _mode_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {"mode_id": {"type": "string"}},
        "additionalProperties": False,
    }


__all__ = ["build_form_tool_registry"]
