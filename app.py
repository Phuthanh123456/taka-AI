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
st.set_page_config(page_title="TakaAI · Bảng điều khiển LIVE", layout="wide", initial_sidebar_state="expanded")
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
        if st.button('Nhận xử lý', key=f'task_claim_{cid}', type='primary', use_container_width=True):
            try:
                claim(state, cid, moderator_name)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
    elif selected['status'] == MOD_WORKING:
        with st.form(f'task_reply_{cid}'):
            reply_text = st.text_area('Phản hồi của người hỗ trợ', key=f'task_text_{cid}', height=80,
                                      placeholder='Nhập câu trả lời cho người xem…')
            if st.form_submit_button('Gửi phản hồi', use_container_width=True):
                try:
                    moderator_reply(state, cid, reply_text)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        with st.popover('Chuyển chuyên môn'):
            note = st.text_input('Nội dung cần xác minh', key=f'task_note_{cid}')
            if st.button('Ghi nhận chuyển chuyên môn', key=f'task_refer_{cid}'):
                try:
                    refer(state, cid, note)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if selected.get('referral'):
            st.info(f"Đã chuyển xác minh: {selected['referral']}")


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
    st.error(f"Không tải được dữ liệu: {exc}")
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
if 'scene_choice' not in st.session_state:
    st.session_state.scene_choice = next(iter(SCENES))
if 'sidebar_open' not in st.session_state:
    st.session_state.sidebar_open = True

