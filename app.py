"""TakaAI operations inbox; replay and routing remain in their existing modules."""

import base64
import os
from pathlib import Path

import streamlit as st

from agent import DEFAULT_MODEL, GeminiAgent
from data_loader import load_bundle
from inbox_ui import chip, context_markup, conversation_markup, host_hint_markup, status_view
from viewer_live_ui import buyer_phone_markup, format_vnd
from presentation import (SCENES, activity_trend_markup, classification_summary_markup,
                          clock_text, dashboard_metrics, e, prepare_scene,
                          routing_breakdown_markup, scene_bundle)
from replay import advance_time, load_next, new_session
from workflow import AI_REPLIED, MOD_WAITING, MOD_WORKING, claim, host_prompts, is_overdue, moderator_reply, process_comment, refer


ROOT = Path(__file__).resolve().parent
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


st.set_page_config(page_title="TakaAI · LIVE Dashboard", layout="wide", initial_sidebar_state="expanded")
st.html('<style>' + (ROOT / 'dashboard.css').read_text(encoding='utf-8-sig') + '</style>')


def setting(name, default=""):
    if os.getenv(name):
        return os.getenv(name)
    try:
        return st.secrets.get(name, default)
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default


@st.cache_data
def get_bundle(data_fingerprint):
    return load_bundle()


def clear_task_widgets():
    for key in list(st.session_state):
        if key.startswith(('task_', 'view_', 'inbox_selected_', 'comment_filter_', 'buyer_cart_')):
            del st.session_state[key]


def first_focus(session):
    pending = [item for item in session['results'].values()
               if item['status'] in (MOD_WAITING, MOD_WORKING)]
    if pending:
        active = session['comments'][-1]['active_product_id'] if session['comments'] else None
        matching = next((item for item in pending if item['comment']['active_product_id'] == active), None)
        if matching:
            return matching['comment_id']
        return pending[0]['comment_id']
    return next(iter(session['results']), None)


def first_buyer_reply(session):
    return next((item['comment_id'] for item in session['results'].values()
                 if item['status'] == AI_REPLIED and item.get('faq_id') == 'B_COMBO'),
                next((item['comment_id'] for item in session['results'].values()
                      if item['status'] == AI_REPLIED), first_focus(session)))


@st.cache_data
def image_data_url(path):
    return 'data:image/png;base64,' + base64.b64encode(Path(path).read_bytes()).decode('ascii')


def moderation_actions(selected, state, moderator_name):
    if not selected:
        return
    cid = selected['comment_id']
    if selected['status'] == MOD_WAITING:
        if st.button('Claim case', key=f'task_claim_{cid}', type='primary', use_container_width=True):
            try:
                claim(state, cid, moderator_name)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    elif selected['status'] == MOD_WORKING:
        with st.form(f'task_reply_{cid}'):
            reply_text = st.text_area('Moderator reply', key=f'task_text_{cid}', height=80,
                                      placeholder='Enter your reply to the viewer…')
            if st.form_submit_button('Send reply', use_container_width=True):
                try:
                    moderator_reply(state, cid, reply_text)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        with st.popover('Escalate for review'):
            note = st.text_input('Details to verify', key=f'task_note_{cid}')
            if st.button('Submit for review', key=f'task_refer_{cid}'):
                try:
                    refer(state, cid, note)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if selected.get('referral'):
            st.info(f"Sent for review: {selected['referral']}")


def classification_key(record):
    if record.get('route') == 'AUTO':
        return f"faq:{record.get('faq_id')}"
    if record.get('route') == 'ESCALATE':
        return 'moderator'
    return 'ignore'


try:
    data_fingerprint = tuple((ROOT / 'data' / f'{name}.json').stat().st_mtime_ns
                             for name in ('products', 'faqs', 'comments', 'policy'))
    bundle = get_bundle(data_fingerprint)
except (OSError, ValueError, KeyError, AssertionError, TypeError) as exc:
    st.error(f"Could not load data: {exc}")
    st.stop()
if st.session_state.get('loaded_data_fingerprint') != data_fingerprint:
    clear_task_widgets()
    st.session_state.pop('scene_sessions', None)
    st.session_state.loaded_data_fingerprint = data_fingerprint

