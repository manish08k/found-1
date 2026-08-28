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
