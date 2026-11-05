"""はてなブログに、毎朝のランキング記事を公式API(AtomPub)で書き込む。

記事は題材ごとに1本で、毎朝同じ記事を上書き更新する(URLが変わらないので検索の評価がたまる)。
初回だけ新しく作り、その記事の編集URLを data/hatena.json に覚えておく。

必要な環境変数: HATENA_ID(はてなID), HATENA_BLOG_ID(例: xxxx.hatenablog.com), HATENA_API_KEY
ブログの設定で編集モードを「Markdown」にしておくこと。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

import requests

REPO = Path(__file__).resolve().parent.parent
STATE = REPO / "data" / "hatena.json"
JST = dt.timezone(dt.timedelta(hours=9))
WEEK = "月火水木金土日"
NS = {"a": "http://www.w3.org/2005/Atom"}
TERM_RE = re.compile(r"\d+\s*(?:か月|ヶ月|ヵ月|カ月|ケ月|年)|普通預金")


def jdate(iso: str) -> str:
    d = dt.datetime.fromisoformat(iso)
    return f"{d.month}月{d.day}日({WEEK[d.weekday()]}) {d:%H:%M}"


def cell(s) -> str:
    return str(s or "").replace("|", "／").replace("\n", " ").strip()


def link(text: str, url: str) -> str:
    return f"[{cell(text)}]({url})"


def term_label(o) -> str:
    m = o["term_months"]
    if m is None:
        return o["kind"]
    return f"{m // 12}年" if m % 12 == 0 else f"{m}か月"


# ---- 記事: 定期預金 ----------------------------------------------------------------
BUCKETS = [
    ("1〜3か月", lambda m, k: m is not None and m <= 3),
    ("4〜6か月", lambda m, k: m is not None and 4 <= m <= 6),
    ("1年まで", lambda m, k: m is not None and 7 <= m <= 12),
    ("2〜3年", lambda m, k: m is not None and 13 <= m <= 36),
    ("4年以上", lambda m, k: m is not None and m >= 37),
    ("普通預金", lambda m, k: k == "普通預金"),
]


def teiki_article():
    p = REPO / "data" / "offers.json"
    if not p.exists():
        return None
    st = json.loads(p.read_text(encoding="utf-8"))
    today = dt.datetime.now(JST).date().isoformat()
    offers = [(o, s) for s in st["sources"].values() for o in s.get("offers", [])
              if not (o.get("end_date") and o["end_date"] < today)]
    offers.sort(key=lambda x: -x[0]["rate_pct"])
    if not offers:
        return None
    teiki = [x for x in offers if x[0]["kind"] != "普通預金"]
    top = teiki[0][0] if teiki else offers[0][0]
    ad = any(s.get("ad") for _, s in offers)
    md = []
    if ad:
        md.append("※この記事には広告(アフィリエイトリンク)を含みます。並び順は金利の高さだけで決めています。\n")
    md.append(f"**{jdate(st['generated_at'])} 時点**の、ネット銀行と地方銀行・信用金庫のネット支店の円定期預金の金利です。"
              f"各銀行の公式ページを毎朝確認して、期間ごとに金利の高い順に並べています。\n")
    md.append(f"今いちばん高いのは、**{top['bank']}の{term_label(top)} 年{top['rate_pct']:.2f}%** です。\n")
    md.append("[:contents]\n")
    for title, pred in BUCKETS:
        rows = [(o, s) for o, s in offers if pred(o["term_months"], o["kind"])]
        if not rows:
            continue
        md.append(f"## {title}の金利ランキング\n")
        md.append("| 年利 | 銀行 | 商品・条件 | 期限 |\n|---:|---|---|---|")
        for o, s in rows:
            cond = ("新規口座の方のみ。" if o["new_customer_only"] else "") + cell(o.get("conditions"))
            end = (lambda d: f"{d.month}/{d.day}まで")(dt.date.fromisoformat(o["end_date"])) if o.get("end_date") else "記載なし"
            md.append(f"| **{o['rate_pct']:.2f}%** | {link(o['bank'], s.get('apply_url') or s['url'])} "
                      f"| {cell(o['product'])}{'' if TERM_RE.search(o['product']) else '(' + term_label(o) + ')'}<br>{cond} | {end} |")
        md.append("")
    stale = [s["name"] for s in st["sources"].values() if s.get("error")]
    if stale:
        md.append(f"今回確認できなかった銀行は、前回の内容のまま載せています: {'、'.join(stale)}\n")
    md.append("## この記事について\n")
    md.append("金利は年利・税引前です。公式ページを機械で読み取って作っているため、誤りや更新の遅れがあり得ます。"
              "申し込む前に、必ず各銀行の公式ページで条件をご確認ください。特定の金融商品を勧誘するものではありません。\n")
    return {"slug": "teiki", "title": "定期預金キャンペーン金利ランキング【毎朝更新】",
            "categories": ["定期預金", "金利"], "body": "\n".join(md)}


# ---- 記事: ふるさと納税 ------------------------------------------------------------
def fmt_qty(q, unit):
    if q is None:
        return "-"
    return f"{q:,.0f}{unit}" if q >= 100 else f"{q:,.1f}{unit}".replace(".0" + unit, unit)


def furusato_article():
    p = REPO / "data" / "furusato.json"
    if not p.exists():
        return None
    st = json.loads(p.read_text(encoding="utf-8"))
    md, any_rows, ad = [], False, False
    for slug, c in st["categories"].items():
        items = sorted([i for i in c["items"] if i.get("per10k")], key=lambda i: -i["per10k"])[:15]
        if not items:
            continue
        any_rows = True
        ad = ad or any(i.get("ad") for i in items)
        md.append(f"## {c['name']} 寄付1万円あたりの量\n")
        md.append("| 1万円あたり | 自治体 | 返礼品 | 寄付額・量 |\n|---:|---|---|---|")
        for i in items:
            name = i["name"] if len(i["name"]) <= 60 else i["name"][:60] + "…"
            extra = f"<br>定期便 全{i['deliveries']}回の合計" if i.get("deliveries", 1) > 1 else ""
            md.append(f"| **{fmt_qty(i['per10k'], c['unit'])}** | {cell(i['shop'])} | {link(name, i['url'])}{extra} "
                      f"| {i['price']:,}円<br>{fmt_qty(i['qty'], c['unit'])} |")
        md.append("")
    if not any_rows:
        return None
    head = []
    if ad:
        head.append("※この記事には広告(楽天アフィリエイトのリンク)を含みます。並び順は寄付1万円あたりの量だけで決めています。\n")
    head.append(f"**{jdate(st['generated_at'])} 時点**の楽天ふるさと納税の返礼品を、届く量を寄付1万円あたりに直して、"
                "品目ごとに多い順に並べています。毎朝更新しています。\n")
    head.append("[:contents]\n")
    tail = ["## この記事について\n",
            "量は商品名と説明文を機械で読み取って換算したもので、定期便は全回の合計です。"
            "申し込む前に商品ページで内容量をご確認ください。ふるさと納税には自己負担2,000円と控除の上限があります。\n"]
    return {"slug": "furusato", "title": "ふるさと納税 寄付1万円あたりの量ランキング【毎朝更新】",
            "categories": ["ふるさと納税"], "body": "\n".join(head + md + tail)}


# ---- 記事: 補助金(分野ごとに1本) -----------------------------------------------------
HOJO_ORDER = ["リフォーム", "省エネ・断熱", "太陽光・蓄電池", "耐震", "ブロック塀", "緑化・雨水", "浄化槽・下水",
              "空き家", "移住・住宅取得", "車・充電", "防災", "その他"]
HOJO_TITLE = {"リフォーム": "住宅リフォーム", "省エネ・断熱": "省エネ・断熱リフォーム", "太陽光・蓄電池": "太陽光発電・蓄電池",
              "耐震": "耐震診断・耐震改修", "ブロック塀": "ブロック塀撤去", "緑化・雨水": "生垣・緑化・雨水タンク",
              "浄化槽・下水": "浄化槽・下水道接続", "空き家": "空き家改修", "移住・住宅取得": "移住・住宅取得",
              "車・充電": "電気自動車・V2H", "防災": "感震ブレーカーなど防災", "その他": "住まいのその他"}


def yen(n):
    return f"{n / 10000:,.0f}万円" if n >= 10000 and n % 10000 == 0 else f"{n:,}円"


def hojokin_articles():
    import yaml
    p = REPO / "data" / "hojokin.json"
    if not p.exists():
        return []
    conf = yaml.safe_load((REPO / "hojokin" / "municipalities.yaml").read_text(encoding="utf-8"))
    ads = yaml.safe_load((REPO / "hojokin" / "ads.yaml").read_text(encoding="utf-8")) or {}
    pref, slug = conf["prefecture"], conf["slug"]
    st = json.loads(p.read_text(encoding="utf-8"))
    today = dt.datetime.now(JST).date().isoformat()
    by_cat, seen = {}, set()
    for pg in st["pages"].values():
        for s in pg.get("subsidies", []):
            key = (pg["municipality"], s["name"])
            if key in seen or s["status"] in ("受付終了", "予算到達") or (s.get("deadline") and s["deadline"] < today):
                continue
            seen.add(key)
            by_cat.setdefault(s["category"], []).append(s | {"municipality": pg["municipality"], "url": pg["url"]})
    rank = {"受付中": 0, "受付前": 1, "不明": 2}
    out = []
    for cat in HOJO_ORDER:
        items = sorted(by_cat.get(cat, []), key=lambda s: (s["municipality"] != pref, s["municipality"],
                                                           rank.get(s["status"], 9)))
        if not items:
            continue
        name = HOJO_TITLE[cat]
        ad = ads.get(cat) if isinstance(ads.get(cat), dict) and ads[cat].get("url") else None
        md = []
        if ad:
            md.append("※この記事には広告(アフィリエイトリンク)を含みます。補助金の掲載や順番には影響しません。\n")
        open_n = sum(1 for s in items if s["status"] == "受付中")
        md.append(f"**{jdate(st['generated_at'])} 時点**で、{pref}と県内の市町村が出している{name}の補助金・助成金は"
                  f"**{len(items)}件**(うち受付中と確認できたもの{open_n}件)です。各自治体の公式ページを毎日読んで更新しています。\n")
        if ad:
            md.append(f"工事の費用感を先に知りたい方は、[{ad['label']}]({ad['url']})で見積もりを比べられます。\n")
        md.append("[:contents]\n")
        cur = None
        for s in items:
            if s["municipality"] != cur:
                cur = s["municipality"]
                md.append(f"## {cur}\n")
            dl = dt.date.fromisoformat(s["deadline"]) if s.get("deadline") else None
            lines = [f"### {s['name']}\n",
                     f"- 補助額: {cell(s['amount'])}" + (f"(上限{yen(s['max_yen'])})" if s.get("max_yen") and yen(s["max_yen"]) not in s["amount"] else ""),
                     f"- 対象: {cell(s['what'])}。{cell(s['who'])}",
                     f"- 受付: {s['status']}" + (f"、{dl.year}年{dl.month}月{dl.day}日まで" if dl else ""),
                     ]
            if s["before_work"]:
                lines.append("- **工事・購入の前に申請が必要です**")
            lines.append(f"- 公式ページ: [{cur}のページ]({s['url']})\n")
            md += lines
        md.append("## この記事について\n")
        md.append("各自治体の公式ページを機械で読み取って作っています。予算に達して締め切られることもあるので、"
                  "申請の前に必ず公式ページで条件をご確認ください。多くの制度は、工事や購入の前に申請が必要です。\n")
        out.append({"slug": f"hojokin-{slug}-{HOJO_ORDER.index(cat)}",
                    "title": f"{pref}の{name}補助金まとめ【毎日更新】",
                    "categories": ["補助金", pref, cat], "body": "\n".join(md)})
    return out


# ---- 投稿 ------------------------------------------------------------------------
def entry_xml(a) -> bytes:
    cats = "".join(f'<category term="{escape(c)}" />' for c in a["categories"])
    return (f'<?xml version="1.0" encoding="utf-8"?>'
            f'<entry xmlns="http://www.w3.org/2005/Atom" xmlns:app="http://www.w3.org/2007/app">'
            f"<title>{escape(a['title'])}</title>"
            f'<content type="text/x-markdown">{escape(a["body"])}</content>{cats}'
            f"<app:control><app:draft>no</app:draft></app:control></entry>").encode("utf-8")


def main() -> int:
    hid, blog, key = (os.environ.get(k) for k in ("HATENA_ID", "HATENA_BLOG_ID", "HATENA_API_KEY"))
    if not (hid and blog and key):
        print("はてなブログのキーが未設定のため、投稿を飛ばす")
        return 0
    root = f"https://blog.hatena.ne.jp/{hid}/{blog}/atom/entry"
    auth = (hid, key)
    hdr = {"Content-Type": "application/xml; charset=utf-8"}
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    failed = 0
    for a in filter(None, [teiki_article(), furusato_article(), *hojokin_articles()]):
        rec = state.get(a["slug"], {})
        digest = hashlib.sha256(entry_xml(a)).hexdigest()
        if rec.get("hash") == digest:
            print(f"変化なし: {a['title']}")
            continue
        try:
            r = None
            if rec.get("edit"):
                r = requests.put(rec["edit"], data=entry_xml(a), headers=hdr, auth=auth, timeout=60)
                if r.status_code == 404:          # 記事が手で消された。作り直す
                    r = None
            if r is None:
                r = requests.post(root, data=entry_xml(a), headers=hdr, auth=auth, timeout=60)
            if r.status_code not in (200, 201):
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
            doc = ET.fromstring(r.content)
            edit = next(l.get("href") for l in doc.findall("a:link", NS) if l.get("rel") == "edit")
            alt = next((l.get("href") for l in doc.findall("a:link", NS) if l.get("rel") == "alternate"), "")
            state[a["slug"]] = {"edit": edit, "url": alt, "hash": digest,
                                "updated": dt.datetime.now(JST).isoformat(timespec="minutes")}
            print(f"更新: {a['title']} {alt}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"失敗: {a['title']}: {type(e).__name__}: {e}", file=sys.stderr)
    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
