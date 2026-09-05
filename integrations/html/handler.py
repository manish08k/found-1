"""HTML integration — extract data, generate from templates, sanitize content.

Pure data-processing nodes; no HTTP calls or credentials required.
Uses Python's stdlib html.parser, re, and string formatting only.
"""
import re
import html
import string
import structlog
from html.parser import HTMLParser
from typing import Any

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


# ─── Helpers ─────────────────────────────────────────────────────────────────

class _TagStripper(HTMLParser):
    """HTMLParser subclass that strips all tags and collects inner text."""

    def __init__(self, allowed_tags: set | None = None):
        super().__init__()
        self._allowed = allowed_tags or set()
        self._parts: list[str] = []
        self._tag_stack: list[str] = []
        self._skip_depth = 0
        self._VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                      "link", "meta", "param", "source", "track", "wbr"}

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if self._skip_depth > 0:
            self._skip_depth += 1
            return
        if tag in self._allowed:
            # Rebuild the tag with allowed attributes only
            attr_str = ""
            for name, value in (attrs or []):
                # Whitelist safe attributes; drop event handlers, javascript: hrefs
                if name.startswith("on"):
                    continue
                if name == "href" and value and value.strip().lower().startswith("javascript:"):
                    continue
                attr_str += f' {html.escape(name)}="{html.escape(value or "")}"'
            self._parts.append(f"<{tag}{attr_str}>")
            if tag not in self._VOID:
                self._tag_stack.append(tag)
        else:
            if tag not in self._VOID:
                self._skip_depth = 0  # still record text inside unknown tags

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag in self._allowed and tag in self._tag_stack:
            self._tag_stack.pop()
            self._parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    def handle_entityref(self, name: str) -> None:
        self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._parts.append(f"&#{name};")

    def get_result(self) -> str:
        return "".join(self._parts)


class _CSSExtractor(HTMLParser):
    """Simple CSS selector extractor (supports tag, .class, #id, tag.class, tag[attr=val])."""

    def __init__(self, selector: str):
        super().__init__()
        self._selector = selector.strip()
        self._matches: list[dict] = []
        self._capture_stack: list[dict] = []  # stack of {tag, depth, text_parts, attrs}
        self._depth = 0
        self._VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
                      "link", "meta", "param", "source", "track", "wbr"}

        # Parse selector into components
        self._sel_tag, self._sel_id, self._sel_class, self._sel_attr = self._parse_selector(selector)

    @staticmethod
    def _parse_selector(selector: str):
        """Parse a basic CSS selector into (tag, id, class, (attr, value))."""
        sel = selector.strip()
        tag = id_ = class_ = None
        attr = attr_val = None

        # Extract attribute selector [attr=val] or [attr]
        attr_match = re.search(r'\[([^\]=]+)(?:=([^\]]*))?\]', sel)
        if attr_match:
            attr = attr_match.group(1).strip().lower()
            attr_val = (attr_match.group(2) or "").strip().strip('"\'')
            sel = sel[:attr_match.start()] + sel[attr_match.end():]

        # Extract id
        id_match = re.search(r'#([\w-]+)', sel)
        if id_match:
            id_ = id_match.group(1)
            sel = sel[:id_match.start()] + sel[id_match.end():]

        # Extract class
        class_match = re.search(r'\.([\w-]+)', sel)
        if class_match:
            class_ = class_match.group(1)
            sel = sel[:class_match.start()] + sel[class_match.end():]

        # Whatever remains is the tag
        tag = sel.strip() or None

        return tag, id_, class_, (attr, attr_val) if attr else None

    def _matches_selector(self, tag: str, attrs: dict) -> bool:
        if self._sel_tag and self._sel_tag != tag:
            return False
        if self._sel_id and attrs.get("id") != self._sel_id:
            return False
        if self._sel_class:
            classes = attrs.get("class", "").split()
            if self._sel_class not in classes:
                return False
        if self._sel_attr:
            attr_name, attr_value = self._sel_attr
            if attr_name not in attrs:
                return False
            if attr_value and attrs[attr_name] != attr_value:
                return False
        return True

    def handle_starttag(self, tag: str, attrs_list: list) -> None:
        self._depth += 1
        attrs = {name.lower(): (value or "") for name, value in attrs_list}
        matched = self._matches_selector(tag, attrs)
        # Start capturing if matched and not already capturing this element
        if matched:
            self._capture_stack.append({
                "tag": tag,
                "start_depth": self._depth,
                "text_parts": [],
                "attrs": attrs,
                "inner_html_parts": [],
            })

    def handle_endtag(self, tag: str) -> None:
        if self._capture_stack and self._capture_stack[-1]["tag"] == tag and \
                self._capture_stack[-1]["start_depth"] == self._depth:
            frame = self._capture_stack.pop()
            self._matches.append({
                "tag": tag,
                "text": "".join(frame["text_parts"]).strip(),
                "attrs": frame["attrs"],
                "inner_html": "".join(frame["inner_html_parts"]).strip(),
            })
        self._depth -= 1

    def handle_data(self, data: str) -> None:
        for frame in self._capture_stack:
            frame["text_parts"].append(data)
            frame["inner_html_parts"].append(html.escape(data))

    def get_matches(self) -> list[dict]:
        return self._matches


