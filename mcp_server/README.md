# POD Market MCP Server

An MCP server integrating eBay, Etsy, and Printify APIs for print-on-demand market research and operations.

## Tools

### eBay
- `ebay_search_sold_listings` — Search completed/sold listings for market research
- `ebay_search_active_listings` — Search active listings
- `ebay_get_listing_details` — Get detailed info on a specific listing
- `ebay_get_category_tree` — Browse eBay category tree

### Etsy
- `etsy_search_listings` — Search listings with filters (price, location, sort)
- `etsy_get_shop_listings` — Get a shop's active listings
- `etsy_get_listing_details` — Get detailed listing info
- `etsy_get_trending_searches` — Get trending Etsy search terms

### Printify
- `printify_list_shops` — List Printify shops
- `printify_get_products` — Get your product catalog
- `printify_get_catalog` — Search the Printify blueprint catalog
- `printify_get_blueprint_variants` — Get variants/pricing for a blueprint
- `printify_calculate_profit` — Calculate estimated profit for a POD product
- `printify_get_orders` — Get order history

## Setup

```bash
cp .env.example .env
# Fill in your API credentials
```

### Where to Get API Keys

- **eBay:** https://developer.ebay.com/ — Create an app, get OAuth token
- **Etsy:** https://www.etsy.com/developers/ — Register app, get API key
- **Printify:** https://developers.printify.com/ — Get API token

## Usage

The server runs on stdio transport (for MCP integration):

```bash
cd mcp_server
python -m mcp_server
```

Or with uv:

```bash
uv run mcp_server
```

### Integration with opencode

Add to `~/.config/opencode/opencode.jsonc`:

```json
{
  "mcp": {
    "pod-market": {
      "type": "local",
      "command": ["python3", "-m", "mcp_server"],
      "cwd": "/path/to/pod_marketing/mcp_server"
    }
  }
}
```
