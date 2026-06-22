"""
Financial calculator tests — exact FY 2025-26 amounts, fully offline.
Run:  python -m pytest tests/test_calculators.py   OR   python tests/test_calculators.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tool_service import calculate_income_tax, calculate_tds_on_fd_interest


def _tax(income, age, regime):
    return calculate_income_tax.invoke({"total_income": income, "age": age, "regime": regime})


def _tds(age, interest, pan):
    return calculate_tds_on_fd_interest.invoke({"age": age, "fd_interest": interest, "pan_available": pan})


# ─── New regime (FY25-26) ────────────────────────────────────────────────────

def test_new_regime_rebate_makes_12L_zero():
    # 87A rebate: taxable income up to ₹12L is effectively nil.
    assert _tax(1200000, 35, "new")["total_tax_liability"] == 0.0


def test_new_regime_16L():
    # slabs: 4-8L@5%=20000, 8-12L@10%=40000, 12-16L@15%=60000 = 120000; +4% cess
    assert _tax(1600000, 35, "new")["total_tax_liability"] == 124800.0


# ─── Old regime (FY25-26) ────────────────────────────────────────────────────

def test_old_regime_5L_rebate_zero():
    # 87A rebate (up to ₹12,500) zeroes tax at ₹5L taxable.
    assert _tax(500000, 35, "old")["total_tax_liability"] == 0.0


def test_old_regime_10L_below60():
    # 2.5-5L@5%=12500, 5-10L@20%=100000 = 112500; +4% cess = 117000
    assert _tax(1000000, 35, "old")["total_tax_liability"] == 117000.0


def test_old_regime_senior_higher_exemption():
    # Senior (60-79): first ₹3L nil → 5-10L band gives 10000 + 100000 = 110000; +cess
    assert _tax(1000000, 65, "old")["total_tax_liability"] == 114400.0


def test_both_returns_recommendation():
    r = _tax(1500000, 35, "both")
    assert "old_regime_tax_liability" in r and "new_regime_tax_liability" in r
    assert r["recommendation"] in ("old", "new")


# ─── TDS on FD interest (FY25-26 §194A) ──────────────────────────────────────

def test_tds_senior_threshold_is_1lakh():
    # FY25-26 raised senior threshold to ₹1,00,000 — ₹80k interest = NO TDS.
    # (The old code used ₹50k and would have wrongly deducted.)
    r = _tds(65, 80000, True)
    assert r["threshold_hit"] is False and r["deductible_tds"] == 0.0


def test_tds_senior_above_threshold():
    r = _tds(65, 120000, True)
    assert r["threshold_hit"] is True and r["deductible_tds"] == 12000.0  # 10% with PAN


def test_tds_non_senior_threshold_is_50k():
    # FY25-26 raised non-senior threshold to ₹50,000 — ₹45k = NO TDS.
    assert _tds(40, 45000, True)["threshold_hit"] is False


def test_tds_no_pan_doubles_rate():
    r = _tds(40, 60000, False)
    assert r["deductible_tds"] == 12000.0  # 20% without PAN


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  PASS  {fn.__name__}")
    print(f"\n{len(fns)}/{len(fns)} calculator tests passed")


if __name__ == "__main__":
    _run()
