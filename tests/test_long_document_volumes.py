# -*- coding: utf-8 -*-
"""Regression tests for long-document volume checkpoints."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from src.assistant.adapters.content_generation_adapter import (
    AssistantContentGenerationAdapter,
)
from src.assistant.application.content_generation_service import (
    AssistantContentGenerationService,
    ContentGenerationRequest,
)
from src.assistant.application.long_document_volumes import (
    LongDocumentCheckpointStore,
    plan_volumes,
)
from src.assistant.runtime.provider_contract import (
    PROVIDER_DONE,
    PROVIDER_START,
    PROVIDER_TEXT_DELTA,
    ProviderStreamEvent,
)


def test_thousand_page_outline_is_split_at_chapter_boundaries():
    titles = tuple(f"第{i}章 内容" for i in range(1, 11))
    volumes = plan_volumes(titles, 1000 * 700, volume_pages=100)
    assert len(volumes) == 10
    assert all(volume.chapter_indices == (i,) for i, volume in enumerate(volumes, 1))
    assert [title for volume in volumes for title in volume.chapter_titles] == list(titles)


def test_checkpoint_persists_completed_chapter_and_resumes(tmp_path: Path):
    store = LongDocumentCheckpointStore("resume-test", root=tmp_path)
    titles = ("第一章 概况", "第二章 方案", "第三章 保障")
    manifest = store.initialize(
        session_id="resume-test",
        prompt="写一篇300页的工程文档",
        outline_titles=titles,
        total_chars=300 * 700,
        volume_pages=100,
    )
    assert manifest["status"] == "pending"
    assert len(manifest["volumes"]) == 3

    first_body = "# 第一章 概况\n\n已完成正文。\n"
    store.save_chapter(
        volume_index=1,
        chapter_index=1,
        title=titles[0],
        markdown=first_body,
    )
    assert store.chapter_markdown(1) == first_body
    assert store.chapter_markdown(2) is None

    resumed = store.initialize(
        session_id="resume-test",
        prompt="写一篇300页的工程文档",
        outline_titles=titles,
        total_chars=300 * 700,
        volume_pages=100,
    )
    assert resumed["fingerprint"] == manifest["fingerprint"]
    assert resumed["volumes"][0]["status"] == "completed"
    assert resumed["volumes"][1]["status"] == "pending"

    store.save_chapter(
        volume_index=2,
        chapter_index=2,
        title=titles[1],
        markdown="# 第二章 方案\n\n已完成正文。\n",
    )
    store.save_chapter(
        volume_index=3,
        chapter_index=3,
        title=titles[2],
        markdown="# 第三章 保障\n\n已完成正文。\n",
    )
    store.finalize()
    final = store.load()
    assert final is not None
    assert final["status"] == "completed"
    assert (
        tmp_path
        / "workbench"
        / "resume-test"
        / "long_document"
        / "volumes"
        / "volume-001"
        / "volume.md"
    ).is_file()


def test_checkpoint_fingerprint_invalidates_changed_request(tmp_path: Path):
    store = LongDocumentCheckpointStore("fingerprint-test", root=tmp_path)
    first = store.initialize(
        session_id="fingerprint-test",
        prompt="写一篇300页的文档",
        outline_titles=("第一章", "第二章"),
        total_chars=210000,
        volume_pages=100,
    )
    store.save_chapter(
        volume_index=1,
        chapter_index=1,
        title="第一章",
        markdown="旧正文",
    )
    changed = store.initialize(
        session_id="fingerprint-test",
        prompt="写一篇300页的文档，增加安全章节",
        outline_titles=("第一章", "第二章", "第三章"),
        total_chars=210000,
        volume_pages=100,
    )
    assert changed["fingerprint"] != first["fingerprint"]
    assert all(not volume.get("chapters") for volume in changed["volumes"])


class _InterruptibleGateway:
    def __init__(self, *, fail_after: int | None = None) -> None:
        self.calls: list[str] = []
        self.fail_after = fail_after

    def stream(self, request):
        index = len(self.calls) + 1
        self.calls.append(request.system_prompt)
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise RuntimeError("simulated_process_interruption")
        import re

        title_match = re.search(r"标题必须为：(.+?)\n", request.system_prompt)
        title = title_match.group(1).strip() if title_match else f"第{index}章"
        text = f"# {title}\n\n本章已完成。"
        yield ProviderStreamEvent(PROVIDER_START, metadata={"provider": "test"})
        yield ProviderStreamEvent(PROVIDER_TEXT_DELTA, text=text)
        yield ProviderStreamEvent(
            PROVIDER_DONE, text=text, metadata={"finish_reason": "stop"}
        )

    def cancel(self):
        return False


def _long_request(
    session_id: str,
    titles: tuple[str, ...],
    memory_dir: Path,
    checkpoint_dir: Path,
):
    return ContentGenerationRequest(
        session_id=session_id,
        turn_id="turn-1",
        prompt="写一篇300页的工程文档",
        provider_id="mock",
        model_id="mock-model",
        artifact_kind="narrative_markdown",
        outline_titles=titles,
        outline_notes=("",) * len(titles),
        volume_pages=100,
        checkpoint_dir=str(checkpoint_dir),
        memory_dir=str(memory_dir),
    )


def test_generation_resumes_from_saved_chapter_without_recalling_model(tmp_path: Path):
    titles = ("第一章 概况", "第二章 方案", "第三章 保障")
    adapter = AssistantContentGenerationAdapter(tmp_path / "artifacts")
    service = AssistantContentGenerationService(adapter)
    first = _long_request(
        "service-resume", titles, tmp_path / "memory", tmp_path / "checkpoints"
    )
    interrupted = _InterruptibleGateway(fail_after=2)
    with pytest.raises(RuntimeError, match="simulated_process_interruption"):
        service.generate(first, interrupted)
    assert len(interrupted.calls) == 3

    resumed = _long_request(
        "service-resume", titles, tmp_path / "memory", tmp_path / "checkpoints"
    )
    continuing = _InterruptibleGateway()
    draft = service.generate(resumed, continuing)
    assert len(continuing.calls) == 1
    assert "第三章 保障" in continuing.calls[0]
    markdown = Path(draft.markdown_path).read_text(encoding="utf-8")
    assert all(title in markdown for title in titles)
