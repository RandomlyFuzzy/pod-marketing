"""Phase 2: Validation — check profitability, demand, and market fit."""
from ..agent import validate_product_idea, call_llm


PROFITABILITY_BENCHMARKS = {
    "T-Shirt (Bella+Canvas 3001)": {"cost": 10.98, "retail_etsy": 28.99, "retail_ebay": 21.00},
    "T-Shirt (Gildan 5000)": {"cost": 8.80, "retail_etsy": 24.00, "retail_ebay": 16.12},
    "T-Shirt (Gildan 64000)": {"cost": 7.95, "retail_etsy": 24.00, "retail_ebay": 16.12},
    "Tote Bag (AOP)": {"cost": 12.38, "retail_etsy": 28.00, "retail_ebay": 23.39},
    "Tote Bag (cotton canvas)": {"cost": 12.00, "retail_etsy": 24.00, "retail_ebay": 23.39},
    "Trucker Hat": {"cost": 11.00, "retail_etsy": 28.00, "retail_ebay": 25.00},
    "Mug (11oz)": {"cost": 6.50, "retail_etsy": 18.99, "retail_ebay": 17.99},
    "Poster (18x24)": {"cost": 5.02, "retail_etsy": 24.99, "retail_ebay": 19.99},
    "Canvas Print (11x14)": {"cost": 10.82, "retail_etsy": 44.99, "retail_ebay": 34.99},
    "Beach Towel": {"cost": 15.00, "retail_etsy": 36.00, "retail_ebay": 28.00},
    "Phone Case": {"cost": 10.06, "retail_etsy": 24.99, "retail_ebay": 22.00},
    "Tumbler (20oz)": {"cost": 15.00, "retail_etsy": 30.00, "retail_ebay": 25.00},
}


def calculate_profit(base_cost: float, retail: float, platform: str) -> dict:
    fee_rate = 0.11 if platform == "etsy" else 0.14 if platform == "ebay" else 0.08
    shipping_cost = 5.00 if platform == "etsy" else 4.50 if platform == "ebay" else 4.00
    fees = round(retail * fee_rate, 2)
    net = round(retail - base_cost - fees - shipping_cost, 2)
    margin = round((net / retail) * 100, 1) if retail > 0 else 0
    return {
        "base_cost": base_cost,
        "retail": retail,
        "fees": fees,
        "shipping": shipping_cost,
        "net_profit": net,
        "margin_pct": margin,
        "fee_rate": fee_rate,
        "platform": platform,
    }


def validate_product_against_benchmarks(product_type: str, retail: float, platform: str = "etsy") -> dict:
    """Check a product idea against known profitability benchmarks."""
    match = None
    for name, data in PROFITABILITY_BENCHMARKS.items():
        if product_type.lower() in name.lower():
            match = (name, data)
            break

    if not match:
        return {"error": f"No benchmark found for '{product_type}'", "matches": list(PROFITABILITY_BENCHMARKS.keys())}

    name, data = match
    base = data["cost"]
    profit = calculate_profit(base, retail, platform)
    benchmark_retail = data[f"retail_{platform}"]
    is_competitive = retail <= benchmark_retail * 1.2

    return {
        "product": name,
        "your_price": retail,
        "benchmark_price": benchmark_retail,
        "is_competitive_pricing": is_competitive,
        "profitability": profit,
        "verdict": "GOOD" if (profit["margin_pct"] >= 25 and is_competitive) else "REVIEW" if profit["margin_pct"] >= 15 else "POOR",
        "recommendation": (
            f"Target ${benchmark_retail:.2f} for best margins ({profit['margin_pct']}% vs benchmark's ~30-50%)"
            if not is_competitive else
            f"Good pricing. Expected margin: {profit['margin_pct']}%"
        ),
    }


async def run_validation(product_idea: str, niche: str, product_type: str = "",
                         retail_price: float = 0, platform: str = "etsy") -> dict:
    ai_validation = await validate_product_idea(product_idea, niche)

    bench = None
    if product_type:
        bench = validate_product_against_benchmarks(product_type, retail_price or 24.99, platform)

    return {
        "product_idea": product_idea,
        "niche": niche,
        "ai_validation": ai_validation,
        "benchmark_validation": bench,
        "status": "complete",
    }
