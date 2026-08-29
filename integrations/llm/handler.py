"""
Extended LLM nodes — Google Gemini, Ollama, HuggingFace, Cohere, Mistral,
Groq, Azure OpenAI, and supporting utilities (embeddings, streaming stubs).

Node IDs follow the same pattern as integrations/ai/handler.py so the
execution engine can dispatch them uniformly.
"""
import json
import re

import httpx
import structlog

from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)


def _render(template: str, data: dict) -> str:
    if not isinstance(template, str):
        return template

    def repl(m):
        path = m.group(1).strip().split(".")
        val = data
        for p in path:
            val = val.get(p) if isinstance(val, dict) else None
        return "" if val is None else (val if isinstance(val, str) else json.dumps(val))

    return re.sub(r"\{\{\s*([\w\.]+)\s*\}\}", repl, template)


# ─── Google Gemini ─────────────────────────────────────────────────────────────

@register_node("llm.gemini")
async def llm_gemini(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Chat completion via Google Gemini API.
    Requires GOOGLE_API_KEY in environment.
    """
    api_key = getattr(settings, "GOOGLE_API_KEY", None)
    if not api_key:
        raise ValueError("llm.gemini requires GOOGLE_API_KEY in environment")

    model = config.get("model", "gemini-1.5-flash")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    contents = []
    if system_prompt:
        contents.append({"role": "user", "parts": [{"text": f"[System]: {system_prompt}"}]})
        contents.append({"role": "model", "parts": [{"text": "Understood."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = {
        "contents": contents,
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return {"text": text, "provider": "gemini", "model": model}


# ─── Ollama (local) ────────────────────────────────────────────────────────────

@register_node("llm.ollama")
async def llm_ollama(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Chat completion via local Ollama instance.
    OLLAMA_BASE_URL defaults to http://localhost:11434.
    """
    base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
    model = config.get("model", "llama3")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    temperature = float(config.get("temperature", 0.7))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {"model": model, "messages": messages, "stream": False,
               "options": {"temperature": temperature}}

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(f"{base_url}/api/chat", json=payload)
        r.raise_for_status()
        data = r.json()

    text = data["message"]["content"]
    return {"text": text, "provider": "ollama", "model": model}


@register_node("llm.ollama_embed")
async def llm_ollama_embed(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Embeddings via Ollama."""
    base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
    model = config.get("model", "nomic-embed-text")
    text = config.get("text") or input_data.get("text", "")

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(f"{base_url}/api/embeddings", json={"model": model, "prompt": text})
        r.raise_for_status()
        data = r.json()

    return {"embedding": data["embedding"], "model": model, "provider": "ollama"}


# ─── HuggingFace Inference API ────────────────────────────────────────────────

@register_node("llm.huggingface")
async def llm_huggingface(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Text generation via HuggingFace Inference API.
    Requires HUGGINGFACE_API_KEY.
    """
    api_key = getattr(settings, "HUGGINGFACE_API_KEY", None)
    if not api_key:
        raise ValueError("llm.huggingface requires HUGGINGFACE_API_KEY in environment")

    model = config.get("model", "mistralai/Mistral-7B-Instruct-v0.3")
    prompt = _render(config.get("prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 512))
    temperature = float(config.get("temperature", 0.7))

    url = f"https://api-inference.huggingface.co/models/{model}"
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": max_tokens, "temperature": temperature, "return_full_text": False},
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    if isinstance(data, list):
        text = data[0].get("generated_text", "")
    else:
        text = data.get("generated_text", str(data))

    return {"text": text, "provider": "huggingface", "model": model}


@register_node("llm.huggingface_embed")
async def llm_huggingface_embed(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Embeddings via HuggingFace feature-extraction endpoint."""
    api_key = getattr(settings, "HUGGINGFACE_API_KEY", None)
    if not api_key:
        raise ValueError("llm.huggingface_embed requires HUGGINGFACE_API_KEY")

    model = config.get("model", "sentence-transformers/all-MiniLM-L6-v2")
    text = config.get("text") or input_data.get("text", "")

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://api-inference.huggingface.co/models/{model}",
            json={"inputs": text},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    embedding = data if isinstance(data, list) else data.get("embedding", [])
    return {"embedding": embedding, "model": model, "provider": "huggingface"}


# ─── Cohere ────────────────────────────────────────────────────────────────────

@register_node("llm.cohere")
async def llm_cohere(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Chat completion via Cohere API.
    Requires COHERE_API_KEY.
    """
    api_key = getattr(settings, "COHERE_API_KEY", None)
    if not api_key:
        raise ValueError("llm.cohere requires COHERE_API_KEY in environment")

    model = config.get("model", "command-r-plus")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    payload = {
        "model": model,
        "message": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if system_prompt:
        payload["preamble"] = system_prompt

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.cohere.ai/v1/chat",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()

    text = data["text"]
    return {"text": text, "provider": "cohere", "model": model}


@register_node("llm.cohere_embed")
async def llm_cohere_embed(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Embeddings via Cohere."""
    api_key = getattr(settings, "COHERE_API_KEY", None)
    if not api_key:
        raise ValueError("llm.cohere_embed requires COHERE_API_KEY")

    model = config.get("model", "embed-english-v3.0")
    texts = config.get("texts") or input_data.get("texts") or [config.get("text") or input_data.get("text", "")]
    input_type = config.get("input_type", "search_document")

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.cohere.ai/v1/embed",
            json={"texts": texts, "model": model, "input_type": input_type},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    return {"embeddings": data["embeddings"], "model": model, "provider": "cohere"}


# ─── Mistral ───────────────────────────────────────────────────────────────────

@register_node("llm.mistral")
async def llm_mistral(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Chat completion via Mistral AI API.
    Requires MISTRAL_API_KEY.
    """
    api_key = getattr(settings, "MISTRAL_API_KEY", None)
    if not api_key:
        raise ValueError("llm.mistral requires MISTRAL_API_KEY in environment")

    model = config.get("model", "mistral-small-latest")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.mistral.ai/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {"text": text, "provider": "mistral", "model": model}


# ─── Groq ──────────────────────────────────────────────────────────────────────

@register_node("llm.groq")
async def llm_groq(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Fast inference via Groq (LLaMA, Mixtral, Gemma).
    Requires GROQ_API_KEY.
    """
    api_key = getattr(settings, "GROQ_API_KEY", None)
    if not api_key:
        raise ValueError("llm.groq requires GROQ_API_KEY in environment")

    model = config.get("model", "llama3-8b-8192")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {"text": text, "provider": "groq", "model": model}


# ─── Azure OpenAI ──────────────────────────────────────────────────────────────

@register_node("llm.azure_openai")
async def llm_azure_openai(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Chat completion via Azure OpenAI.
    Requires AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT.
    """
    api_key = getattr(settings, "AZURE_OPENAI_API_KEY", None)
    endpoint = getattr(settings, "AZURE_OPENAI_ENDPOINT", None)
    if not api_key or not endpoint:
        raise ValueError("llm.azure_openai requires AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT")

    deployment = config.get("deployment") or getattr(settings, "AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    api_version = config.get("api_version", "2024-02-01")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            url,
            json={"messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers={"api-key": api_key},
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {"text": text, "provider": "azure_openai", "model": deployment}


# ─── Together AI ───────────────────────────────────────────────────────────────

@register_node("llm.together_ai")
async def llm_together_ai(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Inference via Together AI (open-source model hosting).
    Requires TOGETHER_API_KEY.
    """
    api_key = getattr(settings, "TOGETHER_API_KEY", None)
    if not api_key:
        raise ValueError("llm.together_ai requires TOGETHER_API_KEY")

    model = config.get("model", "meta-llama/Llama-3-8b-chat-hf")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.together.xyz/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {"text": text, "provider": "together_ai", "model": model}


# ─── Perplexity ────────────────────────────────────────────────────────────────

@register_node("llm.perplexity")
async def llm_perplexity(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Search-augmented chat via Perplexity AI.
    Requires PERPLEXITY_API_KEY.
    """
    api_key = getattr(settings, "PERPLEXITY_API_KEY", None)
    if not api_key:
        raise ValueError("llm.perplexity requires PERPLEXITY_API_KEY")

    model = config.get("model", "llama-3.1-sonar-small-128k-online")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.perplexity.ai/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])
    return {"text": text, "citations": citations, "provider": "perplexity", "model": model}


# ─── Replicate ─────────────────────────────────────────────────────────────────

@register_node("llm.replicate")
async def llm_replicate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Run any Replicate model (text-to-text or text-to-image).
    Requires REPLICATE_API_KEY.
    """
    api_key = getattr(settings, "REPLICATE_API_KEY", None)
    if not api_key:
        raise ValueError("llm.replicate requires REPLICATE_API_KEY")

    model_version = config.get("model_version")
    if not model_version:
        raise ValueError("llm.replicate requires 'model_version' (e.g. owner/model:sha256...)")

    input_payload = config.get("input") or {}
    prompt = _render(config.get("prompt", ""), input_data)
    if prompt:
        input_payload["prompt"] = prompt

    async with httpx.AsyncClient(timeout=300) as client:
        # Create prediction
        r = await client.post(
            "https://api.replicate.com/v1/predictions",
            json={"version": model_version, "input": input_payload},
            headers={"Authorization": f"Token {api_key}"},
        )
        r.raise_for_status()
        pred = r.json()

        # Poll until done
        import asyncio
        poll_url = pred["urls"]["get"]
        for _ in range(60):
            await asyncio.sleep(2)
            pr = await client.get(poll_url, headers={"Authorization": f"Token {api_key}"})
            pr.raise_for_status()
            state = pr.json()
            if state["status"] in ("succeeded", "failed", "canceled"):
                break

    output = state.get("output")
    if isinstance(output, list):
        output = "".join(output)

    return {"output": output, "status": state["status"], "provider": "replicate"}

# ─── AWS Bedrock ───────────────────────────────────────────────────────────────

@register_node("llm.aws_bedrock")
async def llm_aws_bedrock(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chat/text via AWS Bedrock (Claude, Llama, Titan, Mistral on AWS).
    Requires AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION.
    config: model_id, prompt, system_prompt, max_tokens, temperature
    """
    try:
        import boto3
        import asyncio as _asyncio
    except ImportError:
        raise RuntimeError("llm.aws_bedrock requires boto3: pip install boto3")

    import json as _json

    access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None)
    secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
    region = config.get("region") or getattr(settings, "AWS_REGION", "us-east-1")

    model_id = config.get("model_id", "anthropic.claude-3-haiku-20240307-v1:0")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    client_kwargs = {"region_name": region}
    if access_key:
        client_kwargs["aws_access_key_id"] = access_key
    if secret_key:
        client_kwargs["aws_secret_access_key"] = secret_key

    def _invoke():
        bedrock = boto3.client("bedrock-runtime", **client_kwargs)
        if "anthropic" in model_id:
            body = _json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt or None,
                "messages": [{"role": "user", "content": prompt}],
            })
        elif "meta" in model_id or "llama" in model_id.lower():
            body = _json.dumps({
                "prompt": f"<s>[INST] {prompt} [/INST]",
                "max_gen_len": max_tokens,
                "temperature": temperature,
            })
        else:
            body = _json.dumps({
                "inputText": prompt,
                "textGenerationConfig": {"maxTokenCount": max_tokens, "temperature": temperature},
            })
        response = bedrock.invoke_model(
            modelId=model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = _json.loads(response["body"].read())
        return result

    result = await _asyncio.get_event_loop().run_in_executor(None, _invoke)

    if "anthropic" in model_id:
        text = result.get("content", [{}])[0].get("text", "")
    elif "meta" in model_id or "llama" in model_id.lower():
        text = result.get("generation", "")
    else:
        text = result.get("results", [{}])[0].get("outputText", "")

    return {"text": text, "provider": "aws_bedrock", "model": model_id}


# ─── OpenRouter ────────────────────────────────────────────────────────────────

@register_node("llm.openrouter")
async def llm_openrouter(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Access 200+ models through OpenRouter (OpenAI-compatible API).
    Requires OPENROUTER_API_KEY.
    config: model (e.g. "anthropic/claude-3-haiku"), prompt, system_prompt, max_tokens, temperature
    """
    api_key = getattr(settings, "OPENROUTER_API_KEY", None)
    if not api_key:
        raise ValueError("llm.openrouter requires OPENROUTER_API_KEY")

    model = config.get("model", "openai/gpt-4o-mini")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers={
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://autoflow.ai",
                "X-Title": "AutoFlow",
            },
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {"text": text, "provider": "openrouter", "model": model}


# ─── Deepseek ──────────────────────────────────────────────────────────────────

@register_node("llm.deepseek")
async def llm_deepseek(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chat completion via Deepseek API (OpenAI-compatible).
    Requires DEEPSEEK_API_KEY.
    config: model (deepseek-chat | deepseek-reasoner), prompt, system_prompt, max_tokens, temperature
    """
    api_key = getattr(settings, "DEEPSEEK_API_KEY", None)
    if not api_key:
        raise ValueError("llm.deepseek requires DEEPSEEK_API_KEY")

    model = config.get("model", "deepseek-chat")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.deepseek.com/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    reasoning = data["choices"][0]["message"].get("reasoning_content", "")
    return {"text": text, "reasoning": reasoning, "provider": "deepseek", "model": model}


# ─── xAI / Grok ────────────────────────────────────────────────────────────────

@register_node("llm.xai")
async def llm_xai(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chat completion via xAI Grok (OpenAI-compatible API).
    Requires XAI_API_KEY.
    config: model (grok-beta | grok-2-1212), prompt, system_prompt, max_tokens, temperature
    """
    api_key = getattr(settings, "XAI_API_KEY", None)
    if not api_key:
        raise ValueError("llm.xai requires XAI_API_KEY")

    model = config.get("model", "grok-beta")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.x.ai/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {"text": text, "provider": "xai", "model": model}


# ─── Fireworks AI ──────────────────────────────────────────────────────────────

@register_node("llm.fireworks")
async def llm_fireworks(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Fast inference via Fireworks AI (OpenAI-compatible).
    Requires FIREWORKS_API_KEY.
    config: model (accounts/fireworks/models/llama-v3p1-8b-instruct), prompt, system_prompt
    """
    api_key = getattr(settings, "FIREWORKS_API_KEY", None)
    if not api_key:
        raise ValueError("llm.fireworks requires FIREWORKS_API_KEY")

    model = config.get("model", "accounts/fireworks/models/llama-v3p1-8b-instruct")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.fireworks.ai/inference/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {"text": text, "provider": "fireworks", "model": model}


# ─── Cerebras ──────────────────────────────────────────────────────────────────

@register_node("llm.cerebras")
async def llm_cerebras(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Ultra-fast inference via Cerebras (OpenAI-compatible).
    Requires CEREBRAS_API_KEY.
    config: model (llama3.1-8b | llama3.1-70b), prompt, system_prompt, max_tokens, temperature
    """
    api_key = getattr(settings, "CEREBRAS_API_KEY", None)
    if not api_key:
        raise ValueError("llm.cerebras requires CEREBRAS_API_KEY")

    model = config.get("model", "llama3.1-8b")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.cerebras.ai/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {"text": text, "provider": "cerebras", "model": model}


# ─── SambaNova ─────────────────────────────────────────────────────────────────

@register_node("llm.sambanova")
async def llm_sambanova(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Inference via SambaNova Cloud (OpenAI-compatible).
    Requires SAMBANOVA_API_KEY.
    config: model (Meta-Llama-3.1-8B-Instruct), prompt, system_prompt, max_tokens, temperature
    """
    api_key = getattr(settings, "SAMBANOVA_API_KEY", None)
    if not api_key:
        raise ValueError("llm.sambanova requires SAMBANOVA_API_KEY")

    model = config.get("model", "Meta-Llama-3.1-8B-Instruct")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.sambanova.ai/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers={"Authorization": f"Bearer {api_key}"},
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {"text": text, "provider": "sambanova", "model": model}


# ─── LocalAI ───────────────────────────────────────────────────────────────────

@register_node("llm.local_ai")
async def llm_local_ai(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Local self-hosted LLM via LocalAI (OpenAI-compatible REST API).
    config: base_url (default http://localhost:8080), model, prompt, system_prompt, max_tokens, temperature
    """
    base_url = config.get("base_url") or getattr(settings, "LOCAL_AI_BASE_URL", "http://localhost:8080")
    model = config.get("model", "gpt-3.5-turbo")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))
    api_key = config.get("api_key") or getattr(settings, "LOCAL_AI_API_KEY", "")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {"text": text, "provider": "local_ai", "model": model}


# ─── LiteLLM Proxy ─────────────────────────────────────────────────────────────

@register_node("llm.litellm")
async def llm_litellm(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Route to any LLM via LiteLLM proxy (OpenAI-compatible).
    config: base_url (LiteLLM proxy URL), model, prompt, system_prompt, max_tokens, temperature, api_key
    """
    base_url = config.get("base_url") or getattr(settings, "LITELLM_BASE_URL", "http://localhost:4000")
    model = config.get("model", "gpt-3.5-turbo")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))
    api_key = config.get("api_key") or getattr(settings, "LITELLM_API_KEY", "")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    async with httpx.AsyncClient(timeout=300) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            json={"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {"text": text, "provider": "litellm", "model": model}


# ─── Alibaba Tongyi (DashScope) ────────────────────────────────────────────────

@register_node("llm.alibaba_tongyi")
async def llm_alibaba_tongyi(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chat completion via Alibaba Cloud DashScope (Tongyi Qianwen series).
    Requires ALIBABA_API_KEY.
    config: model (qwen-turbo | qwen-plus | qwen-max), prompt, system_prompt, max_tokens, temperature
    """
    api_key = getattr(settings, "ALIBABA_API_KEY", None)
    if not api_key:
        raise ValueError(
            "llm.alibaba_tongyi requires ALIBABA_API_KEY in environment "
            "(obtain from https://dashscope.console.aliyun.com/)"
        )

    model = config.get("model", "qwen-turbo")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = config.get("messages") or input_data.get("messages") or []
    if not messages:
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

    url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
    payload = {
        "model": model,
        "input": {"messages": messages},
        "parameters": {
            "max_tokens": max_tokens,
            "temperature": temperature,
            "result_format": "message",
        },
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()

    if "code" in data and data["code"] != 200 and data.get("code"):
        raise RuntimeError(f"DashScope error {data.get('code')}: {data.get('message', data)}")

    output = data.get("output", {})
    text = (
        output.get("text")
        or (output.get("choices") or [{}])[0].get("message", {}).get("content", "")
    )
    usage = data.get("usage", {})
    return {
        "text": text,
        "provider": "alibaba_tongyi",
        "model": model,
        "usage": usage,
    }


# ─── Baidu ERNIE (Wenxin) ──────────────────────────────────────────────────────

@register_node("llm.baidu_wenxin")
async def llm_baidu_wenxin(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chat completion via Baidu ERNIE (Wenxin Yiyan).
    Requires BAIDU_API_KEY and BAIDU_SECRET_KEY.
    config: model_endpoint (completions_pro | completions | ernie_bot_turbo), prompt, system_prompt,
            max_tokens, temperature
    """
    api_key = getattr(settings, "BAIDU_API_KEY", None)
    secret_key = getattr(settings, "BAIDU_SECRET_KEY", None)
    if not api_key or not secret_key:
        raise ValueError(
            "llm.baidu_wenxin requires both BAIDU_API_KEY and BAIDU_SECRET_KEY in environment "
            "(obtain from https://console.bce.baidu.com/qianfan/)"
        )

    # Step 1: fetch OAuth2 access token
    token_url = "https://aip.baidubce.com/oauth/2.0/token"
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            token_url,
            params={
                "grant_type": "client_credentials",
                "client_id": api_key,
                "client_secret": secret_key,
            },
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()

    access_token = token_data.get("access_token")
    if not access_token:
        raise RuntimeError(
            f"Baidu OAuth token exchange failed: {token_data.get('error_description', token_data)}"
        )

    # Step 2: build chat request
    model_endpoint = config.get("model_endpoint", "completions_pro")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = config.get("messages") or input_data.get("messages") or []
    if not messages:
        messages = [{"role": "user", "content": prompt}]

    payload: dict = {
        "messages": messages,
        "max_output_tokens": max_tokens,
        "temperature": temperature,
    }
    if system_prompt:
        payload["system"] = system_prompt

    chat_url = (
        f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{model_endpoint}"
        f"?access_token={access_token}"
    )

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(chat_url, json=payload, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()

    if "error_code" in data:
        raise RuntimeError(f"Baidu ERNIE error {data['error_code']}: {data.get('error_msg', data)}")

    text = data.get("result", "")
    return {
        "text": text,
        "provider": "baidu_wenxin",
        "model": model_endpoint,
        "usage": data.get("usage", {}),
        "is_truncated": data.get("is_truncated", False),
    }


# ─── Cloudflare Workers AI ─────────────────────────────────────────────────────

@register_node("llm.cloudflare_workers_ai")
async def llm_cloudflare_workers_ai(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Inference via Cloudflare Workers AI.
    Requires CLOUDFLARE_API_KEY and CLOUDFLARE_ACCOUNT_ID.
    config: model (@cf/meta/llama-2-7b-chat-int8 | @cf/mistral/mistral-7b-instruct-v0.1 | ...),
            prompt, system_prompt, max_tokens
    """
    api_key = getattr(settings, "CLOUDFLARE_API_KEY", None)
    account_id = getattr(settings, "CLOUDFLARE_ACCOUNT_ID", None)
    if not api_key or not account_id:
        raise ValueError(
            "llm.cloudflare_workers_ai requires both CLOUDFLARE_API_KEY and CLOUDFLARE_ACCOUNT_ID "
            "(obtain from https://dash.cloudflare.com/profile/api-tokens)"
        )

    model = config.get("model", "@cf/meta/llama-2-7b-chat-int8")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))

    messages = config.get("messages") or input_data.get("messages") or []
    if not messages:
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{model}"
    payload = {"messages": messages, "max_tokens": max_tokens}

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()

    if not data.get("success", True):
        errors = data.get("errors", [])
        raise RuntimeError(f"Cloudflare Workers AI error: {errors}")

    result = data.get("result", {})
    text = result.get("response", "")
    return {
        "text": text,
        "provider": "cloudflare_workers_ai",
        "model": model,
    }


# ─── Comet ML API ──────────────────────────────────────────────────────────────

@register_node("llm.comet_api")
async def llm_comet_api(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chat completion via Comet ML API (OpenAI-compatible endpoint).
    Requires COMET_API_KEY.
    config: model, prompt, system_prompt, max_tokens, temperature
    """
    api_key = getattr(settings, "COMET_API_KEY", None)
    if not api_key:
        raise ValueError(
            "llm.comet_api requires COMET_API_KEY in environment "
            "(obtain from https://www.comet.com/)"
        )

    model = config.get("model", "command-r-plus")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = config.get("messages") or input_data.get("messages") or []
    if not messages:
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

    base_url = config.get("base_url", "https://www.comet.com/api")

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/v1/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {
        "text": text,
        "provider": "comet_api",
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
    }


# ─── Google Vertex AI (Chat) ───────────────────────────────────────────────────

@register_node("llm.google_vertex")
async def llm_google_vertex(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chat completion via Google Vertex AI (Gemini models on Vertex).
    Requires GOOGLE_CLOUD_PROJECT_ID and either VERTEX_AI_API_KEY or
    GOOGLE_APPLICATION_CREDENTIALS pointing to a service-account JSON file.
    config: model (gemini-1.5-pro | gemini-1.5-flash | gemini-1.0-pro), location,
            prompt, system_prompt, max_tokens, temperature
    """
    project_id = getattr(settings, "GOOGLE_CLOUD_PROJECT_ID", None)
    if not project_id:
        raise ValueError(
            "llm.google_vertex requires GOOGLE_CLOUD_PROJECT_ID in environment"
        )

    api_key = getattr(settings, "VERTEX_AI_API_KEY", None)
    credentials_path = getattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", None)

    if not api_key and not credentials_path:
        raise ValueError(
            "llm.google_vertex requires either VERTEX_AI_API_KEY or "
            "GOOGLE_APPLICATION_CREDENTIALS (path to service-account JSON) in environment"
        )

    model = config.get("model", "gemini-1.5-pro")
    location = config.get("location", "us-central1")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    # Build Vertex AI generateContent request (same schema as Gemini REST)
    contents = []
    if system_prompt:
        contents.append({"role": "user", "parts": [{"text": f"[System]: {system_prompt}"}]})
        contents.append({"role": "model", "parts": [{"text": "Understood."}]})
    contents.append({"role": "user", "parts": [{"text": prompt}]})

    payload = {
        "contents": contents,
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
        },
    }

    url = (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}"
        f"/locations/{location}/publishers/google/models/{model}:generateContent"
    )

    # Resolve auth header
    if api_key:
        auth_header = {"x-goog-api-key": api_key}
    else:
        # Attempt to load credentials from service-account JSON
        import asyncio as _asyncio

        def _get_token():
            try:
                import google.auth
                import google.auth.transport.requests
                creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                creds.refresh(google.auth.transport.requests.Request())
                return creds.token
            except Exception as exc:
                raise RuntimeError(
                    f"llm.google_vertex: failed to obtain access token from service-account credentials: {exc}"
                ) from exc

        token = await _asyncio.get_event_loop().run_in_executor(None, _get_token)
        auth_header = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=payload, headers={**auth_header, "Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return {
        "text": text,
        "provider": "google_vertex",
        "model": model,
        "project": project_id,
        "location": location,
    }


# ─── Google Vertex AI (Text Completion) ───────────────────────────────────────

@register_node("llm.google_vertex_completion")
async def llm_google_vertex_completion(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Text completion via Google Vertex AI (PaLM / text-bison family).
    Requires GOOGLE_CLOUD_PROJECT_ID and either VERTEX_AI_API_KEY or
    GOOGLE_APPLICATION_CREDENTIALS.
    config: model (text-bison | text-bison-32k | text-unicorn), location,
            prompt, max_tokens, temperature, top_p, top_k
    """
    project_id = getattr(settings, "GOOGLE_CLOUD_PROJECT_ID", None)
    if not project_id:
        raise ValueError("llm.google_vertex_completion requires GOOGLE_CLOUD_PROJECT_ID in environment")

    api_key = getattr(settings, "VERTEX_AI_API_KEY", None)
    credentials_path = getattr(settings, "GOOGLE_APPLICATION_CREDENTIALS", None)

    if not api_key and not credentials_path:
        raise ValueError(
            "llm.google_vertex_completion requires either VERTEX_AI_API_KEY or "
            "GOOGLE_APPLICATION_CREDENTIALS in environment"
        )

    model = config.get("model", "text-bison")
    location = config.get("location", "us-central1")
    prompt = _render(config.get("prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))
    top_p = float(config.get("top_p", 0.95))
    top_k = int(config.get("top_k", 40))

    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "maxOutputTokens": max_tokens,
            "temperature": temperature,
            "topP": top_p,
            "topK": top_k,
        },
    }

    url = (
        f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}"
        f"/locations/{location}/publishers/google/models/{model}:predict"
    )

    if api_key:
        auth_header = {"x-goog-api-key": api_key}
    else:
        import asyncio as _asyncio

        def _get_token():
            try:
                import google.auth
                import google.auth.transport.requests
                creds, _ = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
                creds.refresh(google.auth.transport.requests.Request())
                return creds.token
            except Exception as exc:
                raise RuntimeError(
                    f"llm.google_vertex_completion: failed to obtain access token: {exc}"
                ) from exc

        token = await _asyncio.get_event_loop().run_in_executor(None, _get_token)
        auth_header = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=payload, headers={**auth_header, "Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()

    predictions = data.get("predictions", [{}])
    text = predictions[0].get("content", "")
    return {
        "text": text,
        "provider": "google_vertex_completion",
        "model": model,
        "project": project_id,
        "location": location,
    }


# ─── IBM watsonx.ai (Chat) ─────────────────────────────────────────────────────

@register_node("llm.ibm_watsonx")
async def llm_ibm_watsonx(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chat / text generation via IBM watsonx.ai.
    Requires IBM_WATSONX_API_KEY, IBM_WATSONX_PROJECT_ID, and IBM_WATSONX_URL.
    config: model_id (ibm/granite-13b-chat-v2 | meta-llama/llama-3-8b-instruct | ...),
            prompt, system_prompt, max_tokens, temperature, top_p
    """
    api_key = getattr(settings, "IBM_WATSONX_API_KEY", None)
    project_id = getattr(settings, "IBM_WATSONX_PROJECT_ID", None)
    watsonx_url = getattr(settings, "IBM_WATSONX_URL", None)

    if not api_key:
        raise ValueError("llm.ibm_watsonx requires IBM_WATSONX_API_KEY in environment")
    if not project_id:
        raise ValueError("llm.ibm_watsonx requires IBM_WATSONX_PROJECT_ID in environment")
    if not watsonx_url:
        raise ValueError(
            "llm.ibm_watsonx requires IBM_WATSONX_URL in environment "
            "(e.g. https://us-south.ml.cloud.ibm.com)"
        )

    # Step 1: exchange IBM API key for IAM Bearer token
    async with httpx.AsyncClient(timeout=30) as client:
        iam_resp = await client.post(
            "https://iam.cloud.ibm.com/identity/token",
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": api_key,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        iam_resp.raise_for_status()
        iam_data = iam_resp.json()

    access_token = iam_data.get("access_token")
    if not access_token:
        raise RuntimeError(f"IBM IAM token exchange failed: {iam_data.get('errorMessage', iam_data)}")

    # Step 2: text generation request
    model_id = config.get("model_id", "ibm/granite-13b-chat-v2")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))
    top_p = float(config.get("top_p", 1.0))

    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"
    else:
        full_prompt = prompt

    payload = {
        "model_id": model_id,
        "input": full_prompt,
        "parameters": {
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        },
        "project_id": project_id,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{watsonx_url.rstrip('/')}/ml/v1/text/generation?version=2023-05-29",
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()

    results = data.get("results", [{}])
    text = results[0].get("generated_text", "")
    return {
        "text": text,
        "provider": "ibm_watsonx",
        "model": model_id,
        "stop_reason": results[0].get("stop_reason"),
        "usage": {
            "input_token_count": data.get("system", {}).get("warnings", []),
            "generated_token_count": results[0].get("generated_token_count"),
        },
    }


# ─── IBM watsonx.ai (Text Completion) ─────────────────────────────────────────

@register_node("llm.ibm_watsonx_completion")
async def llm_ibm_watsonx_completion(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Text completion (streaming-compatible) via IBM watsonx.ai /text/generation_stream.
    Requires IBM_WATSONX_API_KEY, IBM_WATSONX_PROJECT_ID, IBM_WATSONX_URL.
    config: model_id, prompt, max_tokens, temperature, decoding_method (greedy | sample)
    """
    api_key = getattr(settings, "IBM_WATSONX_API_KEY", None)
    project_id = getattr(settings, "IBM_WATSONX_PROJECT_ID", None)
    watsonx_url = getattr(settings, "IBM_WATSONX_URL", None)

    if not api_key:
        raise ValueError("llm.ibm_watsonx_completion requires IBM_WATSONX_API_KEY in environment")
    if not project_id:
        raise ValueError("llm.ibm_watsonx_completion requires IBM_WATSONX_PROJECT_ID in environment")
    if not watsonx_url:
        raise ValueError(
            "llm.ibm_watsonx_completion requires IBM_WATSONX_URL in environment "
            "(e.g. https://us-south.ml.cloud.ibm.com)"
        )

    # IAM token exchange
    async with httpx.AsyncClient(timeout=30) as client:
        iam_resp = await client.post(
            "https://iam.cloud.ibm.com/identity/token",
            data={
                "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                "apikey": api_key,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        iam_resp.raise_for_status()
        iam_data = iam_resp.json()

    access_token = iam_data.get("access_token")
    if not access_token:
        raise RuntimeError(f"IBM IAM token exchange failed: {iam_data.get('errorMessage', iam_data)}")

    model_id = config.get("model_id", "ibm/granite-13b-instruct-v2")
    prompt = _render(config.get("prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 512))
    temperature = float(config.get("temperature", 0.7))
    decoding_method = config.get("decoding_method", "sample")

    payload = {
        "model_id": model_id,
        "input": prompt,
        "parameters": {
            "decoding_method": decoding_method,
            "max_new_tokens": max_tokens,
            "temperature": temperature,
        },
        "project_id": project_id,
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{watsonx_url.rstrip('/')}/ml/v1/text/generation?version=2023-05-29",
            json=payload,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()

    results = data.get("results", [{}])
    text = results[0].get("generated_text", "")
    return {
        "text": text,
        "provider": "ibm_watsonx_completion",
        "model": model_id,
        "stop_reason": results[0].get("stop_reason"),
    }


# ─── NeMo Guardrails ───────────────────────────────────────────────────────────

@register_node("llm.nemo_guardrails")
async def llm_nemo_guardrails(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Safety-wrapped LLM via NVIDIA NeMo Guardrails.
    Requires nemoguardrails package (pip install nemoguardrails) and
    NEMO_GUARDRAILS_CONFIG_PATH pointing to a Guardrails config directory.

    The node applies input/output content safety rails around any underlying
    LLM configured in the Guardrails config (Colang + config.yml).

    config: user_message (or falls back to input_data prompt / messages),
            config_path (override for NEMO_GUARDRAILS_CONFIG_PATH)
    """
    try:
        from nemoguardrails import RailsConfig, LLMRails  # type: ignore
    except ImportError:
        raise RuntimeError(
            "llm.nemo_guardrails requires the nemoguardrails package. "
            "Install it with: pip install nemoguardrails"
        )

    config_path = config.get("config_path") or getattr(settings, "NEMO_GUARDRAILS_CONFIG_PATH", None)
    if not config_path:
        raise ValueError(
            "llm.nemo_guardrails requires NEMO_GUARDRAILS_CONFIG_PATH in environment "
            "or 'config_path' in node config (path to a Guardrails config directory)"
        )

    # Resolve user message from config, input messages, or rendered prompt
    user_message = config.get("user_message") or None
    if not user_message:
        messages = config.get("messages") or input_data.get("messages") or []
        if messages:
            # Extract the last user message from a conversation history
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg["content"]
                    break
    if not user_message:
        user_message = _render(config.get("prompt", ""), input_data)
    if not user_message:
        raise ValueError("llm.nemo_guardrails: no user message found in config or input_data")

    import asyncio as _asyncio

    def _run_rails():
        rails_config = RailsConfig.from_path(config_path)
        rails = LLMRails(rails_config)
        # NeMo Guardrails applies both input and output rails automatically
        result = rails.generate(messages=[{"role": "user", "content": user_message}])
        return result

    try:
        result = await _asyncio.get_event_loop().run_in_executor(None, _run_rails)
    except Exception as exc:
        log.error("llm.nemo_guardrails execution error", error=str(exc))
        raise RuntimeError(f"NeMo Guardrails execution failed: {exc}") from exc

    # result is either a string or a dict with "content"
    if isinstance(result, dict):
        text = result.get("content", str(result))
    else:
        text = str(result)

    return {
        "text": text,
        "provider": "nemo_guardrails",
        "config_path": config_path,
        "guardrails_applied": True,
    }


# ─── NVIDIA NIM ────────────────────────────────────────────────────────────────

@register_node("llm.nvidia_nim")
async def llm_nvidia_nim(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Inference via NVIDIA NIM microservices (OpenAI-compatible API).
    Requires NVIDIA_API_KEY.
    config: model (meta/llama-3.1-8b-instruct | nvidia/nemotron-4-340b-instruct | ...),
            prompt, system_prompt, max_tokens, temperature
    """
    api_key = getattr(settings, "NVIDIA_API_KEY", None)
    if not api_key:
        raise ValueError(
            "llm.nvidia_nim requires NVIDIA_API_KEY in environment "
            "(obtain from https://build.nvidia.com/)"
        )

    model = config.get("model", "meta/llama-3.1-8b-instruct")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))
    top_p = float(config.get("top_p", 1.0))

    messages = config.get("messages") or input_data.get("messages") or []
    if not messages:
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

    base_url = config.get("base_url", "https://integrate.api.nvidia.com/v1")

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "stream": False,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {
        "text": text,
        "provider": "nvidia_nim",
        "model": data.get("model", model),
        "usage": data.get("usage", {}),
    }


# ─── OpenAI-Compatible Custom Endpoint ────────────────────────────────────────

@register_node("llm.openai_custom")
async def llm_openai_custom(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chat completion via any OpenAI-compatible API endpoint (vLLM, Anyscale,
    Lepton, Together, etc.) with a custom base URL.
    Requires OPENAI_CUSTOM_BASE_URL and OPENAI_CUSTOM_API_KEY.
    config: model, prompt, system_prompt, max_tokens, temperature,
            base_url (override), api_key (override)
    """
    base_url = (
        config.get("base_url")
        or getattr(settings, "OPENAI_CUSTOM_BASE_URL", None)
    )
    api_key = (
        config.get("api_key")
        or getattr(settings, "OPENAI_CUSTOM_API_KEY", None)
    )

    if not base_url:
        raise ValueError(
            "llm.openai_custom requires OPENAI_CUSTOM_BASE_URL in environment or 'base_url' in node config"
        )
    if not api_key:
        raise ValueError(
            "llm.openai_custom requires OPENAI_CUSTOM_API_KEY in environment or 'api_key' in node config"
        )

    model = config.get("model", "default")
    prompt = _render(config.get("prompt", ""), input_data)
    system_prompt = _render(config.get("system_prompt", ""), input_data)
    max_tokens = int(config.get("max_tokens", 1024))
    temperature = float(config.get("temperature", 0.7))

    messages = config.get("messages") or input_data.get("messages") or []
    if not messages:
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

    # Allow callers to pass extra body fields (e.g. top_p, stop, frequency_penalty)
    extra_body = config.get("extra_body") or {}

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            json={
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                **extra_body,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()

    text = data["choices"][0]["message"]["content"]
    return {
        "text": text,
        "provider": "openai_custom",
        "model": data.get("model", model),
        "base_url": base_url,
        "usage": data.get("usage", {}),
    }
