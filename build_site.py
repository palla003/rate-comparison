"""data/offers.json から静的サイト(site/)を作る。検索エンジンが読めるよう、表はHTMLに直接書き出す。

デザインは新聞の金利欄(相場表)を下敷きにしている。参考: Hallmark の Newsprint テーマと Floor の規則
(色とフォントは :root のトークン経由、角丸・影・カードなし、罫線で区切る、作った数字を載せない)。
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site"
JST = dt.timezone(dt.timedelta(hours=9))
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
SITE_NAME = os.environ.get("SITE_NAME", "定期預金 金利欄")
WEEK = "月火水木金土日"
TERM_RE = re.compile(r"\d+\s*(?:か月|ヶ月|ヵ月|カ月|ケ月|年)|普通預金")

BUCKETS = [  # (見出し, アンカー, 判定)
    ("1〜3か月", "m3", lambda m, k: m is not None and m <= 3),
    ("4〜6か月", "m6", lambda m, k: m is not None and 4 <= m <= 6),
    ("1年まで", "y1", lambda m, k: m is not None and 7 <= m <= 12),
    ("2〜3年", "y3", lambda m, k: m is not None and 13 <= m <= 36),
    ("4年以上", "y5", lambda m, k: m is not None and m >= 37),
    ("普通預金", "futsu", lambda m, k: k == "普通預金"),
]

e = html.escape

CSS = """/* design: newsprint (Hallmark theme, by request, hand-adapted for Japanese) · genre: editorial · signature: 今朝の最高金利を紙面の見出し数字として置く */
/* critique: 相場表として読むページ。装飾は罫線だけ、色はれんが色を5%未満、数字は表の右端に揃える */
:root{
  --color-paper:oklch(94% 0.011 92);--color-paper-2:oklch(90.5% 0.015 88);
  --color-ink:oklch(17% 0.012 60);--color-ink-2:oklch(27% 0.012 58);--color-muted:oklch(46% 0.014 60);
  --color-rule:oklch(68% 0.016 75);--color-rule-2:oklch(34% 0.012 60);
  --color-accent:oklch(44% 0.13 32);--color-focus:oklch(48% 0.17 32);
  --font-display:"Zilla Slab","Shippori Mincho B1",ui-serif,serif;
  --font-body:"Shippori Mincho","Hiragino Mincho ProN","Yu Mincho",ui-serif,serif;
  --font-agate:"Libre Franklin",ui-sans-serif,sans-serif;
  --rule-hair:1px;--measure:68rem;
  --space-xs:.25rem;--space-sm:.5rem;--space-md:1rem;--space-lg:1.5rem;--space-xl:2.5rem;--space-2xl:4rem;
  --text-sm:.875rem;--text-base:1.0625rem;--text-title:1.375rem;--text-display:clamp(2.25rem,5.5vw,4rem);--text-figure:clamp(2.75rem,7vw,5.25rem);
}
html,body{overflow-x:clip}
body{margin:0;background:var(--color-paper);color:var(--color-ink);font:400 var(--text-base)/1.65 var(--font-body);-webkit-text-size-adjust:100%}
.wrap{max-width:var(--measure);margin-inline:auto;padding-inline:clamp(16px,4vw,40px)}
a{color:var(--color-accent);text-decoration-color:var(--color-accent);text-underline-offset:.18em}
a:hover{text-decoration-thickness:2px}
a:focus-visible,input:focus-visible,label:focus-within{outline:2px solid var(--color-focus);outline-offset:3px}
.rule2{box-sizing:content-box;height:2px;border:0;border-block:var(--rule-hair) solid var(--color-rule-2);margin:0}
.rule{height:0;border:0;border-top:var(--rule-hair) solid var(--color-rule);margin:0}
h1,h2,h3{font-family:var(--font-display);font-weight:800;color:var(--color-ink);margin:0;overflow-wrap:break-word;min-width:0}
.meta{font-size:var(--text-sm);color:var(--color-muted)}

.mast{display:flex;justify-content:space-between;align-items:baseline;gap:var(--space-md);flex-wrap:wrap;padding-block:var(--space-lg) var(--space-sm)}
.mast .name{font:800 var(--text-title)/1.2 var(--font-display);text-decoration:none;color:var(--color-ink)}

