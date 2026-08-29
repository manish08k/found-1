"""
Tool nodes — Calculator, BraveSearch, Arxiv, SerpAPI, DuckDuckGo,
Wikipedia, CurrentDateTime, WeatherAPI, ExaSearch, Tavily, Wolfram Alpha.

These are utility/search nodes that an AI agent can call, or standalone
steps in a workflow.
"""
import asyncio
import json
import math
import re
import urllib.parse
from datetime import datetime, timezone

import httpx
import structlog

from core.execution_engine import register_node
from core.config import settings

log = structlog.get_logger(__name__)


# ─── Calculator ────────────────────────────────────────────────────────────────

@register_node("tool.calculator")
async def tool_calculator(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Safe arithmetic expression evaluator.
    Supports +, -, *, /, **, %, sqrt, abs, round, floor, ceil, log, pi, e.
    """
    expression = config.get("expression") or input_data.get("expression", "")
    expression = str(expression).strip()
    if not expression:
        raise ValueError("tool.calculator requires 'expression'")

    # Whitelist-only evaluation — no eval of arbitrary Python
    safe_names = {
        "sqrt": math.sqrt, "abs": abs, "round": round,
        "floor": math.floor, "ceil": math.ceil,
        "log": math.log, "log10": math.log10, "log2": math.log2,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "pi": math.pi, "e": math.e, "inf": math.inf,
        "pow": math.pow, "max": max, "min": min, "sum": sum,
    }

    # Allow only safe tokens
    if re.search(r"[a-zA-Z_][a-zA-Z0-9_]*", expression):
        allowed = set(safe_names.keys())
        found = set(re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", expression))
        disallowed = found - allowed
        if disallowed:
            raise ValueError(f"tool.calculator: disallowed identifiers: {disallowed}")

    try:
        result = eval(expression, {"__builtins__": {}}, safe_names)  # noqa: S307
    except Exception as e:
        raise ValueError(f"tool.calculator: could not evaluate '{expression}': {e}")

    return {"result": result, "expression": expression}


# ─── Current Date/Time ─────────────────────────────────────────────────────────

@register_node("tool.current_datetime")
async def tool_current_datetime(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Returns the current UTC datetime in multiple formats."""
    now = datetime.now(timezone.utc)
    fmt = config.get("format", "YYYY-MM-DD HH:mm:ss")
    # Convert simple arrow-style tokens
    fmt_map = {
        "YYYY": "%Y", "MM": "%m", "DD": "%d",
        "HH": "%H", "mm": "%M", "ss": "%S",
    }
    python_fmt = fmt
    for token, py in fmt_map.items():
        python_fmt = python_fmt.replace(token, py)

    return {
        "datetime": now.strftime(python_fmt),
        "iso": now.isoformat(),
        "timestamp": int(now.timestamp()),
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "year": now.year,
        "month": now.month,
        "day": now.day,
        "hour": now.hour,
        "minute": now.minute,
        "timezone": "UTC",
    }


# ─── Brave Search ──────────────────────────────────────────────────────────────

@register_node("tool.brave_search")
async def tool_brave_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Web search via Brave Search API.
    Requires BRAVE_SEARCH_API_KEY.
    """
    api_key = getattr(settings, "BRAVE_SEARCH_API_KEY", None)
    if not api_key:
        raise ValueError("tool.brave_search requires BRAVE_SEARCH_API_KEY in environment")

    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("tool.brave_search requires 'query'")

    count = int(config.get("count", 5))
    country = config.get("country", "us")
    search_lang = config.get("search_lang", "en")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": count, "country": country, "search_lang": search_lang},
            headers={"Accept": "application/json", "X-Subscription-Token": api_key},
        )
        r.raise_for_status()
        data = r.json()

    results = []
    for item in data.get("web", {}).get("results", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "description": item.get("description"),
        })

    return {
        "results": results,
        "query": query,
        "total": len(results),
        "summary": "\n".join(f"- {r['title']}: {r['url']}" for r in results),
    }


# ─── SerpAPI (Google Search) ───────────────────────────────────────────────────

@register_node("tool.serp_api")
async def tool_serp_api(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Google Search via SerpAPI.
    Requires SERPAPI_API_KEY.
    """
    api_key = getattr(settings, "SERPAPI_API_KEY", None)
    if not api_key:
        raise ValueError("tool.serp_api requires SERPAPI_API_KEY in environment")

    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("tool.serp_api requires 'query'")

    num = int(config.get("num", 5))
    hl = config.get("hl", "en")
    gl = config.get("gl", "us")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            "https://serpapi.com/search",
            params={"q": query, "num": num, "hl": hl, "gl": gl, "api_key": api_key, "engine": "google"},
        )
        r.raise_for_status()
        data = r.json()

    results = []
    for item in data.get("organic_results", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("link"),
            "snippet": item.get("snippet"),
            "position": item.get("position"),
        })

    answer_box = data.get("answer_box", {})
    return {
        "results": results,
        "answer": answer_box.get("answer") or answer_box.get("snippet"),
        "query": query,
        "total": len(results),
    }


# ─── DuckDuckGo Search (no-API) ────────────────────────────────────────────────

@register_node("tool.duckduckgo_search")
async def tool_duckduckgo_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Web search via DuckDuckGo instant answer API (no API key required).
    For richer results, use tool.brave_search or tool.serp_api.
    """
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("tool.duckduckgo_search requires 'query'")

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            headers={"User-Agent": "AutoFlow/1.0"},
        )
        r.raise_for_status()
        data = r.json()

    abstract = data.get("Abstract", "")
    answer = data.get("Answer", "")
    related = [{"text": r.get("Text"), "url": r.get("FirstURL")} for r in data.get("RelatedTopics", [])[:5]
               if isinstance(r, dict) and r.get("Text")]

    return {
        "abstract": abstract,
        "answer": answer or abstract,
        "source": data.get("AbstractSource"),
        "url": data.get("AbstractURL"),
        "related": related,
        "query": query,
    }


# ─── Wikipedia ─────────────────────────────────────────────────────────────────

@register_node("tool.wikipedia")
async def tool_wikipedia(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Fetches a Wikipedia article summary."""
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("tool.wikipedia requires 'query'")

    lang = config.get("lang", "en")
    sentences = int(config.get("sentences", 3))

    encoded = urllib.parse.quote(query.replace(" ", "_"))
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{encoded}"

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, headers={"User-Agent": "AutoFlow/1.0"})
        if r.status_code == 404:
            return {"found": False, "query": query, "extract": ""}
        r.raise_for_status()
        data = r.json()

    extract = data.get("extract", "")
    # Trim to requested sentences
    parts = extract.split(". ")
    trimmed = ". ".join(parts[:sentences]) + ("." if len(parts) > sentences else "")

    return {
        "title": data.get("title"),
        "extract": trimmed,
        "full_extract": extract,
        "url": data.get("content_urls", {}).get("desktop", {}).get("page"),
        "found": True,
        "query": query,
    }


# ─── Arxiv ─────────────────────────────────────────────────────────────────────

