"""
Chain nodes — LangChain-style composable pipelines.

Nodes:
  chain.llm                         — prompt template + LLM call
  chain.conversation                — LLM + rolling in-memory message history
  chain.retrieval_qa                — vector search → LLM answer (RAG)
  chain.conversational_retrieval_qa — vector search + memory → LLM answer
  chain.api                         — LLM generates + executes HTTP request
  chain.multi_prompt                — router that picks from N prompts/LLMs
  chain.graph_cypher_qa             — Neo4j Cypher generation + execution + answer
  chain.vector_db_qa                — alias for retrieval_qa with configurable k
  chain.sql_db                      — NL→SQL→DB→LLM answer (async compat)
  chain.summarization               — map-reduce summarization over documents
"""
import json
import re
from collections import defaultdict
from typing import Any

import httpx
import structlog

from core.config import settings
from core.execution_engine import register_node

log = structlog.get_logger(__name__)

# ─── in-process conversation store (keyed by session_id) ─────────────────────
_CONV_STORE: dict[str, list[dict]] = defaultdict(list)


def _render(template: str, data: dict) -> str:
    """Render {{variable}} placeholders from input_data."""
    if not isinstance(template, str):
        return str(template) if template is not None else ""

    def repl(m):
        path = m.group(1).strip().split(".")
        val: Any = data
        for p in path:
            val = val.get(p) if isinstance(val, dict) else None
        if val is None:
            return ""
        return val if isinstance(val, str) else json.dumps(val)

    return re.sub(r"\{\{\s*([\w\.]+)\s*\}\}", repl, template)


async def _llm_call(
    provider: str,
    model: str,
    messages: list[dict],
    temperature: float = 0.7,
    max_tokens: int = 1024,
) -> str:
    """Minimal provider-agnostic LLM call returning assistant text."""
    provider = (provider or "openai").lower()

    if provider == "openai":
        api_key = settings.OPENAI_API_KEY
        if not api_key:
            raise ValueError("chain.* requires OPENAI_API_KEY")
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    if provider == "anthropic":
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("chain.* requires ANTHROPIC_API_KEY")
        sys_msgs = [m["content"] for m in messages if m["role"] == "system"]
        user_msgs = [m for m in messages if m["role"] != "system"]
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                json={"model": model, "max_tokens": max_tokens,
                      "system": " ".join(sys_msgs) if sys_msgs else "You are a helpful assistant.",
                      "messages": user_msgs},
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"]

    if provider in ("gemini", "google"):
        api_key = settings.GOOGLE_API_KEY
        if not api_key:
            raise ValueError("chain.* requires GOOGLE_API_KEY")
        parts = [{"text": m["content"]} for m in messages]
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": api_key},
                json={"contents": [{"role": "user", "parts": parts}],
                      "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}},
            )
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]

    if provider == "groq":
        api_key = settings.GROQ_API_KEY
        if not api_key:
            raise ValueError("chain.* requires GROQ_API_KEY")
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": messages,
                      "temperature": temperature, "max_tokens": max_tokens},
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]

    if provider == "ollama":
        base = settings.OLLAMA_BASE_URL or "http://localhost:11434"
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                f"{base}/api/chat",
                json={"model": model, "messages": messages, "stream": False,
                      "options": {"temperature": temperature, "num_predict": max_tokens}},
            )
            r.raise_for_status()
            return r.json()["message"]["content"]

    raise ValueError(f"Unsupported provider for chain nodes: {provider}")


async def _embed_text(text: str) -> list[float]:
    """Embed a single text string via OpenAI embeddings."""
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("Embedding requires OPENAI_API_KEY")
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "text-embedding-3-small", "input": text},
        )
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]


