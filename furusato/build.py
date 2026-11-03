"""data/furusato.json から site/furusato/index.html を作る。デザインは金利欄と共通(design.py)。"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO))
from design import CSS, FONTS_LINK  # noqa: E402

OUT = REPO / "site" / "furusato"
JST = dt.timezone(dt.timedelta(hours=9))
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
NAME = "ふるさと納税 量の欄"
TOP_N = 15
WEEK = "月火水木金土日"
e = html.escape

EXTRA = """
.row.f{grid-template-columns:4rem minmax(0,1fr) 9rem 7rem}
.row.f img{width:4rem;height:4rem;object-fit:cover;border:var(--rule-hair) solid var(--color-rule);display:block}
.row.f .amt{font-size:var(--text-sm);color:var(--color-ink-2);text-align:right;line-height:1.5}
.row.f .rate{font-size:1.35rem}
.row.f .rate small{font-size:.55em;margin-left:.15em}
@media (max-width:760px){
  .row.f{grid-template-columns:3.5rem minmax(0,1fr) auto}
  .row.f img{width:3.5rem;height:3.5rem;grid-row:1/3}
  .row.f .bank{grid-column:2}.row.f .rate{grid-column:3;grid-row:1}
  .row.f .prod{grid-column:2/-1}.row.f .amt{grid-column:2/-1;text-align:left}
}
"""


def fmt_qty(q, unit):
    if q is None:
        return "-"
    if q >= 100:
        return f"{q:,.0f}{unit}"
    return f"{q:,.1f}{unit}".replace(".0" + unit, unit)


def jdate(iso):
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.year}年{d.month}月{d.day}日({WEEK[d.weekday()]})"


def row(it, unit):
    rel = "sponsored noopener" if it["ad"] else "noopener"
    pr = '<span class="pr">広告</span>' if it["ad"] else ""
    extra = []
    if it["deliveries"] and it["deliveries"] > 1:
        extra.append(f"定期便 全{it['deliveries']}回の合計")
    if it.get("note"):
        extra.append(e(it["note"]))
    if it.get("review_count"):
        extra.append(f"レビュー{it['review_avg']:.1f}({it['review_count']:,}件)")
    img = f'<img src="{e(it["image"])}" alt="" loading="lazy" width="64" height="64">' if it.get("image") else "<span></span>"
    name = it["name"] if len(it["name"]) <= 70 else it["name"][:70] + "…"
    return f"""<li class="row f">{img}
<div><div class="bank"><a href="{e(it['url'])}" target="_blank" rel="{rel}">{e(it['shop'])}</a>{pr}</div>
<div class="prod">{e(name)}<br><span class="cond">{'、'.join(extra)}</span></div></div>
<div class="amt">寄付 {it['price']:,}円<br>{fmt_qty(it['qty'], unit)}</div>
<div class="rate">{fmt_qty(it['per10k'], '')}<small>{e(unit)}</small></div>
</li>"""


def main():
    src = REPO / "data" / "furusato.json"
    if not src.exists():
        print("data/furusato.json が無いので、ふるさと納税のページは作らない")
        return
    state = json.loads(src.read_text(encoding="utf-8"))
    cats = state["categories"]
    sections, toc, score = [], [], []
    for slug, c in cats.items():
        items = sorted([i for i in c["items"] if i.get("per10k")], key=lambda i: -i["per10k"])[:TOP_N]
        if not items:
            continue
        toc.append(f'<a href="#{slug}">{e(c["name"])}</a>')
        sections.append(f"""<section id="{slug}"><h2>{e(c['name'])}　寄付1万円あたりの量</h2>
<ol class="list">{''.join(row(i, c['unit']) for i in items)}</ol></section>""")
        if len(score) < 3:
            top = items[0]
            score.append(f'<div><div class="fig">{fmt_qty(top["per10k"], "")}<small>{e(c["unit"])}</small></div>'
                         f'<div class="what">{e(c["name"])}、寄付1万円あたり。{e(top["shop"])}</div></div>')

    checked = state.get("generated_at", "")
    first = next(iter(cats.values()), None)
    best = (sorted([i for i in first["items"] if i.get("per10k")], key=lambda i: -i["per10k"]) or [None])[0] if first else None
    head = (f"寄付1万円で、{first['name']}は{fmt_qty(best['per10k'], first['unit'])}。" if best else "ふるさと納税 量の欄")
    stale = [c["name"] for c in cats.values() if c.get("error")]
    has_ad = any(i.get("ad") for c in cats.values() for i in c["items"])
    desc = "楽天ふるさと納税の返礼品を毎朝集め、お米・肉・海産物・日用品を寄付1万円あたりの量で並べています。"
    canon = f'<link rel="canonical" href="{SITE_URL}/furusato/">' if SITE_URL else ""

    page = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{NAME}({jdate(checked)})寄付1万円あたりの量ランキング</title>
<meta name="description" content="{e(desc)}">{canon}
{FONTS_LINK}
<style>{CSS}{EXTRA}</style></head><body>
<header class="wrap">
<div class="mast"><a class="name" href="./">{NAME}</a><span class="meta">{jdate(checked)} {checked[11:16]} 確認</span></div>
<hr class="rule2">
</header>
<main class="wrap">
<div class="lead">
<div><h1>{e(head)}</h1><p>楽天ふるさと納税の返礼品を毎朝集め、届く量を寄付1万円あたりに直して、品目ごとに多い順に並べています。</p>
<a class="act" href="#{next(iter(cats), '')}">品目ごとの表へ</a></div>
<div class="score">{''.join(score)}</div>
</div>
<hr class="rule2">
<div class="tools"><nav aria-label="品目">{''.join(toc)}</nav></div>
<hr class="rule">
{f'<p class="meta">今回更新できなかった品目は前回の内容のまま載せています: {e("、".join(stale))}</p>' if stale else ''}
{''.join(sections) or '<p>今日は載せられる返礼品がありませんでした。</p>'}
</main>
<footer class="wrap"><hr class="rule2">
<div class="colophon">
<div><h3>この欄について</h3>
<p>量は商品名と説明文を機械で読み取って換算したものです。定期便は全回の合計で数えています。読み取りの誤りがあり得るので、申し込む前に商品ページで内容量をご確認ください。</p>
<p>ふるさと納税には自己負担2,000円と、収入などで決まる控除の上限があります。</p></div>
<div><h3>掲載の方針</h3>
<p>並び順は寄付1万円あたりの量だけで決めています。{'商品へのリンクは楽天アフィリエイトの広告で、「広告」と表示しています。' if has_ad else ''}</p>
<p>姉妹欄: <a href="../">定期預金 金利欄</a></p></div>
</div></footer>
</body></html>"""
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "index.html").write_text(page, encoding="utf-8")
    print(f"site/furusato/index.html を作成: {len(sections)}品目")


if __name__ == "__main__":
    main()
