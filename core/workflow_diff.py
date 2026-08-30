"""
Workflow Version Diff Engine.

Computes a structured diff between two workflow versions, including:
  - Added/removed/changed nodes
  - Added/removed edges
  - Per-node config field changes
"""


def compute_workflow_diff(version_a: dict, version_b: dict) -> dict:
    """
    Compute a detailed diff between two workflow version definitions.

    Returns:
        {
            "nodes_added": [...],
            "nodes_removed": [...],
            "nodes_changed": [...],
            "edges_added": [...],
            "edges_removed": [...],
            "config_changes": {node_id: {field: {"old": v, "new": v}}}
        }
    """
    nodes_a = {n["id"]: n for n in version_a.get("nodes", [])}
    nodes_b = {n["id"]: n for n in version_b.get("nodes", [])}

    ids_a = set(nodes_a.keys())
    ids_b = set(nodes_b.keys())

    nodes_added = [nodes_b[nid] for nid in (ids_b - ids_a)]
    nodes_removed = [nodes_a[nid] for nid in (ids_a - ids_b)]

    # Changed nodes + config diffs
    nodes_changed = []
    config_changes = {}
    for nid in ids_a & ids_b:
        na = nodes_a[nid]
        nb = nodes_b[nid]
        if na != nb:
            nodes_changed.append(nb)

            # Detailed config diff
            config_a = na.get("config", {})
            config_b = nb.get("config", {})
            changes = {}

            all_keys = set(list(config_a.keys()) + list(config_b.keys()))
            for key in all_keys:
                old_val = config_a.get(key)
                new_val = config_b.get(key)
                if old_val != new_val:
                    changes[key] = {"old": old_val, "new": new_val}

            # Check non-config fields too
            for field in ("type", "credential_id", "required"):
                if na.get(field) != nb.get(field):
                    changes[f"__{field}"] = {"old": na.get(field), "new": nb.get(field)}

            if changes:
                config_changes[nid] = changes

    # Edge diffs
    def edge_key(e: dict) -> tuple:
        return (e.get("source", ""), e.get("target", ""))

    edges_a = {edge_key(e): e for e in version_a.get("edges", [])}
    edges_b = {edge_key(e): e for e in version_b.get("edges", [])}

    edges_added = [edges_b[k] for k in (set(edges_b.keys()) - set(edges_a.keys()))]
    edges_removed = [edges_a[k] for k in (set(edges_a.keys()) - set(edges_b.keys()))]

    return {
        "nodes_added": nodes_added,
        "nodes_removed": nodes_removed,
        "nodes_changed": nodes_changed,
        "edges_added": edges_added,
        "edges_removed": edges_removed,
        "config_changes": config_changes,
        "summary": {
            "added": len(nodes_added),
            "removed": len(nodes_removed),
            "changed": len(nodes_changed),
            "edges_added": len(edges_added),
            "edges_removed": len(edges_removed),
        },
    }
