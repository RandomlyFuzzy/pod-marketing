import os
import hmac
import hashlib
import base64
import time
import httpx
from typing import Optional
from urllib.parse import quote

EBAY_API_BASE = "https://api.ebay.com"
EBAY_AUTH_BASE = "https://api.ebay.com/identity/v1"

def _headers():
    token = os.environ.get("EBAY_OAUTH_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
    }


async def ebay_search_sold_listings(
    query: str,
    limit: int = 10,
    category_id: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
) -> str:
    """Search eBay sold/completed listings for market research.

    Args:
        query: Search keywords (e.g. "custom beach tote bag")
        limit: Max results (1-100)
        category_id: eBay category ID filter (e.g. "15724" for T-Shirts)
        min_price: Minimum sold price filter
        max_price: Maximum sold price filter
    """
    params = {
        "q": query,
        "limit": min(limit, 100),
        "filter": "listingEndingSoon,completed,ended",
        "sort": "endTimeDescending",
    }
    if category_id:
        params["category_ids"] = category_id
    if min_price or max_price:
        price_filter = "price:["
        price_filter += str(min_price or 0)
        price_filter += ".."
        price_filter += str(max_price or 999999)
        price_filter += "]"
        params["filter"] = f"price:[{min_price or 0}..{max_price or 999999}]"

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{EBAY_API_BASE}/buy/browse/v1/item_summary/search",
            headers=_headers(),
            params=params,
            timeout=15,
        )
    if resp.status_code != 200:
        return f"eBay API error {resp.status_code}: {resp.text}"

    data = resp.json()
    items = data.get("itemSummaries", [])
    if not items:
        return f"No sold listings found for '{query}'."

    lines = [f"## Sold Listings: '{query}'", ""]
    for i, item in enumerate(items[:limit], 1):
        title = item.get("title", "N/A")
        price = item.get("price", {})
        amount = price.get("value", "N/A")
        currency = price.get("currency", "USD")
        condition = item.get("condition", "N/A")
        url = item.get("itemWebUrl", "")
        seller = (item.get("seller", {}) or {}).get("username", "N/A")
        bids = item.get("bidCount", 0)
        lines.append(f"{i}. **{title}**")
        lines.append(f"   Sold: {amount} {currency} | Condition: {condition} | Seller: {seller} | Bids: {bids}")
        if url:
            lines.append(f"   URL: {url}")
        lines.append("")

    return "\n".join(lines).strip()


async def ebay_search_active_listings(
    query: str,
    limit: int = 10,
    category_id: Optional[str] = None,
    sort: str = "bestMatch",
) -> str:
    """Search eBay active (current) listings.

    Args:
        query: Search keywords
        limit: Max results (1-100)
        category_id: eBay category ID filter
        sort: Sort order (bestMatch, price asc, price desc, endTimeSoonest, newListed)
    """
    params = {
        "q": query,
        "limit": min(limit, 100),
        "sort": sort,
    }
    if category_id:
        params["category_ids"] = category_id

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{EBAY_API_BASE}/buy/browse/v1/item_summary/search",
            headers=_headers(),
            params=params,
            timeout=15,
        )
    if resp.status_code != 200:
        return f"eBay API error {resp.status_code}: {resp.text}"

    data = resp.json()
    items = data.get("itemSummaries", [])
    if not items:
        return f"No active listings found for '{query}'."

    lines = [f"## Active Listings: '{query}'", ""]
    for i, item in enumerate(items[:limit], 1):
        title = item.get("title", "N/A")
        price = item.get("price", {})
        amount = price.get("value", "N/A")
        currency = price.get("currency", "USD")
        url = item.get("itemWebUrl", "")
        item_href = item.get("itemHref", "")
        lines.append(f"{i}. **{title}** — {amount} {currency}")
        if url:
            lines.append(f"   {url}")
        elif item_href:
            lines.append(f"   {item_href}")
        lines.append("")

    return "\n".join(lines).strip()


async def ebay_get_listing_details(item_id: str) -> str:
    """Get detailed info for a specific eBay listing by item ID.

    Args:
        item_id: The eBay item ID (e.g. "v1|395681234567|0")
    """
    encoded_id = quote(item_id, safe="")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{EBAY_API_BASE}/buy/browse/v1/item/{encoded_id}",
            headers=_headers(),
            timeout=15,
        )
    if resp.status_code != 200:
        return f"eBay API error {resp.status_code}: {resp.text}"

    item = resp.json()
    title = item.get("title", "N/A")
    price = item.get("price", {})
    amount = price.get("value", "N/A")
    currency = price.get("currency", "USD")
    condition = item.get("condition", "N/A")
    description = item.get("shortDescription", "No description")
    categories = ", ".join(c["categoryName"] for c in item.get("categories", []))
    brand = item.get("brand", "N/A")
    mpn = item.get("mpn", "N/A")
    image = item.get("image", {}).get("imageUrl", "N/A")
    url = item.get("itemWebUrl", "")
    seller = (item.get("seller", {}) or {}).get("username", "N/A")
    seller_fb = (item.get("seller", {}) or {}).get("feedbackPercentage", "N/A")
    est_handling = item.get("estimatedAvailabilities", [])
    shipping = item.get("shippingOptions", [])

    lines = [
        f"## {title}",
        f"**Price:** {amount} {currency}",
        f"**Condition:** {condition}",
        f"**Seller:** {seller} (Feedback: {seller_fb}%)",
        f"**Categories:** {categories}",
        f"**Brand:** {brand} | **MPN:** {mpn}",
        f"**Description:** {description}",
    ]
    if url:
        lines.append(f"**URL:** {url}")
    if image and image != "N/A":
        lines.append(f"**Image:** {image}")
    if shipping:
        ship = shipping[0]
        ship_cost = ship.get("shippingCost", {}).get("value", "N/A")
        lines.append(f"**Shipping:** {ship_cost} {currency} ({ship.get('shippingServiceCode', 'N/A')})")
    if est_handling:
        lines.append(f"**Estimated handling:** {est_handling[0].get('estimatedAvailabilityPercentage', 'N/A')}% available")

    return "\n".join(lines)


async def ebay_get_category_tree(category_id: str = "0") -> str:
    """Get the eBay category tree for navigation.

    Args:
        category_id: Parent category ID (default "0" for root)
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{EBAY_API_BASE}/commerce/taxonomy/v1/category_tree/{category_id}",
            headers=_headers(),
            timeout=15,
        )
    if resp.status_code != 200:
        return f"eBay API error {resp.status_code}: {resp.text}"

    data = resp.json()
    tree = data.get("categoryTree", data)
    lines = [f"## Category Tree: {tree.get('name', 'Root')}", ""]
    root = tree.get("rootCategory", {})
    _format_category(lines, root, 0, max_depth=3)
    return "\n".join(lines).strip() if lines else "No categories found."


def _format_category(lines, cat, depth, max_depth=3):
    if depth > max_depth:
        return
    indent = "  " * depth
    subcats = cat.get("childCategoryTreeNodes", [])
    marker = "+ " if subcats else "- "
    name = cat.get("name", "Unknown")
    cid = cat.get("categoryId", "")
    lines.append(f"{indent}{marker}{name} ({cid})")
    for sub in subcats[:10]:
        _format_category(lines, sub, depth + 1, max_depth)


ebay_tools = [
    ebay_search_sold_listings,
    ebay_search_active_listings,
    ebay_get_listing_details,
    ebay_get_category_tree,
]
