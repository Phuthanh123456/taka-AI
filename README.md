# TakaAI

Demo Streamlit hỗ trợ vận hành livestream Health & Beauty với kem chống nắng B giả định, 4 FAQ đã duyệt và 48 comment sẵn có về thành phần, SPF, dung tích, combo và các câu cần moderator. Không gửi comment TikTok thật, không tạo số liệu GMV/conversion/retention.

## Cài và chạy trên Windows PowerShell

```powershell
Set-Location D:\PhuThanh\Code\ai_live_demo_day1
# Nếu chưa có .venv:
py -m venv .venv
# Thư mục tạm trên ổ D nếu ổ C hết dung lượng:
New-Item -ItemType Directory -Path .tmp -Force | Out-Null
$env:TEMP = (Join-Path (Get-Location) '.tmp')
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements.txt
.\.venv\Scripts\python.exe data_loader.py
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8503
```

Mở địa chỉ local mà Streamlit hiển thị trong terminal. Dừng bằng Ctrl+C. Không cần Activate.ps1. Nếu không có `py`, dùng `python -m venv .venv`.

App luôn dùng **Gemini API**; giao diện không có lựa chọn chuyển sang chế độ luật. Nếu chưa có key, trạng thái sẽ ghi **Chưa kết nối Gemini** và app chặn chạy kịch bản. Nhập key trong **Cấu hình** hoặc đặt biến môi trường, rồi bấm **Chạy kịch bản**.

## Giao diện Bảng điều khiển LIVE

TakaAI dùng bố cục tối kiểu LIVE Dashboard: menu kịch bản bên trái, tổng quan, hộp thư, khung LIVE và cột phân tích. Trong **Toàn bộ phiên**, chỉ có **một khung LIVE dọc ở góc nhìn người xem**: creator mang tên thương hiệu Mây Skin, tối đa năm bình luận gần nhất, câu hỏi đang chọn, câu trả lời TakaAI hoặc thông báo chuyển người hỗ trợ, sản phẩm đang giới thiệu và gợi ý combo đã duyệt. Dải tổng quan được thu gọn để ba cột LIVE, bình luận và tuyến xử lý hiện trọn trong ảnh chụp màn hình; khung LIVE giữ đúng tỉ lệ ảnh dọc, không cắt mất nửa ảnh. Lượt xem chỉ hiển thị mức tối thiểu từ số người đã bình luận; lượt thích và chia sẻ chưa có dữ liệu nên không hiển thị số. Cột phân tích thể hiện tuyến xử lý, nhịp bình luận, hàng chờ hỗ trợ và ngữ cảnh AI từ kết quả đã nạp. Cả bốn kịch bản dùng ảnh creator giới thiệu kem chống nắng trong studio Health & Beauty. Bạn không cần tải ảnh lên; **Cấu hình → Thay hình LIVE** chỉ dùng khi muốn thay bằng ảnh hoặc video riêng. Hình mặc định là ảnh minh họa, không phải kết nối video TikTok. Toàn bộ 48 comment trong phiên đầy đủ đều xoay quanh kem chống nắng B; mọi chỉ số lấy từ trạng thái phiên.

1. Chọn cảnh ở sidebar, bấm **Chạy kịch bản**. Cảnh 01 minh họa nhiều người hỏi cùng FAQ và gợi ý cho host.
2. Chọn cảnh 02, xem hàng chờ bên phải, bấm **Nhận xử lý** cho câu của Khoa, nhập câu trả lời và bấm **Gửi phản hồi**. Người còn lại vẫn ở hàng chờ.
3. Chọn cảnh 03 để xem lịch sử người xem My và câu hỏi cần hỗ trợ đã quá thời gian chờ.
4. Chọn **Toàn bộ phiên**, bấm **Chạy kịch bản** để xử lý đủ 48 bình luận. Chọn câu C019 về mua kèm kem chống nắng trong hộp thư để thấy phản hồi và thẻ combo ngay trên màn hình LIVE người xem; chọn câu cần hỗ trợ để thấy trạng thái chuyển người. FAQ `B_COMBO` giả định kem chống nắng B giá 189.000đ và sữa rửa mặt C giá 99.000đ; combo 259.000đ, tiết kiệm 29.000đ. Ứng dụng chỉ đưa ra đề xuất khi câu hỏi khớp combo đã duyệt. Nút **Mua** cạnh ô bình luận mở thông tin sản phẩm/combo; **Thêm combo vào giỏ** cập nhật giỏ trong phiên trình duyệt, không tạo đơn hàng thật. Ô bình luận ở đáy màn hình vẫn nhận câu mới qua nút **Gửi**; Gemini xử lý câu này bằng cùng sản phẩm, FAQ và lịch sử của người mua thử. Dải **Phân loại comment** đếm số câu theo FAQ, cần moderator và không cần phản hồi. Bộ lọc tại danh sách bình luận cho phép xem từng nhóm; chọn dải trang để duyệt hết 48 câu. Các số này lấy từ kết quả đã xử lý, không lấy từ tổng dataset khi chưa chạy.

