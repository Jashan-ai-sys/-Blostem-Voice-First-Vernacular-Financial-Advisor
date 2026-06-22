from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.tools import tool

# ─── 1. FD Maturity Calculator ─────────────────────────────────────────────
class FDMaturityInput(BaseModel):
    principal: float = Field(gt=0, description="The initial amount invested in the FD.")
    annual_rate_percent: float = Field(gt=0, description="Annual interest rate percentage (e.g., 7.5).")
    tenure_years: float = Field(gt=0, description="Duration of the FD in years.")
    compounding_frequency: Literal["yearly", "half_yearly", "quarterly", "monthly"] = Field(
        description="How often the interest compounds."
    )

@tool("calculate_fd_maturity", args_schema=FDMaturityInput)
def calculate_fd_maturity(principal: float, annual_rate_percent: float, tenure_years: float, compounding_frequency: str) -> dict:
    """Calculates the final maturity amount and total interest earned for a fixed deposit using compound interest."""
    freq_map = {"yearly": 1, "half_yearly": 2, "quarterly": 4, "monthly": 12}
    n = freq_map[compounding_frequency]
    r = annual_rate_percent / 100
    
    amount = principal * ((1 + r / n) ** (n * tenure_years))
    interest = amount - principal
    
    return {
        "maturity_amount": round(amount, 2),
        "interest_earned": round(interest, 2)
    }

# ─── 2. TDS Calculator ─────────────────────────────────────────────────────
class TDSInput(BaseModel):
    age: int = Field(gt=0, description="Age of the individual.")
    fd_interest: float = Field(ge=0, description="Total projected or earned FD interest for the year.")
    pan_available: bool = Field(description="Whether the individual has linked their PAN card.")

@tool("calculate_tds_on_fd_interest", args_schema=TDSInput)
def calculate_tds_on_fd_interest(age: int, fd_interest: float, pan_available: bool) -> dict:
    """Determines if TDS applies to the FD interest and calculates the deductible amount based on age and PAN status."""
    # Section 194A thresholds, FY 2025-26 (raised in Budget 2025):
    # senior citizens (60+) ₹1,00,000; others ₹50,000.
    threshold = 100000 if age >= 60 else 50000

    if fd_interest <= threshold:
        return {
            "threshold_hit": False,
            "deductible_tds": 0.0,
            "explanation": f"Interest is at or below the ₹{threshold:,} FY25-26 threshold. No TDS."
        }

    rate = 0.10 if pan_available else 0.20
    deductible_tds = fd_interest * rate

    return {
        "threshold_hit": True,
        "deductible_tds": round(deductible_tds, 2),
        "explanation": f"Interest exceeds the ₹{threshold:,} threshold; TDS at {int(rate*100)}% "
                       f"({'PAN linked' if pan_available else 'no PAN'})."
    }

# ─── 3. Income Tax Calculator (Simplified for MVP) ──────────────────────────
class IncomeTaxInput(BaseModel):
    total_income: float = Field(ge=0, description="Total annual income.")
    age: int = Field(gt=0, description="Age of the taxpayer.")
    regime: Literal["old", "new", "both"] = Field(default="both", description="Tax regime preference. Pass 'both' to compare.")

# ─── FY 2025-26 (AY 2026-27) income-tax slabs ──────────────────────────────
# Each table is a list of (upper_bound, marginal_rate); the last band is open-ended.
_INF = float("inf")
_NEW_REGIME = [(400000, 0.0), (800000, 0.05), (1200000, 0.10),
               (1600000, 0.15), (2000000, 0.20), (2400000, 0.25), (_INF, 0.30)]
_OLD_BELOW_60 = [(250000, 0.0), (500000, 0.05), (1000000, 0.20), (_INF, 0.30)]
_OLD_SENIOR = [(300000, 0.0), (500000, 0.05), (1000000, 0.20), (_INF, 0.30)]
_OLD_SUPER_SENIOR = [(500000, 0.0), (1000000, 0.20), (_INF, 0.30)]
_CESS = 0.04  # Health & Education Cess on tax


