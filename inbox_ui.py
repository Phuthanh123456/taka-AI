"""Escaped, read-only markup for the TakaAI operations inbox."""

from presentation import clock_text, e
from workflow import AI_REPLIED, MOD_REPLIED, MOD_WAITING, MOD_WORKING, is_overdue


FAQ_TOPIC_LABELS = {
    "Thành phần công bố": "Listed ingredients",
    "Chỉ số SPF trên nhãn": "Label SPF",
    "Dung tích": "Volume",
    "Combo ưu đãi": "Combo offer",
}


def faq_topic_label(topic):
    return FAQ_TOPIC_LABELS.get(topic, topic)


def status_view(record, state, policy):
    status = record["status"]
    if is_overdue(record, state["demo_time"], policy):
        return "Overdue", "amber"
    if status == AI_REPLIED:
        return "AI replied", "teal"
    if status == MOD_REPLIED:
        return "Moderator replied", "teal"
    if status == MOD_WORKING:
        return "In progress", "indigo"
    if status == MOD_WAITING:
        return "Needs support", "coral"
    return "No reply needed", "muted"


def chip(label, tone):
    return f'<span class="status-chip {e(tone)}">{e(label)}</span>'


def conversation_markup(record, state, products, policy):
    comment = record["comment"]
    label, tone = status_view(record, state, policy)
    product = products.get(comment["active_product_id"], comment["active_product_id"])
    head = f'''<div class="conversation-heading"><div class="identity-avatar">{e(comment['display_name'][:1])}</div>
      <div class="identity-copy"><h2>{e(comment['display_name'])}</h2><p>{e(product)} · {clock_text(comment['at_seconds'])}</p></div>
      {chip(label, tone)}</div>
      <div class="conversation-question"><div class="message-label">Viewer asked</div><p>{e(comment['text'])}</p></div>'''
    response_id = record.get("response_id")
    if response_id:
        response = next((item for item in state["responses"] if item["response_id"] == response_id), None)
        if response:
            author = "TakaAI" if record["status"] == AI_REPLIED else "Moderator"
            return head + f'''<div class="conversation-response"><div class="message-label">{e(author)} replied · {clock_text(response['at_seconds'])}</div>
              <p>{e(response['text'])}</p></div>'''
    if record["status"] in (MOD_WAITING, MOD_WORKING):
        assignee = record.get("assigned_to") or "Unassigned"
        return head + f'''<div class="handoff-note"><strong>Moderator review needed</strong>
            <p>{e(record.get('reason', 'Further verification needed.'))}</p><span>Assigned to: {e(assignee)}</span></div>'''
    return head + '<div class="handoff-note quiet">This comment needs no reply.</div>'


def context_markup(record, state, bundle, products):
    faq_id = record.get("faq_id")
    faq = next((item for item in bundle["faqs"] if item["faq_id"] == faq_id), None)
    if faq:
        product = products.get(faq["product_id"], faq["product_id"])
        faq_block = f'''<section class="context-section"><div class="context-title"><span class="context-signal teal-dot"></span>Matching FAQ</div>
          <strong>{e(faq_topic_label(faq['topic']))}</strong><p>{e(product)}</p><div class="context-answer">{e(faq['approved_answer'])}</div></section>'''
    else:
        faq_block = '<section class="context-section"><div class="context-title"><span class="context-signal coral-dot"></span>Matching FAQ</div><p>No approved answer is available for this comment.</p></section>'
    history = state["viewer_history"].get(record["comment"]["user_id"], [])
    history_items = ''.join(f'''<li><span>{clock_text(item['at_seconds'])}</span><p>{e(item['text'])}</p></li>'''
                            for item in history[-4:])
    history_block = f'''<section class="context-section"><div class="context-title">Viewer history <span class="context-count">{len(history)}</span></div>
      <ul class="context-history">{history_items or '<li>No questions yet.</li>'}</ul></section>'''
    return faq_block + history_block


def host_hint_markup(group, products):
    return f'''<section class="host-hint"><div class="context-title"><span class="context-signal indigo-dot"></span>Host insight</div>
      <p><strong>{len(group['user_ids'])} viewers</strong> asked about {e(faq_topic_label(group['topic']).lower())} for {e(products[group['product_id']])}.</p>
      <span>Consider addressing this during the product showcase.</span></section>'''
