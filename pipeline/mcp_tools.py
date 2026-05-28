"""MCP-compatible pipeline tools for use with the existing MCP server."""
from .agent import research_niche, validate_product_idea, generate_listing_content, call_llm


async def pipeline_research(topic: str, keywords: str = "") -> str:
    """Phase 1: Research any topic, market, or niche. Returns analysis with trends, competitors, and opportunities.

    Args:
        topic: The topic to research (e.g. 'personalized kids gifts', 'golf accessories', 'pet apparel', 'coastal home decor')
        keywords: Optional comma-separated keywords for deeper / more targeted research
    """
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()] if keywords else []
    result = await research_niche(topic, kw_list)
    return result


async def pipeline_validate(product_idea: str, niche: str = "") -> str:
    """Phase 2: Validate a product idea. Returns market fit analysis, profitability check, and go/no-go.

    Args:
        product_idea: Detailed description of the product idea
        niche: The niche this product targets
    """
    return await validate_product_idea(product_idea, niche or "general")


async def pipeline_create_listing(
    product_name: str, niche: str, persona: str = "Vacation Mom",
    features: str = "Premium quality materials,Vibrant print,Machine washable,Multiple sizes"
) -> str:
    """Phase 3: Generate complete Etsy/eBay listing content (title, desc, tags, pricing).

    Args:
        product_name: Name of the product
        niche: Target niche
        persona: Target persona (Vacation Mom, Bach Planner, Coastal Decorator, Gift Buyer, Trend Hopper, eBay Shopper)
        features: Comma-separated product features
    """
    feat_list = [f.strip() for f in features.split(",") if f.strip()]
    result = await generate_listing_content(product_name, niche, persona, feat_list)
    lines = [
        f"## Listing: {product_name}",
        f"**Title:** {result.get('title', '')}",
        f"**Price Point:** ${result.get('price_point', 0)}",
        f"**Description:** {result.get('description', '')[:500]}",
        "",
        "**Tags:** " + ", ".join(result.get('tags', [])),
        "**SEO Keywords:** " + ", ".join(result.get('seo_keywords', [])),
        "**Key Features:**",
    ]
    for f in result.get("key_features", []):
        lines.append(f"- {f}")
    return "\n".join(lines)


pipeline_tools = [
    pipeline_research,
    pipeline_validate,
    pipeline_create_listing,
]
