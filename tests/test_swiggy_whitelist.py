"""Invariant #2: Swiggy is read-only by construction. The whitelist is the
load-bearing safety property — these tests make weakening it a red build.
Two separate MCP services (Food, Instamart), two separate whitelists — a
tool allowed on one must never leak into the other's gate."""
import pytest
from agent.swiggy_mcp import (
    FOOD_ALLOWED_TOOLS, INSTAMART_ALLOWED_TOOLS, SwiggyToolBlocked, _assert_allowed,
)

FORBIDDEN_MARKERS = ("order", "cart", "checkout", "coupon", "pay", "create_address", "delete_address")

def test_no_whitelist_contains_write_capable_tools():
    for service, tools in (("food", FOOD_ALLOWED_TOOLS), ("instamart", INSTAMART_ALLOWED_TOOLS)):
        for tool in tools:
            assert not any(m in tool for m in FORBIDDEN_MARKERS), \
                f"{service}: '{tool}' looks write-capable — the whitelist must stay search-only"

def test_known_dangerous_food_tools_are_blocked():
    """Real Food MCP tool names, verbatim from Swiggy's docs — every one of
    these calls production Swiggy and must never pass the gate."""
    for tool in ("place_food_order", "update_food_cart", "get_food_cart",
                 "flush_food_cart", "apply_food_coupon", "fetch_food_coupons",
                 "get_addresses",  # Food doesn't need it — search_menu takes lat/lng directly
                 "get_food_orders", "track_food_order"):
        with pytest.raises(SwiggyToolBlocked):
            _assert_allowed("food", tool)

def test_known_dangerous_instamart_tools_are_blocked():
    """Real Instamart MCP tool names — 13 tools including cart/checkout and
    address mutation, all against production Swiggy."""
    for tool in ("checkout", "update_cart", "get_cart", "clear_cart",
                 "create_address", "delete_address",
                 "get_orders", "get_order_details", "track_order"):
        with pytest.raises(SwiggyToolBlocked):
            _assert_allowed("instamart", tool)

def test_food_search_tools_pass_the_gate():
    for tool in ("search_restaurants", "search_menu", "get_restaurant_menu"):
        _assert_allowed("food", tool)

def test_instamart_search_tools_pass_the_gate():
    # get_addresses is allowed HERE ONLY — Instamart's search_products needs a
    # saved addressId to search at all; it is read-only (no create/delete).
    for tool in ("search_products", "get_addresses"):
        _assert_allowed("instamart", tool)

def test_food_get_addresses_does_not_leak_from_instamart_whitelist():
    """The two whitelists must stay independent: Instamart legitimately allows
    get_addresses, but that must never make it pass on the Food gate."""
    with pytest.raises(SwiggyToolBlocked):
        _assert_allowed("food", "get_addresses")
