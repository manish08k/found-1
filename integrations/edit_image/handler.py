"""
EditImage integration — Cloudinary image manipulation.

Provides resize, crop, format conversion, and watermark operations via the
Cloudinary Upload & Admin APIs.

Credential fields:
  - cloud_name : Cloudinary cloud name
  - api_key    : Cloudinary API key
  - api_secret : Cloudinary API secret

Base URL: https://api.cloudinary.com/v1_1/{cloud_name}/
"""
import hashlib
import time
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)

_CLOUDINARY_BASE = "https://api.cloudinary.com/v1_1"


def _raise_for_status(r: httpx.Response) -> None:
    if r.status_code >= 300:
        try:
            detail = r.json()
        except Exception:
            detail = r.text
        raise ValueError(f"Cloudinary API error {r.status_code}: {detail}")


async def _get_creds(credential_id: str, db) -> tuple[str, str, str]:
    """Return (cloud_name, api_key, api_secret)."""
    creds = await get_credential_data(credential_id, db)
    cloud_name = creds.get("cloud_name", "").strip()
    api_key = creds.get("api_key", "").strip()
    api_secret = creds.get("api_secret", "").strip()
    if not cloud_name:
        raise ValueError("EditImage credential missing 'cloud_name'")
    if not api_key:
        raise ValueError("EditImage credential missing 'api_key'")
    if not api_secret:
        raise ValueError("EditImage credential missing 'api_secret'")
    return cloud_name, api_key, api_secret


def _sign_params(params: dict, api_secret: str) -> str:
    """Generate a Cloudinary request signature."""
    sorted_params = "&".join(
        f"{k}={v}" for k, v in sorted(params.items()) if k not in ("file", "resource_type")
    )
    to_sign = sorted_params + api_secret
    return hashlib.sha1(to_sign.encode()).hexdigest()


def _build_transformation(config: dict, input_data: dict, allowed_keys: list) -> str:
    """Build a Cloudinary transformation string from config."""
    parts = []
    for key in allowed_keys:
        val = config.get(key) or input_data.get(key)
        if val is not None:
            parts.append(f"{key}_{val}")
    return ",".join(parts)