Chọn một bình luận trong danh sách hoặc hàng chờ để xem chi tiết và FAQ phù hợp. **Điều khiển phiên** chứa Nạp 5 bình luận, Tăng 30 giây và Chạy lại từ đầu. **Cấu hình** hiển thị model Gemini và người hỗ trợ. Mỗi cảnh lưu kết quả riêng; đổi cảnh không gọi lại API. Bấm Chạy kịch bản lần nữa sẽ replay cảnh bằng Gemini.

Giao diện triển khai bằng Streamlit/CSS, tham khảo bố cục từ ảnh LIVE Dashboard TikTok Shop người dùng cung cấp; không sao chép mã nguồn. Các vùng danh sách cuộn riêng khi cần để giữ khung nhìn gọn cho ảnh chụp slide.

Gemini API gọi model đã huấn luyện sẵn cho từng comment trong `data/comments.json`, kèm dữ liệu sản phẩm, FAQ đã duyệt và lịch sử người xem liên quan. Gemini chọn nhóm FAQ hoặc chuyển comment cho moderator. Ứng dụng kiểm tra quyết định rồi trả đúng nội dung `approved_answer` từ `data/faqs.json`; Gemini không tự tạo thêm thông tin sản phẩm. Đây là suy luận bằng model có sẵn, không phải huấn luyện model mới.

## Cấu hình Gemini

Bạn có thể nhập key trong **Cấu hình → Khóa Gemini API**. Trường này được che và chỉ giữ key trong phiên Streamlit đang mở; key không được ghi vào file. Hoặc đặt key cục bộ trong terminal chạy ứng dụng:

```powershell
$env:GEMINI_API_KEY = 'KEY_CUA_BAN'
$env:GEMINI_MODEL = 'gemini-3.5-flash-lite'
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8503
```

Hoặc sao chép `.streamlit/secrets.toml.example` thành `.streamlit/secrets.toml` rồi điền key/model. Biến môi trường được ưu tiên hơn secrets; `GOOGLE_API_KEY` cũng được hỗ trợ. File secrets đã được ignore. `.env` không tự nạp.

