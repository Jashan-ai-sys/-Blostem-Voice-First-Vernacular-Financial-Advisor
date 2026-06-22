"""
Request-scoped retrieval scope — tenant + metadata filters.

The retrieval stack (RAGEngine → HybridRetriever → dense_search) doesn't thread a
tenant/filter argument through every layer. Instead the request handler sets a
ContextVar for the duration of the call, and `rag._dense_search` reads it to scope
the vector search:

  • tenant  → search ONLY that tenant's collection (true search-space isolation)
  • filters → keep only chunks whose metadata matches (post-filter)

ContextVars are per-task, so concurrent requests don't see each other's scope.
(Valid as long as retrieval runs inline in the request task; if retrieval is ever
offloaded to a worker thread, copy the context with contextvars.copy_context.)
"""
from contextlib import contextmanager
from contextvars import ContextVar

_scope: ContextVar[dict] = ContextVar("retrieval_scope", default={})


def current() -> dict:
    """{'tenant': str|None, 'filters': dict|None} for the active request."""
    return _scope.get()


@contextmanager
def scope(tenant: str | None = None, filters: dict | None = None):
    token = _scope.set({"tenant": tenant or None, "filters": filters or None})
    try:
        yield
    finally:
        _scope.reset(token)
