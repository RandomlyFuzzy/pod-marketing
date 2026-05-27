import os
import httpx
from typing import Optional

ETSY_API_BASE = "https://openapi.etsy.com/v3"

def _headers():
    token = os.environ.get("ETSY_ACCESS_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "x-api-key": os.environ.get("ETSY_API_KEY", ""),
    }


async def etsy_search_listings(
    query: str,
    limit: int = 10,
    sort_on: str = "score",
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    shop_location: Optional[str] = None,
) -> str:
    """Search Etsy listings for market research and trend analysis.

    Args:
        query: Search keywords (e.g. "custom beach tote bag personalized")
        limit: Max results (1-100)
        sort_on: Sort field (score, price, recency)
        min_price: Minimum price filter
        max_price: Maximum price filter
        shop_location: Filter by shop location (e.g. "US", "UK")
    """
    params = {
        "q": query,
        "limit": min(limit, 100),
        "sort_on": sort_on,
    }
    if min_price is not None:
        params["min_price"] = min_price
    if max_price is not None:
        params["max_price"] = max_price
    if shop_location:
        params["shop_location"] = shop_location

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{ETSY_API_BASE}/application/listings/active",
            headers=_headers(),
            params=params,
            timeout=15,
        )
    if resp.status_code != 200:
        return f"Etsy API error {resp.status_code}: {resp.text}"

    data = resp.json()
    listings = data.get("results", [])
    if not listings:
        return f"No listings found for '{query}'."

    count = data.get("count", len(listings))
    lines = [f"## Etsy Listings: '{query}' ({count} total)", ""]
    for i, item in enumerate(listings[:limit], 1):
        title = item.get("title", "N/A")
        price = item.get("price", {})
        amount = price.get("amount", price.get("value", "N/A"))
        currency = price.get("currency_code", price.get("currency", "USD"))
        url = item.get("url", "")
        listing_id = item.get("listing_id", "")
        views = item.get("views", "?")
        num_favorers = item.get("num_favorers", 0)
        tags = ", ".join(item.get("tags", [])[:5])
        lines.append(f"{i}. **{title}**")
        lines.append(f"   Price: {amount} {currency} | Views: {views} | Favorites: {num_favorers}")
        if tags:
            lines.append(f"   Tags: {tags}")
        if url:
            lines.append(f"   URL: {url}")
        lines.append("")

    return "\n".join(lines).strip()


async def etsy_get_shop_listings(
    shop_id: str,
    limit: int = 10,
    sort_on: str = "created",
) -> str:
    """Get all listings for a specific Etsy shop.

    Args:
        shop_id: Shop ID (numeric) or shop name
        limit: Max results (1-100)
        sort_on: Sort field (created, price, score)
    """
    params = {
        "limit": min(limit, 100),
        "sort_on": sort_on,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{ETSY_API_BASE}/application/shops/{shop_id}/listings/active",
            headers=_headers(),
            params=params,
            timeout=15,
        )
    if resp.status_code != 200:
        return f"Etsy API error {resp.status_code}: {resp.text}"

    data = resp.json()
    listings = data.get("results", [])
    if not listings:
        return f"No listings found for shop '{shop_id}'."

    lines = [f"## Shop Listings: {shop_id}", ""]
    for i, item in enumerate(listings[:limit], 1):
        title = item.get("title", "N/A")
        price = item.get("price", {})
        amount = price.get("amount", price.get("value", "N/A"))
        currency = price.get("currency_code", price.get("currency", "USD"))
        quantity = item.get("quantity", 0)
        views = item.get("views", "?")
        favorers = item.get("num_favorers", 0)
        lines.append(f"{i}. **{title}** — {amount} {currency} (Qty: {quantity})")
        lines.append(f"   Views: {views} | Favorites: {favorers}")
        lines.append("")

    return "\n".join(lines).strip()


async def etsy_get_listing_details(listing_id: int) -> str:
    """Get detailed info for a specific Etsy listing.

    Args:
        listing_id: The numeric listing ID
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{ETSY_API_BASE}/application/listings/{listing_id}",
            headers=_headers(),
            params={"includes": "Images,Shop,Translations"},
            timeout=15,
        )
    if resp.status_code != 200:
        return f"Etsy API error {resp.status_code}: {resp.text}"

    item = resp.json()
    title = item.get("title", "N/A")
    description = item.get("description", "No description")[:500]
    price = item.get("price", {})
    amount = price.get("amount", price.get("value", "N/A"))
    currency = price.get("currency_code", price.get("currency", "USD"))
    quantity = item.get("quantity", 0)
    views = item.get("views", "?")
    favorers = item.get("num_favorers", 0)
    who_made = item.get("who_made", "N/A")
    is_personalizable = item.get("is_personalizable", False)
    tags = ", ".join(item.get("tags", []))
    materials = ", ".join(item.get("materials", []))
    url = item.get("url", "")

    lines = [
        f"## {title}",
        f"**Price:** {amount} {currency} | **Quantity:** {quantity}",
        f"**Views:** {views} | **Favorites:** {favorers}",
        f"**Made by:** {who_made} | **Personalizable:** {is_personalizable}",
        f"**Description:** {description}",
    ]
    if tags:
        lines.append(f"**Tags:** {tags}")
    if materials:
        lines.append(f"**Materials:** {materials}")
    if url:
        lines.append(f"**URL:** {url}")

    return "\n".join(lines)


async def etsy_get_trending_searches() -> str:
    """Get trending Etsy search terms for trend spotting."""
    params = {"limit": 20}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{ETSY_API_BASE}/application/etsy/trending-searches",
            headers=_headers(),
            params=params,
            timeout=15,
        )
    if resp.status_code != 200:
        return f"Etsy API error {resp.status_code}: {resp.text}"

    data = resp.json()
    searches = []
    if "trending_searches" in data:
        searches = data["trending_searches"]
    elif "results" in data:
        searches = [r.get("query", "") for r in data["results"] if r.get("query")]
    else:
        searches = list(data.values()) if isinstance(data, dict) else data

    if not searches:
        return "No trending searches available."

    lines = ["## Trending Etsy Searches", ""]
    for i, term in enumerate(searches[:20], 1):
        name = term if isinstance(term, str) else (term.get("query", str(term)))
        lines.append(f"{i}. {name}")

    return "\n".join(lines)


etsy_tools = [
    etsy_search_listings,
    etsy_get_shop_listings,
    etsy_get_listing_details,
    etsy_get_trending_searches,
]