@register_node("tool.arxiv")
async def tool_arxiv(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Searches Arxiv for academic papers. No API key required."""
    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("tool.arxiv requires 'query'")

    max_results = int(config.get("max_results", 5))
    sort_by = config.get("sort_by", "relevance")  # relevance | lastUpdatedDate | submittedDate

    params = {
        "search_query": f"all:{urllib.parse.quote(query)}",
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": "descending",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get("http://export.arxiv.org/api/query", params=params)
        r.raise_for_status()
        xml = r.text

    # Simple XML parsing without lxml dependency
    entries = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)
    results = []
    for entry in entries:
        def extract(tag):
            m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", entry, re.DOTALL)
            return m.group(1).strip() if m else ""

        results.append({
            "title": extract("title"),
            "summary": extract("summary")[:500],
            "id": extract("id").split("/abs/")[-1],
            "url": extract("id"),
            "published": extract("published"),
            "authors": re.findall(r"<name>(.*?)</name>", entry),
        })

    return {"results": results, "query": query, "total": len(results)}


# ─── Weather (OpenWeatherMap) ──────────────────────────────────────────────────

@register_node("tool.weather")
async def tool_weather(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Current weather via OpenWeatherMap API.
    Requires OPENWEATHERMAP_API_KEY.
    """
    api_key = getattr(settings, "OPENWEATHERMAP_API_KEY", None)
    if not api_key:
        raise ValueError("tool.weather requires OPENWEATHERMAP_API_KEY")

    location = config.get("location") or input_data.get("location")
    if not location:
        raise ValueError("tool.weather requires 'location'")

    units = config.get("units", "metric")  # metric | imperial | standard

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": location, "appid": api_key, "units": units},
        )
        r.raise_for_status()
        data = r.json()

    return {
        "location": data.get("name"),
        "country": data.get("sys", {}).get("country"),
        "temperature": data["main"]["temp"],
        "feels_like": data["main"]["feels_like"],
        "humidity": data["main"]["humidity"],
        "description": data["weather"][0]["description"] if data.get("weather") else None,
        "wind_speed": data.get("wind", {}).get("speed"),
        "units": units,
    }


# ─── Tavily Search ─────────────────────────────────────────────────────────────

@register_node("tool.tavily_search")
async def tool_tavily_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    AI-optimized web search via Tavily.
    Requires TAVILY_API_KEY.
    """
    api_key = getattr(settings, "TAVILY_API_KEY", None)
    if not api_key:
        raise ValueError("tool.tavily_search requires TAVILY_API_KEY")

    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("tool.tavily_search requires 'query'")

    max_results = int(config.get("max_results", 5))
    search_depth = config.get("search_depth", "basic")  # basic | advanced
    include_answer = config.get("include_answer", True)
    include_raw_content = config.get("include_raw_content", False)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": search_depth,
                "include_answer": include_answer,
                "include_raw_content": include_raw_content,
            },
        )
        r.raise_for_status()
        data = r.json()

    return {
        "answer": data.get("answer"),
        "results": data.get("results", []),
        "query": query,
        "total": len(data.get("results", [])),
    }


# ─── Exa Search ────────────────────────────────────────────────────────────────

@register_node("tool.exa_search")
async def tool_exa_search(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Neural web search via Exa (formerly Metaphor).
    Requires EXA_API_KEY.
    """
    api_key = getattr(settings, "EXA_API_KEY", None)
    if not api_key:
        raise ValueError("tool.exa_search requires EXA_API_KEY")

    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("tool.exa_search requires 'query'")

    num_results = int(config.get("num_results", 5))
    use_autoprompt = config.get("use_autoprompt", True)
    include_text = config.get("include_text", True)

    payload = {
        "query": query,
        "numResults": num_results,
        "useAutoprompt": use_autoprompt,
    }
    if include_text:
        payload["contents"] = {"text": {"maxCharacters": 1000}}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.exa.ai/search",
            json=payload,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()

    results = []
    for item in data.get("results", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("url"),
            "score": item.get("score"),
            "text": item.get("text"),
            "published_date": item.get("publishedDate"),
        })

    return {"results": results, "query": query, "total": len(results)}


# ─── Code Interpreter (E2B sandbox) ────────────────────────────────────────────

@register_node("tool.code_interpreter")
async def tool_code_interpreter(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Execute Python code in an E2B cloud sandbox.
    Requires E2B_API_KEY. Falls back to local sandbox if key is absent.
    """
    code = config.get("code") or input_data.get("code", "")
    if not code:
        raise ValueError("tool.code_interpreter requires 'code'")

    e2b_key = getattr(settings, "E2B_API_KEY", None)
    if e2b_key:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.e2b.dev/sessions",
                json={"kernelName": "python3"},
                headers={"X-API-Key": e2b_key},
            )
            r.raise_for_status()
            session = r.json()
            session_id = session["id"]

            try:
                exec_r = await client.post(
                    f"https://api.e2b.dev/sessions/{session_id}/execute",
                    json={"code": code},
                    headers={"X-API-Key": e2b_key},
                )
                exec_r.raise_for_status()
                result = exec_r.json()
                return {
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                    "output": result.get("stdout", ""),
                    "provider": "e2b",
                }
            finally:
                await client.delete(
                    f"https://api.e2b.dev/sessions/{session_id}",
                    headers={"X-API-Key": e2b_key},
                )
    else:
        # Fallback to local sandboxed execution
        from core.sandbox import run_sandboxed
        return await run_sandboxed(code, input_data)


# ─── AWS SNS ───────────────────────────────────────────────────────────────────

@register_node("tool.aws_sns")
async def tool_aws_sns(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Publish a message to an AWS SNS topic.
    Requires AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION.
    """
    import hmac
    import hashlib
    import base64

    access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None)
    secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
    region = config.get("region") or getattr(settings, "AWS_REGION", "us-east-1")

    if not access_key or not secret_key:
        raise ValueError("tool.aws_sns requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")

    topic_arn = config.get("topic_arn") or input_data.get("topic_arn")
    message = config.get("message") or input_data.get("message", "")
    subject = config.get("subject") or input_data.get("subject")

    if not topic_arn:
        raise ValueError("tool.aws_sns requires 'topic_arn'")

    # Use boto3 if available, else raise helpful error
    try:
        import boto3
        sns = boto3.client(
            "sns",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )
        kwargs = {"TopicArn": topic_arn, "Message": message}
        if subject:
            kwargs["Subject"] = subject

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, lambda: sns.publish(**kwargs))
        return {"message_id": response["MessageId"], "ok": True}
    except ImportError:
        raise RuntimeError("tool.aws_sns requires boto3: pip install boto3")


# ─── AWS DynamoDB KV Storage ───────────────────────────────────────────────────

