"""
Simulate integration — simulate node execution for testing.

No credentials required.

Nodes:
  - simulate.delay      : Sleep for N milliseconds.
  - simulate.error      : Raise a RuntimeError with a configurable message.
  - simulate.random_data: Generate random test data.
"""
import asyncio
import random
import string
import structlog

from core.execution_engine import register_node

log = structlog.get_logger(__name__)


def _random_string(length: int = 8) -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))


def _random_email() -> str:
    return f"{_random_string(6)}@{_random_string(5)}.com"


@register_node("simulate.delay")
async def simulate_delay(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Sleep for a configurable number of milliseconds, then pass input_data through.

    Config keys:
      delay_ms (int): milliseconds to sleep (default 1000, max 30000)
    """
    delay_ms = int(config.get("delay_ms") or input_data.get("delay_ms", 1000))
    delay_ms = max(0, min(delay_ms, 30_000))  # clamp 0–30 000 ms

    log.info("simulate.delay", delay_ms=delay_ms)
    await asyncio.sleep(delay_ms / 1000.0)
    return {"delayed_ms": delay_ms, **input_data}


@register_node("simulate.error")
async def simulate_error(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Raise a RuntimeError to test error-handling paths.

    Config keys:
      message (str): Error message to include (default: 'Simulated error')
    """
    message = config.get("message") or input_data.get("message", "Simulated error")
    log.info("simulate.error", message=message)
    raise RuntimeError(message)


@register_node("simulate.random_data")
async def simulate_random_data(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """
    Generate a dict of random test data for pipeline testing.

    Config keys:
      count     (int) : Number of records to generate (default 1, max 100)
      seed      (int) : Optional random seed for reproducibility
      fields    (list): Optional list of field names to include.
                        Supported: id, name, email, age, score, active, tags.
                        Defaults to all fields.
    """
    count = max(1, min(int(config.get("count") or input_data.get("count", 1)), 100))
    seed = config.get("seed") or input_data.get("seed")
    requested_fields = config.get("fields") or input_data.get("fields") or []

    if seed is not None:
        random.seed(int(seed))

    _all_fields = {"id", "name", "email", "age", "score", "active", "tags"}
    use_fields = set(requested_fields) & _all_fields if requested_fields else _all_fields

    records = []
    for i in range(count):
        record: dict = {}
        if "id" in use_fields:
            record["id"] = f"{_random_string(8)}-{i}"
        if "name" in use_fields:
            record["name"] = f"{_random_string(5).capitalize()} {_random_string(6).capitalize()}"
        if "email" in use_fields:
            record["email"] = _random_email()
        if "age" in use_fields:
            record["age"] = random.randint(18, 90)
        if "score" in use_fields:
            record["score"] = round(random.uniform(0, 100), 2)
        if "active" in use_fields:
            record["active"] = random.choice([True, False])
        if "tags" in use_fields:
            tag_count = random.randint(1, 4)
            record["tags"] = [_random_string(5) for _ in range(tag_count)]
        records.append(record)

    log.info("simulate.random_data", count=count, fields=list(use_fields))
    return {"records": records, "count": len(records)}
