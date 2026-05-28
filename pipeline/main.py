"""POD Pipeline Web App — Research → Validate → Create → Publish."""
import os
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .store import get_state, save_state, append_history
from .phases.research import run_research
from .phases.validate import run_validation
from .phases.create import create_listing, generate_design_brief
from .phases.publish import prepare_publish
from .agent import call_llm

app = FastAPI(title="POD Pipeline", version="1.0.0")

_templates_dir = Path(__file__).parent / "templates"
_static_dir = Path(__file__).parent / "static"
_static_dir.mkdir(exist_ok=True)

_jinja_env = Environment(
    loader=FileSystemLoader(str(_templates_dir)),
    autoescape=select_autoescape(["html", "xml"]),
    cache_size=0,
)

if _static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


def new_session() -> str:
    import uuid
    return uuid.uuid4().hex[:12]


def _render(name: str, **ctx) -> str:
    return _jinja_env.get_template(name).render(**ctx)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    sid = request.cookies.get("session_id") or new_session()
    state = get_state(sid)
    html = _render("index.html", request=request, state=state, session_id=sid)
    response = HTMLResponse(html)
    response.set_cookie("session_id", sid)
    return response


@app.get("/phase/{phase}", response_class=HTMLResponse)
async def phase_page(request: Request, phase: str):
    sid = request.cookies.get("session_id", new_session())
    state = get_state(sid)
    html = _render(f"{phase}.html", request=request, state=state, session_id=sid)
    return HTMLResponse(html)


@app.post("/api/research")
async def api_research(request: Request):
    data = await request.json()
    sid = request.cookies.get("session_id", new_session())
    topic = data.get("niche", data.get("topic", ""))
    keywords = data.get("keywords", [])
    context = data.get("context", "")
    state = get_state(sid)
    state["topic"] = topic
    state["phase"] = "research"
    result = await run_research(topic, keywords, context)
    state["research_data"] = result
    append_history(sid, {"action": "research", "topic": topic, "result_preview": result["research"][:200]})
    save_state(sid, state)
    return JSONResponse(result)


@app.post("/api/validate")
async def api_validate(request: Request):
    data = await request.json()
    sid = request.cookies.get("session_id", new_session())
    state = get_state(sid)
    product_idea = data.get("product_idea", "")
    niche = data.get("niche", state.get("niche", ""))
    product_type = data.get("product_type", "")
    retail_price = data.get("retail_price", 24.99)
    platform = data.get("platform", "etsy")
    result = await run_validation(product_idea, niche, product_type, retail_price, platform)
    state["validation_data"] = result
    state["phase"] = "validate"
    append_history(sid, {"action": "validate", "product": product_idea, "platform": platform})
    save_state(sid, result)
    return JSONResponse(result)


@app.post("/api/create")
async def api_create(request: Request):
    data = await request.json()
    sid = request.cookies.get("session_id", new_session())
    state = get_state(sid)
    product_name = data.get("product_name", "")
    niche = data.get("niche", state.get("niche", ""))
    persona = data.get("persona", "Vacation Mom")
    features = data.get("features", [])
    result = await create_listing(product_name, niche, persona, features)
    state["listing_content"] = result
    state["current_product"] = product_name
    state["phase"] = "create"
    append_history(sid, {"action": "create_listing", "product": product_name, "persona": persona})
    save_state(sid, state)
    return JSONResponse(result)


@app.post("/api/create/design-brief")
async def api_design_brief(request: Request):
    data = await request.json()
    sid = request.cookies.get("session_id", new_session())
    state = get_state(sid)
    result = await generate_design_brief(
        data.get("product_name", ""),
        data.get("niche", state.get("niche", "")),
        data.get("persona", "Vacation Mom"),
        data.get("style_keywords", []),
    )
    return JSONResponse(result)


@app.post("/api/publish")
async def api_publish(request: Request):
    data = await request.json()
    sid = request.cookies.get("session_id", new_session())
    state = get_state(sid)
    product_name = data.get("product_name", state.get("current_product", ""))
    product_type = data.get("product_type", "t-shirt")
    platform = data.get("platform", "etsy")
    listing_content = data.get("listing_content", state.get("listing_content", {}))
    result = await prepare_publish(product_name, product_type, listing_content, platform)
    state["publish_data"] = result
    state["phase"] = "publish"
    append_history(sid, {"action": "publish", "product": product_name, "platform": platform})
    save_state(sid, state)
    return JSONResponse(result)


@app.get("/api/state")
async def api_state(request: Request):
    sid = request.cookies.get("session_id", new_session())
    return JSONResponse(get_state(sid))


@app.post("/api/reset")
async def api_reset(request: Request):
    sid = request.cookies.get("session_id", new_session())
    save_state(sid, {})
    return JSONResponse({"status": "reset"})


@app.post("/api/agent-research")
async def api_agent_research(request: Request):
    """Run the Ollama agent with Scrapling for deep research."""
    data = await request.json()
    niche = data.get("niche", "")
    query = data.get("query", f"{niche} POD market trends 2026")

    system_prompt = """You are a POD market research agent. Research this topic using web search.
    Provide specific data: prices, trends, competitor names, keyword phrases.
    Format as a structured report with sections."""

    user_prompt = f"""Research the POD niche: {niche}
    Search query: {query}

    Provide a comprehensive market research report covering:
    1. Current trends and demand signals
    2. Top-selling products and price points
    3. Design aesthetics that are performing well
    4. Target audience details
    5. Keyword opportunities
    6. Competitive analysis
    7. Recommendations for product development"""

    result = await call_llm(user_prompt, system_prompt)
    return JSONResponse({"niche": niche, "research": result})


def main():
    import uvicorn
    port = int(os.environ.get("PIPELINE_PORT", "8001"))
    print(f"POD Pipeline running at http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