@register_node("tool.aws_dynamodb_kv")
async def tool_aws_dynamodb_kv(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Key-value storage operations on AWS DynamoDB.
    Operations: get | put | delete | scan
    """
    try:
        import boto3
    except ImportError:
        raise RuntimeError("tool.aws_dynamodb_kv requires boto3: pip install boto3")

    access_key = getattr(settings, "AWS_ACCESS_KEY_ID", None)
    secret_key = getattr(settings, "AWS_SECRET_ACCESS_KEY", None)
    region = config.get("region") or getattr(settings, "AWS_REGION", "us-east-1")

    table_name = config.get("table_name") or input_data.get("table_name")
    operation = config.get("operation", "get").lower()
    key_name = config.get("key_name", "id")
    key_value = config.get("key") or input_data.get("key")

    if not table_name:
        raise ValueError("tool.aws_dynamodb_kv requires 'table_name'")

    dynamo = boto3.resource(
        "dynamodb",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    table = dynamo.Table(table_name)
    loop = asyncio.get_event_loop()

    if operation == "get":
        if not key_value:
            raise ValueError("tool.aws_dynamodb_kv get requires 'key'")
        item = await loop.run_in_executor(None, lambda: table.get_item(Key={key_name: key_value}))
        return {"item": item.get("Item"), "found": "Item" in item}
    elif operation == "put":
        item = config.get("item") or input_data.get("item", {})
        if key_value:
            item[key_name] = key_value
        await loop.run_in_executor(None, lambda: table.put_item(Item=item))
        return {"ok": True, "operation": "put"}
    elif operation == "delete":
        if not key_value:
            raise ValueError("tool.aws_dynamodb_kv delete requires 'key'")
        await loop.run_in_executor(None, lambda: table.delete_item(Key={key_name: key_value}))
        return {"ok": True, "operation": "delete"}
    elif operation == "scan":
        result = await loop.run_in_executor(None, lambda: table.scan())
        return {"items": result.get("Items", []), "count": result.get("Count", 0)}
    else:
        raise ValueError(f"tool.aws_dynamodb_kv: unknown operation '{operation}'")

# ─── WolframAlpha ──────────────────────────────────────────────────────────────

@register_node("tool.wolfram_alpha")
async def tool_wolfram_alpha(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Computational intelligence via WolframAlpha Short Answers API.
    Requires WOLFRAM_ALPHA_APP_ID.
    config: query
    """
    app_id = getattr(settings, "WOLFRAM_ALPHA_APP_ID", None)
    if not app_id:
        raise ValueError("tool.wolfram_alpha requires WOLFRAM_ALPHA_APP_ID")

    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("tool.wolfram_alpha requires 'query'")

    async with httpx.AsyncClient(timeout=30) as client:
        # Short Answers API
        r = await client.get(
            "https://api.wolframalpha.com/v1/result",
            params={"appid": app_id, "i": query, "units": config.get("units", "metric")},
        )
        short_answer = r.text if r.status_code == 200 else None

        # Full Results API (XML → parsed)
        r2 = await client.get(
            "https://api.wolframalpha.com/v2/query",
            params={"appid": app_id, "input": query, "format": "plaintext", "output": "JSON"},
        )
        full_data = r2.json() if r2.status_code == 200 and "application/json" in r2.headers.get("content-type", "") else {}

    pods = []
    for pod in full_data.get("queryresult", {}).get("pods", []):
        for sub in pod.get("subpods", []):
            text = sub.get("plaintext", "").strip()
            if text:
                pods.append({"title": pod.get("title"), "text": text})

    return {
        "answer": short_answer or (pods[0]["text"] if pods else "No result"),
        "pods": pods,
        "query": query,
    }


# ─── Google Custom Search API ──────────────────────────────────────────────────

@register_node("tool.google_search")
async def tool_google_search(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Web search via Google Custom Search JSON API.
    Requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID.
    config: query, num (1–10), start (pagination offset)
    """
    api_key = getattr(settings, "GOOGLE_CSE_API_KEY", None)
    cse_id = getattr(settings, "GOOGLE_CSE_ID", None)
    if not api_key or not cse_id:
        raise ValueError("tool.google_search requires GOOGLE_CSE_API_KEY and GOOGLE_CSE_ID")

    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("tool.google_search requires 'query'")

    num = min(int(config.get("num", 5)), 10)
    start = int(config.get("start", 1))

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            "https://www.googleapis.com/customsearch/v1",
            params={"key": api_key, "cx": cse_id, "q": query, "num": num, "start": start},
        )
        r.raise_for_status()
        data = r.json()

    results = []
    for item in data.get("items", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("link"),
            "snippet": item.get("snippet"),
        })

    return {
        "results": results,
        "total": data.get("searchInformation", {}).get("totalResults"),
        "query": query,
    }


# ─── Serper (Google Search via Serper.dev) ─────────────────────────────────────

@register_node("tool.serper")
async def tool_serper(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Google Search results via Serper.dev (fast, cheap).
    Requires SERPER_API_KEY.
    config: query, num, gl (country), hl (language), type (search | news | images)
    """
    api_key = getattr(settings, "SERPER_API_KEY", None)
    if not api_key:
        raise ValueError("tool.serper requires SERPER_API_KEY")

    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("tool.serper requires 'query'")

    num = int(config.get("num", 10))
    search_type = config.get("type", "search")

    payload: dict = {"q": query, "num": num}
    if config.get("gl"):
        payload["gl"] = config["gl"]
    if config.get("hl"):
        payload["hl"] = config["hl"]

    url_map = {"search": "/search", "news": "/news", "images": "/images"}
    endpoint = f"https://google.serper.dev{url_map.get(search_type, '/search')}"

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            endpoint,
            json=payload,
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        )
        r.raise_for_status()
        data = r.json()

    organic = [
        {"title": i.get("title"), "url": i.get("link"), "snippet": i.get("snippet"), "position": i.get("position")}
        for i in data.get("organic", [])
    ]
    answer_box = data.get("answerBox", {})
    return {
        "results": organic,
        "answer": answer_box.get("answer") or answer_box.get("snippet"),
        "knowledge_graph": data.get("knowledgeGraph"),
        "query": query,
        "total": len(organic),
    }


# ─── SearXNG ──────────────────────────────────────────────────────────────────

@register_node("tool.searxng")
async def tool_searxng(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Web search via a self-hosted SearXNG instance (privacy-focused metasearch).
    config: base_url (required), query, num (default 5), categories, engines, language
    """
    base_url = config.get("base_url") or getattr(settings, "SEARXNG_BASE_URL", None)
    if not base_url:
        raise ValueError("tool.searxng requires 'base_url' or SEARXNG_BASE_URL")

    query = config.get("query") or input_data.get("query")
    if not query:
        raise ValueError("tool.searxng requires 'query'")

    params: dict = {"q": query, "format": "json"}
    if config.get("categories"):
        params["categories"] = config["categories"]
    if config.get("engines"):
        params["engines"] = config["engines"]
    if config.get("language"):
        params["language"] = config["language"]
    if config.get("safesearch") is not None:
        params["safesearch"] = config["safesearch"]

    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{base_url.rstrip('/')}/search",
            params=params,
            headers={"Accept": "application/json"},
        )
        r.raise_for_status()
        data = r.json()

    num = int(config.get("num", 5))
    results = [
        {"title": i.get("title"), "url": i.get("url"), "content": i.get("content"), "engine": i.get("engine")}
        for i in data.get("results", [])[:num]
    ]
    return {"results": results, "query": query, "total": len(results)}


# ─── HTTP Request (GET / POST / PUT / DELETE) ──────────────────────────────────

@register_node("tool.http_get")
async def tool_http_get(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Make an HTTP GET request.
    config: url, headers (dict), params (dict), timeout
    """
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("tool.http_get requires 'url'")
    headers = {**config.get("headers", {}), **input_data.get("headers", {})}
    params = {**config.get("params", {}), **input_data.get("params", {})}
    timeout = float(config.get("timeout", 30))

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url, headers=headers, params=params)

    try:
        body = r.json()
    except Exception:
        body = r.text

    return {"status_code": r.status_code, "body": body, "headers": dict(r.headers), "url": str(r.url)}


@register_node("tool.http_post")
async def tool_http_post(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Make an HTTP POST request.
    config: url, headers (dict), body (dict for JSON, str for raw), content_type, timeout
    """
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("tool.http_post requires 'url'")
    headers = {**config.get("headers", {}), **input_data.get("headers", {})}
    body = config.get("body") or input_data.get("body") or {}
    content_type = config.get("content_type", "application/json")
    timeout = float(config.get("timeout", 30))

    headers.setdefault("Content-Type", content_type)

    async with httpx.AsyncClient(timeout=timeout) as client:
        if isinstance(body, dict):
            r = await client.post(url, json=body, headers=headers)
        else:
            r = await client.post(url, content=str(body), headers=headers)

    try:
        resp_body = r.json()
    except Exception:
        resp_body = r.text

    return {"status_code": r.status_code, "body": resp_body, "headers": dict(r.headers)}


@register_node("tool.http_put")
async def tool_http_put(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Make an HTTP PUT request."""
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("tool.http_put requires 'url'")
    headers = {**config.get("headers", {}), **input_data.get("headers", {})}
    body = config.get("body") or input_data.get("body") or {}
    timeout = float(config.get("timeout", 30))

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.put(url, json=body if isinstance(body, dict) else None,
                             content=str(body) if not isinstance(body, dict) else None,
                             headers=headers)
    try:
        resp_body = r.json()
    except Exception:
        resp_body = r.text

    return {"status_code": r.status_code, "body": resp_body}


@register_node("tool.http_delete")
async def tool_http_delete(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Make an HTTP DELETE request."""
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("tool.http_delete requires 'url'")
    headers = {**config.get("headers", {}), **input_data.get("headers", {})}
    timeout = float(config.get("timeout", 30))

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.delete(url, headers=headers)

    try:
        resp_body = r.json()
    except Exception:
        resp_body = r.text

    return {"status_code": r.status_code, "body": resp_body}


# ─── JSON Path Extractor ───────────────────────────────────────────────────────

@register_node("tool.jsonpath")
async def tool_jsonpath(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Extract values from JSON using JSONPath expressions.
    config: path (JSONPath expression, e.g. $.store.book[*].title),
            data (dict/list, falls back to input_data)
    Supports basic JSONPath: $, ., [], *, [n], [-n], [start:end], ..
    """
    import re as _re

    path = config.get("path") or input_data.get("path", "$")
    data = config.get("data") or input_data.get("data") or input_data

    def _get(obj, parts):
        if not parts:
            return [obj]
        part = parts[0]
        rest = parts[1:]
        results = []

        if part == "$":
            return _get(obj, rest)
        elif part == "*":
            if isinstance(obj, dict):
                for v in obj.values():
                    results.extend(_get(v, rest))
            elif isinstance(obj, list):
                for v in obj:
                    results.extend(_get(v, rest))
        elif part == "..":
            results.extend(_get(obj, rest))
            if isinstance(obj, dict):
                for v in obj.values():
                    results.extend(_get(v, [".."] + rest))
            elif isinstance(obj, list):
                for v in obj:
                    results.extend(_get(v, [".."] + rest))
        elif isinstance(obj, dict) and part in obj:
            results.extend(_get(obj[part], rest))
        elif isinstance(obj, list):
            try:
                idx = int(part)
                results.extend(_get(obj[idx], rest))
            except (ValueError, IndexError):
                pass
        return results

    # Parse path segments
    path = path.lstrip("$").lstrip(".")
    segments = []
    for seg in _re.split(r"\.|(?=\[)", path):
        seg = seg.strip("[]'\"")
        if seg:
            segments.append(seg)

    full_path = ["$"] + segments if segments else ["$"]
    values = _get(data, full_path)

    return {
        "values": values,
        "value": values[0] if len(values) == 1 else values,
        "count": len(values),
        "path": config.get("path", "$"),
    }


# ─── Web Browser (HTML fetch + text extraction) ────────────────────────────────

@register_node("tool.web_browser")
async def tool_web_browser(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Fetch a URL and extract readable text from HTML.
    Requires beautifulsoup4 (pip install beautifulsoup4).
    config: url, selector (CSS selector, optional), max_length (default 5000)
    """
    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("tool.web_browser requires 'url'")

    selector = config.get("selector", "")
    max_length = int(config.get("max_length", 5000))

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        r = await client.get(url, headers={"User-Agent": "AutoFlow/1.0 WebBrowser"})
        r.raise_for_status()
        html = r.text

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        # Remove script/style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        if selector:
            elements = soup.select(selector)
            text = "\n\n".join(el.get_text(separator=" ", strip=True) for el in elements)
        else:
            text = soup.get_text(separator="\n", strip=True)

        # Collapse multiple blank lines
        import re as _re
        text = _re.sub(r"\n{3,}", "\n\n", text).strip()
    except ImportError:
        # Fallback: strip HTML tags with regex
        import re as _re
        text = _re.sub(r"<[^>]+>", " ", html)
        text = _re.sub(r"\s+", " ", text).strip()

    title = ""
    try:
        import re as _re
        m = _re.search(r"<title[^>]*>(.*?)</title>", html, _re.IGNORECASE | _re.DOTALL)
        if m:
            title = m.group(1).strip()
    except Exception:
        pass

    return {
        "url": url,
        "title": title,
        "text": text[:max_length],
        "full_length": len(text),
        "truncated": len(text) > max_length,
    }


# ─── OpenAPI Toolkit ──────────────────────────────────────────────────────────

@register_node("tool.openapi")
async def tool_openapi(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Execute an operation defined in an OpenAPI spec.
    config: spec_url (URL to OpenAPI JSON/YAML), operation_id, parameters (dict), auth_header
    input_data: overrides parameters
    """
    import yaml as _yaml

    spec_url = config.get("spec_url")
    if not spec_url:
        raise ValueError("tool.openapi requires 'spec_url'")

    operation_id = config.get("operation_id")
    if not operation_id:
        raise ValueError("tool.openapi requires 'operation_id'")

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(spec_url)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if "yaml" in content_type or spec_url.endswith(".yaml") or spec_url.endswith(".yml"):
            try:
                spec = _yaml.safe_load(r.text)
            except Exception:
                spec = r.json()
        else:
            spec = r.json()

    # Find the operation
    servers = spec.get("servers", [{"url": ""}])
    base_url = servers[0].get("url", "")

    target_path = None
    target_method = None
    target_op = None

    for path, methods in spec.get("paths", {}).items():
        for method, op in methods.items():
            if method.lower() == "parameters":
                continue
            if op.get("operationId") == operation_id:
                target_path = path
                target_method = method.upper()
                target_op = op
                break
        if target_path:
            break

    if not target_path:
        return {"error": f"Operation '{operation_id}' not found in spec", "operations": [
            op.get("operationId")
            for methods in spec.get("paths", {}).values()
            for op in methods.values()
            if isinstance(op, dict) and op.get("operationId")
        ]}

    params = {**config.get("parameters", {}), **input_data}
    headers = {}
    if config.get("auth_header"):
        key, _, value = config["auth_header"].partition(":")
        headers[key.strip()] = value.strip()

    # Substitute path params
    for param in target_op.get("parameters", []):
        if param.get("in") == "path":
            name = param["name"]
            if name in params:
                target_path = target_path.replace(f"{{{name}}}", str(params.pop(name)))

    url = f"{base_url}{target_path}"

    async with httpx.AsyncClient(timeout=30) as client:
        if target_method in ("GET", "DELETE"):
            r = await client.request(target_method, url, params=params, headers=headers)
        else:
            r = await client.request(target_method, url, json=params, headers=headers)

    try:
        body = r.json()
    except Exception:
        body = r.text

    return {"status_code": r.status_code, "body": body, "operation_id": operation_id}


# ─── tool.gmail ──────────────────────────────────────────────────────────────

@register_node("tool.gmail")
async def tool_gmail(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Gmail Tool: send, read, or list Gmail messages via Google OAuth2.

    config:
      - operation: send | list | get (default: send)
      - to: recipient email (for send)
      - subject: email subject (for send)
      - body: email body (for send)
      - message_id: Gmail message ID (for get)
      - max_results: max messages to list (default: 10)
    """
    import base64
    from core.config import settings

    client_id = getattr(settings, "GMAIL_CLIENT_ID", None)
    client_secret = getattr(settings, "GMAIL_CLIENT_SECRET", None)
    refresh_token = getattr(settings, "GMAIL_REFRESH_TOKEN", None)

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("tool.gmail requires GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN")

    # Exchange refresh token for access token
    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        operation = config.get("operation", input_data.get("operation", "send"))

        if operation == "send":
            to = config.get("to") or input_data.get("to", "")
            subject = config.get("subject") or input_data.get("subject", "")
            body = config.get("body") or input_data.get("body") or input_data.get("input", "")
            raw_message = f"To: {to}\r\nSubject: {subject}\r\n\r\n{body}"
            encoded = base64.urlsafe_b64encode(raw_message.encode()).decode()
            r = await client.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                json={"raw": encoded},
                headers=headers,
            )
            r.raise_for_status()
            return {"sent": True, "message_id": r.json().get("id"), "to": to, "subject": subject}

        elif operation == "list":
            max_results = int(config.get("max_results", 10))
            r = await client.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                params={"maxResults": max_results},
                headers=headers,
            )
            r.raise_for_status()
            messages = r.json().get("messages", [])
            return {"messages": messages, "count": len(messages)}

        elif operation == "get":
            msg_id = config.get("message_id") or input_data.get("message_id", "")
            r = await client.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
                headers=headers,
            )
            r.raise_for_status()
            return {"message": r.json()}

    return {"error": f"Unknown operation: {operation}"}


# ─── tool.google_calendar ────────────────────────────────────────────────────

@register_node("tool.google_calendar")
async def tool_google_calendar(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Google Calendar Tool: list or create calendar events.

    config:
      - operation: list | create (default: list)
      - calendar_id: calendar ID (default: primary)
      - summary: event title (for create)
      - start: ISO datetime (for create)
      - end: ISO datetime (for create)
      - max_results: for list (default: 10)
    """
    from core.config import settings

    client_id = getattr(settings, "GMAIL_CLIENT_ID", None)
    client_secret = getattr(settings, "GMAIL_CLIENT_SECRET", None)
    refresh_token = getattr(settings, "GMAIL_REFRESH_TOKEN", None)

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("tool.google_calendar requires GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN")

    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        operation = config.get("operation", input_data.get("operation", "list"))
        calendar_id = config.get("calendar_id", "primary")

        if operation == "list":
            max_results = int(config.get("max_results", 10))
            r = await client.get(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
                params={"maxResults": max_results, "orderBy": "startTime", "singleEvents": "true"},
                headers=headers,
            )
            r.raise_for_status()
            events = r.json().get("items", [])
            return {"events": events, "count": len(events)}

        elif operation == "create":
            summary = config.get("summary") or input_data.get("summary", "New Event")
            start = config.get("start") or input_data.get("start", "")
            end = config.get("end") or input_data.get("end", "")
            event_body = {
                "summary": summary,
                "start": {"dateTime": start, "timeZone": "UTC"},
                "end": {"dateTime": end, "timeZone": "UTC"},
            }
            r = await client.post(
                f"https://www.googleapis.com/calendar/v3/calendars/{calendar_id}/events",
                json=event_body,
                headers=headers,
            )
            r.raise_for_status()
            return {"event": r.json(), "created": True}

    return {"error": f"Unknown operation: {operation}"}


# ─── tool.google_docs ────────────────────────────────────────────────────────

@register_node("tool.google_docs")
async def tool_google_docs(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Google Docs Tool: read or append to a Google Doc.

    config:
      - operation: get | append (default: get)
      - document_id: the Google Docs document ID
      - text: text to append (for append)
    """
    from core.config import settings

    client_id = getattr(settings, "GMAIL_CLIENT_ID", None)
    client_secret = getattr(settings, "GMAIL_CLIENT_SECRET", None)
    refresh_token = getattr(settings, "GMAIL_REFRESH_TOKEN", None)

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("tool.google_docs requires Google OAuth credentials")

    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        document_id = config.get("document_id") or input_data.get("document_id", "")
        operation = config.get("operation", "get")

        if operation == "get":
            r = await client.get(
                f"https://docs.googleapis.com/v1/documents/{document_id}",
                headers=headers,
            )
            r.raise_for_status()
            doc = r.json()
            # Extract plain text from doc body
            content_parts = []
            for elem in doc.get("body", {}).get("content", []):
                para = elem.get("paragraph", {})
                for pe in para.get("elements", []):
                    text_run = pe.get("textRun", {})
                    content_parts.append(text_run.get("content", ""))
            return {"document_id": document_id, "title": doc.get("title"), "text": "".join(content_parts), "raw": doc}

        elif operation == "append":
            text = config.get("text") or input_data.get("text") or input_data.get("input", "")
            requests_body = [{"insertText": {"location": {"index": 1}, "text": text}}]
            r = await client.post(
                f"https://docs.googleapis.com/v1/documents/{document_id}:batchUpdate",
                json={"requests": requests_body},
                headers=headers,
            )
            r.raise_for_status()
            return {"appended": True, "document_id": document_id, "text_length": len(text)}

    return {"error": f"Unknown operation: {operation}"}


# ─── tool.google_drive_tool ──────────────────────────────────────────────────

@register_node("tool.google_drive_tool")
async def tool_google_drive(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Google Drive Tool: list, search, or download files.

    config:
      - operation: list | search | download (default: list)
      - query: search query (for search)
      - file_id: file ID (for download)
      - max_results: max files (default: 10)
    """
    from core.config import settings

    client_id = getattr(settings, "GMAIL_CLIENT_ID", None)
    client_secret = getattr(settings, "GMAIL_CLIENT_SECRET", None)
    refresh_token = getattr(settings, "GMAIL_REFRESH_TOKEN", None)

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("tool.google_drive_tool requires Google OAuth credentials")

    async with httpx.AsyncClient(timeout=60) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        operation = config.get("operation", "list")

        if operation in ("list", "search"):
            max_results = int(config.get("max_results", 10))
            params: dict = {"pageSize": max_results, "fields": "files(id,name,mimeType,size,modifiedTime)"}
            if operation == "search":
                q = config.get("query") or input_data.get("query", "")
                params["q"] = q
            r = await client.get(
                "https://www.googleapis.com/drive/v3/files",
                params=params,
                headers=headers,
            )
            r.raise_for_status()
            files = r.json().get("files", [])
            return {"files": files, "count": len(files)}

        elif operation == "download":
            file_id = config.get("file_id") or input_data.get("file_id", "")
            r = await client.get(
                f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media",
                headers=headers,
            )
            r.raise_for_status()
            return {"file_id": file_id, "content": r.text, "size": len(r.content)}

    return {"error": f"Unknown operation: {operation}"}


# ─── tool.google_sheets_tool ─────────────────────────────────────────────────

@register_node("tool.google_sheets_tool")
async def tool_google_sheets(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Google Sheets Tool: read or append rows.

    config:
      - operation: get | append (default: get)
      - spreadsheet_id: Google Sheets spreadsheet ID
      - range: A1 notation (e.g. "Sheet1!A1:D10")
      - values: list of rows to append (for append)
    """
    from core.config import settings

    client_id = getattr(settings, "GMAIL_CLIENT_ID", None)
    client_secret = getattr(settings, "GMAIL_CLIENT_SECRET", None)
    refresh_token = getattr(settings, "GMAIL_REFRESH_TOKEN", None)

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("tool.google_sheets_tool requires Google OAuth credentials")

    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        spreadsheet_id = config.get("spreadsheet_id") or input_data.get("spreadsheet_id", "")
        range_ = config.get("range", "Sheet1!A1:Z1000")
        operation = config.get("operation", "get")

        if operation == "get":
            r = await client.get(
                f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_}",
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
            return {"values": data.get("values", []), "range": data.get("range"), "spreadsheet_id": spreadsheet_id}

        elif operation == "append":
            values = config.get("values") or input_data.get("values", [])
            if not isinstance(values, list):
                values = [[str(values)]]
            r = await client.post(
                f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{range_}:append",
                params={"valueInputOption": "USER_ENTERED"},
                json={"values": values},
                headers=headers,
            )
            r.raise_for_status()
            return {"appended": True, "updates": r.json().get("updates", {})}

    return {"error": f"Unknown operation: {operation}"}


# ─── tool.microsoft_outlook ──────────────────────────────────────────────────

@register_node("tool.microsoft_outlook")
async def tool_microsoft_outlook(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Microsoft Outlook Tool: send or list emails via Microsoft Graph API.

    config:
      - operation: send | list | get (default: list)
      - to: recipient (for send)
      - subject: subject (for send)
      - body: email body (for send)
      - message_id: message ID (for get)
      - max_results: for list (default: 10)
    """
    from core.config import settings

    client_id = getattr(settings, "MICROSOFT_CLIENT_ID", None)
    client_secret = getattr(settings, "MICROSOFT_CLIENT_SECRET", None)
    refresh_token = getattr(settings, "MICROSOFT_REFRESH_TOKEN", None)

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("tool.microsoft_outlook requires MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_REFRESH_TOKEN")

    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": "https://graph.microsoft.com/Mail.ReadWrite https://graph.microsoft.com/Mail.Send",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        operation = config.get("operation", "list")

        if operation == "send":
            to = config.get("to") or input_data.get("to", "")
            subject = config.get("subject") or input_data.get("subject", "")
            body = config.get("body") or input_data.get("body") or input_data.get("input", "")
            message = {
                "message": {
                    "subject": subject,
                    "body": {"contentType": "Text", "content": body},
                    "toRecipients": [{"emailAddress": {"address": to}}],
                }
            }
            r = await client.post("https://graph.microsoft.com/v1.0/me/sendMail", json=message, headers=headers)
            r.raise_for_status()
            return {"sent": True, "to": to, "subject": subject}

        elif operation == "list":
            max_results = int(config.get("max_results", 10))
            r = await client.get(
                f"https://graph.microsoft.com/v1.0/me/messages?$top={max_results}",
                headers=headers,
            )
            r.raise_for_status()
            messages = r.json().get("value", [])
            return {"messages": messages, "count": len(messages)}

        elif operation == "get":
            msg_id = config.get("message_id") or input_data.get("message_id", "")
            r = await client.get(f"https://graph.microsoft.com/v1.0/me/messages/{msg_id}", headers=headers)
            r.raise_for_status()
            return {"message": r.json()}

    return {"error": f"Unknown operation: {operation}"}


# ─── tool.microsoft_teams ────────────────────────────────────────────────────

@register_node("tool.microsoft_teams")
async def tool_microsoft_teams(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Microsoft Teams Tool: send messages to a Teams channel or chat.

    config:
      - operation: send_message | list_channels (default: send_message)
      - team_id: Teams team ID
      - channel_id: channel ID (for send_message)
      - message: message to send
    """
    from core.config import settings

    client_id = getattr(settings, "MICROSOFT_CLIENT_ID", None)
    client_secret = getattr(settings, "MICROSOFT_CLIENT_SECRET", None)
    refresh_token = getattr(settings, "MICROSOFT_REFRESH_TOKEN", None)

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError("tool.microsoft_teams requires MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, MICROSOFT_REFRESH_TOKEN")

    async with httpx.AsyncClient(timeout=30) as client:
        token_resp = await client.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": "https://graph.microsoft.com/ChannelMessage.Send https://graph.microsoft.com/Channel.ReadBasic.All",
            },
        )
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        operation = config.get("operation", "send_message")
        team_id = config.get("team_id") or input_data.get("team_id", "")

        if operation == "send_message":
            channel_id = config.get("channel_id") or input_data.get("channel_id", "")
            message = config.get("message") or input_data.get("message") or input_data.get("input", "")
            r = await client.post(
                f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels/{channel_id}/messages",
                json={"body": {"content": message}},
                headers=headers,
            )
            r.raise_for_status()
            return {"sent": True, "message_id": r.json().get("id"), "channel_id": channel_id}

        elif operation == "list_channels":
            r = await client.get(
                f"https://graph.microsoft.com/v1.0/teams/{team_id}/channels",
                headers=headers,
            )
            r.raise_for_status()
            channels = r.json().get("value", [])
            return {"channels": channels, "count": len(channels)}

    return {"error": f"Unknown operation: {operation}"}


# ─── tool.composio ───────────────────────────────────────────────────────────

@register_node("tool.composio")
async def tool_composio(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Composio Tool: execute any action on Composio's integration platform.

    config:
      - action: action slug (e.g. GITHUB_CREATE_ISSUE)
      - entity_id: Composio entity ID (default: default)
      - parameters: dict of action parameters
    """
    from core.config import settings

    api_key = getattr(settings, "COMPOSIO_API_KEY", None)
    if not api_key:
        raise ValueError("tool.composio requires COMPOSIO_API_KEY")

    action = config.get("action") or input_data.get("action", "")
    if not action:
        raise ValueError("tool.composio requires 'action'")

    entity_id = config.get("entity_id", "default")
    parameters = {**config.get("parameters", {}), **{k: v for k, v in input_data.items() if k not in ("action", "entity_id")}}

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"https://backend.composio.dev/api/v2/actions/{action}/execute",
            json={"entityId": entity_id, "input": parameters},
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
        )
        r.raise_for_status()
        result = r.json()

    return {
        "action": action,
        "entity_id": entity_id,
        "result": result.get("response", result),
        "success": result.get("successfull", True),
    }


# ─── tool.jira_tool ──────────────────────────────────────────────────────────

@register_node("tool.jira_tool")
async def tool_jira(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Jira Tool: create, get, or search Jira issues.

    config:
      - operation: create | get | search | comment (default: search)
      - host: Jira Cloud base URL (e.g. https://yourorg.atlassian.net)
      - username: Jira email
      - api_token: Jira API token
      - project_key: project key (for create)
      - summary: issue title (for create)
      - description: issue body (for create)
      - issue_key: e.g. PROJ-123 (for get/comment)
      - jql: JQL query (for search)
      - comment: comment text (for comment)
    """
    import base64

    host = config.get("host") or ""
    username = config.get("username") or ""
    api_token = config.get("api_token") or ""

    if not all([host, username, api_token]):
        raise ValueError("tool.jira_tool requires host, username, api_token in config")

    credentials = base64.b64encode(f"{username}:{api_token}".encode()).decode()
    headers = {"Authorization": f"Basic {credentials}", "Content-Type": "application/json"}
    operation = config.get("operation", "search")

    async with httpx.AsyncClient(timeout=30) as client:
        if operation == "create":
            project_key = config.get("project_key") or input_data.get("project_key", "")
            summary = config.get("summary") or input_data.get("summary") or input_data.get("input", "New Issue")
            description = config.get("description") or input_data.get("description", "")
            issue_type = config.get("issue_type", "Task")
            r = await client.post(
                f"{host}/rest/api/3/issue",
                json={
                    "fields": {
                        "project": {"key": project_key},
                        "summary": summary,
                        "description": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}]},
                        "issuetype": {"name": issue_type},
                    }
                },
                headers=headers,
            )
            r.raise_for_status()
            return {"created": True, "issue": r.json()}

        elif operation == "get":
            issue_key = config.get("issue_key") or input_data.get("issue_key", "")
            r = await client.get(f"{host}/rest/api/3/issue/{issue_key}", headers=headers)
            r.raise_for_status()
            return {"issue": r.json()}

        elif operation == "search":
            jql = config.get("jql") or input_data.get("jql") or input_data.get("query", "")
            max_results = int(config.get("max_results", 20))
            r = await client.get(
                f"{host}/rest/api/3/search",
                params={"jql": jql, "maxResults": max_results},
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
            return {"issues": data.get("issues", []), "total": data.get("total", 0)}

        elif operation == "comment":
            issue_key = config.get("issue_key") or input_data.get("issue_key", "")
            comment = config.get("comment") or input_data.get("comment") or input_data.get("input", "")
            r = await client.post(
                f"{host}/rest/api/3/issue/{issue_key}/comment",
                json={"body": {"type": "doc", "version": 1, "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}]}},
                headers=headers,
            )
            r.raise_for_status()
            return {"commented": True, "comment": r.json()}

    return {"error": f"Unknown operation: {operation}"}


# ─── tool.mcp_tool ───────────────────────────────────────────────────────────

@register_node("tool.mcp_tool")
async def tool_mcp(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    MCP Tool: call a tool on an MCP (Model Context Protocol) server.

    config:
      - server_url: MCP server base URL
      - tool_name: name of the tool to call
      - arguments: dict of arguments to pass
    """
    server_url = config.get("server_url") or ""
    tool_name = config.get("tool_name") or input_data.get("tool_name", "")

    if not server_url:
        raise ValueError("tool.mcp_tool requires 'server_url'")
    if not tool_name:
        raise ValueError("tool.mcp_tool requires 'tool_name'")

    arguments = {**config.get("arguments", {}), **{k: v for k, v in input_data.items() if k not in ("tool_name", "server_url")}}

    async with httpx.AsyncClient(timeout=60) as client:
        # MCP JSON-RPC 2.0 protocol
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        r = await client.post(f"{server_url}", json=payload, headers={"Content-Type": "application/json"})
        r.raise_for_status()
        result = r.json()

    if "error" in result:
        raise RuntimeError(f"MCP error: {result['error']}")

    content = result.get("result", {}).get("content", [])
    text_parts = [c.get("text", "") for c in content if c.get("type") == "text"]
    return {
        "tool_name": tool_name,
        "result": "\n".join(text_parts) if text_parts else result.get("result"),
        "raw": result,
    }


# ─── tool.stripe_tool ────────────────────────────────────────────────────────

@register_node("tool.stripe_tool")
async def tool_stripe(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Stripe Tool: perform Stripe API operations.

    config:
      - operation: create_customer | list_customers | create_payment_intent | retrieve_balance (default: retrieve_balance)
      - stripe_secret_key: Stripe secret key (or set STRIPE_SECRET_KEY env var)
      - amount: amount in cents (for create_payment_intent)
      - currency: currency code (default: usd)
      - customer_email: email (for create_customer)
      - customer_name: name (for create_customer)
    """
    import os
    api_key = config.get("stripe_secret_key") or os.getenv("STRIPE_SECRET_KEY", "")
    if not api_key:
        raise ValueError("tool.stripe_tool requires stripe_secret_key or STRIPE_SECRET_KEY env var")

    headers = {"Authorization": f"Bearer {api_key}"}
    operation = config.get("operation", input_data.get("operation", "retrieve_balance"))

    async with httpx.AsyncClient(timeout=30) as client:
        if operation == "retrieve_balance":
            r = await client.get("https://api.stripe.com/v1/balance", headers=headers)
            r.raise_for_status()
            return {"balance": r.json()}

        elif operation == "list_customers":
            limit = int(config.get("limit", 10))
            r = await client.get(f"https://api.stripe.com/v1/customers?limit={limit}", headers=headers)
            r.raise_for_status()
            data = r.json()
            return {"customers": data.get("data", []), "count": len(data.get("data", []))}

        elif operation == "create_customer":
            email = config.get("customer_email") or input_data.get("customer_email", "")
            name = config.get("customer_name") or input_data.get("customer_name", "")
            r = await client.post(
                "https://api.stripe.com/v1/customers",
                data={"email": email, "name": name},
                headers=headers,
            )
            r.raise_for_status()
            return {"customer": r.json(), "created": True}

        elif operation == "create_payment_intent":
            amount = int(config.get("amount") or input_data.get("amount", 0))
            currency = config.get("currency", "usd")
            r = await client.post(
                "https://api.stripe.com/v1/payment_intents",
                data={"amount": str(amount), "currency": currency},
                headers=headers,
            )
            r.raise_for_status()
            return {"payment_intent": r.json(), "created": True}

    return {"error": f"Unknown operation: {operation}"}


# ─── tool.searchapi_tool ─────────────────────────────────────────────────────

@register_node("tool.searchapi_tool")
async def tool_searchapi(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    SearchAPI Tool: perform searches using SearchAPI.io.

    config:
      - engine: google | google_news | youtube | bing (default: google)
      - query: search query
      - num_results: results to return (default: 10)
    """
    from core.config import settings

    api_key = getattr(settings, "SEARCHAPI_API_KEY", None)
    if not api_key:
        raise ValueError("tool.searchapi_tool requires SEARCHAPI_API_KEY")

    query = config.get("query") or input_data.get("query") or input_data.get("input", "")
    if not query:
        raise ValueError("tool.searchapi_tool requires 'query'")

    engine = config.get("engine", "google")
    num_results = int(config.get("num_results", 10))

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            "https://www.searchapi.io/api/v1/search",
            params={"engine": engine, "q": query, "num": num_results, "api_key": api_key},
        )
        r.raise_for_status()
        data = r.json()

    results = data.get("organic_results", data.get("results", []))
    return {
        "results": results,
        "count": len(results),
        "query": query,
        "engine": engine,
    }


# ─── tool.web_scraper ────────────────────────────────────────────────────────

@register_node("tool.web_scraper")
async def tool_web_scraper(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Web Scraper Tool: scrape a URL and return text content.

    config:
      - url: the URL to scrape
      - selector: CSS selector to extract (optional)
      - javascript: bool — render JS before scraping (default: false)
      - timeout: request timeout in seconds (default: 30)
    """
    url = config.get("url") or input_data.get("url") or input_data.get("input", "")
    if not url:
        raise ValueError("tool.web_scraper requires 'url'")

    timeout = int(config.get("timeout", 30))
    use_js = bool(config.get("javascript", False))

    if use_js:
        try:
            from playwright.async_api import async_playwright  # type: ignore
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, timeout=timeout * 1000)
                await page.wait_for_load_state("networkidle")
                html = await page.content()
                await browser.close()
        except ImportError:
            log.warning("playwright_not_installed_fallback_httpx")
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                html = r.text
    else:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            html = r.text

    # Extract text: try BeautifulSoup, fall back to regex
    try:
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
    except ImportError:
        import re as _re
        text = _re.sub(r"<[^>]+>", " ", html)
        text = _re.sub(r"\s+", " ", text).strip()

    return {"url": url, "text": text, "length": len(text)}


# ─── tool.agent_as_tool ──────────────────────────────────────────────────────

@register_node("tool.agent_as_tool")
async def tool_agent_as_tool(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Agent-as-Tool: wraps another agent node as a callable tool.
    Dispatches to the specified agent node and returns its output.

    config:
      - agent_node_id: node type ID of the agent to call
      - agent_config: optional config override for the agent
      - description: tool description (informational)
    """
    from core.execution_engine import NODE_HANDLERS

    agent_node_id = config.get("agent_node_id") or config.get("node_id", "")
    if not agent_node_id:
        raise ValueError("tool.agent_as_tool requires 'agent_node_id'")

    handler = NODE_HANDLERS.get(agent_node_id)
    if not handler:
        raise ValueError(f"tool.agent_as_tool: unknown agent node '{agent_node_id}'")

    agent_config = {**config.get("agent_config", {}), **config}
    agent_config.pop("agent_node_id", None)
    agent_config.pop("agent_config", None)

    result = await handler(agent_config, input_data, credential_id, db)
    return {"agent_node_id": agent_node_id, "result": result, **result}


# ─── tool.chain_tool ─────────────────────────────────────────────────────────

@register_node("tool.chain_tool")
async def tool_chain_tool(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chain-as-Tool: wraps a chain node as a callable tool.
    Useful for making a chain (e.g. QA chain) available as a tool to agents.

    config:
      - chain_node_id: node type ID of the chain to call
      - chain_config: optional config override for the chain
    """
    from core.execution_engine import NODE_HANDLERS

    chain_node_id = config.get("chain_node_id") or config.get("node_id", "")
    if not chain_node_id:
        raise ValueError("tool.chain_tool requires 'chain_node_id'")

    handler = NODE_HANDLERS.get(chain_node_id)
    if not handler:
        raise ValueError(f"tool.chain_tool: unknown chain node '{chain_node_id}'")

    chain_config = {**config.get("chain_config", {}), **config}
    chain_config.pop("chain_node_id", None)
    chain_config.pop("chain_config", None)

    result = await handler(chain_config, input_data, credential_id, db)
    return {"chain_node_id": chain_node_id, "result": result, **result}


# ─── tool.chatflow_tool ──────────────────────────────────────────────────────

@register_node("tool.chatflow_tool")
async def tool_chatflow_tool(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Chatflow-as-Tool: invoke a saved chatflow (workflow) as an agent tool.
    Uses the internal workflow execution engine.

    config:
      - workflow_id: ID of the workflow to execute
      - input_key: key to pass as workflow input (default: input)
    """
    from core.execution_engine import NODE_HANDLERS

    workflow_id = config.get("workflow_id") or input_data.get("workflow_id", "")
    if not workflow_id:
        raise ValueError("tool.chatflow_tool requires 'workflow_id'")

    input_key = config.get("input_key", "input")
    flow_input = {input_key: input_data.get("input", input_data.get("query", ""))}

    # Try to dispatch through execute_flow handler
    execute_handler = NODE_HANDLERS.get("agentflow.execute_flow") or NODE_HANDLERS.get("seqagent.execute_flow")
    if execute_handler:
        result = await execute_handler({"workflow_id": workflow_id}, flow_input, credential_id, db)
    else:
        result = {"workflow_id": workflow_id, "input": flow_input, "note": "No execute_flow handler found"}

    return {"workflow_id": workflow_id, "result": result, **result}


# ─── tool.custom_tool ────────────────────────────────────────────────────────

@register_node("tool.custom_tool")
async def tool_custom_tool(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Custom Tool: execute user-defined Python code as a tool.
    Identical to utility.custom_function but registers as a tool.

    config:
      - code: Python code with a function named 'execute'
      - function_name: name of function to call (default: execute)
      - name: tool name (informational)
      - description: tool description (informational)
      - timeout: max execution seconds (default: 10)
    """
    import asyncio
    import concurrent.futures
    import json as _json
    import math as _math
    import re as _re

    code = config.get("code", "")
    function_name = config.get("function_name", "execute")
    timeout = float(config.get("timeout", 10))

    if not code:
        return input_data

    safe_globals = {
        "__builtins__": {
            "print": print, "len": len, "str": str, "int": int, "float": float, "bool": bool,
            "list": list, "dict": dict, "tuple": tuple, "set": set,
            "range": range, "enumerate": enumerate, "zip": zip,
            "map": map, "filter": filter,
            "sorted": sorted, "reversed": reversed,
            "min": min, "max": max, "sum": sum, "abs": abs, "round": round,
            "any": any, "all": all, "isinstance": isinstance,
            "ValueError": ValueError, "TypeError": TypeError,
            "True": True, "False": False, "None": None,
        },
        "json": _json, "re": _re, "math": _math,
    }

    def _run():
        local_ns: dict = {}
        exec(code, safe_globals, local_ns)  # noqa: S102
        fn = local_ns.get(function_name)
        if fn is None:
            raise ValueError(f"Function '{function_name}' not found")
        result = fn(dict(input_data))
        return result if isinstance(result, dict) else {"result": result}

    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        result = await asyncio.wait_for(loop.run_in_executor(pool, _run), timeout=timeout)
    return {**input_data, **result}


# ─── tool.query_engine_tool ──────────────────────────────────────────────────

@register_node("tool.query_engine_tool")
async def tool_query_engine_tool(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Query Engine Tool: wraps a query engine node as an agent tool.
    Dispatches a query through the engine.query_engine node.

    config:
      - query_engine_config: config for the query engine (collection, provider, model, etc.)
      - name: tool name (informational)
      - description: tool description (informational)
    """
    from core.execution_engine import NODE_HANDLERS

    handler = NODE_HANDLERS.get("engine.query_engine")
    if not handler:
        raise ValueError("tool.query_engine_tool: engine.query_engine handler not registered")

    qe_config = {**config.get("query_engine_config", {}), **config}
    qe_config.pop("query_engine_config", None)

    query = input_data.get("input") or input_data.get("query", "")
    qe_input = {**input_data, "query": query}
    result = await handler(qe_config, qe_input, credential_id, db)
    return {"result": result, **result}


# ─── tool.retriever_tool ─────────────────────────────────────────────────────

@register_node("tool.retriever_tool")
async def tool_retriever_tool(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Retriever Tool: wraps a retriever node as an agent tool.

    config:
      - retriever_node_id: node type ID of the retriever (default: retriever.vector_store)
      - retriever_config: config for the retriever
      - name: tool name (informational)
    """
    from core.execution_engine import NODE_HANDLERS

    retriever_node_id = config.get("retriever_node_id", "retriever.vector_store")
    handler = NODE_HANDLERS.get(retriever_node_id)
    if not handler:
        raise ValueError(f"tool.retriever_tool: unknown retriever '{retriever_node_id}'")

    retriever_config = {**config.get("retriever_config", {}), **config}
    retriever_config.pop("retriever_config", None)
    retriever_config.pop("retriever_node_id", None)

    result = await handler(retriever_config, input_data, credential_id, db)
    return {"retriever_node_id": retriever_node_id, "result": result, **result}
