"""
Policy engine + commit point (BFSI safety backbone).

Classifies every tool as **safe** (read-only — may run freely, and be speculated
early) or **unsafe** (state-changing — submit/pay/update/change). Unsafe tools are
held at a COMMIT POINT and only execute once the plan is stable: explicit user
confirmation, a non-stale page version, and (hook) valid auth. Speculation may
start safe reads early; unsafe writes NEVER run before commit.

Default-deny: a tool not listed as safe is treated as UNSAFE.
"""
from __future__ import annotations

# Read-only tools: free to run (and to speculate on a partial transcript).
SAFE_TOOLS = {
    "search_financial_rules", "calculate_fd_maturity", "calculate_income_tax",
    "calculate_tds_on_fd_interest", "recommend_fd_options",
    "get_current_screen_context", "explain_term", "highlight_field",
}

# State-changing tools, listed for clarity/audit. (Unknown tools are unsafe too.)
UNSAFE_TOOLS = {
    "update_user_profile",
    # future enterprise writes: submit_application, make_payment, change_nominee, send_otp, place_order
}


def classify(tool: str) -> str:
    """'safe' (read-only / speculatable) or 'unsafe' (commit-gated write).
    Unknown tools default to UNSAFE — fail-safe."""
    return "safe" if tool in SAFE_TOOLS else "unsafe"


def check_commit(tool: str, *, confirmed: bool = False, state=None,
                 page_version: int | None = None) -> dict:
    """Decide whether a tool may execute NOW.

    Safe tools always pass. Unsafe tools require the commit point:
      1. explicit user confirmation,
      2. no stale page-version (don't act on an outdated screen),
      3. (hook) valid auth — extend when enterprise auth lands.

    Returns {allow, requires_confirmation, reason}.
    """
    if classify(tool) == "safe":
        return {"allow": True, "requires_confirmation": False, "reason": "safe"}

    if not confirmed:
        return {"allow": False, "requires_confirmation": True, "reason": "needs_explicit_confirmation"}

    if page_version is not None and state is not None:
        cur = (getattr(state, "page", None) or {}).get("page_version")
        if cur is not None and page_version < cur:
            return {"allow": False, "requires_confirmation": True, "reason": "stale_page_version"}

    # auth hook: when enterprise auth exists, require state.user_profile auth_level here.
    return {"allow": True, "requires_confirmation": False, "reason": "committed"}