configured_api_key = setting('GEMINI_API_KEY') or setting('GOOGLE_API_KEY')
api_key = configured_api_key or st.session_state.get('gemini_api_key_input', '').strip()
model = setting('GEMINI_MODEL', DEFAULT_MODEL)
default_mode = 'Gemini API'
if 'scene_sessions' not in st.session_state:
    st.session_state.scene_sessions = {name: new_session(default_mode, model) for name in SCENES}
elif any(session.get('mode') != default_mode for session in st.session_state.scene_sessions.values()):
    # Clear results created by the old rule-mode UI so they cannot appear as Gemini output.
    st.session_state.scene_sessions = {name: new_session(default_mode, model) for name in SCENES}
# Make the full-session inbox the landing view for new visitors and for the
# first rerun after this deployment, while keeping later user selections.
if st.session_state.get('landing_scene_version') != 'full-session-first-v1':
    st.session_state.scene_choice = 'Phiên đầy đủ'
    st.session_state.landing_scene_version = 'full-session-first-v1'
if 'sidebar_open' not in st.session_state:
    st.session_state.sidebar_open = True

scene = st.session_state.scene_choice
full_scene = scene == 'Phiên đầy đủ'
state = st.session_state.scene_sessions[scene]
st.session_state.live_session = state
source = scene_bundle(bundle, scene)
policy = bundle['policy']
products = {item['product_id']: product_label(item['product_id'], item['name']) for item in bundle['products']}

if not st.session_state.sidebar_open:
    st.html('<style>[data-testid="stSidebar"]{display:none!important;}</style>')
else:
    # Keep the menu visible when Streamlit changes its native sidebar to a drawer.
    st.html('''<style>
    @media (max-width:900px) {
      [data-testid="stSidebar"] {display:block!important;position:fixed!important;inset:0 auto 0 0!important;
        width:154px!important;min-width:154px!important;max-width:154px!important;height:100vh!important;transform:none!important;z-index:999991!important;}
      [data-testid="stMain"] {margin-left:154px!important;width:calc(100% - 154px)!important;}
    }
    @media (min-width:901px) {
      [data-testid="stAppViewContainer"]:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stSidebar"] {
        display:block!important;position:fixed!important;inset:0 auto 0 0!important;width:154px!important;min-width:154px!important;
        max-width:154px!important;height:100vh!important;transform:none!important;z-index:999991!important;}
      [data-testid="stAppViewContainer"]:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stMain"] {
        margin-left:154px!important;width:calc(100% - 154px)!important;}
    }
    </style>''')

with st.sidebar:
    mascot = base64.b64encode((ROOT / 'assets' / 'takaai-mascot.png').read_bytes()).decode('ascii')
    st.html(f'''<div class="brand-lockup"><img class="brand-photo" src="data:image/png;base64,{mascot}" alt="Mascot AI TakaAI" />
      <span><strong>TakaAI</strong><small>OPERATIONS INBOX</small></span></div>''')
    st.html('<div class="sidebar-section-label">SCENARIOS</div>')
    scene_order = ['Phiên đầy đủ', *[name for name in SCENES if name != 'Phiên đầy đủ']]
    st.radio('Choose scenario', scene_order, format_func=lambda value: {
        '01 · Gom FAQ': 'Group questions',
        '02 · Moderator': 'Moderator support',
        '03 · Hỏi tiếp': 'Follow-up questions',
        'Phiên đầy đủ': 'Full session',
    }[value], key='scene_choice', label_visibility='collapsed')
    st.html(f'<div class="sidebar-scene"><span>NOW VIEWING</span><strong>{e(SCENES[scene]["title"])}</strong></div>')
    if st.session_state.sidebar_open and st.button('Collapse menu', key='sidebar_toggle', use_container_width=True, type='tertiary'):
        st.session_state.sidebar_open = False
        st.rerun()
if st.session_state.scene_choice != scene:
    st.rerun()

if st.session_state.sidebar_open:
    header_main = st.container()
