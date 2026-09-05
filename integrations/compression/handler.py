"""
Compression/Decompression integration.

Pure data-processing nodes — no credentials or HTTP calls required.
Uses Python stdlib (gzip, zlib, bz2) for compression and base64 for
safe string transport of binary data.

Supported formats: gzip, zlib, bz2
"""
import base64
import bz2
import gzip
import zlib
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)

_SUPPORTED_FORMATS = ("gzip", "zlib", "bz2")


def _to_bytes(data) -> bytes:
    """Convert string or bytes input to bytes."""
    if isinstance(data, bytes):
        return data
    if isinstance(data, str):
        # Try base64 decode first (for previously compressed data passed as string)
        try:
            return base64.b64decode(data)
        except Exception:
            return data.encode("utf-8")
    raise TypeError(f"Unsupported input type: {type(data).__name__}")


def _compress(data: bytes, fmt: str) -> bytes:
    fmt = fmt.lower()
    if fmt == "gzip":
        return gzip.compress(data)
    if fmt == "zlib":
        return zlib.compress(data)
    if fmt == "bz2":
        return bz2.compress(data)
    raise ValueError(f"Unsupported compression format '{fmt}'. Choose from: {_SUPPORTED_FORMATS}")


def _decompress(data: bytes, fmt: str) -> bytes:
    fmt = fmt.lower()
    if fmt == "gzip":
        return gzip.decompress(data)
    if fmt == "zlib":
        return zlib.decompress(data)
    if fmt == "bz2":
        return bz2.decompress(data)
    raise ValueError(f"Unsupported compression format '{fmt}'. Choose from: {_SUPPORTED_FORMATS}")


@register_node("compression.compress")
async def compression_compress(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Compress data using gzip, zlib, or bz2.

    Config / input_data:
      - input_data  : The data to compress — string or bytes.
                      Strings are encoded as UTF-8 before compression.
      - format      : Compression format: 'gzip' (default), 'zlib', or 'bz2'
      - output_encoding : 'base64' (default) or 'hex' — encoding for compressed bytes output

    Returns:
      - compressed      : Compressed data encoded as a string (base64 or hex)
      - format          : The compression format used
      - original_size   : Size in bytes of original data
      - compressed_size : Size in bytes after compression
      - ratio           : Compression ratio (compressed / original)
    """
    raw = config.get("input_data") or input_data.get("input_data") or input_data.get("data")
    if raw is None:
        raise ValueError("compression.compress requires 'input_data'")

    fmt = (config.get("format") or input_data.get("format", "gzip")).lower()
    output_encoding = (config.get("output_encoding") or input_data.get("output_encoding", "base64")).lower()

    if fmt not in _SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format '{fmt}'. Choose from: {_SUPPORTED_FORMATS}")

    # Convert input to bytes
    if isinstance(raw, bytes):
        raw_bytes = raw
    elif isinstance(raw, str):
        raw_bytes = raw.encode("utf-8")
    else:
        raise TypeError(f"'input_data' must be str or bytes, got {type(raw).__name__}")

    original_size = len(raw_bytes)
    compressed_bytes = _compress(raw_bytes, fmt)
    compressed_size = len(compressed_bytes)

    if output_encoding == "hex":
        compressed_str = compressed_bytes.hex()
    else:
        compressed_str = base64.b64encode(compressed_bytes).decode("ascii")

    ratio = round(compressed_size / original_size, 4) if original_size > 0 else 0.0

    log.info("compression.compress", format=fmt, original_size=original_size, compressed_size=compressed_size)

    return {
        "compressed": compressed_str,
        "format": fmt,
        "output_encoding": output_encoding,
        "original_size": original_size,
        "compressed_size": compressed_size,
        "ratio": ratio,
    }


@register_node("compression.decompress")
async def compression_decompress(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Decompress data using gzip, zlib, or bz2.

    Config / input_data:
      - input_data      : The compressed data as a base64 or hex string (or raw bytes)
      - format          : Compression format used: 'gzip' (default), 'zlib', or 'bz2'
      - input_encoding  : How the input string is encoded: 'base64' (default) or 'hex'
      - output_encoding : How to return the decompressed bytes: 'utf-8' (default, tries to
                          decode to text) or 'base64' (always return base64 string)

    Returns:
      - decompressed      : Decompressed data as a string
      - format            : Compression format used
      - compressed_size   : Size in bytes of input data
      - decompressed_size : Size in bytes of decompressed data
    """
    raw = config.get("input_data") or input_data.get("input_data") or input_data.get("data")
    if raw is None:
        raise ValueError("compression.decompress requires 'input_data'")

    fmt = (config.get("format") or input_data.get("format", "gzip")).lower()
    input_encoding = (config.get("input_encoding") or input_data.get("input_encoding", "base64")).lower()
    output_encoding = (config.get("output_encoding") or input_data.get("output_encoding", "utf-8")).lower()

    if fmt not in _SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format '{fmt}'. Choose from: {_SUPPORTED_FORMATS}")

    # Decode the input
    if isinstance(raw, bytes):
        compressed_bytes = raw
    elif isinstance(raw, str):
        if input_encoding == "hex":
            compressed_bytes = bytes.fromhex(raw)
        else:
            compressed_bytes = base64.b64decode(raw)
    else:
        raise TypeError(f"'input_data' must be str or bytes, got {type(raw).__name__}")

    compressed_size = len(compressed_bytes)
    decompressed_bytes = _decompress(compressed_bytes, fmt)
    decompressed_size = len(decompressed_bytes)

    if output_encoding == "base64":
        decompressed_str = base64.b64encode(decompressed_bytes).decode("ascii")
    else:
        try:
            decompressed_str = decompressed_bytes.decode("utf-8")
        except UnicodeDecodeError:
            # Fall back to base64 if not valid UTF-8
            decompressed_str = base64.b64encode(decompressed_bytes).decode("ascii")
            output_encoding = "base64"

    log.info("compression.decompress", format=fmt, compressed_size=compressed_size, decompressed_size=decompressed_size)

    return {
        "decompressed": decompressed_str,
        "format": fmt,
        "output_encoding": output_encoding,
        "compressed_size": compressed_size,
        "decompressed_size": decompressed_size,
    }