.lead{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,5fr);gap:var(--space-xl);padding-block:var(--space-xl)}
.lead h1{font-size:var(--text-display);line-height:1.15;letter-spacing:-.01em}
.lead p{margin:var(--space-md) 0 var(--space-lg);max-width:34em}
.act{display:inline-block;background:var(--color-ink);color:var(--color-paper);font:700 .9375rem/1 var(--font-display);padding:var(--space-md) var(--space-lg);text-decoration:none}
.act:hover{background:var(--color-ink-2);text-decoration:none}
.score{border-left:var(--rule-hair) solid var(--color-rule);padding-left:var(--space-xl);display:grid;align-content:start;gap:var(--space-lg)}
.score>div{border-bottom:var(--rule-hair) solid var(--color-rule);padding-bottom:var(--space-md)}
.score .fig{font:500 var(--text-figure)/1 var(--font-agate);font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.score .fig small{font-size:.4em;margin-left:.1em}
.score .what{font-size:var(--text-sm)}

.tools{display:flex;flex-wrap:wrap;gap:var(--space-sm) var(--space-lg);align-items:baseline;padding-block:var(--space-md)}
.tools nav{display:flex;flex-wrap:wrap;gap:var(--space-xs) var(--space-md)}
.tools label{cursor:pointer;font-size:var(--text-sm)}
.tools input{accent-color:var(--color-ink);margin-right:var(--space-xs)}

section{padding-block:var(--space-xl) 0;scroll-margin-top:var(--space-md)}
section h2{font-size:var(--text-title);padding-bottom:var(--space-sm)}
.list{list-style:none;margin:0;padding:0;border-top:var(--rule-hair) solid var(--color-rule-2)}
.row{display:grid;grid-template-columns:minmax(0,15rem) minmax(0,1fr) 7rem 6.5rem;gap:var(--space-md);align-items:baseline;padding-block:var(--space-md);border-bottom:var(--rule-hair) solid var(--color-rule)}
.row .bank{font-weight:700;line-height:1.4}
.row .bank a{color:var(--color-ink);text-decoration:none}
.row .bank a:hover{text-decoration:underline}
.row .prod{font-size:var(--text-sm);line-height:1.6;color:var(--color-ink-2)}
.row .prod .cond{color:var(--color-muted)}
.row .end{font-size:var(--text-sm);color:var(--color-muted);text-align:right}
.row .rate{font:500 1.5rem/1 var(--font-agate);font-variant-numeric:tabular-nums;text-align:right}
.row .rate small{font-size:.55em}
.note{color:var(--color-accent)}
.pr{font-size:.75em;color:var(--color-muted);border:var(--rule-hair) solid var(--color-rule);padding:0 .3em;margin-left:.4em}
.hide-new .row[data-new="1"]{display:none}

.colophon{margin-top:var(--space-2xl);padding-block:var(--space-lg) var(--space-2xl);display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:var(--space-xl);font-size:var(--text-sm);color:var(--color-ink-2)}
.colophon h3{font-size:1rem;margin-bottom:var(--space-sm)}
.colophon p{margin:0 0 var(--space-sm)}

@media (max-width:760px){
  .lead{grid-template-columns:minmax(0,1fr);gap:var(--space-lg);padding-block:var(--space-lg)}
  .score{border-left:0;padding-left:0;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--space-md)}
  .score .fig{font-size:2rem}
  .row{grid-template-columns:minmax(0,1fr) auto;gap:var(--space-xs) var(--space-md)}
  .row .bank{grid-column:1}.row .rate{grid-column:2;grid-row:1}
  .row .prod{grid-column:1/-1}.row .end{grid-column:1/-1;text-align:left}
  .colophon{grid-template-columns:minmax(0,1fr)}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""


def term_label(o):
    m = o["term_months"]
    if m is None:
        return o["kind"]
    if m % 12 == 0:
        return f"{m // 12}年"
    return f"{m}か月"


def jdate(iso):
    d = dt.date.fromisoformat(iso[:10])
    return f"{d.year}年{d.month}月{d.day}日({WEEK[d.weekday()]})"


def short_date(iso):
    d = dt.date.fromisoformat(iso)
    return f"{d.month}月{d.day}日まで"


def row(o, src):
    notes = []
    if o["new_customer_only"]:
        notes.append('<span class="note">新規口座の方のみ</span>')
    if o["rate_is_max"]:
        notes.append("条件を満たした場合の最大")
    cond = o.get("conditions") or ""
    if o.get("quota"):
        cond += f"(上限 {o['quota']})"
    link = src.get("apply_url") or src["url"]
    rel = "sponsored noopener" if src.get("ad") else "noopener"
    pr = '<span class="pr">広告</span>' if src.get("ad") else ""
    end = short_date(o["end_date"]) if o.get("end_date") else "期限の記載なし"
    return f"""<li class="row" data-new="{int(o['new_customer_only'])}">
<div class="bank"><a href="{e(link)}" target="_blank" rel="{rel}">{e(o['bank'])}</a>{pr}</div>
<div class="prod">{e(o['product'])}{'' if TERM_RE.search(o['product']) else '(' + e(term_label(o)) + ')'}<br><span class="cond">{'、'.join(notes + ([e(cond)] if cond else []))}</span></div>
<div class="end">{e(end)}</div>
<div class="rate">{o['rate_pct']:.2f}<small>%</small></div>
</li>"""


def main():
    state = json.loads((ROOT / "data" / "offers.json").read_text(encoding="utf-8"))
    today = dt.datetime.now(JST).date().isoformat()
    srcs = state["sources"]
    offers = [(o, s) for s in srcs.values() for o in s.get("offers", [])
              if not (o.get("end_date") and o["end_date"] < today)]
    offers.sort(key=lambda x: -x[0]["rate_pct"])
    teiki = [x for x in offers if x[0]["kind"] != "普通預金"]

    sections, toc, best = [], [], {}
    for title, anchor, pred in BUCKETS:
        items = [(o, s) for o, s in offers if pred(o["term_months"], o["kind"])]
        if not items:
            continue
        best[anchor] = items[0][0]
        toc.append(f'<a href="#{anchor}">{title}</a>')
        sections.append(f"""<section id="{anchor}"><h2>{title}</h2>
<ol class="list">{''.join(row(o, s) for o, s in items)}</ol></section>""")

    top = teiki[0][0] if teiki else None
    banks = sum(1 for s in srcs.values() if s.get("offers"))
    checked = state.get("generated_at", today)
    head = f"今日いちばん高い定期は、年{top['rate_pct']:.2f}%。" if top else "今朝の定期預金金利"
    sub = (f"{e(top['bank'])}の{e(term_label(top))}ものです。ネット銀行と地方銀行・信用金庫のネット支店を毎朝読み、"
           f"期間ごとに高い順に並べています。" if top else "")
    score = []
    for anchor, label in (("y1", "1年までの最高"), ("y3", "2〜3年の最高"), ("y5", "4年以上の最高")):
        o = best.get(anchor)
        if o:
            score.append(f'<div><div class="fig">{o["rate_pct"]:.2f}<small>%</small></div>'
                         f'<div class="what">{label}。{e(o["bank"])}</div></div>')
    stale = [s["name"] for s in srcs.values() if s.get("error")]
    stale_html = (f'<p class="meta">今回確認できなかった銀行は前回の内容のまま載せています: {e("、".join(stale))}</p>'
                  if stale else "")
    has_ad = any(s.get("ad") for s in srcs.values())
    desc = (f"ネット銀行・ネット支店・信用金庫の円定期預金キャンペーン{len(offers)}件を毎朝確認し、期間別に金利の高い順に並べています。"
            + (f"今日の最高は{top['bank']}の{term_label(top)} 年{top['rate_pct']:.2f}%。" if top else ""))
    canon = f'<link rel="canonical" href="{SITE_URL}/">' if SITE_URL else ""

    page = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(SITE_NAME)}({jdate(checked)}の金利)</title>
