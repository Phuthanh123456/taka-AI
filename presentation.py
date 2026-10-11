"""Small replay scenes and escaped dashboard markup, independent of Streamlit."""
from html import escape
from collections import Counter
from replay import new_session, load_next, advance_time
from workflow import AI_REPLIED, MOD_REPLIED, MOD_WORKING, MOD_WAITING, PENDING, is_overdue


FAQ_TOPIC_LABELS = {
    "Thành phần công bố": "Listed ingredients",
    "Chỉ số SPF trên nhãn": "Label SPF",
    "Dung tích": "Volume",
    "Combo ưu đãi": "Combo offer",
}


def faq_topic_label(topic):
    return FAQ_TOPIC_LABELS.get(topic, topic)


def product_label(product_id, name):
    return "Sunscreen B" if product_id == "SUN_B" else name.split(" — ")[0]


def dashboard_metrics(state, policy):
    """Read-only counts of received comments; never count unreplayed input as backlog."""
    records = list(state["results"].values())
    pending = [r for r in records if r["status"] in PENDING]
    return {
        "received": len(records),
        "waiting": len(pending),
        "unassigned": sum(not r["assigned_to"] for r in pending),
        "moderator": sum(r["status"] in (MOD_WAITING, MOD_WORKING) for r in records),
        "ai_replied": sum(r["status"] == AI_REPLIED for r in records),
        "mod_replied": sum(r["status"] == MOD_REPLIED for r in records),
        "late": sum(is_overdue(r, state["demo_time"], policy) for r in records),
        "longest_wait": max((state["demo_time"] - r["created_at"] for r in pending), default=None),
    }


def classification_summary_markup(state, bundle, total):
    """Counts actual processed comments by the FAQ or workflow route selected."""
    records = list(state["results"].values())
    processed = len(records)
    faq_counts = Counter(r.get("faq_id") for r in records if r.get("route") == "AUTO")
    route_counts = Counter(r.get("route") for r in records)
    followups = sum(bool(r.get("context")) for r in records)

    items = []
    for faq in bundle["faqs"]:
        count = faq_counts[faq["faq_id"]]
        if count:
            items.append(
                f'<span class="classification-item faq-item"><i></i><span>{e(faq_topic_label(faq["topic"]))}</span><b>{count}</b></span>')
    if route_counts["ESCALATE"]:
        items.append(
            f'<span class="classification-item support-item"><i></i><span>Needs moderator</span><b>{route_counts["ESCALATE"]}</b></span>')
    if route_counts["IGNORE"]:
        items.append(
            f'<span class="classification-item ignore-item"><i></i><span>No reply needed</span><b>{route_counts["IGNORE"]}</b></span>')
    content = ''.join(items) or '<span class="classification-empty">Run a scenario to let Gemini classify comments.</span>'
    return f'''<section class="classification-summary" aria-label="Comment classification summary">
      <div class="classification-heading"><strong>Comment categories</strong>
        <span>{processed} / {total} processed</span></div>
      <div class="classification-items">{content}
        {f'<span class="classification-followups"><i></i>{followups} follow-ups</span>' if followups else ''}
      </div></section>'''


def routing_breakdown_markup(state):
    """Compact distribution based only on comments already processed in this scene."""
    records = list(state["results"].values())
    total = len(records)
    auto = sum(r.get("route") == "AUTO" for r in records)
    support = sum(r.get("route") == "ESCALATE" for r in records)
    ignored = sum(r.get("route") == "IGNORE" for r in records)
    auto_end = round(auto / total * 100, 2) if total else 0
    support_end = round((auto + support) / total * 100, 2) if total else 0
    return f'''<section class="insight-card route-card" aria-label="Comment routing">
      <div class="insight-heading"><h2>Routing</h2><span>{total} received</span></div>
      <div class="route-visual"><div class="route-donut" style="--auto-end:{auto_end}%;--support-end:{support_end}%">
        <div><strong>{total}</strong><span>comments</span></div></div>
        <div class="route-legend">
          <div><i class="legend-auto"></i><span>AI replied</span><strong>{auto}</strong></div>
          <div><i class="legend-support"></i><span>Needs support</span><strong>{support}</strong></div>
          <div><i class="legend-ignored"></i><span>No reply needed</span><strong>{ignored}</strong></div>
        </div></div></section>'''


