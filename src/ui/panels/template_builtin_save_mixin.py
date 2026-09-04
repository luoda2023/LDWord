"""Save built-in template drafts as owned user resources."""

from __future__ import annotations

from src.config.library import template_user_target_path
from src.shared.ui import Toast
from src.ui.template_close_transaction import TemplateSaveCancelled


class TemplateBuiltinSaveMixin:
    """Own the built-in-to-user template save transaction."""

    def _save_builtin_template_as_user_copy(self) -> bool:
        name = self._template_text_request(
            "保存模板副本",
            "内置模板不可覆盖，请为用户副本命名：",
            placeholder="用户模板名称",
            default=self._unique_template_copy_name(),
            ok_text="保存副本",
            parent=self,
        )
        if name is None:
            self._set_template_management_status("ℹ 已取消保存，草稿仍保留")
            return False
        name = name.strip()
        if not name:
            Toast.show_warning("模板名称不能为空")
            return False

        template_id = self._template_library_controller.unique_template_id(
            mode_id=self._current_work_mode_id(),
            name=name,
        )
        target = template_user_target_path(
            template_id,
            mode_id=self._current_work_mode_id(),
        )
        self._current_template.name = name
        self._edit_session.replace_draft(self._current_template)
        try:
            context, saved = self._persist_draft_context(
                self._draft_context,
                target,
                confirm_shared=False,
            )
            context = self._draft_store.rekey(
                context,
                mode_id=context.mode_id,
                template_id=template_id,
                path=saved,
                source="library",
                source_type="user",
            )
            success_text = f"✅ 已保存用户模板: {saved.name}"
            self._set_template_management_status(success_text)
            self._finalize_saved_template_contexts((context,))
            Toast.show_success(f"已保存用户模板: {name}")
            return True
        except TemplateSaveCancelled:
            self._set_template_management_status("ℹ 已取消保存，草稿仍保留")
            return False
        except Exception as exc:
            message = f"❌ 保存失败: {exc}"
            self._set_template_management_status(message)
            Toast.show_error(f"保存失败: {exc}")
            return False


__all__ = ["TemplateBuiltinSaveMixin"]