async def _vector_search(query: str, collection: str, top_k: int, db) -> list[dict]:
    """Search the local pgvector store — mirrors integrations/vector/handler.py logic."""
    import numpy as np
    from sqlalchemy import text

    vec = await _embed_text(query)
    vec_str = "[" + ",".join(str(v) for v in vec) + "]"
    sql = text("""
        SELECT id, content, metadata, 1 - (embedding <=> :vec::vector) AS score
        FROM vector_documents
        WHERE collection_name = :coll
        ORDER BY embedding <=> :vec::vector
        LIMIT :k
    """)
    result = await db.execute(sql, {"vec": vec_str, "coll": collection, "k": top_k})
    rows = result.fetchall()
    return [{"id": str(r[0]), "content": r[1], "metadata": r[2] or {}, "score": float(r[3])} for r in rows]


# ─── chain.llm ───────────────────────────────────────────────────────────────

@register_node("chain.llm")
async def chain_llm(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Prompt template + LLM call.
    config: provider, model, system_prompt, prompt, temperature, max_tokens
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    temperature = float(config.get("temperature", 0.7))
    max_tokens = int(config.get("max_tokens", 1024))
    system_prompt = _render(config.get("system_prompt", "You are a helpful assistant."), input_data)
    prompt = _render(config.get("prompt", "{{input}}"), input_data)

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
    text = await _llm_call(provider, model, messages, temperature, max_tokens)
    return {"text": text, "prompt": prompt}


# ─── chain.conversation ──────────────────────────────────────────────────────

@register_node("chain.conversation")
async def chain_conversation(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    LLM with in-process rolling message history keyed by session_id.
    config: provider, model, system_prompt, max_history (pairs), temperature, max_tokens
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    temperature = float(config.get("temperature", 0.7))
    max_tokens = int(config.get("max_tokens", 1024))
    system_prompt = _render(config.get("system_prompt", "You are a helpful assistant."), input_data)
    max_history = int(config.get("max_history", 10))  # pairs
    session_id = input_data.get("session_id", "default")
    user_input = _render(config.get("input", "{{input}}"), input_data)

    history = _CONV_STORE[session_id]
    history.append({"role": "user", "content": user_input})
    # trim to max_history pairs (user+assistant = 2 messages)
    if len(history) > max_history * 2:
        history[:] = history[-(max_history * 2):]

    messages = [{"role": "system", "content": system_prompt}] + list(history)
    reply = await _llm_call(provider, model, messages, temperature, max_tokens)
    history.append({"role": "assistant", "content": reply})

    return {"text": reply, "session_id": session_id, "history_length": len(history)}


# ─── chain.retrieval_qa ──────────────────────────────────────────────────────

@register_node("chain.retrieval_qa")
async def chain_retrieval_qa(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Retrieval-augmented QA: vector search → stuff into prompt → LLM answer.
    config: provider, model, collection, top_k, qa_prompt, system_prompt, temperature, max_tokens
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    temperature = float(config.get("temperature", 0.3))
    max_tokens = int(config.get("max_tokens", 1024))
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 4))
    question = _render(config.get("question", "{{input}}"), input_data)
    qa_prompt = config.get(
        "qa_prompt",
        "Use the following context to answer the question.\n\nContext:\n{context}\n\nQuestion: {question}\n\nAnswer:"
    )
    system_prompt = _render(config.get("system_prompt", "You are a helpful assistant."), input_data)

    docs = await _vector_search(question, collection, top_k, db)
    context = "\n\n".join(d["content"] for d in docs)
    prompt = qa_prompt.replace("{context}", context).replace("{question}", question)

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
    answer = await _llm_call(provider, model, messages, temperature, max_tokens)
    return {"text": answer, "source_documents": docs, "question": question}


# ─── chain.conversational_retrieval_qa ───────────────────────────────────────

@register_node("chain.conversational_retrieval_qa")
async def chain_conversational_retrieval_qa(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Conversational RAG: condense follow-up question → retrieve → answer.
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    temperature = float(config.get("temperature", 0.3))
    max_tokens = int(config.get("max_tokens", 1024))
    collection = config.get("collection", "default")
    top_k = int(config.get("top_k", 4))
    session_id = input_data.get("session_id", "default")
    user_input = _render(config.get("input", "{{input}}"), input_data)
    system_prompt = _render(config.get("system_prompt", "You are a helpful assistant."), input_data)

    history = _CONV_STORE[session_id]

    # Step 1: condense question with history if there's prior context
    if history:
        hist_text = "\n".join(f"{m['role'].capitalize()}: {m['content']}" for m in history[-6:])
        condense_prompt = (
            f"Given the following conversation and a follow-up question, "
            f"rewrite the follow-up question to be a standalone question.\n\n"
            f"Chat History:\n{hist_text}\n\nFollow-Up: {user_input}\n\nStandalone question:"
        )
        condense_msgs = [{"role": "user", "content": condense_prompt}]
        standalone = await _llm_call(provider, model, condense_msgs, 0.0, 256)
    else:
        standalone = user_input

    # Step 2: retrieve
    docs = await _vector_search(standalone, collection, top_k, db)
    context = "\n\n".join(d["content"] for d in docs)

    # Step 3: answer
    qa_prompt = (
        f"Use the context below to answer the question. "
        f"If you don't know the answer from the context, say so.\n\n"
        f"Context:\n{context}\n\nQuestion: {user_input}"
    )
    history.append({"role": "user", "content": user_input})
    messages = [{"role": "system", "content": system_prompt}] + list(history[:-1]) + [{"role": "user", "content": qa_prompt}]
    answer = await _llm_call(provider, model, messages, temperature, max_tokens)
    history.append({"role": "assistant", "content": answer})

    return {"text": answer, "source_documents": docs, "standalone_question": standalone}


# ─── chain.api ───────────────────────────────────────────────────────────────

@register_node("chain.api")
async def chain_api(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    LLM generates an HTTP request (URL + optional body), executes it, then
    optionally passes the response back through the LLM for a final answer.
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    temperature = float(config.get("temperature", 0.0))
    max_tokens = int(config.get("max_tokens", 512))
    api_docs = config.get("api_docs", "")
    question = _render(config.get("input", "{{input}}"), input_data)
    headers = config.get("request_headers", {})

    # Step 1: let LLM decide what URL/method/body to call
    plan_prompt = (
        f"You are an API assistant. Given the following API documentation and user question, "
        f"return a JSON object with keys: method (GET/POST/PUT/DELETE), url, body (dict or null).\n\n"
        f"API Docs:\n{api_docs}\n\nQuestion: {question}\n\nJSON:"
    )
    plan_text = await _llm_call(provider, model, [{"role": "user", "content": plan_prompt}], temperature, max_tokens)
    try:
        plan_match = re.search(r"\{.*\}", plan_text, re.DOTALL)
        plan = json.loads(plan_match.group()) if plan_match else {}
    except Exception:
        plan = {}

    method = plan.get("method", "GET").upper()
    url = plan.get("url", "")
    body = plan.get("body")

    api_response_text = ""
    if url:
        try:
            async with httpx.AsyncClient(timeout=30) as c:
                r = await c.request(method, url, json=body if body else None, headers=headers)
                api_response_text = r.text[:4000]
        except Exception as e:
            api_response_text = f"Error: {e}"

    # Step 2: LLM interprets the response
    answer_prompt = (
        f"Question: {question}\n\nAPI Response:\n{api_response_text}\n\nAnswer:"
    )
    answer = await _llm_call(provider, model, [{"role": "user", "content": answer_prompt}], temperature, max_tokens)
    return {"text": answer, "api_url": url, "api_method": method, "api_response": api_response_text}


# ─── chain.multi_prompt ──────────────────────────────────────────────────────

@register_node("chain.multi_prompt")
async def chain_multi_prompt(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Router chain: LLM picks which sub-prompt/persona best handles the query,
    then invokes that sub-chain.
    config:
      provider, model — for the router LLM
      destinations: list of {name, description, prompt_template}
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    temperature = float(config.get("temperature", 0.0))
    max_tokens = int(config.get("max_tokens", 1024))
    destinations = config.get("destinations", [])
    question = _render(config.get("input", "{{input}}"), input_data)

    if not destinations:
        return {"text": "No destinations configured.", "destination": None}

    dest_desc = "\n".join(f"- {d['name']}: {d.get('description', '')}" for d in destinations)
    router_prompt = (
        f"Given the user input below, choose the best destination from the list. "
        f"Reply with only the destination name.\n\nDestinations:\n{dest_desc}\n\n"
        f"User input: {question}\n\nDestination:"
    )
    chosen = await _llm_call(provider, model, [{"role": "user", "content": router_prompt}], 0.0, 64)
    chosen = chosen.strip().strip('"').strip("'")

    dest = next((d for d in destinations if d["name"].lower() == chosen.lower()), destinations[0])
    sub_prompt_tmpl = dest.get("prompt_template", "Answer the following: {input}")
    sub_prompt = sub_prompt_tmpl.replace("{input}", question)
    sub_system = dest.get("system_prompt", "You are a helpful assistant.")

    messages = [{"role": "system", "content": sub_system}, {"role": "user", "content": sub_prompt}]
    answer = await _llm_call(provider, model, messages, temperature, max_tokens)
    return {"text": answer, "destination": chosen, "destination_config": dest}


# ─── chain.graph_cypher_qa ───────────────────────────────────────────────────

@register_node("chain.graph_cypher_qa")
async def chain_graph_cypher_qa(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Natural language → Cypher → Neo4j → LLM answer.
    config: provider, model, neo4j_url, neo4j_user, neo4j_password, schema_hint, question
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    temperature = float(config.get("temperature", 0.0))
    max_tokens = int(config.get("max_tokens", 1024))
    neo4j_url = config.get("neo4j_url", settings.__dict__.get("NEO4J_URL", "bolt://localhost:7687"))
    neo4j_user = config.get("neo4j_user", "neo4j")
    neo4j_password = config.get("neo4j_password", "")
    schema_hint = config.get("schema_hint", "")
    question = _render(config.get("question", "{{input}}"), input_data)

    # Generate Cypher
    cypher_prompt = (
        f"You are a Neo4j expert. Convert the question to a Cypher READ query. "
        f"Return only the Cypher query, no explanation.\n\n"
        f"Schema hint: {schema_hint}\n\nQuestion: {question}\n\nCypher:"
    )
    cypher = await _llm_call(provider, model, [{"role": "user", "content": cypher_prompt}], 0.0, 256)
    cypher = cypher.strip().strip("```").replace("cypher\n", "").strip()

    # Execute via Neo4j HTTP API (bolt is sync; use HTTP API instead)
    neo4j_http = neo4j_url.replace("bolt://", "http://").replace("neo4j://", "http://")
    if not neo4j_http.startswith("http"):
        neo4j_http = "http://localhost:7474"
    else:
        # Convert port: bolt default 7687 → HTTP 7474
        neo4j_http = re.sub(r":7687", ":7474", neo4j_http)

    graph_result = []
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(
                f"{neo4j_http}/db/neo4j/tx/commit",
                auth=(neo4j_user, neo4j_password),
                json={"statements": [{"statement": cypher}]},
            )
            r.raise_for_status()
            data = r.json()
            if data.get("results"):
                cols = data["results"][0].get("columns", [])
                for row in data["results"][0].get("data", []):
                    graph_result.append(dict(zip(cols, row.get("row", []))))
    except Exception as e:
        graph_result = [{"error": str(e)}]

    # LLM interprets result
    answer_prompt = (
        f"Question: {question}\n\nCypher query: {cypher}\n\n"
        f"Graph result: {json.dumps(graph_result, default=str)[:3000]}\n\nAnswer:"
    )
    answer = await _llm_call(provider, model, [{"role": "user", "content": answer_prompt}], temperature, max_tokens)
    return {"text": answer, "cypher": cypher, "graph_result": graph_result}


# ─── chain.vector_db_qa ──────────────────────────────────────────────────────

@register_node("chain.vector_db_qa")
async def chain_vector_db_qa(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Alias for chain.retrieval_qa with explicit vector DB parameters."""
    return await chain_retrieval_qa(config, input_data, credential_id, db)


# ─── chain.sql_db ────────────────────────────────────────────────────────────

@register_node("chain.sql_db")
async def chain_sql_db(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Natural language → SQL → DB → LLM interpretation.
    config: provider, model, db_url, question, max_rows
    """
    import asyncio
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    temperature = float(config.get("temperature", 0.0))
    max_tokens = int(config.get("max_tokens", 1024))
    db_url = config.get("db_url", "")
    question = _render(config.get("question", "{{input}}"), input_data)
    max_rows = int(config.get("max_rows", 50))

    if not db_url:
        return {"text": "db_url is required for chain.sql_db", "error": True}

    # Introspect schema (run sync SQLAlchemy in executor)
    schema_desc = ""
    rows = []
    sql_query = ""
    try:
        import sqlalchemy as sa

        def _introspect_and_run(question_text: str):
            engine = sa.create_engine(db_url)
            insp = sa.inspect(engine)
            tables = insp.get_table_names()
            schema_parts = []
            for t in tables[:20]:
                cols = insp.get_columns(t)
                col_str = ", ".join(f"{c['name']} ({c['type']})" for c in cols[:20])
                schema_parts.append(f"{t}({col_str})")
            return " | ".join(schema_parts), engine

        loop = asyncio.get_event_loop()
        schema_desc, engine = await loop.run_in_executor(None, _introspect_and_run, question)

        # Generate SQL
        sql_prompt = (
            f"You are a SQL expert. Write a SELECT query to answer the question. "
            f"Return only the SQL, no explanation.\n\n"
            f"Schema: {schema_desc[:2000]}\n\nQuestion: {question}\n\nSQL:"
        )
        sql_query = await _llm_call(provider, model, [{"role": "user", "content": sql_prompt}], 0.0, 256)
        sql_query = sql_query.strip().strip("```").replace("sql\n", "").strip()

        def _run_sql():
            with engine.connect() as conn:
                result = conn.execute(sa.text(sql_query))
                return [dict(row._mapping) for row in result.fetchmany(max_rows)]

        rows = await loop.run_in_executor(None, _run_sql)

    except Exception as e:
        rows = [{"error": str(e)}]

    answer_prompt = (
        f"Question: {question}\n\nSQL: {sql_query}\n\n"
        f"Results: {json.dumps(rows, default=str)[:3000]}\n\nAnswer:"
    )
    answer = await _llm_call(provider, model, [{"role": "user", "content": answer_prompt}], temperature, max_tokens)
    return {"text": answer, "sql": sql_query, "rows": rows, "row_count": len(rows)}


# ─── chain.summarization ─────────────────────────────────────────────────────

@register_node("chain.summarization")
async def chain_summarization(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Map-reduce summarization over a list of documents or a long text.
    config: provider, model, chain_type (stuff|map_reduce|refine), temperature, max_tokens
    """
    provider = config.get("provider", "openai")
    model = config.get("model", "gpt-4o-mini")
    temperature = float(config.get("temperature", 0.3))
    max_tokens = int(config.get("max_tokens", 1024))
    chain_type = config.get("chain_type", "stuff")
    map_prompt = config.get("map_prompt", "Summarize the following text:\n\n{text}\n\nSummary:")
    combine_prompt = config.get("combine_prompt", "Combine these summaries into a final summary:\n\n{text}\n\nFinal Summary:")

    # Accept either 'documents' list or 'text' string
    documents = input_data.get("documents") or []
    if not documents:
        raw = input_data.get("text", "")
        if raw:
            documents = [{"content": raw, "metadata": {}}]

    if not documents:
        return {"text": "No documents provided to summarize."}

    if chain_type == "stuff" or len(documents) == 1:
        all_text = "\n\n---\n\n".join(d.get("content", d) if isinstance(d, dict) else str(d) for d in documents)[:8000]
        prompt = map_prompt.replace("{text}", all_text)
        summary = await _llm_call(provider, model, [{"role": "user", "content": prompt}], temperature, max_tokens)
        return {"text": summary, "method": "stuff", "document_count": len(documents)}

    if chain_type in ("map_reduce", "map-reduce"):
        # Map phase
        summaries = []
        for doc in documents:
            chunk = (doc.get("content", doc) if isinstance(doc, dict) else str(doc))[:4000]
            p = map_prompt.replace("{text}", chunk)
            s = await _llm_call(provider, model, [{"role": "user", "content": p}], temperature, max_tokens // 2)
            summaries.append(s)
        # Reduce phase
        combined = "\n\n".join(summaries)[:8000]
        final_prompt = combine_prompt.replace("{text}", combined)
        final = await _llm_call(provider, model, [{"role": "user", "content": final_prompt}], temperature, max_tokens)
        return {"text": final, "method": "map_reduce", "document_count": len(documents), "intermediate_summaries": summaries}

    if chain_type == "refine":
        # Refine: iteratively refine summary with each new document
        first_chunk = (documents[0].get("content", documents[0]) if isinstance(documents[0], dict) else str(documents[0]))[:4000]
        current_summary = await _llm_call(
            provider, model,
            [{"role": "user", "content": map_prompt.replace("{text}", first_chunk)}],
            temperature, max_tokens
        )
        for doc in documents[1:]:
            chunk = (doc.get("content", doc) if isinstance(doc, dict) else str(doc))[:2000]
            refine_p = (
                f"Here is an existing summary:\n{current_summary}\n\n"
                f"Refine it with the new context below:\n{chunk}\n\nRefined summary:"
            )
            current_summary = await _llm_call(
                provider, model, [{"role": "user", "content": refine_p}], temperature, max_tokens
            )
        return {"text": current_summary, "method": "refine", "document_count": len(documents)}

    return {"text": "Unknown chain_type. Use: stuff, map_reduce, or refine."}


# ─── chain.multi_retrieval_qa ────────────────────────────────────────────────

@register_node("chain.multi_retrieval_qa")
async def chain_multi_retrieval_qa(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    MultiRetrievalQA Chain: routes a query to the most relevant retriever from a
    set of named retrievers, then synthesizes an answer.

    config:
      - retrievers: list of {name, description, collection, node_id} dicts
      - query: the user question
      - provider: openai | anthropic (default: openai)
      - model: LLM model for routing + synthesis
      - max_tokens: max answer tokens (default: 1024)
      - top_k: documents to retrieve per retriever (default: 4)
    """
    from core.execution_engine import NODE_HANDLERS

    query = (
        config.get("query") or config.get("input") or
        input_data.get("query") or input_data.get("input", "")
    )
    if not query:
        raise ValueError("chain.multi_retrieval_qa requires 'query'")

    retrievers_cfg = config.get("retrievers", [])
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    max_tokens = int(config.get("max_tokens", 1024))
    top_k = int(config.get("top_k", 4))

    if not retrievers_cfg:
        return {"answer": "No retrievers configured.", "query": query, "retriever_used": None}

    # Step 1: Route — choose best retriever using LLM
    retriever_descriptions = "\n".join(
        f"{i+1}. {r.get('name', f'retriever_{i}')}: {r.get('description', 'No description')}"
        for i, r in enumerate(retrievers_cfg)
    )
    routing_prompt = (
        f"Given the question: '{query}'\n\n"
        f"Choose the most relevant retriever:\n{retriever_descriptions}\n\n"
        f"Reply with ONLY the number of the best retriever (e.g. '1' or '2'):"
    )
    chosen_idx = 0
    try:
        routing_answer = await _llm_call(provider, model, [{"role": "user", "content": routing_prompt}], 0, 16)
        import re as _re
        nums = _re.findall(r"\d+", routing_answer.strip())
        if nums:
            chosen_idx = max(0, min(int(nums[0]) - 1, len(retrievers_cfg) - 1))
    except Exception:
        pass

    chosen_retriever = retrievers_cfg[chosen_idx]
    retriever_node_id = chosen_retriever.get("node_id", "retriever.vector_store")
    retriever_config = {
        "collection": chosen_retriever.get("collection", ""),
        "query": query,
        "top_k": top_k,
        **chosen_retriever.get("config", {}),
    }

    handler = NODE_HANDLERS.get(retriever_node_id)
    if not handler:
        return {"error": f"Retriever node '{retriever_node_id}' not registered", "query": query}

    retriever_result = await handler(retriever_config, input_data, credential_id, db)
    documents = retriever_result.get("documents", [])

    # Step 2: Synthesize answer
    context_parts = []
    for i, doc in enumerate(documents):
        text = doc.get("content", doc.get("text", str(doc))) if isinstance(doc, dict) else str(doc)
        context_parts.append(f"[{i+1}]: {text[:1000]}")
    context_str = "\n\n".join(context_parts)

    if not context_str:
        return {
            "answer": "No relevant documents found.",
            "query": query,
            "retriever_used": chosen_retriever.get("name"),
            "documents": documents,
        }

    synthesis_prompt = (
        f"Context:\n{context_str}\n\n"
        f"Question: {query}\n\nAnswer based on the context:"
    )
    answer = await _llm_call(provider, model, [{"role": "user", "content": synthesis_prompt}], 0.2, max_tokens)

    return {
        "answer": answer.strip(),
        "query": query,
        "retriever_used": chosen_retriever.get("name"),
        "retriever_node_id": retriever_node_id,
        "documents": documents,
        "documents_used": len(documents),
    }


# ─── chain.vectara_qa ────────────────────────────────────────────────────────

@register_node("chain.vectara_qa")
async def chain_vectara_qa(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    VectaraQA Chain: uses Vectara's built-in RAG pipeline for question answering.
    Combines Vectara's hybrid search + summarization in a single API call.

    config:
      - query: user question
      - corpus_id: Vectara corpus ID (or use VECTARA_CORPUS_ID env)
      - num_results: documents to retrieve (default: 5)
      - response_language: language for response (default: eng)
      - summarizer_prompt: Vectara summarizer prompt name (default: vectara-summary-ext-24-05-sml)
    """
    from core.config import settings

    api_key = getattr(settings, "VECTARA_API_KEY", None)
    corpus_id = config.get("corpus_id") or getattr(settings, "VECTARA_CORPUS_ID", None)

    if not api_key:
        raise ValueError("chain.vectara_qa requires VECTARA_API_KEY")
    if not corpus_id:
        raise ValueError("chain.vectara_qa requires VECTARA_CORPUS_ID or corpus_id in config")

    query = (
        config.get("query") or config.get("input") or
        input_data.get("query") or input_data.get("input", "")
    )
    if not query:
        raise ValueError("chain.vectara_qa requires 'query'")

    num_results = int(config.get("num_results", 5))
    response_language = config.get("response_language", "eng")
    summarizer_prompt = config.get("summarizer_prompt", "vectara-summary-ext-24-05-sml")

    payload = {
        "query": query,
        "search": {
            "corpora": [{"corpus_key": str(corpus_id)}],
            "offset": 0,
            "limit": num_results,
        },
        "generation": {
            "prompt_name": summarizer_prompt,
            "max_used_search_results": num_results,
            "response_language": response_language,
        },
    }

    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            "https://api.vectara.io/v2/query",
            json=payload,
            headers={
                "x-api-key": api_key,
                "Content-Type": "application/json",
            },
        )
        r.raise_for_status()
        data = r.json()

    answer = data.get("summary", "")
    search_results = data.get("search_results", [])

    return {
        "answer": answer,
        "query": query,
        "corpus_id": corpus_id,
        "documents": search_results,
        "documents_used": len(search_results),
        "provider": "vectara",
    }
