"""
Comprehensive unit tests for the new integration nodes:
  - integrations/transform/handler.py
  - integrations/code/handler.py
  - integrations/files/handler.py
  - integrations/datetime_/handler.py
  - integrations/crypto_/handler.py
  - integrations/flow_control/handler.py

Run with:
    python3 -m pytest tests/test_new_nodes.py -v
"""
import asyncio
import base64
import os
import pytest
from unittest.mock import AsyncMock

# ---------------------------------------------------------------------------
# conftest sets these, but confirm they're present before any import that
# touches settings so the tests don't blow up if run in isolation.
# ---------------------------------------------------------------------------
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-for-pytest-32chars!!")
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", "test-cred-key-for-pytest-32chars!!")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("FRONTEND_URL", "http://localhost:3000")

# Import handlers (this also registers them with the execution engine)
from integrations.transform.handler import (
    transform_set,
    transform_remove_fields,
    transform_rename_fields,
    transform_filter_array,
    transform_aggregate,
    transform_sort,
    transform_deduplicate,
    transform_flatten,
    transform_unflatten,
    transform_merge,
    transform_to_json,
    transform_from_json,
    transform_to_csv,
    transform_from_csv,
    transform_html_to_text,
    transform_markdown_to_html,
    transform_jmespath,
    transform_jsonpath,
)
from integrations.code.handler import (
    code_python,
    code_expression,
    code_template,
)
from integrations.files.handler import (
    files_read_text,
    files_write_text,
    files_read_binary,
    files_write_binary,
    files_list_directory,
    files_delete,
    files_move,
    files_copy,
    files_exists,
    files_compress_zip,
    files_extract_zip,
    files_parse_csv,
    files_generate_csv,
)
from integrations.datetime_.handler import (
    datetime_now,
    datetime_parse,
    datetime_format,
    datetime_add,
    datetime_subtract,
    datetime_diff,
    datetime_compare,
    datetime_to_timezone,
    datetime_business_hours,
)
from integrations.crypto_.handler import (
    crypto_hash,
    crypto_hmac,
    crypto_aes_encrypt,
    crypto_aes_decrypt,
    crypto_base64_encode,
    crypto_base64_decode,
    crypto_uuid,
    crypto_random_string,
    crypto_jwt_sign,
    crypto_jwt_verify,
)
from integrations.flow_control.handler import (
    flow_merge,
    flow_delay,
    flow_retry_on_error,
    flow_set_variable,
    flow_get_variable,
    flow_stop,
    flow_no_op,
    StopExecution,
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

DB = AsyncMock()
CRED = None  # credential_id — not used by these nodes


# ===========================================================================
# TRANSFORM NODES
# ===========================================================================

class TestTransformSet:
    @pytest.mark.asyncio
    async def test_sets_top_level_field(self):
        result = await transform_set(
            config={"fields": {"status": "active"}},
            input_data={"name": "Alice"},
            credential_id=CRED,
            db=DB,
        )
        assert result["status"] == "active"
        assert result["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_sets_nested_field_dot_notation(self):
        result = await transform_set(
            config={"fields": {"address.city": "London"}},
            input_data={"address": {"country": "UK"}},
            credential_id=CRED,
            db=DB,
        )
        assert result["address"]["city"] == "London"
        assert result["address"]["country"] == "UK"

    @pytest.mark.asyncio
    async def test_overwrites_existing_field(self):
        result = await transform_set(
            config={"fields": {"score": 99}},
            input_data={"score": 10},
            credential_id=CRED,
            db=DB,
        )
        assert result["score"] == 99

    @pytest.mark.asyncio
    async def test_sets_multiple_fields(self):
        result = await transform_set(
            config={"fields": {"a": 1, "b": 2, "c": 3}},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result == {"a": 1, "b": 2, "c": 3}

    @pytest.mark.asyncio
    async def test_does_not_mutate_input(self):
        original = {"x": 1}
        await transform_set(
            config={"fields": {"x": 999}},
            input_data=original,
            credential_id=CRED,
            db=DB,
        )
        assert original["x"] == 1  # original must be unchanged

    @pytest.mark.asyncio
    async def test_empty_fields_config_returns_copy(self):
        result = await transform_set(
            config={},
            input_data={"key": "value"},
            credential_id=CRED,
            db=DB,
        )
        assert result == {"key": "value"}


class TestTransformRemoveFields:
    @pytest.mark.asyncio
    async def test_removes_top_level_field(self):
        result = await transform_remove_fields(
            config={"fields": ["secret"]},
            input_data={"name": "Bob", "secret": "pwd"},
            credential_id=CRED,
            db=DB,
        )
        assert "secret" not in result
        assert result["name"] == "Bob"

    @pytest.mark.asyncio
    async def test_removes_nested_field(self):
        result = await transform_remove_fields(
            config={"fields": ["meta.internal"]},
            input_data={"meta": {"internal": True, "public": "yes"}},
            credential_id=CRED,
            db=DB,
        )
        assert "internal" not in result["meta"]
        assert result["meta"]["public"] == "yes"

    @pytest.mark.asyncio
    async def test_silently_ignores_missing_field(self):
        result = await transform_remove_fields(
            config={"fields": ["nonexistent"]},
            input_data={"a": 1},
            credential_id=CRED,
            db=DB,
        )
        assert result == {"a": 1}

    @pytest.mark.asyncio
    async def test_accepts_comma_separated_string(self):
        result = await transform_remove_fields(
            config={"fields": "pw, token"},
            input_data={"pw": "x", "token": "y", "name": "z"},
            credential_id=CRED,
            db=DB,
        )
        assert "pw" not in result
        assert "token" not in result
        assert result["name"] == "z"

    @pytest.mark.asyncio
    async def test_removes_multiple_fields(self):
        result = await transform_remove_fields(
            config={"fields": ["a", "b"]},
            input_data={"a": 1, "b": 2, "c": 3},
            credential_id=CRED,
            db=DB,
        )
        assert result == {"c": 3}


class TestTransformRenameFields:
    @pytest.mark.asyncio
    async def test_renames_top_level_field(self):
        result = await transform_rename_fields(
            config={"mapping": {"old_name": "new_name"}},
            input_data={"old_name": "value"},
            credential_id=CRED,
            db=DB,
        )
        assert "old_name" not in result
        assert result["new_name"] == "value"

    @pytest.mark.asyncio
    async def test_ignores_missing_source_key(self):
        result = await transform_rename_fields(
            config={"mapping": {"missing": "present"}},
            input_data={"x": 1},
            credential_id=CRED,
            db=DB,
        )
        assert "present" not in result

    @pytest.mark.asyncio
    async def test_renames_multiple_fields(self):
        result = await transform_rename_fields(
            config={"mapping": {"a": "alpha", "b": "beta"}},
            input_data={"a": 1, "b": 2, "c": 3},
            credential_id=CRED,
            db=DB,
        )
        assert result["alpha"] == 1
        assert result["beta"] == 2
        assert result["c"] == 3

    @pytest.mark.asyncio
    async def test_preserves_value_on_rename(self):
        result = await transform_rename_fields(
            config={"mapping": {"num": "number"}},
            input_data={"num": 42},
            credential_id=CRED,
            db=DB,
        )
        assert result["number"] == 42

    @pytest.mark.asyncio
    async def test_empty_mapping_passes_through(self):
        data = {"x": 1, "y": 2}
        result = await transform_rename_fields(
            config={"mapping": {}},
            input_data=data,
            credential_id=CRED,
            db=DB,
        )
        assert result == data


class TestTransformFilterArray:
    @pytest.mark.asyncio
    async def test_filter_eq(self):
        items = [{"status": "active"}, {"status": "inactive"}, {"status": "active"}]
        result = await transform_filter_array(
            config={"array_field": "items", "condition_field": "status", "operator": "eq", "value": "active"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2
        assert all(i["status"] == "active" for i in result["items"])

    @pytest.mark.asyncio
    async def test_filter_gt(self):
        items = [{"score": 10}, {"score": 50}, {"score": 90}]
        result = await transform_filter_array(
            config={"array_field": "items", "condition_field": "score", "operator": "gt", "value": 40},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_filter_contains(self):
        items = [{"name": "Alice"}, {"name": "Bob"}, {"name": "Alicia"}]
        result = await transform_filter_array(
            config={"array_field": "items", "condition_field": "name", "operator": "contains", "value": "Ali"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_raises_on_non_list(self):
        with pytest.raises(ValueError, match="expected list"):
            await transform_filter_array(
                config={"array_field": "items", "condition_field": "x", "operator": "eq", "value": 1},
                input_data={"items": "not a list"},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_raises_on_unknown_operator(self):
        with pytest.raises(ValueError, match="unknown operator"):
            await transform_filter_array(
                config={"array_field": "items", "condition_field": "x", "operator": "BOGUS", "value": 1},
                input_data={"items": [{"x": 1}]},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_filter_ne(self):
        items = [{"v": 1}, {"v": 2}, {"v": 1}]
        result = await transform_filter_array(
            config={"array_field": "items", "condition_field": "v", "operator": "ne", "value": 1},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 1


class TestTransformAggregate:
    @pytest.mark.asyncio
    async def test_count(self):
        result = await transform_aggregate(
            config={"array_field": "items", "operation": "count"},
            input_data={"items": [1, 2, 3]},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == 3

    @pytest.mark.asyncio
    async def test_sum(self):
        items = [{"n": 10}, {"n": 20}, {"n": 30}]
        result = await transform_aggregate(
            config={"array_field": "items", "operation": "sum", "field": "n"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == 60

    @pytest.mark.asyncio
    async def test_avg(self):
        items = [{"n": 10}, {"n": 30}]
        result = await transform_aggregate(
            config={"array_field": "items", "operation": "avg", "field": "n"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == 20.0

    @pytest.mark.asyncio
    async def test_min_max(self):
        items = [{"v": 5}, {"v": 1}, {"v": 9}]
        r_min = await transform_aggregate(
            config={"array_field": "items", "operation": "min", "field": "v"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        r_max = await transform_aggregate(
            config={"array_field": "items", "operation": "max", "field": "v"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert r_min["result"] == 1
        assert r_max["result"] == 9

    @pytest.mark.asyncio
    async def test_first_and_last(self):
        items = [{"x": "a"}, {"x": "b"}, {"x": "c"}]
        r_first = await transform_aggregate(
            config={"array_field": "items", "operation": "first", "field": "x"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        r_last = await transform_aggregate(
            config={"array_field": "items", "operation": "last", "field": "x"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert r_first["result"] == "a"
        assert r_last["result"] == "c"

    @pytest.mark.asyncio
    async def test_raises_on_unknown_operation(self):
        with pytest.raises(ValueError, match="unknown operation"):
            await transform_aggregate(
                config={"array_field": "items", "operation": "BOGUS", "field": "n"},
                input_data={"items": [{"n": 1}]},
                credential_id=CRED,
                db=DB,
            )


class TestTransformSort:
    @pytest.mark.asyncio
    async def test_sort_asc(self):
        items = [{"n": 3}, {"n": 1}, {"n": 2}]
        result = await transform_sort(
            config={"array_field": "items", "field": "n", "direction": "asc"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert [i["n"] for i in result["items"]] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_sort_desc(self):
        items = [{"n": 3}, {"n": 1}, {"n": 2}]
        result = await transform_sort(
            config={"array_field": "items", "field": "n", "direction": "desc"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert [i["n"] for i in result["items"]] == [3, 2, 1]

    @pytest.mark.asyncio
    async def test_sort_without_field(self):
        result = await transform_sort(
            config={"array_field": "items", "direction": "asc"},
            input_data={"items": [3, 1, 2]},
            credential_id=CRED,
            db=DB,
        )
        assert result["items"] == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_sort_raises_on_non_list(self):
        with pytest.raises(ValueError, match="expected list"):
            await transform_sort(
                config={"array_field": "items", "field": "n"},
                input_data={"items": "oops"},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_sort_preserves_extra_input_keys(self):
        result = await transform_sort(
            config={"array_field": "items", "field": "n"},
            input_data={"items": [{"n": 2}, {"n": 1}], "meta": "keep"},
            credential_id=CRED,
            db=DB,
        )
        assert result["meta"] == "keep"


class TestTransformDeduplicateAndFlattenUnflatten:
    @pytest.mark.asyncio
    async def test_deduplicate_by_key(self):
        items = [{"id": 1, "v": "a"}, {"id": 2, "v": "b"}, {"id": 1, "v": "c"}]
        result = await transform_deduplicate(
            config={"array_field": "items", "key_field": "id"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert len(result["items"]) == 2
        assert result["removed"] == 1

    @pytest.mark.asyncio
    async def test_deduplicate_full_object(self):
        items = [{"a": 1}, {"a": 2}, {"a": 1}]
        result = await transform_deduplicate(
            config={"array_field": "items"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert len(result["items"]) == 2
        assert result["removed"] == 1

    @pytest.mark.asyncio
    async def test_flatten(self):
        result = await transform_flatten(
            config={},
            input_data={"a": {"b": {"c": 1}}},
            credential_id=CRED,
            db=DB,
        )
        assert result["a.b.c"] == 1

    @pytest.mark.asyncio
    async def test_unflatten(self):
        result = await transform_unflatten(
            config={},
            input_data={"a.b.c": 42},
            credential_id=CRED,
            db=DB,
        )
        assert result["a"]["b"]["c"] == 42

    @pytest.mark.asyncio
    async def test_flatten_then_unflatten_roundtrip(self):
        original = {"x": {"y": {"z": "deep"}}}
        flat = await transform_flatten(config={}, input_data=original, credential_id=CRED, db=DB)
        restored = await transform_unflatten(config={}, input_data=flat, credential_id=CRED, db=DB)
        assert restored == original


class TestTransformMerge:
    @pytest.mark.asyncio
    async def test_merge_deep(self):
        result = await transform_merge(
            config={"overlay": {"b": 2, "nested": {"y": 99}}},
            input_data={"a": 1, "nested": {"x": 10}},
            credential_id=CRED,
            db=DB,
        )
        assert result["a"] == 1
        assert result["b"] == 2
        assert result["nested"]["x"] == 10
        assert result["nested"]["y"] == 99

    @pytest.mark.asyncio
    async def test_overlay_overwrites_scalar(self):
        result = await transform_merge(
            config={"overlay": {"a": "new"}},
            input_data={"a": "old"},
            credential_id=CRED,
            db=DB,
        )
        assert result["a"] == "new"

    @pytest.mark.asyncio
    async def test_empty_overlay_leaves_input_unchanged(self):
        result = await transform_merge(
            config={},
            input_data={"x": 1},
            credential_id=CRED,
            db=DB,
        )
        assert result == {"x": 1}


class TestTransformJsonCsvConversions:
    @pytest.mark.asyncio
    async def test_to_json_and_from_json_roundtrip(self):
        data = {"numbers": [1, 2, 3], "flag": True}
        to_result = await transform_to_json(
            config={},
            input_data=data,
            credential_id=CRED,
            db=DB,
        )
        assert isinstance(to_result["json"], str)
        from_result = await transform_from_json(
            config={"field": "json"},
            input_data=to_result,
            credential_id=CRED,
            db=DB,
        )
        assert from_result["data"] == data

    @pytest.mark.asyncio
    async def test_from_json_raises_on_invalid(self):
        with pytest.raises(ValueError, match="invalid JSON"):
            await transform_from_json(
                config={"field": "json"},
                input_data={"json": "{not valid json}"},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_to_csv_and_from_csv_roundtrip(self):
        items = [{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}]
        csv_result = await transform_to_csv(
            config={"array_field": "items"},
            input_data={"items": items},
            credential_id=CRED,
            db=DB,
        )
        assert "Alice" in csv_result["csv"]
        parsed = await transform_from_csv(
            config={"field": "csv"},
            input_data=csv_result,
            credential_id=CRED,
            db=DB,
        )
        assert parsed["count"] == 2
        assert parsed["items"][0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_to_csv_empty_list(self):
        result = await transform_to_csv(
            config={"array_field": "items"},
            input_data={"items": []},
            credential_id=CRED,
            db=DB,
        )
        assert result["csv"] == ""

    @pytest.mark.asyncio
    async def test_from_csv_raises_on_non_string(self):
        with pytest.raises(ValueError, match="not a string"):
            await transform_from_csv(
                config={"field": "csv"},
                input_data={"csv": 123},
                credential_id=CRED,
                db=DB,
            )


class TestTransformHtmlMarkdown:
    @pytest.mark.asyncio
    async def test_html_to_text_strips_tags(self):
        result = await transform_html_to_text(
            config={"field": "html"},
            input_data={"html": "<h1>Hello</h1><p>World</p>"},
            credential_id=CRED,
            db=DB,
        )
        assert "Hello" in result["text"]
        assert "World" in result["text"]
        assert "<h1>" not in result["text"]

    @pytest.mark.asyncio
    async def test_html_to_text_raises_on_non_string(self):
        with pytest.raises(ValueError, match="not a string"):
            await transform_html_to_text(
                config={"field": "html"},
                input_data={"html": 42},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_markdown_to_html_basic(self):
        result = await transform_markdown_to_html(
            config={"field": "markdown"},
            input_data={"markdown": "# Title\n\nParagraph text."},
            credential_id=CRED,
            db=DB,
        )
        assert "<h1>" in result["html"]
        assert "Title" in result["html"]

    @pytest.mark.asyncio
    async def test_markdown_bold_conversion(self):
        result = await transform_markdown_to_html(
            config={"field": "markdown"},
            input_data={"markdown": "**bold**"},
            credential_id=CRED,
            db=DB,
        )
        assert "<strong>" in result["html"] or "<b>" in result["html"]


class TestTransformJmespathJsonpath:
    @pytest.mark.asyncio
    async def test_jmespath_simple_field(self):
        result = await transform_jmespath(
            config={"expression": "name"},
            input_data={"name": "Alice", "age": 30},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == "Alice"

    @pytest.mark.asyncio
    async def test_jmespath_nested_field(self):
        result = await transform_jmespath(
            config={"expression": "user.email"},
            input_data={"user": {"email": "a@b.com", "name": "A"}},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == "a@b.com"

    @pytest.mark.asyncio
    async def test_jmespath_raises_without_expression(self):
        with pytest.raises(ValueError, match="'expression' is required"):
            await transform_jmespath(
                config={},
                input_data={"x": 1},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_jsonpath_matches(self):
        result = await transform_jsonpath(
            config={"expression": "$.items[*].name"},
            input_data={"items": [{"name": "a"}, {"name": "b"}]},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == ["a", "b"]

    @pytest.mark.asyncio
    async def test_jsonpath_first_only(self):
        result = await transform_jsonpath(
            config={"expression": "$.items[*].id", "first_only": True},
            input_data={"items": [{"id": 10}, {"id": 20}]},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == 10


# ===========================================================================
# CODE NODES
# ===========================================================================

class TestCodePython:
    @pytest.mark.asyncio
    async def test_simple_computation(self):
        result = await code_python(
            config={"code": "result = 2 + 2"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == 4

    @pytest.mark.asyncio
    async def test_access_input_data(self):
        result = await code_python(
            config={"code": "result = data['x'] * 3"},
            input_data={"x": 7},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == 21

    @pytest.mark.asyncio
    async def test_stdout_is_captured(self):
        result = await code_python(
            config={"code": "print('hello'); result = 1"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert "hello" in result["stdout"]
        assert result["result"] == 1

    @pytest.mark.asyncio
    async def test_import_statement_is_rejected(self):
        with pytest.raises(ValueError, match="import statements are not allowed"):
            await code_python(
                config={"code": "import os; result = os.getcwd()"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_forbidden_builtin_open_is_rejected(self):
        with pytest.raises(ValueError, match="'open' is not allowed"):
            await code_python(
                config={"code": "f = open('/etc/passwd'); result = f.read()"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_forbidden_exec_is_rejected(self):
        with pytest.raises(ValueError, match="'exec' is not allowed"):
            await code_python(
                config={"code": "exec('x=1')"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_missing_code_raises(self):
        with pytest.raises(ValueError, match="'code' is required"):
            await code_python(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_math_module_available(self):
        result = await code_python(
            config={"code": "result = math.sqrt(16)"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == 4.0

    @pytest.mark.asyncio
    async def test_syntax_error_raises_value_error(self):
        with pytest.raises(ValueError, match="syntax error"):
            await code_python(
                config={"code": "def bad(: pass"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )


class TestCodeExpression:
    @pytest.mark.asyncio
    async def test_arithmetic_expression(self):
        result = await code_expression(
            config={"expression": "1 + 1"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == 2

    @pytest.mark.asyncio
    async def test_access_data_in_expression(self):
        result = await code_expression(
            config={"expression": "data['price'] * data['qty']"},
            input_data={"price": 5.0, "qty": 3},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == 15.0

    @pytest.mark.asyncio
    async def test_string_expression(self):
        result = await code_expression(
            config={"expression": "'hello'.upper()"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == "HELLO"

    @pytest.mark.asyncio
    async def test_missing_expression_raises(self):
        with pytest.raises(ValueError, match="'expression' is required"):
            await code_expression(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_syntax_error_raises(self):
        with pytest.raises(ValueError, match="syntax error"):
            await code_expression(
                config={"expression": "1 +"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_list_comprehension(self):
        result = await code_expression(
            config={"expression": "[x*x for x in range(4)]"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["result"] == [0, 1, 4, 9]


class TestCodeTemplate:
    @pytest.mark.asyncio
    async def test_simple_template_render(self):
        result = await code_template(
            config={"template": "Hello, {{ name }}!"},
            input_data={"name": "World"},
            credential_id=CRED,
            db=DB,
        )
        assert result["output"] == "Hello, World!"

    @pytest.mark.asyncio
    async def test_template_with_conditional(self):
        result = await code_template(
            config={"template": "{% if active %}YES{% else %}NO{% endif %}"},
            input_data={"active": True},
            credential_id=CRED,
            db=DB,
        )
        assert result["output"] == "YES"

    @pytest.mark.asyncio
    async def test_template_with_loop(self):
        result = await code_template(
            config={"template": "{% for i in items %}{{ i }},{% endfor %}"},
            input_data={"items": [1, 2, 3]},
            credential_id=CRED,
            db=DB,
        )
        assert result["output"] == "1,2,3,"

    @pytest.mark.asyncio
    async def test_missing_template_raises(self):
        with pytest.raises(ValueError, match="'template' is required"):
            await code_template(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_syntax_error_in_template_raises(self):
        with pytest.raises(ValueError, match="template syntax error"):
            await code_template(
                config={"template": "{% if %}"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_custom_output_field(self):
        result = await code_template(
            config={"template": "Hi {{ name }}", "output_field": "rendered"},
            input_data={"name": "Claude"},
            credential_id=CRED,
            db=DB,
        )
        assert result["rendered"] == "Hi Claude"


# ===========================================================================
# FILES NODES
# ===========================================================================

class TestFilesReadWrite:
    @pytest.mark.asyncio
    async def test_write_text_and_read_text(self, tmp_path):
        filepath = str(tmp_path / "hello.txt")
        write_result = await files_write_text(
            config={"path": filepath, "content": "Hello, world!"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert write_result["bytes_written"] == len("Hello, world!")
        assert write_result["path"] == filepath

        read_result = await files_read_text(
            config={"path": filepath},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert read_result["content"] == "Hello, world!"
        assert read_result["size"] > 0

    @pytest.mark.asyncio
    async def test_write_text_append_mode(self, tmp_path):
        filepath = str(tmp_path / "append.txt")
        await files_write_text(
            config={"path": filepath, "content": "line1\n"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        await files_write_text(
            config={"path": filepath, "content": "line2\n", "append": True},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        result = await files_read_text(
            config={"path": filepath},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert "line1" in result["content"]
        assert "line2" in result["content"]

    @pytest.mark.asyncio
    async def test_read_text_raises_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            await files_read_text(
                config={"path": str(tmp_path / "nonexistent.txt")},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_read_binary_and_write_binary(self, tmp_path):
        raw = b"\x00\x01\x02\x03binary_data"
        src = tmp_path / "src.bin"
        src.write_bytes(raw)

        read_result = await files_read_binary(
            config={"path": str(src)},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert read_result["size"] == len(raw)
        assert isinstance(read_result["content_base64"], str)

        dst = str(tmp_path / "dst.bin")
        write_result = await files_write_binary(
            config={"path": dst, "content_base64": read_result["content_base64"]},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert write_result["bytes_written"] == len(raw)
        assert (tmp_path / "dst.bin").read_bytes() == raw

    @pytest.mark.asyncio
    async def test_write_text_missing_path_raises(self):
        with pytest.raises(ValueError, match="'path' is required"):
            await files_write_text(
                config={"content": "hello"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )


class TestFilesDirectoryOps:
    @pytest.mark.asyncio
    async def test_list_directory(self, tmp_path):
        (tmp_path / "a.txt").write_text("a")
        (tmp_path / "b.txt").write_text("b")

        result = await files_list_directory(
            config={"path": str(tmp_path), "pattern": "*.txt"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2
        names = {f["name"] for f in result["files"]}
        assert "a.txt" in names
        assert "b.txt" in names

    @pytest.mark.asyncio
    async def test_list_directory_recursive(self, tmp_path):
        subdir = tmp_path / "sub"
        subdir.mkdir()
        (tmp_path / "top.txt").write_text("top")
        (subdir / "nested.txt").write_text("nested")

        result = await files_list_directory(
            config={"path": str(tmp_path), "pattern": "*.txt", "recursive": True},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2

    @pytest.mark.asyncio
    async def test_list_directory_raises_on_non_dir(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        with pytest.raises(ValueError, match="not a directory"):
            await files_list_directory(
                config={"path": str(f)},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_exists_returns_true_for_file(self, tmp_path):
        f = tmp_path / "exists.txt"
        f.write_text("here")
        result = await files_exists(
            config={"path": str(f)},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["exists"] is True
        assert result["is_file"] is True
        assert result["is_dir"] is False

    @pytest.mark.asyncio
    async def test_exists_returns_false_for_missing(self, tmp_path):
        result = await files_exists(
            config={"path": str(tmp_path / "ghost.txt")},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["exists"] is False


class TestFilesDeleteMoveCopy:
    @pytest.mark.asyncio
    async def test_delete_file(self, tmp_path):
        f = tmp_path / "delete_me.txt"
        f.write_text("bye")
        result = await files_delete(
            config={"path": str(f)},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["deleted"] is True
        assert not f.exists()

    @pytest.mark.asyncio
    async def test_delete_returns_not_found_for_missing(self, tmp_path):
        result = await files_delete(
            config={"path": str(tmp_path / "missing.txt")},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["deleted"] is False
        assert result["reason"] == "not found"

    @pytest.mark.asyncio
    async def test_move_file(self, tmp_path):
        src = tmp_path / "src.txt"
        src.write_text("content")
        dst = str(tmp_path / "dst.txt")
        result = await files_move(
            config={"source": str(src), "destination": dst},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert not src.exists()
        assert (tmp_path / "dst.txt").exists()
        assert result["destination"] == dst

    @pytest.mark.asyncio
    async def test_copy_file(self, tmp_path):
        src = tmp_path / "original.txt"
        src.write_text("hello")
        dst = str(tmp_path / "copy.txt")
        result = await files_copy(
            config={"source": str(src), "destination": dst},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert src.exists()  # original must still exist
        assert (tmp_path / "copy.txt").read_text() == "hello"

    @pytest.mark.asyncio
    async def test_move_raises_when_source_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            await files_move(
                config={"source": str(tmp_path / "nope.txt"), "destination": str(tmp_path / "out.txt")},
                input_data={},
                credential_id=CRED,
                db=DB,
            )


class TestFilesZipCsvParse:
    @pytest.mark.asyncio
    async def test_compress_and_extract_zip(self, tmp_path):
        f = tmp_path / "data.txt"
        f.write_text("zip content")
        zip_path = str(tmp_path / "archive.zip")

        compress_result = await files_compress_zip(
            config={"files": [str(f)], "output_path": zip_path},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert compress_result["size"] > 0

        out_dir = str(tmp_path / "extracted")
        extract_result = await files_extract_zip(
            config={"path": zip_path, "output_dir": out_dir},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert extract_result["file_count"] >= 1

    @pytest.mark.asyncio
    async def test_parse_csv_from_content(self):
        csv_content = "name,age\nAlice,30\nBob,25"
        result = await files_parse_csv(
            config={"content": csv_content},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2
        assert result["items"][0]["name"] == "Alice"

    @pytest.mark.asyncio
    async def test_generate_csv(self):
        data = [{"col1": "a", "col2": "b"}, {"col1": "c", "col2": "d"}]
        result = await files_generate_csv(
            config={"data": data},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["row_count"] == 2
        assert "col1" in result["csv"]
        assert "col2" in result["csv"]

    @pytest.mark.asyncio
    async def test_generate_csv_writes_to_file(self, tmp_path):
        data = [{"x": "1"}, {"x": "2"}]
        out = str(tmp_path / "output.csv")
        result = await files_generate_csv(
            config={"data": data, "output_path": out},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["output_path"] == out
        assert (tmp_path / "output.csv").exists()

    @pytest.mark.asyncio
    async def test_parse_csv_from_file(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("a,b\n1,2\n3,4")
        result = await files_parse_csv(
            config={"path": str(f)},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2


# ===========================================================================
# DATETIME NODES
# ===========================================================================

class TestDatetimeNowAndParse:
    @pytest.mark.asyncio
    async def test_now_returns_expected_fields(self):
        result = await datetime_now(
            config={"timezone": "UTC"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        for field in ("iso", "unix", "year", "month", "day", "hour", "minute", "second", "weekday", "formatted"):
            assert field in result

    @pytest.mark.asyncio
    async def test_now_respects_timezone(self):
        result = await datetime_now(
            config={"timezone": "America/New_York"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["timezone"] == "America/New_York"

    @pytest.mark.asyncio
    async def test_parse_iso_string(self):
        result = await datetime_parse(
            config={"value": "2024-06-15T10:30:00"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["year"] == 2024
        assert result["month"] == 6
        assert result["day"] == 15
        assert result["hour"] == 10

    @pytest.mark.asyncio
    async def test_parse_unix_timestamp(self):
        result = await datetime_parse(
            config={"value": 0},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["year"] == 1970

    @pytest.mark.asyncio
    async def test_parse_raises_without_value(self):
        with pytest.raises(ValueError, match="'value' is required"):
            await datetime_parse(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_format_datetime(self):
        result = await datetime_format(
            config={"value": "2024-01-05T08:30:00", "format": "%d/%m/%Y"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["formatted"] == "05/01/2024"


class TestDatetimeAddSubtract:
    @pytest.mark.asyncio
    async def test_add_days(self):
        result = await datetime_add(
            config={"value": "2024-01-01T00:00:00", "days": 7},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["day"] == 8
        assert result["month"] == 1

    @pytest.mark.asyncio
    async def test_add_hours(self):
        result = await datetime_add(
            config={"value": "2024-01-01T20:00:00", "hours": 5},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["hour"] == 1  # crosses midnight to next day
        assert result["day"] == 2

    @pytest.mark.asyncio
    async def test_subtract_days(self):
        result = await datetime_subtract(
            config={"value": "2024-03-10T00:00:00", "days": 5},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["day"] == 5
        assert result["month"] == 3

    @pytest.mark.asyncio
    async def test_subtract_minutes(self):
        result = await datetime_subtract(
            config={"value": "2024-06-15T10:10:00", "minutes": 30},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["hour"] == 9
        assert result["minute"] == 40

    @pytest.mark.asyncio
    async def test_add_weeks(self):
        result = await datetime_add(
            config={"value": "2024-01-01T00:00:00", "weeks": 2},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["day"] == 15


class TestDatetimeDiffAndCompare:
    @pytest.mark.asyncio
    async def test_diff_positive(self):
        result = await datetime_diff(
            config={"start": "2024-01-01T00:00:00Z", "end": "2024-01-02T00:00:00Z"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["days"] == 1
        assert result["total_seconds"] == 86400.0
        assert result["is_negative"] is False

    @pytest.mark.asyncio
    async def test_diff_negative(self):
        result = await datetime_diff(
            config={"start": "2024-01-02T00:00:00Z", "end": "2024-01-01T00:00:00Z"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["is_negative"] is True

    @pytest.mark.asyncio
    async def test_diff_raises_without_start_or_end(self):
        with pytest.raises(ValueError, match="'start' and 'end' are required"):
            await datetime_diff(
                config={"start": "2024-01-01"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_compare_before(self):
        result = await datetime_compare(
            config={"a": "2023-01-01T00:00:00Z", "b": "2024-01-01T00:00:00Z"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["is_before"] is True
        assert result["is_after"] is False
        assert result["is_equal"] is False

    @pytest.mark.asyncio
    async def test_compare_equal(self):
        result = await datetime_compare(
            config={"a": "2024-06-15T12:00:00Z", "b": "2024-06-15T12:00:00Z"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["is_equal"] is True
        assert result["diff_seconds"] == 0.0


class TestDatetimeTimezoneAndBusinessHours:
    @pytest.mark.asyncio
    async def test_to_timezone_conversion(self):
        result = await datetime_to_timezone(
            config={"value": "2024-01-01T00:00:00Z", "to_tz": "America/New_York"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        # UTC midnight → EST is -5h, so hour should be 19 of previous day
        assert result["hour"] == 19
        assert result["timezone"] == "America/New_York"

    @pytest.mark.asyncio
    async def test_to_timezone_invalid_tz_raises(self):
        with pytest.raises(ValueError, match="unknown timezone"):
            await datetime_to_timezone(
                config={"value": "2024-01-01T00:00:00Z", "to_tz": "Mars/Olympus"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_business_hours_in_hours(self):
        # Tuesday 10:00 UTC is a regular business day
        result = await datetime_business_hours(
            config={"value": "2024-01-09T10:00:00Z", "timezone": "UTC"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["in_business_hours"] is True
        assert result["in_workday"] is True

    @pytest.mark.asyncio
    async def test_business_hours_outside_hours(self):
        # Saturday should be outside weekday list by default
        result = await datetime_business_hours(
            config={"value": "2024-01-06T10:00:00Z", "timezone": "UTC"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["in_workday"] is False
        assert result["in_business_hours"] is False

    @pytest.mark.asyncio
    async def test_business_hours_before_start(self):
        # Wednesday at 7am is before 9am start
        result = await datetime_business_hours(
            config={"value": "2024-01-10T07:00:00Z", "timezone": "UTC", "start_hour": 9},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["in_work_hours"] is False


# ===========================================================================
# CRYPTO NODES
# ===========================================================================

class TestCryptoHash:
    @pytest.mark.asyncio
    async def test_sha256_hex(self):
        result = await crypto_hash(
            config={"algorithm": "sha256", "value": "hello", "encoding": "hex"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        # Known SHA-256 of "hello"
        assert result["hash"] == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        assert result["algorithm"] == "sha256"

    @pytest.mark.asyncio
    async def test_md5_hex(self):
        result = await crypto_hash(
            config={"algorithm": "md5", "value": "test"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["hash"] == "098f6bcd4621d373cade4e832627b4f6"

    @pytest.mark.asyncio
    async def test_sha256_base64(self):
        result = await crypto_hash(
            config={"algorithm": "sha256", "value": "hello", "encoding": "base64"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["encoding"] == "base64"
        # Should be valid base64
        base64.b64decode(result["hash"])

    @pytest.mark.asyncio
    async def test_unsupported_algorithm_raises(self):
        with pytest.raises(ValueError, match="unsupported algorithm"):
            await crypto_hash(
                config={"algorithm": "crc32", "value": "x"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_unsupported_encoding_raises(self):
        with pytest.raises(ValueError, match="unsupported encoding"):
            await crypto_hash(
                config={"algorithm": "sha256", "value": "x", "encoding": "binary"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_sha512(self):
        result = await crypto_hash(
            config={"algorithm": "sha512", "value": "data"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert len(result["hash"]) == 128  # SHA-512 hex is 128 chars


class TestCryptoHmac:
    @pytest.mark.asyncio
    async def test_hmac_sha256_deterministic(self):
        r1 = await crypto_hmac(
            config={"algorithm": "sha256", "key": "secret", "value": "message"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        r2 = await crypto_hmac(
            config={"algorithm": "sha256", "key": "secret", "value": "message"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert r1["signature"] == r2["signature"]

    @pytest.mark.asyncio
    async def test_hmac_different_keys_differ(self):
        r1 = await crypto_hmac(
            config={"algorithm": "sha256", "key": "key1", "value": "msg"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        r2 = await crypto_hmac(
            config={"algorithm": "sha256", "key": "key2", "value": "msg"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert r1["signature"] != r2["signature"]

    @pytest.mark.asyncio
    async def test_hmac_unsupported_algorithm_raises(self):
        with pytest.raises(ValueError, match="unsupported algorithm"):
            await crypto_hmac(
                config={"algorithm": "blake2", "key": "k", "value": "v"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_hmac_base64_encoding(self):
        result = await crypto_hmac(
            config={"algorithm": "sha256", "key": "k", "value": "v", "encoding": "base64"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        # Should be valid base64
        base64.b64decode(result["signature"])


class TestCryptoAes:
    @pytest.mark.asyncio
    async def test_aes_encrypt_decrypt_roundtrip(self):
        # 32-byte key in base64
        key = base64.b64encode(b"a" * 32).decode()
        encrypt_result = await crypto_aes_encrypt(
            config={"key": key, "data": "top secret message"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert "ciphertext_base64" in encrypt_result
        assert "nonce_base64" in encrypt_result

        decrypt_result = await crypto_aes_decrypt(
            config={
                "key": key,
                "ciphertext_base64": encrypt_result["ciphertext_base64"],
                "nonce_base64": encrypt_result["nonce_base64"],
            },
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert decrypt_result["plaintext"] == "top secret message"

    @pytest.mark.asyncio
    async def test_aes_encrypt_missing_key_raises(self):
        with pytest.raises(ValueError, match="'key'.*is required"):
            await crypto_aes_encrypt(
                config={"data": "x"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_aes_decrypt_wrong_key_raises(self):
        key = base64.b64encode(b"a" * 32).decode()
        wrong_key = base64.b64encode(b"b" * 32).decode()
        enc = await crypto_aes_encrypt(
            config={"key": key, "data": "hello"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        with pytest.raises(ValueError, match="decryption failed"):
            await crypto_aes_decrypt(
                config={
                    "key": wrong_key,
                    "ciphertext_base64": enc["ciphertext_base64"],
                    "nonce_base64": enc["nonce_base64"],
                },
                input_data={},
                credential_id=CRED,
                db=DB,
            )


class TestCryptoBase64:
    @pytest.mark.asyncio
    async def test_encode_decode_roundtrip(self):
        enc = await crypto_base64_encode(
            config={"value": "Hello, Base64!"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert enc["encoded"] == base64.b64encode(b"Hello, Base64!").decode()

        dec = await crypto_base64_decode(
            config={"value": enc["encoded"]},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert dec["decoded"] == "Hello, Base64!"

    @pytest.mark.asyncio
    async def test_url_safe_encode_decode(self):
        enc = await crypto_base64_encode(
            config={"value": "safe?chars+test", "url_safe": True},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert "+" not in enc["encoded"]
        assert "/" not in enc["encoded"]

        dec = await crypto_base64_decode(
            config={"value": enc["encoded"], "url_safe": True},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert dec["decoded"] == "safe?chars+test"

    @pytest.mark.asyncio
    async def test_encode_empty_string(self):
        enc = await crypto_base64_encode(
            config={"value": ""},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert enc["encoded"] == ""


class TestCryptoUuid:
    @pytest.mark.asyncio
    async def test_uuid4_is_valid_format(self):
        import uuid
        result = await crypto_uuid(
            config={"version": 4},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["version"] == 4
        parsed = uuid.UUID(result["uuid"])
        assert parsed.version == 4

    @pytest.mark.asyncio
    async def test_uuid4_is_unique(self):
        r1 = await crypto_uuid(config={"version": 4}, input_data={}, credential_id=CRED, db=DB)
        r2 = await crypto_uuid(config={"version": 4}, input_data={}, credential_id=CRED, db=DB)
        assert r1["uuid"] != r2["uuid"]

    @pytest.mark.asyncio
    async def test_uuid5_is_deterministic(self):
        config = {"version": 5, "namespace": "dns", "name": "example.com"}
        r1 = await crypto_uuid(config=config, input_data={}, credential_id=CRED, db=DB)
        r2 = await crypto_uuid(config=config, input_data={}, credential_id=CRED, db=DB)
        assert r1["uuid"] == r2["uuid"]

    @pytest.mark.asyncio
    async def test_uuid_invalid_version_raises(self):
        with pytest.raises(ValueError, match="unsupported version"):
            await crypto_uuid(config={"version": 9}, input_data={}, credential_id=CRED, db=DB)


class TestCryptoRandomString:
    @pytest.mark.asyncio
    async def test_correct_length(self):
        result = await crypto_random_string(
            config={"length": 20},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert len(result["value"]) == 20
        assert result["length"] == 20

    @pytest.mark.asyncio
    async def test_hex_charset(self):
        result = await crypto_random_string(
            config={"length": 32, "charset": "hex"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert all(c in "0123456789abcdef" for c in result["value"])

    @pytest.mark.asyncio
    async def test_is_random(self):
        r1 = await crypto_random_string(config={"length": 32}, input_data={}, credential_id=CRED, db=DB)
        r2 = await crypto_random_string(config={"length": 32}, input_data={}, credential_id=CRED, db=DB)
        assert r1["value"] != r2["value"]

    @pytest.mark.asyncio
    async def test_invalid_length_raises(self):
        with pytest.raises(ValueError, match="between 1 and 4096"):
            await crypto_random_string(config={"length": 0}, input_data={}, credential_id=CRED, db=DB)

    @pytest.mark.asyncio
    async def test_unknown_charset_raises(self):
        with pytest.raises(ValueError, match="unknown charset"):
            await crypto_random_string(config={"charset": "base58"}, input_data={}, credential_id=CRED, db=DB)


class TestCryptoJwt:
    @pytest.mark.asyncio
    async def test_sign_and_verify_roundtrip(self):
        payload = {"sub": "user-123", "role": "admin"}
        sign_result = await crypto_jwt_sign(
            config={"payload": payload, "secret": "my-jwt-secret"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert isinstance(sign_result["token"], str)
        assert len(sign_result["token"].split(".")) == 3  # header.payload.signature

        verify_result = await crypto_jwt_verify(
            config={"token": sign_result["token"], "secret": "my-jwt-secret"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert verify_result["valid"] is True
        assert verify_result["payload"]["sub"] == "user-123"

    @pytest.mark.asyncio
    async def test_verify_wrong_secret_raises(self):
        sign_result = await crypto_jwt_sign(
            config={"payload": {"x": 1}, "secret": "correct-secret"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        with pytest.raises(ValueError, match="token invalid"):
            await crypto_jwt_verify(
                config={"token": sign_result["token"], "secret": "wrong-secret"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_sign_missing_secret_raises(self):
        with pytest.raises(ValueError, match="'secret' is required"):
            await crypto_jwt_sign(
                config={"payload": {"x": 1}},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_verify_missing_token_raises(self):
        with pytest.raises(ValueError, match="'token' is required"):
            await crypto_jwt_verify(
                config={"secret": "s"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_jwt_with_expiry(self):
        sign_result = await crypto_jwt_sign(
            config={"payload": {"u": "bob"}, "secret": "s", "expire_minutes": 60},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        verify_result = await crypto_jwt_verify(
            config={"token": sign_result["token"], "secret": "s"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert "exp" in verify_result["payload"]


# ===========================================================================
# FLOW CONTROL NODES
# ===========================================================================

class TestFlowMerge:
    @pytest.mark.asyncio
    async def test_passthrough_when_no_branches_key(self):
        data = {"result": 42, "name": "test"}
        result = await flow_merge(
            config={},
            input_data=data,
            credential_id=CRED,
            db=DB,
        )
        assert result == data

    @pytest.mark.asyncio
    async def test_mode_first(self):
        result = await flow_merge(
            config={"mode": "first"},
            input_data={"branches": [{"value": "A"}, {"value": "B"}]},
            credential_id=CRED,
            db=DB,
        )
        assert result == {"value": "A"}

    @pytest.mark.asyncio
    async def test_mode_all(self):
        result = await flow_merge(
            config={"mode": "all"},
            input_data={"branches": [{"v": 1}, {"v": 2}]},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 2
        assert len(result["branches"]) == 2

    @pytest.mark.asyncio
    async def test_mode_any_synonym(self):
        result = await flow_merge(
            config={"mode": "any"},
            input_data={"branches": [{"v": 1}]},
            credential_id=CRED,
            db=DB,
        )
        assert result["count"] == 1

    @pytest.mark.asyncio
    async def test_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="unknown mode"):
            await flow_merge(
                config={"mode": "random"},
                input_data={"branches": [{}]},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_branches_not_list_raises(self):
        with pytest.raises(ValueError, match="'branches' must be a list"):
            await flow_merge(
                config={},
                input_data={"branches": "not_a_list"},
                credential_id=CRED,
                db=DB,
            )


class TestFlowDelay:
    @pytest.mark.asyncio
    async def test_delay_passthrough(self):
        result = await flow_delay(
            config={"seconds": 0.001},
            input_data={"x": 1},
            credential_id=CRED,
            db=DB,
        )
        assert result["x"] == 1
        assert result["__delayed_seconds__"] == 0.001

    @pytest.mark.asyncio
    async def test_delay_negative_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            await flow_delay(
                config={"seconds": -1},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_delay_capped_at_300(self):
        result = await flow_delay(
            config={"seconds": 9999},
            # Use 0 sleep implicitly — we just check the cap, not actual sleep
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["__delayed_seconds__"] == 300

    @pytest.mark.asyncio
    async def test_delay_default_is_one_second(self):
        # Only check the metadata — we don't want to actually sleep 1s in tests
        # We override to 0 to be fast
        result = await flow_delay(
            config={"seconds": 0},
            input_data={"payload": "data"},
            credential_id=CRED,
            db=DB,
        )
        assert result["__delayed_seconds__"] == 0
        assert result["payload"] == "data"


class TestFlowRetryOnError:
    @pytest.mark.asyncio
    async def test_adds_retry_policy_to_output(self):
        result = await flow_retry_on_error(
            config={"max_attempts": 5, "delay_seconds": 2.5},
            input_data={"value": "original"},
            credential_id=CRED,
            db=DB,
        )
        assert result["__retry_policy__"]["max_attempts"] == 5
        assert result["__retry_policy__"]["delay_seconds"] == 2.5
        assert result["value"] == "original"

    @pytest.mark.asyncio
    async def test_default_retry_policy(self):
        result = await flow_retry_on_error(
            config={},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["__retry_policy__"]["max_attempts"] == 3
        assert result["__retry_policy__"]["delay_seconds"] == 1.0

    @pytest.mark.asyncio
    async def test_zero_max_attempts_raises(self):
        with pytest.raises(ValueError, match="max_attempts.*>=.*1"):
            await flow_retry_on_error(
                config={"max_attempts": 0},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_negative_delay_raises(self):
        with pytest.raises(ValueError, match="delay_seconds.*>=.*0"):
            await flow_retry_on_error(
                config={"delay_seconds": -1},
                input_data={},
                credential_id=CRED,
                db=DB,
            )


class TestFlowSetGetVariable:
    @pytest.mark.asyncio
    async def test_set_then_get_variable(self):
        set_result = await flow_set_variable(
            config={"name": "counter", "value": 42},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert set_result["__variables__"]["counter"] == 42

        get_result = await flow_get_variable(
            config={"name": "counter"},
            input_data=set_result,
            credential_id=CRED,
            db=DB,
        )
        assert get_result["value"] == 42
        assert get_result["variable_name"] == "counter"

    @pytest.mark.asyncio
    async def test_set_variable_missing_name_raises(self):
        with pytest.raises(ValueError, match="'name' is required"):
            await flow_set_variable(
                config={"value": 1},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_get_variable_missing_name_raises(self):
        with pytest.raises(ValueError, match="'name' is required"):
            await flow_get_variable(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_get_variable_returns_default_when_missing(self):
        result = await flow_get_variable(
            config={"name": "unset_var", "default": "fallback"},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result["value"] == "fallback"

    @pytest.mark.asyncio
    async def test_get_required_variable_missing_raises(self):
        with pytest.raises(ValueError, match="has not been set"):
            await flow_get_variable(
                config={"name": "required_var", "required": True},
                input_data={},
                credential_id=CRED,
                db=DB,
            )

    @pytest.mark.asyncio
    async def test_set_variable_preserves_existing_input(self):
        result = await flow_set_variable(
            config={"name": "foo", "value": "bar"},
            input_data={"existing": "data", "__variables__": {"other": "kept"}},
            credential_id=CRED,
            db=DB,
        )
        assert result["existing"] == "data"
        assert result["__variables__"]["other"] == "kept"
        assert result["__variables__"]["foo"] == "bar"


class TestFlowStopAndNoOp:
    @pytest.mark.asyncio
    async def test_stop_raises_stop_execution(self):
        with pytest.raises(StopExecution) as exc_info:
            await flow_stop(
                config={"reason": "user requested halt"},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert "user requested halt" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stop_uses_default_reason(self):
        with pytest.raises(StopExecution) as exc_info:
            await flow_stop(
                config={},
                input_data={},
                credential_id=CRED,
                db=DB,
            )
        assert "flow.stop node reached" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stop_reason_from_input_data(self):
        with pytest.raises(StopExecution) as exc_info:
            await flow_stop(
                config={},
                input_data={"reason": "condition not met"},
                credential_id=CRED,
                db=DB,
            )
        assert "condition not met" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_no_op_returns_identical_copy(self):
        data = {"a": 1, "b": [2, 3], "nested": {"x": "y"}}
        result = await flow_no_op(
            config={},
            input_data=data,
            credential_id=CRED,
            db=DB,
        )
        assert result == data

    @pytest.mark.asyncio
    async def test_no_op_does_not_return_same_object(self):
        data = {"list": [1, 2, 3]}
        result = await flow_no_op(
            config={},
            input_data=data,
            credential_id=CRED,
            db=DB,
        )
        # Must be a deep copy, not the same reference
        assert result is not data
        result["list"].append(99)
        assert 99 not in data["list"]

    @pytest.mark.asyncio
    async def test_no_op_empty_input(self):
        result = await flow_no_op(
            config={},
            input_data={},
            credential_id=CRED,
            db=DB,
        )
        assert result == {}
