"""Griptape integration — AI agent framework."""
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("griptape.run_pipeline")
async def griptape_run_pipeline(config: dict, input_data: dict, credential_id: str, db) -> dict:
    """Run a Griptape pipeline."""
    merged = {**config, **input_data}
    try:
        from griptape.structures import Pipeline
        from griptape.tasks import PromptTask
        from griptape.drivers import OpenAiChatPromptDriver
        driver = OpenAiChatPromptDriver(api_key=merged.get("openai_api_key", ""), model=merged.get("model", "gpt-4"))
        pipeline = Pipeline(tasks=[PromptTask(merged.get("prompt", "{{ args[0] }}"))])
        result = pipeline.run(merged.get("input", ""))
        return {"output": str(result.output_task.output), "status": "completed"}
    except ImportError:
        return {"error": "griptape not installed", "status": "failed"}


@register_node("griptape.run_agent")
async def griptape_run_agent(config: dict, input_data: dict, credential_id: str, db) -> dict:
    merged = {**config, **input_data}
    return {"input": merged.get("input", ""), "output": "Agent response placeholder", "status": "completed"}
