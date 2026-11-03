"""data/offers.json から静的サイト(site/)を作る。検索エンジンが読めるよう、表はHTMLに直接書き出す。"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site"
JST = dt.timezone(dt.timedelta(hours=9))
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")
SITE_NAME = os.environ.get("SITE_NAME", "定期預金キャンペーン金利 毎日更新")

BUCKETS = [  # (見出し, アンカー, 判定)
    ("普通預金", "futsu", lambda m, k: k == "普通預金"),
    ("1〜3か月", "m3", lambda m, k: m is not None and m <= 3),
    ("4〜6か月", "m6", lambda m, k: m is not None and 4 <= m <= 6),
    ("7か月〜1年", "y1", lambda m, k: m is not None and 7 <= m <= 12),
    ("2〜3年", "y3", lambda m, k: m is not None and 13 <= m <= 36),
    ("4年以上", "y5", lambda m, k: m is not None and m >= 37),
]

e = html.escape


def term_label(o):
    m = o["term_months"]
    if m is None:
        return o["kind"]
    if m % 12 == 0:
        return f"{m // 12}年"
    return f"{m}か月"


def row(o, src):
    tags = []
    if o["new_customer_only"]:
        tags.append('<span class="tag new">新規限定</span>')
    if o["rate_is_max"]:
        tags.append('<span class="tag">条件で最大</span>')
    end = o.get("end_date") or "定めなし/不明"
    link = src.get("apply_url") or src["url"]
    pr = '<span class="pr">PR</span>' if src.get("ad") else ""
    rel = "sponsored noopener" if src.get("ad") else "noopener"
    return f"""<tr data-new="{int(o['new_customer_only'])}">
<td class="rate">{o['rate_pct']:.2f}%</td>
<td><b>{e(o['bank'])}</b><br><span class="sub">{e(o['product'])}</span> {''.join(tags)}</td>
<td>{e(term_label(o))}</td>
<td class="sub">{e(o.get('conditions') or '')}{('<br>上限: ' + e(o['quota'])) if o.get('quota') else ''}</td>
<td>{e(end)}</td>
<td><a href="{e(link)}" target="_blank" rel="{rel}">公式{pr}</a></td>
</tr>"""


def main():
    state = json.loads((ROOT / "data" / "offers.json").read_text(encoding="utf-8"))
    today = dt.datetime.now(JST).date().isoformat()
    srcs = state["sources"]
    offers = [(o, s) for s in srcs.values() for o in s.get("offers", [])
              if not (o.get("end_date") and o["end_date"] < today)]
    offers.sort(key=lambda x: -x[0]["rate_pct"])

    sections, toc = [], []
    for title, anchor, pred in BUCKETS:
        rows = [row(o, s) for o, s in offers if pred(o["term_months"], o["kind"])]
        if not rows:
            continue
        toc.append(f'<a href="#{anchor}">{title}</a>')
        sections.append(f"""<section id="{anchor}"><h2>{title}の金利ランキング</h2>
<div class="scroll"><table><thead><tr><th>年利</th><th>銀行・商品</th><th>期間</th><th>条件</th><th>期限</th><th></th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></section>""")

    top = offers[0][0] if offers else None
    lead = (f"いま一番高いのは{e(top['bank'])}の{e(term_label(top))} 年{top['rate_pct']:.2f}%です。"
            if top else "")
    stale = [s["name"] for s in srcs.values() if s.get("error")]
    stale_html = (f'<p class="sub">一時的に確認できていない銀行: {e("、".join(stale))}(前回の情報を表示)</p>'
                  if stale else "")
    has_ad = any(s.get("ad") for s in srcs.values())
    updated = state.get("generated_at", "")[:16].replace("T", " ")
    desc = f"ネット銀行・ネット支店・信用金庫の円定期預金キャンペーン{len(offers)}件を毎日自動で確認し、期間別に金利の高い順に並べています。{lead}"
    canon = f'<link rel="canonical" href="{SITE_URL}/">' if SITE_URL else ""

    page = f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(SITE_NAME)}({today[:7].replace('-', '年')}月)</title>
<meta name="description" content="{e(desc)}">{canon}
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--sub:#666;--line:#e5e5e5;--acc:#0a6e5c;--tag:#eef6f4}}
@media(prefers-color-scheme:dark){{:root{{--bg:#16181a;--fg:#eee;--sub:#aaa;--line:#333;--acc:#4fd1b5;--tag:#1f2d2a}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 system-ui,-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif}}
main{{max-width:1000px;margin:auto;padding:16px}}
h1{{font-size:1.5em;margin:.4em 0}} h2{{font-size:1.15em;margin-top:2em;border-left:4px solid var(--acc);padding-left:8px}}
.sub{{color:var(--sub);font-size:.88em}} .scroll{{overflow-x:auto}}
table{{border-collapse:collapse;width:100%;min-width:640px}} th,td{{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:top}}
th{{font-size:.85em;color:var(--sub)}} .rate{{font-weight:700;font-size:1.15em;color:var(--acc);white-space:nowrap}}
.tag{{display:inline-block;background:var(--tag);border-radius:4px;padding:0 5px;font-size:.75em;margin-left:4px}}
.tag.new{{color:#b54708}} .pr{{font-size:.7em;border:1px solid var(--sub);border-radius:3px;padding:0 3px;margin-left:4px}}
nav a{{margin-right:12px}} a{{color:var(--acc)}} label{{cursor:pointer}}
.hide-new tr[data-new="1"]{{display:none}} footer{{margin:3em 0 1em;font-size:.82em;color:var(--sub)}}
</style></head><body><main>
<h1>{e(SITE_NAME)}</h1>
<p>{e(desc)}</p>
<p class="sub">最終確認: {e(updated)}(毎朝自動更新)</p>
{'<p class="sub">当サイトのリンクには広告(PR)を含みます。表示順は金利の高さのみで決めており、広告の有無で変えていません。</p>' if has_ad else ''}
{stale_html}
<nav>{''.join(toc)}</nav>
<p><label><input type="checkbox" id="hn"> 新規口座開設者限定を除く</label></p>
<div id="t">{''.join(sections) or '<p>現在掲載できる情報がありません。</p>'}</div>
<footer>
<p>金利は年利・税引前です。各銀行の公式ページを機械で読み取って作成しているため、誤りや更新の遅れがあり得ます。申込の前に必ず公式ページで条件をご確認ください。
本サイトは情報提供のみを目的とし、特定の金融商品を勧誘するものではありません。</p>
</footer></main>
<script>document.getElementById('hn').onchange=function(){{document.getElementById('t').classList.toggle('hide-new',this.checked)}}</script>
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
