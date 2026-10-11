"""Validated decisions, immutable approved replies and moderator lifecycle."""
from copy import deepcopy
from agent import SCHEMA, explicit_products, resolve_product, scope_reason, is_combo_question, normalize, contains

WAITING = "Đang chờ"
AI_REPLIED = "AI đã phản hồi trong mô phỏng"
MOD_WAITING = "Chờ moderator"
MOD_WORKING = "Moderator đang xử lý"
MOD_REPLIED = "Người hỗ trợ đã phản hồi"
IGNORED = "Không cần tác vụ hỏi đáp"
PENDING = {WAITING, MOD_WAITING, MOD_WORKING}
HISTORY_LIMIT = 5
_USE_AGENT = object()


def fallback(comment, reason):
    return dict(comment_id=comment["comment_id"], route="ESCALATE", product_id=None,
                faq_id=None, reason=reason)


def validate_decision(decision, comment, bundle, history=None):
    if not isinstance(decision, dict) or set(decision) != set(SCHEMA["required"]):
        raise ValueError("Invalid JSON structure")
    if decision["comment_id"] != comment["comment_id"] or decision["route"] not in ("AUTO", "ESCALATE", "IGNORE"):
        raise ValueError("Invalid comment_id or route")
    if not isinstance(decision["reason"], str) or not decision["reason"].strip():
        raise ValueError("Missing reason")
    products = {p["product_id"] for p in bundle["products"]}
    faqs = {f["faq_id"]: f for f in bundle["faqs"]}
    pid, fid = decision["product_id"], decision["faq_id"]
    if pid is not None and (not isinstance(pid, str) or pid not in products):
        raise ValueError("Unknown product_id")
    if fid is not None and (not isinstance(fid, str) or fid not in faqs):
        raise ValueError("Unknown faq_id")
    if fid is not None and faqs[fid]["product_id"] != pid:
        raise ValueError("FAQ does not belong to this product")
    approved_combo = (decision["route"] == "AUTO" and fid in faqs
                      and bool(faqs[fid].get("offer")) and is_combo_question(comment["text"]))
    reason = scope_reason(comment["text"], allow_approved_combo=approved_combo)
    if reason:
        return fallback(comment, reason)
    if decision["route"] == "AUTO":
        if pid is None or fid is None or not faqs[fid]["auto_reply_allowed"]:
            raise ValueError("FAQ is not approved for automatic replies")
        explicit = explicit_products(comment["text"], bundle["products"])
        if explicit and explicit != {pid}:
            raise ValueError("Explicit product does not match the decision")
        if not explicit and resolve_product(comment, bundle["products"], history or []) is None:
            return fallback(comment, "Product context is unclear; moderator verification is needed.")
        text = normalize(comment["text"])
        if normalize(faqs[fid]["topic"]) == "thanh phan cong bo" and any(contains(text, q) for q in ["có", "không"]) and not any(contains(text, q) for q in ["gì", "nào", "danh sách", "liệt kê"]):
            return fallback(comment, "The ingredient list is incomplete; a specific ingredient cannot be verified.")
    elif fid is not None:
        raise ValueError("ESCALATE/IGNORE must have faq_id=null")
    return deepcopy(decision)


