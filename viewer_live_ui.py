"""Buyer LIVE surface backed by processed comments and approved FAQ offers."""

from presentation import clock_text, e
from workflow import AI_REPLIED, MOD_WAITING, MOD_WORKING

HOST_NAME = "Mây Skin"


def icon(name):
    paths = {
        "eye": '<path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6Z"/><circle cx="12" cy="12" r="2.5"/>',
        "heart": '<path d="M20.8 8.6c0 4.3-8.8 10-8.8 10s-8.8-5.7-8.8-10a4.7 4.7 0 0 1 8.8-2.1 4.7 4.7 0 0 1 8.8 2.1Z"/>',
        "comment": '<path d="M20 11.5a7.5 7.5 0 0 1-7.5 7.5H5l1.4-2.7A7.5 7.5 0 1 1 20 11.5Z"/>',
        "share": '<path d="m13 4 7 7-7 7v-4c-5 0-8 2-10 6 0-7 3-12 10-12V4Z"/>',
        "bag": '<path d="M4 9h16l-1 12H5L4 9Z"/><path d="M9 10V7a3 3 0 0 1 6 0v3"/>',
        "check": '<path d="m4 12 5 5L20 6"/>',
    }
    return f'<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{paths[name]}</svg>'


def selected_response(record, state):
    if not record or not record.get("response_id"):
        return None
    return next((response for response in state["responses"]
                 if response["response_id"] == record["response_id"]), None)


def format_vnd(value):
    return f"{value:,}".replace(",", ".") + "đ"


def buyer_phone_markup(state, selected, product, image_url, offer=None):
    """One LIVE frame shows real feed comments, a selected reply and approved combo."""
    records = list(state["results"].values())
    people = len({r["comment"]["user_id"] for r in records})
    viewer_label = f"{people}+ views" if people else "— views"
    feed = ''.join(
        f'<div class="viewer-feed-line"><b>{e(r["comment"]["display_name"])}</b>'
        f'<span>{e(r["comment"]["text"])}</span></div>' for r in records[-5:]
    ) or '<div class="viewer-feed-empty">Comments will appear when the session starts.</div>'
    response = selected_response(selected, state)
    if selected:
        question = selected["comment"]
        viewer = e(question["display_name"])
        question_text = e(question["text"])
        time = clock_text(question["at_seconds"])
        buyer_message = f'''<div class="viewer-question"><span class="viewer-question-avatar">{e(question['display_name'][:1])}</span>
          <div><span><b>{viewer}</b><small>{time}</small></span><p>{question_text}</p></div></div>'''
        if response:
            who = "TakaAI" if selected["status"] == AI_REPLIED else "Moderator"
            answer = f'''<div class="viewer-answer"><div class="viewer-answer-head"><span class="viewer-ai-avatar">AI</span>
              <b>{e(who)} replied</b><span>{icon('check')} {clock_text(response['at_seconds'])}</span></div>
              <p>{e(response['text'])}</p></div>'''
        elif selected["status"] in (MOD_WAITING, MOD_WORKING):
            answer = '''<div class="viewer-answer viewer-handoff"><div class="viewer-answer-head"><span class="viewer-ai-avatar">AI</span>
              <b>TakaAI</b></div><p>Mình đã chuyển câu hỏi của bạn cho người hỗ trợ. Bạn sẽ nhận phản hồi tại đây.</p></div>'''
        else:
            answer = '<div class="viewer-awaiting">Your comment has been received.</div>'
    else:
        buyer_message = '<div class="viewer-awaiting">Run a scenario or ask a question to see a reply here.</div>'
        answer = ''
    approved_offer = bool(selected and selected["status"] == AI_REPLIED and offer
                          and selected.get("product_id") == offer["product_id"])
    offer_data = offer["offer"] if approved_offer else None
    if offer_data:
        saved = offer_data["primary_price_vnd"] + offer_data["companion_price_vnd"] - offer_data["combo_price_vnd"]
        offer_badge = f'<div class="viewer-deal-ribbon">LIVE COMBO <strong>Tiết kiệm {format_vnd(saved)}</strong></div>'
        offer_card = f'''<div class="viewer-offer"><span>{icon('bag')}</span><div><small>TAKAAI RECOMMENDS</small>
          <b>{e(product)} + {e(offer_data['companion_product'])}</b>
          <em>Mua lẻ {format_vnd(offer_data['primary_price_vnd'] + offer_data['companion_price_vnd'])} · Combo {format_vnd(offer_data['combo_price_vnd'])}</em></div>
          <strong>−{format_vnd(saved)}</strong></div>'''
    else:
        offer_badge = ''
        offer_card = ''
    media = (f'<video class="live-viewer-photo" src="{image_url}" autoplay muted loop playsinline '
             'aria-label="LIVE creator video"></video>' if image_url.startswith("data:video/") else
             f'<img class="live-viewer-photo" src="{image_url}" alt="Creator presenting sunscreen during LIVE" />')
    return f'''<div class="live-viewer" aria-label="LIVE viewer screen">
      {media}
      <div class="live-viewer-shade"></div>
      <div class="live-viewer-top"><div class="live-viewer-host"><span class="live-host-avatar">M</span>
        <span><b>{HOST_NAME}</b><small>Skincare · {people} commenters</small></span></div>
        <span class="live-follow">+ Follow</span><span class="live-close" aria-hidden="true">×</span></div>
      <div class="live-viewer-meta"><span class="viewer-live-badge">LIVE</span><span>{icon('eye')} {viewer_label}</span>
        <span>{len(records)} comments</span></div>{offer_badge}
      <div class="live-viewer-bottom"><div class="viewer-feed" aria-label="Recent comments">{feed}</div>
        <div class="viewer-side-actions" aria-label="LIVE interaction controls">
          <span title="Like count unavailable">{icon('heart')}<small>Like</small></span>
          <span title="Processed comments">{icon('comment')}<small>{len(records)}</small></span>
          <span title="Share count unavailable">{icon('share')}<small>Share</small></span></div>
        <div class="viewer-thread"><span class="viewer-thread-title">ASK TAKA AI DURING LIVE</span>
          {buyer_message}{answer}{offer_card}</div>
      </div></div>'''
