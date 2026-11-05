"""業者向けの週報(サンプル)。分野を選び、締め切り間近・予算到達・受付中の補助金をメール用HTMLにまとめる。

使い方: python hojokin/digest.py 太陽光・蓄電池 > out.html
前回の data/hojokin.json と比べた「新着」は、毎週のスナップショットが貯まってから出す。
"""
from __future__ import annotations

import datetime as dt
import html
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
JST = dt.timezone(dt.timedelta(hours=9))
e = html.escape


def yen(n):
    if not n:
        return ""
    return f"上限{n // 10000:,}万円" if n % 10000 == 0 else f"上限{n:,}円"


def item(s):
    dl = f" / 締切 {s['deadline']}" if s.get("deadline") else ""
    pre = " / <b>工事前に申請</b>" if s["before_work"] else ""
    return (f'<li style="margin:0 0 12px"><b>{e(s["municipality"])}</b> '
            f'<a href="{e(s["url"])}">{e(s["name"])}</a><br>'
            f'<span style="color:#555">{e(s["amount"])} {yen(s.get("max_yen"))}{dl}{pre}<br>'
            f'対象: {e(s["what"])}</span></li>')


def main(cat: str) -> str:
    d = json.loads((REPO / "data" / "hojokin.json").read_text(encoding="utf-8"))
    today = dt.datetime.now(JST).date()
    subs, seen = [], set()
    for p in d["pages"].values():
        for s in p.get("subsidies", []):
            if s["category"] != cat or (p["municipality"], s["name"]) in seen:
                continue
            seen.add((p["municipality"], s["name"]))
            subs.append(s | {"municipality": p["municipality"], "url": p["url"]})
    live = [s for s in subs if s["status"] in ("受付中", "受付前") and not (s.get("deadline") and s["deadline"] < today.isoformat())]
    soon = sorted([s for s in live if s.get("deadline") and (dt.date.fromisoformat(s["deadline"]) - today).days <= 45],
                  key=lambda s: s["deadline"])
    full = [s for s in subs if s["status"] == "予算到達"]
    rest = sorted([s for s in live if s not in soon], key=lambda s: -(s.get("max_yen") or 0))
    munis = len({s["municipality"] for s in live})

    def sec(title, note, xs):
        if not xs:
            return ""
        return (f'<h2 style="font-size:17px;border-bottom:2px solid #222;padding-bottom:4px;margin:28px 0 12px">'
                f'{title}({len(xs)}件)</h2><p style="color:#555;margin:0 0 12px">{note}</p>'
                f'<ul style="padding-left:18px">{"".join(item(s) for s in xs)}</ul>')

    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>補助金週報 {e(cat)}</title></head>
<body style="font-family:sans-serif;max-width:640px;margin:24px auto;padding:0 16px;line-height:1.6;color:#222">
<p style="color:#555;margin:0">神奈川県 住まいの補助金週報 / {today:%Y年%m月%d日}</p>
<h1 style="font-size:22px;margin:4px 0 8px">{e(cat)}: 受付中 {len(live)}件({munis}自治体)</h1>
<p>県と県内33市町村の公式ページを毎日確認しています。お客様への提案前に、各自治体のページで最新の条件をご確認ください。</p>
{sec("締め切りが近い", "45日以内に申請期限が来るもの。早い順。", soon)}
{sec("予算に達して締め切られたもの", "提案から外してください。", full)}
{sec("受付中のその他", "上限額の大きい順。", rest)}
<p style="color:#888;font-size:13px;margin-top:32px">配信地域・分野の変更、配信停止はこちら(サンプルのためリンクなし)。<br>
このメールは公式ページを機械で読み取って作っています。誤りがあり得ます。</p>
</body></html>"""


if __name__ == "__main__":
    print(main(sys.argv[1] if len(sys.argv) > 1 else "太陽光・蓄電池"))