else:
    header_toggle, header_main = st.columns([0.12, 0.88], gap='small', vertical_alignment='center')
    with header_toggle:
        if st.button('Show menu', key='sidebar_toggle', type='tertiary'):
            st.session_state.sidebar_open = True
            st.rerun()
with header_main:
    visible_mode = f"Gemini · {state['model'] or model}" if api_key else 'Gemini not connected'
    st.html(f'''<header class="inbox-header"><div><span class="overline">TAKAAI / LIVE SESSION</span>
      <h1>LIVE Dashboard <span class="live-indicator"><i></i> LIVE</span></h1></div>
      <div class="session-meta"><span>{e(visible_mode)}</span><strong>{clock_text(state['demo_time'])}</strong></div></header>''')

toolbar_main, toolbar_tools, toolbar_settings, toolbar_guide = st.columns([1.7, 1.0, 1.0, 1.0], gap='small')
with toolbar_main:
    prepare_clicked = st.button('Run scenario', key='prepare_scene', type='primary', use_container_width=True)
with toolbar_tools:
    with st.popover('Session controls', use_container_width=True):
        load_clicked = st.button('Load 5 comments', key='load_next', disabled=state['next_index'] >= len(source['comments']), use_container_width=True)
        time_clicked = st.button('Advance 30 seconds', key='advance_time', use_container_width=True)
        reset_clicked = st.button('Restart session', key='reset_scene', use_container_width=True)
with toolbar_settings:
    with st.popover('Settings', use_container_width=True):
        st.markdown('**Processor: Gemini API**')
        moderator_name = st.text_input('Moderator name', value='Moderator', key='moderator_name')
        live_media = st.file_uploader('Replace LIVE image or video (optional)',
                                      type=['mp4', 'webm', 'mov', 'jpg', 'jpeg', 'png'],
                                      key='live_media')
        st.caption('Gemini classifies each sample comment against approved FAQs.')
        if not configured_api_key:
            api_key_input = st.text_input('Gemini API key', type='password',
                                          key='gemini_api_key_input',
                                          placeholder='Paste your API key here')
            api_key = api_key_input.strip()
            if not api_key:
                st.info('Enter a key to use Gemini. It stays only in this browser session.')
        st.caption(f'Pretrained model: {model}. Comments come from data/comments.json; replies come from approved FAQs.')
        reset_all_clicked = st.button('Clear all scenario results', key='reset_all')
with toolbar_guide:
    with st.popover('Scenario guide', use_container_width=True):
        st.write('1. Group questions: review FAQ replies and host prompts.')
        st.write('2. Moderator support: claim a case and send a reply.')
        st.write('3. Follow-ups: review viewer history and overdue cases.')

selected_key = f'inbox_selected_{scene}'
if reset_all_clicked:
    clear_task_widgets()
    st.session_state.scene_sessions = {name: new_session(default_mode, model) for name in SCENES}
    st.rerun()
if reset_clicked or prepare_clicked:
    clear_task_widgets()
    if prepare_clicked:
        if not api_key:
            st.error('Gemini API key missing. Open Settings, enter a key, then run the scenario.')
        else:
            agent = GeminiAgent(api_key, model)
            with st.spinner(f"Gemini is classifying {len(source['comments'])} comments…"):
                session = prepare_scene(bundle, scene, agent, default_mode, model)
            st.session_state.scene_sessions[scene] = session
            st.session_state[selected_key] = first_buyer_reply(session) if full_scene else first_focus(session)
            st.rerun()
    else:
        st.session_state.scene_sessions[scene] = new_session(default_mode, model)
        st.rerun()
if time_clicked:
    advance_time(state)
    st.rerun()
if load_clicked:
    if not api_key:
        st.error('Gemini API key missing. Open Settings, enter a key, then load comments.')
    else:
        state['mode'] = default_mode
        state['model'] = model
        agent = GeminiAgent(api_key, model)
        count_to_load = min(5, len(source['comments']) - state['next_index'])
        with st.spinner(f"Gemini is classifying the next {count_to_load} comments…"):
            load_next(state, source, agent, count_to_load)
        st.session_state[selected_key] = first_buyer_reply(state) if full_scene else first_focus(state)
        st.rerun()

