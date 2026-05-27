import os
from pathlib import Path
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from mcp_server.tools.ebay import ebay_tools
from mcp_server.tools.etsy import etsy_tools
from mcp_server.tools.printify import printify_tools

load_dotenv(Path(__file__).parent / ".env")

mcp = FastMCP("pod-market", instructions="""POD Market MCP Server — eBay, Etsy, and Printify API integration.

Use these tools to research POD market trends, search listings, manage Printify products,
and get pricing data across all three platforms.

Required environment variables:
  EBAY_APP_ID, EBAY_CERT_ID, EBAY_OAUTH_TOKEN (for eBay)
  ETSY_API_KEY, ETSY_API_SECRET, ETSY_ACCESS_TOKEN (for Etsy)
  PRINTIFY_API_TOKEN, PRINTIFY_SHOP_ID (for Printify)
""")

for tool in ebay_tools:
    mcp.tool()(tool)

for tool in etsy_tools:
    mcp.tool()(tool)

for tool in printify_tools:
    mcp.tool()(tool)


def main():
    mcp.run(transport="stdio")
