"""Close-transaction and lazy-detail lifecycle for the template panel."""

from __future__ import annotations


class TemplateCloseLifecycleMixin:
    """Keep close coordination out of the template panel composition shell."""

    def _has_pending_template_edits(self) -> bool:
        return bool(self._edit_session.is_dirty())

    def request_leave_pending_changes(self, reason: str = "离开模板管理") -> bool:
        """Keep drafts in memory while ordinary application navigation continues."""

        del reason
        return True

    def pending_template_draft_count(self) -> int:
        return len(self._draft_store.dirty_contexts())

    def _prompt_close_template_draft_action(self, count: int) -> str:
        return self._close_prompt.ask(count)

    def prepare_close_pending_changes(self) -> bool:
        return self._close_transaction.prepare()

    def commit_close_pending_changes(self) -> bool:
        return self._close_transaction.commit()

    def rollback_close_pending_changes(self) -> bool:
        return self._close_transaction.rollback()

    def finalize_close_pending_changes(self) -> None:
        self._close_transaction.finalize()

    def cancel_prepared_close(self) -> None:
        self._close_transaction.cancel()

    def __getattr__(self, name: str):
        detail_attrs = self.__dict__.get("_detail_attr_names", {})
        card_id = detail_attrs.get(name)
        if card_id:
            return self._ensure_detail_loaded(card_id)
        raise AttributeError(f"{type(self).__name__} object has no attribute {name!r}")
