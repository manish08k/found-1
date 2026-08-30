"""
Evaluations — dataset management, test runs, and regression comparison.
"""
import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.middleware.auth import get_current_user
from storage.database import get_db
from storage.models import (
    EvaluationCase,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    User,
    Workflow,
)

log = structlog.get_logger(__name__)

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class DatasetCreate(BaseModel):
    name: str
    workflow_id: Optional[str] = None
    description: Optional[str] = None


class DatasetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class CaseCreate(BaseModel):
    input_data: dict
    expected_output: Optional[dict] = None
    tags: list[str] = []


class CaseBulkCreate(BaseModel):
    cases: list[CaseCreate]


class RunCreate(BaseModel):
    dataset_id: str
    workflow_id: str
    scorer_type: str = "exact_match"  # exact_match, contains, llm_judge, regex
    scorer_config: dict = {}


# ─── Datasets ─────────────────────────────────────────────────────────────────

@router.get("/datasets")
async def list_datasets(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(EvaluationDataset)
        .where(EvaluationDataset.created_by == user.id)
        .order_by(EvaluationDataset.created_at.desc())
    )
    datasets = result.scalars().all()
    return {
        "datasets": [
            {
                "id": d.id,
                "name": d.name,
                "workflow_id": d.workflow_id,
                "description": d.description,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in datasets
        ]
    }


@router.post("/datasets", status_code=201)
async def create_dataset(
    body: DatasetCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    dataset = EvaluationDataset(
        name=body.name,
        workflow_id=body.workflow_id,
        org_id=user.org_id,
        created_by=user.id,
        description=body.description,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return {
        "id": dataset.id,
        "name": dataset.name,
        "workflow_id": dataset.workflow_id,
        "description": dataset.description,
    }


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id,
            EvaluationDataset.created_by == user.id,
        )
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    await db.delete(dataset)
    await db.commit()
    return {"deleted": True, "id": dataset_id}


# ─── Cases ────────────────────────────────────────────────────────────────────

@router.get("/datasets/{dataset_id}/cases")
async def list_cases(
    dataset_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Verify ownership
    ds_result = await db.execute(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id,
            EvaluationDataset.created_by == user.id,
        )
    )
    if not ds_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Dataset not found")

    result = await db.execute(
        select(EvaluationCase)
        .where(EvaluationCase.dataset_id == dataset_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    cases = result.scalars().all()
    return {
        "cases": [
            {
                "id": c.id,
                "input_data": c.input_data,
                "expected_output": c.expected_output,
                "tags": c.tags,
            }
            for c in cases
        ],
        "page": page,
    }


@router.post("/datasets/{dataset_id}/cases", status_code=201)
async def create_case(
    dataset_id: str,
    body: CaseCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds_result = await db.execute(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id,
            EvaluationDataset.created_by == user.id,
        )
    )
    if not ds_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Dataset not found")

    case = EvaluationCase(
        dataset_id=dataset_id,
        input_data=body.input_data,
        expected_output=body.expected_output,
        tags=body.tags,
    )
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return {"id": case.id, "input_data": case.input_data, "expected_output": case.expected_output}


@router.post("/datasets/{dataset_id}/cases/bulk", status_code=201)
async def bulk_create_cases(
    dataset_id: str,
    body: CaseBulkCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds_result = await db.execute(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id,
            EvaluationDataset.created_by == user.id,
        )
    )
    if not ds_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Dataset not found")

    ids = []
    for c in body.cases:
        case = EvaluationCase(
            dataset_id=dataset_id,
            input_data=c.input_data,
            expected_output=c.expected_output,
            tags=c.tags,
        )
        db.add(case)
        await db.flush()
        ids.append(case.id)

    await db.commit()
    return {"created": len(ids), "ids": ids}


@router.delete("/datasets/{dataset_id}/cases/{case_id}")
async def delete_case(
    dataset_id: str,
    case_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ds_result = await db.execute(
        select(EvaluationDataset).where(
            EvaluationDataset.id == dataset_id,
            EvaluationDataset.created_by == user.id,
        )
    )
    if not ds_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Dataset not found")

    result = await db.execute(
        select(EvaluationCase).where(
            EvaluationCase.id == case_id,
            EvaluationCase.dataset_id == dataset_id,
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    await db.delete(case)
    await db.commit()
    return {"deleted": True, "id": case_id}


# ─── Runs ─────────────────────────────────────────────────────────────────────

@router.post("/runs", status_code=201)
async def start_evaluation_run(
    body: RunCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start an evaluation run (dispatched async via Celery)."""
    # Verify dataset
    ds_result = await db.execute(
        select(EvaluationDataset).where(
            EvaluationDataset.id == body.dataset_id,
            EvaluationDataset.created_by == user.id,
        )
    )
    if not ds_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Verify workflow
    wf_result = await db.execute(
        select(Workflow).where(
            Workflow.id == body.workflow_id,
            Workflow.owner_id == user.id,
        )
    )
    if not wf_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workflow not found")

    run = EvaluationRun(
        dataset_id=body.dataset_id,
        workflow_id=body.workflow_id,
        scorer_type=body.scorer_type,
        scorer_config=body.scorer_config,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Dispatch to Celery
    from workers.tasks import run_evaluation_task
    run_evaluation_task.delay(run.id)

    return {
        "id": run.id,
        "status": "pending",
        "dataset_id": run.dataset_id,
        "workflow_id": run.workflow_id,
    }


@router.get("/runs/{run_id}")
async def get_evaluation_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get evaluation run status and summary."""
    result = await db.execute(
        select(EvaluationRun)
        .join(EvaluationDataset, EvaluationDataset.id == EvaluationRun.dataset_id)
        .where(
            EvaluationRun.id == run_id,
            EvaluationDataset.created_by == user.id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return {
        "id": run.id,
        "dataset_id": run.dataset_id,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "scorer_type": run.scorer_type,
        "summary": run.summary,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


@router.get("/runs/{run_id}/results")
async def get_evaluation_results(
    run_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Paginated per-case results for an evaluation run."""
    # Verify ownership
    run_result = await db.execute(
        select(EvaluationRun)
        .join(EvaluationDataset, EvaluationDataset.id == EvaluationRun.dataset_id)
        .where(
            EvaluationRun.id == run_id,
            EvaluationDataset.created_by == user.id,
        )
    )
    if not run_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Run not found")

    result = await db.execute(
        select(EvaluationResult)
        .where(EvaluationResult.run_id == run_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    results = result.scalars().all()

    return {
        "results": [
            {
                "id": r.id,
                "case_id": r.case_id,
                "actual_output": r.actual_output,
                "score": r.score,
                "passed": r.passed,
                "error": r.error,
            }
            for r in results
        ],
        "page": page,
    }


@router.get("/compare")
async def compare_runs(
    run1: str = Query(...),
    run2: str = Query(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Compare two evaluation runs for regression detection."""
    # Load both runs
    r1_result = await db.execute(
        select(EvaluationRun)
        .join(EvaluationDataset, EvaluationDataset.id == EvaluationRun.dataset_id)
        .where(EvaluationRun.id == run1, EvaluationDataset.created_by == user.id)
    )
    r2_result = await db.execute(
        select(EvaluationRun)
        .join(EvaluationDataset, EvaluationDataset.id == EvaluationRun.dataset_id)
        .where(EvaluationRun.id == run2, EvaluationDataset.created_by == user.id)
    )
    run_1 = r1_result.scalar_one_or_none()
    run_2 = r2_result.scalar_one_or_none()

    if not run_1 or not run_2:
        raise HTTPException(status_code=404, detail="One or both runs not found")

    # Load results for both runs
    res1_result = await db.execute(
        select(EvaluationResult).where(EvaluationResult.run_id == run1)
    )
    res2_result = await db.execute(
        select(EvaluationResult).where(EvaluationResult.run_id == run2)
    )
    results_1 = {r.case_id: r for r in res1_result.scalars().all()}
    results_2 = {r.case_id: r for r in res2_result.scalars().all()}

    # Compare per case
    regressions = []
    improvements = []
    unchanged = []

    all_case_ids = set(results_1.keys()) | set(results_2.keys())
    for case_id in all_case_ids:
        r1 = results_1.get(case_id)
        r2 = results_2.get(case_id)

        if r1 and r2:
            if r1.passed and not r2.passed:
                regressions.append({"case_id": case_id, "run1_score": r1.score, "run2_score": r2.score})
            elif not r1.passed and r2.passed:
                improvements.append({"case_id": case_id, "run1_score": r1.score, "run2_score": r2.score})
            else:
                unchanged.append({"case_id": case_id, "run1_score": r1.score, "run2_score": r2.score})

    return {
        "run1": {"id": run1, "summary": run_1.summary},
        "run2": {"id": run2, "summary": run_2.summary},
        "regressions": regressions,
        "improvements": improvements,
        "unchanged_count": len(unchanged),
        "regression_count": len(regressions),
        "improvement_count": len(improvements),
    }
