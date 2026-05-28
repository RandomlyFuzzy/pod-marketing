"""Phase 3: Listing Creation — generate titles, descriptions, tags, design briefs."""
from ..agent import generate_listing_content, call_llm


PERSONA_TEMPLATES = {
    "Vacation Mom": {
        "tone": "warm, family-oriented, excited",
        "angle": "Make vacation memories with matching family outfits",
        "pain_points": ["Coordinating different ages/sizes", "Getting everyone to agree on a design",
                       "Finding something photo-worthy"],
    },
    "Bach Planner": {
        "tone": "fun, energetic, party-focused",
        "angle": "The bride will LOVE these matching bach party essentials",
        "pain_points": ["Coordinating a large group", "Tight timeline before the trip",
                       "Finding designs everyone likes"],
    },
    "Coastal Decorator": {
        "tone": "sophisticated, calming, aesthetic",
        "angle": "Transform your space with coastal-inspired decor",
        "pain_points": ["Finding unique coastal decor", "Matching bathroom sets",
                       "Quality that lasts beyond one season"],
    },
    "Gift Buyer": {
        "tone": "heartfelt, thoughtful, appreciative",
        "angle": "The perfect gift they'll actually use and love",
        "pain_points": ["Finding something unique", "Not knowing what they want",
                       "Wanting to show thoughtfulness"],
    },
    "Trend Hopper": {
        "tone": "trendy, social-media-savvy, exciting",
        "angle": "Be the first to rock this viral aesthetic",
        "pain_points": ["Finding what's actually trending", "Fast shipping needed",
                       "Wanting Instagram-worthy content"],
    },
    "eBay Shopper": {
        "tone": "direct, value-focused, practical",
        "angle": "Custom shirts without the boutique markup",
        "pain_points": ["Needing a custom shirt on a budget", "Fast turnaround",
                       "Simple customization without fluff"],
    },
}


async def create_listing(product_name: str, niche: str, persona: str,
                          features: list[str] | None = None) -> dict:
    if features is None:
        features = [
            "Premium quality materials",
            "Vibrant, fade-resistant print",
            "Machine washable",
            "Available in multiple sizes/colors",
            "Makes a great gift",
        ]
    content = await generate_listing_content(product_name, niche, persona, features)
    persona_details = PERSONA_TEMPLATES.get(persona, {})
    return {
        "product_name": product_name,
        "niche": niche,
        "persona": persona,
        "persona_details": persona_details,
        "listing": content,
        "status": "complete",
    }


async def generate_design_brief(product_name: str, niche: str, persona: str,
                                 style_keywords: list[str] | None = None) -> str:
    if style_keywords is None:
        style_keywords = ["minimalist", "trendy"]
    kw = ", ".join(style_keywords)
    prompt = f"""Create a detailed design brief for a POD product.

Product: {product_name}
Niche: {niche}
Target Persona: {persona}
Style Keywords: {kw}

Include:
1. Design concept description
2. Color palette (specific hex codes)
3. Typography recommendations
4. Placement (center chest, left pocket, full print, etc.)
5. Size recommendations (what print dimensions work best)
6. Mockup description for listing photos

Make it specific enough that a designer could execute it."""
    designer = await call_llm(prompt)
    return {"product_name": product_name, "design_brief": designer, "status": "complete"}
