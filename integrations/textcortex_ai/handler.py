"""TextCortex AI writing assistant integration."""
import httpx
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

TEXTCORTEX_BASE = "https://api.textcortex.com/v1"


@register_node("textcortex_ai.create_blog")
async def textcortex_ai_create_blog(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate a blog post using TextCortex AI.

    config/input_data:
      api_key         — TextCortex API key
      text            — context or topic for the blog post
      blog_categories — list of category strings (default ["general"])
      tone_of_voice   — tone (default "informative")
      n               — number of outputs to generate (default 1)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    text = merged.get("text") or ""
    blog_categories = merged.get("blog_categories") or ["general"]
    tone_of_voice = merged.get("tone_of_voice") or "informative"
    n = int(merged.get("n", 1))

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "context": text,
        "blog_categories": blog_categories,
        "tone_of_voice": tone_of_voice,
        "n": n,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{TEXTCORTEX_BASE}/texts/blogs", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("textcortex_ai.create_blog", tone=tone_of_voice)
    return {"result": result}


@register_node("textcortex_ai.paraphrase")
async def textcortex_ai_paraphrase(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Paraphrase text using TextCortex AI.

    config/input_data:
      api_key       — TextCortex API key
      text          — text to paraphrase
      tone_of_voice — tone (default "formal")
      n             — number of outputs (default 1)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    text = merged.get("text") or ""
    tone_of_voice = merged.get("tone_of_voice") or "formal"
    n = int(merged.get("n", 1))

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"text": text, "tone_of_voice": tone_of_voice, "n": n}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{TEXTCORTEX_BASE}/texts/paraphrase", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("textcortex_ai.paraphrase", tone=tone_of_voice)
    return {"result": result}


@register_node("textcortex_ai.summarize")
async def textcortex_ai_summarize(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Summarize text using TextCortex AI.

    config/input_data:
      api_key    — TextCortex API key
      text       — text to summarize
      max_tokens — max tokens in the summary (default 100)
      n          — number of outputs (default 1)
    """
    merged = {**config, **input_data}
    api_key = merged.get("api_key") or ""
    text = merged.get("text") or ""
    max_tokens = int(merged.get("max_tokens", 100))
    n = int(merged.get("n", 1))

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"text": text, "max_tokens": max_tokens, "n": n}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{TEXTCORTEX_BASE}/texts/summarize", headers=headers, json=payload)
        r.raise_for_status()

    result = r.json()
    log.info("textcortex_ai.summarize", max_tokens=max_tokens)
    return {"result": result}
