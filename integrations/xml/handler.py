"""XML integration — convert between XML strings and Python dicts."""
import xml.etree.ElementTree as ET
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _elem_to_dict(elem: ET.Element) -> dict:
    """Recursively convert an ElementTree Element to a dict."""
    d: dict = {}
    if elem.attrib:
        d["@attributes"] = dict(elem.attrib)
    children = list(elem)
    if children:
        child_dict: dict = {}
        for child in children:
            child_data = _elem_to_dict(child)
            if child.tag in child_dict:
                if not isinstance(child_dict[child.tag], list):
                    child_dict[child.tag] = [child_dict[child.tag]]
                child_dict[child.tag].append(child_data)
            else:
                child_dict[child.tag] = child_data
        d.update(child_dict)
    else:
        if elem.text and elem.text.strip():
            d["#text"] = elem.text.strip()
    return d


def _dict_to_elem(tag: str, data) -> ET.Element:
    """Recursively convert a dict (or scalar) to an ElementTree Element."""
    elem = ET.Element(tag)
    if isinstance(data, dict):
        attrs = data.get("@attributes", {})
        for k, v in attrs.items():
            elem.set(k, str(v))
        for key, value in data.items():
            if key in ("@attributes", "#text"):
                continue
            if isinstance(value, list):
                for item in value:
                    elem.append(_dict_to_elem(key, item))
            else:
                elem.append(_dict_to_elem(key, value))
        if "#text" in data:
            elem.text = str(data["#text"])
    elif data is not None:
        elem.text = str(data)
    return elem


@register_node("xml.to_json")
async def xml_to_json(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Convert an XML string to a Python dict.

    config / input_data:
      xml_string — the XML string to parse (config takes precedence, falls back to input_data["xml"])
    """
    merged = {**config, **input_data}
    xml_string = merged.get("xml_string") or merged.get("xml")
    if not xml_string:
        raise ValueError("xml_string (or input_data['xml']) is required for xml.to_json")

    root = ET.fromstring(xml_string)
    converted = {root.tag: _elem_to_dict(root)}

    log.info("xml.to_json", root_tag=root.tag)
    return {"json": converted}


@register_node("xml.to_xml")
async def xml_to_xml(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Convert a Python dict to an XML string.

    config / input_data:
      json_data — the dict to convert (config takes precedence, falls back to input_data["json"])
    """
    merged = {**config, **input_data}
    json_data = merged.get("json_data") or merged.get("json")
    if not json_data:
        raise ValueError("json_data (or input_data['json']) is required for xml.to_xml")

    if not isinstance(json_data, dict) or len(json_data) != 1:
        raise ValueError("json_data must be a dict with exactly one root key for xml.to_xml")

    root_tag = next(iter(json_data))
    root_elem = _dict_to_elem(root_tag, json_data[root_tag])
    xml_string = ET.tostring(root_elem, encoding="unicode")

    log.info("xml.to_xml", root_tag=root_tag)
    return {"xml": xml_string}
