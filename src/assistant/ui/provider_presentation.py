"""Single user-facing projection for AI provider state and failures."""

from __future__ import annotations

from src.assistant.runtime.providers.profiles import ProviderProfile


def provider_connection_badge(
    profile: ProviderProfile,
    *,
    ready: bool,
    show_unready: bool = False,
) -> str:
    """Return the short status label shared by settings and composers."""

    if not ready:
        return "未就绪" if show_unready else ""
    if profile.kind == "mock":
        return "本地"
    if profile.connection_status == "success":
        return "文本已验证"
    if profile.connection_status == "failed":
        return "上次失败"
    return "未测试"


def provider_connection_status_text(
    profile: ProviderProfile,
    *,
    ready: bool,
    readiness_message: str,
) -> str:
    """Project persisted connection evidence without implying live health."""

    if not ready:
        return f"连接状态：未就绪 · {readiness_message}"
    if profile.kind == "mock":
        return "连接状态：本地可用，不访问网络"
    timestamp = str(profile.last_checked_at or "").replace("T", " ")
    if profile.connection_status == "success":
        return f"连接状态：文本流已验证 · {timestamp or '时间未记录'}"
    if profile.connection_status == "failed":
        detail = profile.last_check_message or "请重新测试"
        return f"连接状态：上次测试失败 · {detail}"
    return "连接状态：配置完整但尚未测试"


def provider_error_text(value: object) -> str:
    """Translate stable provider/runtime failures into one product vocabulary."""

    text = str(value or "").strip()
    normalized = text.lower()
    if "no api key" in normalized or "missing_api_key" in normalized:
        return "缺少 API Key"
    if "timed out" in normalized or "timeout" in normalized:
        return "连接超时，请检查 API 地址和网络"
    if "http 401" in normalized or "unauthorized" in normalized:
        return "鉴权失败（HTTP 401），请检查 API Key"
    if "http 403" in normalized or "forbidden" in normalized:
        return "当前 API Key 没有访问该模型的权限（HTTP 403）"
    if "http 404" in normalized:
        return "接口或模型不存在（HTTP 404），请检查 API 地址和模型 ID"
    if "http 429" in normalized:
        return "请求过于频繁或额度不足（HTTP 429）"
    if "connection failed" in normalized or "urlerror" in normalized:
        return "无法连接 API 地址，请检查地址、网络和代理"
    if (
        "stream ended before" in normalized
        or "stream_incomplete" in normalized
        or "provider_stream_incomplete" in normalized
    ):
        return "服务返回的数据流不完整"
    if "provider_returned_empty_response" in normalized:
        return "服务连接成功，但未返回有效内容"
    if "credential" in normalized and "unavailable" in normalized:
        return "无法读取 Windows 凭据中的 API Key"
    return text or "未知错误"


__all__ = [
    "provider_connection_badge",
    "provider_connection_status_text",
    "provider_error_text",
]