def process_comment(state, bundle, agent, comment, decision_override=_USE_AGENT,
                    classification_error=None):
    cid = comment["comment_id"]
    if cid in state["results"]:
        return state["results"][cid]
    history = deepcopy(state["viewer_history"].get(comment["user_id"], []))
    state["comments"].append(deepcopy(comment))
    record = dict(comment=deepcopy(comment), status=WAITING, created_at=state["demo_time"],
                  response_id=None, context=history, assigned_to=None, referral=None)
    # Reserve ID before the provider call so ordinary reruns cannot call it again.
    state["results"][cid] = record
    if classification_error:
        decision = fallback(comment, classification_error)
    else:
        try:
            raw_decision = decision_override
            if decision_override is _USE_AGENT:
                raw_decision = agent.classify(comment, bundle["products"], bundle["faqs"], history)
            decision = validate_decision(raw_decision, comment, bundle, history)
        except Exception as exc:
            # Do not expose provider exception text: it can contain credentials or payloads.
            decision = fallback(comment, f"System error or invalid result ({type(exc).__name__}); moderator review is needed.")
    record.update(decision)
    if decision["route"] == "AUTO":
        faq = next(f for f in bundle["faqs"] if f["faq_id"] == decision["faq_id"])
        response = dict(response_id=f"R{len(state['responses']) + 1:03}",
                        comment_ids=[cid], user_ids=[comment["user_id"]], author="AI / approved FAQ",
                        text=faq["approved_answer"], at_seconds=state["demo_time"], mode=state["mode"])
        state["responses"].append(response)
        record.update(response_id=response["response_id"], status=AI_REPLIED)
        window = bundle["policy"]["group_window_seconds"]
        group = next((g for g in reversed(state["groups"])
                      if g["product_id"] == decision["product_id"] and g["faq_id"] == faq["faq_id"]
                      and 0 <= state["demo_time"] - g["created_at"] <= window), None)
        if group is None:
            group = dict(group_id=f"G{len(state['groups']) + 1:03}", product_id=decision["product_id"],
                         faq_id=faq["faq_id"], topic=faq["topic"], answer=faq["approved_answer"],
                         created_at=state["demo_time"], comment_ids=[], user_ids=[], response_ids=[])
            state["groups"].append(group)
        group["comment_ids"].append(cid)
        if comment["user_id"] not in group["user_ids"]:
            group["user_ids"].append(comment["user_id"])
        group["response_ids"].append(response["response_id"])
    elif decision["route"] == "ESCALATE":
        record["status"] = MOD_WAITING
        state["moderator_queue"][cid] = record
    else:
        record["status"] = IGNORED
    entry = dict(comment_id=cid, text=comment["text"], at_seconds=comment["at_seconds"],
                 active_product_id=comment["active_product_id"], product_id=decision["product_id"],
                 route=decision["route"], status=record["status"], response=None)
    if record["response_id"]:
        entry["response"] = state["responses"][-1]["text"]
    user_history = state["viewer_history"].setdefault(comment["user_id"], [])
    user_history.append(entry)
    del user_history[:-HISTORY_LIMIT]
    return record


def is_overdue(record, demo_time, policy):
    return record["status"] in PENDING and demo_time - record["created_at"] >= policy["moderator_timeout_seconds"]


def claim(state, cid, moderator):
    record = state["moderator_queue"][cid]
    if record["status"] != MOD_WAITING or not moderator.strip():
        raise ValueError("Case is not ready to claim or moderator name is missing.")
    record.update(status=MOD_WORKING, assigned_to=moderator.strip())
    update_history(state, record)


def refer(state, cid, note):
    record = state["moderator_queue"][cid]
    if record["status"] != MOD_WORKING or not note.strip():
        raise ValueError("Claim the case and enter the details to verify.")
    record["referral"] = note.strip()


def moderator_reply(state, cid, text):
    record = state["moderator_queue"][cid]
    if record["status"] != MOD_WORKING or not text.strip():
        raise ValueError("Claim the case before entering a reply.")
    response = dict(response_id=f"R{len(state['responses']) + 1:03}", comment_ids=[cid],
                    user_ids=[record["comment"]["user_id"]], author=record["assigned_to"],
                    text=text.strip(), at_seconds=state["demo_time"], mode="Moderator")
    state["responses"].append(response)
    record.update(status=MOD_REPLIED, response_id=response["response_id"])
    update_history(state, record, text.strip())


def update_history(state, record, response=None):
    for entry in state["viewer_history"].get(record["comment"]["user_id"], []):
        if entry["comment_id"] == record["comment_id"]:
            entry["status"] = record["status"]
            if response is not None:
                entry["response"] = response


def host_prompts(state, policy):
    return [g for g in state["groups"]
            if len(g["user_ids"]) >= policy["host_prompt_unique_viewers"]
            and state["demo_time"] - g["created_at"] <= policy["group_window_seconds"]]
