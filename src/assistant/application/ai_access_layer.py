# -*- coding: utf-8 -*-
"""AI 统一接入层（AiAccessLayer）— 软件所有功能的 AI 查询与控制入口。

目标（用户要求）：软件里没有 AI 到不了的地方。所有内部功能向 AI
登记为「可查询 / 可控制」两类接口，由这一层统一暴露：

* **查询（只读）** — 软件状态、工作模式、场景/模板清单、会话与任务
  状态、能力目录、工程阶段指南……任何 AI（内嵌对话、悬浮窗、外部
  统一 AI）都能通过 ``query()`` 拿到结构化 JSON。
* **控制（动作）** — 通过 ``request_action()`` 驱动功能。控制永远不是
  直接执行：动作被转成类型化的 document_action / 导航意图，沿既有
  状态机与用户确认闸门走；破坏性动作（覆盖文件、落盘）必须用户点头。

外部统一 AI 通过 ``external_api``（本地 HTTP 服务）访问同一层 ——
外部与内部共享同一套目录、同一套校验、同一套确认闸门。

设计约束：
* 只做门面与投影，不复刻业务逻辑；查询端只读，控制端只提交意图。
* 所有返回 JSON-serializable（plain data），供 HTTP / WebChannel 直通。
* ``AiAccessLayer`` 不持有 UI 引用；UI 侧通过 ``attach_panel`` /
  ``attach_window`` 注册弱接入点，未注册的查询自动降级返回
  ``available: False``，绝不抛异常打断调用方。
"""
from __future__ import annotations

import threading
from typing import Any, Callable

from src.qt_api import QApplication, QObject, QThread, Signal, Slot

from src.assistant.application.ai_operations_api import (
    AI_OPERATIONS,
    AI_OP_EXECUTABLE,
    AI_OP_GATED,
    AI_OP_PLANNED,
)

# 控制动作用户确认等级。
CONTROL_SUGGEST = "suggest"        # AI 建议动作，用户点卡片确认后执行
CONTROL_DIRECT = "direct"          # AI 可直接驱动（仍受本地状态机约束）
CONTROL_GATED = "requires_user"    # 必须用户显式批准（覆盖文件、落盘等）

# 动作 ID → 确认等级。与 ai_operations_api 的三态对齐，供外部 AI
# 在发起前自查"这个动作我能不能自动做"。
_ACTION_CONSENT: dict[str, str] = {
    "chat": CONTROL_DIRECT,
    "build_outline": CONTROL_DIRECT,
    "edit_outline_inline": CONTROL_DIRECT,
    "author_chapters": CONTROL_DIRECT,
    "revise_draft": CONTROL_DIRECT,
    "revise_content_draft": CONTROL_DIRECT,
    "apply_typesetting_template": CONTROL_DIRECT,
    "reconcile_typesetting": CONTROL_DIRECT,
    "preflight": CONTROL_DIRECT,
    "generate_content_draft": CONTROL_DIRECT,
    "navigate": CONTROL_DIRECT,
    "compose_word": CONTROL_GATED,
    "approve_execute": CONTROL_GATED,
    "open_artifact": CONTROL_GATED,
    "open_content_draft": CONTROL_GATED,
    "open_output_folder": CONTROL_GATED,
}

# 软件版本信息的稳定来源。
_APP_META: dict[str, str] = {}


def register_app_meta(meta: dict[str, str]) -> None:
    """启动时登记应用元数据，供 ``query('app_info')`` 返回。"""
    _APP_META.update({str(k): str(v) for k, v in dict(meta).items()})


class _ControlRelay(QObject):
    """跨线程控制投递中继。

    HTTP server 线程不能直接触碰 UI（Qt 控件只允许主线程访问），
    控制动作经此中继的信号以 QueuedConnection 投递到主线程执行，
    结果通过 ``threading.Event`` 回传等待方。
    """

    controlRequested = Signal(str, dict, object, object)

    def dispatch(self, action_id: str, payload: dict, box: dict, done: threading.Event) -> None:
        self.controlRequested.emit(action_id, payload, box, done)


