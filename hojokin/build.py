"""data/hojokin.json から site/hojokin/<県>/index.html を作る。デザインは金利欄と共通(design.py)。"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO))
from design import CSS, FONTS_LINK  # noqa: E402

JST = dt.timezone(dt.timedelta(hours=9))
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
WEEK = "月火水木金土日"
ORDER = ["リフォーム", "省エネ・断熱", "太陽光・蓄電池", "耐震", "ブロック塀", "緑化・雨水", "浄化槽・下水",
         "空き家", "移住・住宅取得", "車・充電", "防災", "その他"]
STATUS_RANK = {"受付中": 0, "受付前": 1, "不明": 2}
e = html.escape

EXTRA = """
.row.h{grid-template-columns:7rem minmax(0,1fr) 11rem 7rem}
.row.h .muni{font-weight:700}
.row.h .amt{text-align:right;font-size:var(--text-sm);color:var(--color-ink-2);line-height:1.5}
.row.h .max{font:500 1.25rem/1.1 var(--font-agate);font-variant-numeric:tabular-nums;color:var(--color-ink)}
.row.h .st{font-size:var(--text-sm);text-align:right;color:var(--color-muted)}
.row.h .st b{color:var(--color-ink);font-weight:700}
.adline{font-size:var(--text-sm);margin:0 0 var(--space-sm)}
@media (max-width:760px){
  .row.h{grid-template-columns:minmax(0,1fr) auto}
  .row.h .muni{grid-column:1}.row.h .amt{grid-column:2;grid-row:1}
  .row.h .prod{grid-column:1/-1}.row.h .st{grid-column:1/-1;text-align:left}
}
"""


def jdate(iso):
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.year}年{d.month}月{d.day}日({WEEK[d.weekday()]})"


def yen(n):
    if n is None:
        return ""
    return f"{n / 10000:,.0f}万円" if n >= 10000 and n % 10000 == 0 else f"{n:,}円"


def row(s):
    dl = dt.date.fromisoformat(s["deadline"]) if s.get("deadline") else None
    st = f"<b>{e(s['status'])}</b>" + (f"<br>{dl.month}月{dl.day}日まで" if dl else "")
    note = "工事・購入の前に申請が必要" if s["before_work"] else ""
    return f"""<li class="row h">
<div class="muni">{e(s['municipality'])}</div>
<div class="prod"><a href="{e(s['url'])}" target="_blank" rel="noopener">{e(s['name'])}</a><br>
<span class="cond">{e(s['what'])}。{e(s['who'])}{('。<span class="note">' + note + '</span>') if note else ''}</span></div>
<div class="amt">{f'<div class="max">上限{yen(s["max_yen"])}</div>' if s.get('max_yen') else ''}{e(s['amount'])}</div>
<div class="st">{st}</div>
</li>"""


def main():
    conf = yaml.safe_load((ROOT / "municipalities.yaml").read_text(encoding="utf-8"))
    ads = yaml.safe_load((ROOT / "ads.yaml").read_text(encoding="utf-8")) or {}
    src = REPO / "data" / "hojokin.json"
    if not src.exists():
        print("data/hojokin.json が無いので、補助金のページは作らない")
        return
    state = json.loads(src.read_text(encoding="utf-8"))
    today = dt.datetime.now(JST).date().isoformat()
    subs, seen = [], set()
    for p in state["pages"].values():
        for s in p.get("subsidies", []):
            key = (p["municipality"], s["name"])
            if key in seen or s["status"] in ("受付終了", "予算到達") or (s.get("deadline") and s["deadline"] < today):
                continue
            seen.add(key)
            subs.append(s | {"municipality": p["municipality"], "url": p["url"]})
    by_cat = defaultdict(list)
    for s in subs:
        by_cat[s["category"]].append(s)

    pref, slug = conf["prefecture"], conf["slug"]
    name = f"{pref} 住まいの補助金欄"
    sections, toc = [], []
    for cat in ORDER:
        items = sorted(by_cat.get(cat, []), key=lambda s: (STATUS_RANK.get(s["status"], 9), -(s.get("max_yen") or 0)))
        if not items:
            continue
        toc.append(f'<a href="#{e(cat)}">{e(cat)}</a>')
        ad = ads.get(cat)
        adline = (f'<p class="adline"><a href="{e(ad["url"])}" target="_blank" rel="sponsored noopener">{e(ad["label"])}</a>'
                  f'<span class="pr">広告</span></p>') if ad and ad.get("url") else ""
        sections.append(f"""<section id="{e(cat)}"><h2>{e(cat)}({len(items)}件)</h2>{adline}
