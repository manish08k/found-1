"""Tests for the workflow execution engine."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from collections import defaultdict

# ── topological_sort ──────────────────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.execution_engine import topological_sort, _build_node_input, NODE_HANDLERS, register_node


def _nodes(*ids):
    return [{"id": i} for i in ids]


def _edges(*pairs):
    return [{"source": s, "target": t} for s, t in pairs]


def test_topo_sort_linear():
    nodes = _nodes("a", "b", "c")
    edges = _edges(("a", "b"), ("b", "c"))
    levels = topological_sort(nodes, edges)
    assert levels == [["a"], ["b"], ["c"]]


def test_topo_sort_parallel():
    nodes = _nodes("a", "b", "c")
    edges = _edges(("a", "b"), ("a", "c"))
    levels = topological_sort(nodes, edges)
    assert levels[0] == ["a"]
    assert set(levels[1]) == {"b", "c"}


def test_topo_sort_no_edges():
    nodes = _nodes("x", "y", "z")
    levels = topological_sort(nodes, [])
    flat = [n for level in levels for n in level]
    assert set(flat) == {"x", "y", "z"}


def test_topo_sort_cycle_raises():
    nodes = _nodes("a", "b")
    edges = _edges(("a", "b"), ("b", "a"))
    with pytest.raises(ValueError, match="cycle"):
        topological_sort(nodes, edges)


def test_topo_sort_diamond():
    # a → b, a → c, b → d, c → d
    nodes = _nodes("a", "b", "c", "d")
    edges = _edges(("a", "b"), ("a", "c"), ("b", "d"), ("c", "d"))
    levels = topological_sort(nodes, edges)
    assert levels[0] == ["a"]
    assert set(levels[1]) == {"b", "c"}
    assert levels[2] == ["d"]


# ── _build_node_input ─────────────────────────────────────────────────────────

def test_build_node_input_no_parents():
    trigger = {"event": "push"}
    result = _build_node_input("node1", [], {}, trigger)
    assert result == trigger


def test_build_node_input_merges_parents():
    edges = [{"source": "a", "target": "c"}, {"source": "b", "target": "c"}]
    node_results = {
        "a": {"status": "success", "output": {"x": 1}},
        "b": {"status": "success", "output": {"y": 2}},
    }
    result = _build_node_input("c", edges, node_results, {})
    assert result == {"x": 1, "y": 2}


def test_build_node_input_missing_parent_skipped():
    edges = [{"source": "missing", "target": "b"}]
    result = _build_node_input("b", edges, {}, {"fallback": True})
    assert result == {}  # no parent output, merges nothing


# ── register_node decorator ───────────────────────────────────────────────────

def test_register_node():
    @register_node("test_node_type_xyz")
    async def handler(**kwargs):
        return {"ok": True}

    assert "test_node_type_xyz" in NODE_HANDLERS


# ── timeout enforcement ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_node_timeout_raises():
    from core.execution_engine import _execute_node

    @register_node("slow_node")
    async def slow_handler(**kwargs):
        await asyncio.sleep(999)

    node = {"id": "n1", "type": "slow_node", "timeout_seconds": 1, "retry": {}}
    with pytest.raises((TimeoutError, asyncio.TimeoutError)):
        await _execute_node(node, {}, AsyncMock())


@pytest.mark.asyncio
async def test_node_success():
    from core.execution_engine import _execute_node

    @register_node("fast_node")
    async def fast_handler(**kwargs):
        return {"result": "ok"}

    node = {"id": "n2", "type": "fast_node", "timeout_seconds": 5, "retry": {}}
    result = await _execute_node(node, {}, AsyncMock())
    assert result == {"result": "ok"}


@pytest.mark.asyncio
async def test_node_unknown_type_raises():
    from core.execution_engine import _execute_node
    node = {"id": "n3", "type": "nonexistent_type_abc", "timeout_seconds": 5, "retry": {}}
    with pytest.raises(ValueError, match="No handler"):
        await _execute_node(node, {}, AsyncMock())