<meta name="description" content="{e(desc)}">{canon}
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@700&family=Shippori+Mincho+B1:wght@800&family=Shippori+Mincho:wght@400;700&family=Libre+Franklin:wght@500&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<header class="wrap">
<div class="mast"><a class="name" href="./">{e(SITE_NAME)}</a><span class="meta">{jdate(checked)} {checked[11:16]} 確認</span></div>
<hr class="rule2">
</header>
<main class="wrap">
<div class="lead">
<div><h1>{e(head)}</h1><p>{sub}</p><a class="act" href="#{'y1' if 'y1' in best else (next(iter(best), ''))}">期間ごとの金利表へ</a></div>
<div class="score">{''.join(score)}</div>
</div>
<hr class="rule2">
<div class="tools"><nav aria-label="期間">{''.join(toc)}</nav>
<label><input type="checkbox" id="hn">新規口座の方のみの金利を外す</label></div>
<hr class="rule">
{stale_html}
<div id="t">{''.join(sections) or '<p>今日は載せられる金利がありませんでした。</p>'}</div>
</main>
<footer class="wrap"><hr class="rule2">
<div class="colophon">
<div><h3>この金利欄について</h3>
<p>{banks}の銀行・支店の公式ページを毎朝6時半に機械で読み取り、{len(offers)}件を載せています。金利は年利・税引前です。</p>
<p>読み取りの誤りや更新の遅れがあり得ます。申し込む前に、必ず各銀行の公式ページで条件をご確認ください。</p></div>
<div><h3>掲載の方針</h3>
<p>並び順は金利の高さだけで決めています。{'一部のリンクは広告で、「広告」と表示しています。広告かどうかで順番は変えていません。' if has_ad else '広告は載せていません。'}</p>
<p>特定の金融商品への勧誘を目的としたものではありません。</p></div>
</div></footer>
<script>document.getElementById('hn').addEventListener('change',function(){{document.getElementById('t').classList.toggle('hide-new',this.checked)}})</script>
</body></html>"""

    OUT.mkdir(exist_ok=True)
    (OUT / "index.html").write_text(page, encoding="utf-8")
    (OUT / ".nojekyll").write_text("")
    if SITE_URL:
        (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n")
        (OUT / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            f"<url><loc>{SITE_URL}/</loc><lastmod>{today}</lastmod></url></urlset>")
    print(f"site/index.html を作成: {len(offers)}件")


if __name__ == "__main__":
    main()
