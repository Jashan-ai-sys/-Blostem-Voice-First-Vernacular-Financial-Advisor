from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
import operator
from langchain_core.messages import AnyMessage

class JourneyState(TypedDict):
    stage: str  # discovery, profiling, comparison, decision_support, action_readiness
    next_best_action: Optional[str]

class Profile(TypedDict):
    name: Optional[str]
    age: Optional[int]
    city: Optional[str]
    employment_type: Optional[str]
    senior_citizen: Optional[bool]

class FinancialState(TypedDict):
    monthly_income: Optional[float]
    annual_income: Optional[float]
    cash_available_for_fd: Optional[float]
    existing_fd_amount: Optional[float]
    savings_balance: Optional[float]
    tax_regime: Optional[str]
    pan_available: bool

class Preferences(TypedDict):
    language: str
    bank_preference: List[str]
    tenure_preference_months: Optional[int]
    liquidity_need: str  # high, medium, low
    risk_appetite: str   # low, medium, high
    goal_type: Optional[str]

class RecommendationContext(TypedDict):
    eligible_for_15g: Optional[bool]
    eligible_for_15h: Optional[bool]
    recommended_fd_type: Optional[str]
    reason_codes: List[str]

class AgentState(TypedDict):
    # The list of chat messages
    messages: Annotated[list[AnyMessage], operator.add]
    
    # Session ID
    user_id: str
    
    # User state segments
    profile: Profile
    financial_state: FinancialState
    preferences: Preferences
    journey_state: JourneyState
    recommendation_context: RecommendationContext

def get_initial_state(user_id: str) -> AgentState:
    """Returns a fully mocked initial state for the 3-minute hackathon demo."""
    return {
        "messages": [],
        "user_id": user_id,
        "profile": {
            "name": "Ramesh", "age": 65, "city": "Mumbai", 
            "employment_type": "Retired", "senior_citizen": True
        },
        "financial_state": {
            "monthly_income": 40000.0, "annual_income": 480000.0, 
            "cash_available_for_fd": 500000.0, "existing_fd_amount": 0.0, 
            "savings_balance": 550000.0, "tax_regime": "old", "pan_available": True
        },
        "preferences": {
            "language": "hinglish", "bank_preference": ["SBI", "HDFC"], 
            "tenure_preference_months": 36, "liquidity_need": "high", 
            "risk_appetite": "low", "goal_type": "tax_saving"
        },
        "journey_state": {
            "stage": "amount_tenure_selection", "next_best_action": "recommend_fd"
        },
        "recommendation_context": {
            "eligible_for_15g": False, "eligible_for_15h": True,
            "recommended_fd_type": None, "reason_codes": []
        }
    }
