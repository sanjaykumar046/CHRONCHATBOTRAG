from django.core.cache import cache


class SessionStore:
    """
    Stores pending "ASK_USER" context per session_id so that when the
    user replies with a missing value, the pipeline resumes from where
    it left off instead of starting over.

    KEY STRATEGY
    ------------
    The PHP bridge does not always send a stable session_id across
    turns (it may generate a new UUID per request). To handle this,
    we store the context under TWO keys simultaneously:

        1. session_id key  — used when a consistent session_id is
                             provided (the normal, ideal case).
        2. userid key      — fallback for when session_id changes
                             between turns. Keyed to the logged-in
                             user's EMPID, so only one pending context
                             per user at a time.

    load() checks session_id first, then falls back to userid.
    save() writes to both.
    clear() removes both.

    Backed by Django diskcache — survives across requests and
    worker processes unlike LocMemCache.
    """

    _TTL_SECONDS = 600       # 10 minutes
    _SESSION_PREFIX = "askuser_session"
    _USER_PREFIX    = "askuser_user"
    _HISTORY_SESSION_PREFIX = "history_session"
    _HISTORY_USER_PREFIX    = "history_user"

    # ----------------------------------------------------------
    # Key builders
    # ----------------------------------------------------------

    def _session_key(self, session_id: str) -> str:
        return f"{self._SESSION_PREFIX}:{session_id}"

    def _user_key(self, userid: str) -> str:
        return f"{self._USER_PREFIX}:{userid}"

    def _history_session_key(self, session_id: str) -> str:
        return f"{self._HISTORY_SESSION_PREFIX}:{session_id}"

    def _history_user_key(self, userid: str) -> str:
        return f"{self._HISTORY_USER_PREFIX}:{userid}"

    # ----------------------------------------------------------
    # Public API - Pending Sessions
    # ----------------------------------------------------------

    def save(self, session_id: str, context: dict, userid: str = None):
        if session_id:
            cache.set(self._session_key(session_id), context,
                      timeout=self._TTL_SECONDS)
        if userid:
            cache.set(self._user_key(userid), context,
                      timeout=self._TTL_SECONDS)

    def load(self, session_id: str, userid: str = None):
        # Try session_id first (most precise)
        if session_id:
            ctx = cache.get(self._session_key(session_id))
            if ctx is not None:
                return ctx
        # Fall back to userid (handles PHP bridge session_id drift)
        if userid:
            return cache.get(self._user_key(userid))
        return None

    def clear(self, session_id: str, userid: str = None):
        if session_id:
            cache.delete(self._session_key(session_id))
        if userid:
            cache.delete(self._user_key(userid))

    # ----------------------------------------------------------
    # Public API - Conversation History
    # ----------------------------------------------------------

    def save_turn(self, session_id: str, user_message: str, bot_reply: str, userid: str = None):
        history = self.get_history(session_id, userid=userid, limit=6)
        history.append({
            "user": user_message,
            "assistant": bot_reply
        })
        # Keep last 6 turns
        history = history[-6:]

        if session_id:
            cache.set(self._history_session_key(session_id), history,
                      timeout=self._TTL_SECONDS)
        if userid:
            cache.set(self._history_user_key(userid), history,
                      timeout=self._TTL_SECONDS)

    def get_history(self, session_id: str, userid: str = None, limit: int = 3) -> list:
        history = None
        if session_id:
            history = cache.get(self._history_session_key(session_id))
        if history is None and userid:
            history = cache.get(self._history_user_key(userid))

        if not history or not isinstance(history, list):
            return []
        return history[-limit:]
