import os
import httpx
from typing import Optional

PRINTIFY_API_BASE = "https://api.printify.com/v1"

def _headers():
    token = os.environ.get("PRINTIFY_API_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def printify_list_shops() -> str:
    """List your Printify shops."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PRINTIFY_API_BASE}/shops.json",
            headers=_headers(),
            timeout=15,
        )
    if resp.status_code != 200:
        return f"Printify API error {resp.status_code}: {resp.text}"

    shops = resp.json()
    if not shops:
        return "No Printify shops found."

    lines = ["## Printify Shops", ""]
    for shop in shops:
        sid = shop.get("id", "N/A")
        title = shop.get("title", "Unnamed")
        sales = shop.get("sales", 0)
        orders = shop.get("orders", 0)
        lines.append(f"- **{title}** (ID: {sid}) — Sales: {sales}, Orders: {orders}")

    return "\n".join(lines)


async def printify_get_products(limit: int = 20) -> str:
    """Get your Printify product catalog.

    Args:
        limit: Max products to return (1-100)
    """
    shop_id = os.environ.get("PRINTIFY_SHOP_ID", "")
    if not shop_id:
        shops_resp = await printify_list_shops_raw()
        if not shops_resp:
            return "No Printify shops found. Set PRINTIFY_SHOP_ID in .env."
        shop_id = str(shops_resp[0]["id"])

    params = {"limit": min(limit, 100)}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PRINTIFY_API_BASE}/shops/{shop_id}/products.json",
            headers=_headers(),
            params=params,
            timeout=15,
        )
    if resp.status_code != 200:
        return f"Printify API error {resp.status_code}: {resp.text}"

    data = resp.json()
    products = data.get("data", [])
    if not products:
        return "No products found."

    lines = [f"## Printify Products (Shop {shop_id})", ""]
    for p in products[:limit]:
        pid = p.get("id", "N/A")
        title = p.get("title", "N/A")
        variants = p.get("variants", [])
        prices = [v.get("price", 0) for v in variants if v.get("price")]
        min_price = min(prices) / 100 if prices else 0
        max_price = max(prices) / 100 if prices else 0
        images = p.get("images", [])
        thumbnail = images[0].get("src", "") if images else ""
        is_visible = p.get("visible", False)
        created = p.get("created_at", "")[:10]

        price_str = f"${min_price:.2f}" if min_price == max_price else f"${min_price:.2f} - ${max_price:.2f}"
        lines.append(f"- **{title}** (ID: {pid})")
        lines.append(f"  Price range: {price_str} | Visible: {is_visible} | Created: {created}")
        lines.append("")

    return "\n".join(lines).strip()


async def printify_list_shops_raw():
    token = os.environ.get("PRINTIFY_API_TOKEN", "")
    if not token:
        return None
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PRINTIFY_API_BASE}/shops.json",
            headers=_headers(),
            timeout=15,
        )
    if resp.status_code == 200:
        return resp.json()
    return None


async def printify_get_catalog(query: Optional[str] = None, limit: int = 20) -> str:
    """Search the Printify catalog of printable products with pricing.

    Args:
        query: Optional search term to filter (e.g. "tote bag", "t-shirt")
        limit: Max results (1-50)
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PRINTIFY_API_BASE}/catalog/blueprints.json",
            headers=_headers(),
            timeout=15,
        )
    if resp.status_code != 200:
        return f"Printify API error {resp.status_code}: {resp.text}"

    blueprints = resp.json()
    query_lower = query.lower() if query else ""

    matched = []
    for bp in blueprints[:200]:
        title = bp.get("title", "").lower()
        if query_lower and query_lower not in title:
            continue
        matched.append(bp)
        if len(matched) >= limit:
            break

    if not matched:
        return f"No catalog items matching '{query}'." if query else "No catalog items found."

    lines = [f"## Printify Catalog{(' - ' + query) if query else ''}", ""]
    for bp in matched:
        bid = bp.get("id", "N/A")
        title = bp.get("title", "N/A")
        description = bp.get("description", "")[:120]
        provider = bp.get("provider", "")
        print_providers = bp.get("print_providers", [])
        provider_count = len(print_providers)
        lines.append(f"- **{title}** (ID: {bid})")
        lines.append(f"  {description}")
        lines.append(f"  Provider: {provider} | Available from {provider_count} print provider(s)")
        lines.append("")

    return "\n".join(lines).strip()


