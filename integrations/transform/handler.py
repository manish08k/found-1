"""
Transform nodes — data manipulation utilities.

Covers:
  set, remove_fields, rename_fields, filter_array, aggregate, sort,
  deduplicate, flatten, unflatten, merge, to_json, from_json, to_csv,
  from_csv, xml_to_json, json_to_xml, html_to_text, markdown_to_html,
  jmespath, jsonpath
"""
import ast
import csv
import io
import json
import re
from copy import deepcopy
from typing import Any

import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _get_nested(obj: Any, key: str) -> Any:
    """Resolve a dot-notation key from a nested dict."""
    parts = key.split(".")
    val = obj
    for p in parts:
        if isinstance(val, dict):
            val = val.get(p)
        else:
            return None
    return val


def _set_nested(obj: dict, key: str, value: Any) -> None:
    """Set a dot-notation key in a nested dict, creating intermediaries."""
    parts = key.split(".")
    d = obj
    for p in parts[:-1]:
        if p not in d or not isinstance(d[p], dict):
            d[p] = {}
        d = d[p]
    d[parts[-1]] = value


def _del_nested(obj: dict, key: str) -> None:
    """Delete a dot-notation key from a nested dict (silently ignores missing)."""
    parts = key.split(".")
    d = obj
    for p in parts[:-1]:
        if not isinstance(d, dict) or p not in d:
            return
        d = d[p]
    if isinstance(d, dict):
        d.pop(parts[-1], None)


def _flatten(obj: Any, prefix: str = "", sep: str = ".") -> dict:
    items: dict = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{prefix}{sep}{k}" if prefix else k
            items.update(_flatten(v, new_key, sep))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            new_key = f"{prefix}{sep}{i}" if prefix else str(i)
            items.update(_flatten(v, new_key, sep))
    else:
        items[prefix] = obj
    return items


def _unflatten(flat: dict, sep: str = ".") -> dict:
    result: dict = {}
    for key, value in flat.items():
        parts = key.split(sep)
        d = result
        for p in parts[:-1]:
            if p not in d or not isinstance(d[p], dict):
                d[p] = {}
            d = d[p]
        d[parts[-1]] = value
    return result


def _deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, dict):
        result = deepcopy(base)
        for k, v in overlay.items():
            if k in result:
                result[k] = _deep_merge(result[k], v)
            else:
                result[k] = deepcopy(v)
        return result
    return deepcopy(overlay)


# ─── set ──────────────────────────────────────────────────────────────────────

