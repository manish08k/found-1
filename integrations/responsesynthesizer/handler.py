"""
Response synthesizer nodes — LlamaIndex-compatible response synthesis strategies.
These nodes take retrieved documents and synthesize a final answer using different
strategies: compact, refine, simple, and tree-based hierarchical summarization.

Nodes:
  - synthesizer.compact_refine    — CompactRefine: compact then refine
  - synthesizer.refine            — Refine: iterative refinement
  - synthesizer.simple_response   — SimpleResponseBuilder: single-pass synthesis
  - synthesizer.tree_summarize    — TreeSummarize: hierarchical summarization
"""
import asyncio
import json
import math
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


async def _call_llm(provider: str, model: str, system: str, prompt: str,
                    max_tokens: int = 1024) -> str:
    if provider == "anthropic":
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY required")
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

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise ValueError("OPENAI_API_KEY required (or set provider=anthropic)")
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


def _extract_docs(config: dict, input_data: dict) -> list[str]:
    """Extract document texts from config or input_data."""
    docs = (
        config.get("context_docs")
        or config.get("documents")
        or input_data.get("documents")
        or input_data.get("context_docs")
        or []
    )
    texts = []
    for doc in docs:
        if isinstance(doc, dict):
            texts.append(doc.get("content") or doc.get("text", str(doc)))
        elif isinstance(doc, str):
            texts.append(doc)
    return texts


# ─── SimpleResponseBuilder ────────────────────────────────────────────────────

