"""Single, source-neutral router for material ``{{token}}`` occurrences.

Callers supply already extracted text blocks. A block may carry run fragments;
the router joins them before scanning, so a token split across Word runs is
counted exactly once. It does not inspect OOXML or decide whether a surface is
supported for insertion; those are later preflight responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Iterable, Mapping, Sequence, TypeVar

from src.shared.engine.material_token_contract import (
    MATERIAL_TOKEN_PATTERN,
    MaterialTokenKind,
    MaterialTokenNamespace,
    MaterialTokenProducer,
    material_token_identifier,
    material_token_key,
    normalize_material_token,
    parse_material_token,
)


class _StringEnum(str, Enum):
    pass


class TokenOccurrencePolicy(_StringEnum):
    EXACTLY_ONE = "exactly_one"
    ALL = "all"


class TokenDiagnosticSeverity(_StringEnum):
    ERROR = "error"
    WARNING = "warning"


class TokenDiagnosticCode(_StringEnum):
    INVALID_TOKEN = "invalid_token"
    TYPE_CONFLICT = "type_conflict"
    DUPLICATE_DECLARATION = "duplicate_declaration"
    MISSING_DECLARATION = "missing_declaration"
    MISSING_OCCURRENCE = "missing_occurrence"
    DUPLICATE_OCCURRENCE = "duplicate_occurrence"


@dataclass(frozen=True, slots=True)
class TokenTextBlock:
    """One extracted story block, optionally preserving its run boundaries."""

    block_id: str
    text: str = ""
    runs: tuple[str, ...] = ()
    surface: str = "body"
    story_id: str = "main"

    def __post_init__(self) -> None:
        if not isinstance(self.block_id, str) or not self.block_id.strip():
            raise ValueError("block_id must not be empty")
        if not isinstance(self.text, str):
            raise TypeError("text must be a string")
        runs = tuple(self.runs or ())
        if any(not isinstance(run, str) for run in runs):
            raise TypeError("runs must contain only strings")
        object.__setattr__(self, "runs", runs)
        if runs and self.text and self.text != "".join(runs):
            raise ValueError("text and runs describe different block content")
        if not isinstance(self.surface, str) or not self.surface.strip():
            raise ValueError("surface must not be empty")
        if not isinstance(self.story_id, str) or not self.story_id.strip():
            raise ValueError("story_id must not be empty")

    @property
    def combined_text(self) -> str:
        return "".join(self.runs) if self.runs else self.text

    @classmethod
    def from_runs(
        cls,
        block_id: str,
        runs: Sequence[str],
        *,
        surface: str = "body",
        story_id: str = "main",
    ) -> "TokenTextBlock":
        return cls(block_id=block_id, runs=tuple(runs), surface=surface, story_id=story_id)


@dataclass(frozen=True, slots=True)
class TokenDeclaration:
    token: str
    kind: MaterialTokenKind
    declaration_id: str = ""
    required: bool = True
    occurrence_policy: TokenOccurrencePolicy = TokenOccurrencePolicy.EXACTLY_ONE
    producer: MaterialTokenProducer | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "token", normalize_material_token(self.token))
        _coerce_enum_field(self, "kind", MaterialTokenKind)
        _coerce_enum_field(self, "occurrence_policy", TokenOccurrencePolicy)
        ref = parse_material_token(self.token)
        ref.validate_kind(self.kind)
        object.__setattr__(self, "producer", ref.validate_producer(self.producer))
        if not isinstance(self.required, bool):
            raise TypeError("required must be a boolean")


@dataclass(frozen=True, slots=True)
class MaterialTokenOccurrence:
    occurrence_id: str
    token: str
    key: str
    identifier: str
    namespace: MaterialTokenNamespace
    kind: MaterialTokenKind
    block_id: str
    surface: str
    story_id: str
    block_index: int
    start: int
    end: int
    start_run_index: int | None
    end_run_index: int | None
    ordinal: int
    token_ordinal: int
    consumer_id: str = ""
    router_occurrence_id: str = ""


@dataclass(frozen=True, slots=True)
class MaterialTokenRoute:
    token: str
    key: str
    identifier: str
    namespace: MaterialTokenNamespace
    kind: MaterialTokenKind
    producer: MaterialTokenProducer
    occurrences: tuple[MaterialTokenOccurrence, ...]
    declaration_ids: tuple[str, ...] = ()
    required: bool = False
    occurrence_policy: TokenOccurrencePolicy = TokenOccurrencePolicy.ALL

    @property
    def occurrence_count(self) -> int:
        return len(self.occurrences)


@dataclass(frozen=True, slots=True)
class TokenRoutingDiagnostic:
    code: TokenDiagnosticCode
    severity: TokenDiagnosticSeverity
    message: str
    token: str = ""
    kind: MaterialTokenKind | None = None
    declaration_ids: tuple[str, ...] = ()
    occurrence_ids: tuple[str, ...] = ()
    block_id: str = ""


@dataclass(frozen=True, slots=True)
class TokenRoutingResult:
    blocks: tuple[TokenTextBlock, ...]
    routes: tuple[MaterialTokenRoute, ...]
    occurrences: tuple[MaterialTokenOccurrence, ...]
    diagnostics: tuple[TokenRoutingDiagnostic, ...]
    consumer_id: str = ""

    @property
    def ok(self) -> bool:
        return not any(
            item.severity is TokenDiagnosticSeverity.ERROR for item in self.diagnostics
        )

    @property
    def field_occurrences(self) -> tuple[MaterialTokenOccurrence, ...]:
        return self._occurrences_of(MaterialTokenKind.FIELD)

    @property
    def image_occurrences(self) -> tuple[MaterialTokenOccurrence, ...]:
        return self._occurrences_of(MaterialTokenKind.IMAGE)

    @property
    def content_occurrences(self) -> tuple[MaterialTokenOccurrence, ...]:
        return self._occurrences_of(MaterialTokenKind.CONTENT)

    @property
    def attachment_occurrences(self) -> tuple[MaterialTokenOccurrence, ...]:
        return self._occurrences_of(MaterialTokenKind.ATTACHMENT)

    def route_for(self, token_or_key: str) -> MaterialTokenRoute | None:
        try:
            token = normalize_material_token(token_or_key)
        except (TypeError, ValueError):
            return None
        return next((route for route in self.routes if route.token == token), None)

    def occurrence_count(self, token_or_key: str) -> int:
        route = self.route_for(token_or_key)
        return route.occurrence_count if route else 0

    def _occurrences_of(
        self, kind: MaterialTokenKind
    ) -> tuple[MaterialTokenOccurrence, ...]:
        return tuple(item for item in self.occurrences if item.kind is kind)


TextBlockInput = TokenTextBlock | str | Sequence[str]


def route_material_tokens(
    text_blocks: Sequence[TextBlockInput],
    *,
    image_tokens: Iterable[str | TokenDeclaration] | Mapping[str, object] = (),
    content_tokens: Iterable[str | TokenDeclaration] | Mapping[str, object] = (),
    attachment_tokens: Iterable[str | TokenDeclaration] | Mapping[str, object] = (),
    content_rules: Iterable[object] = (),
    attachment_rules: Iterable[object] = (),
    consumer_id: str = "",
) -> TokenRoutingResult:
    """Classify actual occurrences and validate configured declarations.

    ``content_rules`` accepts the public ``ContentInsertionRule`` contract or
    mapping/object equivalents exposing ``anchor_token``, ``rule_id``,
    ``required``, and ``occurrence_policy``. This keeps the router independent
    from persistence modules while allowing all surfaces to consume one result.
    """

    if not isinstance(consumer_id, str):
        raise TypeError("consumer_id must be a string")
    consumer_id = consumer_id.strip()
    blocks = tuple(_normalize_text_block(item, index) for index, item in enumerate(text_blocks))
    diagnostics: list[TokenRoutingDiagnostic] = []
    declarations: list[TokenDeclaration] = []
    declarations.extend(
        _materialize_declarations(
            image_tokens, MaterialTokenKind.IMAGE, "image", diagnostics
        )
    )
    declarations.extend(
        _materialize_declarations(
            content_tokens, MaterialTokenKind.CONTENT, "content", diagnostics
        )
    )
    declarations.extend(
        _materialize_declarations(
            attachment_tokens,
            MaterialTokenKind.ATTACHMENT,
            "attachment",
            diagnostics,
        )
    )
    declarations.extend(
        _declarations_from_rules(
            content_rules, MaterialTokenKind.CONTENT, "content", diagnostics
        )
    )
    declarations.extend(
        _declarations_from_rules(
            attachment_rules,
            MaterialTokenKind.ATTACHMENT,
            "attachment",
            diagnostics,
        )
    )

    declared_by_token: dict[str, list[TokenDeclaration]] = {}
    for declaration in declarations:
        declared_by_token.setdefault(declaration.token, []).append(declaration)

    for token, token_declarations in declared_by_token.items():
        kinds = {item.kind for item in token_declarations}
        if len(kinds) > 1:
            diagnostics.append(
                _diagnostic(
                    TokenDiagnosticCode.TYPE_CONFLICT,
                    f"{token} is declared as incompatible material types",
                    token=token,
                    declaration_ids=_declaration_ids(token_declarations),
                )
            )
        groups: dict[MaterialTokenKind, list[TokenDeclaration]] = {}
        for item in token_declarations:
            groups.setdefault(item.kind, []).append(item)
        for kind, same_kind in groups.items():
            if len(same_kind) > 1:
                diagnostics.append(
                    _diagnostic(
                        TokenDiagnosticCode.DUPLICATE_DECLARATION,
                        f"{token} has {len(same_kind)} {kind.value} declarations",
                        token=token,
                        kind=kind,
                        declaration_ids=_declaration_ids(same_kind),
                    )
                )

    occurrence_specs: list[
        tuple[
            str,
            str,
            str,
            MaterialTokenNamespace,
            MaterialTokenKind,
            TokenTextBlock,
            int,
            int,
            int,
            int | None,
            int | None,
        ]
    ] = []
    seen_token_order: list[str] = []
    token_counts: dict[str, int] = {}
    for block_index, block in enumerate(blocks):
        text = block.combined_text
        for match in MATERIAL_TOKEN_PATTERN.finditer(text):
            raw_key = match.group(1)
            key = raw_key.strip()
            if not key or raw_key != key:
                diagnostics.append(
                    _diagnostic(
                        TokenDiagnosticCode.INVALID_TOKEN,
                        f"invalid token syntax {match.group(0)!r}",
                        token=match.group(0),
                        block_id=block.block_id,
                    )
                )
                continue
            # Visibility/control markers share braces but are not materials.
            if key.startswith("#"):
                continue
            try:
                ref = parse_material_token(match.group(0))
            except (TypeError, ValueError) as exc:
                diagnostics.append(
                    _diagnostic(
                        TokenDiagnosticCode.INVALID_TOKEN,
                        str(exc),
                        token=match.group(0),
                        block_id=block.block_id,
                    )
                )
                continue
            token = ref.token
            key = ref.key
            kind = ref.kind
            if token not in token_counts:
                seen_token_order.append(token)
                token_counts[token] = 0
            token_counts[token] += 1
            start_run, end_run = _run_span(block, match.start(), match.end())
            occurrence_specs.append(
                (
                    token,
                    key,
                    ref.identifier,
                    ref.namespace,
                    kind,
                    block,
                    block_index,
                    match.start(),
                    match.end(),
                    start_run,
                    end_run,
                )
            )

    occurrences: list[MaterialTokenOccurrence] = []
    per_token_ordinal: dict[str, int] = {}
    for ordinal, spec in enumerate(occurrence_specs, start=1):
        (
            token,
            key,
            identifier,
            namespace,
            kind,
            block,
            block_index,
            start,
            end,
            start_run,
            end_run,
        ) = spec
        per_token_ordinal[token] = per_token_ordinal.get(token, 0) + 1
        token_ordinal = per_token_ordinal[token]
        identity = "\x1f".join(
            (
                block.story_id,
                block.surface,
                block.block_id,
                str(start),
                str(end),
                token,
                str(token_ordinal),
            )
        )
        router_occurrence_id = (
            "tokocc-" + sha256(identity.encode("utf-8")).hexdigest()[:20]
        )
        occurrence_id = (
            "tokocc-"
            + sha256(
                f"{consumer_id}\x1f{router_occurrence_id}".encode("utf-8")
            ).hexdigest()[:20]
            if consumer_id
            else router_occurrence_id
        )
        occurrences.append(
            MaterialTokenOccurrence(
                occurrence_id=occurrence_id,
                token=token,
                key=key,
                identifier=identifier,
                namespace=namespace,
                kind=kind,
                block_id=block.block_id,
                surface=block.surface,
                story_id=block.story_id,
                block_index=block_index,
                start=start,
                end=end,
                start_run_index=start_run,
                end_run_index=end_run,
                ordinal=ordinal,
                token_ordinal=token_ordinal,
                consumer_id=consumer_id,
                router_occurrence_id=router_occurrence_id,
            )
        )

    all_token_order = list(seen_token_order)
    for declaration in declarations:
        if declaration.token not in all_token_order:
            all_token_order.append(declaration.token)
    occurrences_by_token: dict[str, list[MaterialTokenOccurrence]] = {}
    for occurrence in occurrences:
        occurrences_by_token.setdefault(occurrence.token, []).append(occurrence)

    routes: list[MaterialTokenRoute] = []
    for token in all_token_order:
        token_occurrences = tuple(occurrences_by_token.get(token, ()))
        token_declarations = declared_by_token.get(token, [])
        ref = parse_material_token(token)
        key = ref.key
        observed_kind = token_occurrences[0].kind if token_occurrences else None
        declared_kind = token_declarations[0].kind if token_declarations else None
        kind = observed_kind or declared_kind or ref.kind
        same_kind = [item for item in token_declarations if item.kind is kind]
        required = any(item.required for item in same_kind)
        policies = {item.occurrence_policy for item in same_kind}
        occurrence_policy = (
            TokenOccurrencePolicy.EXACTLY_ONE
            if TokenOccurrencePolicy.EXACTLY_ONE in policies
            else TokenOccurrencePolicy.ALL
        )
        declaration_ids = _declaration_ids(same_kind)
        producer = same_kind[0].producer if same_kind else ref.default_producer
        route = MaterialTokenRoute(
            token=token,
            key=key,
            identifier=ref.identifier,
            namespace=ref.namespace,
            kind=kind,
            producer=producer,
            occurrences=token_occurrences,
            declaration_ids=declaration_ids,
            required=required,
            occurrence_policy=occurrence_policy,
        )
        routes.append(route)
        if ref.spec.requires_declaration and not same_kind and token_occurrences:
            diagnostics.append(
                _diagnostic(
                    TokenDiagnosticCode.MISSING_DECLARATION,
                    f"{token} has no {kind.value} declaration",
                    token=token,
                    kind=kind,
                    occurrence_ids=tuple(item.occurrence_id for item in token_occurrences),
                )
            )
        if required and not token_occurrences:
            diagnostics.append(
                _diagnostic(
                    TokenDiagnosticCode.MISSING_OCCURRENCE,
                    f"required {kind.value} token {token} is missing",
                    token=token,
                    kind=kind,
                    declaration_ids=declaration_ids,
                )
            )
        if (
            occurrence_policy is TokenOccurrencePolicy.EXACTLY_ONE
            and len(token_occurrences) > 1
        ):
            diagnostics.append(
                _diagnostic(
                    TokenDiagnosticCode.DUPLICATE_OCCURRENCE,
                    f"{token} occurs {len(token_occurrences)} times but requires exactly one",
                    token=token,
                    kind=kind,
                    declaration_ids=declaration_ids,
                    occurrence_ids=tuple(item.occurrence_id for item in token_occurrences),
                )
            )

    return TokenRoutingResult(
        blocks=blocks,
        routes=tuple(routes),
        occurrences=tuple(occurrences),
        diagnostics=tuple(diagnostics),
        consumer_id=consumer_id,
    )


def token_key(token_or_key: str) -> str:
    return material_token_key(token_or_key)


def token_identifier(token_or_key: str) -> str:
    return material_token_identifier(token_or_key)


def _normalize_text_block(item: TextBlockInput, index: int) -> TokenTextBlock:
    if isinstance(item, TokenTextBlock):
        return item
    if isinstance(item, str):
        return TokenTextBlock(block_id=f"block-{index:06d}", text=item)
    if isinstance(item, Sequence) and not isinstance(item, (bytes, bytearray)):
        return TokenTextBlock.from_runs(f"block-{index:06d}", tuple(item))
    raise TypeError("text blocks must be strings, run sequences, or TokenTextBlock values")


def _materialize_declarations(
    values: Iterable[str | TokenDeclaration] | Mapping[str, object],
    kind: MaterialTokenKind,
    id_prefix: str,
    diagnostics: list[TokenRoutingDiagnostic],
) -> list[TokenDeclaration]:
    raw_values = values.keys() if isinstance(values, Mapping) else values
    result: list[TokenDeclaration] = []
    for index, raw in enumerate(raw_values):
        try:
            if isinstance(raw, TokenDeclaration):
                declaration = raw
                if declaration.kind is not kind:
                    raise ValueError(
                        f"expected a {kind.value} declaration, got {declaration.kind.value}"
                    )
            else:
                declaration = TokenDeclaration(
                    token=str(raw),
                    kind=kind,
                    declaration_id=f"{id_prefix}-{index + 1}",
                )
            parse_material_token(declaration.token).validate_kind(kind)
            result.append(declaration)
        except (TypeError, ValueError) as exc:
            diagnostics.append(
                _diagnostic(
                    TokenDiagnosticCode.INVALID_TOKEN,
                    str(exc),
                    token=str(getattr(raw, "token", raw) or ""),
                    kind=kind,
                )
            )
    return result


def _declarations_from_rules(
    rules: Iterable[object],
    kind: MaterialTokenKind,
    id_prefix: str,
    diagnostics: list[TokenRoutingDiagnostic],
) -> list[TokenDeclaration]:
    result: list[TokenDeclaration] = []
    for index, rule in enumerate(rules):
        getter = rule.get if isinstance(rule, Mapping) else lambda name, default=None: getattr(
            rule, name, default
        )
        raw_token = getter("anchor_token", "")
        try:
            declaration = TokenDeclaration(
                token=str(raw_token or ""),
                kind=kind,
                declaration_id=str(
                    getter("rule_id", "") or f"{id_prefix}-rule-{index + 1}"
                ),
                required=bool(
                    getter(
                        "token_required",
                        getter("required", True),
                    )
                ),
                occurrence_policy=getter("occurrence_policy", "exactly_one")
                or "exactly_one",
            )
            result.append(declaration)
        except (TypeError, ValueError) as exc:
            diagnostics.append(
                _diagnostic(
                    TokenDiagnosticCode.INVALID_TOKEN,
                    str(exc),
                    token=str(raw_token or ""),
                    kind=kind,
                    declaration_ids=(str(getter("rule_id", "") or ""),),
                )
            )
    return result


def _run_span(
    block: TokenTextBlock, start: int, end: int
) -> tuple[int | None, int | None]:
    if not block.runs:
        return None, None
    cursor = 0
    start_run = None
    end_run = None
    for index, run in enumerate(block.runs):
        run_end = cursor + len(run)
        if start_run is None and start < run_end:
            start_run = index
        if end > cursor and end <= run_end:
            end_run = index
            break
        cursor = run_end
    return start_run, end_run


def _declaration_ids(values: Sequence[TokenDeclaration]) -> tuple[str, ...]:
    return tuple(item.declaration_id for item in values if item.declaration_id)


def _diagnostic(
    code: TokenDiagnosticCode,
    message: str,
    *,
    token: str = "",
    kind: MaterialTokenKind | None = None,
    declaration_ids: tuple[str, ...] = (),
    occurrence_ids: tuple[str, ...] = (),
    block_id: str = "",
) -> TokenRoutingDiagnostic:
    return TokenRoutingDiagnostic(
        code=code,
        severity=TokenDiagnosticSeverity.ERROR,
        message=message,
        token=token,
        kind=kind,
        declaration_ids=declaration_ids,
        occurrence_ids=occurrence_ids,
        block_id=block_id,
    )


EnumType = TypeVar("EnumType", bound=Enum)


def _coerce_enum_field(instance: object, name: str, enum_type: type[EnumType]) -> None:
    raw_value = getattr(instance, name)
    serialized = raw_value.value if isinstance(raw_value, Enum) else str(raw_value)
    try:
        value = raw_value if isinstance(raw_value, enum_type) else enum_type(serialized)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{name} must be one of: {allowed}") from exc
    object.__setattr__(instance, name, value)


__all__ = [
    "MATERIAL_TOKEN_PATTERN",
    "MaterialTokenKind",
    "MaterialTokenOccurrence",
    "MaterialTokenRoute",
    "TokenDeclaration",
    "TokenDiagnosticCode",
    "TokenDiagnosticSeverity",
    "TokenOccurrencePolicy",
    "TokenRoutingDiagnostic",
    "TokenRoutingResult",
    "TokenTextBlock",
    "normalize_material_token",
    "route_material_tokens",
    "token_key",
    "token_identifier",
]