@register_node("transform.set")
async def transform_set(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Set/add/overwrite fields in data using dot-notation keys."""
    result = deepcopy(input_data)
    fields: dict = config.get("fields") or {}
    for key, value in fields.items():
        _set_nested(result, key, value)
    return result


# ─── remove_fields ────────────────────────────────────────────────────────────

@register_node("transform.remove_fields")
async def transform_remove_fields(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Remove specified fields from data (supports dot-notation)."""
    result = deepcopy(input_data)
    fields = config.get("fields") or []
    if isinstance(fields, str):
        fields = [f.strip() for f in fields.split(",")]
    for field in fields:
        _del_nested(result, field)
    return result


# ─── rename_fields ────────────────────────────────────────────────────────────

@register_node("transform.rename_fields")
async def transform_rename_fields(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Rename fields via a mapping dict {old_key: new_key}."""
    result = deepcopy(input_data)
    mapping: dict = config.get("mapping") or {}
    for old_key, new_key in mapping.items():
        value = _get_nested(result, old_key)
        if value is not None:
            _del_nested(result, old_key)
            _set_nested(result, new_key, value)
    return result


# ─── filter_array ─────────────────────────────────────────────────────────────

@register_node("transform.filter_array")
async def transform_filter_array(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Filter array items by condition expressed as a JSONPath expression or field equality."""
    array_field = config.get("array_field", "items")
    items = input_data.get(array_field, input_data) if isinstance(input_data, dict) else input_data
    if not isinstance(items, list):
        raise ValueError(f"transform.filter_array: expected list at '{array_field}', got {type(items).__name__}")

    condition_field = config.get("condition_field")
    condition_op = config.get("operator", "eq")
    condition_value = config.get("value")

    if condition_field is None:
        # JSONPath expression mode
        expression = config.get("expression")
        if not expression:
            raise ValueError("transform.filter_array: provide 'condition_field' or 'expression'")
        from jsonpath_ng.ext import parse as jp_parse  # type: ignore
        jp_expr = jp_parse(expression)
        filtered = [item for item in items if jp_expr.find(item)]
    else:
        ops = {
            "eq": lambda a, b: a == b,
            "ne": lambda a, b: a != b,
            "gt": lambda a, b: a > b,
            "gte": lambda a, b: a >= b,
            "lt": lambda a, b: a < b,
            "lte": lambda a, b: a <= b,
            "contains": lambda a, b: b in str(a),
            "startswith": lambda a, b: str(a).startswith(str(b)),
            "endswith": lambda a, b: str(a).endswith(str(b)),
        }
        op_fn = ops.get(condition_op)
        if op_fn is None:
            raise ValueError(f"transform.filter_array: unknown operator '{condition_op}'")
        filtered = [item for item in items if op_fn(_get_nested(item, condition_field), condition_value)]

    result = deepcopy(input_data) if isinstance(input_data, dict) else {}
    result[array_field] = filtered
    result["count"] = len(filtered)
    return result


# ─── aggregate ────────────────────────────────────────────────────────────────

@register_node("transform.aggregate")
async def transform_aggregate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Aggregate array: sum/avg/min/max/count/first/last on a field."""
    array_field = config.get("array_field", "items")
    items = input_data.get(array_field, input_data) if isinstance(input_data, dict) else input_data
    if not isinstance(items, list):
        raise ValueError(f"transform.aggregate: expected list at '{array_field}'")

    operation = config.get("operation", "count").lower()
    field = config.get("field")

    if operation == "count":
        return {"result": len(items), "operation": "count"}

    if not field:
        raise ValueError(f"transform.aggregate: 'field' is required for operation '{operation}'")

    values = [_get_nested(item, field) for item in items]
    numeric = [v for v in values if v is not None and isinstance(v, (int, float))]

    if operation == "sum":
        return {"result": sum(numeric), "operation": "sum", "field": field}
    elif operation == "avg":
        return {"result": sum(numeric) / len(numeric) if numeric else None, "operation": "avg", "field": field}
    elif operation == "min":
        return {"result": min(numeric) if numeric else None, "operation": "min", "field": field}
    elif operation == "max":
        return {"result": max(numeric) if numeric else None, "operation": "max", "field": field}
    elif operation == "first":
        return {"result": values[0] if values else None, "operation": "first", "field": field}
    elif operation == "last":
        return {"result": values[-1] if values else None, "operation": "last", "field": field}
    else:
        raise ValueError(f"transform.aggregate: unknown operation '{operation}'")


# ─── sort ─────────────────────────────────────────────────────────────────────

@register_node("transform.sort")
async def transform_sort(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Sort array by field (asc/desc)."""
    array_field = config.get("array_field", "items")
    items = input_data.get(array_field, input_data) if isinstance(input_data, dict) else input_data
    if not isinstance(items, list):
        raise ValueError(f"transform.sort: expected list at '{array_field}'")

    field = config.get("field")
    direction = config.get("direction", "asc").lower()
    reverse = direction == "desc"

    if field:
        sorted_items = sorted(items, key=lambda x: (_get_nested(x, field) is None, _get_nested(x, field)), reverse=reverse)
    else:
        sorted_items = sorted(items, reverse=reverse)

    result = deepcopy(input_data) if isinstance(input_data, dict) else {}
    result[array_field] = sorted_items
    return result


# ─── deduplicate ──────────────────────────────────────────────────────────────

@register_node("transform.deduplicate")
async def transform_deduplicate(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Remove duplicate items from array by key field."""
    array_field = config.get("array_field", "items")
    items = input_data.get(array_field, input_data) if isinstance(input_data, dict) else input_data
    if not isinstance(items, list):
        raise ValueError(f"transform.deduplicate: expected list at '{array_field}'")

    key_field = config.get("key_field")
    seen: set = set()
    unique = []

    for item in items:
        if key_field:
            key = _get_nested(item, key_field)
            canonical = json.dumps(key, sort_keys=True, default=str)
        else:
            canonical = json.dumps(item, sort_keys=True, default=str)
        if canonical not in seen:
            seen.add(canonical)
            unique.append(item)

    result = deepcopy(input_data) if isinstance(input_data, dict) else {}
    result[array_field] = unique
    result["removed"] = len(items) - len(unique)
    return result


# ─── flatten ──────────────────────────────────────────────────────────────────

@register_node("transform.flatten")
async def transform_flatten(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Flatten nested object to dot-notation keys."""
    sep = config.get("separator", ".")
    return _flatten(input_data, sep=sep)


# ─── unflatten ────────────────────────────────────────────────────────────────

@register_node("transform.unflatten")
async def transform_unflatten(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Reverse of flatten — convert dot-notation keys to nested dict."""
    sep = config.get("separator", ".")
    return _unflatten(input_data, sep=sep)


# ─── merge ────────────────────────────────────────────────────────────────────

@register_node("transform.merge")
async def transform_merge(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Deep merge two objects. 'overlay' config key is merged on top of input_data."""
    overlay = config.get("overlay") or {}
    return _deep_merge(input_data, overlay)


# ─── to_json ──────────────────────────────────────────────────────────────────

@register_node("transform.to_json")
async def transform_to_json(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convert data (or a field) to a JSON string."""
    field = config.get("field")
    indent = config.get("indent")
    value = _get_nested(input_data, field) if field else input_data
    json_str = json.dumps(value, indent=indent, default=str)
    output_field = config.get("output_field", "json")
    return {output_field: json_str}


# ─── from_json ────────────────────────────────────────────────────────────────

@register_node("transform.from_json")
async def transform_from_json(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Parse a JSON string to an object."""
    field = config.get("field", "json")
    json_str = input_data.get(field) if isinstance(input_data, dict) else input_data
    if not isinstance(json_str, str):
        raise ValueError(f"transform.from_json: field '{field}' is not a string")
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"transform.from_json: invalid JSON — {exc}") from exc
    output_field = config.get("output_field", "data")
    return {output_field: parsed}


# ─── to_csv ───────────────────────────────────────────────────────────────────

@register_node("transform.to_csv")
async def transform_to_csv(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convert array of objects to CSV string."""
    array_field = config.get("array_field", "items")
    items = input_data.get(array_field, input_data) if isinstance(input_data, dict) else input_data
    if not isinstance(items, list):
        raise ValueError(f"transform.to_csv: expected list at '{array_field}'")

    delimiter = config.get("delimiter", ",")
    fields = config.get("fields")
    include_header = config.get("include_header", True)

    if not items:
        return {"csv": ""}

    if not fields:
        fields = list(items[0].keys()) if isinstance(items[0], dict) else []

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, delimiter=delimiter, extrasaction="ignore")
    if include_header:
        writer.writeheader()
    for item in items:
        writer.writerow(item if isinstance(item, dict) else {})
    return {"csv": buf.getvalue()}


# ─── from_csv ─────────────────────────────────────────────────────────────────

@register_node("transform.from_csv")
async def transform_from_csv(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Parse CSV string to array of objects."""
    field = config.get("field", "csv")
    csv_str = input_data.get(field) if isinstance(input_data, dict) else input_data
    if not isinstance(csv_str, str):
        raise ValueError(f"transform.from_csv: field '{field}' is not a string")

    delimiter = config.get("delimiter", ",")
    has_header = config.get("has_header", True)

    buf = io.StringIO(csv_str)
    if has_header:
        reader = csv.DictReader(buf, delimiter=delimiter)
        items = [dict(row) for row in reader]
    else:
        reader_plain = csv.reader(buf, delimiter=delimiter)
        items = [row for row in reader_plain]
    return {"items": items, "count": len(items)}


# ─── xml_to_json ──────────────────────────────────────────────────────────────

@register_node("transform.xml_to_json")
async def transform_xml_to_json(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convert XML string to dict."""
    import xmltodict  # already in requirements

    field = config.get("field", "xml")
    xml_str = input_data.get(field) if isinstance(input_data, dict) else input_data
    if not isinstance(xml_str, str):
        raise ValueError(f"transform.xml_to_json: field '{field}' is not a string")
    try:
        parsed = xmltodict.parse(xml_str)
    except Exception as exc:
        raise ValueError(f"transform.xml_to_json: parse error — {exc}") from exc
    output_field = config.get("output_field", "data")
    return {output_field: parsed}


# ─── json_to_xml ──────────────────────────────────────────────────────────────

@register_node("transform.json_to_xml")
async def transform_json_to_xml(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convert dict to XML string."""
    import xmltodict  # already in requirements

    data = config.get("data") or input_data
    root = config.get("root_element", "root")
    try:
        xml_str = xmltodict.unparse({root: data}, pretty=config.get("pretty", True))
    except Exception as exc:
        raise ValueError(f"transform.json_to_xml: serialization error — {exc}") from exc
    return {"xml": xml_str}


# ─── html_to_text ─────────────────────────────────────────────────────────────

@register_node("transform.html_to_text")
async def transform_html_to_text(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Strip HTML tags and extract plain text."""
    from bs4 import BeautifulSoup  # beautifulsoup4 in requirements

    field = config.get("field", "html")
    html_str = input_data.get(field) if isinstance(input_data, dict) else input_data
    if not isinstance(html_str, str):
        raise ValueError(f"transform.html_to_text: field '{field}' is not a string")

    soup = BeautifulSoup(html_str, "html.parser")
    text = soup.get_text(separator=config.get("separator", "\n"), strip=True)
    return {"text": text}


# ─── markdown_to_html ─────────────────────────────────────────────────────────

@register_node("transform.markdown_to_html")
async def transform_markdown_to_html(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Convert Markdown to HTML."""
    from markdown_it import MarkdownIt

    field = config.get("field", "markdown")
    md_str = input_data.get(field) if isinstance(input_data, dict) else input_data
    if not isinstance(md_str, str):
        raise ValueError(f"transform.markdown_to_html: field '{field}' is not a string")
    md = MarkdownIt()
    html = md.render(md_str)
    return {"html": html}


# ─── jmespath ─────────────────────────────────────────────────────────────────

@register_node("transform.jmespath")
async def transform_jmespath(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Apply JMESPath query expression to data."""
    import jmespath  # jmespath in requirements

    expression = config.get("expression")
    if not expression:
        raise ValueError("transform.jmespath: 'expression' is required")
    try:
        result = jmespath.search(expression, input_data)
    except jmespath.exceptions.JMESPathError as exc:
        raise ValueError(f"transform.jmespath: invalid expression — {exc}") from exc
    output_field = config.get("output_field", "result")
    return {output_field: result}


# ─── jsonpath ─────────────────────────────────────────────────────────────────

@register_node("transform.jsonpath")
async def transform_jsonpath(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Apply JSONPath query to data."""
    from jsonpath_ng.ext import parse as jp_parse  # type: ignore

    expression = config.get("expression")
    if not expression:
        raise ValueError("transform.jsonpath: 'expression' is required")
    try:
        jp_expr = jp_parse(expression)
        matches = [m.value for m in jp_expr.find(input_data)]
    except Exception as exc:
        raise ValueError(f"transform.jsonpath: query error — {exc}") from exc
    output_field = config.get("output_field", "result")
    first_only = config.get("first_only", False)
    return {output_field: matches[0] if (first_only and matches) else matches}
