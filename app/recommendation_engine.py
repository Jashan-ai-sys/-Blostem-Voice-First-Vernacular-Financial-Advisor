import json
import os
from pydantic import BaseModel, Field
from langchain_core.tools import tool

class RecommendFDInput(BaseModel):
    goal_type: str = Field(description="The user's financial goal, e.g., 'tax_saving' or 'growth'.")
    liquidity_need: str = Field(description="The user's liquidity need: 'high', 'medium', or 'low'.")
    senior_citizen: bool = Field(description="Whether the user is a senior citizen (True/False).")

@tool("recommend_fd_options", args_schema=RecommendFDInput)
def recommend_fd_options(goal_type: str, liquidity_need: str, senior_citizen: bool) -> dict:
    """A rule-based scoring engine that recommends FDs based on the user's profile and preferences."""
    
    # Load Mock Database from JSON
    file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "products.json")
    try:
        with open(file_path, "r") as f:
            fd_products = json.load(f)
    except FileNotFoundError:
        return {"error": "Product database not found."}
        
    recommendations = []
    
    for product in fd_products:
        product_score = 0
        
        # Rule 1: Goal matching
        if goal_type == "tax_saving" and product.get("type") == "tax_saving":
            product_score += 3
            
        # Rule 2: Liquidity needs
        if liquidity_need == "high":
            if product.get("lock_in", 0) > 12:
                product_score -= 2
            else:
                product_score += 2
                
        # Rule 3: Senior Citizen bonus
        rate = product.get("base_rate", 0.0)
        if senior_citizen:
            rate += 0.5
            
        # Append scored product
        recommendations.append({
            "product": product.get("name"),
            "effective_rate": rate,
            "score": product_score
        })
        
    # Sort by score descending
    recommendations = sorted(recommendations, key=lambda x: x["score"], reverse=True)
    
    return {
        "top_recommendations": recommendations[:2],
        "reason": "Scored based on age (senior citizen status), liquidity needs, and tax goals."
    }