# ─── Nodes ───────────────────────────────────────────────────────────────────

@register_node("html.extract_data")
async def html_extract_data(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Extract data from HTML content using CSS selectors.

    config/input_data:
      html_content — raw HTML string to parse (required)
      selectors    — dict mapping output keys to CSS selectors,
                     e.g. {"titles": "h1", "links": "a.nav-link"}
                     OR a single selector string (mapped to key 'results')
      extract_attr — attribute to extract from each match instead of text
                     (e.g. 'href' to get link URLs) (optional)
      first_only   — bool, return only the first match per selector (default False)
      base_url     — optional base URL to resolve relative href/src values

    Supported selectors: tag, #id, .class, tag.class, [attr], [attr=value]
    and simple combinations thereof (single-level only — no descendant combinator).
    """
    html_content = config.get("html_content") or input_data.get("html_content", "")
    selectors = config.get("selectors") or input_data.get("selectors")
    extract_attr = config.get("extract_attr") or input_data.get("extract_attr")
    first_only = bool(config.get("first_only") or input_data.get("first_only", False))
    base_url = config.get("base_url") or input_data.get("base_url", "")

    if not html_content:
        raise ValueError("html_content is required for html.extract_data")

    # Normalise selectors to a dict
    if isinstance(selectors, str):
        selectors = {"results": selectors}
    elif not selectors:
        selectors = {"body_text": "body"}

    output: dict[str, Any] = {}

    for key, selector in selectors.items():
        extractor = _CSSExtractor(selector)
        extractor.feed(html_content)
        matches = extractor.get_matches()

        if extract_attr:
            values = [m["attrs"].get(extract_attr, "") for m in matches]
            # Resolve relative URLs if base_url given and attr is href/src
            if base_url and extract_attr in ("href", "src", "action"):
                resolved = []
                for v in values:
                    if v and not v.startswith(("http://", "https://", "//", "mailto:", "#", "javascript:")):
                        v = base_url.rstrip("/") + "/" + v.lstrip("/")
                    resolved.append(v)
                values = resolved
        else:
            values = [m["text"] for m in matches]

        output[key] = values[0] if first_only else values

    total_matches = sum(len(v) if isinstance(v, list) else 1 for v in output.values())
    log.info("html.extract_data", selectors=list(selectors.keys()), total_matches=total_matches)
    return {
        "extracted": output,
        "selector_count": len(selectors),
        "total_matches": total_matches,
    }


@register_node("html.generate_from_template")
async def html_generate_from_template(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Generate an HTML string from a template with variable substitution.

    Supports two modes:
    1. Python str.format_map style: use {variable_name} in template
    2. $variable / ${variable} style (shell-like) if template_style='dollar'

    config/input_data:
      template       — HTML template string with placeholders (required)
      variables      — dict of variable name → value to substitute (required)
      template_style — 'format' (default) or 'dollar'
      strict         — bool, raise error on missing variables (default False)

    Example:
      template: '<h1>{title}</h1><p>{body}</p>'
      variables: {"title": "Hello", "body": "World"}
    """
    template = config.get("template") or input_data.get("template", "")
    variables = config.get("variables") or input_data.get("variables", {})
    template_style = config.get("template_style") or input_data.get("template_style", "format")
    strict = bool(config.get("strict") or input_data.get("strict", False))

    if not template:
        raise ValueError("template is required for html.generate_from_template")

    # Escape all variable values to prevent XSS
    safe_vars = {k: html.escape(str(v)) for k, v in variables.items()}

    try:
        if template_style == "dollar":
            tmpl = string.Template(template)
            if strict:
                result = tmpl.substitute(safe_vars)
            else:
                result = tmpl.safe_substitute(safe_vars)
        else:
            # format_map with a defaultdict-like fallback for missing keys
            class _SafeDict(dict):
                def __missing__(self, key: str) -> str:
                    if strict:
                        raise KeyError(f"Template variable '{key}' not provided")
                    return f"{{{key}}}"  # leave placeholder intact

            result = template.format_map(_SafeDict(safe_vars))
    except KeyError as exc:
        raise ValueError(f"Missing template variable: {exc}") from exc

    char_count = len(result)
    log.info("html.generate_from_template", char_count=char_count, variables=list(variables.keys()))
    return {
        "html": result,
        "char_count": char_count,
        "variables_applied": list(variables.keys()),
    }


@register_node("html.sanitize")
async def html_sanitize(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Sanitize HTML content by removing dangerous tags and attributes.

    config/input_data:
      html_content  — HTML string to sanitize (required)
      allowed_tags  — list of tag names to keep (default: safe subset)
                      Pass [] to strip ALL tags (plain text output)
      strip_comments — bool, also remove HTML comments (default True)
      collapse_whitespace — bool, collapse multiple spaces/newlines (default False)

    Default allowed tags (safe inline/block elements):
      p, br, b, i, strong, em, u, s, ul, ol, li, a, span, div, h1-h6,
      blockquote, pre, code, table, thead, tbody, tr, th, td
    """
    html_content = config.get("html_content") or input_data.get("html_content", "")
    if not html_content:
        raise ValueError("html_content is required for html.sanitize")

    _SAFE_DEFAULT = {
        "p", "br", "b", "i", "strong", "em", "u", "s",
        "ul", "ol", "li", "a", "span", "div",
        "h1", "h2", "h3", "h4", "h5", "h6",
        "blockquote", "pre", "code",
        "table", "thead", "tbody", "tr", "th", "td",
        "img",  # img kept but with src whitelist handled in _TagStripper
    }

    raw_allowed = config.get("allowed_tags") or input_data.get("allowed_tags")
    if raw_allowed is None:
        allowed_tags = _SAFE_DEFAULT
    else:
        allowed_tags = set(raw_allowed)

    strip_comments = bool(config.get("strip_comments", True) or input_data.get("strip_comments", True))
    collapse_ws = bool(config.get("collapse_whitespace") or input_data.get("collapse_whitespace", False))

    work = html_content

    # Strip HTML comments
    if strip_comments:
        work = re.sub(r'<!--.*?-->', '', work, flags=re.DOTALL)

    # Strip <script> and <style> blocks including their content
    work = re.sub(r'<script\b[^>]*>.*?</script>', '', work, flags=re.DOTALL | re.IGNORECASE)
    work = re.sub(r'<style\b[^>]*>.*?</style>', '', work, flags=re.DOTALL | re.IGNORECASE)

    # Use _TagStripper to keep allowed tags
    stripper = _TagStripper(allowed_tags=allowed_tags)
    stripper.feed(work)
    sanitized = stripper.get_result()

    if collapse_ws:
        sanitized = re.sub(r'[ \t]+', ' ', sanitized)
        sanitized = re.sub(r'\n{3,}', '\n\n', sanitized)
        sanitized = sanitized.strip()

    # Count stripped tags
    original_tag_count = len(re.findall(r'<[^>]+>', html_content))
    result_tag_count = len(re.findall(r'<[^>]+>', sanitized))
    tags_removed = original_tag_count - result_tag_count

    log.info("html.sanitize", original_length=len(html_content), result_length=len(sanitized),
             tags_removed=tags_removed)
    return {
        "sanitized_html": sanitized,
        "original_length": len(html_content),
        "result_length": len(sanitized),
        "tags_removed": max(0, tags_removed),
        "allowed_tags": sorted(allowed_tags),
    }