@register_node("synthesizer.simple_response")
async def synthesizer_simple_response(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    SimpleResponseBuilder: concatenates all context into a single prompt and
    generates one response. The simplest and fastest synthesis strategy.

    config:
      - query: user question
      - context_docs/documents: list of {text/content, metadata} dicts or strings
      - provider: openai | anthropic (default: openai)
      - model: LLM model
      - max_tokens: max response length (default: 1024)
      - system_prompt: custom system instructions
    """
    query = _render(
        config.get("query") or config.get("input") or config.get("prompt", ""),
        input_data,
    ) or input_data.get("query") or input_data.get("input", "")

    if not query:
        raise ValueError("synthesizer.simple_response requires 'query'")

    doc_texts = _extract_docs(config, input_data)
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    max_tokens = int(config.get("max_tokens", 1024))

    if not doc_texts:
        return {
            "answer": "No context documents provided for synthesis.",
            "query": query,
            "strategy": "simple_response",
            "documents_used": 0,
        }

    context_str = "\n\n".join(f"[Doc {i+1}]: {t}" for i, t in enumerate(doc_texts))
    system = config.get("system_prompt") or (
        "You answer questions accurately based on provided context. "
        "Cite document numbers when using specific information."
    )
    prompt = f"Context:\n{context_str}\n\nQuestion: {query}\n\nAnswer:"

    answer = await _call_llm(provider, model, system, prompt, max_tokens)

    return {
        "answer": answer.strip(),
        "query": query,
        "strategy": "simple_response",
        "documents_used": len(doc_texts),
        "provider": provider,
    }


# ─── Refine ──────────────────────────────────────────────────────────────────

@register_node("synthesizer.refine")
async def synthesizer_refine(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Refine: iteratively refines the answer by going through each document chunk.
    Makes N LLM calls (one per document), each refining the previous answer.
    Good for when documents contain complementary information.

    config:
      - query: user question
      - context_docs/documents: list of document dicts or strings
      - provider: openai | anthropic (default: openai)
      - model: LLM model
      - max_tokens: max response per refinement step (default: 1024)
    """
    query = _render(
        config.get("query") or config.get("input") or config.get("prompt", ""),
        input_data,
    ) or input_data.get("query") or input_data.get("input", "")

    if not query:
        raise ValueError("synthesizer.refine requires 'query'")

    doc_texts = _extract_docs(config, input_data)
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    max_tokens = int(config.get("max_tokens", 1024))

    if not doc_texts:
        return {
            "answer": "No context documents provided.",
            "query": query,
            "strategy": "refine",
            "documents_used": 0,
            "refinement_steps": 0,
        }

    system = (
        "You refine answers using additional context. "
        "If the new context adds value, improve the answer. Otherwise, return it unchanged."
    )

    # Initial answer from first document
    initial_prompt = f"Context:\n{doc_texts[0]}\n\nQuestion: {query}\n\nAnswer:"
    answer = await _call_llm(provider, model, system, initial_prompt, max_tokens)
    steps = 1

    # Refine with remaining documents
    for doc_text in doc_texts[1:]:
        refine_prompt = (
            f"Question: {query}\n\n"
            f"Existing answer: {answer}\n\n"
            f"New context:\n{doc_text}\n\n"
            "Refine the existing answer using the new context if it adds relevant information. "
            "Return the improved answer (or the original if no improvement needed):"
        )
        answer = await _call_llm(provider, model, system, refine_prompt, max_tokens)
        steps += 1

    return {
        "answer": answer.strip(),
        "query": query,
        "strategy": "refine",
        "documents_used": len(doc_texts),
        "refinement_steps": steps,
        "provider": provider,
    }


# ─── CompactRefine ───────────────────────────────────────────────────────────

@register_node("synthesizer.compact_refine")
async def synthesizer_compact_refine(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    CompactRefine: first compacts all documents into condensed summaries to fit
    within context limits, then runs refine over the compacted chunks.
    Best for handling many/large documents efficiently.

    config:
      - query: user question
      - context_docs/documents: list of document dicts or strings
      - provider: openai | anthropic (default: openai)
      - model: LLM model
      - max_tokens: max response length (default: 1024)
      - compact_chunk_size: chars per compact group (default: 3000)
    """
    query = _render(
        config.get("query") or config.get("input") or config.get("prompt", ""),
        input_data,
    ) or input_data.get("query") or input_data.get("input", "")

    if not query:
        raise ValueError("synthesizer.compact_refine requires 'query'")

    doc_texts = _extract_docs(config, input_data)
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    max_tokens = int(config.get("max_tokens", 1024))
    compact_chunk_size = int(config.get("compact_chunk_size", 3000))

    if not doc_texts:
        return {
            "answer": "No context documents provided.",
            "query": query,
            "strategy": "compact_refine",
            "documents_used": 0,
        }

    # Step 1: Compact — group docs into chunks that fit in context
    compact_chunks = []
    current_chunk = ""
    for text in doc_texts:
        candidate = current_chunk + "\n\n" + text if current_chunk else text
        if len(candidate) <= compact_chunk_size:
            current_chunk = candidate
        else:
            if current_chunk:
                compact_chunks.append(current_chunk)
            current_chunk = text
    if current_chunk:
        compact_chunks.append(current_chunk)

    # Step 2: Summarize each compact chunk for the query
    compact_system = (
        "Extract only the information relevant to the given question from the context. "
        "Be concise — include only what matters for answering the question."
    )
    summaries = []
    for chunk in compact_chunks:
        summary = await _call_llm(
            provider, model, compact_system,
            f"Question: {query}\n\nContext:\n{chunk}\n\nRelevant information:",
            512,
        )
        summaries.append(summary.strip())

    # Step 3: Refine over compacted summaries
    refine_system = "You synthesize and refine answers from multiple context summaries."
    answer = summaries[0] if summaries else "No answer."
    for summary in summaries[1:]:
        answer = await _call_llm(
            provider, model, refine_system,
            f"Question: {query}\n\nExisting answer: {answer}\n\n"
            f"Additional relevant information: {summary}\n\n"
            "Synthesize a better answer combining both:",
            max_tokens,
        )

    # Final polish
    if len(summaries) > 0:
        final_answer = await _call_llm(
            provider, model,
            "You give clear, comprehensive final answers.",
            f"Question: {query}\n\nSynthesized information: {answer}\n\nFinal answer:",
            max_tokens,
        )
    else:
        final_answer = answer

    return {
        "answer": final_answer.strip(),
        "query": query,
        "strategy": "compact_refine",
        "documents_used": len(doc_texts),
        "compact_chunks": len(compact_chunks),
        "provider": provider,
    }


# ─── TreeSummarize ───────────────────────────────────────────────────────────

@register_node("synthesizer.tree_summarize")
async def synthesizer_tree_summarize(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    TreeSummarize: builds a tree of summaries bottom-up. Chunks are summarized,
    then groups of summaries are summarized again, until a single answer remains.
    Most effective for very large document sets.

    config:
      - query: user question
      - context_docs/documents: list of document dicts or strings
      - provider: openai | anthropic (default: openai)
      - model: LLM model
      - max_tokens: max final answer length (default: 1024)
      - num_children: branching factor for tree (default: 5)
    """
    query = _render(
        config.get("query") or config.get("input") or config.get("prompt", ""),
        input_data,
    ) or input_data.get("query") or input_data.get("input", "")

    if not query:
        raise ValueError("synthesizer.tree_summarize requires 'query'")

    doc_texts = _extract_docs(config, input_data)
    provider = config.get("provider", "openai")
    model = config.get("model", "")
    max_tokens = int(config.get("max_tokens", 1024))
    num_children = int(config.get("num_children", 5))

    if not doc_texts:
        return {
            "answer": "No context documents provided.",
            "query": query,
            "strategy": "tree_summarize",
            "documents_used": 0,
            "tree_levels": 0,
        }

    summarize_system = (
        "You summarize information relevant to a specific question. "
        "Focus on content that directly helps answer the question."
    )

    async def summarize_group(texts: list[str]) -> str:
        combined = "\n\n---\n\n".join(texts)
        return await _call_llm(
            provider, model, summarize_system,
            f"Question: {query}\n\nContent to summarize:\n{combined}\n\nSummary:",
            512,
        )

    # Bottom-up tree reduction
    current_level = doc_texts
    levels = 0

    while len(current_level) > 1:
        levels += 1
        # Group into chunks of num_children
        groups = [
            current_level[i:i + num_children]
            for i in range(0, len(current_level), num_children)
        ]
        # Summarize all groups concurrently
        summaries = await asyncio.gather(*[summarize_group(g) for g in groups])
        current_level = list(summaries)

    # Final synthesis
    final_answer = await _call_llm(
        provider, model,
        "You give comprehensive, well-structured answers based on synthesized information.",
        f"Question: {query}\n\nSynthesized context:\n{current_level[0]}\n\nFinal answer:",
        max_tokens,
    )

    return {
        "answer": final_answer.strip(),
        "query": query,
        "strategy": "tree_summarize",
        "documents_used": len(doc_texts),
        "tree_levels": levels,
        "num_children": num_children,
        "provider": provider,
    }
