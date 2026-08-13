LANES = {"working", "waiting", "done", "failed"}


def classify_lane(item):
    kind = item.get("kind")
    state = item.get("state")

    if kind == "issue":
        if state == "open":
            return {"lane": "working", "laneReason": "open_issue"}
        if state == "closed":
            return {"lane": "done", "laneReason": "closed_issue"}

    if kind == "pull_request":
        if state == "open":
            return {"lane": "waiting", "laneReason": "open_pull_request"}
        if state == "closed":
            return {"lane": "done", "laneReason": "closed_pull_request"}

    if kind == "workflow_run":
        if state in {"queued", "in_progress"}:
            return {"lane": "working", "laneReason": f"workflow_{state}"}
        if state in {"completed", "skipped"}:
            return {"lane": "done", "laneReason": f"workflow_{state}"}
        if state in {"failed", "cancelled"}:
            return {"lane": "failed", "laneReason": f"workflow_{state}"}

    return {"lane": "waiting", "laneReason": "unknown_state_requires_review"}


def add_lane(item):
    enriched = dict(item)
    enriched.update(classify_lane(item))
    return enriched
