"""Tests for workflow definition schema validation."""
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pydantic import ValidationError


def _import():
    from api.routes.workflows import WorkflowDefinition, NodeDefinition, EdgeDefinition
    return WorkflowDefinition, NodeDefinition, EdgeDefinition


def test_empty_definition_valid():
    WD, _, _ = _import()
    d = WD()
    assert d.nodes == []
    assert d.edges == []


def test_valid_definition():
    WD, _, _ = _import()
    d = WD(
        nodes=[{"id": "n1", "type": "http_request"}, {"id": "n2", "type": "slack.send_message"}],
        edges=[{"source": "n1", "target": "n2"}],
    )
    assert len(d.nodes) == 2
    assert d.edges[0].source == "n1"


def test_edge_invalid_source_raises():
    WD, _, _ = _import()
    with pytest.raises(ValidationError, match="source"):
        WD(
            nodes=[{"id": "n1", "type": "http"}],
            edges=[{"source": "MISSING", "target": "n1"}],
        )


def test_edge_invalid_target_raises():
    WD, _, _ = _import()
    with pytest.raises(ValidationError, match="target"):
        WD(
            nodes=[{"id": "n1", "type": "http"}],
            edges=[{"source": "n1", "target": "MISSING"}],
        )


def test_node_missing_id_raises():
    WD, ND, _ = _import()
    with pytest.raises(ValidationError):
        ND(type="http")


def test_node_missing_type_raises():
    WD, ND, _ = _import()
    with pytest.raises(ValidationError):
        ND(id="n1")


def test_node_timeout_bounds():
    WD, ND, _ = _import()
    with pytest.raises(ValidationError):
        ND(id="n1", type="http", timeout_seconds=0)
    with pytest.raises(ValidationError):
        ND(id="n1", type="http", timeout_seconds=9999)


def test_node_retry_defaults():
    WD, ND, _ = _import()
    n = ND(id="n1", type="http")
    assert n.retry.max_attempts == 1
    assert n.required is True
    assert n.timeout_seconds == 300


def test_model_dump_serializable():
    WD, _, _ = _import()
    import json
    d = WD(
        nodes=[{"id": "n1", "type": "http"}],
        edges=[],
    )
    dumped = d.model_dump()
    json.dumps(dumped)  # must not raise
