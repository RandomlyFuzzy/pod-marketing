"""Phase 4: Publishing — create products on Printify, prepare listings."""
import os
import httpx

PRINTIFY_API_BASE = "https://api.printify.com/v1"

def _printify_headers():
    return {
        "Authorization": f"Bearer {os.environ.get('PRINTIFY_API_TOKEN', '')}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def get_shop_id() -> str | None:
    token = os.environ.get("PRINTIFY_API_TOKEN", "")
    if not token:
        return None
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PRINTIFY_API_BASE}/shops.json",
            headers=_printify_headers(),
            timeout=15,
        )
    if resp.status_code == 200:
        shops = resp.json()
        if shops:
            return str(shops[0]["id"])
    return os.environ.get("PRINTIFY_SHOP_ID") or None


async def search_blueprint(product_type: str) -> list[dict]:
    """Find Printify blueprints matching a product type."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PRINTIFY_API_BASE}/catalog/blueprints.json",
            headers=_printify_headers(),
            timeout=15,
        )
    if resp.status_code != 200:
        return []
    blueprints = resp.json()
    query = product_type.lower()
    return [bp for bp in blueprints[:200] if query in bp.get("title", "").lower()][:5]


async def get_variant_pricing(blueprint_id: int, product_type: str) -> dict:
    """Get pricing for a blueprint's variants."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{PRINTIFY_API_BASE}/catalog/blueprints/{blueprint_id}/print_providers.json",
            headers=_printify_headers(),
            timeout=15,
        )
    if resp.status_code != 200:
        return {"error": f"Failed to get variants: {resp.status_code}"}

    data = resp.json()
    providers = data if isinstance(data, list) else data.get("data", [])
    results = []
    for pp in providers[:3]:
        pp_name = pp.get("title", "Unknown")
        location = pp.get("location", "")
        variants = pp.get("variants", [])
        pricing = []
        for v in variants[:5]:
            pricing.append({
                "title": v.get("title", "Unknown"),
                "cost": v.get("price", 0) / 100,
                "id": v.get("id"),
            })
        results.append({
            "provider": pp_name,
            "location": location,
            "variants": pricing,
        })
    return {"blueprint_id": blueprint_id, "product_type": product_type, "providers": results}


def format_etsy_listing(listing_data: dict) -> dict:
    """Format listing content for Etsy."""
    l = listing_data.get("listing", listing_data)
    return {
        "title": l.get("title", ""),
        "description": l.get("description", ""),
        "tags": l.get("tags", []),
        "price": l.get("price_point", 24.99),
        "who_made": "professionally_designed",
        "is_personalizable": True,
        "should_auto_renew": True,
        "quantity": 999,
        "type": "physical",
    }


def format_ebay_listing(listing_data: dict) -> dict:
    """Format listing content for eBay."""
    l = listing_data.get("listing", listing_data)
    return {
        "title": l.get("title", "")[:80],
        "description": l.get("description", ""),
        "price": l.get("price_point", 19.99),
        "condition": "New",
        "quantity": 10,
        "category_id": "15724",  # default t-shirts
    }


async def prepare_publish(product_name: str, product_type: str,
                           listing_content: dict, platform: str = "etsy") -> dict:
    blueprints = await search_blueprint(product_type)
    blueprint_info = []
    for bp in blueprints[:3]:
        pricing = await get_variant_pricing(bp["id"], product_type)
        blueprint_info.append(pricing)

    shop_id = await get_shop_id()

    listing_formatted = (
        format_etsy_listing(listing_content) if platform == "etsy"
        else format_ebay_listing(listing_content)
    )

    return {
        "product_name": product_name,
        "product_type": product_type,
        "platform": platform,
        "shop_id": shop_id,
        "available_blueprints": blueprint_info,
        "listing_draft": listing_formatted,
        "status": "ready_for_publish",
        "requires_api_keys": {
            "printify": bool(os.environ.get("PRINTIFY_API_TOKEN")),
            "etsy": bool(os.environ.get("ETSY_ACCESS_TOKEN")),
            "ebay": bool(os.environ.get("EBAY_OAUTH_TOKEN")),
        },
    }
