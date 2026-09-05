"""HtmlExtract integration — extract data from HTML using stdlib html.parser."""
import re
import structlog
import httpx
from html.parser import HTMLParser
from urllib.parse import urljoin

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


class _LinkExtractor(HTMLParser):
    """Extract all <a href="..."> links from HTML."""

    def __init__(self, base_url: str = ""):
        super().__init__()
        self.links: list[dict] = []
        self.base_url = base_url

    def handle_starttag(self, tag: str, attrs: list[tuple]) -> None:
        if tag.lower() == "a":
            attr_dict = dict(attrs)
            href = attr_dict.get("href", "")
            if href:
                absolute = urljoin(self.base_url, href) if self.base_url else href
                self.links.append({
                    "href": href,
                    "absolute_url": absolute,
                    "text": "",
                    "title": attr_dict.get("title", ""),
                    "rel": attr_dict.get("rel", ""),
                })
            self._current_link_index = len(self.links) - 1 if href else None
        else:
            self._current_link_index = None

    def handle_data(self, data: str) -> None:
        idx = getattr(self, "_current_link_index", None)
        if idx is not None and 0 <= idx < len(self.links):
            self.links[idx]["text"] += data.strip()


class _TextExtractor(HTMLParser):
    """Extract visible text from HTML, stripping tags."""

    _SKIP_TAGS = {"script", "style", "head", "meta", "link"}

    def __init__(self):
        super().__init__()
        self._skip = 0
        self.texts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple]) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip = max(0, self._skip - 1)

    def handle_data(self, data: str) -> None:
        if self._skip == 0:
            stripped = data.strip()
            if stripped:
                self.texts.append(stripped)


class _SelectorExtractor(HTMLParser):
    """
    Minimal CSS-selector-like extractor supporting:
      - tag name: "div"
      - id: "#myid"
      - class: ".myclass"
      - tag.class: "div.myclass"
      - tag#id: "div#myid"
    Collects inner text content of all matching elements.
    """

    def __init__(self, selector: str):
        super().__init__()
        self._selector = selector
        self._tag_filter: str | None = None
        self._id_filter: str | None = None
        self._class_filter: str | None = None
        self._parse_selector(selector)
        self._depth = 0
        self._collecting = 0
        self.matches: list[dict] = []
        self._current_text = ""

    def _parse_selector(self, selector: str) -> None:
        # Support: tag, #id, .class, tag.class, tag#id
        id_match = re.match(r"^([a-z]*)#([\w-]+)$", selector, re.I)
        class_match = re.match(r"^([a-z]*)\.([\w-]+)$", selector, re.I)
        if id_match:
            self._tag_filter = id_match.group(1).lower() or None
            self._id_filter = id_match.group(2)
        elif class_match:
            self._tag_filter = class_match.group(1).lower() or None
            self._class_filter = class_match.group(2)
        elif selector.startswith("#"):
            self._id_filter = selector[1:]
        elif selector.startswith("."):
            self._class_filter = selector[1:]
        else:
            self._tag_filter = selector.lower()

    def _matches_element(self, tag: str, attrs: list[tuple]) -> bool:
        attr_dict = dict(attrs)
        elem_classes = attr_dict.get("class", "").split()
        elem_id = attr_dict.get("id", "")

        if self._tag_filter and tag.lower() != self._tag_filter:
            return False
        if self._id_filter and elem_id != self._id_filter:
            return False
        if self._class_filter and self._class_filter not in elem_classes:
            return False
        return True

    def handle_starttag(self, tag: str, attrs: list[tuple]) -> None:
        if self._collecting > 0:
            self._collecting += 1
        elif self._matches_element(tag, attrs):
            self._collecting = 1
            self._current_text = ""

    def handle_endtag(self, tag: str) -> None:
        if self._collecting > 0:
            self._collecting -= 1
            if self._collecting == 0:
                self.matches.append({"text": self._current_text.strip()})
                self._current_text = ""

    def handle_data(self, data: str) -> None:
        if self._collecting > 0:
            self._current_text += data


@register_node("htmlextract.extract_all_links")
async def htmlextract_extract_all_links(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Extract all hyperlinks from an HTML string."""
    html = config.get("html") or input_data.get("html") or input_data.get("body", "")
    base_url = config.get("base_url") or input_data.get("base_url") or input_data.get("url", "")

    log.info("htmlextract.extract_all_links", base_url=base_url)

    parser = _LinkExtractor(base_url=base_url)
    parser.feed(html)

    return {"links": parser.links, "count": len(parser.links)}


@register_node("htmlextract.extract_text")
async def htmlextract_extract_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Extract all visible text content from an HTML string."""
    html = config.get("html") or input_data.get("html") or input_data.get("body", "")
    separator = config.get("separator", " ")

    log.info("htmlextract.extract_text")

    parser = _TextExtractor()
    parser.feed(html)

    text = separator.join(parser.texts)
    return {"text": text, "fragments": parser.texts, "fragment_count": len(parser.texts)}


@register_node("htmlextract.extract_by_selector")
async def htmlextract_extract_by_selector(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Extract elements matching a CSS-style selector from an HTML string.

    Supported selector forms: tag, #id, .class, tag.class, tag#id.
    """
    html = config.get("html") or input_data.get("html") or input_data.get("body", "")
    selector = config.get("selector") or input_data.get("selector", "")

    if not selector:
        raise ValueError("htmlextract.extract_by_selector: 'selector' is required")

    log.info("htmlextract.extract_by_selector", selector=selector)

    parser = _SelectorExtractor(selector)
    parser.feed(html)

    return {"matches": parser.matches, "count": len(parser.matches), "selector": selector}