records = list(state['results'].values())
metrics = dashboard_metrics(state, policy)
scene_total = len(source['comments']) + state.get('buyer_comment_seq', 0)
st.html(f'''<section class="live-hero" aria-label="LIVE session overview">
  <div class="hero-intro"><span class="hero-eyebrow">SESSION OVERVIEW</span>
    <strong>Comments processed</strong><span>Current scenario data</span></div>
  <div class="hero-total"><strong>{metrics['received']}</strong><span>/ {scene_total} comments</span></div>
  <div class="hero-stats">
    <div><span>AI replied</span><strong>{metrics['ai_replied']}</strong></div>
    <div><span>Needs support</span><strong>{metrics['moderator']}</strong></div>
    <div><span>Overdue</span><strong>{metrics['late']}</strong></div>
  </div></section>''')
st.html(classification_summary_markup(state, bundle, scene_total))

faq_by_id = {faq['faq_id']: faq for faq in bundle['faqs']}
filter_labels = {'all': f"All comments ({len(records)})"}
filter_options = ['all']
for faq in bundle['faqs']:
    key = f"faq:{faq['faq_id']}"
    count = sum(item.get('route') == 'AUTO' and item.get('faq_id') == faq['faq_id'] for item in records)
    if count:
        filter_options.append(key)
        filter_labels[key] = f"FAQ · {faq_topic_label(faq['topic'])} ({count})"
moderator_count = sum(item.get('route') == 'ESCALATE' for item in records)
ignored_count = sum(item.get('route') == 'IGNORE' for item in records)
followup_count = sum(bool(item.get('context')) for item in records)
if moderator_count:
    filter_options.append('moderator')
    filter_labels['moderator'] = f'Needs moderator ({moderator_count})'
if ignored_count:
    filter_options.append('ignore')
    filter_labels['ignore'] = f'No reply needed ({ignored_count})'
if followup_count:
    filter_options.append('followup')
    filter_labels['followup'] = f'Follow-up questions ({followup_count})'

filter_key = f'comment_filter_{scene}'
page_size = 10
page_key = f'view_comments_{scene}'
buyer_jump = st.session_state.pop('buyer_jump', None)
if buyer_jump and buyer_jump['scene'] == scene:
    st.session_state[filter_key] = 'all'
    st.session_state[page_key] = buyer_jump['page']
if st.session_state.get(filter_key) not in filter_options:
    st.session_state[filter_key] = 'all'
active_filter = st.session_state[filter_key]
if active_filter == 'all':
    filtered_records = records
elif active_filter == 'followup':
    filtered_records = [item for item in records if item.get('context')]
else:
    filtered_records = [item for item in records if classification_key(item) == active_filter]

