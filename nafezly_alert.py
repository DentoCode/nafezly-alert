#!/usr/bin/env python3
"""تنبيهات مشاريع نفذلي -> Telegram.

بيقرا القناة العامة t.me/s/nafezly، يفلتر المشاريع الجديدة بالكلمات المفتاحية،
ويبعتلك المناسب منها على Telegram. مكتبات بايثون الأساسية بس (من غير pip).
"""
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request

CHANNEL_URL = "https://t.me/s/nafezly"
STATE_FILE = "state.json"

# ---------- عدّل الكلمات دي على كيفك ----------
INCLUDE = [
    # Flutter مباشرة
    "flutter", "فلاتر", "dart", "دارت",
    # تحويل موقع/ويب إلى تطبيق
    "موقع الى تطبيق", "موقع إلى تطبيق", "موقع الي تطبيق", "موقع لتطبيق",
    "ويب الى تطبيق", "ويب لتطبيق", "ويب الي تطبيق",
    "webview", "web view", "web to app", "website to app", "web app to mobile",
    "convert website", "convert web",
]
# أي مشروع فيه الكلمات دي بيتتجاهل (سبام واضح بس)
EXCLUDE = [
    "كواي", "زيادة متابعين", "زياده متابعين", "تقييمات جوجل", "تقيمات جوجل",
]
# أقل ميزانية (حدها الأعلى) بالدولار. 0 = من غير فلتر. ممكن تغيّره من متغير MIN_BUDGET
MIN_BUDGET_USD = int(os.getenv("MIN_BUDGET", "0"))
# -----------------------------------------------


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[\u064B-\u0652\u0640]", "", s)  # تشكيل وتطويل
    for a, b in (("أ", "ا"), ("إ", "ا"), ("آ", "ا"), ("ى", "ي"), ("ة", "ه")):
        s = s.replace(a, b)
    return s


INCLUDE_N = [norm(k) for k in INCLUDE]
EXCLUDE_N = [norm(k) for k in EXCLUDE]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def parse(page: str):
    """بترجّع [(post_id, text)] من صفحة القناة."""
    posts = []
    for block in page.split('<div class="tgme_widget_message_wrap')[1:]:
        m = re.search(r'data-post="[^"/]+/(\d+)"', block)
        t = re.search(
            r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>',
            block, re.S)
        if not m or not t:
            continue
        raw = re.sub(r"<br\s*/?>", "\n", t.group(1))
        raw = re.sub(r"<[^>]+>", "", raw)
        posts.append((int(m.group(1)), html.unescape(raw).strip()))
    return posts


def analyze(text: str):
    """بترجّع dict لو المنشور مشروع مناسب، وإلا None."""
    if "عنوان المشروع" not in text:
        return None
    title = re.search(r"عنوان المشروع\s*:\s*(.+)", text)
    link = re.search(r"https://nafezly\.com/project/\S+", text)
    budget = re.search(r"الميزانية\s*:\s*(.+)", text)
    rng = re.search(r"الميزانية\s*:\s*(\d+)\s*-\s*(\d+)", text)

    n = norm(text)
    if any(k in n for k in EXCLUDE_N):
        return None
    hits = [k for k, kn in zip(INCLUDE, INCLUDE_N) if kn in n]
    if not hits:
        return None
    if rng and int(rng.group(2)) < MIN_BUDGET_USD:
        return None
    return {
        "title": title.group(1).strip() if title else "(بدون عنوان)",
        "budget": budget.group(1).strip() if budget else "غير محدد",
        "link": link.group(0) if link else "",
        "hits": hits[:5],
    }


def send(text: str):
    token = os.getenv("TELEGRAM_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("[DRY RUN]\n" + text + "\n")
        return
    data = urllib.parse.urlencode({
        "chat_id": chat, "text": text, "disable_web_page_preview": "true",
    }).encode()
    urllib.request.urlopen(
        f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=30
    ).read()


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main(page: str | None = None):
    posts = parse(page if page is not None else fetch(CHANNEL_URL))
    if not posts:
        sys.exit("ما لقيتش منشورات: يمكن شكل الصفحة اتغير.")
    max_id = max(i for i, _ in posts)

    state = load_state()
    last_id = state.get("last_id")

    if last_id is None:
        send("✅ تنبيهات نفذلي اشتغلت. هتوصلك المشاريع المناسبة من دلوقتي.")
    else:
        for pid, text in sorted(posts):
            if pid <= last_id:
                continue
            info = analyze(text)
            if info:
                send(
                    f"🆕 {info['title']}\n"
                    f"💰 {info['budget']}\n"
                    f"🔑 {', '.join(info['hits'])}\n"
                    f"🔗 {info['link']}"
                )

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_id": max_id}, f)


if __name__ == "__main__":
    main()
