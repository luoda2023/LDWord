"""Filesystem lifecycle behavior for the scene editor panel."""

from __future__ import annotations

from pathlib import Path

from src.config import library as config_library
from src.config.library import (
    default_scene_entry,
    get_scene_entry,
    load_scene_from_library,
)
from src.config.master_library import OFFICIAL_USER_MASTER_DIR
from src.config.scene import SceneWorkspace
from src.qt_api import QTimer
from src.shared.ui.toast import Toast
from src.ui.panels.scene_state_projection import (
    builtin_scene_id_set as _builtin_scene_id_set,
)


class SceneFileLifecycleMixin:
    def _current_scene_id(self) -> str:
        return self._scene_session.current_scene_id()

    def _builtin_scene_ids(self) -> set[str]:
        builtin_ids = {
            str(getattr(descriptor, "config_id", "") or "").strip()
            for descriptor in self._scene_descriptors
            if str(getattr(descriptor, "source_type", "") or "").strip() == "builtin"
            and str(getattr(descriptor, "config_id", "") or "").strip()
        }
        builtin_ids.update(_builtin_scene_id_set())
        return builtin_ids

    def _current_scene_is_builtin(self) -> bool:
        scene_id = self._current_scene_id()
        if not scene_id:
            return False
        source_type = str(self._current_scene_source_type or "").strip()
        if source_type:
            return source_type == "builtin"
        descriptor = self._descriptor_for_scene_id(scene_id)
        if descriptor is not None:
            return (
                str(getattr(descriptor, "source_type", "") or "").strip() == "builtin"
            )
        return scene_id in self._builtin_scene_ids()

    def _current_scene_path_obj(self) -> Path | None:
        path = str(self._current_scene_path or "").strip()
        if path:
            return Path(path)
        scene_id = self._current_scene_id()
        if scene_id:
            entry = get_scene_entry(scene_id, mode_id=self._current_work_mode_id())
            if entry is not None:
                return entry.path
        return None

    def _current_scene_manage_path(self) -> Path | None:
        path = self._current_scene_path_obj()
        if path is None or not path.exists() or path.is_dir():
            return None
        source_type = str(self._current_scene_source_type or "").strip()
        if not source_type:
            descriptor = self._descriptor_for_scene_id(self._current_scene_id())
            source_type = str(getattr(descriptor, "source_type", "") or "").strip()
        if not source_type:
            source_type = config_library.scene_source_type_for_path(path)
        if source_type != "user":
            return None
        return path if config_library.is_scene_user_library_path(path) else None

    def _current_scene_can_rename(self) -> bool:
        return (
            self._current_scene is not None
            and not self._current_scene_is_builtin()
            and self._current_scene_manage_path() is not None
        )

    def _current_scene_can_delete(self) -> bool:
        return (
            not self._current_scene_is_builtin()
            and self._current_scene_manage_path() is not None
        )

    def _current_scene_folder(self) -> Path:
        if self._current_work_mode_id() == "official":
            return OFFICIAL_USER_MASTER_DIR
        path = self._current_scene_path_obj()
        if path is not None:
            folder = path if path.is_dir() else path.parent
            if folder.exists():
                return folder
        return config_library.scene_user_dir(self._current_work_mode_id())

    def _sync_scene_file_status(self) -> None:
        self._scene_file_status_stale = False
        if not hasattr(self, "_overview"):
            return
        is_builtin = self._current_scene_is_builtin()
        can_rename = self._current_scene_can_rename()
        can_delete = self._current_scene_can_delete()
        source_type = str(self._current_scene_source_type or "").strip()
        unavailable_reason = (
            "内置方案不能修改，请先创建副本"
            if is_builtin
            else (
                "外部方案不能直接修改，请先创建副本"
                if source_type == "external"
                else "当前方案还没有保存为用户方案文件"
            )
        )
        self._overview.set_scene_action_state(
            can_rename=can_rename,
            can_delete=can_delete,
            rename_tooltip="" if can_rename else unavailable_reason,
            delete_tooltip="" if can_delete else unavailable_reason,
            folder_tooltip=str(self._current_scene_folder()),
        )

    def _scene_library_watch_directories(self) -> list[str]:
        return [
            str(path)
            for path in config_library.scene_library_watch_dirs(
                mode_id=self._current_work_mode_id()
            )
        ]

    def _setup_scene_library_watcher(self) -> None:
        watcher = getattr(self, "_scene_library_watcher", None)
        if watcher is None:
            return
        target_dirs = set(self._scene_library_watch_directories())
        current_dirs = set(watcher.directories())
        remove_dirs = list(current_dirs - target_dirs)
        add_dirs = list(target_dirs - current_dirs)
        if remove_dirs:
            watcher.removePaths(remove_dirs)
        if add_dirs:
            watcher.addPaths(add_dirs)

    def _on_scene_library_path_changed(self, _path: str = "") -> None:
        if self._scene_library_refresh_pending:
            return
        self._scene_library_refresh_pending = True
        QTimer.singleShot(50, self._refresh_scene_library_from_disk)

    def _current_scene_file_was_removed(self) -> bool:
        source = str(self._current_scene_source or "").strip()
        if source not in {"library", "file"}:
            return False
        path = self._current_scene_path_obj()
        return path is not None and not path.exists()

    def _refresh_scene_library_from_disk(self) -> None:
        self._scene_library_refresh_pending = False
        try:
            self._setup_scene_library_watcher()
        except Exception as exc:
            Toast.show_error(f"刷新方案目录失败: {exc}")
            return
        authoritative_conflict = (
            self._scene_session.refresh_authoritative_user_conflict()
        )
        if authoritative_conflict:
            if self._scene_session.recovery_required():
                Toast.show_warning(
                    "上一次方案保存仍需恢复；已保留当前现场，"
                    "恢复完成前不会重载、切换或覆盖方案文件"
                )
                return
            if self._current_scene_file_was_removed():
                if self.bridge.is_scene_dirty():
                    Toast.show_warning(
                        "当前方案文件已被外部删除；未保存草稿仍保留，请保存为新的用户方案"
                    )
                    return
                self._switch_to_default_scene_after_missing_file()
                return
            if self.bridge.is_scene_dirty():
                Toast.show_warning(
                    "当前方案文件已被外部修改；未保存草稿仍保留，"
                    "为避免覆盖外部版本，请保存为新的用户方案"
                )
                return
            self._reload_clean_current_user_scene_from_disk()
            return
        if self._current_scene_file_was_removed():
            if self.bridge.is_scene_dirty():
                Toast.show_warning(
                    "当前方案文件已被外部删除；未保存草稿仍保留，请保存为新的用户方案"
                )
                return
            self._switch_to_default_scene_after_missing_file()
            return
        try:
            self._refresh_scene_selector_options()
        except Exception as exc:
            Toast.show_error(f"刷新方案列表失败: {exc}")

    def _reload_clean_current_user_scene_from_disk(self) -> bool:
        scene_id = self._current_scene_id()
        path = self._current_scene_path_obj()
        mode_id = self._current_work_mode_id()
        try:
            if not scene_id or path is None:
                raise ValueError("当前用户方案缺少可重载的身份或路径")
            expected_path = config_library.validate_scene_library_write_path(path)
            entry = get_scene_entry(scene_id, mode_id=mode_id)
            if (
                entry is None
                or not bool(getattr(entry, "is_available", True))
                or str(getattr(entry, "source_type", "") or "").strip() != "user"
            ):
                raise ValueError("当前用户方案不再是可用的权威库条目")
            entry_path = config_library.validate_scene_library_write_path(entry.path)
            if entry_path != expected_path:
                raise ValueError("当前用户方案的库路径发生变化")
            before_load = self._scene_session.capture_user_reload_candidate(
                expected_path
            )
            scene = load_scene_from_library(scene_id, mode_id=mode_id)
            if str(getattr(scene, "scene_id", "") or "").strip() != scene_id:
                raise ValueError("外部方案内容与当前方案身份不一致")
            after_load = self._scene_session.capture_user_reload_candidate(
                expected_path
            )
            if after_load.revision != before_load.revision:
                raise RuntimeError("方案文件在重载期间再次变化")
        except Exception as exc:
            Toast.show_error(f"重新加载外部修改的方案失败: {exc}")
            return False
        activated = self._activate_scene(
            scene,
            scene_id=scene_id,
            path=str(entry_path),
            source="library",
            source_type="user",
            dirty=False,
            expected_user_revision=after_load.revision,
        )
        if not activated:
            return False
        Toast.show_info("当前方案文件已被外部更新，已重新加载")
        return True

    def _switch_to_default_scene_after_missing_file(self) -> bool:
        message = "当前方案文件已不存在，已切换到默认方案"
        try:
            mode_id = self._current_work_mode_id()
            entry = default_scene_entry(mode_id=mode_id)
            if entry is not None:
                scene = load_scene_from_library(
                    entry.config_id,
                    mode_id=mode_id,
                )
                activated = self._activate_scene(
                    scene,
                    scene_id=entry.config_id,
                    path=str(entry.path),
                    source="library",
                    source_type=entry.source_type,
                    dirty=False,
                )
            else:
                scene = SceneWorkspace(
                    scene_id="custom",
                    mode_id=mode_id,
                    template_id="default",
                )
                activated = self._activate_scene(
                    scene,
                    scene_id="custom",
                    path="",
                    source="runtime",
                    source_type="runtime",
                    dirty=False,
                )
        except Exception as exc:
            Toast.show_error(f"当前方案缺失后加载默认方案失败: {exc}")
            return False
        if activated:
            Toast.show_info(message)
            return True
        return False


__all__ = ["SceneFileLifecycleMixin"]
