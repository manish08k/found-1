"""
Markdown integration.

Provides conversion between Markdown and HTML, plus heading extraction.
Uses the `markdown` library when available, with basic regex fallbacks.

No credentials required — pure data processing.
"""
import re
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

try:
    import markdown as _markdown_lib
    _MARKDOWN_AVAILABLE = True
except ImportError:
    _MARKDOWN_AVAILABLE = False
    log.warning("markdown library not available; using regex fallback")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _md_to_html_regex(md_text: str) -> str:
    """Minimal regex-based Markdown → HTML fallback."""
    html = md_text

    # Headers
    for level in range(6, 0, -1):
        pattern = r"(?m)^{hashes}\s+(.+)$".format(hashes="#" * level)
        html = re.sub(pattern, r"<h{l}>\1</h{l}>".format(l=level), html)

    # Bold & italic
    html = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", html)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Inline code
    html = re.sub(r"`(.+?)`", r"<code>\1</code>", html)

    # Links
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)

    # Paragraphs (double newline → paragraph break)
    paragraphs = re.split(r"\n{2,}", html.strip())
    html = "\n".join(
        f"<p>{p.strip()}</p>" if not p.strip().startswith("<h") else p.strip()
        for p in paragraphs
        if p.strip()
    )

    return html


def _html_to_md_regex(html_text: str) -> str:
    """Minimal regex-based HTML → Markdown fallback."""
    md = html_text

    # Headers
    for level in range(1, 7):
        md = re.sub(
            r"<h{l}[^>]*>(.*?)</h{l}>".format(l=level),
            lambda m, l=level: "{} {}".format("#" * l, m.group(1)),
            md,
            flags=re.IGNORECASE | re.DOTALL,
        )

    # Bold / italic
    md = re.sub(r"<strong>(.*?)</strong>", r"**\1**", md, flags=re.IGNORECASE | re.DOTALL)
    md = re.sub(r"<b>(.*?)</b>", r"**\1**", md, flags=re.IGNORECASE | re.DOTALL)
    md = re.sub(r"<em>(.*?)</em>", r"*\1*", md, flags=re.IGNORECASE | re.DOTALL)
    md = re.sub(r"<i>(.*?)</i>", r"*\1*", md, flags=re.IGNORECASE | re.DOTALL)

    # Code
    md = re.sub(r"<code>(.*?)</code>", r"`\1`", md, flags=re.IGNORECASE | re.DOTALL)

    # Links
    md = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r"[\2](\1)", md, flags=re.IGNORECASE | re.DOTALL)

    # Paragraphs
    md = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", md, flags=re.IGNORECASE | re.DOTALL)

    # Strip remaining tags
    md = re.sub(r"<[^>]+>", "", md)

    return md.strip()


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

@register_node("markdown.to_html")
async def markdown_to_html(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convert Markdown text to HTML."""
    md_text = config.get("markdown") or input_data.get("markdown") or input_data.get("text", "")

    if _MARKDOWN_AVAILABLE:
        extensions = config.get("extensions") or ["extra", "codehilite"]
        try:
            html = _markdown_lib.markdown(md_text, extensions=extensions)
        except Exception:
            html = _markdown_lib.markdown(md_text)
    else:
        html = _md_to_html_regex(md_text)

    log.info("markdown.to_html", input_length=len(md_text), output_length=len(html))
    return {"html": html}


@register_node("markdown.from_html")
async def markdown_from_html(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convert HTML to Markdown text."""
    html_text = config.get("html") or input_data.get("html") or input_data.get("text", "")

    try:
        import html2text as _h2t
        converter = _h2t.HTML2Text()
        converter.ignore_links = False
        md = converter.handle(html_text)
    except ImportError:
        md = _html_to_md_regex(html_text)

    log.info("markdown.from_html", input_length=len(html_text), output_length=len(md))
    return {"markdown": md}


@register_node("markdown.extract_headings")
async def markdown_extract_headings(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Extract all headings from Markdown text."""
    md_text = config.get("markdown") or input_data.get("markdown") or input_data.get("text", "")

    headings = []
    pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    for match in pattern.finditer(md_text):
        level = len(match.group(1))
        text = match.group(2).strip()
        headings.append({"level": level, "text": text})

    log.info("markdown.extract_headings", count=len(headings))
    return {"headings": headings}
