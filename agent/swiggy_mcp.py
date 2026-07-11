"""Swiggy MCP client with a hard whitelist.

SAFETY BY CONSTRUCTION: only SEARCH tools are ever exposed to the agent.
Order-placing tools are not in the whitelist, therefore the agent cannot
call them — no prompt injection or model mistake can place an order.

Until you're approved at mcp.swiggy.com/builders, SWIGGY_MOCK=true serves
realistic mock dishes so the whole flow works end-to-end today.
"""
from app.config import settings

ALLOWED_TOOLS = {"search_restaurants", "get_menu"}   # NEVER add order/cart tools

MOCK_DISHES = [
    {"restaurant": "Grill Nation, Koramangala", "dish": "Tandoori Chicken (Half)",
     "price": 289, "description": "Char-grilled half chicken, mint chutney"},
    {"restaurant": "Grill Nation, Koramangala", "dish": "Chicken Tikka (8 pc)",
     "price": 249, "description": "Boneless tikka, onion salad"},
    {"restaurant": "Wok Story", "dish": "Chilli Chicken Dry",
     "price": 219, "description": "Indo-Chinese, bell peppers, less oil on request"},
    {"restaurant": "Ghar Ka Khana", "dish": "Egg Curry + 2 Roti",
     "price": 149, "description": "Homestyle, 2 eggs"},
    {"restaurant": "Protein Bowl Co", "dish": "Paneer Tikka Bowl",
     "price": 269, "description": "150g paneer, brown rice, veggies"},
]

async def search_dishes(query: str, max_results: int = 8) -> list[dict]:
    if settings.swiggy_mock:
        q = query.lower()
        hits = [d for d in MOCK_DISHES if any(w in (d["dish"] + d["description"]).lower()
                                              for w in q.split())] or MOCK_DISHES
        return hits[:max_results]
    # --- Real MCP path (fill in after Builders Club approval) ---
    # Connect to settings.swiggy_mcp_url with settings.swiggy_mcp_token using the
    # `mcp` python client; list tools; assert every tool you register is in
    # ALLOWED_TOOLS; call search_restaurants/get_menu near (USER_LAT, USER_LNG).
    raise NotImplementedError("Set SWIGGY_MOCK=true or implement MCP connection")
