"""Template draft-session activation, persistence, and publication."""

from __future__ import annotations

from pathlib import Path

from src.config.library import (
    ConfigDependencyResolutionError,
)
from src.config.template import TemplateConfig
from src.shared.ui import Toast
from src.ui.template_close_transaction import TemplateSaveCancelled
from src.ui.template_draft_save_coordinator import (
    OVERWRITE_EXISTING_TARGET,
    PreparedTemplateSave,
    TemplateSavePreparationCancelled,
    TemplateSaveRevisionChanged,
)
from src.ui.template_edit_session import TemplateDraftContext


class TemplateSessionPersistenceMixin:
    """Own draft synchronization, activation, save, and publication.

    The host panel supplies template-library selection, detail projection,
    management-status, and work-mode hooks. Close snapshots and prepared-close
    state remain owned by ``TemplateCloseTransaction``.
    """

    def _discard_all_pending_template_edits(self) -> None:
        self._draft_store.discard_all()
        self._sync_bridge_draft_protections()
        self._current_template = self._edit_session.draft
        self._set_detail_templates(self._current_template)
        self._capture_detail_snapshots()
        self._set_detail_save_enabled(False)
        self.bridge.clear_template_dirty()
        self._refresh_template_selector_options()
        self._sync_template_file_status()
        self._refresh_overview_projection(
            reason="all_template_drafts_discarded"
        )

    def _finalize_saved_template_contexts(
        self,
        contexts: tuple[TemplateDraftContext, ...],
    ) -> None:
        for context in contexts:
            if context is self._draft_context:
                self._bind_saved_current_context(context)
        self._sync_bridge_draft_protections()
        self.bridge.clear_template_dirty()
        self._refresh_template_selector_options()
        self._sync_template_file_status()
        self._publish_current_template()
        self._capture_detail_snapshots()
        self._set_detail_save_enabled(False)

    def _capture_detail_snapshots(self) -> None:
        for detail in self._parameter_details():
            if hasattr(detail, "capture_entry_snapshot"):
                detail.capture_entry_snapshot()

    def _compute_dirty_against_persisted_snapshot(self) -> bool:
        if self._current_template is None:
            return False
        self._current_template = self._edit_session.replace_draft(
            self._current_template
        )
        return self._edit_session.is_dirty()

    def _sync_template_dirty_state(self) -> bool:
        dirty = self._compute_dirty_against_persisted_snapshot()
        self._sync_bridge_draft_protections()
        if dirty:
            self.bridge.mark_template_dirty()
        else:
            self.bridge.clear_template_dirty()
        self._set_detail_save_enabled(dirty)
        return dirty

    def _sync_bridge_draft_protections(self) -> None:
        self.bridge.replace_protected_template_commits(
            [
                (
                    context.mode_id,
                    context.template_id,
                    context.path,
                    context.session.committed_copy(),
                )
                for context in self._draft_store.dirty_contexts()
            ]
        )

    def _can_save_in_place(self) -> bool:
        if self._current_template_is_builtin():
            return False
        path = str(self._current_template_path or "").strip()
        if not path:
            return False
        target = Path(path)
        return (
            target.suffix.lower() in {".json", ".yaml", ".yml"}
            and not target.is_dir()
        )

    def _publish_current_template(
        self,
        *,
        emit_signal: bool = True,
    ) -> None:
        if self._current_template is None:
            return
        self._publishing_template = True
        try:
            self.bridge.set_current_template(
                self._edit_session.committed_copy(),
                config_id=self._current_template_id,
                path=self._current_template_path,
                source=self._current_template_source,
                source_type=self._current_template_source_type,
                emit_signal=emit_signal,
                allow_dirty_same_identity_replace=True,
            )
        finally:
            self._publishing_template = False

    def _confirm_template_save_overwrite(
        self,
        reason: str,
        target: Path,
    ) -> bool:
        if reason == OVERWRITE_EXISTING_TARGET:
            return self._template_persistence_confirm(
                "保存目标已经存在",
                f"目标文件 {target.name} 已存在。继续会覆盖该文件，是否继续？",
                confirm_text="覆盖并保存",
                parent=self,
            )
        return self._template_persistence_confirm(
            "模板文件已被外部修改",
            "模板文件在本次编辑期间发生了变化。"
            "继续保存会覆盖外部修改，是否仍然覆盖？",
            confirm_text="仍然覆盖",
            parent=self,
        )

    def _prepare_draft_context_saves(
        self,
        contexts: tuple[TemplateDraftContext, ...],
        *,
        confirm_shared: bool,
        path: str | Path | None = None,
    ) -> tuple[PreparedTemplateSave, ...]:
        try:
            plans = self._draft_save_coordinator.prepare(
                contexts,
                path=path,
            )
        except TemplateSavePreparationCancelled as exc:
            raise TemplateSaveCancelled from exc
        if confirm_shared:
            for plan in plans:
                if not self._confirm_shared_template_write_for_context(
                    plan.context,
                    target=plan.target,
                    template_id=plan.template_id,
                    mode_id=plan.context.mode_id,
                ):
                    raise TemplateSaveCancelled
        return plans

    def _execute_prepared_template_saves(
        self,
        plans: tuple[PreparedTemplateSave, ...],
    ) -> tuple[TemplateDraftContext, ...]:
        try:
            return self._draft_save_coordinator.commit(plans)
        except TemplateSaveRevisionChanged as exc:
            raise TemplateSaveCancelled from exc

    def _persist_draft_context(
        self,
        context: TemplateDraftContext,
        path: str | Path | None = None,
        *,
        confirm_shared: bool = False,
    ) -> tuple[TemplateDraftContext, Path]:
        plans = self._prepare_draft_context_saves(
            (context,),
            confirm_shared=confirm_shared,
            path=path,
        )
        updated = self._execute_prepared_template_saves(plans)[0]
        return updated, plans[0].target

    def _bind_saved_current_context(
        self,
        context: TemplateDraftContext,
    ) -> None:
        self._draft_context = context
        self._edit_session = context.session
        self._current_template = context.session.draft
        self._current_template_id = context.template_id
        self._current_template_path = context.path
        self._current_template_source = context.source
        self._current_template_source_type = context.source_type

    def _write_current_template_to_path(
        self,
        path: str | Path | None,
        *,
        success_message: str,
    ) -> bool:
        if self._current_template is None:
            return False

        try:
            context, saved = self._persist_draft_context(
                self._draft_context,
                path,
                confirm_shared=True,
            )
            success_text = success_message.format(name=saved.name)
            self._set_template_management_status(success_text)
            self._finalize_saved_template_contexts((context,))
            Toast.show_success(success_text.replace("✅ ", ""))
            return True
        except TemplateSaveCancelled:
            self._set_template_management_status(
                "ℹ 已取消保存，草稿仍保留"
            )
            return False
        except Exception as exc:
            message = f"❌ 保存失败: {exc}"
            self._set_template_management_status(message)
            Toast.show_error(f"保存失败: {exc}")
            return False

    def _load_template_for_selector(
        self,
        template_id: str,
    ) -> tuple[TemplateConfig, str, str]:
        selection = self._template_library_controller.load_selection(
            mode_id=self._current_work_mode_id(),
            template_id=template_id,
            current_template_id=self._current_template_id,
            current_template=self._current_template,
            current_path=self._current_template_path,
            current_source=self._current_template_source,
        )
        return selection.template, selection.path, selection.source

    def _unique_template_copy_name(self) -> str:
        return self._template_library_controller.unique_copy_name(
            mode_id=self._current_work_mode_id(),
            current_name=str(
                getattr(self._current_template, "name", "")
                or "自定义模板"
            ),
        )

    def _create_template_copy(
        self,
        name: str,
        *,
        action_label: str,
    ) -> bool:
        try:
            selection = self._template_library_controller.create_copy(
                mode_id=self._current_work_mode_id(),
                source_template=self._current_template,
                name=name,
            )
        except Exception as exc:
            message = f"{action_label}失败: {exc}"
            self._set_template_management_status(f"❌ {message}")
            Toast.show_error(message)
            return False

        self._activate_template(
            selection.template,
            template_id=selection.template_id,
            path=selection.path,
            source=selection.source,
            source_type=selection.source_type,
            status=f"✅ 已{action_label}: {Path(selection.path).name}",
        )
        Toast.show_success(f"已{action_label}: {name}")
        return True

    def _activate_template(
        self,
        template: TemplateConfig,
        *,
        template_id: str,
        path: str = "",
        source: str = "",
        source_type: str | None = None,
        status: str = "",
        replace_cached: bool = False,
        publish: bool = True,
    ) -> None:
        explicit_source_type = str(source_type or "").strip()
        resolved_source_type = (
            self._template_source_type_for_context(
                template_id=template_id,
                path=path,
                source=source,
            )
            if not explicit_source_type
            else explicit_source_type
        )
        context = self._draft_store.activate(
            template,
            mode_id=self._current_work_mode_id(),
            template_id=template_id,
            path=path,
            source=source,
            source_type=resolved_source_type,
            replace=replace_cached,
        )
        self._draft_context = context
        self._edit_session = context.session
        self._current_template_id = context.template_id
        self._current_template_path = context.path
        self._current_template_source = context.source
        self._current_template_source_type = context.source_type
        self._current_template = self._edit_session.draft
        self._refresh_template_selector_options()
        self._set_detail_templates(self._current_template)
        self._sync_template_file_status()
        self._set_template_management_status(status)
        active_dirty = self._edit_session.is_dirty()
        if active_dirty:
            self.bridge.mark_template_dirty()
        else:
            self.bridge.clear_template_dirty()
        self._sync_bridge_draft_protections()
        self._set_detail_save_enabled(active_dirty)
        self._refresh_overview_projection(reason="template_activated")
        if publish:
            self._publish_current_template()

    def _template_source_type_for_context(
        self,
        *,
        template_id: str,
        path: str,
        source: str,
    ) -> str:
        return self._template_library_controller.source_type_for_context(
            mode_id=self._current_work_mode_id(),
            template_id=template_id,
            path=path,
            source=source,
        )

    def _save_current_template(self) -> bool:
        if self._current_template is None:
            return False
        if self._current_template_is_builtin():
            return self._save_builtin_template_as_user_copy()
        target = self._current_template_path if self._can_save_in_place() else None
        return self._write_current_template_to_path(
            target,
            success_message="✅ 已保存: {name}",
        )

    def _confirm_shared_template_write_for_context(
        self,
        context: TemplateDraftContext,
        *,
        target: str | Path | None = None,
        template_id: str | None = None,
        mode_id: str | None = None,
    ) -> bool:
        # The authoritative ownership boundary is the resolved path, not the
        # mutable source/source_type labels carried by UI state. A path outside
        # the mode-scoped template library cannot be the shared resource
        # referenced by library plans, even when stale metadata says "library".
        effective_target = str(target or context.path or "").strip()
        if (
            not effective_target
            or not self._template_library_path_predicate(effective_target)
        ):
            return True
        effective_template_id = str(
            context.template_id if template_id is None else template_id
        ).strip()
        if not effective_template_id:
            return True
        effective_mode_id = str(
            context.mode_id if mode_id is None else mode_id
        ).strip()
        try:
            dependents = self._template_dependency_resolver(
                effective_template_id,
                mode_id=effective_mode_id,
            )
        except ConfigDependencyResolutionError as exc:
            message = f"无法核验共享模板影响，已阻止保存: {exc}"
            self._set_template_management_status(f"❌ {message}")
            Toast.show_error(message)
            return False
        if len(dependents) <= 1:
            return True
        labels = "、".join(
            str(item.name or item.config_id)
            for item in dependents[:5]
        )
        if len(dependents) > 5:
            labels += f"等 {len(dependents)} 个方案"
        return self._template_persistence_confirm(
            "保存共享模板",
            f"该模板被 {len(dependents)} 个方案共同引用：{labels}。"
            "保存后这些方案都会使用新版本，是否继续？",
            confirm_text="保存共享模板",
            parent=self,
        )
