"""
Voice Agent — Tool Schemas
==========================
Gemini Live function-calling schemas for the Blostem voice agent. Kept separate
from voice_agent.py so the pipeline file stays focused on orchestration. The
handler implementations live in voice_agent.py and are bound to these by name.
"""

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema


SEARCH_RULES_TOOL = FunctionSchema(
    name="search_financial_rules",
    description="Search official knowledge base for rules, FDs, TDS, savings, etc.",
    properties={
        "query": {"type": "string", "description": "Search query"},
    },
    required=["query"],
)

CALC_MATURITY_TOOL = FunctionSchema(
    name="calculate_fd_maturity",
    description="Calculates final maturity amount and total interest earned for a fixed deposit.",
    # Numeric params declared as "string": Groq/Llama emit numbers as strings and
    # strict tool validation rejects them against "number"; the backend Pydantic
    # models (float/int) coerce the strings back. Same workaround as the booleans.
    properties={
        "principal": {"type": "string", "description": "Initial amount invested, as a number e.g. '100000'"},
        "annual_rate_percent": {"type": "string", "description": "Annual interest rate percentage as a number e.g. '7.5'"},
        "tenure_years": {"type": "string", "description": "Duration in years as a number e.g. '5'"},
        "compounding_frequency": {
            "type": "string",
            "enum": ["yearly", "half_yearly", "quarterly", "monthly"],
            "description": "How often interest compounds",
        },
    },
    required=["principal", "annual_rate_percent", "tenure_years", "compounding_frequency"],
)

RECOMMEND_FD_TOOL = FunctionSchema(
    name="recommend_fd_options",
    description="A rule-based scoring engine that recommends FDs based on the user's profile.",
    properties={
        "goal_type": {"type": "string", "description": "Financial goal, e.g., 'tax_saving' or 'growth'."},
        "liquidity_need": {"type": "string", "description": "Liquidity need: 'high', 'medium', or 'low'."},
        "senior_citizen": {"type": "string", "enum": ["true", "false"], "description": "Whether the user is a senior citizen: 'true' or 'false'."},
    },
    required=["goal_type", "liquidity_need", "senior_citizen"],
)

UPDATE_PROFILE_TOOL = FunctionSchema(
    name="update_user_profile",
    description="Call this tool if the user explicitly changes their age or investment amount.",
    properties={
        "new_cash_amount": {"type": "string", "description": "The new amount the user wants to invest, as a number e.g. '500000'."},
        "new_age": {"type": "string", "description": "The user's updated age, as a number e.g. '60'."},
        "confirm": {"type": "string", "enum": ["true", "false"], "description": "Set 'true' ONLY after the user has explicitly confirmed the change. 'false' first → the system returns a confirmation prompt; the change is applied only on 'true'."},
    },
    required=[],
)

CALC_INCOME_TAX_TOOL = FunctionSchema(
    name="calculate_income_tax",
    description="Calculates basic income tax liability using old vs new tax regimes. Use when asked to calculate tax.",
    properties={
        "total_income": {"type": "string", "description": "Total annual income, as a number e.g. '1500000'."},
        "age": {"type": "string", "description": "Age of the taxpayer, as a number e.g. '65'."},
        "regime": {"type": "string", "enum": ["old", "new", "both"], "description": "Tax regime preference. Pass 'both' to compare."},
    },
    required=["total_income", "age", "regime"],
)

CALC_TDS_TOOL = FunctionSchema(
    name="calculate_tds_on_fd_interest",
    description="Determines if TDS applies to FD interest based on age and PAN.",
    properties={
        "age": {"type": "string", "description": "Age of the individual, as a number e.g. '65'."},
        "fd_interest": {"type": "string", "description": "Total projected FD interest, as a number e.g. '120000'."},
        "pan_available": {"type": "string", "enum": ["true", "false"], "description": "Whether PAN card is linked: 'true' or 'false'."},
    },
    required=["age", "fd_interest", "pan_available"],
)

GET_SCREEN_TOOL = FunctionSchema(
    name="get_current_screen_context",
    description="Retrieves the exact screen name and step the user is currently looking at in the UI. Call this when the user needs help navigating.",
    # No parameters: a required boolean here made Groq/Llama emit "true" (string)
    # and fail strict schema validation. The tool always just fetches the screen.
    properties={},
    required=[],
)

EXPLAIN_TERM_TOOL = FunctionSchema(
    name="explain_term",
    description="Explains a specific financial term in simple language. Call this when the user asks what a complex financial term means.",
    properties={
        "term": {"type": "string", "description": "The specific financial term to explain."},
        "language": {"type": "string", "description": "The language code, e.g. 'en', 'hi', or 'pa'. Defaults to 'en'."}
    },
    required=["term"],
)

HIGHLIGHT_FIELD_TOOL = FunctionSchema(
    name="highlight_field",
    description="Visually point the user to a specific field/element on the CURRENT screen by highlighting it (optionally with a short tooltip). Use when guiding them to where to look or act — e.g. highlight the PAN field when explaining a PAN error.",
    properties={
        "field": {"type": "string", "description": "Field/element key on the current screen, e.g. 'pan', 'amount', 'tenure', 'nominee', 'email'."},
        "message": {"type": "string", "description": "Optional short tooltip shown on the field."},
    },
    required=["field"],
)

TOOLS = ToolsSchema(
    standard_tools=[
        SEARCH_RULES_TOOL, CALC_MATURITY_TOOL, RECOMMEND_FD_TOOL, UPDATE_PROFILE_TOOL,
        CALC_INCOME_TAX_TOOL, CALC_TDS_TOOL, GET_SCREEN_TOOL, EXPLAIN_TERM_TOOL,
        HIGHLIGHT_FIELD_TOOL,
    ],
)
