"""Invariant #2: Swiggy is read-only by construction. The whitelist is the
load-bearing safety property — these tests make weakening it a red build."""
import pytest
from agent.swiggy_mcp import ALLOWED_TOOLS, SwiggyToolBlocked, _assert_allowed

FORBIDDEN_MARKERS = ("order", "cart", "checkout", "coupon", "pay", "address")

def test_whitelist_contains_no_write_capable_tools():
    for tool in ALLOWED_TOOLS:
        assert not any(m in tool for m in FORBIDDEN_MARKERS), \
            f"'{tool}' looks write-capable — the whitelist must stay search-only"

def test_known_dangerous_swiggy_tools_are_blocked():
    """The real Food MCP tool names, verbatim from Swiggy's docs — every one
    of these calls production Swiggy and must never pass the gate."""
    for tool in ("place_food_order", "update_food_cart", "get_food_cart",
                 "flush_food_cart", "apply_food_coupon", "fetch_food_coupons",
                 "get_addresses", "get_food_orders", "track_food_order"):
        with pytest.raises(SwiggyToolBlocked):
            _assert_allowed(tool)

def test_search_tools_pass_the_gate():
    for tool in ("search_restaurants", "search_menu", "get_restaurant_menu"):
        _assert_allowed(tool)
