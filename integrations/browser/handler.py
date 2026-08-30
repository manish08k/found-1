"""
Browser automation nodes — powered by Playwright.

Session management, navigation, interaction, data extraction, file handling,
wait/assert, and JavaScript evaluation nodes for headless browser workflows.

Safety guarantees
-----------------
- browser.navigate: SSRF-guarded via core.ssrf_guard.assert_safe_url
- browser.evaluate: gated by config["allow_js_evaluation"] (default False)
- File uploads: path must be under ALLOWED_UPLOAD_DIRS
- Sessions: auto-expire after SESSION_TIMEOUT_SECONDS of inactivity
- Max concurrent sessions: MAX_SESSIONS
- Selectors: reject javascript: schemes and eval( calls
"""
import asyncio
import base64
import io
import os
import re
import time
import uuid
from typing import Any

import structlog

from core.execution_engine import register_node
from core.ssrf_guard import assert_safe_url

log = structlog.get_logger(__name__)

# ─── Playwright optional import ────────────────────────────────────────────────

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page  # type: ignore
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    log.warning("playwright_not_installed", hint="pip install playwright && playwright install")

# ─── Session store ─────────────────────────────────────────────────────────────
# In production this would be Redis-backed; here we use a module-level dict.
# Each entry: {playwright, browser, context, page, last_used}

_SESSIONS: dict[str, dict[str, Any]] = {}
_SESSIONS_LOCK = asyncio.Lock()

SESSION_TIMEOUT_SECONDS = 300   # 5 minutes of inactivity
MAX_SESSIONS = 10
ALLOWED_UPLOAD_DIRS = ["/tmp", "/uploads", os.path.expanduser("~/uploads")]


# ─── Internal helpers ──────────────────────────────────────────────────────────

def _require_playwright() -> None:
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError(
            "Playwright is not installed. Run: pip install playwright && playwright install"
        )


def _validate_selector(selector: str) -> None:
    """Reject dangerous selector patterns."""
    if not selector:
        raise ValueError("selector must not be empty")
    low = selector.lower()
    if low.startswith("javascript:"):
        raise ValueError("Selector must not start with 'javascript:'")
    if "eval(" in low:
        raise ValueError("Selector must not contain 'eval('")


def _touch_session(session_id: str) -> None:
    if session_id in _SESSIONS:
        _SESSIONS[session_id]["last_used"] = time.monotonic()


def _is_session_expired(session_data: dict) -> bool:
    return time.monotonic() - session_data.get("last_used", 0) > SESSION_TIMEOUT_SECONDS


async def _expire_stale_sessions() -> None:
    """Close and remove sessions that have timed out."""
    expired = [sid for sid, s in _SESSIONS.items() if _is_session_expired(s)]
    for sid in expired:
        session = _SESSIONS.pop(sid, None)
        if session:
            try:
                await session["browser"].close()
            except Exception:
                pass
            try:
                await session["playwright"].__aexit__(None, None, None)
            except Exception:
                pass
            log.info("browser_session_expired", session_id=sid)


async def _get_session(session_id: str | None, config: dict) -> tuple[str, "Page"]:
    """
    Resolve a session_id from config/input or raise.
    Also touches last_used to reset the inactivity timer.
    """
    sid = session_id or config.get("session_id")
    if not sid:
        raise ValueError("session_id is required; run browser.launch first")
    if sid not in _SESSIONS:
        raise ValueError(f"Session '{sid}' not found or already closed")
    session = _SESSIONS[sid]
    if _is_session_expired(session):
        # Clean up lazily
        async with _SESSIONS_LOCK:
            _SESSIONS.pop(sid, None)
        try:
            await session["browser"].close()
        except Exception:
            pass
        try:
            await session["playwright"].__aexit__(None, None, None)
        except Exception:
            pass
        raise ValueError(f"Session '{sid}' has expired (>{SESSION_TIMEOUT_SECONDS}s of inactivity)")
    _touch_session(sid)
    return sid, session["page"]