async def printify_get_blueprint_variants(blueprint_id: int) -> str:
    """Get variants and pricing for a specific Printify blueprint.

    Args:
        blueprint_id: Blueprint ID from the catalog
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PRINTIFY_API_BASE}/catalog/blueprints/{blueprint_id}.json",
            headers=_headers(),
            timeout=15,
        )
    if resp.status_code != 200:
        resp2 = await client.get(
            f"{PRINTIFY_API_BASE}/catalog/blueprints/{blueprint_id}/print_providers.json",
            headers=_headers(),
            timeout=15,
        )
        if resp2.status_code != 200:
            return f"Printify API error {resp.status_code}: {resp.text}"
        data = resp2.json()

        lines = [f"## Blueprint {blueprint_id} — Print Providers", ""]
        for pp in data if isinstance(data, list) else data.get("data", []):
            pp_id = pp.get("id", "N/A")
            pp_name = pp.get("title", "Unknown")
            location = pp.get("location", "")
            variants = pp.get("variants", [])
            lines.append(f"- **{pp_name}** (ID: {pp_id}) — {location}")
            for v in variants[:3]:
                cost = v.get("price", 0) / 100
                title = v.get("title", "Unknown")
                lines.append(f"  - {title}: ${cost:.2f}")
            lines.append("")
        return "\n".join(lines).strip()

    bp = resp.json()
    lines = [f"## {bp.get('title', f'Blueprint {blueprint_id}')}", ""]
    desc = bp.get("description", "No description")
    lines.append(f"{desc}")
    lines.append("")
    print_providers = bp.get("print_providers", [])
    for pp in print_providers[:5]:
        pp_name = pp.get("title", "Unknown")
        pp_id = pp.get("id", "N/A")
        location = pp.get("location", "")
        lines.append(f"**{pp_name}** (ID: {pp_id}) — {location}")
        variants = pp.get("variants", [])
        for v in variants[:5]:
            cost = v.get("price", 0) / 100
            v_title = v.get("title", "Unknown")
            lines.append(f"  - {v_title}: ${cost:.2f}")
        lines.append("")

    return "\n".join(lines).strip()


async def printify_calculate_profit(
    product_name: str,
    base_cost: float,
    retail_price: float,
    platform: str = "etsy",
    shipping_cost: float = 5.0,
) -> str:
    """Calculate estimated profit for a POD product on Etsy or eBay.

    Uses the fee structures from the profitability report:
    Etsy: ~11% fees, eBay: ~14% fees.

    Args:
        product_name: Name of the product
        base_cost: Your cost from the POD provider
        retail_price: Your retail price
        platform: 'etsy' or 'ebay'
        shipping_cost: Shipping cost to buyer (default $5.00)
    """
    if platform.lower() == "etsy":
        fee_rate = 0.11
        platform_name = "Etsy"
    elif platform.lower() == "ebay":
        fee_rate = 0.14
        platform_name = "eBay"
    else:
        return f"Unknown platform: {platform}. Use 'etsy' or 'ebay'."

    fees = round(retail_price * fee_rate, 2)
    net_profit = round(retail_price - base_cost - fees - shipping_cost, 2)
    margin_pct = round((net_profit / retail_price) * 100, 1)

    lines = [
        f"## Profit Calculator: {product_name}",
        f"**Platform:** {platform_name}",
        "",
        "| Item | Amount |",
        "|------|--------|",
        f"| Retail Price | ${retail_price:.2f} |",
        f"| Base Cost | -${base_cost:.2f} |",
        f"| Platform Fees ({platform_name}, {int(fee_rate*100)}%) | -${fees:.2f} |",
        f"| Estimated Shipping | -${shipping_cost:.2f} |",
        f"| **Net Profit** | **${net_profit:.2f}** |",
        f"| **Margin** | **{margin_pct}%** |",
        "",
    ]

    if margin_pct >= 35:
        lines.append("✅ Great margin! Matches the report's target for profitability.")
    elif margin_pct >= 25:
        lines.append("✅ Decent margin — acceptable for volume sales on eBay.")
    elif margin_pct >= 15:
        lines.append("⚠️ Tight margin — consider raising price or lowering costs.")
    else:
        lines.append("❌ Margin too thin — look for cheaper providers or higher retail price.")

    return "\n".join(lines)


async def printify_get_orders(limit: int = 10) -> str:
    """Get your Printify order history.

    Args:
        limit: Max orders to return (1-50)
    """
    shop_id = os.environ.get("PRINTIFY_SHOP_ID", "")
    if not shop_id:
        return "Set PRINTIFY_SHOP_ID in .env."

    params = {"limit": min(limit, 50)}
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PRINTIFY_API_BASE}/shops/{shop_id}/orders.json",
            headers=_headers(),
            params=params,
            timeout=15,
        )
    if resp.status_code != 200:
        return f"Printify API error {resp.status_code}: {resp.text}"

    data = resp.json()
    orders = data.get("data", [])
    if not orders:
        return "No orders found."

    lines = [f"## Printify Orders (Shop {shop_id})", ""]
    for o in orders[:limit]:
        oid = o.get("id", "N/A")
        status = o.get("status", "N/A")
        total = o.get("total_price", 0) / 100
        shipping = o.get("total_shipping", 0) / 100
        created = o.get("created_at", "")[:10]
        address = o.get("address_to", {})
        name = address.get("first_name", "") + " " + address.get("last_name", "")
        items = o.get("line_items", [])
        item_count = len(items)
        lines.append(f"- **Order {oid}** | Status: {status} | Total: ${total:.2f} | Shipping: ${shipping:.2f}")
        lines.append(f"  Created: {created} | To: {name.strip()} | Items: {item_count}")
        lines.append("")

    return "\n".join(lines).strip()


printify_tools = [
    printify_list_shops,
    printify_get_products,
    printify_get_catalog,
    printify_get_blueprint_variants,
    printify_calculate_profit,
    printify_get_orders,
]
