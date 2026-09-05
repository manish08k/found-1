"""
OpenAI integration.

Auth: Bearer token (api_key).

Credential fields:
  - api_key:       OpenAI API key
  - organization:  (optional) OpenAI organization ID

Nodes:
  - openai.chat_completion    — chat completions (GPT-4o, etc.)
  - openai.create_embedding   — generate text embeddings
  - openai.create_image       — generate images via DALL-E
  - openai.transcribe_audio   — speech-to-text via Whisper
  - openai.list_models        — list available models
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_BASE_URL = "https://api.openai.com/v1/"


async def _client(credential_id: str, db) -> httpx.AsyncClient:
    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("OpenAI credential missing 'api_key'")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    org = creds.get("organization")
    if org:
        headers["OpenAI-Organization"] = org
    return httpx.AsyncClient(base_url=_BASE_URL, headers=headers, timeout=120.0)


def _check(r: httpx.Response) -> dict:
    if not r.is_success:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"OpenAI API error {r.status_code}: {detail}")
    if not r.content:
        return {}
    return r.json()


@register_node("openai.chat_completion")
async def chat_completion(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    POST /chat/completions — generate a chat completion.

    Config:
      model       — model ID (default: gpt-4o)
      messages    — list of {role, content} dicts (required)
      temperature — sampling temperature 0-2 (optional)
      max_tokens  — max tokens to generate (optional)
      stream      — bool, streaming (not supported here; default false)
      top_p       — nucleus sampling parameter (optional)
      n           — number of completions (optional)
      stop        — stop sequence string or list (optional)
      system      — shortcut: system prompt string (used if messages not set)
    """
    messages = config.get("messages") or input_data.get("messages")
    system_prompt = config.get("system") or input_data.get("system")
    user_input = config.get("user") or input_data.get("user") or input_data.get("text")

    if not messages:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if user_input:
            messages.append({"role": "user", "content": user_input})
    if not messages:
        raise ValueError("openai.chat_completion requires 'messages' or 'user' text")

    model = config.get("model") or input_data.get("model") or "gpt-4o"
    payload: dict = {"model": model, "messages": messages}

    for field in ("temperature", "max_tokens", "top_p", "n", "stop", "frequency_penalty",
                  "presence_penalty", "response_format", "seed", "tools", "tool_choice"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            payload[field] = val

    log.info("openai.chat_completion", model=model, message_count=len(messages))
    async with await _client(credential_id, db) as client:
        r = await client.post("chat/completions", json=payload)
    return _check(r)


@register_node("openai.create_embedding")
async def create_embedding(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    POST /embeddings — generate embeddings for input text.

    Config:
      input           — (required) string or list of strings to embed
      model           — embedding model (default: text-embedding-3-small)
      encoding_format — float | base64 (optional)
      dimensions      — output dimension reduction (optional, model-dependent)
    """
    text_input = config.get("input") if config.get("input") is not None else input_data.get("input")
    if text_input is None:
        text_input = input_data.get("text")
    if not text_input:
        raise ValueError("openai.create_embedding requires 'input'")

    model = config.get("model") or input_data.get("model") or "text-embedding-3-small"
    payload: dict = {"input": text_input, "model": model}
    for field in ("encoding_format", "dimensions"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            payload[field] = val

    log.info("openai.create_embedding", model=model)
    async with await _client(credential_id, db) as client:
        r = await client.post("embeddings", json=payload)
    return _check(r)


@register_node("openai.create_image")
async def create_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    POST /images/generations — generate images with DALL-E.

    Config:
      prompt  — (required) text description of the image
      model   — dall-e-2 | dall-e-3 (default: dall-e-3)
      n       — number of images (default: 1; dall-e-3 max 1)
      size    — 256x256 | 512x512 | 1024x1024 | 1792x1024 | 1024x1792 (default: 1024x1024)
      quality — standard | hd (dall-e-3 only, default: standard)
      style   — vivid | natural (dall-e-3 only, optional)
      response_format — url | b64_json (default: url)
    """
    prompt = config.get("prompt") or input_data.get("prompt") or input_data.get("text")
    if not prompt:
        raise ValueError("openai.create_image requires 'prompt'")

    model = config.get("model") or input_data.get("model") or "dall-e-3"
    payload: dict = {"prompt": prompt, "model": model}
    for field in ("n", "size", "quality", "style", "response_format"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            payload[field] = val

    log.info("openai.create_image", model=model, prompt_length=len(prompt))
    async with await _client(credential_id, db) as client:
        r = await client.post("images/generations", json=payload)
    return _check(r)


@register_node("openai.transcribe_audio")
async def transcribe_audio(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    POST /audio/transcriptions — transcribe audio via Whisper.

    Config:
      file            — (required) audio file content as bytes or base64 string
      filename        — filename with extension (default: audio.mp3)
      model           — whisper-1 (default)
      language        — ISO-639-1 language code (optional, improves accuracy)
      prompt          — optional text to guide the model
      response_format — json | text | srt | verbose_json | vtt (default: json)
      temperature     — 0-1 (optional)
    """
    import base64

    file_content = config.get("file") if config.get("file") is not None else input_data.get("file")
    if not file_content:
        raise ValueError("openai.transcribe_audio requires 'file' content")

    filename = config.get("filename") or input_data.get("filename") or "audio.mp3"
    model = config.get("model") or input_data.get("model") or "whisper-1"

    if isinstance(file_content, str):
        raw_bytes = base64.b64decode(file_content)
    else:
        raw_bytes = bytes(file_content)

    creds = await get_credential_data(credential_id, db)
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("OpenAI credential missing 'api_key'")
    headers = {"Authorization": f"Bearer {api_key}"}
    org = creds.get("organization")
    if org:
        headers["OpenAI-Organization"] = org

    data: dict = {"model": model}
    for field in ("language", "prompt", "response_format", "temperature"):
        val = config.get(field) if config.get(field) is not None else input_data.get(field)
        if val is not None:
            data[field] = str(val)

    log.info("openai.transcribe_audio", model=model, filename=filename, bytes=len(raw_bytes))
    async with httpx.AsyncClient(base_url=_BASE_URL, headers=headers, timeout=120.0) as client:
        r = await client.post(
            "audio/transcriptions",
            files={"file": (filename, raw_bytes)},
            data=data,
        )
    return _check(r)


@register_node("openai.list_models")
async def list_models(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    GET /models — list all available OpenAI models.

    Config (optional):
      filter — string to filter model IDs by prefix (e.g. gpt, dall-e)
    """
    log.info("openai.list_models")
    async with await _client(credential_id, db) as client:
        r = await client.get("models")
    data = _check(r)

    filter_str = config.get("filter") or input_data.get("filter")
    if filter_str and isinstance(data.get("data"), list):
        data["data"] = [m for m in data["data"] if filter_str.lower() in m.get("id", "").lower()]

    return data


async def test_connection(creds: dict) -> None:
    """Verify OpenAI API key by listing models."""
    api_key = creds.get("api_key")
    if not api_key:
        raise ValueError("OpenAI requires 'api_key'")
    headers = {"Authorization": f"Bearer {api_key}"}
    org = creds.get("organization")
    if org:
        headers["OpenAI-Organization"] = org
    async with httpx.AsyncClient(base_url=_BASE_URL, headers=headers, timeout=15.0) as client:
        r = await client.get("models")
    if not r.is_success:
        raise ValueError(f"OpenAI connection failed: {r.status_code}")
