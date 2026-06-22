"""
Phase 14/15 guardrail tests — pure, offline.
Run:  python -m pytest tests/test_guardrails.py   OR   python tests/test_guardrails.py
"""

import os
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.guardrails import apply_guardrails, check_output_text


@dataclass
class FakeChunk:
    title: str = "Sec"
    text: str = "some evidence text"
    source_url: str = "RBI_FD_DICGC_summary.md"


def test_no_evidence_refuses():
    r = apply_guardrails("Banks pay 8% for sure.", sources=[])
    assert not r.grounded
    assert "no_evidence_refusal" in r.notes
    assert "verify" in r.text.lower()


def test_grounded_answer_carries_citations():
    r = apply_guardrails("The minimum FD tenure is 7 days.", sources=[FakeChunk()])
    assert r.grounded and not r.blocked
    assert r.citations and r.citations[0]["source"] == "RBI_FD_DICGC_summary.md"


def test_output_pii_is_masked():
    r = apply_guardrails("Your PAN ABCDE1234F is noted.", sources=[FakeChunk()])
    assert "ABCDE1234F" not in r.text
    assert "pii_masked" in r.notes


def test_misselling_claim_gets_disclaimer():
    r = apply_guardrails("This FD offers guaranteed returns of 9%.", sources=[FakeChunk()])
    assert "compliance_disclaimer" in r.notes
    assert "not personalized investment advice" in r.text.lower()


def test_toxic_output_blocked():
    r = apply_guardrails("kill yourself", sources=[FakeChunk()])
    assert r.blocked and "toxicity_blocked" in r.notes


def test_citations_dedupe_by_source():
    chunks = [FakeChunk(), FakeChunk(title="Sec2")]  # same source_url
    r = apply_guardrails("FD tenure info.", sources=chunks)
    assert len(r.citations) == 1


def test_clean_text_passthrough_when_safe():
    text, notes, blocked = check_output_text("FDs are term deposits with fixed interest.")
    assert not blocked and notes == []


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} guardrail tests passed")


if __name__ == "__main__":
    _run()
