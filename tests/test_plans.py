"""Tests for core/plans.py — plan limits and enforcement."""
import pytest
from types import SimpleNamespace

from fastapi import HTTPException

from core.plans import PLAN_LIMITS, get_plan_limits


def test_all_five_tiers_defined():
    assert set(PLAN_LIMITS.keys()) == {"free", "starter", "pro", "business", "enterprise"}


def test_pricing_matches_the_table():
    assert PLAN_LIMITS["free"].price_inr_per_month == 0
    assert PLAN_LIMITS["starter"].price_inr_per_month == 999
    assert PLAN_LIMITS["pro"].price_inr_per_month == 3_499
    assert PLAN_LIMITS["business"].price_inr_per_month == 12_999
    assert PLAN_LIMITS["enterprise"].price_inr_per_month is None


def test_execution_limits_match_the_table():
    assert PLAN_LIMITS["free"].max_executions_per_month == 500
    assert PLAN_LIMITS["starter"].max_executions_per_month == 10_000
    assert PLAN_LIMITS["pro"].max_executions_per_month == 50_000
    assert PLAN_LIMITS["business"].max_executions_per_month == 250_000
    assert PLAN_LIMITS["enterprise"].max_executions_per_month is None


def test_active_workflow_limits_match_the_table():
    assert PLAN_LIMITS["free"].max_active_workflows == 5
    assert PLAN_LIMITS["starter"].max_active_workflows == 25
    assert PLAN_LIMITS["pro"].max_active_workflows is None  # unlimited
    assert PLAN_LIMITS["business"].max_active_workflows is None
    assert PLAN_LIMITS["enterprise"].max_active_workflows is None


def test_user_limits_match_the_table():
    assert PLAN_LIMITS["free"].max_users == 1
    assert PLAN_LIMITS["starter"].max_users == 2
    assert PLAN_LIMITS["pro"].max_users == 10
    assert PLAN_LIMITS["business"].max_users == 50
    assert PLAN_LIMITS["enterprise"].max_users is None


def test_execution_history_days_match_the_table():
    assert PLAN_LIMITS["free"].execution_history_days == 1
    assert PLAN_LIMITS["starter"].execution_history_days == 7
    assert PLAN_LIMITS["pro"].execution_history_days == 30
    assert PLAN_LIMITS["business"].execution_history_days == 90
    assert PLAN_LIMITS["enterprise"].execution_history_days is None


def test_rbac_audit_logs_only_business_and_up():
    assert PLAN_LIMITS["free"].rbac_audit_logs is False
    assert PLAN_LIMITS["starter"].rbac_audit_logs is False
    assert PLAN_LIMITS["pro"].rbac_audit_logs is False
    assert PLAN_LIMITS["business"].rbac_audit_logs is True
    assert PLAN_LIMITS["enterprise"].rbac_audit_logs is True


def test_sso_saml_only_business_and_up():
    assert PLAN_LIMITS["pro"].sso_saml is False
    assert PLAN_LIMITS["business"].sso_saml is True
    assert PLAN_LIMITS["enterprise"].sso_saml is True


def test_on_premise_only_enterprise():
    assert PLAN_LIMITS["business"].on_premise is False
    assert PLAN_LIMITS["enterprise"].on_premise is True


def test_get_plan_limits_with_no_org_is_unmetered():
    """Solo/personal accounts are never limited — see core/plans.py's module docstring."""
    limits = get_plan_limits(None)
    assert limits.max_active_workflows is None
    assert limits.max_executions_per_month is None
    assert limits.max_users is None
    assert limits.execution_history_days is None


def test_get_plan_limits_reads_org_plan():
    org = SimpleNamespace(plan=SimpleNamespace(value="starter"))
    limits = get_plan_limits(org)
    assert limits.max_active_workflows == 25


def test_get_plan_limits_falls_back_to_free_for_unknown_plan():
    org = SimpleNamespace(plan=SimpleNamespace(value="not-a-real-plan"))
    limits = get_plan_limits(org)
    assert limits.max_active_workflows == 5  # free tier's value