class AiAccessLayer:
    """软件全部功能的 AI 查询 + 控制统一门面。

    一个应用实例挂一层（通常由 MainWindow 创建并挂在
    ``bridge.ai_access`` 上）；内嵌对话、悬浮窗与外部 API 都汇到这层。
    """

    def __init__(self) -> None:
        self._bridge = None
        self._panel_provider: Callable[[], Any] | None = None
        self._session_coordinator = None
        # 外部 API 需要把"控制意图"转成 UI 动作的回调（由接线方注册）。
        self._action_dispatcher: Callable[[str, dict], dict] | None = None
        # 跨线程控制投递中继：单例总在主线程首次创建（main_window 接
        # 线时），因此信号槽落在主线程。防线程亲和性漂移，挂载时强制
        # 回主线程（见 attach_bridge）。
        self._relay = _ControlRelay()
        self._relay.controlRequested.connect(self._dispatch_on_main)
        self._relay_thread_checked = False

    # ---- 接线（UI 侧注册，可选；缺省查询自动降级） ------------------

    def attach_bridge(self, bridge: Any) -> None:
        self._bridge = bridge
        # 防线程亲和性漂移：单例若在非主线程被首次创建，这里（主线程
        # 接线时）把中继拉回主线程，保证信号槽落在 UI 线程。
        if not self._relay_thread_checked:
            self._relay_thread_checked = True
            app = QApplication.instance()
            if app is not None and self._relay.thread() is not app.thread():
                self._relay.moveToThread(app.thread())

    def attach_panel(self, panel_provider: Callable[[], Any]) -> None:
        """注册返回当前 AssistantPanel（可为 None）的提供者。"""

        self._panel_provider = panel_provider

    def attach_session_coordinator(self, coordinator: Any) -> None:
        self._session_coordinator = coordinator

    def register_action_dispatcher(
        self, dispatcher: Callable[[str, dict], dict]
    ) -> None:
        """注册控制意图分发器。

        ``dispatcher(action_id, payload) -> {"accepted": bool, **detail}``
        由 UI 接线方实现（通常调用 AssistantCardActionMixin 的
        document action 通道），保证控制动作沿状态机与确认闸门执行。
        """

        self._action_dispatcher = dispatcher

    # ---- 查询（只读） -----------------------------------------------

    def query(self, what: str, **params: Any) -> dict[str, Any]:
        """AI 查询软件状态的统一入口，返回 plain-data JSON。"""

        handler = {
            "app_info": self._q_app_info,
            "capabilities": self._q_capabilities,
            "work_modes": self._q_work_modes,
            "session_status": self._q_session_status,
            "sessions": self._q_sessions,
            "templates": self._q_templates,
            "scenes": self._q_scenes,
            "engineering_stages": self._q_engineering_stages,
            "operations": self._q_operations,
        }.get(str(what or "").strip())
        if handler is None:
            return {
                "ok": False,
                "error": f"unknown_query:{what}",
                "known": sorted(
                    {
                        "app_info",
                        "capabilities",
                        "work_modes",
                        "session_status",
                        "sessions",
                        "templates",
                        "scenes",
                        "engineering_stages",
                        "operations",
                    }
                ),
            }
        try:
            result = handler(**params)
        except Exception as exc:  # noqa: BLE001 - 查询永不打断调用方
            result = {"error": f"{type(exc).__name__}:{exc}"}
        return {"ok": "error" not in result, "what": what, **result}

    def _q_app_info(self) -> dict[str, Any]:
        from src.config.work_mode import list_work_modes

        modes = list_work_modes()
        return {
            "app": dict(_APP_META),
            "work_mode": getattr(self._bridge, "current_work_mode_id", lambda: "")(),
            "available_modes": [m.mode_id for m in modes],
            "assistant_attached": self._panel_provider is not None,
        }

    def _q_capabilities(self) -> dict[str, Any]:
        """AI 操作目录：每个功能的 id、名称、确认等级与触达路径。"""

        operations = []
        for key, op in AI_OPERATIONS.items():
            operations.append(
                {
                    "id": key,
                    "name": op["name"],
                    "params": op["params"],
                    "status": op["status"],
                    "consent": _ACTION_CONSENT.get(key, CONTROL_SUGGEST),
                    "path": op["path"],
                }
            )
        return {"operations": operations}

    def _q_work_modes(self) -> dict[str, Any]:
        from src.config.work_mode import list_work_modes

        return {
            "modes": [
                {
                    "id": m.mode_id,
                    "label": m.label,
                    "description": m.description,
                    "default_scene_id": m.default_scene_id,
                    "default_template_id": m.default_template_id,
                }
                for m in list_work_modes()
            ]
        }

    def _current_session(self) -> Any:
        panel = self._panel_provider() if self._panel_provider else None
        return getattr(panel, "_active_session", None)

    def _q_session_status(self) -> dict[str, Any]:
        session = self._current_session()
        if session is None:
            return {"available": False, "reason": "no_active_session"}
        job = dict(getattr(session, "document_job", {}) or {})
        plan = dict(getattr(session, "active_plan", {}) or {})
        return {
            "available": True,
            "session_id": session.session_id,
            "title": session.title,
            "turn_status": session.turn_status,
            "document_job_status": job.get("status"),
            "error_text": job.get("error_text"),
            "plan_id": plan.get("plan_id"),
            "plan_intent": plan.get("intent"),
            "outline_confirmed_titles": job.get("outline_edited_titles"),
            "primary_output_path": job.get("primary_output_path"),
            "message_count": len(tuple(getattr(session, "messages", ()) or ())),
        }

    def _q_sessions(self) -> dict[str, Any]:
        if self._session_coordinator is None:
            return {"available": False, "reason": "coordinator_not_attached"}
        summaries = self._session_coordinator.list_sessions()
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "title": s.title,
                    "updated_at": s.updated_at,
                    "document_job_status": s.document_job_status,
                }
                for s in summaries
            ]
        }

    def _q_templates(self, mode_id: str | None = None) -> dict[str, Any]:
        from src.config.library import list_template_entries

        entries = list_template_entries(mode_id=mode_id or None)
        return {
            "templates": [
                {
                    "id": e.config_id,
                    "name": e.name,
                    "mode_id": e.mode_id,
                    "source": e.source_type,
                }
                for e in entries
            ]
        }

    def _q_scenes(self, mode_id: str | None = None) -> dict[str, Any]:
        from src.config.library import list_scene_entries

        entries = list_scene_entries(mode_id=mode_id or None)
        return {
            "scenes": [
                {
                    "id": e.config_id,
                    "name": e.name,
                    "mode_id": e.mode_id,
                    "available": e.load_error == "",
                }
                for e in entries
            ]
        }

    def _q_engineering_stages(self) -> dict[str, Any]:
        from src.config.engineering_stage_library import list_engineering_stages

        return {
            "stages": [
                {
                    "id": s.stage_id,
                    "label": s.label,
                    "doc_kinds": list(s.doc_kinds),
                }
                for s in list_engineering_stages()
            ]
        }

    def _q_operations(self) -> dict[str, Any]:
        return {
            "operations": [
                {
                    "id": key,
                    "name": op["name"],
                    "status": op["status"],
                    "consent": _ACTION_CONSENT.get(key, CONTROL_SUGGEST),
                }
                for key, op in AI_OPERATIONS.items()
            ],
            "consent_levels": {
                CONTROL_DIRECT: "AI 可直接发起，由本地状态机校验执行",
                CONTROL_GATED: "必须用户显式批准后执行",
                CONTROL_SUGGEST: "AI 建议动作，默认由用户点卡片确认",
            },
        }

    # ---- 控制（动作意图） -------------------------------------------

    def request_action(self, action_id: str, payload: dict | None = None) -> dict:
        """AI 控制软件的统一入口。

        控制动作不在此执行：交给注册的分发器（UI document-action 通
        道），沿用状态机校验与用户确认闸门。未注册分发器或未挂面板
        时返回 ``accepted: False`` 并说明原因，外部 AI 可据此改道。

        线程安全：允许任意线程调用。非主线程调用时（外部 HTTP API），
        动作经信号投递到主线程执行并等待结果——Qt UI 只能在主线程
        触碰，跨线程直调是未定义行为。
        """

        action = str(action_id or "").strip()
        if not action:
            return {"accepted": False, "error": "action_id_required"}
        if self._action_dispatcher is None:
            return {
                "accepted": False,
                "error": "dispatcher_not_ready",
                "hint": "软件界面尚未完成初始化，请稍后重试",
            }
        payload_dict = dict(payload or {})
        app = QApplication.instance()
        on_main = app is None or QThread.currentThread() is app.thread()
        if on_main:
            return self._run_action(action, payload_dict)
        # 跨线程：投递到主线程，等待执行完成（限时防 UI 死锁拖垮调用方）。
        box: dict = {}
        done = threading.Event()
        self._relay.dispatch(action, payload_dict, box, done)
        if not done.wait(timeout=60.0):
            return {
                "accepted": False,
                "error": "ui_thread_unresponsive",
                "hint": "主线程 60s 未处理该控制动作，请稍后重试",
            }
        result = box.get("result")
        if not isinstance(result, dict):
            return {"accepted": False, "error": "dispatch_failed"}
        return result

    def _run_action(self, action: str, payload_dict: dict) -> dict:
        """在主线程执行控制分发（仅供 request_action 内部调用）。"""

        result = self._action_dispatcher(action, payload_dict)  # type: ignore[misc]
        return {
            "accepted": bool(result.get("accepted", False)),
            "action_id": action,
            **{k: v for k, v in result.items() if k != "accepted"},
        }

    def consent_level(self, action_id: str) -> str:
        """查询某动作需要的用户确认等级（外部 AI 发起前自查）。"""

        return _ACTION_CONSENT.get(str(action_id or "").strip(), CONTROL_SUGGEST)

    @Slot(str, dict, object, object)
    def _dispatch_on_main(
        self, action: str, payload: dict, box: dict, done: threading.Event
    ) -> None:
        """中继信号槽（主线程）：执行控制分发并回传结果。"""

        try:
            result = self._run_action(action, payload)
        except Exception as exc:  # noqa: BLE001 - 主线程崩溃回传而非炸掉事件循环
            result = {"accepted": False, "error": f"dispatch_crashed: {exc}"}
        box["result"] = result
        done.set()


# 应用级单例：main_window 创建后由 bridge 引用共享。
_ACCESS_LAYER: AiAccessLayer | None = None


def get_ai_access_layer() -> AiAccessLayer:
    global _ACCESS_LAYER
    if _ACCESS_LAYER is None:
        _ACCESS_LAYER = AiAccessLayer()
    return _ACCESS_LAYER


__all__ = [
    "AiAccessLayer",
    "CONTROL_DIRECT",
    "CONTROL_GATED",
    "CONTROL_SUGGEST",
    "AI_OP_EXECUTABLE",
    "AI_OP_GATED",
    "AI_OP_PLANNED",
    "get_ai_access_layer",
    "register_app_meta",
]