def activity_trend_markup(state):
    """Cumulative received and AI-answered comments by replay timestamp."""
    records = sorted(state["results"].values(), key=lambda r: r["comment"]["at_seconds"])
    if not records:
        return '''<section class="insight-card trend-card"><div class="insight-heading"><h2>Comment activity</h2></div>
          <p class="trend-empty">No comments in this session yet.</p></section>'''
    left, right, top, bottom = 18, 276, 12, 88
    start = records[0]["comment"]["at_seconds"]
    end = max(records[-1]["comment"]["at_seconds"], start + 1)
    total = len(records)
    received_points = []
    answered_points = []
    answered = 0
    for index, record in enumerate(records, 1):
        at = record["comment"]["at_seconds"]
        x = left + (at - start) / (end - start) * (right - left)
        answered += record.get("route") == "AUTO"
        received_points.append(f"{x:.1f},{bottom - index / total * (bottom - top):.1f}")
        answered_points.append(f"{x:.1f},{bottom - answered / total * (bottom - top):.1f}")
    received_line = " ".join([f"{left},{bottom}", *received_points])
    answered_line = " ".join([f"{left},{bottom}", *answered_points])
    return f'''<section class="insight-card trend-card" aria-label="Comment activity">
      <div class="insight-heading"><h2>Comment activity</h2><span>{clock_text(start)}–{clock_text(end)}</span></div>
      <svg viewBox="0 0 294 104" role="img" aria-label="{total} comments received, {answered} AI replies">
        <path d="M18 88H276 M18 50H276 M18 12H276" class="trend-grid" />
        <polyline points="{received_line}" class="trend-received" />
        <polyline points="{answered_line}" class="trend-answered" />
      </svg><div class="trend-legend"><span><i></i>Received {total}</span><span><i></i>AI replied {answered}</span></div></section>'''


def overview_markup(state, policy, total):
    m = dashboard_metrics(state, policy)
    wait = clock_text(m["longest_wait"]) if m["longest_wait"] is not None else "—"
    return f'''<div class="overview">
    <section class="overview-card"><div class="overview-heading"><h2>Backlog</h2><span>Received {m['received']} / {total} comments</span></div>
    <div class="overview-values"><div><strong>{m['waiting']}</strong><span>Awaiting reply</span></div>
    <div><strong>{m['unassigned']}</strong><span>Unassigned</span></div>
    <div class="metric-details"><span><b>{m['moderator']}</b> need support</span><span><b>{m['late']}</b> overdue</span></div></div></section>
    <section class="overview-card"><div class="overview-heading"><h2>Performance</h2><span>Session results</span></div>
    <div class="overview-values"><div><strong>{m['ai_replied']}</strong><span>AI replied</span></div>
    <div title="Actual response time not measured"><strong>—</strong><span>Response time</span></div>
    <div class="metric-details"><span><b>{m['mod_replied']}</b> moderator replies</span><span>Longest wait <b>{wait}</b> (min:sec)</span></div></div></section></div>'''


def question_rows(state, policy):
    """One row per actual FAQ group, plus non-FAQ routing buckets."""
    rows = []
    grouped = set()
    for group in state["groups"]:
        ids = group["comment_ids"]
        grouped.update(ids)
        rows.append((faq_topic_label(group["topic"]), group["faq_id"], [state["results"][cid] for cid in ids]))
    remaining = [r for cid, r in state["results"].items() if cid not in grouped]
    for title, route in [("Needs individual support", "ESCALATE"), ("No reply needed", "IGNORE")]:
        subset = [r for r in remaining if r.get("route") == route]
        if subset:
            rows.append((title, "Moderator" if route == "ESCALATE" else "Ignore", subset))
    return rows


def question_table_markup(rows, state, policy):
    body = []
    for title, source, records in rows:
        waiting = [r for r in records if r["status"] in PENDING]
        longest = max((state["demo_time"] - r["created_at"] for r in waiting), default=None)
        body.append(f'''<tr><th scope="row">{e(title)}</th>
        <td>{len(records)}</td><td>{sum(r['status'] == AI_REPLIED for r in records)}</td>
        <td>{sum(r['status'] == MOD_REPLIED for r in records)}</td><td>{len(waiting)}</td>
        <td>{sum(not r['assigned_to'] for r in waiting)}</td><td>{clock_text(longest) if longest is not None else '—'}</td></tr>''')
    if not body:
        body.append('<tr><td colspan="7" class="table-empty">No data yet · Run this scenario to begin</td></tr>')
    return '''<div class="question-table"><table><caption>Question category statistics</caption>
    <thead><tr><th scope="col">Question category</th><th scope="col">Comments</th><th scope="col">AI replied</th>
    <th scope="col">Moderator replied</th><th scope="col">Waiting</th><th scope="col">Unassigned</th><th scope="col">Longest wait</th></tr></thead>
    <tbody>''' + ''.join(body) + '</tbody></table></div>'

