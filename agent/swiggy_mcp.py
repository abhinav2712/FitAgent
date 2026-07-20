"""Swiggy MCP clients (Food + Instamart) with a hard whitelist per service.

SAFETY BY CONSTRUCTION: Food's MCP server exposes 14 tools including cart,
coupon, and place_food_order; Instamart's exposes 13 including cart/checkout
and address management — both against PRODUCTION Swiggy. Only the read-only
search tools below can ever be called, and the agent never sees Swiggy tool
names at all (it gets our search_swiggy / search_instamart facades). No
prompt injection or model mistake can place an order or touch an address.

Auth is OAuth 2.1 + PKCE (phone + OTP, browser) — per user, linked once via
`python -m app.swiggy_auth <user_id>`; the 5-day Bearer token lives on the
users row and is shared by both services. SWIGGY_MOCK=true serves realistic
mock data so the whole flow works without a linked account.
"""
from app.config import settings

FOOD_ALLOWED_TOOLS = {"search_restaurants", "search_menu", "get_restaurant_menu"}
# Instamart's search needs a saved delivery address, not raw coordinates —
# get_addresses is READ-ONLY (views saved addresses; create/delete are not
# whitelisted) and exists solely to resolve the addressId search_products needs.
INSTAMART_ALLOWED_TOOLS = {"search_products", "get_addresses"}
# NEVER add cart/order/checkout/coupon/create_address/delete_address tools
# to either set. Whitelist, not blocklist.

class SwiggyToolBlocked(Exception):
    pass

def _assert_allowed(service: str, tool: str):
    """Fail closed before any network call. This is the load-bearing check."""
    allowed = FOOD_ALLOWED_TOOLS if service == "food" else INSTAMART_ALLOWED_TOOLS
    if tool not in allowed:
        raise SwiggyToolBlocked(f"tool '{tool}' is not in the {service} read-only whitelist")

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

# Grocery/packaged snacks worth keeping on hand — the pantry-stocking flavor
# of a recommendation, distinct from a one-off restaurant order.
MOCK_INSTAMART_ITEMS = [
    {"brand": "Yogabar", "item": "Peanut Protein Bar", "pack_size": "40g",
     "price": 49, "description": "10g protein, no added sugar"},
    {"brand": "Happilo", "item": "Roasted Makhana", "pack_size": "100g",
     "price": 99, "description": "Foxnuts roasted in olive oil, lightly salted"},
    {"brand": "Epigamia", "item": "Greek Yogurt Cup", "pack_size": "90g",
     "price": 40, "description": "High-protein, unsweetened plain"},
    {"brand": "The Whole Truth", "item": "Protein Bar — Peanut Butter",
     "pack_size": "52g", "price": 89, "description": "No added sugar, 20g protein"},
    {"brand": "Nutraj", "item": "Mixed Nuts & Seeds", "pack_size": "200g",
     "price": 249, "description": "Almonds, walnuts, pumpkin seeds"},
    {"brand": "Too Yumm", "item": "Multigrain Chips — Tomato",
     "pack_size": "70g", "price": 30, "description": "Baked not fried"},
    {"brand": "RiteBite", "item": "Max Protein Chips — Peri Peri",
     "pack_size": "25g", "price": 35, "description": "High protein savory snack"},
    {"brand": "Sattva", "item": "Sprouted Moong (frozen)",
     "pack_size": "200g", "price": 59, "description": "Steam-ready, high fibre"},
    {"brand": "Nutty Yogi", "item": "Roasted Chana", "pack_size": "150g",
     "price": 69, "description": "High protein, high fibre snack"},
    {"brand": "Whey Wolf", "item": "Whey Protein Sachet", "pack_size": "30g",
     "price": 79, "description": "25g protein per scoop, mixes with water/milk"},
]

async def search_dishes(query: str, user: dict | None = None, max_results: int = 8):
    """Restaurant dishes for delivery — one-off meals."""
    if settings.swiggy_mock:
        q = query.lower()
        hits = [d for d in MOCK_DISHES if any(w in (d["dish"] + d["description"]).lower()
                                              for w in q.split())] or MOCK_DISHES
        return hits[:max_results]
    return await _search_food_real(query, user or {})

async def search_grocery_items(query: str, user: dict | None = None, max_results: int = 8):
    """Instamart grocery/snack items — things to keep in the pantry, not a
    single meal. Same whitelist discipline as search_dishes."""
    if settings.swiggy_mock:
        q = query.lower()
        hits = [d for d in MOCK_INSTAMART_ITEMS
                if any(w in (d["item"] + d["brand"] + d["description"]).lower()
                       for w in q.split())] or MOCK_INSTAMART_ITEMS
        return hits[:max_results]
    return await _search_instamart_real(query, user or {})

async def _call_swiggy(user: dict, service: str, endpoint: str, tool: str, args: dict) -> str:
    """One whitelisted tool call over MCP streamable HTTP. Returns the tool's
    text content; auth problems come back as strings the agent can relay."""
    _assert_allowed(service, tool)
    token = user.get("swiggy_token")
    if not token:
        return ("Swiggy account not linked. Tell the user to run: "
                "python -m app.swiggy_auth <their user id> (one-time phone+OTP).")
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    try:
        async with streamablehttp_client(
                endpoint, headers={"Authorization": f"Bearer {token}"}) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool, args)
                texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
                return "\n".join(texts)[:4000] or "(empty result)"
    except Exception as e:  # 401/419 = expired session; surface, don't crash the run
        return f"Swiggy MCP error ({e}). If this mentions 401/419, the user must re-link via app.swiggy_auth."

async def _search_food_real(query: str, user: dict) -> dict:
    """Dish-level search near the user. Swiggy's menu data has no macros —
    the agent estimates them and must label numbers 'est.'."""
    out = await _call_swiggy(user, "food", settings.swiggy_mcp_url, "search_menu", {
        "query": query,
        "lat": float(user.get("lat") or settings.user_lat),
        "lng": float(user.get("lng") or settings.user_lng),
    })
    return {"source": "swiggy_live", "results": out}

async def _search_instamart_real(query: str, user: dict) -> dict:
    """Instamart needs a saved delivery addressId, not lat/lng — resolve the
    user's first saved address (read-only lookup), then search products
    against it. If they've never saved a Swiggy address, we say so instead
    of guessing; we never call create_address (that's a write, out of scope)."""
    addr_json = await _call_swiggy(user, "instamart", settings.swiggy_instamart_mcp_url,
                                   "get_addresses", {})
    if "Swiggy account not linked" in addr_json or "Swiggy MCP error" in addr_json:
        return {"source": "swiggy_live", "results": addr_json}
    import json as _json
    try:
        addresses = _json.loads(addr_json)
        address_id = (addresses[0] or {}).get("id") if addresses else None
    except (ValueError, IndexError, AttributeError, TypeError):
        address_id = None
    if not address_id:
        return {"source": "swiggy_live",
                "results": "No saved Instamart delivery address on this Swiggy account. "
                           "Add one address in the Swiggy app first, then ask again."}
    out = await _call_swiggy(user, "instamart", settings.swiggy_instamart_mcp_url,
                             "search_products", {"query": query, "addressId": address_id})
    return {"source": "swiggy_live", "results": out}