@register_node("edit_image.resize")
async def resize_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Resize an image already uploaded to Cloudinary.

    Config / input keys:
      - public_id (str)   : Cloudinary public ID of the source image.
      - width     (int)   : Target width in pixels.
      - height    (int)   : Target height in pixels.
      - crop      (str)   : Cloudinary crop mode (default: "scale").
      - format    (str)   : Output format, e.g. "jpg", "png", "webp".

    Returns the derived image URL and metadata.
    """
    public_id = config.get("public_id") or input_data.get("public_id")
    width = config.get("width") or input_data.get("width")
    height = config.get("height") or input_data.get("height")
    crop = config.get("crop") or input_data.get("crop", "scale")
    fmt = config.get("format") or input_data.get("format", "jpg")

    if not public_id:
        raise ValueError("edit_image.resize requires 'public_id'")
    if not width and not height:
        raise ValueError("edit_image.resize requires at least 'width' or 'height'")

    cloud_name, api_key, api_secret = await _get_creds(credential_id, db)

    # Build transformation
    transformation_parts = [f"c_{crop}"]
    if width:
        transformation_parts.append(f"w_{width}")
    if height:
        transformation_parts.append(f"h_{height}")
    transformation = ",".join(transformation_parts)

    # Use Cloudinary explicit API to create a derived version
    timestamp = int(time.time())
    params = {
        "public_id": public_id,
        "timestamp": timestamp,
        "eager": transformation,
        "eager_async": "false",
    }
    signature = _sign_params(params, api_secret)

    payload = {**params, "signature": signature, "api_key": api_key}

    log.info("edit_image.resize", public_id=public_id, width=width, height=height, crop=crop)

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{_CLOUDINARY_BASE}/{cloud_name}/image/explicit",
            data=payload,
        )
        _raise_for_status(r)
        data = r.json()

    eager = data.get("eager", [{}])
    derived_url = eager[0].get("secure_url", "") if eager else ""

    return {
        "public_id": data.get("public_id"),
        "url": data.get("secure_url"),
        "derived_url": derived_url,
        "width": data.get("width"),
        "height": data.get("height"),
        "format": data.get("format"),
        "bytes": data.get("bytes"),
        "transformation": transformation,
    }


@register_node("edit_image.crop")
async def crop_image(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Crop an image using Cloudinary's transformation pipeline.

    Config / input keys:
      - public_id (str)         : Cloudinary public ID.
      - width     (int)         : Crop width.
      - height    (int)         : Crop height.
      - x         (int)         : X offset for the crop (gravity-free mode).
      - y         (int)         : Y offset for the crop.
      - gravity   (str)         : Gravity for the crop (e.g. "face", "center",
                                  "north_east").  Defaults to "center".
      - zoom      (float)       : Zoom factor (for face/auto detection crops).

    Returns derived URL and dimensions.
    """
    public_id = config.get("public_id") or input_data.get("public_id")
    width = config.get("width") or input_data.get("width")
    height = config.get("height") or input_data.get("height")
    x = config.get("x") or input_data.get("x")
    y = config.get("y") or input_data.get("y")
    gravity = config.get("gravity") or input_data.get("gravity", "center")
    zoom = config.get("zoom") or input_data.get("zoom")

    if not public_id:
        raise ValueError("edit_image.crop requires 'public_id'")

    cloud_name, api_key, api_secret = await _get_creds(credential_id, db)

    parts = ["c_crop", f"g_{gravity}"]
    if width:
        parts.append(f"w_{width}")
    if height:
        parts.append(f"h_{height}")
    if x is not None:
        parts.append(f"x_{x}")
    if y is not None:
        parts.append(f"y_{y}")
    if zoom:
        parts.append(f"z_{zoom}")
    transformation = ",".join(parts)

    timestamp = int(time.time())
    params = {
        "public_id": public_id,
        "timestamp": timestamp,
        "eager": transformation,
        "eager_async": "false",
    }
    signature = _sign_params(params, api_secret)
    payload = {**params, "signature": signature, "api_key": api_key}

    log.info("edit_image.crop", public_id=public_id, transformation=transformation)

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{_CLOUDINARY_BASE}/{cloud_name}/image/explicit",
            data=payload,
        )
        _raise_for_status(r)
        data = r.json()

    eager = data.get("eager", [{}])
    derived_url = eager[0].get("secure_url", "") if eager else ""

    return {
        "public_id": data.get("public_id"),
        "url": data.get("secure_url"),
        "derived_url": derived_url,
        "transformation": transformation,
        "width": data.get("width"),
        "height": data.get("height"),
    }


