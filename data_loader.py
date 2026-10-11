from pathlib import Path
import json

DATA_DIR = Path(__file__).resolve().parent / "data"

def require(condition, message):
    if not condition:
        raise ValueError(message)

def load_bundle():
    bundle = {name: json.loads((DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))
              for name in ("products", "faqs", "comments", "policy")}
    products = {p["product_id"] for p in bundle["products"]}
    require(len(products) == len(bundle["products"]), "Trùng product_id")
    faq_ids = [f["faq_id"] for f in bundle["faqs"]]
    require(len(faq_ids) == len(set(faq_ids)), "Trùng faq_id")
    for f in bundle["faqs"]:
        require(f["product_id"] in products, "FAQ tham chiếu sản phẩm không tồn tại")
        require(isinstance(f["approved_answer"], str) and bool(f["approved_answer"].strip()), "FAQ thiếu đáp án")
        require(isinstance(f["auto_reply_allowed"], bool), "Quyền tự trả lời phải là boolean")
        require(bool(f["topic"]) and bool(f["question"]), "FAQ thiếu chủ đề hoặc câu hỏi")
        offer = f.get("offer")
        if offer is not None:
            require(isinstance(offer, dict) and bool(offer.get("companion_product")), "Combo thiếu sản phẩm mua kèm")
            price_keys = ("primary_price_vnd", "companion_price_vnd", "combo_price_vnd")
            require(all(type(offer.get(key)) is int and offer[key] > 0 for key in price_keys), "Giá combo phải là số nguyên dương")
            individual_total = offer["primary_price_vnd"] + offer["companion_price_vnd"]
            require(offer["combo_price_vnd"] < individual_total, "Combo phải tiết kiệm so với mua lẻ")
            for amount in (offer["primary_price_vnd"], offer["companion_price_vnd"],
                           offer["combo_price_vnd"], individual_total,
                           individual_total - offer["combo_price_vnd"]):
                shown = f"{amount:,}".replace(",", ".") + "đ"
                require(shown in f["approved_answer"], "Giá trong FAQ không khớp dữ liệu combo")
    comment_ids = [c["comment_id"] for c in bundle["comments"]]
    require(len(comment_ids) == len(set(comment_ids)), "Trùng comment_id")
    times = [c["at_seconds"] for c in bundle["comments"]]
    require(all(type(t) is int and t >= 0 for t in times), "Thời điểm phải là số nguyên không âm")
    require(times == sorted(times), "Comment không theo thứ tự thời gian")
    for c in bundle["comments"]:
        require(c["active_product_id"] in products, "Ngữ cảnh host tham chiếu sản phẩm không tồn tại")
        require(bool(c["user_id"]) and bool(c["display_name"]) and bool(c["text"].strip()), "Comment thiếu người hỏi hoặc nội dung")
        require(not any(k.startswith("expected_") for k in c), "Không để đáp án kiểm thử trong input")
    for key in ("group_window_seconds", "moderator_timeout_seconds", "host_prompt_unique_viewers"):
        require(type(bundle["policy"][key]) is int and bundle["policy"][key] > 0, f"Policy {key} phải là số nguyên dương")
    return bundle

if __name__ == "__main__":
    data = load_bundle()
    print(f"OK: {len(data['products'])} products, {len(data['faqs'])} FAQs, {len(data['comments'])} comments")
