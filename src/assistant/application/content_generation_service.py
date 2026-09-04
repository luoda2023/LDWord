"""Provider-to-compiler content generation with disclosure enforcement."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import re
from uuid import uuid4

from src.assistant.adapters.content_generation_adapter import (
    AssistantContentGenerationAdapter,
    GeneratedDraft,
)
from src.assistant.application.capability_registry import (
    NARRATIVE_PROMPT_PROFILE_ID,
    system_prompt_for_profile,
)
from src.assistant.domain.exam_authoring_contract import (
    ExamBlueprint,
    ExamSectionBlueprint,
    exam_generation_prompt_addendum,
    generated_exam_blockers,
    parse_exam_authoring_requirements,
    resolve_exam_blueprint,
)
from src.assistant.contracts.task_plan import (
    ARTIFACT_KIND_EXAM,
    ARTIFACT_KIND_NARRATIVE,
)
from src.assistant.contracts.permissions import DisclosureGrant
from src.assistant.runtime.cancellation import AssistantCancellationToken, is_cancelled
from src.assistant.runtime.provider_contract import (
    PROVIDER_DONE,
    PROVIDER_ERROR,
    PROVIDER_TEXT_DELTA,
    ModelGateway,
    ProviderRequest,
)
from src.shared.engine.exam_question_schema import parse_exam_markdown_source


_EXAM_QUESTION_PHASE_IGNORED_ISSUES = frozenset(
    {"missing_answer", "missing_answer_block"}
)
_EXAM_SECTION_PHASE_IGNORED_ISSUES = frozenset(
    {
        *_EXAM_QUESTION_PHASE_IGNORED_ISSUES,
        "question_number_sequence_invalid",
        "total_score_mismatch",
    }
)
_EXAM_QUESTION_PHASE_IGNORED_BLOCKERS = frozenset(
    {
        "answer_coverage_incomplete",
        "requested_analysis_coverage_incomplete",
    }
)
_EXAM_SECTION_SCORE_REPAIR_CODES = frozenset(
    {
        "section_score_coverage_incomplete",
        "section_score_mismatch",
        "section_per_question_score_mismatch",
    }
)
_EXAM_INLINE_SCORE_RE = re.compile(
    r"[\(（]\s*\d+(?:\.\d+)?\s*分\s*[\)）]"
)


@dataclass(frozen=True, slots=True)
class ContentGenerationRequest:
    session_id: str
    turn_id: str
    prompt: str
    provider_id: str
    model_id: str
    generation_id: str = ""
    plan_id: str = ""
    plan_revision: int = 0
    plan_fingerprint: str = ""
    context_text: str = ""
    context_documents: tuple[dict[str, object], ...] = ()
    context_refs: tuple[str, ...] = ()
    context_fields: tuple[str, ...] = ()
    context_fingerprints: tuple[tuple[str, str], ...] = ()
    disclosure_grant: DisclosureGrant | None = None
    capability_id: str = ""
    artifact_kind: str = ARTIFACT_KIND_NARRATIVE
    prompt_profile_id: str = NARRATIVE_PROMPT_PROFILE_ID
    scene_id: str = ""
    scale_profile_id: str = ""
    document_type_id: str = ""
    authoritative_fields: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        if not self.session_id or not self.turn_id or not self.prompt.strip():
            raise ValueError("Content generation identity and prompt are required")
        object.__setattr__(
            self,
            "context_documents",
            tuple(dict(item) for item in self.context_documents),
        )
        object.__setattr__(
            self,
            "authoritative_fields",
            dict(self.authoritative_fields or {}),
        )
        if self.context_text or self.context_documents:
            grant = self.disclosure_grant
            fingerprints = dict(self.context_fingerprints)
            if grant is None or not grant.permits(
                session_id=self.session_id,
                provider_id=self.provider_id,
                model_id=self.model_id,
                refs=self.context_refs,
                fields=self.context_fields,
                fingerprints=fingerprints,
            ):
                raise PermissionError("content_context_disclosure_not_authorized")


class AssistantContentGenerationService:
    def __init__(self, adapter: AssistantContentGenerationAdapter) -> None:
        self.adapter = adapter

    def generate(
        self,
        request: ContentGenerationRequest,
        gateway: ModelGateway,
        *,
        cancellation: AssistantCancellationToken | None = None,
        delta_callback=None,
    ) -> GeneratedDraft:
        unregister = (
            cancellation.register_cancel_callback(gateway.cancel)
            if cancellation is not None
            else lambda: None
        )
        user_content = request.prompt.strip()
        context_text = request.context_text
        if request.context_documents:
            from src.assistant.runtime.turn_runner import build_attachment_context

            extracted, _audit = build_attachment_context(request.context_documents)
            context_text = "\n\n".join(
                part for part in (context_text.strip(), extracted.strip()) if part
            )
        if context_text:
            user_content += "\n\n以下素材已由用户明确授权用于本次生成：\n" + context_text
        if request.document_type_id:
            user_content += (
                "\n\n本次任务已确定的公文文种 ID："
                + request.document_type_id
                + "。不得改成其他文种。"
            )
        try:
            if request.artifact_kind == ARTIFACT_KIND_EXAM:
                draft = self._generate_staged_exam(
                    request,
                    gateway,
                    user_content=user_content,
                    cancellation=cancellation,
                )
                if delta_callback is not None:
                    delta_callback(
                        Path(draft.markdown_path).read_text(encoding="utf-8")
                    )
                return draft

            system_prompt = system_prompt_for_profile(request.prompt_profile_id)
            if request.artifact_kind == ARTIFACT_KIND_EXAM:
                system_prompt += exam_generation_prompt_addendum(
                    request.prompt,
                    scene_id=request.scene_id,
                    scale_profile_id=request.scale_profile_id,
                )
            provider_request = self._provider_request(
                request,
                system_prompt=system_prompt,
                user_content=user_content,
                generation_phase="single",
            )
            generated_text = self._collect_provider_text(
                gateway,
                provider_request,
                cancellation=cancellation,
                delta_callback=delta_callback,
            )
            if is_cancelled(cancellation):
                raise RuntimeError("content_generation_cancelled")
            return self.adapter.compile_generated(
                session_id=request.session_id,
                markdown=generated_text,
                artifact_kind=request.artifact_kind,
                intent=request.prompt,
                scene_id=request.scene_id,
                scale_profile_id=request.scale_profile_id,
                prompt_profile_id=request.prompt_profile_id,
                document_type_id=request.document_type_id,
                authoritative_fields=request.authoritative_fields,
                cancelled=(cancellation.cancelled if cancellation is not None else None),
            )
        finally:
            unregister()

    def _generate_staged_exam(
        self,
        request: ContentGenerationRequest,
        gateway: ModelGateway,
        *,
        user_content: str,
        cancellation: AssistantCancellationToken | None,
    ) -> GeneratedDraft:
        blueprint = resolve_exam_blueprint(
            request.prompt,
            scene_id=request.scene_id,
            scale_profile_id=request.scale_profile_id,
        )
        base_prompt = system_prompt_for_profile(request.prompt_profile_id)
        base_prompt += exam_generation_prompt_addendum(
            request.prompt,
            scene_id=request.scene_id,
            scale_profile_id=request.scale_profile_id,
        )
        question_prompt = (
            base_prompt
            + "\n\n【分阶段生成：第一阶段——只生成试题】\n"
            "只输出标题、元数据、全部大题和全部题目；暂时不要输出答案速查、"
            "解析或评分标准。必须完整写到蓝图中的最后一道题后再结束。"
        )
        question_markdown = ""
        question_issues: tuple[str, ...] = ()
        full_attempt_count = 1 if blueprint.section_blueprints else 2
        for attempt in range(full_attempt_count):
            phase_user_content = user_content
            if attempt:
                phase_user_content += (
                    "\n\n上一稿没有通过本地题目蓝图校验。请从 # 标题开始完整重写，"
                    "不要解释，也不要省略任何题目。错误代码："
                    + ", ".join(question_issues)
                    + "\n\n上一稿如下，仅用于定位遗漏：\n"
                    + question_markdown
                )
            question_markdown = self._collect_provider_text(
                gateway,
                self._provider_request(
                    request,
                    system_prompt=question_prompt,
                    user_content=phase_user_content,
                    generation_phase=(
                        "questions" if attempt == 0 else "questions_repair"
                    ),
                ),
                cancellation=cancellation,
            )
            question_markdown = _strip_exam_answer_block(question_markdown)
            question_markdown = _normalize_exam_header_metadata(
                question_markdown,
                intent=request.prompt,
                blueprint=blueprint,
            )
            question_markdown = _normalize_exam_difficulty_metadata(
                question_markdown,
                blueprint.difficulty_counts,
            )
            question_markdown = _normalize_exam_score_metadata(
                question_markdown,
                _blueprint_score_plan(blueprint, question_markdown),
            )
            question_issues = _exam_question_phase_blockers(
                question_markdown,
                intent=request.prompt,
                scene_id=request.scene_id,
                scale_profile_id=request.scale_profile_id,
            )
            if not question_issues:
                break
        if question_issues and blueprint.section_blueprints:
            question_markdown = self._generate_exam_sections(
                request,
                gateway,
                user_content=user_content,
                base_prompt=base_prompt,
                blueprint=blueprint,
                seed_markdown=question_markdown,
                cancellation=cancellation,
            )
            question_markdown = _normalize_exam_difficulty_metadata(
                question_markdown,
                blueprint.difficulty_counts,
            )
            question_markdown = _normalize_exam_score_metadata(
                question_markdown,
                _blueprint_score_plan(blueprint, question_markdown),
            )
            question_issues = _exam_question_phase_blockers(
                question_markdown,
                intent=request.prompt,
                scene_id=request.scene_id,
                scale_profile_id=request.scale_profile_id,
            )
        if question_issues:
            diagnostic_path = self.adapter.persist_rejected_exam(
                session_id=request.session_id,
                markdown=question_markdown,
                phase="questions",
            )
            raise ValueError(
                "exam_question_phase_blocked:"
                + ",".join(question_issues)
                + f"|diagnostic={diagnostic_path}"
            )

        answer_prompt = (
            "你是一名严谨的试卷答案编审。根据用户消息中已经冻结的试题，"
            "只输出一个“## 答案速查”区块，不要重复标题、元数据、题干或大题。\n"
            "要求：按全卷题号从 1 连续写到最后一题，每个题号恰好出现一次；"
            "客观题给出唯一答案并写简短解析；主观题给出参考答案、解析和逐点评分标准；"
            "不得更改题目分值；使用纯 Markdown 文本，不要使用 **加粗标记**、"
            "水平分隔线或重复大题标题，不要使用 JSON 或代码围栏包住整个输出。"
            "程序题必须逐行核算：Python 3 中字符串与整数使用 >、<、>=、<= "
            "比较会抛出 TypeError；两个字符串之间则可以按字典序比较，二者不得混淆。"
        )
        answer_markdown = ""
        last_error = ""
        for attempt in range(2):
            answer_user_content = (
                "以下试题已经通过结构校验，请为它生成答案区：\n\n"
                + question_markdown
            )
            if attempt:
                answer_user_content += (
                    "\n\n上一版答案没有通过合卷校验。请重新输出完整答案区。"
                    f"错误：{last_error}\n\n上一版答案：\n{answer_markdown}"
                )
            answer_markdown = self._collect_provider_text(
                gateway,
                self._provider_request(
                    request,
                    system_prompt=answer_prompt,
                    user_content=answer_user_content,
                    generation_phase=(
                        "answers" if attempt == 0 else "answers_repair"
                    ),
                ),
                cancellation=cancellation,
            )
            answer_markdown = _normalize_exam_answer_numbering(
                answer_markdown,
                expected_count=blueprint.question_count,
            )
            combined = (
                question_markdown.rstrip()
                + "\n\n"
                + answer_markdown.strip()
                + "\n"
            )
            try:
                return self.adapter.compile_generated(
                    session_id=request.session_id,
                    markdown=combined,
                    artifact_kind=request.artifact_kind,
                    intent=request.prompt,
                    scene_id=request.scene_id,
                    scale_profile_id=request.scale_profile_id,
                    prompt_profile_id=request.prompt_profile_id,
                    cancelled=(
                        cancellation.cancelled
                        if cancellation is not None
                        else None
                    ),
                )
            except ValueError as exc:
                last_error = str(exc)
        raise ValueError(last_error or "exam_answer_phase_blocked")

    def _generate_exam_sections(
        self,
        request: ContentGenerationRequest,
        gateway: ModelGateway,
        *,
        user_content: str,
        base_prompt: str,
        blueprint: ExamBlueprint,
        seed_markdown: str,
        cancellation: AssistantCancellationToken | None,
    ) -> str:
        header = _deterministic_exam_markdown_header(request.prompt, blueprint)
        sections: list[str] = []
        first_question_number = 1
        for section_index, section in enumerate(
            blueprint.section_blueprints,
            start=1,
        ):
            last_question_number = (
                first_question_number + section.question_count - 1
            )
            expected_numbers = tuple(
                range(first_question_number, last_question_number + 1)
            )
            difficulty_text = _difficulty_plan_for_numbers(
                blueprint,
                expected_numbers,
            )
            score_text = "、".join(
                f"第 {number} 题 {_format_exam_number(score)} 分"
                for number, score in zip(
                    expected_numbers,
                    section.question_score_plan(),
                )
            )
            section_prompt = (
                base_prompt
                + "\n\n【分阶段生成：单个大题】\n"
                "本阶段只输出一个大题，不得输出试卷标题、元数据、其他大题或答案区。"
                f"\n大题标题必须以“## {section.label}”开头。"
                f"\n只生成全卷第 {first_question_number}-{last_question_number} 题，"
                f"恰好 {section.question_count} 道，题号必须使用这些全局题号。"
                f"\n本大题总分必须为 {_format_exam_number(section.total_score)} 分；"
                "每道题都要明确标分，所有题目分值之和必须等于本大题总分。"
                f"\n题号与分值必须依次为：{score_text}；不得改成小数均分。"
                f"\n难度必须按题号设置为：{difficulty_text}。"
                "\n每题必须给出 knowledge_points；选择题必须有 A-D 四个完整选项；"
                "主观题按真实作答量设置 answer_area_kind 和 answer_lines。"
                "\n题目所需材料和代码必须写在对应题号之后。"
            )
            section_markdown = ""
            section_issues: tuple[str, ...] = ()
            for attempt in range(2):
                phase_user_content = user_content + (
                    f"\n\n当前只完成第 {section_index} 大题：{section.label}。"
                )
                if attempt:
                    phase_user_content += (
                        "\n上一稿没有通过本地大题校验，请完整重写这个大题。"
                        "错误代码："
                        + ", ".join(section_issues)
                        + "\n上一稿：\n"
                        + section_markdown
                    )
                generated = self._collect_provider_text(
                    gateway,
                    self._provider_request(
                        request,
                        system_prompt=section_prompt,
                        user_content=phase_user_content,
                        generation_phase=(
                            f"questions_section_{section_index}"
                            if attempt == 0
                            else f"questions_section_{section_index}_repair"
                        ),
                    ),
                    cancellation=cancellation,
                )
                section_markdown = _extract_exam_section_markdown(
                    generated,
                    section,
                )
                section_issues = _exam_section_phase_blockers(
                    header + "\n\n" + section_markdown,
                    section=section,
                    expected_numbers=expected_numbers,
                )
                if any(
                    issue in _EXAM_SECTION_SCORE_REPAIR_CODES
                    for issue in section_issues
                ):
                    section_markdown = _repair_exam_section_score_metadata(
                        section_markdown,
                        header=header,
                        section=section,
                    )
                    section_issues = _exam_section_phase_blockers(
                        header + "\n\n" + section_markdown,
                        section=section,
                        expected_numbers=expected_numbers,
                    )
                if not section_issues:
                    break
            if section_issues:
                diagnostic_path = self.adapter.persist_rejected_exam(
                    session_id=request.session_id,
                    markdown=header.rstrip() + "\n\n" + section_markdown,
                    phase=f"questions_section_{section_index}",
                )
                raise ValueError(
                    "exam_section_phase_blocked:"
                    f"section_{section_index}:"
                    + ",".join(section_issues)
                    + f"|diagnostic={diagnostic_path}"
                )
            sections.append(section_markdown)
            first_question_number = last_question_number + 1
        return header.rstrip() + "\n\n" + "\n\n".join(sections) + "\n"

    @staticmethod
    def _provider_request(
        request: ContentGenerationRequest,
        *,
        system_prompt: str,
        user_content: str,
        generation_phase: str,
    ) -> ProviderRequest:
        return ProviderRequest(
            request_id=uuid4().hex,
            model=request.model_id,
            system_prompt=system_prompt,
            messages=({"role": "user", "content": user_content},),
            metadata={
                "session_id": request.session_id,
                "purpose": "content_generation",
                "capability_id": request.capability_id,
                "artifact_kind": request.artifact_kind,
                "prompt_profile_id": request.prompt_profile_id,
                "scene_id": request.scene_id,
                "scale_profile_id": request.scale_profile_id,
                "generation_phase": generation_phase,
            },
        )

    @staticmethod
    def _collect_provider_text(
        gateway: ModelGateway,
        provider_request: ProviderRequest,
        *,
        cancellation: AssistantCancellationToken | None,
        delta_callback=None,
    ) -> str:
        parts: list[str] = []
        for event in gateway.stream(provider_request):
            if is_cancelled(cancellation):
                raise RuntimeError("content_generation_cancelled")
            if event.type == PROVIDER_TEXT_DELTA:
                parts.append(event.text)
                if delta_callback is not None:
                    delta_callback(event.text)
            elif event.type == PROVIDER_ERROR:
                raise RuntimeError(event.text or "content_generation_provider_failed")
            elif event.type == PROVIDER_DONE and not parts and event.text:
                parts.append(event.text)
        return "".join(parts)


def _strip_exam_answer_block(markdown: str) -> str:
    text = str(markdown or "")
    match = re.search(r"(?m)^##+\s+.*答案(?:速查|解析|与评分)?.*$", text)
    return (text[: match.start()] if match else text).rstrip() + "\n"


def _normalize_exam_header_metadata(
    markdown: str,
    *,
    intent: str,
    blueprint: ExamBlueprint,
) -> str:
    """Keep semantic metadata controller-owned while retaining generated items."""

    text = _strip_exam_answer_block(markdown)
    section_match = re.search(r"(?m)^##+\s+\S.*$", text)
    if section_match is None:
        return text
    body = text[section_match.start() :].strip()
    return (
        _deterministic_exam_markdown_header(intent, blueprint).rstrip()
        + "\n\n"
        + body
        + "\n"
    )


def _deterministic_exam_markdown_header(
    intent: str,
    blueprint: ExamBlueprint,
) -> str:
    requirements = parse_exam_authoring_requirements(intent)
    subject = requirements.subject or "综合"
    grade = _exam_display_grade(requirements, intent)
    normalized_intent = str(intent or "")
    if "期末" in normalized_intent:
        suffix = "期末试卷"
    elif "期中" in normalized_intent:
        suffix = "期中试卷"
    elif blueprint.profile.profile_id == "quiz":
        suffix = "随堂测验"
    elif "阶段" in normalized_intent:
        suffix = "阶段测试"
    else:
        suffix = "单元测试"
    topic = " Python" if "python" in normalized_intent.casefold() else ""
    title = f"{grade}{subject}{topic}{suffix}"
    return (
        f"# {title}\n"
        f"> 科目：{subject}　年级：{grade}　"
        f"考试时间：{_format_exam_number(blueprint.duration_minutes)} 分钟　"
        f"满分：{_format_exam_number(blueprint.total_score)} 分"
    )


def _exam_display_grade(requirements, intent: str) -> str:
    grade = requirements.grade or "适用年级"
    stage = requirements.school_stage
    normalized_intent = str(intent or "")
    canonical_grade = (
        _canonical_exam_grade(stage, grade)
        if grade != "适用年级"
        else grade
    )
    if stage == "小学" and grade != "适用年级":
        return f"小学{canonical_grade}"
    if stage == "初中" and grade == "六年级" and "预备" in normalized_intent:
        return f"初中预备班（{grade}）"
    if stage == "初中" and grade != "适用年级":
        return f"初中{canonical_grade}"
    return canonical_grade


def _canonical_exam_grade(stage: str, grade: str) -> str:
    value = re.sub(r"\s+", "", str(grade or ""))
    if stage == "高中":
        return {
            "一年级": "高一",
            "二年级": "高二",
            "三年级": "高三",
        }.get(value, value)
    if stage == "初中":
        return {
            "一年级": "七年级",
            "二年级": "八年级",
            "三年级": "九年级",
            "初一": "七年级",
            "初二": "八年级",
            "初三": "九年级",
        }.get(value, value)
    return value


def _normalize_exam_answer_numbering(
    markdown: str,
    *,
    expected_count: int,
) -> str:
    """Repair section-restarted answer numbers when answer order is complete.

    Only top-level answer entries are touched, and only when their count exactly
    matches the frozen question count.  Numbered reasoning steps and incomplete
    answers are left unchanged for the validator to reject or repair upstream.
    """

    lines = str(markdown or "").splitlines()
    entry_indexes: list[int] = []
    entry_matches: list[re.Match[str]] = []
    pattern = re.compile(r"^(?P<indent> {0,3})(?P<number>\d+)(?P<sep>[.、])(?P<rest>\s+.+)$")
    in_answer_block = not any(
        re.match(r"^##+\s+.*答案", line.strip()) for line in lines
    )
    for index, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"^##+\s+.*答案", stripped):
            in_answer_block = True
            continue
        subgroup_heading = re.match(r"^##+\s+(.+?)\s*$", stripped)
        if in_answer_block and subgroup_heading is not None:
            subgroup_title = subgroup_heading.group(1).strip()
            if re.match(
                r"^[一二三四五六七八九十]+[、.．]\s*.+",
                subgroup_title,
            ) or subgroup_title.endswith("题"):
                lines[index] = subgroup_title
            continue
        if not in_answer_block:
            continue
        match = pattern.match(line.expandtabs(4))
        if match is not None:
            entry_indexes.append(index)
            entry_matches.append(match)
    if len(entry_indexes) != int(expected_count or 0) or expected_count < 1:
        return str(markdown or "").strip() + "\n"
    for number, (index, match) in enumerate(
        zip(entry_indexes, entry_matches),
        start=1,
    ):
        lines[index] = (
            f"{match.group('indent')}{number}{match.group('sep')}"
            f"{match.group('rest')}"
        )
    return "\n".join(lines).strip() + "\n"


def _extract_exam_section_markdown(
    markdown: str,
    section: ExamSectionBlueprint,
) -> str:
    text = _strip_exam_answer_block(markdown)
    section_match = re.search(r"(?m)^##+\s+\S.*$", text)
    if section_match is None:
        return ""
    body_start = text.find("\n", section_match.start())
    if body_start < 0:
        body = ""
    else:
        body = text[body_start + 1 :]
        next_section = re.search(r"(?m)^##+\s+\S.*$", body)
        if next_section is not None:
            body = body[: next_section.start()]
    return _exam_section_heading(section) + "\n\n" + body.strip()


def _exam_section_heading(section: ExamSectionBlueprint) -> str:
    score_plan = section.question_score_plan()
    if score_plan and all(
        abs(score - score_plan[0]) <= 0.001 for score in score_plan
    ):
        score_clause = (
            f"每小题 {_format_exam_number(score_plan[0])} 分，"
        )
    else:
        score_clause = ""
    return (
        f"## {section.label}（本大题共 {section.question_count} 小题，"
        f"{score_clause}共 {_format_exam_number(section.total_score)} 分）"
    )


def _exam_section_phase_blockers(
    markdown: str,
    *,
    section: ExamSectionBlueprint,
    expected_numbers: tuple[int, ...],
) -> tuple[str, ...]:
    result = parse_exam_markdown_source(markdown)
    blockers = [
        str(issue.kind or "unknown")
        for issue in result.issues
        if str(issue.severity or "").casefold() == "error"
        and str(issue.kind or "") not in _EXAM_SECTION_PHASE_IGNORED_ISSUES
    ]
    payload_sections = [
        item
        for item in list(result.payload.get("sections") or [])
        if isinstance(item, dict)
    ]
    if len(payload_sections) != 1:
        blockers.append("section_count_mismatch")
        return tuple(dict.fromkeys(blockers))
    questions = [
        item
        for item in list(payload_sections[0].get("questions") or [])
        if isinstance(item, dict)
    ]
    if len(questions) != section.question_count:
        blockers.append("section_question_count_mismatch")
    numbers = tuple(
        int(question.get("number"))
        for question in questions
        if str(question.get("number") or "").isdigit()
    )
    if numbers != expected_numbers:
        blockers.append("section_question_number_mismatch")
    scores = [
        _first_exam_number(question.get("score"))
        for question in questions
    ]
    if any(score is None for score in scores):
        blockers.append("section_score_coverage_incomplete")
    elif abs(
        sum(float(score) for score in scores if score is not None)
        - section.total_score
    ) > 0.01:
        blockers.append("section_score_mismatch")
    if any(not str(question.get("difficulty") or "").strip() for question in questions):
        blockers.append("section_difficulty_metadata_incomplete")
    if any(
        not question.get("knowledge_points")
        for question in questions
    ):
        blockers.append("section_knowledge_points_incomplete")
    if "选择" in section.label:
        for question in questions:
            options = question.get("options")
            if not isinstance(options, list) or len(options) < 4:
                blockers.append("section_choice_options_incomplete")
                break
    return tuple(dict.fromkeys(blockers))


def _difficulty_plan_for_numbers(
    blueprint: ExamBlueprint,
    numbers: tuple[int, ...],
) -> str:
    labels = {
        "basic": "基础",
        "medium": "中等",
        "advanced": "提高",
    }
    expanded = [
        labels[level]
        for level, count in blueprint.difficulty_counts
        for _ in range(max(0, count))
    ]
    return "、".join(
        f"{number}={expanded[number - 1]}"
        for number in numbers
        if 0 < number <= len(expanded)
    )


def _first_exam_number(value: object) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    return float(match.group(0)) if match else None


def _format_exam_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def _blueprint_score_plan(
    blueprint: ExamBlueprint,
    markdown: str = "",
) -> tuple[float | None, ...]:
    scores: list[float | None] = []
    parsed_sections: list[Mapping[str, object]] = []
    if str(markdown or "").strip():
        result = parse_exam_markdown_source(markdown)
        parsed_sections = [
            section
            for section in list(result.payload.get("sections") or [])
            if isinstance(section, Mapping)
        ]
    for section_index, section in enumerate(blueprint.section_blueprints):
        parsed_questions = (
            [
                question
                for question in list(
                    parsed_sections[section_index].get("questions") or []
                )
                if isinstance(question, Mapping)
            ]
            if section_index < len(parsed_sections)
            else []
        )
        existing = tuple(
            _first_exam_number(question.get("score"))
            for question in parsed_questions
        )
        if _score_plan_is_acceptable(
            existing,
            expected_count=section.question_count,
            expected_total=section.total_score,
        ):
            scores.extend(existing)
        else:
            scores.extend(section.question_score_plan())
    if scores:
        return tuple(scores)

    existing_scores = _existing_exam_score_plan(
        markdown,
        expected_count=blueprint.question_count,
        expected_total=blueprint.total_score,
    )
    if existing_scores:
        return existing_scores
    return _balanced_exam_score_plan(
        blueprint.total_score,
        blueprint.question_count,
    )


def _repair_exam_section_score_metadata(
    markdown: str,
    *,
    header: str,
    section: ExamSectionBlueprint,
) -> str:
    del header
    return _normalize_exam_score_metadata(
        markdown,
        tuple(section.question_score_plan()),
    )


def _balanced_exam_score_plan(
    total_score: float,
    question_count: int,
) -> tuple[float | None, ...]:
    count = max(1, int(question_count))
    use_whole_points = (
        float(total_score).is_integer() and float(total_score) >= count
    )
    precision = 1 if use_whole_points else 100
    total_units = round(float(total_score) * precision)
    base_units, remainder = divmod(total_units, count)
    return tuple(
        (
            base_units
            + (1 if question_index >= count - remainder else 0)
        )
        / precision
        for question_index in range(count)
    )


def _existing_exam_score_plan(
    markdown: str,
    *,
    expected_count: int,
    expected_total: float,
) -> tuple[float | None, ...]:
    if not str(markdown or "").strip():
        return ()
    result = parse_exam_markdown_source(markdown)
    questions = [
        question
        for section in list(result.payload.get("sections") or [])
        if isinstance(section, dict)
        for question in list(section.get("questions") or [])
        if isinstance(question, dict)
    ]
    scores = tuple(
        _first_exam_number(question.get("score")) for question in questions
    )
    return (
        scores
        if _score_plan_is_acceptable(
            scores,
            expected_count=expected_count,
            expected_total=expected_total,
        )
        else ()
    )


def _score_plan_is_acceptable(
    scores: tuple[float | None, ...],
    *,
    expected_count: int,
    expected_total: float,
) -> bool:
    if (
        len(scores) != expected_count
        or any(score is None or score <= 0 for score in scores)
        or abs(
            sum(float(score) for score in scores if score is not None)
            - float(expected_total)
        )
        > 0.01
    ):
        return False
    if float(expected_total).is_integer() and float(expected_total) >= expected_count:
        return all(
            float(score).is_integer()
            for score in scores
            if score is not None
        )
    return True


def _normalize_exam_score_metadata(
    markdown: str,
    desired_scores: tuple[float | None, ...],
) -> str:
    lines = str(markdown or "").splitlines()
    question_positions = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^ {0,3}\d+[\.\u3001]\s+\S", line.expandtabs(4))
    ]
    offset = 0
    for question_index, start in enumerate(question_positions):
        if question_index >= len(desired_scores):
            break
        desired_score = desired_scores[question_index]
        if desired_score is None:
            continue
        adjusted_start = start + offset
        next_question = (
            question_positions[question_index + 1] + offset
            if question_index + 1 < len(question_positions)
            else len(lines)
        )
        boundary = next_question
        for index in range(adjusted_start + 1, next_question):
            if re.match(r"^\s*##+\s+\S", lines[index]):
                boundary = index
                break
        score_line = next(
            (
                index
                for index in range(adjusted_start + 1, boundary)
                if re.match(
                    r"^\s*(?:score|points)\s*[:：]",
                    lines[index],
                    flags=re.IGNORECASE,
                )
            ),
            None,
        )
        score_text = _format_exam_number(desired_score)
        inline_score_positions = [
            (index, match)
            for index in range(adjusted_start, boundary)
            for match in _EXAM_INLINE_SCORE_RE.finditer(lines[index])
        ]
        if len(inline_score_positions) == 1:
            inline_index, inline_match = inline_score_positions[0]
            lines[inline_index] = (
                lines[inline_index][: inline_match.start()]
                + f"（{score_text} 分）"
                + lines[inline_index][inline_match.end() :]
            )
        if score_line is not None:
            indentation = lines[score_line][
                : len(lines[score_line]) - len(lines[score_line].lstrip())
            ]
            lines[score_line] = f"{indentation}score: {score_text}"
            continue
        insertion = boundary
        while insertion > adjusted_start + 1 and not lines[insertion - 1].strip():
            insertion -= 1
        lines.insert(insertion, f"   score: {score_text}")
        offset += 1
    return "\n".join(lines).rstrip() + "\n"


def _normalize_exam_difficulty_metadata(
    markdown: str,
    difficulty_counts: tuple[tuple[str, int], ...],
) -> str:
    labels = {
        "basic": "基础",
        "medium": "中等",
        "advanced": "提高",
    }
    desired = [
        labels[level]
        for level, count in difficulty_counts
        for _ in range(max(0, count))
    ]
    lines = str(markdown or "").splitlines()
    question_positions = [
        index
        for index, line in enumerate(lines)
        if re.match(r"^ {0,3}\d+[\.\u3001]\s+\S", line.expandtabs(4))
    ]
    offset = 0
    for question_index, start in enumerate(question_positions):
        if question_index >= len(desired):
            break
        adjusted_start = start + offset
        next_question = (
            question_positions[question_index + 1] + offset
            if question_index + 1 < len(question_positions)
            else len(lines)
        )
        boundary = next_question
        for index in range(adjusted_start + 1, next_question):
            if re.match(r"^\s*##+\s+\S", lines[index]):
                boundary = index
                break
        difficulty_line = next(
            (
                index
                for index in range(adjusted_start + 1, boundary)
                if re.match(
                    r"^\s*(?:difficulty|difficulty_level)\s*[:：]",
                    lines[index],
                    flags=re.IGNORECASE,
                )
            ),
            None,
        )
        if difficulty_line is not None:
            indentation = lines[difficulty_line][
                : len(lines[difficulty_line]) - len(lines[difficulty_line].lstrip())
            ]
            lines[difficulty_line] = (
                f"{indentation}difficulty: {desired[question_index]}"
            )
            continue
        insertion = boundary
        while insertion > adjusted_start + 1 and not lines[insertion - 1].strip():
            insertion -= 1
        lines.insert(
            insertion,
            f"   difficulty: {desired[question_index]}",
        )
        offset += 1
    return "\n".join(lines).rstrip() + "\n"


def _exam_question_phase_blockers(
    markdown: str,
    *,
    intent: str,
    scene_id: str,
    scale_profile_id: str = "",
) -> tuple[str, ...]:
    result = parse_exam_markdown_source(markdown)
    codes = [
        str(issue.kind or "unknown")
        for issue in result.issues
        if str(issue.severity or "").casefold() == "error"
        and str(issue.kind or "") not in _EXAM_QUESTION_PHASE_IGNORED_ISSUES
    ]
    codes.extend(
        code
        for code in generated_exam_blockers(
            markdown,
            result,
            intent=intent,
            scene_id=scene_id,
            scale_profile_id=scale_profile_id,
        )
        if code not in _EXAM_QUESTION_PHASE_IGNORED_BLOCKERS
    )
    return tuple(dict.fromkeys(codes))


__all__ = ["AssistantContentGenerationService", "ContentGenerationRequest"]
