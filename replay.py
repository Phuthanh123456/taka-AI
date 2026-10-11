"""Session-local state and a monotonic simulated clock."""


def new_session(mode="Rule mode", model=None):
    return {"next_index": 0, "demo_time": 0, "comments": [], "results": {},
            "groups": [], "responses": [], "moderator_queue": {}, "viewer_history": {},
            "mode": mode, "model": model}


def advance_time(state, seconds=30):
    if seconds < 0:
        raise ValueError("Session time cannot move backward.")
    state["demo_time"] += seconds


def load_next(state, bundle, agent, count=5):
    from workflow import process_comment
    batch = bundle["comments"][state["next_index"]:state["next_index"] + count]
    batch = sorted(batch, key=lambda c: c["at_seconds"])
    classify_batch = getattr(agent, "classify_batch", None)
    if batch and callable(classify_batch):
        try:
            decisions = classify_batch(batch, bundle["products"], bundle["faqs"], state["viewer_history"])
            if not isinstance(decisions, list) or len(decisions) != len(batch):
                raise ValueError("Gemini returned an incomplete batch.")
            batch_error = None
        except Exception as exc:
            # Keep the cause generic; provider exceptions can contain request data or credentials.
            decisions = [None] * len(batch)
            batch_error = f"Gemini could not process the comment batch ({type(exc).__name__}); moderator review is needed."
        for comment, decision in zip(batch, decisions):
            state["demo_time"] = max(state["demo_time"], comment["at_seconds"])
            process_comment(state, bundle, agent, comment, decision_override=decision,
                            classification_error=batch_error)
            state["next_index"] += 1
        return len(batch)

    for comment in batch:
        state["demo_time"] = max(state["demo_time"], comment["at_seconds"])
        process_comment(state, bundle, agent, comment)
        state["next_index"] += 1
    return len(batch)
