"""Phase 1: Market Research — trend discovery, competitor analysis, niche validation."""
from ..agent import research_niche, call_llm
from ..agent import analyze_competitor as _analyze


async def run_research(topic: str, keywords: list[str] | None = None, context: str = "") -> dict:
    if not keywords:
        keywords = [f"{topic} 2026 trends", f"{topic} market analysis",
                    f"{topic} top products", f"{topic} opportunities"]
    search_keywords = keywords[:]
    if context:
        search_keywords.insert(0, f"{topic} {context[:100]}")
    research = await research_niche(topic, search_keywords)
    return {
        "topic": topic,
        "research": research,
        "keywords": keywords,
        "context": context,
        "status": "complete",
    }


async def run_competitor_analysis(product_or_topic: str, market: str = "") -> dict:
    result = await _analyze(product_or_topic, market or product_or_topic)
    return {"topic": product_or_topic, "analysis": result, "status": "complete"}


async def get_research_prompts() -> list[dict]:
    return [
        {"label": "Market Trends", "prompt": "What are the current trends and opportunities in this market? Include growth signals, emerging sub-niches, and demand indicators."},
        {"label": "Competitor Analysis", "prompt": "Who are the top competitors in this space? What are their strategies, price points, and weaknesses? How can a new entrant differentiate?"},
        {"label": "Customer Research", "prompt": "Who is the target customer? What are their demographics, psychographics, pain points, and buying behavior? What channels reach them?"},
        {"label": "Product Ideation", "prompt": "What specific products could be created for this topic? Include product types, design themes, price points, and unique selling propositions."},
        {"label": "SEO & Keywords", "prompt": "What are the best keywords and search phrases for this topic? Include high-volume, long-tail, and low-competition opportunities."},
        {"label": "Pricing Strategy", "prompt": "What pricing strategy works for this market? Include price ranges, perceived value tactics, bundling opportunities, and platform-specific pricing (Etsy vs eBay)."},
        {"label": "Full Market Report", "prompt": "Produce a comprehensive market research report covering all aspects: trends, competition, customers, products, keywords, pricing, and actionable recommendations."},
    ]
