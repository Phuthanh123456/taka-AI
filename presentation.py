"""Small replay scenes and escaped dashboard markup, independent of Streamlit."""
from html import escape
from collections import Counter
from replay import new_session, load_next, advance_time
from workflow import AI_REPLIED, MOD_REPLIED, MOD_WORKING, MOD_WAITING, PENDING, is_overdue


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
                f'<span class="classification-item faq-item"><i></i><span>{e(faq["topic"])}</span><b>{count}</b></span>')
    if route_counts["ESCALATE"]:
        items.append(
            f'<span class="classification-item support-item"><i></i><span>Cần moderator</span><b>{route_counts["ESCALATE"]}</b></span>')
    if route_counts["IGNORE"]:
        items.append(
            f'<span class="classification-item ignore-item"><i></i><span>Không cần phản hồi</span><b>{route_counts["IGNORE"]}</b></span>')
    content = ''.join(items) or '<span class="classification-empty">Chạy kịch bản để Gemini phân loại comment.</span>'
    return f'''<section class="classification-summary" aria-label="Tổng hợp phân loại bình luận">
      <div class="classification-heading"><strong>Phân loại comment</strong>
        <span>{processed} / {total} đã xử lý</span></div>
      <div class="classification-items">{content}
        {f'<span class="classification-followups"><i></i>{followups} lượt hỏi tiếp</span>' if followups else ''}
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
    return f'''<section class="insight-card route-card" aria-label="Tuyến xử lý bình luận">
      <div class="insight-heading"><h2>Tuyến xử lý</h2><span>{total} đã nhận</span></div>
      <div class="route-visual"><div class="route-donut" style="--auto-end:{auto_end}%;--support-end:{support_end}%">
        <div><strong>{total}</strong><span>bình luận</span></div></div>
        <div class="route-legend">
          <div><i class="legend-auto"></i><span>AI trả lời</span><strong>{auto}</strong></div>
          <div><i class="legend-support"></i><span>Cần hỗ trợ</span><strong>{support}</strong></div>
          <div><i class="legend-ignored"></i><span>Không cần phản hồi</span><strong>{ignored}</strong></div>
        </div></div></section>'''


def activity_trend_markup(state):
    """Cumulative received and AI-answered comments by replay timestamp."""
    records = sorted(state["results"].values(), key=lambda r: r["comment"]["at_seconds"])
    if not records:
        return '''<section class="insight-card trend-card"><div class="insight-heading"><h2>Nhịp bình luận</h2></div>
          <p class="trend-empty">Chưa có bình luận trong phiên.</p></section>'''
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
    return f'''<section class="insight-card trend-card" aria-label="Nhịp xử lý bình luận">
      <div class="insight-heading"><h2>Nhịp bình luận</h2><span>{clock_text(start)}–{clock_text(end)}</span></div>
      <svg viewBox="0 0 294 104" role="img" aria-label="{total} bình luận đã nhận, {answered} câu AI trả lời">
        <path d="M18 88H276 M18 50H276 M18 12H276" class="trend-grid" />
        <polyline points="{received_line}" class="trend-received" />
        <polyline points="{answered_line}" class="trend-answered" />
      </svg><div class="trend-legend"><span><i></i>Đã nhận {total}</span><span><i></i>AI trả lời {answered}</span></div></section>'''


def overview_markup(state, policy, total):
    m = dashboard_metrics(state, policy)
    wait = clock_text(m["longest_wait"]) if m["longest_wait"] is not None else "—"
    return f'''<div class="overview">
    <section class="overview-card"><div class="overview-heading"><h2>Backlog</h2><span>Đã nhận {m['received']} / {total} bình luận</span></div>
    <div class="overview-values"><div><strong>{m['waiting']}</strong><span>Chờ phản hồi</span></div>
    <div><strong>{m['unassigned']}</strong><span>Chưa phân công</span></div>
    <div class="metric-details"><span><b>{m['moderator']}</b> cần hỗ trợ</span><span><b>{m['late']}</b> quá thời gian chờ</span></div></div></section>
    <section class="overview-card"><div class="overview-heading"><h2>Performance</h2><span>Kết quả trong phiên</span></div>
    <div class="overview-values"><div><strong>{m['ai_replied']}</strong><span>AI đã trả lời</span></div>
    <div title="Chưa đo thời gian phản hồi thực tế"><strong>—</strong><span>Thời gian phản hồi</span></div>
    <div class="metric-details"><span><b>{m['mod_replied']}</b> người hỗ trợ đã trả lời</span><span>Chờ lâu nhất <b>{wait}</b> (phút:giây)</span></div></div></section></div>'''


def question_rows(state, policy):
    """One row per actual FAQ group, plus non-FAQ routing buckets."""
    rows = []
    grouped = set()
    for group in state["groups"]:
        ids = group["comment_ids"]
        grouped.update(ids)
        rows.append((group["topic"], group["faq_id"], [state["results"][cid] for cid in ids]))
    remaining = [r for cid, r in state["results"].items() if cid not in grouped]
    for title, route in [("Cần hỗ trợ riêng", "ESCALATE"), ("Không cần trả lời", "IGNORE")]:
        subset = [r for r in remaining if r.get("route") == route]
        if subset:
            rows.append((title, "Moderator" if route == "ESCALATE" else "Bỏ qua", subset))
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
        body.append('<tr><td colspan="7" class="table-empty">Chưa có dữ liệu · Chạy cảnh này để bắt đầu</td></tr>')
    return '''<div class="question-table"><table><caption>Thống kê theo nhóm câu hỏi</caption>
    <thead><tr><th scope="col">Nhóm câu hỏi</th><th scope="col">Bình luận</th><th scope="col">AI đã trả lời</th>
    <th scope="col">Hỗ trợ đã trả lời</th><th scope="col">Đang chờ</th><th scope="col">Chưa phân công</th><th scope="col">Chờ lâu nhất</th></tr></thead>
    <tbody>''' + ''.join(body) + '</tbody></table></div>'

SCENES = {
    "01 · Gom FAQ": {
        "title": "Nhiều cách hỏi. Một đáp án đã duyệt.",
        "ids": ["C025", "C026", "C027", "C028", "C029"],
    },
    "02 · Moderator": {
        "title": "Câu cần tư vấn được chuyển đến người hỗ trợ.",
        "ids": ["C030", "C031", "C032", "C033", "C035"],
    },
    "03 · Hỏi tiếp": {
        "title": "Theo dõi từng câu hỏi. Nhắc câu đang chờ lâu.",
        "ids": ["C025", "C029", "C041"],
    },
    "Phiên đầy đủ": {
        "title": "Gemini phân loại toàn bộ 48 comment theo FAQ và hỗ trợ.",
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
        return '<span class="badge amber">Quá thời gian chờ</span>'
    status = record["status"]
    if status == AI_REPLIED:
        return '<span class="badge teal">AI đã trả lời</span>'
    if status == MOD_REPLIED:
        return '<span class="badge teal">Đã được hỗ trợ</span>'
    if status == MOD_WORKING:
        return '<span class="badge blue">Đang xử lý</span>'
    return '<span class="badge muted">' + e("Chờ hỗ trợ" if record["route"] == "ESCALATE" else "Không cần trả lời") + '</span>'


def comment_markup(records, state, policy):
    if not records:
        return empty("Chưa có comment", "Bấm Chạy cảnh này hoặc Nạp 5 câu để bắt đầu.")
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
        return empty("Chưa có nhóm FAQ", "Câu có đáp án đã duyệt sẽ xuất hiện tại đây.")
    cards = []
    for g in groups:
        cards.append(f'''<article class="faq-card">
          <div class="card-line"><span>{e(products[g['product_id']])}</span><span class="badge teal">Đã trả lời</span></div>
          <h3>{e(g['topic'])}</h3>
          <div class="group-count"><strong>{len(g['user_ids'])}</strong> người hỏi <span>· {len(g['comment_ids'])} comment</span></div>
          <div class="approved-answer">{e(g['answer'])}</div>
          <div class="small answer-source">Trả lời theo FAQ đã duyệt</div>
        </article>''')
    return '<div class="faq-list">' + ''.join(cards) + '</div>'


def moderator_reply_markup(record, state):
    response = next(s for s in state["responses"] if s["response_id"] == record["response_id"])
    return f'''<article class="faq-card human-card">
          <div class="card-line"><span>Người hỗ trợ</span><span class="badge blue">Đã trả lời</span></div>
      <h3>Moderator đã trả lời</h3>
      <p class="comment-text">{e(record['comment']['text'])}</p>
      <div class="approved-answer">{e(response['text'])}</div>
      <div class="small answer-source">{e(response['author'])} · {clock_text(response['at_seconds'])}</div>
    </article>'''


def history_markup(history, state, policy):
    if not history:
        return empty("Chưa có lịch sử", "Chạy cảnh 03 để theo dõi các câu hỏi của My.")
    cards = []
    for i, h in enumerate(history):
        r = state["results"][h["comment_id"]]
        response = h.get("response")
        cards.append(f'''<article class="timeline-item">
          <span class="timeline-dot">{i+1}</span><div class="timeline-body">
          <div class="card-line"><strong>Lượt {i+1} · {clock_text(h['at_seconds'])}</strong>{badge(r, state, policy)}</div>
          <p class="comment-text">{e(h['text'])}</p>
          <div class="timeline-answer">{e(response) if response else 'Chờ người hỗ trợ · chưa có phản hồi'}</div></div>
        </article>''')
    return '<div class="viewer-heading"><span class="avatar">M</span><div><strong>My</strong><div class="small">3 lượt hỏi trong phiên</div></div></div><div class="timeline">' + ''.join(cards) + '</div>'


def empty(title, description):
    return f'<div class="empty-state"><div class="empty-mark">· · ·</div><strong>{e(title)}</strong><p>{e(description)}</p></div>'