scene = st.session_state.scene_choice
full_scene = scene == 'Phiên đầy đủ'
state = st.session_state.scene_sessions[scene]
st.session_state.live_session = state
source = scene_bundle(bundle, scene)
policy = bundle['policy']
products = {item['product_id']: item['name'].split(' — ')[0] for item in bundle['products']}

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
      <span><strong>TakaAI</strong><small>HỘP THƯ VẬN HÀNH</small></span></div>''')
    st.html('<div class="sidebar-section-label">KỊCH BẢN</div>')
    st.radio('Chọn kịch bản', list(SCENES), format_func=lambda value: {
        '01 · Gom FAQ': 'Gom câu hỏi',
        '02 · Moderator': 'Cần người hỗ trợ',
        '03 · Hỏi tiếp': 'Theo dõi hỏi tiếp',
        'Phiên đầy đủ': 'Toàn bộ phiên',
    }[value], key='scene_choice', label_visibility='collapsed')
    st.html(f'<div class="sidebar-scene"><span>ĐANG XEM</span><strong>{e(SCENES[scene]["title"])}</strong></div>')
    if st.session_state.sidebar_open and st.button('Thu gọn menu', key='sidebar_toggle', use_container_width=True, type='tertiary'):
        st.session_state.sidebar_open = False
        st.rerun()
if st.session_state.scene_choice != scene:
    st.rerun()

if st.session_state.sidebar_open:
    header_main = st.container()
else:
    header_toggle, header_main = st.columns([0.12, 0.88], gap='small', vertical_alignment='center')
    with header_toggle:
        if st.button('Hiện menu', key='sidebar_toggle', type='tertiary'):
            st.session_state.sidebar_open = True
            st.rerun()
with header_main:
    visible_mode = f"Gemini · {state['model'] or model}" if api_key else 'Chưa kết nối Gemini'
    st.html(f'''<header class="inbox-header"><div><span class="overline">TAKAAI / PHIÊN TRỰC TIẾP</span>
      <h1>Bảng điều khiển LIVE <span class="live-indicator"><i></i> LIVE</span></h1></div>
      <div class="session-meta"><span>{e(visible_mode)}</span><strong>{clock_text(state['demo_time'])}</strong></div></header>''')

toolbar_main, toolbar_tools, toolbar_settings, toolbar_guide = st.columns([1.7, 1.0, 1.0, 1.0], gap='small')
with toolbar_main:
    prepare_clicked = st.button('Chạy kịch bản', key='prepare_scene', type='primary', use_container_width=True)
with toolbar_tools:
    with st.popover('Điều khiển phiên', use_container_width=True):
        load_clicked = st.button('Nạp 5 bình luận', key='load_next', disabled=state['next_index'] >= len(source['comments']), use_container_width=True)
        time_clicked = st.button('Tăng 30 giây', key='advance_time', use_container_width=True)
        reset_clicked = st.button('Chạy lại từ đầu', key='reset_scene', use_container_width=True)
with toolbar_settings:
    with st.popover('Cấu hình', use_container_width=True):
        st.markdown('**Bộ xử lý: Gemini API**')
        moderator_name = st.text_input('Tên người hỗ trợ', value='Người điều phối', key='moderator_name')
        live_media = st.file_uploader('Thay hình LIVE (tùy chọn)',
                                      type=['mp4', 'webm', 'mov', 'jpg', 'jpeg', 'png'],
                                      key='live_media')
        st.caption('Gemini đọc từng comment mẫu và FAQ để chọn câu trả lời phù hợp.')
        if not configured_api_key:
            api_key_input = st.text_input('Khóa Gemini API', type='password',
                                          key='gemini_api_key_input',
                                          placeholder='Dán khóa API tại đây')
            api_key = api_key_input.strip()
            if not api_key:
                st.info('Nhập khóa để gọi Gemini. Khóa chỉ được giữ trong phiên đang mở.')
        st.caption(f'Model dựng sẵn: {model}. Comment lấy từ data/comments.json; câu trả lời lấy từ FAQ đã duyệt.')
        reset_all_clicked = st.button('Xóa kết quả mọi kịch bản', key='reset_all')
with toolbar_guide:
    with st.popover('Kịch bản', use_container_width=True):
        st.write('1. Gom câu hỏi: xem AI trả lời FAQ và gợi ý cho host.')
        st.write('2. Cần người hỗ trợ: nhận câu hỏi, nhập và gửi phản hồi.')
        st.write('3. Theo dõi hỏi tiếp: xem lịch sử của My và cảnh báo chờ lâu.')

selected_key = f'inbox_selected_{scene}'
if reset_all_clicked:
    clear_task_widgets()
    st.session_state.scene_sessions = {name: new_session(default_mode, model) for name in SCENES}
    st.rerun()
if reset_clicked or prepare_clicked:
    clear_task_widgets()
    if prepare_clicked:
        if not api_key:
            st.error('Chưa có khóa Gemini API. Mở Cấu hình, nhập khóa rồi chạy lại kịch bản.')
        else:
            agent = GeminiAgent(api_key, model)
            with st.spinner(f"Gemini đang phân loại {len(source['comments'])} bình luận…"):
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
        st.error('Chưa có khóa Gemini API. Mở Cấu hình, nhập khóa rồi nạp lại bình luận.')
    else:
        state['mode'] = default_mode
        state['model'] = model
        agent = GeminiAgent(api_key, model)
        count_to_load = min(5, len(source['comments']) - state['next_index'])
        with st.spinner(f"Gemini đang phân loại {count_to_load} bình luận tiếp theo…"):
            load_next(state, source, agent, count_to_load)
        st.session_state[selected_key] = first_buyer_reply(state) if full_scene else first_focus(state)
        st.rerun()

records = list(state['results'].values())
metrics = dashboard_metrics(state, policy)
scene_total = len(source['comments']) + state.get('buyer_comment_seq', 0)
st.html(f'''<section class="live-hero" aria-label="Tổng quan phiên LIVE">
  <div class="hero-intro"><span class="hero-eyebrow">TỔNG QUAN PHIÊN</span>
    <strong>Bình luận đã xử lý</strong><span>Dữ liệu từ kịch bản đang chọn</span></div>
  <div class="hero-total"><strong>{metrics['received']}</strong><span>/ {scene_total} bình luận</span></div>
  <div class="hero-stats">
    <div><span>AI đã trả lời</span><strong>{metrics['ai_replied']}</strong></div>
    <div><span>Cần hỗ trợ</span><strong>{metrics['moderator']}</strong></div>
    <div><span>Chờ quá lâu</span><strong>{metrics['late']}</strong></div>
  </div></section>''')
st.html(classification_summary_markup(state, bundle, scene_total))

faq_by_id = {faq['faq_id']: faq for faq in bundle['faqs']}
filter_labels = {'all': f"Tất cả bình luận ({len(records)})"}
filter_options = ['all']
for faq in bundle['faqs']:
    key = f"faq:{faq['faq_id']}"
    count = sum(item.get('route') == 'AUTO' and item.get('faq_id') == faq['faq_id'] for item in records)
    if count:
        filter_options.append(key)
        filter_labels[key] = f"FAQ · {faq['topic']} ({count})"
moderator_count = sum(item.get('route') == 'ESCALATE' for item in records)
ignored_count = sum(item.get('route') == 'IGNORE' for item in records)
followup_count = sum(bool(item.get('context')) for item in records)
if moderator_count:
    filter_options.append('moderator')
    filter_labels['moderator'] = f'Cần moderator ({moderator_count})'
if ignored_count:
    filter_options.append('ignore')
    filter_labels['ignore'] = f'Không cần phản hồi ({ignored_count})'
if followup_count:
    filter_options.append('followup')
    filter_labels['followup'] = f'Câu hỏi tiếp theo ({followup_count})'

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
                st.html('<div class="pane-heading"><h2>Khung LIVE</h2><span class="live-pane-state"><i></i> LIVE</span></div>')
                if live_media is not None:
                    if live_media.type.startswith('video/'):
                        st.video(live_media, format=live_media.type)
                    else:
                        st.image(live_media, width='stretch')
                    active_comment = records[-1] if records else None
                    active_product_id = (active_comment['comment']['active_product_id'] if active_comment
                                         else source['comments'][0]['active_product_id'])
                    product_caption = 'SẢN PHẨM ĐANG GIỚI THIỆU'
                else:
                    st.image(str(ROOT / 'assets' / 'live-health-beauty-sunscreen.png'), width='stretch')
                    active_product_id = 'SUN_B'
                    product_caption = 'SẢN PHẨM TRONG KHUNG'
                st.html(f'''<div class="live-product-strip"><span>{product_caption}</span>
                    <strong>{e(products.get(active_product_id, active_product_id))}</strong></div>''')
    with inbox_column, st.container(key='panel_inbox'):
        st.html(f'<div class="pane-heading"><h2>Bình luận</h2><span>{len(records)} / {scene_total} đã xử lý</span></div>')
        st.selectbox('Lọc comment theo nhóm', filter_options,
                     format_func=lambda value: filter_labels[value], key=filter_key,
                     label_visibility='collapsed')
        if pages > 1:
            page = st.selectbox('Trang bình luận', range(pages),
                                format_func=lambda number: f"{number * page_size + 1}–{min((number + 1) * page_size, len(filtered_records))} / {len(filtered_records)}",
                                key=page_key, label_visibility='collapsed')
        else:
            page = 0
        visible = filtered_records[page * page_size:(page + 1) * page_size]
        if not visible:
            st.html('<div class="inbox-empty"><strong>Chưa có bình luận</strong><p>Bấm “Chạy kịch bản” để Gemini phân loại comment mẫu.</p></div>')
        for item in visible:
            comment = item['comment']
            cid = item['comment_id']
            label, tone = status_view(item, state, policy)
            faq = faq_by_id.get(item.get('faq_id'))
            category = f"FAQ · {faq['topic']}" if faq else ('Cần moderator' if item.get('route') == 'ESCALATE' else 'Không cần phản hồi')
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
            st.html('<div class="pane-heading"><h2>LIVE · Góc nhìn người xem</h2><span>Chat và ưu đãi</span></div>')
            buyer_product_id = selected['comment']['active_product_id'] if selected else 'SUN_B'
            approved_offer = next((faq for faq in bundle['faqs']
                                   if faq['product_id'] == buyer_product_id and faq.get('offer')), None)
            st.html(buyer_phone_markup(state, selected, products.get(buyer_product_id, buyer_product_id),
                                       phone_image_url, approved_offer))
            with st.container(key='buyer_bottom_actions'):
                with st.form('buyer_comment_form', clear_on_submit=True):
                    buyer_text = st.text_input('Hỏi thử như người mua', max_chars=220,
                                               placeholder=('Hỏi về kem chống nắng B…' if api_key
                                                            else 'Kết nối Gemini để bình luận'))
                    buyer_sent = st.form_submit_button('Gửi', use_container_width=True,
                                                       disabled=not bool(api_key))
                with st.container(key='buyer_product_action'):
                    in_cart = st.session_state.get(f'buyer_cart_{scene}', False)
                    with st.popover('Giỏ' if in_cart else 'Mua', use_container_width=False):
                        st.markdown(f"**{products.get(buyer_product_id, buyer_product_id)}**")
                        if approved_offer:
                            deal = approved_offer['offer']
                            saved = deal['primary_price_vnd'] + deal['companion_price_vnd'] - deal['combo_price_vnd']
                            st.write(f"Mua cùng {deal['companion_product']}: {format_vnd(deal['combo_price_vnd'])}")
                            st.caption(f"Tiết kiệm {format_vnd(saved)} so với mua lẻ.")
                            if st.button('Thêm combo vào giỏ', key=f'buyer_cart_add_{scene}',
                                         disabled=in_cart, use_container_width=True):
                                st.session_state[f'buyer_cart_{scene}'] = True
                                st.rerun()
                            if in_cart:
                                st.success('Combo đã có trong giỏ hàng.')
            if buyer_sent:
                if not buyer_text.strip():
                    st.warning('Nhập câu hỏi trước khi gửi.')
                else:
                    next_buyer = state.get('buyer_comment_seq', 0) + 1
                    buyer_id = f'BUY{next_buyer:03}'
                    state['demo_time'] += 1
                    buyer_comment = dict(comment_id=buyer_id, at_seconds=state['demo_time'],
                                         user_id='buyer_demo', display_name='Bạn',
                                         active_product_id='SUN_B', text=buyer_text.strip())
                    with st.spinner('TakaAI đang phân loại câu hỏi…'):
                        process_comment(state, bundle, GeminiAgent(api_key, model), buyer_comment)
                    state['buyer_comment_seq'] = next_buyer
                    st.session_state[selected_key] = buyer_id
                    st.session_state['buyer_jump'] = dict(scene=scene, page=(len(state['results']) - 1) // page_size)
                    st.rerun()
        else:
            st.html('<div class="pane-heading"><h2>TakaAI hỗ trợ</h2><span>Bình luận đã chọn</span></div>')
            if not selected:
                st.html('<div class="detail-empty"><span class="empty-icon">○</span><h3>Chọn một bình luận để xem</h3><p>Phản hồi của AI và tác vụ hỗ trợ sẽ hiện tại đây.</p></div>')
            else:
                st.html(conversation_markup(selected, state, products, policy))
                moderation_actions(selected, state, moderator_name)

    with context_column, st.container(key='panel_context'):
        st.html(routing_breakdown_markup(state))
        st.html(activity_trend_markup(state))
        st.html(f'<div class="pane-heading queue-heading"><h2>Hàng chờ hỗ trợ</h2><span class="queue-count">{len(pending)}</span></div>')
        if not pending:
            st.html('<p class="queue-empty">Không có câu hỏi cần người hỗ trợ.</p>')
        for item in pending[:2]:
            comment = item['comment']
            cid = item['comment_id']
            label, tone = status_view(item, state, policy)
            st.html(f'<div class="queue-item-head">{chip(label, tone)}<span>{e(comment["display_name"])}</span></div>')
            if st.button(comment['text'], key=f'queue_open_{cid}', type='tertiary', use_container_width=True):
                st.session_state[selected_key] = cid
                st.rerun()
        if len(pending) > 2:
            with st.popover(f'Xem thêm {len(pending) - 2} câu hỏi', use_container_width=True):
                choice = st.selectbox('Câu cần hỗ trợ', [item['comment_id'] for item in pending],
                                      format_func=lambda cid: f"{state['results'][cid]['comment']['display_name']} · {state['results'][cid]['comment']['text'][:48]}",
                                      key=f'task_selected_{scene}')
                if st.button('Mở câu hỏi', key=f'task_open_{scene}'):
                    st.session_state[selected_key] = choice
                    st.rerun()
        if full_scene and selected and selected['status'] in (MOD_WAITING, MOD_WORKING):
            st.html('<div class="context-divider"></div><div class="pane-heading"><h2>Xử lý câu đang chọn</h2></div>')
            moderation_actions(selected, state, moderator_name)
        st.html('<div class="context-divider"></div><div class="pane-heading context-heading"><h2>Ngữ cảnh AI</h2></div>')
        if selected:
            st.html(context_markup(selected, state, bundle, products))
        else:
            st.html('<p class="context-placeholder">Chọn bình luận để xem FAQ và lịch sử người xem.</p>')
        prompts = host_prompts(state, policy)
        if prompts:
            related = next((group for group in prompts if selected and selected_id in group['comment_ids']), prompts[0])
            st.html(host_hint_markup(related, products))