def _slab_tax(income: float, slabs: list) -> float:
    tax, lower = 0.0, 0.0
    for upper, rate in slabs:
        if income > lower:
            tax += (min(income, upper) - lower) * rate
            lower = upper
        else:
            break
    return tax


def _new_regime_tax(taxable_income: float) -> float:
    tax = _slab_tax(taxable_income, _NEW_REGIME)
    if taxable_income <= 1200000:  # Section 87A rebate makes it effectively nil
        tax = 0.0
    return round(tax * (1 + _CESS), 2)


def _old_regime_tax(taxable_income: float, age: int) -> float:
    slabs = _OLD_SUPER_SENIOR if age >= 80 else _OLD_SENIOR if age >= 60 else _OLD_BELOW_60
    tax = _slab_tax(taxable_income, slabs)
    if taxable_income <= 500000:  # Section 87A rebate (up to ₹12,500)
        tax = max(0.0, tax - 12500)
    return round(tax * (1 + _CESS), 2)


@tool("calculate_income_tax", args_schema=IncomeTaxInput)
def calculate_income_tax(total_income: float, age: int, regime: str = "both") -> dict:
    """Calculates income tax for FY 2025-26 (AY 2026-27) using real slabs, the
    Section 87A rebate, and 4% cess. `total_income` is taken as taxable income."""
    note = ("FY 2025-26 (AY 2026-27) slabs, incl. Section 87A rebate and 4% cess. "
            "Assumes total_income is taxable income (after deductions). "
            "Surcharge for very high incomes not included.")

    if regime == "both":
        new_tax = _new_regime_tax(total_income)
        old_tax = _old_regime_tax(total_income, age)
        return {
            "old_regime_tax_liability": old_tax,
            "new_regime_tax_liability": new_tax,
            "recommendation": "new" if new_tax <= old_tax else "old",
            "note": note,
        }

    tax = _new_regime_tax(total_income) if regime == "new" else _old_regime_tax(total_income, age)
    return {"regime_used": regime, "total_tax_liability": tax, "note": note}

# ─── Shared RAG engine ──────────────────────────────────────────────────────
# Calculators are invoked by main.py's tool endpoints; the voice agent and
# frontend reach RAG/profile via those HTTP endpoints, so the LangChain @tool
# wrappers for search/profile are not bound here.
from app.rag import RAGEngine

rag_engine = RAGEngine()
rag_engine.initialize()


# ─── Term Explainer (RAG-grounded) ──────────────────────────────────────────

class ExplainTermInput(BaseModel):
    term: str = Field(description="The specific financial term or concept the user wants explained (e.g., 'compound interest', 'FD', 'TDS').")
    language: str = Field(default="en", description="The language code to explain the term in ('en', 'hi', 'pa'). Default is 'en'.")

@tool("explain_term", args_schema=ExplainTermInput)
def explain_term(term: str, language: str = "en") -> dict:
    """Returns official knowledge-base context for a financial term. Grounded in
    RAG (no extra LLM call) — the conversational model phrases it for the user.

    Fully wrapped: never raises (so the endpoint can't 500). If nothing is found
    it says so explicitly, so the model won't invent a definition."""
    try:
        sources = rag_engine.retrieve_chunks(f"What is {term}?")
        if sources and sources[0].text.strip():
            context = " ".join(s.text for s in sources[:2])[:800]
            return {"term": term, "explanation": context, "found": True}
        return {
            "term": term, "found": False,
            "explanation": f"No official definition found for '{term}'. Tell the user you "
                           f"couldn't find it and suggest verifying with the bank — do not invent one.",
        }
    except Exception as e:
        print(f"explain_term error: {e}")
        return {
            "term": term, "found": False,
            "explanation": f"Couldn't fetch an explanation for '{term}' right now. "
                           f"Tell the user to try again shortly — do not invent one.",
        }