@register_node("edit_image.convert_format")
async def convert_format(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Convert an image to a different format via Cloudinary.

    Config / input keys:
      - public_id  (str)  : Cloudinary public ID.
      - format     (str)  : Target format: "jpg", "png", "webp", "gif", "avif".
      - quality    (int)  : Quality 1-100 (for lossy formats).

    Returns the new URL in the requested format.
    """
    public_id = config.get("public_id") or input_data.get("public_id")
    fmt = config.get("format") or input_data.get("format", "webp")
    quality = config.get("quality") or input_data.get("quality")

    if not public_id:
        raise ValueError("edit_image.convert_format requires 'public_id'")

    cloud_name, api_key, api_secret = await _get_creds(credential_id, db)

    transformation_parts = [f"f_{fmt}"]
    if quality:
        transformation_parts.append(f"q_{quality}")
    transformation = ",".join(transformation_parts)

    timestamp = int(time.time())
    params = {
        "public_id": public_id,
        "timestamp": timestamp,
        "eager": transformation,
        "eager_async": "false",
    }
    signature = _sign_params(params, api_secret)
    payload = {**params, "signature": signature, "api_key": api_key}

    log.info("edit_image.convert_format", public_id=public_id, format=fmt)

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{_CLOUDINARY_BASE}/{cloud_name}/image/explicit",
            data=payload,
        )
        _raise_for_status(r)
        data = r.json()

    eager = data.get("eager", [{}])
    derived_url = eager[0].get("secure_url", "") if eager else ""

    return {
        "public_id": data.get("public_id"),
        "original_url": data.get("secure_url"),
        "converted_url": derived_url,
        "format": fmt,
        "bytes": eager[0].get("bytes") if eager else None,
        "transformation": transformation,
    }


@register_node("edit_image.add_watermark")
async def add_watermark(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Overlay a watermark (text or image) on a Cloudinary image.

    Config / input keys:
      - public_id         (str)  : Base image public ID.
      - watermark_text    (str)  : Text to overlay (mutually exclusive with
                                   watermark_public_id).
      - watermark_public_id (str): Public ID of an overlay image.
      - gravity           (str)  : Position — "center", "south_east", etc.
                                   Defaults to "south_east".
      - opacity           (int)  : Opacity 0-100. Defaults to 70.
      - x                 (int)  : X offset. Defaults to 10.
      - y                 (int)  : Y offset. Defaults to 10.
      - font_family       (str)  : Font for text watermarks (default "Arial").
      - font_size         (int)  : Font size (default 40).
      - font_color        (str)  : Font color hex without # (default "ffffff").

    Returns derived URL with watermark applied.
    """
    public_id = config.get("public_id") or input_data.get("public_id")
    watermark_text = config.get("watermark_text") or input_data.get("watermark_text")
    watermark_pid = config.get("watermark_public_id") or input_data.get("watermark_public_id")
    gravity = config.get("gravity") or input_data.get("gravity", "south_east")
    opacity = int(config.get("opacity") or input_data.get("opacity", 70))
    x = int(config.get("x") or input_data.get("x", 10))
    y = int(config.get("y") or input_data.get("y", 10))

    if not public_id:
        raise ValueError("edit_image.add_watermark requires 'public_id'")
    if not watermark_text and not watermark_pid:
        raise ValueError(
            "edit_image.add_watermark requires 'watermark_text' or 'watermark_public_id'"
        )

    cloud_name, api_key, api_secret = await _get_creds(credential_id, db)

    if watermark_text:
        font_family = config.get("font_family") or input_data.get("font_family", "Arial")
        font_size = int(config.get("font_size") or input_data.get("font_size", 40))
        font_color = config.get("font_color") or input_data.get("font_color", "ffffff")
        overlay = f"text:{font_family}_{font_size}_bold:{watermark_text}"
        transformation = (
            f"l_{overlay},co_rgb:{font_color},o_{opacity},g_{gravity},x_{x},y_{y}/fl_layer_apply"
        )
    else:
        overlay = watermark_pid.replace("/", ":")
        transformation = (
            f"l_{overlay},o_{opacity},g_{gravity},x_{x},y_{y}/fl_layer_apply"
        )

    timestamp = int(time.time())
    params = {
        "public_id": public_id,
        "timestamp": timestamp,
        "eager": transformation,
        "eager_async": "false",
    }
    signature = _sign_params(params, api_secret)
    payload = {**params, "signature": signature, "api_key": api_key}

    log.info("edit_image.add_watermark", public_id=public_id, gravity=gravity)

    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{_CLOUDINARY_BASE}/{cloud_name}/image/explicit",
            data=payload,
        )
        _raise_for_status(r)
        data = r.json()

    eager = data.get("eager", [{}])
    derived_url = eager[0].get("secure_url", "") if eager else ""

    return {
        "public_id": data.get("public_id"),
        "original_url": data.get("secure_url"),
        "watermarked_url": derived_url,
        "transformation": transformation,
    }
