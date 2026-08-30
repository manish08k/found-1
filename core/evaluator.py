"""
Evaluation engine — runs test datasets against workflows and scores results.

Scoring methods:
  - exact_match: actual output must exactly match expected
  - contains: expected text must appear in actual output
  - regex: actual output must match a regex pattern
  - llm_judge: uses an LLM to judge output quality (0-100)
"""
import json
import re
import traceback
from datetime import datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from storage.models import (
    EvaluationCase,
    EvaluationResult,
    EvaluationRun,
    EvaluationDataset,
    Workflow,
    Execution,
    ExecutionStatus,
)
from storage.database import db_context
from core.execution_engine import execute_workflow

log = structlog.get_logger(__name__)


def _score_exact_match(actual: dict, expected: dict, config: dict) -> tuple[bool, int]:
    """Exact equality check. Returns (passed, score 0-100)."""
    # Compare specific fields if configured, otherwise compare entire dicts
    fields = config.get("compare_fields")
    if fields:
        for field in fields:
            if actual.get(field) != expected.get(field):
                return False, 0
        return True, 100

    if actual == expected:
        return True, 100
    return False, 0


def _score_contains(actual: dict, expected: dict, config: dict) -> tuple[bool, int]:
    """Check if expected values appear in actual output."""
    actual_str = json.dumps(actual).lower()
    check_fields = config.get("check_fields") or list(expected.keys())

    matches = 0
    total = len(check_fields)
    if total == 0:
        return True, 100

    for field in check_fields:
        expected_val = expected.get(field)
        if expected_val is None:
            matches += 1
            continue
        expected_str = str(expected_val).lower()
        if expected_str in actual_str:
            matches += 1

    score = int((matches / total) * 100)
    return score >= 100, score


def _score_regex(actual: dict, expected: dict, config: dict) -> tuple[bool, int]:
    """Check if actual output matches regex patterns."""
    pattern = config.get("pattern", "")
    field = config.get("field", "text")

    actual_val = actual.get(field, "")
    if not isinstance(actual_val, str):
        actual_val = json.dumps(actual_val)

    if not pattern:
        # Use expected output values as patterns
        patterns = [str(v) for v in expected.values()]
    else:
        patterns = [pattern]

    for pat in patterns:
        try:
            if re.search(pat, actual_val, re.IGNORECASE):
                return True, 100
        except re.error:
            continue

    return False, 0


async def _score_llm_judge(actual: dict, expected: dict, config: dict) -> tuple[bool, int]:
    """Use an LLM to judge the quality of the output."""
    from integrations.ai.handler import _call_llm, _pick_provider

    provider = _pick_provider(config)
    model = config.get("model", "")

    system = (
        "You are an evaluation judge. Compare the actual output to the expected output "
        "and score the actual output from 0 to 100.\n"
        "Respond with ONLY a JSON object: {\"score\": <0-100>, \"reason\": \"...\"}\n"
        "Score 100 = perfect match in meaning (even if wording differs).\n"
        "Score 0 = completely wrong or irrelevant."
    )
    prompt = (
        f"Expected output:\n{json.dumps(expected, indent=2)}\n\n"
        f"Actual output:\n{json.dumps(actual, indent=2)}\n\n"
        "Score this output:"
    )

    raw = await _call_llm(provider, model, system, prompt, 200, 0)
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()

    try:
        result = json.loads(cleaned)
        score = int(result.get("score", 0))
    except (json.JSONDecodeError, TypeError, ValueError):
        score = 0

    threshold = int(config.get("pass_threshold", 70))
    return score >= threshold, min(score, 100)


async def run_evaluation(run_id: str) -> dict:
    """
    Execute all test cases in an evaluation run against the target workflow.
    Called by the Celery task.
    """
    async with db_context() as db:
        # Load run
        result = await db.execute(select(EvaluationRun).where(EvaluationRun.id == run_id))
        run = result.scalar_one_or_none()
        if not run:
            log.error("evaluation_run_not_found", run_id=run_id)
            return {"error": "Run not found"}

        run.status = "running"
        run.started_at = datetime.utcnow()
        await db.flush()

        # Load dataset cases
        cases_result = await db.execute(
            select(EvaluationCase).where(EvaluationCase.dataset_id == run.dataset_id)
        )
        cases = cases_result.scalars().all()

        # Load workflow
        wf_result = await db.execute(select(Workflow).where(Workflow.id == run.workflow_id))
        workflow = wf_result.scalar_one_or_none()
        if not workflow:
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            run.summary = {"error": "Workflow not found"}
            await db.commit()
            return {"error": "Workflow not found"}

        pass_count = 0
        fail_count = 0
        total_score = 0

        for case in cases:
            actual_output = None
            error_text = None

            try:
                # Create an execution for this test case
                import uuid
                exec_id = str(uuid.uuid4())
                execution = Execution(
                    id=exec_id,
                    workflow_id=workflow.id,
                    status=ExecutionStatus.queued,
                    trigger_type="evaluation",
                    trigger_data=case.input_data or {},
                )
                db.add(execution)
                await db.flush()

                # Run the workflow synchronously
                await execute_workflow(exec_id, workflow.definition, case.input_data or {})

                # Reload execution to get results
                await db.refresh(execution)
                node_results = execution.node_results or {}

                # Collect outputs from all successful nodes
                actual_output = {}
                for nid, nr in node_results.items():
                    if isinstance(nr, dict) and nr.get("status") == "success":
                        output = nr.get("output", {})
                        if isinstance(output, dict):
                            actual_output.update(output)

                if execution.status == ExecutionStatus.failed:
                    error_text = execution.error

            except Exception as exc:
                error_text = traceback.format_exc()
                actual_output = {"error": str(exc)}

            # Score the result
            expected = case.expected_output or {}
            passed = False
            score = 0

            if error_text and not actual_output:
                passed = False
                score = 0
            else:
                try:
                    scorer = run.scorer_type or "exact_match"
                    scorer_config = run.scorer_config or {}

                    if scorer == "exact_match":
                        passed, score = _score_exact_match(actual_output or {}, expected, scorer_config)
                    elif scorer == "contains":
                        passed, score = _score_contains(actual_output or {}, expected, scorer_config)
                    elif scorer == "regex":
                        passed, score = _score_regex(actual_output or {}, expected, scorer_config)
                    elif scorer == "llm_judge":
                        passed, score = await _score_llm_judge(actual_output or {}, expected, scorer_config)
                    else:
                        passed, score = _score_exact_match(actual_output or {}, expected, scorer_config)
                except Exception as e:
                    error_text = (error_text or "") + f"\nScoring error: {e}"

            # Save result
            eval_result = EvaluationResult(
                run_id=run.id,
                case_id=case.id,
                actual_output=actual_output,
                score=score,
                passed=passed,
                error=error_text,
            )
            db.add(eval_result)

            if passed:
                pass_count += 1
            else:
                fail_count += 1
            total_score += score

        # Update run summary
        total_cases = len(cases)
        run.status = "completed"
        run.finished_at = datetime.utcnow()
        run.summary = {
            "pass_count": pass_count,
            "fail_count": fail_count,
            "total_cases": total_cases,
            "pass_rate": round(pass_count / total_cases * 100, 1) if total_cases else 0,
            "avg_score": round(total_score / total_cases, 1) if total_cases else 0,
        }

        await db.commit()
        log.info("evaluation_completed", run_id=run_id, summary=run.summary)
        return run.summary