<ol class="list">{''.join(row(s) for s in items)}</ol></section>""")

    open_n = sum(1 for s in subs if s["status"] == "受付中")
    munis = len({s["municipality"] for s in subs})
    top = sorted([s for s in subs if s.get("max_yen")], key=lambda s: -s["max_yen"])[:3]
    score = "".join(f'<div><div class="fig">{yen(s["max_yen"]).replace("万円", "")}<small>{"万円" if "万円" in yen(s["max_yen"]) else ""}</small></div>'
                    f'<div class="what">{e(s["municipality"])}の{e(s["name"])}の上限</div></div>' for s in top)
    checked = state.get("generated_at", "")
    has_ad = any(a.get("url") for a in ads.values() if isinstance(a, dict))
    desc = (f"{pref}と県内の市町村が出している、住宅リフォーム・省エネ・太陽光・耐震などの補助金{len(subs)}件を、"
            f"各自治体の公式ページから毎日集めて分野ごとに並べています。")
    page = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(name)}(リフォーム・省エネ・太陽光・耐震)</title>
<meta name="description" content="{e(desc)}">
{f'<link rel="canonical" href="{SITE_URL}/hojokin/{slug}/">' if SITE_URL else ''}
{FONTS_LINK}
<style>{CSS}{EXTRA}</style></head><body>
<header class="wrap">
<div class="mast"><a class="name" href="./">{e(name)}</a><span class="meta">{jdate(checked)} {checked[11:16]} 確認</span></div>
<hr class="rule2"></header>
<main class="wrap">
<div class="lead">
<div><h1>{e(pref)}の住まいの補助金、受付中は{open_n}件。</h1>
<p>{munis}の自治体の公式ページを毎日読み、リフォームや省エネ、太陽光、耐震などの補助金を分野ごとに並べています。</p>
<a class="act" href="#{e(next((c for c in ORDER if by_cat.get(c)), ''))}">分野ごとの一覧へ</a></div>
<div class="score">{score}</div>
</div>
<hr class="rule2">
<div class="tools"><nav aria-label="分野">{''.join(toc)}</nav></div>
<hr class="rule">
{''.join(sections) or '<p>今日は載せられる補助金がありませんでした。</p>'}
</main>
<footer class="wrap"><hr class="rule2">
<div class="colophon">
<div><h3>この欄について</h3>
<p>各自治体の公式ページを機械で読み取って作っています。受付終了の制度は外していますが、予算に達して締め切られることもあります。
申請の前に、必ず各自治体の公式ページで条件をご確認ください。多くの制度は、工事や購入の前に申請が必要です。</p></div>
<div><h3>掲載の方針</h3>
<p>{'分野ごとの見積もりサービスへのリンクは広告で、「広告」と表示しています。補助金の掲載や並び順には影響しません。' if has_ad else '広告は載せていません。'}</p>
<p>姉妹欄: <a href="../../">定期預金 金利欄</a></p></div>
</div></footer></body></html>"""
    out = REPO / "site" / "hojokin" / slug
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page, encoding="utf-8")
    print(f"site/hojokin/{slug}/index.html を作成: {len(subs)}件")


if __name__ == "__main__":
    main()
