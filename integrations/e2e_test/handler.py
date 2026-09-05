"""E2eTest integration — end-to-end workflow testing assertions."""
import structlog
import httpx

from core.execution_engine import register_node
from oauth.flow import get_credential_data

log = structlog.get_logger(__name__)


@register_node("e2e_test.assert_equals")
async def e2e_assert_equals(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Assert that two values are equal."""
    actual = config.get("actual") if "actual" in config else input_data.get("actual")
    expected = config.get("expected") if "expected" in config else input_data.get("expected")
    message = config.get("message", f"Expected {expected!r} but got {actual!r}")

    log.info("e2e_test.assert_equals", actual=actual, expected=expected)

    if actual != expected:
        raise AssertionError(f"assert_equals failed: {message}. actual={actual!r}, expected={expected!r}")

    return {"passed": True, "actual": actual, "expected": expected}


@register_node("e2e_test.assert_contains")
async def e2e_assert_contains(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Assert that a container value contains the expected item."""
    container = config.get("container") if "container" in config else input_data.get("container")
    item = config.get("item") if "item" in config else input_data.get("item")
    message = config.get("message", f"Expected {container!r} to contain {item!r}")

    log.info("e2e_test.assert_contains", item=item)

    if container is None:
        raise AssertionError(f"assert_contains failed: container is None. {message}")

    if item not in container:
        raise AssertionError(f"assert_contains failed: {message}. {item!r} not found in {container!r}")

    return {"passed": True, "item": item, "container": container}


@register_node("e2e_test.assert_not_empty")
async def e2e_assert_not_empty(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Assert that a value is not empty (not None, not empty string/list/dict)."""
    value = config.get("value") if "value" in config else input_data.get("value")
    message = config.get("message", "Expected value to not be empty")

    log.info("e2e_test.assert_not_empty")

    if value is None or value == "" or value == [] or value == {}:
        raise AssertionError(f"assert_not_empty failed: {message}. Got {value!r}")

    return {"passed": True, "value": value}


@register_node("e2e_test.fail")
async def e2e_fail(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Unconditionally fail the workflow with a message."""
    message = config.get("message") or input_data.get("message", "Test explicitly failed")

    log.info("e2e_test.fail", message=message)
    raise AssertionError(f"e2e_test.fail: {message}")
