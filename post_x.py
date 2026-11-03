"""data/ の内容から X(旧Twitter)への投稿文を作り、キーがあれば投稿する。

* その日に新着・金利上げがあれば「新着」投稿、なければ毎週月曜に「ランキング」投稿。何もない日は投稿しない
* 同じ日に二度は投稿しない(data/x_posts.json に記録)
* X_API_KEY / X_API_SECRET / X_ACCESS_TOKEN / X_ACCESS_TOKEN_SECRET が揃っていなければ、文面を表示するだけ
* 広告(ad: true)の銀行を含む投稿には先頭に「PR」を付ける(ステマ規制)
* 投稿に失敗したら Discord に知らせ、終了コード1で終わる

使い方: python post_x.py            (キーがあれば投稿)
        python post_x.py --dry-run  (文面だけ表示)
        python post_x.py --dry-run --force-ranking  (ランキング投稿の文面を試す)
"""
from __future__ import annotations

import os
import re
import sys

from build_site import term_label
from monitor import DATA, EVENTS, OFFERS, expired, load_json, notify, now_jst, save_json

POSTS = DATA / "x_posts.json"
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
TAGS = "#定期預金 #金利"
MAX_WEIGHT = 280
URL_WEIGHT = 23
URL_RE = re.compile(r"https?://\S+")
KEYS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET")


def weight(text: str) -> int:
    """Xの文字数の数え方。日本語や絵文字は2、ASCIIなどは1、URLは23として数える。"""
    w = URL_WEIGHT * len(URL_RE.findall(text))
    for ch in URL_RE.sub("", text):
        c = ord(ch)
        w += 1 if (c <= 4351 or 8192 <= c <= 8205 or 8208 <= c <= 8223 or 8242 <= c <= 8247) else 2
    return w


def line(o: dict) -> str:
    mx = "最大" if o["rate_is_max"] else ""
    new = "・新規限定" if o["new_customer_only"] else ""
    end = f'〜{int(o["end_date"][5:7])}/{int(o["end_date"][8:10])}' if o.get("end_date") else ""
    return f'{o["bank"]} {term_label(o)} 年{mx}{o["rate_pct"]:.2f}%{new}{end}'


def compose(head: str, offers: list[dict], ads: set[str]) -> str | None:
    """入る分だけ行を詰める。1行も入らなければ None。"""
    tail = "\n" + "\n".join(x for x in (SITE_URL, TAGS) if x)
    body, used = [], []
    for o in offers:
        trial = "\n".join([head] + body + [line(o)]) + tail
        pr = "PR " if any(u["bank"] in ads for u in used + [o]) else ""
        if weight(pr + trial) > MAX_WEIGHT:
            break
        body.append(line(o))
        used.append(o)
    if not body:
        return None
    pr = "PR " if any(o["bank"] in ads for o in used) else ""
    return pr + "\n".join([head] + body) + tail


def build(force_ranking: bool = False) -> str | None:
    state = load_json(OFFERS, {"sources": {}})
    events = load_json(EVENTS, [])
    now = now_jst()
    today = now.date().isoformat()
    ads = {name for name, s in state["sources"].items() if s.get("ad")}

    fresh, seen = [], set()
    for ev in events:
        if ev["date"] == today and ev["type"] in ("new", "up") and not expired(ev["offer"], today):
            o = ev["offer"]
            k = (o["bank"], o["product"], o["term_months"])
            if k not in seen:
                seen.add(k)
                fresh.append(o)
    if fresh and not force_ranking:
        fresh.sort(key=lambda o: -o["rate_pct"])
        return compose("【新着】預金キャンペーン", fresh, ads)

    if now.weekday() == 0 or force_ranking:   # 月曜
        cur = [o for s in state["sources"].values() for o in s.get("offers", [])
               if not expired(o, today) and o["kind"] == "定期預金"]
        cur.sort(key=lambda o: -o["rate_pct"])
        return compose(f"【{now.month}/{now.day} 定期預金 金利ランキング】", cur, ads)
    return None


def post(text: str) -> str:
    from requests_oauthlib import OAuth1Session

    s = OAuth1Session(*(os.environ[k] for k in KEYS))
    r = s.post("https://api.x.com/2/tweets", json={"text": text}, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()["data"]["id"]


def main() -> int:
    dry = "--dry-run" in sys.argv
    text = build(force_ranking="--force-ranking" in sys.argv)
    if not text:
        print("今日は投稿なし")
        return 0
    print(f"--- 投稿文 ({weight(text)}/{MAX_WEIGHT}) ---\n{text}\n---")
    if dry:
        return 0
    if not all(os.environ.get(k) for k in KEYS):
        print("Xのキーが未設定のため投稿しません")
        return 0

    log = load_json(POSTS, [])
    today = now_jst().date().isoformat()
    if any(p["date"] == today for p in log):
        print("今日は投稿済み")
        return 0
    try:
        pid = post(text)
    except Exception as e:  # noqa: BLE001
        msg = f"⚠ Xへの投稿に失敗: {type(e).__name__}: {e}"[:300]
        print(msg, file=sys.stderr)
        notify(["**要確認**", msg + "\n→ 401/403ならキーか権限(Read and Write)を、429なら投稿回数の上限を確認してください"])
        return 1
    log.append({"date": today, "id": pid, "text": text})
    save_json(POSTS, log[-500:])
    print(f"投稿しました: https://x.com/i/web/status/{pid}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
