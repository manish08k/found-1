"""
Integration SDK — IntegrationGenerator.

Generates Python integration class code from an OpenAPI 3.x specification.

IMPORTANT REVIEW WARNING: Generated code is a starting point only.
It requires careful human review before being used in production:
- Auth schemes are approximated from securitySchemes; verify correctness.
- Request/response handling may need provider-specific adjustments.
- Error messages and field mappings are generic.
- Rate limits, pagination, and retry behaviour are not inferred.

Usage::

    import yaml
    from integrations.sdk.generator import IntegrationGenerator

    with open("openapi.yaml") as f:
        spec = yaml.safe_load(f)

    code = IntegrationGenerator.from_openapi(spec)
    print(code)
    # or write to disk:
    with open("integrations/myapp/handler.py", "w") as f:
        f.write(code)
"""
from __future__ import annotations

import keyword
import re
import textwrap
from typing import Any


class IntegrationGenerator:
    """
    Generates a ``BaseIntegration`` subclass from an OpenAPI 3.x spec dict.

    All methods are static — the class is a namespace, not intended to be
    instantiated.
    """

    @staticmethod
    def from_openapi(spec_dict: dict) -> str:
        """
        Parse an OpenAPI 3.x spec and generate Python integration code.

        Parameters
        ----------
        spec_dict:
            A parsed OpenAPI spec dict (from ``yaml.safe_load`` or
            ``json.load``).

        Returns
        -------
        str
            Valid Python source code for a ``BaseIntegration`` subclass.
            Write it to ``integrations/<name>/handler.py``.
        """
        info = spec_dict.get("info", {})
        title = info.get("title", "MyIntegration")
        description = info.get("description", "")
        version = info.get("version", "")
        servers = spec_dict.get("servers", [])
        base_url = servers[0].get("url", "") if servers else ""

        class_name = _to_class_name(title)
        integration_name = _to_snake(title).replace("_", "-")

        # Parse security schemes → credential fields
        security_schemes = spec_dict.get("components", {}).get("securitySchemes", {})
        credential_fields, auth_type, auth_details = _parse_security_schemes(security_schemes)

        # Parse paths → operations
        paths = spec_dict.get("paths", {})
        operations = _parse_paths(paths, integration_name)

        # Render
        return _render_integration(
            class_name=class_name,
            integration_name=integration_name,
            display_name=title,
            description=description,
            base_url=base_url,
            credential_fields=credential_fields,
            auth_type=auth_type,
            auth_details=auth_details,
            operations=operations,
            openapi_version=spec_dict.get("openapi", "3.0.0"),
            api_version=version,
        )


# ── Internal helpers ───────────────────────────────────────────────────────────

def _to_class_name(name: str) -> str:
    """Convert a human name to a PascalCase class name."""
    parts = re.sub(r"[^a-zA-Z0-9 ]", " ", name).split()
    result = "".join(p.capitalize() for p in parts)
    if not result or not result[0].isalpha():
        result = "Integration" + result
    return result + "Integration" if not result.endswith("Integration") else result


