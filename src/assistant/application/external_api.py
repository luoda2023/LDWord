# -*- coding: utf-8 -*-
"""外部 AI 本地 API 服务 — 让一个统一的外部 AI 查询与控制本软件。

* **默认关闭**：用户在 偏好设置 → 外部 AI 接口 显式开启后才监听。
* **仅本机回环**：绑定 127.0.0.1，不暴露到局域网/公网。
* **Token 认证**：开启时生成随机 token（保存在用户偏好目录），
  外部请求必须带 ``Authorization: Bearer <token>``。
* **查询只读 + 控制走闸门**：GET 全部开放；POST 仅
  ``/api/chat``、``/api/action`` 两个入口，控制动作沿内部状态机与
  用户确认闸门执行，AI 永远不能替用户做破坏性决定。

端点（JSON）：
  GET  /api/health        存活探针 + 应用信息
  GET  /api/capabilities  软件全部 AI 可查询/可控制能力目录
  GET  /api/state         当前工作模式 / 活动会话 / 任务状态快照
  GET  /api/sessions      会话清单（概要）
  GET  /api/templates     模板清单（可按 mode_id 过滤）
  GET  /api/scenes        场景清单（可按 mode_id 过滤）
  GET  /api/query?what=…  任意已登记查询的通配入口
  POST /api/chat          提交一条自然语言消息（走主会话链路）
  POST /api/action        提交一个控制动作意图（走 document-action 闸门）

服务跑在守护线程上，退出随宿主；一切异常都不打断 GUI 主线程。
"""
from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from src.assistant.application.ai_access_layer import AiAccessLayer
from src.assistant.storage.paths import assistant_storage_root

_TOKEN_SCHEMA = "ldword-external-api-token/v1"


def token_path() -> Path:
    return assistant_storage_root() / "external-api-token.json"


def _load_or_create_token() -> str:
    """读取或生成外部 API token（文件权限即用户目录权限）。"""

    path = token_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema") == _TOKEN_SCHEMA and payload.get("token"):
            return str(payload["token"])
    except (OSError, ValueError, TypeError):
        pass
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"schema": _TOKEN_SCHEMA, "token": token}, ensure_ascii=False),
        encoding="utf-8",
    )
    return token


class ExternalApiServer:
    """本地回环 HTTP 服务，把外部请求转交 :class:`AiAccessLayer`。"""

    def __init__(self, access: AiAccessLayer, *, port: int = 0) -> None:
        self._access = access
        self._port = int(port)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._token = _load_or_create_token()

    # ---- 生命周期 ----------------------------------------------------

    @property
    def is_running(self) -> bool:
        return self._server is not None

    @property
    def port(self) -> int:
        return int(self._server.server_address[1]) if self._server else self._port

    def start(self) -> bool:
        if self._server is not None:
            return True
        try:
            self._server = ThreadingHTTPServer(
                ("127.0.0.1", self._port or 0), self._make_handler()
            )
        except OSError:
            self._server = None
            return False
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="ldword-external-api",
            daemon=True,
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        server = self._server
        if server is None:
            return
        self._server = None
        server.shutdown()
        server.server_close()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        self._thread = None

    # ---- 请求处理 ----------------------------------------------------

    def _make_handler(self):
        access = self._access
        token = self._token
        server_ref = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # noqa: A003 - 静默默认日志
                return

            # -- 工具 --

            def _authorized(self) -> bool:
                header = self.headers.get("Authorization", "")
                return header == f"Bearer {token}"

            def _send(self, status: int, payload: dict) -> None:
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _unauthorized(self) -> None:
                self._send(401, {"ok": False, "error": "unauthorized"})

            def _not_found(self) -> None:
                self._send(404, {"ok": False, "error": "not_found"})

            def _read_json(self) -> dict:
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > 1_000_000:
                    return {}
                try:
                    data = json.loads(self.rfile.read(length).decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    return {}
                return data if isinstance(data, dict) else {}

            def _server_down(self) -> None:
                self._send(503, {"ok": False, "error": "server_stopping"})

            def _check(self) -> bool:
                if server_ref._server is None:
                    self._server_down()
                    return False
                if not self._authorized():
                    self._unauthorized()
                    return False
                return True

            # -- GET --

            def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 约定
                try:
                    self._do_get_guarded()
                except Exception:
                    import traceback, sys as _sys
                    traceback.print_exc(file=_sys.stderr)
                    raise

            def _do_get_guarded(self) -> None:
                if not self._check():
                    return
                parsed = urlparse(self.path)
                route = parsed.path.rstrip("/") or "/"
                params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
                if route == "/api/health":
                    info = access.query("app_info")
                    self._send(200, {"ok": True, **info})
                elif route == "/api/capabilities":
                    self._send(200, access.query("capabilities"))
                elif route == "/api/state":
                    self._send(
                        200,
                        {
                            "app_info": access.query("app_info"),
                            "session": access.query("session_status"),
                        },
                    )
                elif route == "/api/sessions":
                    self._send(200, access.query("sessions"))
                elif route == "/api/templates":
                    self._send(200, access.query("templates", mode_id=params.get("mode_id")))
                elif route == "/api/scenes":
                    self._send(200, access.query("scenes", mode_id=params.get("mode_id")))
                elif route == "/api/query":
                    what = str(params.pop("what", "") or "")
                    if not what:
                        self._send(400, {"ok": False, "error": "what_required"})
                    else:
                        self._send(200, access.query(what, **params))
                else:
                    self._not_found()

            # -- POST --

            def do_POST(self) -> None:  # noqa: N802
                if not self._check():
                    return
                route = urlparse(self.path).path.rstrip("/") or "/"
                data = self._read_json()
                if route == "/api/chat":
                    text = str(data.get("message") or "").strip()
                    if not text:
                        self._send(400, {"ok": False, "error": "message_required"})
                        return
                    self._send(200, access.request_action("chat", {"message": text}))
                elif route == "/api/action":
                    action_id = str(data.pop("action_id", "") or "")
                    result = access.request_action(action_id, data)
                    status = 202 if result.get("accepted") else 422
                    self._send(status, result)
                else:
                    self._not_found()

        return Handler


__all__ = ["ExternalApiServer", "token_path"]
