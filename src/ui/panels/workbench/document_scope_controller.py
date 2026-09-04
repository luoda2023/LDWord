"""Coordinate current-document structure scanning and scope review."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

from src.config.document_scope import coerce_document_scope_policy
from src.services.document_structure_evidence import (
    DocumentStructureEvidence,
    RegionDecision,
    document_structure_evidence_is_current,
    pending_document_structure_review_roles,
)
from src.qt_api import QWidget

from .document_scope_review import (
    DocumentScopeReviewDialog,
    DocumentStructureScanHandle,
)


class WorkbenchDocumentScopeController:
    """Own the imported document's scan, corrections, status, and gate."""

    def __init__(
        self,
        *,
        parent: QWidget,
        source_path: Callable[[], str],
        mode_id: Callable[[], str],
        scene: Callable[[], object],
        status_detail,
    ) -> None:
        self._parent = parent
        self._source_path = source_path
        self._mode_id = mode_id
        self._scene = scene
        self._status_detail = status_detail
        self._evidence: DocumentStructureEvidence | None = None
        self._decisions: tuple[RegionDecision, ...] = ()
        self._scan_request_id = ""
        self._scan_source_path = ""
        self._scans: dict[str, DocumentStructureScanHandle] = {}

    @property
    def evidence(self) -> DocumentStructureEvidence | None:
        return self._evidence

    @property
    def decisions(self) -> tuple[RegionDecision, ...]:
        return self._decisions

    def reset_decisions(self) -> None:
        self._decisions = ()

    def shutdown(self, timeout_ms: int = 1000) -> bool:
        scans = tuple(self._scans.values())
        if not scans:
            return True
        per_scan_timeout = max(1, int(timeout_ms) // len(scans))
        results = tuple(scan.shutdown(per_scan_timeout) for scan in scans)
        return all(results)

    def clear(self) -> None:
        self._scan_request_id = uuid4().hex
        self._scan_source_path = ""
        self._evidence = None
        self._decisions = ()
        self._status_detail.set_document_scope_status("idle")

    def start_scan(self, source_path: str, *, force: bool = False) -> None:
        cleaned = str(source_path or "").strip()
        if not self._is_applicable(cleaned):
            self.clear()
            return
        if (
            self._scan_source_path == cleaned
            and self._scan_request_id in self._scans
        ):
            return
        if (
            not force
            and isinstance(self._evidence, DocumentStructureEvidence)
            and document_structure_evidence_is_current(self._evidence, cleaned)
        ):
            self.refresh_status()
            return

        request_id = uuid4().hex
        self._scan_request_id = request_id
        self._scan_source_path = cleaned
        self._evidence = None
        self._decisions = ()
        self._status_detail.set_document_scope_status("scanning")
        scan = DocumentStructureScanHandle(
            request_id,
            cleaned,
            parent=self._parent,
        )
        self._scans[request_id] = scan
        scan.finished.connect(self._on_scanned)
        scan.start()

    def refresh_status(self) -> None:
        source_path = self._source_path() or ""
        if not self._is_applicable(source_path):
            self._status_detail.set_document_scope_status("idle")
            return
        evidence = self._evidence
        if not isinstance(evidence, DocumentStructureEvidence):
            state = "scanning" if self._scan_source_path else "failed"
            self._status_detail.set_document_scope_status(state)
            return
        if (
            not document_structure_evidence_is_current(evidence, source_path)
            or not evidence.ready
        ):
            self._status_detail.set_document_scope_status("failed")
            return

        pending = pending_document_structure_review_roles(
            evidence,
            self._decisions,
            included_roles=self._included_roles(),
        )
        if pending:
            self._status_detail.set_document_scope_status(
                "review",
                count=len(pending),
            )
            return
        effective_roles = self._effective_roles(evidence)
        if not effective_roles:
            self._status_detail.set_document_scope_status("review", count=1)
            return
        self._status_detail.set_document_scope_status(
            "ready",
            count=len(effective_roles),
        )

    def recheck(self) -> None:
        source_path = self._source_path() or ""
        if not self._is_applicable(source_path):
            self._status_detail.set_document_scope_status("idle")
            return
        if (
            isinstance(self._evidence, DocumentStructureEvidence)
            and document_structure_evidence_is_current(
                self._evidence,
                source_path,
            )
        ):
            self.refresh_status()
            return
        self.start_scan(source_path)

    def review(self) -> bool:
        source_path = self._source_path() or ""
        if not self._is_applicable(source_path):
            return True
        evidence = self._evidence
        if (
            isinstance(evidence, DocumentStructureEvidence)
            and evidence.source_path == source_path
            and not evidence.ready
        ):
            self._build_dialog(evidence, source_path).exec()
            return False
        if (
            not isinstance(evidence, DocumentStructureEvidence)
            or not document_structure_evidence_is_current(evidence, source_path)
        ):
            self.start_scan(source_path, force=True)
            return False

        dialog = self._build_dialog(
            evidence,
            source_path,
            existing_decisions=self._decisions,
        )
        if not dialog.exec() or not evidence.ready:
            return False
        self._decisions = dialog.decisions()
        self.refresh_status()
        return (
            not pending_document_structure_review_roles(
                evidence,
                self._decisions,
                included_roles=self._included_roles(),
            )
            and bool(self._effective_roles(evidence))
        )

    def ensure_confirmed(self) -> bool:
        source_path = self._source_path() or ""
        if not self._is_applicable(source_path):
            return True
        evidence = self._evidence
        if (
            isinstance(evidence, DocumentStructureEvidence)
            and evidence.source_path == source_path
            and not evidence.ready
        ):
            self.review()
            return False
        if (
            not isinstance(evidence, DocumentStructureEvidence)
            or not document_structure_evidence_is_current(evidence, source_path)
        ):
            self.start_scan(source_path, force=True)
            return False
        if not evidence.ready:
            self.review()
            return False
        if pending_document_structure_review_roles(
            evidence,
            self._decisions,
            included_roles=self._included_roles(),
        ):
            return self.review()
        if not self._effective_roles(evidence):
            return self.review()
        return True

    def _on_scanned(self, request_id: str, evidence: object) -> None:
        self._scans.pop(str(request_id or ""), None)
        if request_id != self._scan_request_id:
            return
        self._scan_source_path = ""
        self._evidence = (
            evidence
            if isinstance(evidence, DocumentStructureEvidence)
            else None
        )
        self._decisions = ()
        self.refresh_status()

    def _is_applicable(self, source_path: str) -> bool:
        if self._mode_id() in {"official", "exam"}:
            return False
        return str(source_path or "").strip().lower().endswith(".docx")

    def _included_roles(self) -> tuple[str, ...]:
        policy = coerce_document_scope_policy(
            getattr(self._scene(), "document_scope", None)
        )
        return policy.included_roles(self._mode_id())

    def _effective_roles(
        self,
        evidence: DocumentStructureEvidence,
    ) -> set[str]:
        included = set(self._included_roles())
        excluded = {
            decision.role_id
            for decision in self._decisions
            if decision.action == "exclude"
        }
        roles = {
            region.role_id
            for region in evidence.regions
            if region.role_id in included and region.role_id not in excluded
        }
        roles.update(
            decision.role_id
            for decision in self._decisions
            if decision.action == "set_start"
            and decision.role_id in included
        )
        return roles

    def _build_dialog(
        self,
        evidence: DocumentStructureEvidence,
        source_path: str,
        *,
        existing_decisions: tuple[RegionDecision, ...] = (),
    ) -> DocumentScopeReviewDialog:
        return DocumentScopeReviewDialog(
            evidence,
            source_path=source_path,
            policy=getattr(self._scene(), "document_scope", None),
            mode_id=self._mode_id(),
            existing_decisions=existing_decisions,
            parent=self._parent,
        )


__all__ = ["WorkbenchDocumentScopeController"]
