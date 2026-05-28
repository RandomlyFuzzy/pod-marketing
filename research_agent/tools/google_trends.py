"""Google Trends tool — checks search interest over time for keywords."""
import urllib3.util.retry as retry_mod
from typing import Optional
from pytrends.request import TrendReq

# Fix pytrends compatibility with urllib3 v2+
# pytrends uses old method_whitelist which was renamed to allowed_methods in urllib3 v2
_orig_init = retry_mod.Retry.__init__


def _patched_init(self, *args, **kwargs):
    if "method_whitelist" in kwargs:
        kwargs["allowed_methods"] = kwargs.pop("method_whitelist")
    _orig_init(self, *args, **kwargs)


retry_mod.Retry.__init__ = _patched_init


def _build_pytrends():
    return TrendReq(
        hl="en-US",
        tz=360,
        timeout=10,
        retries=3,
    )


async def google_trends_check(
    keywords: list[str],
    timeframe: str = "today 12-m",
    geo: str = "",
    gprop: str = "",
) -> str:
    """Check Google Trends interest for keywords over time.

    Args:
        keywords: List of search terms to compare (max 5)
        timeframe: Time range (e.g. 'today 12-m', 'today 3-m', 'today 5-y', 'all')
        geo: Geographic region (e.g. 'US', 'GB', '' for worldwide)
        gprop: Property filter ('', 'images', 'news', 'youtube', 'froogle')
    """
    try:
        p = _build_pytrends()
        p.build_payload(
            kw_list=keywords[:5],
            timeframe=timeframe,
            geo=geo or "",
            gprop=gprop or "",
        )

        interest = p.interest_over_time()
        if interest.empty:
            return "No trend data available for these keywords."

        recent = interest.tail(12)
        lines = ["## Google Trends Results", ""]

        for kw in keywords[:5]:
            if kw in recent.columns:
                vals = recent[kw].values
                avg = round(float(vals.mean()), 1)
                peak = int(vals.max())
                latest = int(vals[-1])
                direction = "up" if len(vals) > 1 and vals[-1] > vals[0] else "down" if len(vals) > 1 and vals[-1] < vals[0] else "stable"
                lines.append(f"**{kw}**")
                lines.append(f"  Avg interest: {avg}/100 | Peak: {peak} | Latest: {latest} | Trend: {direction}")
                lines.append("")

        # Related queries
        related = p.related_queries()
        for kw in keywords[:3]:
            if kw in related and related[kw] is not None:
                top = related[kw].get("top")
                rising = related[kw].get("rising")
                if top is not None and not top.empty:
                    lines.append(f"**Top related queries for '{kw}':**")
                    for _, row in top.head(5).iterrows():
                        lines.append(f"  - {row.get('query', '')} ({row.get('value', 0)})")
                    lines.append("")
                if rising is not None and not rising.empty:
                    lines.append(f"**Rising queries for '{kw}':**")
                    for _, row in rising.head(5).iterrows():
                        lines.append(f"  - {row.get('query', '')} ({row.get('value', '')})")
                    lines.append("")

        # Regional interest
        regions = p.interest_by_region()
        if not regions.empty:
            lines.append("**Top regions:**")
            top_regions = regions.sort_values(keywords[0], ascending=False).head(5)
            for idx, row in top_regions.iterrows():
                val = row.get(keywords[0], 0)
                if val > 0:
                    lines.append(f"  - {idx}: {val}")

        return "\n".join(lines).strip() if len(lines) > 2 else "No trend data available."

    except Exception as e:
        return f"Google Trends error: {e}"


async def google_trends_compare(product_idea: str, related_terms: list[str] | None = None) -> str:
    """Compare a product idea against related terms to validate demand.

    Args:
        product_idea: The main product or topic to check
        related_terms: Optional related terms to compare against (e.g. competitors, alternatives)
    """
    terms = [product_idea]
    if related_terms:
        terms.extend(related_terms[:4])
    return await google_trends_check(terms)
