"""
QuickChart chart generation integration.

Provides chart image generation, QR code generation, and chart URL
construction via the QuickChart API.

Credential fields (optional — only needed for premium features):
  - api_key : QuickChart API key for premium/high-volume usage.

Auth: api_key included as a query parameter or JSON body field (optional).
Base URL: https://quickchart.io/
"""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

BASE_URL = "https://quickchart.io"


async def _get_api_key(credential_id: str | None, db) -> str | None:
    """Return the API key if a credential_id is provided, otherwise None."""
    if not credential_id:
        return None
    try:
        creds = await get_credential_data(credential_id, db)
        return creds.get("api_key")
    except Exception:
        return None


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"QuickChart API error {r.status_code}: {detail}")


@register_node("quickchart.create_chart")
async def quickchart_create_chart(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Generate a chart image and return it as base64 or a hosted URL.

    Params:
      - chart (required): Chart.js configuration object (dict). Must include at
        minimum 'type' and 'data' keys.
        Example: {"type": "bar", "data": {"labels": ["A","B"], "datasets": [{"data": [1,2]}]}}
      - width: Image width in pixels (default 500).
      - height: Image height in pixels (default 300).
      - device_pixel_ratio: Device pixel ratio for retina output (default 1.0).
      - format: Output format — 'png', 'svg', 'webp', 'pdf' (default 'png').
      - background_color: Background color string (default 'white').
      - version: Chart.js version to use (e.g. '3', '4').
      - encoding: 'url' to return a hosted short URL, 'base64' to embed data inline.
        Default returns binary — use 'base64' for automation-friendly output.
    """
    chart_config = config.get("chart") or input_data.get("chart")
    if not chart_config:
        raise ValueError("quickchart.create_chart requires 'chart' (Chart.js config dict)")

    api_key = await _get_api_key(credential_id, db)

    payload: dict = {"chart": chart_config}

    payload["width"] = int(config.get("width") or input_data.get("width", 500))
    payload["height"] = int(config.get("height") or input_data.get("height", 300))

    device_pixel_ratio = config.get("device_pixel_ratio") or input_data.get("device_pixel_ratio")
    if device_pixel_ratio is not None:
        payload["devicePixelRatio"] = float(device_pixel_ratio)

    fmt = config.get("format") or input_data.get("format", "png")
    payload["format"] = fmt

    bg = config.get("background_color") or input_data.get("background_color", "white")
    payload["backgroundColor"] = bg

    version = config.get("version") or input_data.get("version")
    if version:
        payload["version"] = str(version)

    if api_key:
        payload["key"] = api_key

    encoding = config.get("encoding") or input_data.get("encoding", "base64")

    if encoding == "url":
        # Return a short-URL hosted by QuickChart
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            r = await client.post("/chart/create", json=payload)
            _raise_for_status(r)
            data = r.json()
        chart_url = data.get("url", "")
        log.info("quickchart.create_chart", encoding="url", url=chart_url)
        return {"chart_url": chart_url, "encoding": "url"}
    else:
        import base64
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            r = await client.post("/chart", json=payload)
            _raise_for_status(r)
            content = r.content

        encoded = base64.b64encode(content).decode("utf-8")
        mime = "image/svg+xml" if fmt == "svg" else f"image/{fmt}"
        log.info("quickchart.create_chart", encoding="base64", size=len(content), format=fmt)
        return {
            "content_base64": encoded,
            "mime_type": mime,
            "format": fmt,
            "encoding": "base64",
            "size": len(content),
        }


@register_node("quickchart.get_qr_code")
async def quickchart_get_qr_code(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Generate a QR code image.

    Params:
      - text (required): The text or URL to encode in the QR code.
      - width: Image width in pixels (default 200).
      - height: Image height in pixels (default 200).
      - format: Output format — 'png' or 'svg' (default 'png').
      - margin: Margin (quiet zone) in modules (default 4).
      - ec_level: Error correction level — 'L', 'M', 'Q', 'H' (default 'M').
      - dark: Dark module color (default 'black').
      - light: Light module color (default 'white').
      - center_image_url: URL of an image to embed in the center of the QR code.
    """
    text = config.get("text") or input_data.get("text")
    if not text:
        raise ValueError("quickchart.get_qr_code requires 'text'")

    params: dict = {"text": text}

    params["width"] = int(config.get("width") or input_data.get("width", 200))
    params["height"] = int(config.get("height") or input_data.get("height", 200))

    fmt = config.get("format") or input_data.get("format", "png")
    params["format"] = fmt

    margin = config.get("margin")
    if margin is None:
        margin = input_data.get("margin")
    if margin is not None:
        params["margin"] = int(margin)

    ec_level = config.get("ec_level") or input_data.get("ec_level")
    if ec_level:
        params["ecLevel"] = ec_level

    dark = config.get("dark") or input_data.get("dark")
    if dark:
        params["dark"] = dark

    light = config.get("light") or input_data.get("light")
    if light:
        params["light"] = light

    center_image_url = config.get("center_image_url") or input_data.get("center_image_url")
    if center_image_url:
        params["centerImageUrl"] = center_image_url

    import base64
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        r = await client.get("/qr", params=params)
        _raise_for_status(r)
        content = r.content

    encoded = base64.b64encode(content).decode("utf-8")
    mime = "image/svg+xml" if fmt == "svg" else "image/png"
    log.info("quickchart.get_qr_code", text=text[:60], size=len(content))
    return {
        "content_base64": encoded,
        "mime_type": mime,
        "format": fmt,
        "size": len(content),
    }


@register_node("quickchart.get_chart_url")
async def quickchart_get_chart_url(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Build a QuickChart URL that renders a chart inline (no API call needed for basic usage).

    Params:
      - chart (required): Chart.js configuration object (dict).
      - width: Image width in pixels (default 500).
      - height: Image height in pixels (default 300).
      - format: Output format — 'png', 'svg', 'webp' (default 'png').
      - background_color: Background color (default 'white').
      - version: Chart.js version (e.g. '3').
      - device_pixel_ratio: Device pixel ratio (default 1.0).
      - shorten: bool — if True, request a short URL from QuickChart (default False).
    """
    import json
    import urllib.parse

    chart_config = config.get("chart") or input_data.get("chart")
    if not chart_config:
        raise ValueError("quickchart.get_chart_url requires 'chart' (Chart.js config dict)")

    api_key = await _get_api_key(credential_id, db)

    qp: dict = {
        "c": json.dumps(chart_config, separators=(",", ":")),
        "w": int(config.get("width") or input_data.get("width", 500)),
        "h": int(config.get("height") or input_data.get("height", 300)),
        "f": config.get("format") or input_data.get("format", "png"),
        "bkg": config.get("background_color") or input_data.get("background_color", "white"),
    }

    version = config.get("version") or input_data.get("version")
    if version:
        qp["v"] = str(version)

    dpr = config.get("device_pixel_ratio") or input_data.get("device_pixel_ratio")
    if dpr is not None:
        qp["devicePixelRatio"] = float(dpr)

    if api_key:
        qp["key"] = api_key

    chart_url = f"https://quickchart.io/chart?{urllib.parse.urlencode(qp)}"

    shorten = config.get("shorten") or input_data.get("shorten", False)
    if shorten:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
            r = await client.post("/chart/create", json={"chart": chart_config, **{k: v for k, v in qp.items() if k != "c"}})
            if r.status_code < 300:
                data = r.json()
                chart_url = data.get("url", chart_url)

    log.info("quickchart.get_chart_url", url_length=len(chart_url))
    return {"chart_url": chart_url}
