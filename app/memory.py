"""
Session Memory Service
======================
Per-session state, replacing the old process-global variables in main.py that
made the backend single-user. This is the seed of the future standalone
"Memory Service": all state access goes through the `StateStore` interface, so
the storage backend (in-process dict vs. Redis) can be swapped via config with
zero changes to callers.

Short-term session state (screen, rag context, conversation) lives here keyed by
`session_id`. Long-term, user-keyed profile persistence (Postgres) is a later
wave; the `SessionState.user_profile` field and the store interface are shaped so
that split won't touch handler code.
"""

from __future__ import annotations

import json
import threading
from typing import Protocol

from pydantic import BaseModel, Field

from app.config import settings

MAX_CONVERSATION_MESSAGES = 50
MAX_SCREEN_HISTORY = 20
MAX_ERROR_HISTORY = 20

DEFAULT_USER_PROFILE = {
    "age": 65,
    "senior_citizen": True,
    "cash": 500000.0,
    "language": "hinglish",
}

DEFAULT_SCREEN = "Step 1: Mobile Verification Screen"


class SessionState(BaseModel):
    """Everything we track for a single user session."""

    screen: str = DEFAULT_SCREEN
    # Flow tracking: the canonical graph screen id + position in the journey, plus
    # a capped transition history. screen (above) stays as the human-readable label.
    screen_id: str | None = None
    screen_seq: int | None = None
    screen_history: list[dict] = Field(default_factory=list)
    # Live error the user is currently seeing (classified remedy), cleared on
    # navigation; error_history is kept for the coverage-monitor/learning loop.
    active_error: dict | None = None
    error_history: list[dict] = Field(default_factory=list)
    # Rich, structured page context streamed by the SDK (route/fields/focus/errors)
    # + friction signals — the page-aware layer the realtime copilot reasons over.
    page: dict | None = None
    behavior: dict = Field(default_factory=dict)
    # Observability: was the last RAG answer served from the speculation cache?
    last_rag_spec_hit: bool = False
    user_profile: dict = Field(default_factory=lambda: dict(DEFAULT_USER_PROFILE))
    rag_image: str | None = None
    rag_text: str | None = None
    conversation: list[dict] = Field(default_factory=list)

    def add_message(self, role: str, text: str, timestamp: str) -> None:
        self.conversation.append({"role": role, "text": text, "timestamp": timestamp})
        # Cap to keep memory/payload bounded.
        if len(self.conversation) > MAX_CONVERSATION_MESSAGES:
            self.conversation = self.conversation[-MAX_CONVERSATION_MESSAGES:]

    def record_screen(self, label: str, screen_id: str | None, seq: int | None,
                      timestamp: str) -> bool:
        """Update the current screen and append to history if it actually changed.

        Returns True if this was a transition (new screen), False if a repeat."""
        changed = label != self.screen or screen_id != self.screen_id
        self.screen = label
        self.screen_id = screen_id
        self.screen_seq = seq
        if changed:
            self.screen_history.append({
                "screen": label, "screen_id": screen_id,
                "seq": seq, "timestamp": timestamp,
            })
            if len(self.screen_history) > MAX_SCREEN_HISTORY:
                self.screen_history = self.screen_history[-MAX_SCREEN_HISTORY:]
            self.active_error = None  # old error is stale once the screen changes
        return changed

    def record_error(self, error: dict) -> None:
        """Set the active error + append to capped history (for learning)."""
        self.active_error = error
        self.error_history.append(error)
        if len(self.error_history) > MAX_ERROR_HISTORY:
            self.error_history = self.error_history[-MAX_ERROR_HISTORY:]

    def set_page(self, page: dict) -> bool:
        """Store the latest page context, ignoring out-of-order (stale) updates —
        SPA navigations can arrive out of order, so a lower page_version is
        dropped. Returns True if applied."""
        new_v = (page or {}).get("page_version", 0)
        cur_v = (self.page or {}).get("page_version", -1)
        if self.page is not None and new_v < cur_v:
            return False
        self.page = page
        return True


class StateStore(Protocol):
    """Storage boundary. Implementations must be safe for concurrent access."""

    def get(self, session_id: str) -> SessionState: ...

    def save(self, session_id: str, state: SessionState) -> None: ...

    def clear_conversation(self, session_id: str) -> None: ...


class InMemoryStore:
    """Dev/default backend. Thread-safe dict. State is lost on restart."""

    def __init__(self) -> None:
        self._data: dict[str, SessionState] = {}
        self._lock = threading.RLock()

    def get(self, session_id: str) -> SessionState:
        with self._lock:
            state = self._data.get(session_id)
            if state is None:
                state = SessionState()
                self._data[session_id] = state
            # Return a copy so mutations only land via save().
            return state.model_copy(deep=True)

    def save(self, session_id: str, state: SessionState) -> None:
        with self._lock:
            self._data[session_id] = state

    def clear_conversation(self, session_id: str) -> None:
        with self._lock:
            state = self._data.get(session_id)
            if state is not None:
                state.conversation = []


class RedisStore:
    """Production backend. Survives restarts; sessions expire after TTL idle."""

    def __init__(self, url: str, ttl_seconds: int) -> None:
        import redis  # imported lazily so dev installs need no redis

        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    def get(self, session_id: str) -> SessionState:
        raw = self._client.get(self._key(session_id))
        if raw is None:
            return SessionState()
        return SessionState.model_validate(json.loads(raw))

    def save(self, session_id: str, state: SessionState) -> None:
        self._client.set(
            self._key(session_id),
            state.model_dump_json(),
            ex=self._ttl,
        )

    def clear_conversation(self, session_id: str) -> None:
        state = self.get(session_id)
        state.conversation = []
        self.save(session_id, state)


def _build_store() -> StateStore:
    backend = (settings.STATE_BACKEND or "memory").lower()
    if backend == "redis":
        return RedisStore(settings.REDIS_URL, settings.SESSION_TTL_SECONDS)
    return InMemoryStore()


# Module-level singleton selected by config.
store: StateStore = _build_store()
