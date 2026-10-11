"""Escaped, read-only markup for the TakaAI operations inbox."""

from presentation import clock_text, e
from workflow import AI_REPLIED, MOD_REPLIED, MOD_WAITING, MOD_WORKING, is_overdue


def status_view(record, state, policy):
    status = record["status"]
    if is_overdue(record, state["demo_time"], policy):
        return "Quá thời gian chờ", "amber"
    if status == AI_REPLIED:
        return "AI đã trả lời", "teal"
    if status == MOD_REPLIED:
        return "Đã hỗ trợ", "teal"
    if status == MOD_WORKING:
        return "Đang xử lý", "indigo"
    if status == MOD_WAITING:
        return "Cần hỗ trợ", "coral"
    return "Không cần trả lời", "muted"


def chip(label, tone):
    return f'<span class="status-chip {e(tone)}">{e(label)}</span>'


def conversation_markup(record, state, products, policy):
    comment = record["comment"]
    label, tone = status_view(record, state, policy)
    product = products.get(comment["active_product_id"], comment["active_product_id"])
    head = f'''<div class="conversation-heading"><div class="identity-avatar">{e(comment['display_name'][:1])}</div>
      <div class="identity-copy"><h2>{e(comment['display_name'])}</h2><p>{e(product)} · {clock_text(comment['at_seconds'])}</p></div>
      {chip(label, tone)}</div>
      <div class="conversation-question"><div class="message-label">Người xem hỏi</div><p>{e(comment['text'])}</p></div>'''
    response_id = record.get("response_id")
    if response_id:
        response = next((item for item in state["responses"] if item["response_id"] == response_id), None)
        if response:
            author = "TakaAI" if record["status"] == AI_REPLIED else "Người hỗ trợ"
            return head + f'''<div class="conversation-response"><div class="message-label">{e(author)} đã trả lời · {clock_text(response['at_seconds'])}</div>
              <p>{e(response['text'])}</p></div>'''
    if record["status"] in (MOD_WAITING, MOD_WORKING):
        assignee = record.get("assigned_to") or "Chưa phân công"
        return head + f'''<div class="handoff-note"><strong>Cần người hỗ trợ xem xét</strong>
            <p>{e(record.get('reason', 'Cần xác minh thêm.'))}</p><span>Phụ trách: {e(assignee)}</span></div>'''
    return head + '<div class="handoff-note quiet">Bình luận này không cần phản hồi.</div>'


def context_markup(record, state, bundle, products):
    faq_id = record.get("faq_id")
    faq = next((item for item in bundle["faqs"] if item["faq_id"] == faq_id), None)
    if faq:
        product = products.get(faq["product_id"], faq["product_id"])
        faq_block = f'''<section class="context-section"><div class="context-title"><span class="context-signal teal-dot"></span>FAQ phù hợp</div>
          <strong>{e(faq['topic'])}</strong><p>{e(product)}</p><div class="context-answer">{e(faq['approved_answer'])}</div></section>'''
    else:
        faq_block = '<section class="context-section"><div class="context-title"><span class="context-signal coral-dot"></span>FAQ phù hợp</div><p>Chưa có câu trả lời đã duyệt cho bình luận này.</p></section>'
    history = state["viewer_history"].get(record["comment"]["user_id"], [])
    history_items = ''.join(f'''<li><span>{clock_text(item['at_seconds'])}</span><p>{e(item['text'])}</p></li>'''
                            for item in history[-4:])
    history_block = f'''<section class="context-section"><div class="context-title">Lịch sử người xem <span class="context-count">{len(history)}</span></div>
      <ul class="context-history">{history_items or '<li>Chưa có câu hỏi nào.</li>'}</ul></section>'''
    return faq_block + history_block


def host_hint_markup(group, products):
    return f'''<section class="host-hint"><div class="context-title"><span class="context-signal indigo-dot"></span>Gợi ý cho host</div>
      <p><strong>{len(group['user_ids'])} người xem</strong> cùng hỏi về {e(group['topic'].lower())} của {e(products[group['product_id']])}.</p>
      <span>Có thể minh họa thêm trong phần giới thiệu sản phẩm.</span></section>'''
