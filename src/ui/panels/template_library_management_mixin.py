"""Template-library status, watching, selection, and user actions."""

from __future__ import annotations

from pathlib import Path

from src.config.library import template_library_watch_dirs
from src.config.template_authoring_workspace import (
    ensure_template_authoring_workspace,
    template_authoring_workspace_path,
)
from src.qt_api import QDesktopServices, QUrl
from src.shared.ui import Toast


class TemplateLibraryManagementMixin:
    """Own template-library presentation, refresh, and management actions."""

    def _template_source_text(self) -> str:
        source = str(self._current_template_source or "").strip()
        path = str(self._current_template_path or "").strip()
        if source == "library" and path:
            return self._format_source_text("模板文件", path)
        if source == "file" and path:
            return self._format_source_text("本地文件", path)
        if source == "builtin":
            return self._format_source_text("模板类型", "内置模板")
        if path:
            return self._format_source_text("模板文件", path)
        return "未保存到模板文件"

    def _template_overview_status_text(self) -> str:
        source = str(self._current_template_source or "").strip()
        path = str(self._current_template_path or "").strip()
        if source == "file" and path:
            status = "本地文件"
        elif source == "library" and path:
            status = "模板文件"
        elif source == "builtin":
            status = "内置模板"
        elif path:
            status = "模板文件"
        else:
            status = "未保存"
        pending_count = self.pending_template_draft_count()
        if self._edit_session.is_dirty():
            return (
                f"{status} · 草稿预览（执行仍使用已保存版本）"
                f" · 暂存 {pending_count}"
            )
        if pending_count:
            return f"{status} · 暂存 {pending_count}"
        return status

    def _template_path_status_text(self) -> str:
        path = str(self._current_template_path or "").strip()
        if not path:
            return "保存位置：未保存到文件"
        parent = str(Path(path).parent)
        if parent in ("", "."):
            parent = "当前文件夹"
        return f"保存位置：{parent}"

    def _template_path_tooltip(self) -> str:
        path = str(self._current_template_path or "").strip()
        return path if path else "当前模板还没有保存到文件"

    def _current_template_path_obj(self) -> Path | None:
        path = str(self._current_template_path or "").strip()
        if not path:
            return None
        return Path(path)

    def _current_template_is_builtin(self) -> bool:
        return self._template_library_controller.is_builtin(
            mode_id=self._current_work_mode_id(),
            template_id=self._current_template_id,
            path=self._current_template_path,
            source=self._current_template_source,
            source_type=self._current_template_source_type,
        )

    def _current_template_manage_path(self) -> Path | None:
        return self._template_library_controller.manageable_path(
            path=self._current_template_path,
            source_type=self._current_template_source_type,
        )

    def _current_template_can_rename(self) -> bool:
        return (
            self._current_template is not None
            and not self._current_template_is_builtin()
            and self._current_template_manage_path() is not None
        )

    def _current_template_can_delete(self) -> bool:
        return (
            not self._current_template_is_builtin()
            and self._current_template_manage_path() is not None
        )

    def _template_authoring_workspace_folder(self) -> Path:
        return template_authoring_workspace_path(
            self._current_work_mode_id()
        )

    def _current_template_file_was_removed(self) -> bool:
        source = str(self._current_template_source or "").strip()
        if source not in {"library", "file"}:
            return False
        path = self._current_template_path_obj()
        return path is not None and not path.exists()

    def _current_template_should_stay_in_selector(self) -> bool:
        if self._current_template is None:
            return False
        path = self._current_template_path_obj()
        if path is not None:
            return path.exists()
        source = str(self._current_template_source or "").strip()
        return source not in {"library", "file"}

    def _template_library_watch_directories(self) -> list[str]:
        return [
            str(path)
            for path in template_library_watch_dirs(
                mode_id=self._current_work_mode_id()
            )
        ]

    def _setup_template_library_watcher(self) -> None:
        watcher = getattr(self, "_template_library_watcher", None)
        if watcher is None:
            return
        target_dirs = set(self._template_library_watch_directories())
        current_dirs = set(watcher.directories())
        remove_dirs = list(current_dirs - target_dirs)
        add_dirs = list(target_dirs - current_dirs)
        if remove_dirs:
            watcher.removePaths(remove_dirs)
        if add_dirs:
            watcher.addPaths(add_dirs)

    def _on_template_library_path_changed(self, _path: str = "") -> None:
        self._schedule_template_library_refresh(80)

    def _schedule_template_library_refresh(
        self,
        delay_ms: int = 80,
    ) -> None:
        if self._template_library_refresh_running:
            self._template_library_refresh_again = True
            return
        self._template_library_refresh_timer.start(
            max(0, int(delay_ms))
        )

    def _switch_to_default_template_after_missing_file(self) -> None:
        if self._has_pending_template_edits():
            message = (
                "当前模板文件已被删除；未保存草稿仍保留，"
                "点击保存可在原路径重新创建文件。"
            )
            self._set_template_management_status(f"⚠ {message}")
            self._sync_template_file_status()
            Toast.show_warning(message)
            return
        message = "当前模板文件已不存在，已切换到默认格式"
        selection = self._template_library_controller.default_selection(
            mode_id=self._current_work_mode_id()
        )
        self._activate_template(
            selection.template,
            template_id=selection.template_id,
            path=selection.path,
            source=selection.source,
            source_type=selection.source_type,
            status=f"ℹ {message}",
        )
        Toast.show_info(message)

    def _refresh_template_library_from_disk(self) -> None:
        self._template_library_refresh_timer.stop()
        if self._template_library_refresh_running:
            self._template_library_refresh_again = True
            return

        self._template_library_refresh_running = True
        self._template_library_refresh_again = False
        try:
            self._setup_template_library_watcher()
            current_was_removed = (
                self._current_template_file_was_removed()
            )
            self._refresh_template_selector_options()
            if current_was_removed:
                self._switch_to_default_template_after_missing_file()
            else:
                self._sync_template_file_status()
        except Exception as exc:
            Toast.show_error(f"刷新模板文件夹失败: {exc}")
        finally:
            self._template_library_refresh_running = False
            should_refresh_again = self._template_library_refresh_again
            self._template_library_refresh_again = False
            if should_refresh_again:
                self._template_library_refresh_timer.start(80)

    def _on_template_import_completed(self, mode_id: str, batch) -> None:
        if str(mode_id or "").strip() != self._current_work_mode_id():
            return
        self._refresh_template_library_from_disk()
        if batch.successes:
            names = "、".join(
                success.entry.name for success in batch.successes[:3]
            )
            if len(batch.successes) > 3:
                names += f"等 {len(batch.successes)} 个"
            Toast.show_success(
                f"已导入模板: {names}；当前编辑保持不变"
            )
        if batch.rejections:
            detail = str(batch.rejections[0].message or "").strip()
            Toast.show_error(
                f"有 {len(batch.rejections)} 个模板未通过校验"
                + (
                    f"：{detail}"
                    if detail
                    else "，请修正后重新放入“待导入”"
                )
            )
        if batch.warnings:
            detail = str(batch.warnings[0].message or "").strip()
            Toast.show_warning(
                f"模板已处理，但有 {len(batch.warnings)} 条提醒"
                + (f"：{detail}" if detail else "")
            )

    def _on_work_mode_changed(self, _mode) -> None:
        self._template_library_refresh_timer.stop()
        self._template_library_refresh_again = False
        self._setup_template_library_watcher()
        self._refresh_template_library_from_disk()

    @staticmethod
    def _format_source_text(
        source_label: str,
        path: str = "",
    ) -> str:
        label = str(source_label or "").strip() or "模板文件"
        value = str(path or "").strip()
        if not value:
            return label
        display = (
            Path(value).name
            if any(sep in value for sep in ("/", "\\"))
            else value
        )
        return f"{label}：{display}"

    def _sync_template_file_status(self) -> None:
        self._overview_detail.set_status_text(
            self._template_overview_status_text()
        )
        is_builtin = self._current_template_is_builtin()
        can_rename = self._current_template_can_rename()
        can_delete = self._current_template_can_delete()
        source_type = str(
            self._current_template_source_type or ""
        ).strip()
        unavailable_reason = (
            "内置模板保存时会创建用户副本，不能重命名或删除"
            if is_builtin
            else (
                "外部模板可以编辑和保存，但不在模板库中管理名称"
                if source_type == "external"
                else "当前模板还没有保存为用户模板文件"
            )
        )
        self._overview_detail.set_template_action_state(
            can_rename=can_rename,
            can_delete=can_delete,
            rename_tooltip="" if can_rename else unavailable_reason,
            delete_tooltip="" if can_delete else unavailable_reason,
            folder_tooltip=(
                "打开当前工作模式的模板工作台\n"
                f"{self._template_authoring_workspace_folder()}"
            ),
        )

    def _refresh_template_selector_options(self) -> None:
        options = self._template_library_controller.options(
            mode_id=self._current_work_mode_id(),
            current_template_id=self._current_template_id,
            current_template=self._current_template,
            include_current=self._current_template_should_stay_in_selector(),
        )
        self._overview_detail.set_template_options(
            list(options),
            current_template_id=self._current_template_id,
        )

    def _on_new_template_requested(self) -> None:
        name = self._template_text_request(
            "新建模板",
            "请输入模板名称：",
            placeholder="例如：论文自定义模板",
            default=self._unique_template_copy_name(),
            ok_text="创建",
            parent=self,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            Toast.show_warning("模板名称不能为空")
            return
        self._create_template_copy(name, action_label="新建模板")

    def _on_duplicate_template_requested(self) -> None:
        self._create_template_copy(
            self._unique_template_copy_name(),
            action_label="创建副本",
        )

    def _on_rename_template_requested(self) -> None:
        if not self._current_template_can_rename():
            Toast.show_warning(
                "当前模板不能直接重命名，请先创建副本"
                if self._current_template_is_builtin()
                or str(self._current_template_source_type or "").strip()
                in {"legacy", "external"}
                else "当前模板还没有保存为用户模板文件"
            )
            return
        current_name = str(
            getattr(self._current_template, "name", "")
            or self._current_template_id
            or ""
        ).strip()
        name = self._template_text_request(
            "重命名模板",
            "请输入新的模板名称：",
            placeholder="模板名称",
            default=current_name,
            ok_text="暂存名称",
            parent=self,
        )
        if name is None:
            return
        name = name.strip()
        if not name:
            Toast.show_warning("模板名称不能为空")
            return
        if self._current_template is None:
            return

        self._current_template.name = name
        self._on_template_edited(self._current_template)
        self._refresh_template_selector_options()
        self._set_template_management_status(
            f"ℹ 名称“{name}”已暂存，点击保存后写入模板文件"
        )
        Toast.show_info("模板名称已暂存，尚未写入文件")

    def _on_open_template_folder_requested(self) -> None:
        try:
            workspace = ensure_template_authoring_workspace(
                self._current_work_mode_id()
            )
            opened = QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(workspace.root))
            )
        except Exception as exc:
            Toast.show_error(f"准备模板工作区失败: {exc}")
            return
        if not opened:
            Toast.show_error(
                f"无法打开模板文件夹: {workspace.root}"
            )

    def _on_delete_template_requested(self) -> None:
        if not self._current_template_can_delete():
            Toast.show_warning(
                "当前模板不能直接删除，请先创建副本"
                if self._current_template_is_builtin()
                or str(self._current_template_source_type or "").strip()
                in {"legacy", "external"}
                else "当前模板还没有可删除的用户模板文件"
            )
            return
        path = self._current_template_manage_path()
        if path is None:
            Toast.show_warning("当前模板还没有可删除的用户模板文件")
            return
        template_name = str(
            getattr(self._current_template, "name", "")
            or self._current_template_id
            or path.stem
        ).strip()
        draft_warning = (
            "\n\n当前模板还有未保存草稿；"
            "确认删除后，该草稿也会一并丢弃。"
            if self._has_pending_template_edits()
            else ""
        )
        if not self._template_persistence_confirm(
            "删除模板",
            f"确定删除模板“{template_name}”吗？"
            f"\n\n文件：{path.name}{draft_warning}",
            confirm_text="删除",
            destructive=True,
            parent=self,
        ):
            return

        try:
            self._template_library_controller.delete_user_template(path)
        except Exception as exc:
            message = f"删除模板失败: {exc}"
            self._set_template_management_status(f"❌ {message}")
            Toast.show_error(message)
            return

        self._draft_store.remove(self._draft_context)
        self._sync_bridge_draft_protections()
        selection = self._template_library_controller.default_selection(
            mode_id=self._current_work_mode_id()
        )
        self._activate_template(
            selection.template,
            template_id=selection.template_id,
            path=selection.path,
            source=selection.source,
            source_type=selection.source_type,
            status=f"✅ 已删除模板: {template_name}",
        )
        Toast.show_success(f"已删除模板: {template_name}")

    def _on_template_selected(self, index: int) -> None:
        template_id = str(
            self._overview_detail._combo.itemData(index) or ""
        ).strip()
        if not template_id:
            return
        item = self._overview_detail._combo.model().item(index)
        if (
            template_id == self._current_template_id
            and (item is None or item.isEnabled())
        ):
            return
        try:
            template, path, source = self._load_template_for_selector(
                template_id
            )
        except Exception as exc:
            message = f"模板加载失败: {exc}"
            self._set_template_management_status(f"❌ {message}")
            Toast.show_error(message)
            self._refresh_template_selector_options()
            return
        self._activate_template(
            template,
            template_id=template_id,
            path=path,
            source=source,
            status="",
        )