def _validate_upload_path(path: str) -> None:
    abs_path = os.path.realpath(path)
    for allowed in ALLOWED_UPLOAD_DIRS:
        abs_allowed = os.path.realpath(allowed)
        if abs_path.startswith(abs_allowed + os.sep) or abs_path == abs_allowed:
            return
    raise ValueError(
        f"Upload path '{path}' is not within an allowed directory. "
        f"Allowed: {ALLOWED_UPLOAD_DIRS}"
    )


# ─── Session management ────────────────────────────────────────────────────────

@register_node("browser.launch")
async def browser_launch(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Launch a new browser session.

    config:
      browser         — chromium | firefox | webkit (default: chromium)
      headless        — bool (default: true)
      viewport_width  — int (default: 1280)
      viewport_height — int (default: 720)
      user_agent      — string (optional)
      timeout_ms      — default navigation timeout ms (default: 30000)
    returns: {session_id}
    """
    _require_playwright()

    async with _SESSIONS_LOCK:
        await _expire_stale_sessions()
        if len(_SESSIONS) >= MAX_SESSIONS:
            raise RuntimeError(
                f"Maximum concurrent browser sessions ({MAX_SESSIONS}) reached. "
                "Close an existing session first."
            )

    browser_type = config.get("browser", "chromium").lower()
    headless = bool(config.get("headless", True))
    viewport_width = int(config.get("viewport_width", 1280))
    viewport_height = int(config.get("viewport_height", 720))
    user_agent = config.get("user_agent")
    timeout_ms = int(config.get("timeout_ms", 30000))

    if browser_type not in ("chromium", "firefox", "webkit"):
        raise ValueError(f"Invalid browser type '{browser_type}'. Choose chromium, firefox, or webkit.")

    pw = await async_playwright().start()
    launcher = getattr(pw, browser_type)
    browser: Browser = await launcher.launch(headless=headless)

    context_kwargs: dict = {
        "viewport": {"width": viewport_width, "height": viewport_height},
    }
    if user_agent:
        context_kwargs["user_agent"] = user_agent

    context: BrowserContext = await browser.new_context(**context_kwargs)
    context.set_default_timeout(timeout_ms)
    page: Page = await context.new_page()

    session_id = str(uuid.uuid4())
    async with _SESSIONS_LOCK:
        _SESSIONS[session_id] = {
            "playwright": pw,
            "browser": browser,
            "context": context,
            "page": page,
            "last_used": time.monotonic(),
            "browser_type": browser_type,
        }

    log.info("browser_session_launched", session_id=session_id, browser=browser_type, headless=headless)
    return {"session_id": session_id}


@register_node("browser.close")
async def browser_close(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Close a browser session and free all resources.

    config:
      session_id — the session to close
    returns: {closed: true}
    """
    _require_playwright()

    sid = config.get("session_id") or input_data.get("session_id")
    if not sid:
        raise ValueError("browser.close requires 'session_id'")

    async with _SESSIONS_LOCK:
        session = _SESSIONS.pop(sid, None)

    if session:
        try:
            await session["browser"].close()
        except Exception as exc:
            log.warning("browser_close_error", session_id=sid, error=str(exc))
        try:
            await session["playwright"].stop()
        except Exception as exc:
            log.warning("playwright_stop_error", session_id=sid, error=str(exc))
        log.info("browser_session_closed", session_id=sid)
    else:
        log.warning("browser_close_unknown_session", session_id=sid)

    return {"closed": True, "session_id": sid}


@register_node("browser.screenshot")
async def browser_screenshot(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Take a screenshot of the current page or a specific element.

    config:
      session_id   — session to use
      full_page    — bool, capture full scrollable page (default: false)
      selector     — CSS selector to screenshot a specific element (optional)
    returns: {screenshot_base64, width, height}
    """
    _require_playwright()

    sid, page = await _get_session(input_data.get("session_id"), config)
    full_page = bool(config.get("full_page", False))
    selector = config.get("selector")

    screenshot_bytes: bytes
    if selector:
        _validate_selector(selector)
        element = await page.query_selector(selector)
        if not element:
            raise ValueError(f"browser.screenshot: selector '{selector}' found no elements")
        screenshot_bytes = await element.screenshot()
    else:
        screenshot_bytes = await page.screenshot(full_page=full_page)

    # Get dimensions from the screenshot metadata
    try:
        import struct
        # PNG header: width at bytes 16-20, height at 20-24
        width = struct.unpack(">I", screenshot_bytes[16:20])[0]
        height = struct.unpack(">I", screenshot_bytes[20:24])[0]
    except Exception:
        width = 0
        height = 0

    encoded = base64.b64encode(screenshot_bytes).decode("ascii")
    return {"screenshot_base64": encoded, "width": width, "height": height}


# ─── Navigation ───────────────────────────────────────────────────────────────

@register_node("browser.navigate")
async def browser_navigate(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Navigate to a URL.

    config:
      session_id — session to use
      url        — destination URL (SSRF-checked)
      wait_until — load | domcontentloaded | networkidle (default: load)
    returns: {url, title, status}
    """
    _require_playwright()

    url = config.get("url") or input_data.get("url")
    if not url:
        raise ValueError("browser.navigate requires 'url'")

    # SSRF guard — prevents navigating to internal/metadata addresses
    assert_safe_url(url)

    wait_until = config.get("wait_until", "load")
    if wait_until not in ("load", "domcontentloaded", "networkidle"):
        wait_until = "load"

    sid, page = await _get_session(input_data.get("session_id"), config)
    response = await page.goto(url, wait_until=wait_until)

    status = response.status if response else 0
    current_url = page.url
    title = await page.title()

    log.info("browser_navigated", session_id=sid, url=current_url, status=status)
    return {"url": current_url, "title": title, "status": status}


@register_node("browser.go_back")
async def browser_go_back(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Go back in browser history. returns: {url, title}"""
    _require_playwright()
    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.go_back()
    return {"url": page.url, "title": await page.title()}


@register_node("browser.go_forward")
async def browser_go_forward(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Go forward in browser history. returns: {url, title}"""
    _require_playwright()
    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.go_forward()
    return {"url": page.url, "title": await page.title()}


@register_node("browser.reload")
async def browser_reload(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Reload the current page. returns: {url}"""
    _require_playwright()
    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.reload()
    return {"url": page.url}


@register_node("browser.get_url")
async def browser_get_url(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the current page URL and title. returns: {url, title}"""
    _require_playwright()
    sid, page = await _get_session(input_data.get("session_id"), config)
    return {"url": page.url, "title": await page.title()}


# ─── Interaction ──────────────────────────────────────────────────────────────

@register_node("browser.click")
async def browser_click(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Click an element.

    config:
      session_id — session to use
      selector   — CSS or XPath selector
      timeout_ms — wait timeout (default: session default)
    returns: {clicked: true, selector}
    """
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.click requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    kwargs: dict = {}
    if config.get("timeout_ms"):
        kwargs["timeout"] = int(config["timeout_ms"])
    await page.click(selector, **kwargs)
    return {"clicked": True, "selector": selector}


@register_node("browser.double_click")
async def browser_double_click(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Double-click an element. config: selector. returns: {double_clicked: true}"""
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.double_click requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.dblclick(selector)
    return {"double_clicked": True, "selector": selector}


@register_node("browser.right_click")
async def browser_right_click(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Right-click (context menu) an element. config: selector. returns: {right_clicked: true}"""
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.right_click requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.click(selector, button="right")
    return {"right_clicked": True, "selector": selector}


@register_node("browser.type")
async def browser_type(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Type text into an element.

    config:
      selector — target element
      text     — text to type
      delay_ms — delay between keystrokes in ms (0 = instant, default: 0)
    returns: {typed: true}
    """
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    text = config.get("text", input_data.get("text", ""))
    if not selector:
        raise ValueError("browser.type requires 'selector'")
    _validate_selector(selector)

    delay_ms = int(config.get("delay_ms", 0))
    sid, page = await _get_session(input_data.get("session_id"), config)

    if delay_ms > 0:
        await page.type(selector, text, delay=delay_ms)
    else:
        await page.fill(selector, text)

    return {"typed": True, "selector": selector, "length": len(text)}


@register_node("browser.clear")
async def browser_clear(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Clear an input field. config: selector. returns: {cleared: true}"""
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.clear requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.fill(selector, "")
    return {"cleared": True, "selector": selector}


@register_node("browser.press_key")
async def browser_press_key(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Press a keyboard key.

    config:
      key        — e.g. Enter, Escape, Tab, ArrowDown, Control+a
      selector   — element to focus before pressing (optional)
    returns: {pressed: true, key}
    """
    _require_playwright()
    key = config.get("key") or input_data.get("key")
    if not key:
        raise ValueError("browser.press_key requires 'key'")

    sid, page = await _get_session(input_data.get("session_id"), config)
    selector = config.get("selector")
    if selector:
        _validate_selector(selector)
        await page.press(selector, key)
    else:
        await page.keyboard.press(key)

    return {"pressed": True, "key": key}


@register_node("browser.select_option")
async def browser_select_option(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Select a dropdown option.

    config:
      selector — select element
      value    — option value (or label, or index)
      label    — option label text (alternative to value)
      index    — zero-based option index (alternative to value/label)
    returns: {selected: true}
    """
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.select_option requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)

    if "value" in config:
        await page.select_option(selector, value=str(config["value"]))
    elif "label" in config:
        await page.select_option(selector, label=str(config["label"]))
    elif "index" in config:
        await page.select_option(selector, index=int(config["index"]))
    else:
        raise ValueError("browser.select_option requires one of: value, label, index")

    return {"selected": True, "selector": selector}


@register_node("browser.check")
async def browser_check(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Check a checkbox. config: selector. returns: {checked: true}"""
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.check requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.check(selector)
    return {"checked": True, "selector": selector}


@register_node("browser.uncheck")
async def browser_uncheck(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Uncheck a checkbox. config: selector. returns: {unchecked: true}"""
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.uncheck requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.uncheck(selector)
    return {"unchecked": True, "selector": selector}


@register_node("browser.hover")
async def browser_hover(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Hover over an element. config: selector. returns: {hovered: true}"""
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.hover requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.hover(selector)
    return {"hovered": True, "selector": selector}


@register_node("browser.focus")
async def browser_focus(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Focus an element. config: selector. returns: {focused: true}"""
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.focus requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.focus(selector)
    return {"focused": True, "selector": selector}


@register_node("browser.scroll")
async def browser_scroll(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Scroll the page or scroll to an element.

    config:
      selector — CSS selector to scroll into view (optional)
      x        — horizontal scroll pixels (default: 0)
      y        — vertical scroll pixels (default: 0)
    returns: {scrolled: true}
    """
    _require_playwright()
    sid, page = await _get_session(input_data.get("session_id"), config)

    selector = config.get("selector")
    if selector:
        _validate_selector(selector)
        element = await page.query_selector(selector)
        if not element:
            raise ValueError(f"browser.scroll: selector '{selector}' found no elements")
        await element.scroll_into_view_if_needed()
    else:
        x = int(config.get("x", 0))
        y = int(config.get("y", 0))
        await page.evaluate(f"window.scrollBy({x}, {y})")

    return {"scrolled": True}


@register_node("browser.drag_and_drop")
async def browser_drag_and_drop(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Drag an element from source to target.

    config:
      source_selector — element to drag from
      target_selector — element to drop onto
    returns: {dragged: true}
    """
    _require_playwright()
    source = config.get("source_selector") or input_data.get("source_selector")
    target = config.get("target_selector") or input_data.get("target_selector")
    if not source:
        raise ValueError("browser.drag_and_drop requires 'source_selector'")
    if not target:
        raise ValueError("browser.drag_and_drop requires 'target_selector'")
    _validate_selector(source)
    _validate_selector(target)

    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.drag_and_drop(source, target)
    return {"dragged": True, "source": source, "target": target}


# ─── Data extraction ──────────────────────────────────────────────────────────

@register_node("browser.get_text")
async def browser_get_text(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get text content of an element. config: selector. returns: {text}"""
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.get_text requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    text = await page.inner_text(selector)
    return {"text": text, "selector": selector}


@register_node("browser.get_attribute")
async def browser_get_attribute(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Get an attribute value from an element.

    config:
      selector  — target element
      attribute — attribute name (e.g. href, src, data-id)
    returns: {value}
    """
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    attribute = config.get("attribute") or input_data.get("attribute")
    if not selector:
        raise ValueError("browser.get_attribute requires 'selector'")
    if not attribute:
        raise ValueError("browser.get_attribute requires 'attribute'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    value = await page.get_attribute(selector, attribute)
    return {"value": value, "selector": selector, "attribute": attribute}


@register_node("browser.get_inner_html")
async def browser_get_inner_html(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get innerHTML of an element. config: selector. returns: {html}"""
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.get_inner_html requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    html = await page.inner_html(selector)
    return {"html": html, "selector": selector}


@register_node("browser.get_value")
async def browser_get_value(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Get the value of an input/textarea/select element. config: selector. returns: {value}"""
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.get_value requires 'selector'")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)
    value = await page.input_value(selector)
    return {"value": value, "selector": selector}


@register_node("browser.query_all")
async def browser_query_all(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Query all elements matching a selector and extract data from each.

    config:
      selector       — CSS selector
      extract        — text | href | src | value | attribute (default: text)
      attribute_name — attribute name when extract=attribute
    returns: {items: [...], count}
    """
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.query_all requires 'selector'")
    _validate_selector(selector)

    extract = config.get("extract", "text").lower()
    attribute_name = config.get("attribute_name", "")

    sid, page = await _get_session(input_data.get("session_id"), config)
    elements = await page.query_selector_all(selector)

    items = []
    for el in elements:
        if extract == "text":
            items.append(await el.inner_text())
        elif extract == "href":
            items.append(await el.get_attribute("href"))
        elif extract == "src":
            items.append(await el.get_attribute("src"))
        elif extract == "value":
            items.append(await el.input_value())
        elif extract == "attribute":
            if not attribute_name:
                raise ValueError("browser.query_all: 'attribute_name' required when extract=attribute")
            items.append(await el.get_attribute(attribute_name))
        else:
            items.append(await el.inner_text())

    return {"items": items, "count": len(items), "selector": selector}


@register_node("browser.extract_table")
async def browser_extract_table(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Extract data from an HTML table element.

    config:
      selector — CSS selector pointing to the <table> element
    returns: {headers: [...], rows: [[...]], row_count}
    """
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector", "table")
    _validate_selector(selector)

    sid, page = await _get_session(input_data.get("session_id"), config)

    # Extract via JS evaluation — table structure requires it
    result = await page.evaluate(f"""
        (() => {{
            const table = document.querySelector({repr(selector)});
            if (!table) return null;
            const rows = Array.from(table.querySelectorAll('tr'));
            const headers = [];
            const data = [];
            let headerDone = false;
            for (const row of rows) {{
                const ths = Array.from(row.querySelectorAll('th'));
                const tds = Array.from(row.querySelectorAll('td'));
                if (!headerDone && ths.length > 0) {{
                    headers.push(...ths.map(th => th.innerText.trim()));
                    headerDone = true;
                }} else if (tds.length > 0) {{
                    data.push(tds.map(td => td.innerText.trim()));
                }}
            }}
            return {{headers, rows: data}};
        }})()
    """)

    if result is None:
        raise ValueError(f"browser.extract_table: no table found at selector '{selector}'")

    return {
        "headers": result["headers"],
        "rows": result["rows"],
        "row_count": len(result["rows"]),
        "selector": selector,
    }


@register_node("browser.get_cookies")
async def browser_get_cookies(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Get all cookies for the current page context.
    returns: {cookies: [{name, value, domain, path, ...}]}
    """
    _require_playwright()
    sid, page = await _get_session(input_data.get("session_id"), config)
    context = _SESSIONS[sid]["context"]
    raw_cookies = await context.cookies()
    cookies = [
        {
            "name": c.get("name"),
            "value": c.get("value"),
            "domain": c.get("domain"),
            "path": c.get("path"),
            "secure": c.get("secure", False),
            "http_only": c.get("httpOnly", False),
        }
        for c in raw_cookies
    ]
    return {"cookies": cookies, "count": len(cookies)}


@register_node("browser.get_local_storage")
async def browser_get_local_storage(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Get a localStorage value by key.

    config:
      key — localStorage key
    returns: {value}
    """
    _require_playwright()
    key = config.get("key") or input_data.get("key")
    if not key:
        raise ValueError("browser.get_local_storage requires 'key'")

    sid, page = await _get_session(input_data.get("session_id"), config)
    value = await page.evaluate(f"localStorage.getItem({repr(key)})")
    return {"value": value, "key": key}


# ─── Files ────────────────────────────────────────────────────────────────────

@register_node("browser.upload_file")
async def browser_upload_file(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Upload a file via a file input element.

    config:
      selector       — file input CSS selector
      file_path      — absolute path to the file (must be in an allowed dir)
      content_base64 — base64-encoded file content (alternative to file_path)
      filename       — filename to use with content_base64
    returns: {uploaded: true}
    """
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.upload_file requires 'selector'")
    _validate_selector(selector)

    file_path = config.get("file_path")
    content_base64 = config.get("content_base64")

    sid, page = await _get_session(input_data.get("session_id"), config)

    if file_path:
        _validate_upload_path(file_path)
        if not os.path.isfile(file_path):
            raise ValueError(f"browser.upload_file: file not found: {file_path}")
        await page.set_input_files(selector, file_path)
    elif content_base64:
        filename = config.get("filename", "upload.bin")
        raw = base64.b64decode(content_base64)
        tmp_path = os.path.join("/tmp", f"browser_upload_{uuid.uuid4().hex}_{filename}")
        with open(tmp_path, "wb") as f:
            f.write(raw)
        try:
            await page.set_input_files(selector, tmp_path)
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    else:
        raise ValueError("browser.upload_file requires either 'file_path' or 'content_base64'")

    return {"uploaded": True, "selector": selector}


@register_node("browser.download_wait")
async def browser_download_wait(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Wait for a file download to complete (must be triggered just before this node).

    config:
      timeout_ms — max wait time (default: 30000)
    returns: {filename, path, size}
    """
    _require_playwright()
    timeout_ms = int(config.get("timeout_ms", 30000))
    sid, page = await _get_session(input_data.get("session_id"), config)

    async with page.expect_download(timeout=timeout_ms) as download_info:
        # The download must have been triggered by a prior click/navigation step.
        # We await the download object created by Playwright.
        pass

    download = await download_info.value
    save_path = os.path.join("/tmp", download.suggested_filename)
    await download.save_as(save_path)
    size = os.path.getsize(save_path) if os.path.exists(save_path) else 0

    return {
        "filename": download.suggested_filename,
        "path": save_path,
        "size": size,
    }


# ─── Wait / Assert ────────────────────────────────────────────────────────────

@register_node("browser.wait_for_selector")
async def browser_wait_for_selector(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Wait until an element matching the selector reaches the given state.

    config:
      selector   — CSS selector
      state      — visible | hidden | attached | detached (default: visible)
      timeout_ms — max wait (default: session default)
    returns: {found: true, selector}
    """
    _require_playwright()
    selector = config.get("selector") or input_data.get("selector")
    if not selector:
        raise ValueError("browser.wait_for_selector requires 'selector'")
    _validate_selector(selector)

    state = config.get("state", "visible")
    if state not in ("visible", "hidden", "attached", "detached"):
        state = "visible"

    sid, page = await _get_session(input_data.get("session_id"), config)
    kwargs: dict = {"state": state}
    if config.get("timeout_ms"):
        kwargs["timeout"] = int(config["timeout_ms"])

    await page.wait_for_selector(selector, **kwargs)
    return {"found": True, "selector": selector, "state": state}


@register_node("browser.wait_for_url")
async def browser_wait_for_url(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Wait until the page URL matches a pattern.

    config:
      url_pattern — string (substring match) or regex pattern
      timeout_ms  — max wait (default: session default)
    returns: {url}
    """
    _require_playwright()
    url_pattern = config.get("url_pattern") or input_data.get("url_pattern")
    if not url_pattern:
        raise ValueError("browser.wait_for_url requires 'url_pattern'")

    timeout_ms = int(config.get("timeout_ms", 30000))
    sid, page = await _get_session(input_data.get("session_id"), config)

    try:
        pattern = re.compile(url_pattern)
        await page.wait_for_url(pattern, timeout=timeout_ms)
    except re.error:
        # Treat as substring match
        await page.wait_for_url(f"**{url_pattern}**", timeout=timeout_ms)

    return {"url": page.url}


@register_node("browser.wait_for_response")
async def browser_wait_for_response(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Wait for a network response whose URL matches a pattern.

    config:
      url_pattern — string or regex to match response URL
      timeout_ms  — max wait (default: 30000)
    returns: {status, url}
    """
    _require_playwright()
    url_pattern = config.get("url_pattern") or input_data.get("url_pattern")
    if not url_pattern:
        raise ValueError("browser.wait_for_response requires 'url_pattern'")

    timeout_ms = int(config.get("timeout_ms", 30000))
    sid, page = await _get_session(input_data.get("session_id"), config)

    try:
        pattern = re.compile(url_pattern)
        predicate = lambda response: bool(pattern.search(response.url))
    except re.error:
        predicate = lambda response: url_pattern in response.url

    async with page.expect_response(predicate, timeout=timeout_ms) as response_info:
        pass

    response = await response_info.value
    return {"status": response.status, "url": response.url}


@register_node("browser.wait_ms")
async def browser_wait_ms(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Simple delay node.

    config:
      ms — milliseconds to wait (max 10000)
    returns: {waited_ms}
    """
    ms = int(config.get("ms", input_data.get("ms", 1000)))
    ms = min(ms, 10000)  # hard cap at 10 seconds
    await asyncio.sleep(ms / 1000)
    return {"waited_ms": ms}


# ─── JavaScript ───────────────────────────────────────────────────────────────

@register_node("browser.evaluate")
async def browser_evaluate(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Execute a JavaScript expression in the page context.

    IMPORTANT: disabled by default. Set config.allow_js_evaluation=true to enable.

    config:
      expression          — JS expression that returns a serializable value
      allow_js_evaluation — must be true (default: false)
    returns: {result}
    """
    _require_playwright()

    if not config.get("allow_js_evaluation", False):
        raise PermissionError(
            "browser.evaluate is disabled by policy. "
            "Set allow_js_evaluation=true in the node config to enable JavaScript execution."
        )

    expression = config.get("expression") or input_data.get("expression")
    if not expression:
        raise ValueError("browser.evaluate requires 'expression'")

    sid, page = await _get_session(input_data.get("session_id"), config)
    result = await page.evaluate(expression)
    return {"result": result}


@register_node("browser.inject_style")
async def browser_inject_style(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """
    Inject CSS into the current page.

    config:
      css — CSS string to inject
    returns: {injected: true}
    """
    _require_playwright()
    css = config.get("css") or input_data.get("css")
    if not css:
        raise ValueError("browser.inject_style requires 'css'")

    sid, page = await _get_session(input_data.get("session_id"), config)
    await page.add_style_tag(content=css)
    return {"injected": True, "length": len(css)}