SDK là `google-genai`; model mặc định khai báo một chỗ trong `agent.py` và có thể đổi qua `GEMINI_MODEL`. Mặc định hiện tại là `gemini-3.5-flash-lite`. Kết quả kiểm tra API trước đây thuộc bộ dữ liệu cũ, nên cần chạy lại `evaluation/check_live.py` để đo bộ Health & Beauty mới. Xem [danh sách model chính thức](https://ai.google.dev/gemini-api/docs/models); quyền truy cập và hạn mức phụ thuộc tài khoản. Tích hợp Generate Content với `response_json_schema` theo [SDK chính thức](https://github.com/googleapis/python-genai); xem thêm [structured output](https://ai.google.dev/gemini-api/docs/structured-output).

Gemini API hiện không cung cấp fine-tuning trực tiếp; để huấn luyện trọng số cần chọn một nền tảng/model có hỗ trợ tuning và chuẩn bị bộ dữ liệu huấn luyện riêng. Xem [tình trạng fine-tuning chính thức của Gemini API](https://ai.google.dev/gemini-api/docs/model-tuning).

Mỗi lần nạp gửi một lô bình luận cho Gemini: 5 câu khi bấm **Nạp 5 bình luận**, hoặc toàn bộ câu trong kịch bản khi bấm **Chạy kịch bản** (48 câu ở **Toàn bộ phiên**). Gemini trả một quyết định riêng cho từng ID; ứng dụng kiểm tra đủ ID, áp dụng FAQ đã duyệt và cập nhật nhóm/lịch sử theo thứ tự thời gian. Mỗi lô có timeout HTTP 60 giây và một lần thử; không gọi lại khi giao diện rerun. Nếu API lỗi, JSON sai hoặc thiếu ID, toàn lô được chuyển sang hàng chờ hỗ trợ với lý do chung, không đổi sang luật âm thầm hoặc gửi đáp án đoán. RuleAgent chỉ dùng trong kiểm thử offline; giao diện luôn gọi Gemini.

## Ba feature

1. Chọn FAQ, kiểm tra ID/sản phẩm/quyền tự trả lời, lấy nguyên `approved_answer`. Gom theo `product_id + faq_id` trong cửa sổ cố định 60 giây từ câu đầu nhóm. Mỗi câu có phản hồi riêng; nhóm hiển thị comment ID và các user khác nhau. Từ ba người hỏi có nhắc host. Câu mới luôn được xử lý, hết cửa sổ thì mở nhóm mới.
2. Câu ngoài phạm vi hoặc lỗi chuyển moderator. Thẻ có ID, người hỏi, thời điểm, ngữ cảnh, lý do, trạng thái, người nhận. Nhận xử lý chưa tính đã trả lời. Có form gửi phản hồi mô phỏng hoặc ghi nhận chuyển người phụ trách sản phẩm; chuyển chuyên môn vẫn đang xử lý.
3. Lưu năm lượt gần nhất theo `user_id`, truyền lịch sử trước câu mới cho model. Mỗi câu hỏi tiếp theo có ID/trạng thái riêng. Ưu tiên sản phẩm nói rõ; khi đổi sản phẩm và lịch sử mâu thuẫn thì chuyển người hỗ trợ. Đồng hồ tăng theo replay và nút +30 giây; câu chưa phản hồi từ 45 giây được gắn Chờ lâu. Câu đã phản hồi không báo trễ.

Ngưỡng lấy từ `data/policy.json`. Chạy lại từ đầu xóa state và widget của cảnh; Xóa toàn bộ phiên xóa tất cả các cảnh. Dữ liệu sản phẩm/FAQ được giữ nguyên. `st.cache_data` chỉ cache bộ dữ liệu, không cache quyết định API.

## Kịch bản demo 60–90 giây

- **0–25 giây:** Chạy cả ba cảnh trước khi trình bày, chọn 01 · Gom FAQ. Chỉ ra năm câu hỏi về thành phần kem chống nắng, một nhóm FAQ, đáp án duyệt và lời nhắc host.
- **25–50 giây:** Chọn 02 · Moderator. C031 hỏi khi da đang kích ứng, C032 hỏi về sử dụng khi mang thai. Nhận xử lý C031: vẫn chưa tính đã phản hồi. Nhập phản hồi của người hỗ trợ và gửi; số đã phản hồi tăng.
- **50–75 giây:** Chọn 03 · Hỏi tiếp. Cùng My hỏi dung tích → thành phần → tư vấn da: ba trạng thái riêng. C041 còn chờ, quá ngưỡng 45 giây nên được nhắc.
- **75–90 giây:** Nêu ranh giới: FAQ đã duyệt được tự trả lời; tư vấn/an toàn/giá/tồn kho cần người hỗ trợ. Phản hồi chỉ ở mô phỏng, tác động kinh doanh cần kiểm chứng.

Trong Phiên đầy đủ, có thể chỉ ra dải phân loại gom câu hỏi theo thành phần, chỉ số SPF và dung tích; câu hỏi về thành phần cụ thể chưa có trong FAQ hoặc tư vấn cá nhân được chuyển cho moderator.

## Kiểm thử

```powershell
$env:PYTHONIOENCODING = 'utf-8'
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
# API thật: chỉ chạy khi đã đặt key trong biến môi trường
.\.venv\Scripts\python.exe evaluation/check_live.py
```

`tests/test_workflow.py`: mock model kiểm tra đáp án đã duyệt, lỗi output/API, chuyển ngoài phạm vi, đúng sản phẩm/lịch sử, nhóm/host, không lặp, moderator, quá hạn/reset. Chế độ luật chỉ dùng trong kiểm tra offline, không xuất hiện trong giao diện. SDK schema kiểm tra không gọi mạng. `tests/test_app.py`: AppTest giả lập Gemini để kiểm tra nạp comment, đổi cảnh, nhận xử lý/gửi/reset mà không gọi mạng thật.

`evaluation/check_live.py` kiểm tra tám câu với Gemini thật; không có key thì SKIP và exit 2. Chỉ đọc nhãn trong evaluation sau phân loại; runtime/prompt không đọc nhãn. Không coi test mock/luật là kiểm chứng model thật.

Bộ dữ liệu Health & Beauty hiện được kiểm tra bằng nhãn offline và AppTest. Chưa gọi lại Gemini thật trên bộ dữ liệu mới; không dùng kết quả 8/8 của bộ cũ để suy ra độ chính xác hiện tại.

## File triển khai

- `app.py`: TakaAI, điều hướng trái, thống kê state, ba vùng thao tác và moderator.
- `dashboard.css`, `inbox_ui.py`: bố cục inbox ba cột, nhận diện TakaAI và markup có escape nội dung. `presentation.py`: cấu hình cảnh replay và số liệu từ state.
- `data_loader.py`: tải/kiểm tra JSON, không đọc evaluation; dùng ValueError thay assert để kiểm tra vẫn có hiệu lực khi Python chạy tối ưu.
- `replay.py`: state phiên, nạp theo thời gian, đồng hồ mô phỏng.
- `agent.py`: Gemini structured output và bộ phân loại luật chỉ dành cho kiểm thử offline.
- `workflow.py`: kiểm tra quyết định, phản hồi/nhóm, lịch sử, moderator/quá hạn.
- `requirements.txt`, `.gitignore`: thêm SDK và bỏ qua thư mục tạm.
- `tests/`, `evaluation/check_live.py`: kiểm thử offline và kiểm tra API tùy chọn.
- `tests/test_dashboard_metrics.py`: số liệu state, chuyển trạng thái moderator, thời gian chờ mô phỏng và escape nội dung bảng.
- `.streamlit/config.toml`, `.streamlit/secrets.toml.example`: giao diện, cấu hình mẫu.
- `data/*.json`, `evaluation/expected_routes.json`: giữ nguyên dữ liệu khởi đầu.

## Giới hạn thực tế

- Luật theo từ khóa là fallback giới hạn, không phải AI hiểu ngôn ngữ tổng quát. Một số câu hợp lệ có thể bị chuyển thận trọng. Model có thể phân loại sai dù JSON đúng; guard code giảm rủi ro nhưng không bảo đảm hiểu mọi cách viết hoặc chống mọi prompt injection.
- Chỉ năm lượt lịch sử mỗi người; state nằm trong bộ nhớ một phiên trình duyệt, không lưu bền khi server khởi động lại. Không đăng nhập, phân quyền, database hoặc đồng bộ nhiều moderator.
- Chỉ nút replay, không đọc TikTok thật hoặc gửi phản hồi ra ngoài. Đã gửi chưa nghĩa là đã đọc/hết thắc mắc. Moderator chịu trách nhiệm nội dung tự nhập.
- FAQ và mức giá combo là dữ liệu giả định. Danh sách thành phần minh họa không đủ kết luận không có chất khác hoặc độ an toàn. Chỉ mức giá combo trong FAQ đã duyệt được tự trả lời; voucher, giá ngoài combo, tồn kho và đơn hàng không nằm trong dữ liệu tự trả lời.
- API key chỉ nằm trong terminal người dùng, không lưu trong project. Đã kiểm tra tám câu qua API thật nhưng chưa đo độ chính xác trên dữ liệu mới, độ trễ trung bình hoặc hạn mức dài hạn.