SCENES = {
    "01 · Gom FAQ": {
        "title": "Many questions. One approved answer.",
        "ids": ["C025", "C026", "C027", "C028", "C029"],
    },
    "02 · Moderator": {
        "title": "Questions needing advice go to a moderator.",
        "ids": ["C030", "C031", "C032", "C033", "C035"],
    },
    "03 · Hỏi tiếp": {
        "title": "Track follow-ups and overdue questions.",
        "ids": ["C025", "C029", "C041"],
    },
    "Phiên đầy đủ": {
        "title": "Gemini routes all 48 comments to FAQs or moderator support.",
        "ids": None,
    },
}


def scene_bundle(bundle, scene):
    ids = SCENES[scene]["ids"]
    return dict(bundle, comments=[c for c in bundle["comments"] if ids is None or c["comment_id"] in ids])


def prepare_scene(bundle, scene, agent, mode, model):
    state = new_session(mode, model)
    source = scene_bundle(bundle, scene)
    load_next(state, source, agent, len(source["comments"]))
    if scene == "03 · Hỏi tiếp":
        advance_time(state, bundle["policy"]["moderator_timeout_seconds"])
    return state


def clock_text(seconds):
    return f"{int(seconds) // 60:02}:{int(seconds) % 60:02}"


def e(value):
    return escape(str(value))


def badge(record, state, policy):
    if is_overdue(record, state["demo_time"], policy):
        return '<span class="badge amber">Overdue</span>'
    status = record["status"]
    if status == AI_REPLIED:
        return '<span class="badge teal">AI replied</span>'
    if status == MOD_REPLIED:
        return '<span class="badge teal">Moderator replied</span>'
    if status == MOD_WORKING:
        return '<span class="badge blue">In progress</span>'
    return '<span class="badge muted">' + e("Waiting for support" if record["route"] == "ESCALATE" else "No reply needed") + '</span>'


def comment_markup(records, state, policy):
    if not records:
        return empty("No comments yet", "Run this scenario or load 5 comments to begin.")
    cards = []
    for r in records:
        c = r["comment"]
        cards.append(f'''<article class="comment-card">
          <div class="card-line"><span class="person"><span class="avatar">{e(c['display_name'][:1])}</span><strong>{e(c['display_name'])}</strong></span><div class="small">{clock_text(c['at_seconds'])}</div></div>
          <div class="comment-bottom"><p class="comment-text">{e(c['text'])}</p>{badge(r, state, policy)}</div>
        </article>''')
    return '<div class="comment-list">' + ''.join(cards) + '</div>'


def group_markup(groups, products, state):
    if not groups:
        return empty("No FAQ groups yet", "Questions with approved answers appear here.")
    cards = []
    for g in groups:
        cards.append(f'''<article class="faq-card">
          <div class="card-line"><span>{e(products[g['product_id']])}</span><span class="badge teal">Answered</span></div>
          <h3>{e(faq_topic_label(g['topic']))}</h3>
          <div class="group-count"><strong>{len(g['user_ids'])}</strong> viewers asked <span>· {len(g['comment_ids'])} comment</span></div>
          <div class="approved-answer">{e(g['answer'])}</div>
          <div class="small answer-source">Reply from an approved FAQ</div>
        </article>''')
    return '<div class="faq-list">' + ''.join(cards) + '</div>'


def moderator_reply_markup(record, state):
    response = next(s for s in state["responses"] if s["response_id"] == record["response_id"])
    return f'''<article class="faq-card human-card">
          <div class="card-line"><span>Moderator</span><span class="badge blue">Answered</span></div>
      <h3>Moderator replied</h3>
      <p class="comment-text">{e(record['comment']['text'])}</p>
      <div class="approved-answer">{e(response['text'])}</div>
      <div class="small answer-source">{e(response['author'])} · {clock_text(response['at_seconds'])}</div>
    </article>'''


def history_markup(history, state, policy):
    if not history:
        return empty("No history yet", "Run scenario 03 to follow My’s questions.")
    cards = []
    for i, h in enumerate(history):
        r = state["results"][h["comment_id"]]
        response = h.get("response")
        cards.append(f'''<article class="timeline-item">
          <span class="timeline-dot">{i+1}</span><div class="timeline-body">
          <div class="card-line"><strong>Question {i+1} · {clock_text(h['at_seconds'])}</strong>{badge(r, state, policy)}</div>
          <p class="comment-text">{e(h['text'])}</p>
          <div class="timeline-answer">{e(response) if response else 'Waiting for a moderator · no reply yet'}</div></div>
        </article>''')
    return '<div class="viewer-heading"><span class="avatar">M</span><div><strong>My</strong><div class="small">3 questions in this session</div></div></div><div class="timeline">' + ''.join(cards) + '</div>'


def empty(title, description):
    return f'<div class="empty-state"><div class="empty-mark">· · ·</div><strong>{e(title)}</strong><p>{e(description)}</p></div>'
