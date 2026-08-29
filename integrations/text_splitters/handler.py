"""
Text splitter nodes — split documents into chunks for RAG ingestion.

Nodes:
  - splitter.recursive_character  — LangChain-style recursive splitting
  - splitter.character            — simple fixed delimiter split
  - splitter.token                — split by approximate token count
  - splitter.markdown             — split at Markdown headers
  - splitter.code                 — split by code constructs (functions/classes)
  - splitter.sentence             — split at sentence boundaries
"""
import re

from core.execution_engine import register_node

# ─── Recursive Character Splitter ─────────────────────────────────────────────

@register_node("splitter.recursive_character")
async def splitter_recursive_character(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Mimics LangChain's RecursiveCharacterTextSplitter.
    Tries each separator in order, recursively splitting until chunks are small enough.
    """
    text = config.get("text") or input_data.get("text") or ""
    documents = config.get("documents") or input_data.get("documents")

    chunk_size = int(config.get("chunk_size", 1000))
    chunk_overlap = int(config.get("chunk_overlap", 200))
    separators = config.get("separators") or ["\n\n", "\n", ". ", " ", ""]

    def split_recursive(t: str, seps: list[str]) -> list[str]:
        if len(t) <= chunk_size or not seps:
            return [t] if t.strip() else []

        sep = seps[0]
        remaining_seps = seps[1:]

        if sep == "":
            # Split by character
            parts = [t[i:i + chunk_size] for i in range(0, len(t), chunk_size - chunk_overlap)]
            return [p for p in parts if p.strip()]

        splits = t.split(sep) if sep else list(t)
        chunks = []
        current = ""

        for part in splits:
            candidate = current + sep + part if current else part
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.extend(split_recursive(current, remaining_seps))
                if len(part) > chunk_size:
                    chunks.extend(split_recursive(part, remaining_seps))
                    current = ""
                else:
                    current = part

        if current:
            chunks.extend(split_recursive(current, remaining_seps))

        # Merge small chunks
        merged = []
        buf = ""
        for chunk in chunks:
            if not buf:
                buf = chunk
            elif len(buf) + len(chunk) + len(sep) <= chunk_size:
                buf = buf + sep + chunk
            else:
                merged.append(buf)
                buf = chunk
        if buf:
            merged.append(buf)

        return merged

    if documents:
        # Process list of document objects
        all_docs = []
        for doc in documents:
            doc_text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
            doc_meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            chunks = split_recursive(doc_text, separators)
            for i, chunk in enumerate(chunks):
                all_docs.append({"text": chunk, "metadata": {**doc_meta, "chunk_index": i}})
        return {"documents": all_docs, "count": len(all_docs)}
    else:
        chunks = split_recursive(text, separators)
        docs = [{"text": c, "metadata": {"chunk_index": i}} for i, c in enumerate(chunks)]
        return {"documents": docs, "count": len(docs), "chunks": chunks}


# ─── Character Splitter ────────────────────────────────────────────────────────

@register_node("splitter.character")
async def splitter_character(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Split text on a fixed separator (default: double newline)."""
    text = config.get("text") or input_data.get("text") or ""
    documents = config.get("documents") or input_data.get("documents")
    separator = config.get("separator", "\n\n")
    chunk_size = int(config.get("chunk_size", 1000))
    chunk_overlap = int(config.get("chunk_overlap", 200))

    def split_text(t):
        parts = t.split(separator)
        chunks = []
        current = ""
        for part in parts:
            candidate = (current + separator + part).strip() if current else part.strip()
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                # Further split large parts by character
                for i in range(0, len(part), chunk_size - chunk_overlap):
                    chunks.append(part[i:i + chunk_size])
                current = ""
        if current:
            chunks.append(current)
        return [c for c in chunks if c.strip()]

    if documents:
        all_docs = []
        for doc in documents:
            doc_text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
            doc_meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            for i, chunk in enumerate(split_text(doc_text)):
                all_docs.append({"text": chunk, "metadata": {**doc_meta, "chunk_index": i}})
        return {"documents": all_docs, "count": len(all_docs)}
    else:
        chunks = split_text(text)
        docs = [{"text": c, "metadata": {"chunk_index": i}} for i, c in enumerate(chunks)]
        return {"documents": docs, "count": len(docs), "chunks": chunks}


# ─── Token Splitter ────────────────────────────────────────────────────────────

@register_node("splitter.token")
async def splitter_token(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Split by approximate token count (1 token ≈ 4 characters, or use tiktoken if available).
    """
    text = config.get("text") or input_data.get("text") or ""
    documents = config.get("documents") or input_data.get("documents")
    chunk_tokens = int(config.get("chunk_tokens", 256))
    chunk_overlap_tokens = int(config.get("chunk_overlap_tokens", 50))
    encoding_name = config.get("encoding", "cl100k_base")

    def approx_split(t: str) -> list[str]:
        # Try tiktoken for accurate token counting
        try:
            import tiktoken
            enc = tiktoken.get_encoding(encoding_name)
            tokens = enc.encode(t)
            chunks = []
            start = 0
            while start < len(tokens):
                end = start + chunk_tokens
                chunk_tokens_slice = tokens[start:end]
                chunks.append(enc.decode(chunk_tokens_slice))
                start += chunk_tokens - chunk_overlap_tokens
            return [c for c in chunks if c.strip()]
        except ImportError:
            # Fallback: 1 token ≈ 4 chars
            char_size = chunk_tokens * 4
            char_overlap = chunk_overlap_tokens * 4
            chunks = []
            start = 0
            while start < len(t):
                chunks.append(t[start:start + char_size])
                start += char_size - char_overlap
            return [c.strip() for c in chunks if c.strip()]

    if documents:
        all_docs = []
        for doc in documents:
            doc_text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
            doc_meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            for i, chunk in enumerate(approx_split(doc_text)):
                all_docs.append({"text": chunk, "metadata": {**doc_meta, "chunk_index": i}})
        return {"documents": all_docs, "count": len(all_docs)}
    else:
        chunks = approx_split(text)
        docs = [{"text": c, "metadata": {"chunk_index": i}} for i, c in enumerate(chunks)]
        return {"documents": docs, "count": len(docs), "chunks": chunks}


# ─── Markdown Header Splitter ─────────────────────────────────────────────────

@register_node("splitter.markdown")
async def splitter_markdown(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Split Markdown at header boundaries, preserving header context."""
    text = config.get("text") or input_data.get("text") or ""
    documents = config.get("documents") or input_data.get("documents")
    header_levels = config.get("header_levels", [1, 2, 3])  # H1, H2, H3

    pattern = "|".join(f"(?m)^{'#' * lvl} " for lvl in header_levels)
    header_re = re.compile(r"(?m)^(#{1,6}) (.+)$")

    def split_md(t: str) -> list[dict]:
        lines = t.split("\n")
        sections = []
        current_headers = {}
        current_lines = []

        for line in lines:
            m = header_re.match(line)
            if m and int(len(m.group(1))) in header_levels:
                if current_lines:
                    sections.append({
                        "text": "\n".join(current_lines).strip(),
                        "metadata": dict(current_headers),
                    })
                level = len(m.group(1))
                current_headers[f"h{level}"] = m.group(2)
                # Clear deeper headers
                for lvl in range(level + 1, 7):
                    current_headers.pop(f"h{lvl}", None)
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            sections.append({
                "text": "\n".join(current_lines).strip(),
                "metadata": dict(current_headers),
            })

        return [s for s in sections if s["text"]]

    if documents:
        all_docs = []
        for doc in documents:
            doc_text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
            doc_meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            for s in split_md(doc_text):
                all_docs.append({"text": s["text"], "metadata": {**doc_meta, **s["metadata"]}})
        return {"documents": all_docs, "count": len(all_docs)}
    else:
        sections = split_md(text)
        return {"documents": sections, "count": len(sections)}


# ─── Code Splitter ────────────────────────────────────────────────────────────

@register_node("splitter.code")
async def splitter_code(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Split source code at function/class boundaries.
    Supports: python, javascript, typescript, java, go, rust, c, cpp.
    """
    text = config.get("text") or input_data.get("text") or ""
    documents = config.get("documents") or input_data.get("documents")
    language = config.get("language", "python").lower()
    chunk_size = int(config.get("chunk_size", 1500))

    # Language-specific separators (function/class defs)
    separators = {
        "python": ["\nclass ", "\ndef ", "\nasync def ", "\n\n"],
        "javascript": ["\nfunction ", "\nconst ", "\nclass ", "\n\n"],
        "typescript": ["\nfunction ", "\nconst ", "\nclass ", "\ninterface ", "\n\n"],
        "java": ["\npublic ", "\nprivate ", "\nprotected ", "\nclass ", "\n\n"],
        "go": ["\nfunc ", "\ntype ", "\n\n"],
        "rust": ["\nfn ", "\nimpl ", "\nstruct ", "\n\n"],
        "c": ["\nvoid ", "\nint ", "\nstatic ", "\n\n"],
        "cpp": ["\nvoid ", "\nclass ", "\ntemplate", "\n\n"],
    }

    seps = separators.get(language, ["\n\n", "\n"])

    def split_code(t: str) -> list[str]:
        if len(t) <= chunk_size:
            return [t] if t.strip() else []
        for sep in seps:
            if sep in t:
                parts = t.split(sep)
                chunks = []
                current = ""
                for part in parts:
                    candidate = current + sep + part if current else part
                    if len(candidate) <= chunk_size:
                        current = candidate
                    else:
                        if current:
                            chunks.append(current)
                        current = part
                if current:
                    chunks.append(current)
                return [c for c in chunks if c.strip()]
        return [t[i:i + chunk_size] for i in range(0, len(t), chunk_size)]

    if documents:
        all_docs = []
        for doc in documents:
            doc_text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
            doc_meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            for i, chunk in enumerate(split_code(doc_text)):
                all_docs.append({"text": chunk, "metadata": {**doc_meta, "chunk_index": i, "language": language}})
        return {"documents": all_docs, "count": len(all_docs)}
    else:
        chunks = split_code(text)
        docs = [{"text": c, "metadata": {"chunk_index": i, "language": language}} for i, c in enumerate(chunks)]
        return {"documents": docs, "count": len(docs), "chunks": chunks}


# ─── Sentence Splitter ────────────────────────────────────────────────────────

@register_node("splitter.sentence")
async def splitter_sentence(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Split text at sentence boundaries, grouping into chunks by size."""
    text = config.get("text") or input_data.get("text") or ""
    documents = config.get("documents") or input_data.get("documents")
    chunk_size = int(config.get("chunk_size", 1000))
    chunk_overlap_sentences = int(config.get("chunk_overlap_sentences", 1))

    sentence_re = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")

    def split_sentences(t: str) -> list[str]:
        sentences = sentence_re.split(t)
        chunks = []
        current = ""
        i = 0
        while i < len(sentences):
            candidate = (current + " " + sentences[i]).strip() if current else sentences[i]
            if len(candidate) <= chunk_size:
                current = candidate
                i += 1
            else:
                if current:
                    chunks.append(current)
                    # Overlap: go back
                    i = max(0, i - chunk_overlap_sentences)
                    current = ""
                else:
                    chunks.append(sentences[i])
                    i += 1
        if current:
            chunks.append(current)
        return [c.strip() for c in chunks if c.strip()]

    if documents:
        all_docs = []
        for doc in documents:
            doc_text = doc.get("text", "") if isinstance(doc, dict) else str(doc)
            doc_meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            for i, chunk in enumerate(split_sentences(doc_text)):
                all_docs.append({"text": chunk, "metadata": {**doc_meta, "chunk_index": i}})
        return {"documents": all_docs, "count": len(all_docs)}
    else:
        chunks = split_sentences(text)
        docs = [{"text": c, "metadata": {"chunk_index": i}} for i, c in enumerate(chunks)]
        return {"documents": docs, "count": len(docs), "chunks": chunks}


# ─── HTML to Markdown Text Splitter ──────────────────────────────────────────

@register_node("splitter.html_to_markdown")
async def splitter_html_to_markdown(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Convert HTML content to Markdown, then split at Markdown header boundaries.
    Useful for loading HTML pages and splitting for RAG ingestion.
    
    config:
      - text/html: HTML content (or pass via input_data)
      - chunk_size: max characters per chunk (default 1000)
      - chunk_overlap: overlap between chunks (default 200)
      - header_levels: list of header levels to split on (default [1, 2, 3])
      - strip_tags: remove all HTML tags without converting (default False)
    """
    import re

    html = config.get("html") or config.get("text") or input_data.get("html") or input_data.get("text", "")
    documents = config.get("documents") or input_data.get("documents")
    chunk_size = int(config.get("chunk_size", 1000))
    chunk_overlap = int(config.get("chunk_overlap", 200))
    header_levels = config.get("header_levels", [1, 2, 3])
    strip_only = config.get("strip_tags", False)

    def html_to_markdown(h: str) -> str:
        """Convert basic HTML tags to Markdown equivalents."""
        if strip_only:
            return re.sub(r"<[^>]+>", "", h)

        # Try html2text if available
        try:
            import html2text
            converter = html2text.HTML2Text()
            converter.ignore_links = False
            converter.ignore_images = True
            converter.body_width = 0
            return converter.handle(h)
        except ImportError:
            pass

        # Fallback: manual conversion of common tags
        text = h
        # Headers
        for lvl in range(6, 0, -1):
            text = re.sub(
                rf"<h{lvl}[^>]*>(.*?)</h{lvl}>",
                lambda m, l=lvl: "\n" + "#" * l + " " + re.sub(r"<[^>]+>", "", m.group(1)).strip() + "\n",
                text, flags=re.IGNORECASE | re.DOTALL,
            )
        # Bold / strong
        text = re.sub(r"<(b|strong)[^>]*>(.*?)</(b|strong)>", r"**\2**", text, flags=re.IGNORECASE | re.DOTALL)
        # Italic / em
        text = re.sub(r"<(i|em)[^>]*>(.*?)</(i|em)>", r"*\2*", text, flags=re.IGNORECASE | re.DOTALL)
        # Links
        text = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r"[\2](\1)", text, flags=re.IGNORECASE | re.DOTALL)
        # Paragraphs and line breaks
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<p[^>]*>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</p>", "\n", text, flags=re.IGNORECASE)
        # List items
        text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.IGNORECASE | re.DOTALL)
        # Strip remaining tags
        text = re.sub(r"<[^>]+>", "", text)
        # Decode common HTML entities
        text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        text = text.replace("&nbsp;", " ").replace("&quot;", '"').replace("&#39;", "'")
        # Collapse multiple blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def split_markdown_chunks(md: str, meta: dict) -> list[dict]:
        """Split markdown at headers, then further split large sections."""
        header_re = re.compile(r"(?m)^(#{1,6}) (.+)$")
        lines = md.split("\n")
        sections: list[dict] = []
        current_headers: dict = {}
        current_lines: list[str] = []

        for line in lines:
            m = header_re.match(line)
            if m and len(m.group(1)) in header_levels:
                if current_lines:
                    text_chunk = "\n".join(current_lines).strip()
                    if text_chunk:
                        sections.append({"text": text_chunk, "headers": dict(current_headers)})
                level = len(m.group(1))
                current_headers[f"h{level}"] = m.group(2)
                for lvl in range(level + 1, 7):
                    current_headers.pop(f"h{lvl}", None)
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            text_chunk = "\n".join(current_lines).strip()
            if text_chunk:
                sections.append({"text": text_chunk, "headers": dict(current_headers)})

        # Further split large sections
        result = []
        for sec in sections:
            t = sec["text"]
            if len(t) <= chunk_size:
                result.append({"text": t, "metadata": {**meta, **sec["headers"]}})
            else:
                start = 0
                while start < len(t):
                    end = start + chunk_size
                    result.append({"text": t[start:end], "metadata": {**meta, **sec["headers"]}})
                    start += chunk_size - chunk_overlap
        return result

    if documents:
        all_docs = []
        for doc in documents:
            doc_html = doc.get("html") or doc.get("text", "") if isinstance(doc, dict) else str(doc)
            doc_meta = doc.get("metadata", {}) if isinstance(doc, dict) else {}
            md = html_to_markdown(doc_html)
            chunks = split_markdown_chunks(md, doc_meta)
            for i, chunk in enumerate(chunks):
                chunk["metadata"]["chunk_index"] = i
                all_docs.append(chunk)
        return {"documents": all_docs, "count": len(all_docs)}
    else:
        md = html_to_markdown(html)
        chunks = split_markdown_chunks(md, {})
        for i, chunk in enumerate(chunks):
            chunk["metadata"]["chunk_index"] = i
        return {"documents": chunks, "count": len(chunks), "markdown": md}