pages = max(1, (len(filtered_records) + page_size - 1) // page_size)
if st.session_state.get(page_key, 0) >= pages:
    st.session_state[page_key] = 0

selected_id = st.session_state.get(selected_key)
if selected_id not in state['results']:
    selected_id = first_buyer_reply(state) if full_scene else first_focus(state)
if selected_id and selected_id not in {item['comment_id'] for item in filtered_records}:
    selected_id = filtered_records[0]['comment_id'] if filtered_records else None
st.session_state[selected_key] = selected_id
selected = state['results'].get(selected_id)
pending = [item for item in records if item['status'] in (MOD_WAITING, MOD_WORKING)]
pending.sort(key=lambda item: (not is_overdue(item, state['demo_time'], policy), item['created_at']))
phone_image_url = image_data_url(str(ROOT / 'assets' / 'live-health-beauty-sunscreen.png')) if full_scene else None
if full_scene and live_media is not None and live_media.type.startswith(('image/', 'video/')):
    phone_image_url = f"data:{live_media.type};base64,{base64.b64encode(live_media.getvalue()).decode('ascii')}"

with st.container(key='workspace'):
    if full_scene:
        st.html('<span class="full-session-marker" hidden></span>')
    live_column, inbox_column, detail_column, context_column = st.columns([0.95, 1.25, 1.45, 0.92], gap='small')
    with live_column:
        if not full_scene:
            with st.container(key='panel_live'):
                st.html('<div class="pane-heading"><h2>LIVE view</h2><span class="live-pane-state"><i></i> LIVE</span></div>')
                if live_media is not None:
                    if live_media.type.startswith('video/'):
                        st.video(live_media, format=live_media.type)
                    else:
                        st.image(live_media, width='stretch')
                    active_comment = records[-1] if records else None
                    active_product_id = (active_comment['comment']['active_product_id'] if active_comment
                                         else source['comments'][0]['active_product_id'])
                    product_caption = 'FEATURED PRODUCT'
                else:
                    st.image(str(ROOT / 'assets' / 'live-health-beauty-sunscreen.png'), width='stretch')
                    active_product_id = 'SUN_B'
                    product_caption = 'PRODUCT IN VIEW'
                st.html(f'''<div class="live-product-strip"><span>{product_caption}</span>
                    <strong>{e(products.get(active_product_id, active_product_id))}</strong></div>''')
    with inbox_column, st.container(key='panel_inbox'):
        st.html(f'<div class="pane-heading"><h2>Comments</h2><span>{len(records)} / {scene_total} processed</span></div>')
        st.selectbox('Filter comments by group', filter_options,
                     format_func=lambda value: filter_labels[value], key=filter_key,
                     label_visibility='collapsed')
        if pages > 1:
            page = st.selectbox('Comments page', range(pages),
                                format_func=lambda number: f"{number * page_size + 1}–{min((number + 1) * page_size, len(filtered_records))} / {len(filtered_records)}",
                                key=page_key, label_visibility='collapsed')
        else:
            page = 0
        visible = filtered_records[page * page_size:(page + 1) * page_size]
        if not visible:
            st.html('<div class="inbox-empty"><strong>No comments yet</strong><p>Run the scenario to let Gemini classify sample comments.</p></div>')
        for item in visible:
            comment = item['comment']
            cid = item['comment_id']
            label, tone = status_view(item, state, policy)
            faq = faq_by_id.get(item.get('faq_id'))
            category = f"FAQ · {faq_topic_label(faq['topic'])}" if faq else ('Needs moderator' if item.get('route') == 'ESCALATE' else 'No reply needed')
            row_type = 'active' if cid == selected_id else 'idle'
            with st.container(key=f'row_{row_type}_{cid}'):
                st.html(f'''<div class="inbox-row-top"><span class="avatar-mini">{e(comment['display_name'][:1])}</span>
                <strong>{e(comment['display_name'])}</strong><span class="inbox-time">{clock_text(comment['at_seconds'])}</span></div>''')
                if st.button(comment['text'], key=f'inbox_open_{cid}', use_container_width=True, type='tertiary'):
                    st.session_state[selected_key] = cid
                    st.rerun()
                st.html(f'<div class="inbox-row-bottom"><span class="status-dot {e(tone)}-dot"></span>{e(label)}<span class="comment-category">· {e(category)}</span></div>')

    with detail_column, st.container(key='panel_detail'):
        if full_scene:
            st.html('<div class="pane-heading"><h2>LIVE</h2><span>Chat and offers</span></div>')
            buyer_product_id = selected['comment']['active_product_id'] if selected else 'SUN_B'
            approved_offer = next((faq for faq in bundle['faqs']
                                   if faq['product_id'] == buyer_product_id and faq.get('offer')), None)
            st.html(buyer_phone_markup(state, selected, products.get(buyer_product_id, buyer_product_id),
                                       phone_image_url, approved_offer))
            with st.container(key='buyer_bottom_actions'):
                with st.form('buyer_comment_form', clear_on_submit=True):
                    buyer_input_col, buyer_send_col = st.columns([0.74, 0.26], gap='small')
                    with buyer_input_col:
                        buyer_text = st.text_input('Ask as a viewer', max_chars=220,
                                                   placeholder=('Ask about Sunscreen B…' if api_key
                                                                else 'Connect Gemini to comment'))
                    with buyer_send_col:
                        buyer_sent = st.form_submit_button('Send', use_container_width=True,
                                                           disabled=not bool(api_key))
                with st.container(key='buyer_product_action'):
                    in_cart = st.session_state.get(f'buyer_cart_{scene}', False)
                    with st.popover('Cart' if in_cart else 'Shop', use_container_width=False):
                        st.markdown(f"**{products.get(buyer_product_id, buyer_product_id)}**")
                        if approved_offer:
                            deal = approved_offer['offer']
                            saved = deal['primary_price_vnd'] + deal['companion_price_vnd'] - deal['combo_price_vnd']
                            st.write(f"Pair with Facial Cleanser C: {format_vnd(deal['combo_price_vnd'])}")
                            st.caption(f"Save {format_vnd(saved)} compared with separate purchases.")
                            if st.button('Add combo to cart', key=f'buyer_cart_add_{scene}',
                                         disabled=in_cart, use_container_width=True):
                                st.session_state[f'buyer_cart_{scene}'] = True
                                st.rerun()
                            if in_cart:
                                st.success('Combo added to cart.')
            if buyer_sent:
                if not buyer_text.strip():
                    st.warning('Enter a question before sending.')
                else:
                    next_buyer = state.get('buyer_comment_seq', 0) + 1
                    buyer_id = f'BUY{next_buyer:03}'
                    state['demo_time'] += 1
                    buyer_comment = dict(comment_id=buyer_id, at_seconds=state['demo_time'],
                                         user_id='buyer_demo', display_name='You',
                                         active_product_id='SUN_B', text=buyer_text.strip())
                    with st.spinner('TakaAI is classifying the question…'):
                        process_comment(state, bundle, GeminiAgent(api_key, model), buyer_comment)
                    state['buyer_comment_seq'] = next_buyer
                    st.session_state[selected_key] = buyer_id
                    st.session_state['buyer_jump'] = dict(scene=scene, page=(len(state['results']) - 1) // page_size)
                    st.rerun()
        else:
            st.html('<div class="pane-heading"><h2>TakaAI assistant</h2><span>Selected comment</span></div>')
            if not selected:
                st.html('<div class="detail-empty"><span class="empty-icon">○</span><h3>Select a comment</h3><p>AI replies and moderator tasks appear here.</p></div>')
            else:
                st.html(conversation_markup(selected, state, products, policy))
                moderation_actions(selected, state, moderator_name)

    with context_column, st.container(key='panel_context'):
        st.html(routing_breakdown_markup(state))
        st.html(activity_trend_markup(state))
        st.html(f'<div class="pane-heading queue-heading"><h2>Support queue</h2><span class="queue-count">{len(pending)}</span></div>')
        if not pending:
            st.html('<p class="queue-empty">No questions need moderator support.</p>')
        for item in pending[:2]:
            comment = item['comment']
            cid = item['comment_id']
            label, tone = status_view(item, state, policy)
            st.html(f'<div class="queue-item-head">{chip(label, tone)}<span>{e(comment["display_name"])}</span></div>')
            if st.button(comment['text'], key=f'queue_open_{cid}', type='tertiary', use_container_width=True):
                st.session_state[selected_key] = cid
                st.rerun()
        if len(pending) > 2:
            with st.popover(f'View {len(pending) - 2} more questions', use_container_width=True):
                choice = st.selectbox('Question needing support', [item['comment_id'] for item in pending],
                                      format_func=lambda cid: f"{state['results'][cid]['comment']['display_name']} · {state['results'][cid]['comment']['text'][:48]}",
                                      key=f'task_selected_{scene}')
                if st.button('Open question', key=f'task_open_{scene}'):
                    st.session_state[selected_key] = choice
                    st.rerun()
        if full_scene and selected and selected['status'] in (MOD_WAITING, MOD_WORKING):
            st.html('<div class="context-divider"></div><div class="pane-heading"><h2>Handle selected case</h2></div>')
            moderation_actions(selected, state, moderator_name)
        st.html('<div class="context-divider"></div><div class="pane-heading context-heading"><h2>AI context</h2></div>')
        if selected:
            st.html(context_markup(selected, state, bundle, products))
        else:
            st.html('<p class="context-placeholder">Select a comment to view its FAQ and viewer history.</p>')
        prompts = host_prompts(state, policy)
        if prompts:
            related = next((group for group in prompts if selected and selected_id in group['comment_ids']), prompts[0])
            st.html(host_hint_markup(related, products))

