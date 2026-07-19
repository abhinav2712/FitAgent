"""Swiggy MCP client with a hard whitelist.

SAFETY BY CONSTRUCTION: the Swiggy Food MCP server exposes 14 tools including
cart, coupon, and place_food_order — against PRODUCTION Swiggy. Only the three
read-only search tools below can ever be called from here, and the agent never
sees Swiggy tool names at all (it gets our search_swiggy facade). No prompt
injection or model mistake can place an order.

Auth is OAuth 2.1 + PKCE (phone + OTP, browser) — per user, linked once via
`python -m app.swiggy_auth <user_id>`; the 5-day Bearer token lives on the
users row. SWIGGY_MOCK=true serves realistic mock dishes so the whole flow
works without a linked account.
"""
from app.config import settings

ALLOWED_TOOLS = {"search_restaurants", "search_menu", "get_restaurant_menu"}
# NEVER add cart/order/checkout/coupon/address tools. Whitelist, not blocklist.

class SwiggyToolBlocked(Exception):
    pass

def _assert_allowed(tool: str):
    """Fail closed before any network call. This is the load-bearing check."""
    if tool not in ALLOWED_TOOLS:
        raise SwiggyToolBlocked(f"tool '{tool}' is not in the read-only whitelist")

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
    {"restaurant": "Protein Bowl Co", "dish": "Sprout & Peanut Chaat",
     "price": 129, "description": "Steamed moong sprouts, peanuts, lemon"},
    {"restaurant": "The Juice Yard", "dish": "Greek Yogurt Berry Cup",
     "price": 159, "description": "Unsweetened greek yogurt, seasonal berries"},
    {"restaurant": "Roast Route", "dish": "Masala Roasted Chana (100g)",
     "price": 99, "description": "Dry-roasted chickpeas, chaat masala"},
]

async def search_dishes(query: str, user: dict | None = None, max_results: int = 8):
    if settings.swiggy_mock:
        q = query.lower()
        hits = [d for d in MOCK_DISHES if any(w in (d["dish"] + d["description"]).lower()
                                              for w in q.split())] or MOCK_DISHES
        return hits[:max_results]
    return await _search_real(query, user or {})

async def _call_swiggy(user: dict, tool: str, args: dict) -> str:
    """One whitelisted tool call over MCP streamable HTTP. Returns the tool's
    text content; auth problems come back as strings the agent can relay."""
    _assert_allowed(tool)
    token = user.get("swiggy_token")
    if not token:
        return ("Swiggy account not linked. Tell the user to run: "
                "python -m app.swiggy_auth <their user id> (one-time phone+OTP).")
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    try:
        async with streamablehttp_client(
                settings.swiggy_mcp_url,
                headers={"Authorization": f"Bearer {token}"}) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, args)
                texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
                return "\n".join(texts)[:4000] or "(empty result)"
    except Exception as e:  # 401/419 = expired session; surface, don't crash the run
        return f"Swiggy MCP error ({e}). If this mentions 401/419, the user must re-link via app.swiggy_auth."

async def _search_real(query: str, user: dict) -> dict:
    """Dish-level search near the user. Swiggy's menu data has no macros —
    the agent estimates them and must label numbers 'est.'."""
    out = await _call_swiggy(user, "search_menu", {
        "query": query,
        "lat": float(user.get("lat") or settings.user_lat),
        "lng": float(user.get("lng") or settings.user_lng),
    })
    return {"source": "swiggy_live", "results": out}
