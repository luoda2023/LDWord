# -*- coding: utf-8 -*-
"""Regression tests for the unified AI access layer + external API.

约定锁定：
* AiAccessLayer 查询端：已登记的查询项返回 plain-data JSON，未知项
  返回 known 清单而非异常；UI 未挂载时 session 查询自动降级。
* AiAccessLayer 控制端：动作交给注册的分发器（沿状态机/确认闸门），
  未注册分发器时 fail-closed（accepted=False）；危险动作 consent
  等级必须为 requires_user，且与 ai_operations_api 的 gated 三态一致。
* ExternalApiServer：默认不监听；启动后仅回环地址、无 token 返回 401、
  /api/capabilities 可用、/api/action 把控制交给分发器、未知路由 404。
"""

from __future__ import annotations

import json
import os
import urllib.request

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from src.assistant.application.ai_access_layer import (
    CONTROL_DIRECT,
    CONTROL_GATED,
    AiAccessLayer,
    get_ai_access_layer,
)
from src.assistant.application.ai_operations_api import AI_OPERATIONS, AI_OP_GATED


def test_query_unknown_returns_known_list_not_exception():
    access = AiAccessLayer()
    result = access.query("no_such_query")
    assert result["ok"] is False
    assert "operations" in result["known"]
    assert "work_modes" in result["known"]


def test_query_session_degrades_without_ui():
    access = AiAccessLayer()
    result = access.query("session_status")
    assert result["ok"] is True
    assert result["available"] is False


def test_query_capabilities_lists_operations_with_consent():
    access = AiAccessLayer()
    result = access.query("capabilities")
    ids = {op["id"] for op in result["operations"]}
    assert {"chat", "compose_word", "preflight"} <= ids
    for op in result["operations"]:
        assert op["consent"] in {"direct", "requires_user", "suggest"}


def test_query_work_modes_and_templates_reflect_config():
    access = AiAccessLayer()
    modes = access.query("work_modes")
    mode_ids = {m["id"] for m in modes["modes"]}
    assert {"custom", "engineering", "exam", "thesis", "official"} <= mode_ids
    templates = access.query("templates", mode_id="engineering")
    assert any(t["id"] == "eng_document" for t in templates["templates"])


def test_control_fails_closed_without_dispatcher():
    access = AiAccessLayer()
    result = access.request_action("compose_word", {})
    assert result["accepted"] is False
    assert result["error"] == "dispatcher_not_ready"


def test_control_routes_through_dispatcher():
    access = AiAccessLayer()
    seen = {}

    def dispatcher(action_id, payload):
        seen["action_id"] = action_id
        seen["payload"] = payload
        return {"accepted": True, "detail": "ok"}

    access.register_action_dispatcher(dispatcher)
    result = access.request_action("preflight", {"k": 1})
    assert result["accepted"] is True
    assert seen == {"action_id": "preflight", "payload": {"k": 1}}


def test_dangerous_actions_require_user_consent():
    access = AiAccessLayer()
    # 落盘与覆盖文件类动作必须用户点头（gated 三态 ↔ requires_user）。
    for key, op in AI_OPERATIONS.items():
        if op["status"] == AI_OP_GATED:
            assert access.consent_level(key) == CONTROL_GATED, key
    # 对话/查询类可直接驱动。
    assert access.consent_level("chat") == CONTROL_DIRECT
    assert access.consent_level("preflight") == CONTROL_DIRECT


def test_access_layer_is_app_level_singleton():
    assert get_ai_access_layer() is get_ai_access_layer()


def test_external_api_server_loopback_auth_and_dispatch():
    from src.assistant.application.external_api import ExternalApiServer

    access = AiAccessLayer()
    access.register_action_dispatcher(
        lambda action_id, payload: {"accepted": True, "echo": payload}
    )
    server = ExternalApiServer(access, port=0)
    try:
        assert server.start() is True
        port = server.port
        assert server.is_running
        assert server.port == port

        def request(method, path, body=None, with_token=True):
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}{path}", method=method
            )
            if with_token:
                req.add_header("Authorization", f"Bearer {server._token}")
            data = None
            if body is not None:
                data = json.dumps(body).encode("utf-8")
                req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, data=data, timeout=5) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))

        # 无 token → 401
        try:
            request("GET", "/api/capabilities", with_token=False)
            raise AssertionError("missing token must raise 401")
        except urllib.error.HTTPError as exc:
            assert exc.code == 401

        # 查询端
        status, health = request("GET", "/api/health")
        assert status == 200 and health["ok"] is True
        _status, caps = request("GET", "/api/capabilities")
        assert caps["ok"] is True and caps["operations"]
        _status, state = request("GET", "/api/state")
        assert state["app_info"]["ok"] is True

        # 控制端：动作交给分发器（内部闸门仍在 UI 侧）
        status, action = request(
            "POST", "/api/action", body={"action_id": "preflight", "x": 1}
        )
        assert status == 202 and action["accepted"] is True and action["echo"]["x"] == 1

        # 未知查询 → ok=False 带说明；未知路由 → 404
        status, unknown = request("GET", "/api/query?what=zzz")
        assert status == 200 and unknown["ok"] is False
        try:
            request("GET", "/api/nothing")
            raise AssertionError("unknown route must raise 404")
        except urllib.error.HTTPError as exc:
            assert exc.code == 404
    finally:
        server.stop()
    assert server.is_running is False
