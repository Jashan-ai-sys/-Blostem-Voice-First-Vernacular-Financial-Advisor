"""
Guardrail Service — output safety + citation enforcement (Phase 14/15)
=====================================================================
The gate every generated answer passes through before it reaches the user.

Phase 14 (hallucination prevention): an answer is only allowed if it's backed by
retrieved evidence. No evidence → we refuse and tell the user to verify with the
official source, instead of letting the LLM answer from parametric memory. Every
allowed answer carries its citations (the actual sources retrieved).

Phase 15 (output guardrails): before returning we
  - mask any PII the model echoed (Aadhaar/PAN/phone)
  - append a compliance disclaimer if the text makes a mis-selling claim
    ("guaranteed returns", "you should invest", ...)
  - block clearly abusive/toxic output

Heuristics here are deliberate, auditable, and zero-latency. The compliance and
toxicity checks are the right place to later swap in an LLM/Perspective classifier
behind the same interface — callers won't change.

This gates the TEXT path (/chat). Pure speech-to-speech voice can't be gated
before TTS; that requires the cascaded ASR→LLM→guardrail→TTS pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.pii_masker import mask_pii

# Mis-selling / prohibited-claim patterns for a regulated financial advisor.
_RISKY_CLAIMS = [
    r"guarantee\w*\s+returns?",
    r"assured\s+returns?",
    r"risk[-\s]?free",
    r"\b(you should|i recommend you|you must|definitely)\s+(invest|buy|sell)\b",
]

# Minimal obvious-abuse stub — production should use an LLM/Perspective classifier.
_TOXIC = {"idiot", "stupid bot", "kill yourself"}

_DISCLAIMER = (
    "Note: This is general information from official documents, not personalized "
    "investment advice. Please verify with your bank or a SEBI-registered advisor."
)

_REFUSAL = (
    "I couldn't find this in the official documents I have access to. Please verify "
    "with your bank or the latest RBI / official source."
)

_BLOCKED = "I'm sorry, I can't help with that."


@dataclass
class GuardrailResult:
    text: str
    grounded: bool
    citations: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    blocked: bool = False


def _has_evidence(sources) -> bool:
    return any((getattr(s, "text", "") or "").strip() for s in sources)


def _citations(sources) -> list:
    seen, out = set(), []
    for s in sources:
        src = getattr(s, "source_url", "") or getattr(s, "title", "")
        if src and src not in seen:
            seen.add(src)
            out.append({"title": getattr(s, "title", ""), "source": src})
    return out


def check_output_text(text: str) -> tuple[str, list, bool]:
    """Sanitize a model output. Returns (clean_text, notes, blocked)."""
    notes: list[str] = []
    masked = mask_pii(text)
    if masked != text:
        notes.append("pii_masked")

    low = masked.lower()
    if any(t in low for t in _TOXIC):
        return masked, notes + ["toxicity_blocked"], True

    if any(re.search(p, low) for p in _RISKY_CLAIMS):
        notes.append("compliance_disclaimer")
        masked = masked.rstrip() + "\n\n" + _DISCLAIMER

    return masked, notes, False


def apply_guardrails(answer: str, sources, query: str | None = None) -> GuardrailResult:
    """Phase 14 + 15 gate. Refuse if ungrounded; otherwise sanitize and cite."""
    if not _has_evidence(sources):
        return GuardrailResult(text=_REFUSAL, grounded=False, notes=["no_evidence_refusal"])

    text, notes, blocked = check_output_text(answer)
    if blocked:
        return GuardrailResult(text=_BLOCKED, grounded=False, notes=notes, blocked=True)

    return GuardrailResult(text=text, grounded=True, citations=_citations(sources), notes=notes)
