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
    threshold = 50000 if age >= 60 else 40000
    
    if fd_interest <= threshold:
        return {
            "threshold_hit": False,
            "deductible_tds": 0.0,
            "explanation": f"Interest is below the ₹{threshold} threshold. No TDS."
        }
        
    rate = 0.10 if pan_available else 0.20
    deductible_tds = fd_interest * rate
    
    return {
        "threshold_hit": True,
        "deductible_tds": round(deductible_tds, 2),
        "explanation": f"Interest exceeds the ₹{threshold} threshold. TDS applied at {rate*100}%."
    }

# ─── 3. Income Tax Calculator (Simplified for MVP) ──────────────────────────
class IncomeTaxInput(BaseModel):
    total_income: float = Field(ge=0, description="Total annual income.")
    age: int = Field(gt=0, description="Age of the taxpayer.")
    regime: Literal["old", "new", "both"] = Field(default="both", description="Tax regime preference. Pass 'both' to compare.")

@tool("calculate_income_tax", args_schema=IncomeTaxInput)
def calculate_income_tax(total_income: float, age: int, regime: str = "both") -> dict:
    """Calculates basic income tax liability (MVP logic) and compares old vs new regimes if requested."""
    
    def calc_tax(reg: str):
        tax = 0.0
        if reg == "new":
            if total_income > 700000:
                tax = (total_income - 700000) * 0.10
        else:
            exemption = 300000 if age >= 60 else 250000
            if total_income > exemption:
                tax = (total_income - exemption) * 0.20
        return round(tax, 2)
        
    if regime == "both":
        return {
            "old_regime_tax_liability": calc_tax("old"),
            "new_regime_tax_liability": calc_tax("new"),
            "recommendation": "new" if calc_tax("new") < calc_tax("old") else "old",
            "note": "This is a simplified MVP tax comparison."
        }
    else:
        return {
            "regime_used": regime,
            "total_tax_liability": calc_tax(regime),
            "note": "This is a simplified MVP tax calculation."
        }

# Combine into a list that the Agent will bind
from app.recommendation_engine import recommend_fd_options
from app.rag import RAGEngine

# Initialize RAG Engine globally for the tool
rag_engine = RAGEngine()
rag_engine.initialize()

class RAGInput(BaseModel):
    query: str = Field(description="The question or search query to look up in the financial knowledge base.")

@tool("search_financial_rules", args_schema=RAGInput)
def search_financial_rules(query: str) -> list[dict]:
    """Searches the official knowledge base for rules, FAQs, and policies regarding FDs, TDS, savings accounts, etc."""
    sources = rag_engine.retrieve_chunks(query)
    # Return as list of dicts for LLM to parse
    import json
    return json.dumps([{"title": s.title, "content": s.text, "image_path": s.source_url} for s in sources])

class UpdateProfileInput(BaseModel):
    new_cash_amount: float = Field(default=None, description="The new amount the user wants to invest.")
    new_age: int = Field(default=None, description="The user's updated age.")

@tool("update_user_profile", args_schema=UpdateProfileInput)
def update_user_profile(new_cash_amount: float = None, new_age: int = None) -> dict:
    """Call this tool if the user explicitly changes their age, age-group, or investment amount."""
    return {"status": "success", "message": "State updated successfully in the backend!"}


# ─── 6. Term Explainer (RAG-grounded) ──────────────────────────────────────

class ExplainTermInput(BaseModel):
    term: str = Field(description="The specific financial term or concept the user wants explained (e.g., 'compound interest', 'FD', 'TDS').")
    language: str = Field(default="en", description="The language code to explain the term in ('en', 'hi', 'pa'). Default is 'en'.")

@tool("explain_term", args_schema=ExplainTermInput)
def explain_term(term: str, language: str = "en") -> dict:
    """Explains a complex financial term in simple language, grounded with official RAG knowledge base context."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.config import settings

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash", 
        temperature=0.1,
        api_key=settings.GOOGLE_API_KEY
    )

    lang_map = {"en": "English", "hi": "Hindi", "pa": "Punjabi"}
    target_lang = lang_map.get(language, "English")

    # Retrieve RAG context for grounding
    sources = rag_engine.retrieve_chunks(f"What is {term}?")
    context = "\n".join([s.text for s in sources[:2]]) if sources else "No specific bank context found."

    prompt = f"""Explain the financial term '{term}' in 1 short, simple sentence for a beginner. 
The explanation MUST be completely in the {target_lang} language.

Bank Knowledge Base Context (use if relevant):
{context}
"""

    try:
        response = llm.invoke(prompt)
        return {"explanation": response.content.strip()}
    except Exception:
        return {"explanation": "Explanation temporarily unavailable."}


CALCULATOR_TOOLS = [
    calculate_fd_maturity,
    calculate_tds_on_fd_interest,
    calculate_income_tax,
    recommend_fd_options,
    search_financial_rules,
    update_user_profile,
    explain_term
]

