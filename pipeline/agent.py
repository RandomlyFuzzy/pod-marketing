import os
import sys
import json
import httpx
from typing import Optional

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:e2b-128k")

SYSTEM_PROMPT = """You are a market research agent. Your job is to research any topic, analyze trends and opportunities, and generate actionable insights.

You have access to a web search tool called `web_search` that takes a query string and returns search results.

Research workflow:
1. Search for the given topic across relevant sources
2. Identify key trends, players, opportunities, and risks
3. Analyze what drives success in this space
4. Summarize findings with specific, actionable recommendations

Always provide specific data points: prices, metrics, sources, examples.
Cite your sources when possible.

Adapt your output format to the topic — if it's a product market, focus on products and pricing. If it's a trend, focus on growth signals and trajectory. If it's a competitor, focus on their strategy and weaknesses.
"""


async def call_llm(prompt: str, system: Optional[str] = None) -> str:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "system": system or SYSTEM_PROMPT,
                "stream": False,
                "options": {"temperature": 0.7, "num_ctx": 32768},
            },
        )
    if resp.status_code != 200:
        return f"LLM error {resp.status_code}: {resp.text}"
    data = resp.json()
    return data.get("response", "").strip()


async def research_niche(topic: str, keywords: list[str]) -> str:
    """Research any topic using the Ollama agent with web search context."""
    search_results = []
    for kw in keywords[:5]:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": kw},
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "text/html",
                    },
                )
            search_results.append(f"=== Search: {kw} ===\n{resp.text[:3000]}")
        except Exception as e:
            search_results.append(f"=== Search: {kw} ===\nError: {e}")

    context = "\n\n".join(search_results)
    prompt = f"""Research the following topic: "{topic}"

Search results for context:
{context[:15000]}

Based on this research, provide a structured analysis covering:
1. Overview — what is this topic/market?
2. Key trends and developments
3. Major players, products, or offerings
4. Opportunities and gaps
5. Risks and challenges
6. Target audience / customer profile
7. Key metrics: price ranges, market size signals, growth indicators
8. Actionable recommendations

If this is a product-oriented topic, include specific product ideas and price points.
If it's a trend or concept, focus on trajectory and implications.

Be specific, provide data points, and cite sources where possible."""
    return await call_llm(prompt)


async def analyze_competitor(product_description: str, niche: str) -> str:
    """Analyze competition and market positioning."""
    prompt = f"""Product description: {product_description}
Niche: {niche}

Analyze the competitive landscape:
1. How saturated is this niche? (low/medium/high)
2. What are the top 3 ways to differentiate this product?
3. What price range would be competitive?
4. What unique selling propositions could work?
5. What are the key keywords needed in the listing?

Provide specific, actionable recommendations."""
    return await call_llm(prompt)


async def generate_listing_content(
    product_name: str,
    niche: str,
    target_persona: str,
    features: list[str],
) -> dict:
    """Generate complete listing content using AI."""
    features_str = "\n".join(f"- {f}" for f in features)
    prompt = f"""Generate a complete Etsy/eBay listing for a POD product.

Product: {product_name}
Niche: {niche}
Target Persona: {target_persona}
Features:
{features_str}

Return a JSON object with exactly these fields:
- "title": A compelling listing title (under 140 chars for Etsy, under 80 for eBay)
- "description": A 3-4 paragraph product description that sells benefits, not features
- "tags": Array of 13 relevant tags (for Etsy SEO)
- "key_features": Array of 5-6 key features as bullet points
- "price_point": Recommended price based on the niche and persona
- "seo_keywords": Array of 5 key search phrases

Only return valid JSON, no other text."""
    result = await call_llm(prompt)
    try:
        first_brace = result.index("{")
        last_brace = result.rindex("}")
        json_str = result[first_brace : last_brace + 1]
        return json.loads(json_str)
    except (ValueError, json.JSONDecodeError):
        return {
            "title": product_name,
            "description": result,
            "tags": [niche],
            "key_features": features,
            "price_point": 24.99,
            "seo_keywords": [niche],
        }


async def validate_product_idea(idea: str, niche: str) -> str:
    """Validate a product idea against market data."""
    prompt = f"""Validate this POD product idea:

Product Idea: {idea}
Niche: {niche}

Evaluate:
1. DEMAND: Is there proven demand? What evidence supports this?
2. COMPETITION: How many competitors exist? Is the market saturated?
3. PRICING: What price range does the market support?
4. PROFITABILITY: Estimated margins (base cost ~$8-12, fees ~11-15%)
5. SEASONALITY: Is this year-round or seasonal?
6. RISK: What are the main risks?
7. VERDICT: Should this product be pursued? (YES / MAYBE / NO)

Be honest and critical - this is business validation."""
    return await call_llm(prompt)
