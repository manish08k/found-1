"""
Engine nodes — query and chat engines analogous to LlamaIndex's engine layer.
These nodes combine retrieval + synthesis into a single callable unit.

Nodes:
  - engine.query_engine           — QueryEngine: retrieve + synthesize answer
  - engine.chat_engine            — ChatEngine: retrieval + conversation memory
  - engine.sub_question_query     — SubQuestionQueryEngine: decompose + answer
"""
import asyncio
import json
import re

import httpx
import structlog

from core.execution_engine import register_node, NODE_HANDLERS
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


async def _call_llm(provider: str, model: str, system: str, prompt: str,
                    max_tokens: int = 1024) -> str:
    """Shared LLM caller for engine nodes."""
    if provider == "anthropic":
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY required for engine nodes")
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                json={
                    "model": model or "claude-3-5-haiku-20241022",
                    "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            r.raise_for_status()
            return r.json()["content"][0]["text"]

    # Default: OpenAI
    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY required for engine nodes (or set provider=anthropic)")
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model or "gpt-4o-mini",
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


async def _retrieve(vs_type: str, collection: str, query: str, top_k: int,
                    credential_id, db) -> list[dict]:
    """Retrieve documents from configured vector store."""
    query_node = f"vectorstore.{vs_type}.query"
    if query_node in NODE_HANDLERS:
        result = await NODE_HANDLERS[query_node](
            {"collection": collection, "query": query, "top_k": top_k},
            {"query": query},
            credential_id,
            db,
        )
        return result.get("results", result.get("documents", []))

    # Fallback to generic vector search
    if "vector.search" in NODE_HANDLERS:
        result = await NODE_HANDLERS["vector.search"](
            {"collection": collection, "query": query, "top_k": top_k},
            {"query": query},
            credential_id,
            db,
        )
        return result.get("results", [])

    return []


# ─── QueryEngine ──────────────────────────────────────────────────────────────

@register_node("engine.query_engine")
async def engine_query_engine(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    QueryEngine: retrieves relevant documents from a vector store and synthesizes
    a comprehensive answer. Analogous to LlamaIndex's VectorStoreIndex.as_query_engine().

    config:
      - query: user question (supports {{ }} templates)
      - collection: vector store collection name
      - vectorstore_type: inmemory | faiss | chroma | pinecone | qdrant | weaviate | ...
      - top_k: documents to retrieve (default: 4)
      - provider: openai | anthropic (default: openai)
      - model: LLM model
      - response_mode: compact | refine | simple (default: compact)
      - system_prompt: custom system instructions
      - cite_sources: include source citations in answer (default: True)
    """
    query = _render(
        config.get("query") or config.get("input") or config.get("prompt", ""),
        input_data,
    ) or input_data.get("query") or input_data.get("input", "")

    if not query:
        raise ValueError("engine.query_engine requires 'query' in config or input_data")

    collection = config.get("collection", "default")
    vs_type = config.get("vectorstore_type", "inmemory")
    top_k = int(config.get("top_k", 4))
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    response_mode = config.get("response_mode", "compact")
    cite_sources = config.get("cite_sources", True)
    max_tokens = int(config.get("max_tokens", 1024))

    # Step 1: Retrieve
    docs = await _retrieve(vs_type, collection, query, top_k, credential_id, db)

    if not docs:
        return {
            "answer": "No relevant documents found in the knowledge base.",
            "query": query,
            "sources": [],
            "retrieved_count": 0,
        }

    # Step 2: Format context
    context_parts = []
    for i, doc in enumerate(docs):
        text = doc.get("content") or doc.get("text", str(doc))
        meta = doc.get("metadata", {})
        source = meta.get("source") or meta.get("url") or meta.get("file") or f"Document {i+1}"
        if cite_sources:
            context_parts.append(f"[Source {i+1}: {source}]\n{text}")
        else:
            context_parts.append(text)

    context_str = "\n\n---\n\n".join(context_parts)

    # Step 3: Synthesize answer
    system = config.get("system_prompt") or (
        "You are a helpful assistant that answers questions based on the provided context. "
        "Base your answer strictly on the context. If the context doesn't contain the answer, "
        "say so clearly. Be concise but comprehensive."
    )

    if response_mode == "refine":
        # Iterative refinement over document chunks
        answer = "No answer yet."
        for i, doc in enumerate(docs):
            text = doc.get("content") or doc.get("text", str(doc))
            refine_prompt = (
                f"Question: {query}\n\n"
                f"Existing answer: {answer}\n\n"
                f"Additional context (document {i+1}):\n{text}\n\n"
                "Refine the answer using this additional context if helpful. "
                "If the existing answer is already good, return it unchanged."
            )
            answer = await _call_llm(provider, model, system, refine_prompt, max_tokens)
    else:
        # Compact: all context in one call
        qa_prompt = (
            f"Context:\n{context_str}\n\n"
            f"Question: {query}\n\n"
            f"{'Include source citations (e.g., [Source 1]) where relevant. ' if cite_sources else ''}"
            "Answer:"
        )
        answer = await _call_llm(provider, model, system, qa_prompt, max_tokens)

    sources = []
    for i, doc in enumerate(docs):
        meta = doc.get("metadata", {})
        sources.append({
            "index": i + 1,
            "source": meta.get("source") or meta.get("url") or meta.get("file") or f"Document {i+1}",
            "score": doc.get("score"),
            "metadata": meta,
        })

    return {
        "answer": answer.strip(),
        "query": query,
        "sources": sources,
        "retrieved_count": len(docs),
        "collection": collection,
        "response_mode": response_mode,
        "provider": provider,
    }


# ─── ChatEngine ──────────────────────────────────────────────────────────────

# In-process session store for chat engines
_CHAT_ENGINE_SESSIONS: dict[str, list[dict]] = {}


@register_node("engine.chat_engine")
async def engine_chat_engine(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    ChatEngine: combines retrieval with conversation memory for multi-turn RAG.
    Maintains session history and condenses follow-up questions.
    Analogous to LlamaIndex's CondensePlusContextChatEngine.

    config:
      - query/input: user message
      - session_id: conversation identifier (default: "default")
      - collection: vector store collection name
      - vectorstore_type: vector store backend (default: inmemory)
      - top_k: documents to retrieve per turn (default: 4)
      - provider: openai | anthropic (default: openai)
      - model: LLM model
      - max_history: max conversation turns to keep (default: 10)
      - system_prompt: custom system instructions
    """
    query = _render(
        config.get("query") or config.get("input") or config.get("message") or config.get("prompt", ""),
        input_data,
    ) or input_data.get("query") or input_data.get("input") or input_data.get("message", "")

    if not query:
        raise ValueError("engine.chat_engine requires 'query', 'input', or 'message'")

    session_id = config.get("session_id") or input_data.get("session_id", "default")
    collection = config.get("collection", "default")
    vs_type = config.get("vectorstore_type", "inmemory")
    top_k = int(config.get("top_k", 4))
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    max_history = int(config.get("max_history", 10))
    max_tokens = int(config.get("max_tokens", 1024))

    history = _CHAT_ENGINE_SESSIONS.get(session_id, [])

    # Step 1: Condense follow-up question if there's history
    standalone_query = query
    if history:
        hist_str = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
        condense_prompt = (
            f"Chat history:\n{hist_str}\n\n"
            f"Follow-up question: {query}\n\n"
            "Rephrase the follow-up as a standalone question with full context. "
            "Return ONLY the rephrased question:"
        )
        standalone_query = await _call_llm(
            provider, model,
            "Rephrase follow-up questions as standalone questions.",
            condense_prompt,
            256,
        )
        standalone_query = standalone_query.strip()

    # Step 2: Retrieve relevant context
    docs = await _retrieve(vs_type, collection, standalone_query, top_k, credential_id, db)
    context_str = "\n\n".join(
        d.get("content") or d.get("text", str(d)) for d in docs
    ) if docs else "No relevant context found."

    # Step 3: Generate response
    hist_str = "\n".join(f"{m['role']}: {m['content']}" for m in history[-max_history * 2:])

    system = config.get("system_prompt") or (
        "You are a helpful conversational assistant with access to a knowledge base. "
        "Answer based on the provided context. For questions not covered in context, "
        "use your general knowledge but indicate when doing so."
    )

    qa_prompt = (
        f"{'Conversation history:' + chr(10) + hist_str + chr(10) + chr(10) if hist_str else ''}"
        f"Context from knowledge base:\n{context_str}\n\n"
        f"User: {query}\n\nAssistant:"
    )

    response = await _call_llm(provider, model, system, qa_prompt, max_tokens)
    response = response.strip()

    # Update session history
    history.append({"role": "user", "content": query})
    history.append({"role": "assistant", "content": response})
    _CHAT_ENGINE_SESSIONS[session_id] = history[-(max_history * 2):]

    return {
        "response": response,
        "query": query,
        "standalone_query": standalone_query,
        "session_id": session_id,
        "sources": [
            {"source": d.get("metadata", {}).get("source", f"doc_{i}"), "score": d.get("score")}
            for i, d in enumerate(docs)
        ],
        "retrieved_count": len(docs),
        "history_length": len(_CHAT_ENGINE_SESSIONS.get(session_id, [])),
        "provider": provider,
    }


# ─── SubQuestionQueryEngine ──────────────────────────────────────────────────

@register_node("engine.sub_question_query")
async def engine_sub_question_query(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    SubQuestionQueryEngine: decomposes complex queries into sub-questions,
    answers each independently, then synthesizes a final comprehensive answer.
    Analogous to LlamaIndex's SubQuestionQueryEngine.

    config:
      - query/input: complex user question
      - collections: list of collection names to query (each becomes a "tool")
      - vectorstore_type: vector store backend (default: inmemory)
      - top_k: documents per sub-question (default: 3)
      - provider: openai | anthropic (default: openai)
      - model: LLM model
      - max_sub_questions: max sub-questions to generate (default: 4)
    """
    query = _render(
        config.get("query") or config.get("input") or config.get("prompt", ""),
        input_data,
    ) or input_data.get("query") or input_data.get("input", "")

    if not query:
        raise ValueError("engine.sub_question_query requires 'query' in config or input_data")

    collections = config.get("collections") or [config.get("collection", "default")]
    vs_type = config.get("vectorstore_type", "inmemory")
    top_k = int(config.get("top_k", 3))
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    max_sub_questions = int(config.get("max_sub_questions", 4))
    max_tokens = int(config.get("max_tokens", 1024))

    # Step 1: Decompose into sub-questions
    collections_desc = "\n".join(f"- {c}" for c in collections)
    decompose_system = (
        "You decompose complex questions into simple, focused sub-questions. "
        "Each sub-question should be answerable from a specific knowledge source."
    )
    decompose_prompt = (
        f"Available knowledge sources:\n{collections_desc}\n\n"
        f"Complex question: {query}\n\n"
        f"Break this into at most {max_sub_questions} focused sub-questions. "
        "For each, specify which source to use. Format:\n"
        "1. [source_name] Sub-question text\n"
        "2. [source_name] Sub-question text\n"
        "...\n\nSub-questions:"
    )

    sub_questions_text = await _call_llm(provider, model, decompose_system, decompose_prompt, 512)

    # Parse sub-questions
    sub_questions = []
    for line in sub_questions_text.strip().split("\n"):
        line = line.strip()
        if not line or not (line[0].isdigit() or line.startswith("-")):
            continue
        # Remove leading number/bullet
        line = re.sub(r"^[\d\.\-\)\s]+", "", line).strip()
        if not line:
            continue
        # Extract source if specified as [source_name]
        source_match = re.match(r"\[([^\]]+)\]\s*(.+)", line)
        if source_match:
            src = source_match.group(1)
            q = source_match.group(2)
        else:
            src = collections[0] if collections else "default"
            q = line
        # Match source to actual collection
        matched_src = next(
            (c for c in collections if src.lower() in c.lower() or c.lower() in src.lower()),
            collections[0] if collections else "default",
        )
        sub_questions.append({"collection": matched_src, "question": q})

    if not sub_questions:
        sub_questions = [{"collection": collections[0] if collections else "default", "question": query}]

    # Step 2: Answer each sub-question
    sub_answers = []
    for sq in sub_questions[:max_sub_questions]:
        docs = await _retrieve(vs_type, sq["collection"], sq["question"], top_k, credential_id, db)
        context = "\n\n".join(d.get("content") or d.get("text", str(d)) for d in docs) or "No context found."

        answer = await _call_llm(
            provider, model,
            "Answer the question concisely based on the provided context.",
            f"Context:\n{context}\n\nQuestion: {sq['question']}\n\nAnswer:",
            512,
        )
        sub_answers.append({
            "question": sq["question"],
            "collection": sq["collection"],
            "answer": answer.strip(),
            "sources": len(docs),
        })

    # Step 3: Synthesize final answer
    sub_qa_str = "\n\n".join(
        f"Q: {sa['question']}\nA: {sa['answer']}"
        for sa in sub_answers
    )

    final_system = (
        "You synthesize answers to sub-questions into a comprehensive, well-structured final answer. "
        "Integrate all relevant information coherently."
    )
    final_prompt = (
        f"Original question: {query}\n\n"
        f"Sub-question answers:\n{sub_qa_str}\n\n"
        "Synthesize a comprehensive answer to the original question:"
    )

    final_answer = await _call_llm(provider, model, final_system, final_prompt, max_tokens)

    return {
        "answer": final_answer.strip(),
        "query": query,
        "sub_questions": sub_answers,
        "collections": collections,
        "provider": provider,
        "model": model,
    }
