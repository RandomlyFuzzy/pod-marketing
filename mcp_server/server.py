import os
from pathlib import Path
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from mcp_server.tools.ebay import ebay_tools
from mcp_server.tools.etsy import etsy_tools
from mcp_server.tools.printify import printify_tools
try:
    from pipeline.mcp_tools import pipeline_tools
except ImportError:
    pipeline_tools = []

load_dotenv(Path(__file__).parent / ".env")

mcp = FastMCP("pod-market", instructions="""POD Market MCP Server — eBay, Etsy, Printify, and Pipeline tools.

Use these tools to research POD market trends, search listings, manage Printify products,
get pricing data, AND run the full research-to-publish pipeline.

Pipeline phases:
1. pipeline_research — Research a niche (trends, competitors, opportunities)
2. pipeline_validate — Validate a product idea (market fit, profitability)
3. pipeline_create_listing — Generate listing content (title, desc, tags, price)

Use the standalone tool alongside web search / scrapling for deeper research.

Required environment variables:
  EBAY_APP_ID, EBAY_CERT_ID, EBAY_OAUTH_TOKEN (for eBay)
  ETSY_API_KEY, ETSY_API_SECRET, ETSY_ACCESS_TOKEN (for Etsy)
  PRINTIFY_API_TOKEN, PRINTIFY_SHOP_ID (for Printify)
  OLLAMA_URL (default: http://localhost:11434)
""")

for tool in ebay_tools:
    mcp.tool()(tool)

for tool in etsy_tools:
    mcp.tool()(tool)

for tool in printify_tools:
    mcp.tool()(tool)

for tool in pipeline_tools:
    mcp.tool()(tool)


def main():
    mcp.run(transport="stdio")
