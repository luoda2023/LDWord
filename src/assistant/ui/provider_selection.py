"""Provider selection coordination extracted from the Assistant UI shell."""

from __future__ import annotations

from src.assistant.application.session_coordinator import AssistantSessionCoordinator
from src.assistant.runtime.providers.router import ProviderRouter
from src.assistant.storage.models import AssistantSession
from src.assistant.ui.provider_presentation import provider_error_text


class ProviderSelectionCoordinator:
    """Keep provider identity and composer projection out of ``AssistantPanel``."""

    def __init__(
        self,
        *,
        router: ProviderRouter,
        sessions: AssistantSessionCoordinator,
        provider_combo,
        conversation_composer,
        home_composer,
    ) -> None:
        self._router = router
        self._sessions = sessions
        self._provider_combo = provider_combo
        self._conversation_composer = conversation_composer
        self._home_composer = home_composer

    def select(self, profile_id: str) -> None:
        self._conversation_composer.select_provider(profile_id)
        self._home_composer.select_provider(profile_id)

    def selected_identity(self) -> tuple[str, str]:
        profile_id = str(
            self._provider_combo.currentData() or "mock-default"
        )
        try:
            profile = self._router.profiles.get(profile_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return "mock-default", "form-assistant-mock"
        return profile.profile_id, profile.model_id

    def synchronize_session(self, session: AssistantSession) -> AssistantSession:
        try:
            profile = self._router.profiles.get(session.provider_profile_id)
        except (KeyError, OSError, RuntimeError, TypeError, ValueError):
            return session
        if session.model_id == profile.model_id:
            return session
        return self._sessions.update_state(session, model_id=profile.model_id)

    def failure_message(self, profile_id: str, error: Exception) -> str:
        readiness = self._router.readiness(profile_id)
        if not readiness.ready and readiness.message:
            return readiness.message
        text = str(error or "").strip()
        return (
            provider_error_text(text)
            if text
            else "模型连接暂不可用，请检查配置后重试"
        )


__all__ = ["ProviderSelectionCoordinator"]