def _to_snake(name: str) -> str:
    """Convert a human name to snake_case."""
    name = re.sub(r"[^a-zA-Z0-9]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    return name or "integration"


def _to_method_name(operation_id: str, method: str, path: str) -> str:
    """
    Derive a valid Python method name from an operationId or method+path.
    Falls back to method + path segments if operationId is absent.
    """
    if operation_id:
        name = re.sub(r"[^a-zA-Z0-9_]", "_", operation_id)
    else:
        parts = [method] + [p for p in path.split("/") if p and not p.startswith("{")]
        name = "_".join(parts)
    name = re.sub(r"_+", "_", name).strip("_").lower()
    if keyword.iskeyword(name):
        name = name + "_"
    return name or "handle"


def _parse_security_schemes(
    schemes: dict,
) -> tuple[list[dict], str, dict]:
    """
    Derive credential fields and auth type from OpenAPI securitySchemes.

    Returns (credential_fields, auth_type, auth_details).
    auth_type is one of: "apikey_header", "apikey_query", "bearer", "basic", "oauth2", "none"
    """
    if not schemes:
        return [], "none", {}

    # Take the first scheme as the primary auth
    first_name, first_scheme = next(iter(schemes.items()))
    scheme_type = first_scheme.get("type", "").lower()

    if scheme_type == "apikey":
        location = first_scheme.get("in", "header")
        param_name = first_scheme.get("name", "X-API-Key")
        if location == "header":
            return (
                [{"name": "api_key", "label": "API Key", "type": "password", "help_text": f"Sent as {param_name} header."}],
                "apikey_header",
                {"header_name": param_name},
            )
        else:
            return (
                [{"name": "api_key", "label": "API Key", "type": "password", "help_text": f"Sent as ?{param_name}= query param."}],
                "apikey_query",
                {"param_name": param_name},
            )

    if scheme_type == "http":
        http_scheme = first_scheme.get("scheme", "").lower()
        if http_scheme == "bearer":
            return (
                [{"name": "access_token", "label": "Access Token", "type": "password", "help_text": "Bearer token."}],
                "bearer",
                {},
            )
        if http_scheme == "basic":
            return (
                [
                    {"name": "username", "label": "Username", "type": "text", "help_text": "Basic auth username."},
                    {"name": "password", "label": "Password", "type": "password", "help_text": "Basic auth password."},
                ],
                "basic",
                {},
            )

    if scheme_type == "oauth2":
        flows = first_scheme.get("flows", {})
        scopes_list: list[str] = []
        for flow_data in flows.values():
            scopes_list.extend(flow_data.get("scopes", {}).keys())
        return (
            [
                {"name": "access_token", "label": "OAuth Access Token", "type": "password", "help_text": "OAuth 2.0 access token."},
                {"name": "client_id", "label": "Client ID", "type": "text", "required": False, "help_text": "OAuth client ID."},
                {"name": "client_secret", "label": "Client Secret", "type": "password", "required": False, "help_text": "OAuth client secret."},
            ],
            "oauth2",
            {"scopes": scopes_list},
        )

    # Unknown/unsupported scheme
    return (
        [{"name": "api_key", "label": "API Key", "type": "password", "help_text": f"Credential for {first_name}."}],
        "none",
        {},
    )


def _parse_paths(paths: dict, integration_name: str) -> list[dict]:
    """Extract operation metadata from OpenAPI paths."""
    ops = []
    for path, path_item in paths.items():
        for http_method in ("get", "post", "put", "patch", "delete"):
            op = path_item.get(http_method)
            if op is None:
                continue

            operation_id = op.get("operationId", "")
            method_name = _to_method_name(operation_id, http_method, path)
            node_type = f"{integration_name}.{method_name}"
            label = op.get("summary") or operation_id or f"{http_method.upper()} {path}"
            description = op.get("description") or op.get("summary") or ""

            # Build input schema from parameters + request body
            input_schema = {}
            for param in op.get("parameters", []):
                pname = param.get("name", "")
                pschema = param.get("schema", {})
                input_schema[pname] = {
                    "type": pschema.get("type", "string"),
                    "required": param.get("required", False),
                    "description": param.get("description", ""),
                    "location": param.get("in", "query"),
                }

            req_body = op.get("requestBody", {})
            if req_body:
                for media_type, media_obj in req_body.get("content", {}).items():
                    if "json" in media_type:
                        body_schema = media_obj.get("schema", {})
                        props = body_schema.get("properties", {})
                        required_props = body_schema.get("required", [])
                        for prop_name, prop_schema in props.items():
                            input_schema[prop_name] = {
                                "type": prop_schema.get("type", "string"),
                                "required": prop_name in required_props,
                                "description": prop_schema.get("description", ""),
                                "location": "body",
                            }
                        break

            # Build output schema from 200/201 response
            output_schema = {}
            responses = op.get("responses", {})
            for status in ("200", "201", "202"):
                resp = responses.get(status)
                if resp:
                    for media_type, media_obj in resp.get("content", {}).items():
                        if "json" in media_type:
                            resp_schema = media_obj.get("schema", {})
                            props = resp_schema.get("properties", {})
                            for prop_name, prop_schema in props.items():
                                output_schema[prop_name] = {
                                    "type": prop_schema.get("type", "string"),
                                    "description": prop_schema.get("description", ""),
                                }
                            break
                    break

            # Extract path params
            path_params = re.findall(r"\{([^}]+)\}", path)

            ops.append({
                "method_name": method_name,
                "node_type": node_type,
                "label": label,
                "description": description,
                "http_method": http_method.upper(),
                "path": path,
                "path_params": path_params,
                "input_schema": input_schema,
                "output_schema": output_schema,
            })
    return ops


def _render_credential_fields(fields: list[dict]) -> str:
    """Render the credential_fields list literal."""
    if not fields:
        return "    credential_fields: list[CredentialField] = []"

    lines = ["    credential_fields = ["]
    for f in fields:
        req = f.get("required", True)
        ftype = f.get("type", "text")
        help_text = f.get("help_text", "")
        lines.append(
            f'        CredentialField({f["name"]!r}, {f["label"]!r}, '
            f'type={ftype!r}, required={req}, help_text={help_text!r}),'
        )
    lines.append("    ]")
    return "\n".join(lines)


def _render_get_headers(auth_type: str, auth_details: dict) -> str:
    """Render the get_headers() method."""
    if auth_type == "apikey_header":
        header = auth_details.get("header_name", "X-API-Key")
        return textwrap.dedent(f"""\
            def get_headers(self, credential: dict) -> dict:
                return {{{header!r}: credential.get("api_key", "")}}
        """)
    if auth_type == "bearer":
        return textwrap.dedent("""\
            def get_headers(self, credential: dict) -> dict:
                return {"Authorization": f"Bearer {credential.get('access_token', '')}"}
        """)
    if auth_type == "oauth2":
        return textwrap.dedent("""\
            def get_headers(self, credential: dict) -> dict:
                return {"Authorization": f"Bearer {credential.get('access_token', '')}"}
        """)
    if auth_type == "basic":
        return textwrap.dedent("""\
            def get_headers(self, credential: dict) -> dict:
                import base64
                creds = f"{credential.get('username', '')}:{credential.get('password', '')}"
                encoded = base64.b64encode(creds.encode()).decode()
                return {"Authorization": f"Basic {encoded}"}
        """)
    if auth_type == "apikey_query":
        param = auth_details.get("param_name", "api_key")
        return textwrap.dedent(f"""\
            def get_headers(self, credential: dict) -> dict:
                # NOTE: This API uses query-param auth ({param}=...).
                # The key is injected per-request via QueryParamAuth; headers are empty.
                return {{}}
        """)
    return textwrap.dedent("""\
        def get_headers(self, credential: dict) -> dict:
            # TODO: implement auth header logic
            return {}
    """)


def _render_operation(op: dict) -> str:
    """Render a single operation method."""
    method_name = op["method_name"]
    node_type = op["node_type"]
    label = op["label"]
    description = op["description"]
    http_method = op["http_method"]
    path = op["path"]
    path_params = op["path_params"]
    input_schema = op["input_schema"]

    # Build param-extraction snippet
    param_lines = []
    for pname, pmeta in input_schema.items():
        location = pmeta.get("location", "query")
        if location in ("query", "header", "path"):
            snake = _to_snake(pname)
            param_lines.append(
                f'    {snake} = config.get({pname!r}) or input_data.get({pname!r})'
            )

    # Build path with substitutions
    rendered_path = path
    for pp in path_params:
        snake = _to_snake(pp)
        rendered_path = rendered_path.replace(f"{{{pp}}}", f"{{{snake}}}")

    # Build request call
    body_fields = [
        pname for pname, pmeta in input_schema.items()
        if pmeta.get("location") == "body"
    ]
    query_fields = [
        pname for pname, pmeta in input_schema.items()
        if pmeta.get("location") in ("query", None)
        and pname not in path_params
    ]

    request_kwargs = []
    if query_fields:
        query_dict = "{" + ", ".join(f'{p!r}: {_to_snake(p)}' for p in query_fields) + "}"
        request_kwargs.append(f"params={query_dict}")
    if body_fields:
        body_dict = "{" + ", ".join(f'{p!r}: {_to_snake(p)}' for p in body_fields) + "}"
        request_kwargs.append(f"json={body_dict}")

    kwargs_str = ", ".join(request_kwargs)

    lines = [
        f'    @operation(',
        f'        {node_type!r},',
        f'        label={label!r},',
        f'        description={description!r},',
        f'    )',
        f'    async def {method_name}(self, config: dict, input_data: dict, credential_id: str, db) -> dict:',
        f'        credential = await self._load_credential(credential_id, db)',
        f'        async with self.build_client(credential) as client:',
    ]

    if param_lines:
        # Extract params
        for pl in param_lines:
            lines.append("        " + pl)

    request_line = f'            return await client.{http_method.lower()}(f{rendered_path!r}'
    if kwargs_str:
        request_line += f", {kwargs_str}"
    request_line += ")"
    lines.append(request_line)

    return "\n".join(lines)


def _render_integration(
    *,
    class_name: str,
    integration_name: str,
    display_name: str,
    description: str,
    base_url: str,
    credential_fields: list[dict],
    auth_type: str,
    auth_details: dict,
    operations: list[dict],
    openapi_version: str,
    api_version: str,
) -> str:
    """Assemble the full generated Python file."""
    cred_fields_str = _render_credential_fields(credential_fields)
    # Indent the get_headers block by 4 spaces so it sits correctly inside
    # the class body when embedded in the f-string template below.
    _raw_headers = _render_get_headers(auth_type, auth_details)
    get_headers_str = textwrap.indent(_raw_headers.rstrip(), "    ")

    op_methods = "\n\n".join(_render_operation(op) for op in operations) if operations else (
        "    # No operations were parsed from the OpenAPI spec.\n"
        "    # Add operation methods decorated with @operation here."
    )

    auth_import = ""
    if auth_type == "apikey_query":
        auth_import = "\nfrom integrations.sdk.auth import QueryParamAuth"

    total_ops = len(operations)

    return f'''\
# ============================================================================
# AUTO-GENERATED INTEGRATION: {display_name}
# Generated by integrations.sdk.generator from OpenAPI {openapi_version}
# API Version: {api_version}
#
# WARNING: This file was generated and requires human review before use.
# - Verify authentication logic in get_headers()
# - Check request parameters match the actual API docs
# - Add proper pagination for list endpoints
# - Add input validation where required
# - Review error handling for provider-specific responses
# - This file is NOT production-ready without review
# ============================================================================
"""
{display_name} integration — auto-generated from OpenAPI spec.

Generated {total_ops} operation(s). Review each method before use.
"""
from integrations.sdk.base import BaseIntegration, CredentialField
from integrations.sdk.decorators import operation, trigger{auth_import}


class {class_name}(BaseIntegration):
    name = {integration_name!r}
    display_name = {display_name!r}
    description = {description[:200]!r}
    icon = ""  # TODO: add icon URL or identifier
    category = ""  # TODO: set category (e.g. "CRM", "Payments")
    base_url = {base_url!r}

{cred_fields_str}

{get_headers_str}

    async def test_credential(self, credential: dict) -> bool:
        # TODO: replace with a real lightweight read-only API call
        async with self.build_client(credential) as client:
            try:
                await client.get("/")
                return True
            except Exception:
                return False

{op_methods}


# Register all operations with the execution engine at import time.
# This line must remain at the bottom of the file.
{_to_snake(display_name)}_integration = {class_name}()
{_to_snake(display_name)}_integration.register_all()
'''
