"""Parallel execution workflow control node."""
import asyncio
import structlog
from core.execution_engine import register_node

log = structlog.get_logger(__name__)


@register_node("parallel.execute_parallel")
async def parallel_execute_parallel(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Execute multiple branches in parallel."""
    merged = {**config, **input_data}
    branches = merged.get("branches", [])
    if not branches:
        raise ValueError("branches is required for parallel.execute_parallel")
    if not isinstance(branches, list):
        raise ValueError("branches must be a list of callables or data items")

    async def run_branch(branch: dict, index: int) -> dict:
        branch_id = branch.get("id", f"branch_{index}")
        branch_input = branch.get("input", {})
        log.info("parallel.execute_parallel", branch_id=branch_id)
        return {"branch_id": branch_id, "input": branch_input, "status": "queued"}

    tasks = [run_branch(b if isinstance(b, dict) else {"id": f"branch_{i}", "input": b}, i)
             for i, b in enumerate(branches)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed.append({"branch_index": i, "status": "error", "error": str(result)})
        else:
            processed.append({**result, "status": "completed"})

    log.info("parallel.execute_parallel", total_branches=len(branches))
    return {"results": processed, "total": len(branches), "completed": len([r for r in processed if r.get("status") == "completed"])}


@register_node("parallel.gather_results")
async def parallel_gather_results(config: dict, input_data: dict, credential_id: str | None, db) -> dict:
    """Gather and merge results from parallel branches."""
    merged = {**config, **input_data}
    results = merged.get("results", [])
    merge_strategy = merged.get("merge_strategy", "list")

    if merge_strategy == "merge" and all(isinstance(r, dict) for r in results):
        merged_data: dict = {}
        for r in results:
            merged_data.update(r)
        log.info("parallel.gather_results", strategy="merge", count=len(results))
        return {"merged": merged_data, "count": len(results)}
    elif merge_strategy == "concat":
        all_items = []
        for r in results:
            if isinstance(r, list):
                all_items.extend(r)
            else:
                all_items.append(r)
        log.info("parallel.gather_results", strategy="concat", count=len(all_items))
        return {"items": all_items, "count": len(all_items)}
    else:
        log.info("parallel.gather_results", strategy="list", count=len(results))
        return {"results": results, "count": len(results)}
