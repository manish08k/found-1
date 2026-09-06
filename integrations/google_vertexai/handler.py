"""Google Vertex AI integration — ML and generative AI platform."""
import httpx
import structlog
from core.execution_engine import register_node
from oauth.flow import get_access_token

log = structlog.get_logger(__name__)


async def _headers(credential_id: str, db) -> dict:
    token = await get_access_token(credential_id, db)
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@register_node("google_vertexai.generate_text")
async def google_vertexai_generate_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    project_id = merged.get("project_id", "")
    location = merged.get("location", "us-central1")
    model = merged.get("model", "gemini-1.5-flash-001")
    headers = await _headers(credential_id, db)
    base = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model}:generateContent"
    async with httpx.AsyncClient(headers=headers, timeout=60) as client:
        r = await client.post(base, json={
            "contents": [{"role": "user", "parts": [{"text": merged.get("prompt", "")}]}],
            "generationConfig": {"maxOutputTokens": merged.get("max_tokens", 1024), "temperature": merged.get("temperature", 0.7)},
        })
        r.raise_for_status()
    data = r.json()
    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
    return {"text": text, "model": model}


@register_node("google_vertexai.embed_text")
async def google_vertexai_embed_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    project_id = merged.get("project_id", "")
    location = merged.get("location", "us-central1")
    model = merged.get("model", "text-embedding-004")
    headers = await _headers(credential_id, db)
    base = f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}/locations/{location}/publishers/google/models/{model}:predict"
    async with httpx.AsyncClient(headers=headers, timeout=30) as client:
        r = await client.post(base, json={"instances": [{"content": merged.get("text", "")}]})
        r.raise_for_status()
    data = r.json()
    return {"embeddings": data.get("predictions", [{}])[0].get("embeddings", {}).get("values", [])}
