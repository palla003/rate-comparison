"""English price-table sites (power stations / VPS). Shared fetch, history and page shell."""
import datetime as dt
import html
import json
import os
import pathlib
import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

REPO = pathlib.Path(__file__).resolve().parent.parent
DATA = REPO / "data"
SITE = REPO / "site" / "en"
SITE_URL = os.environ.get("EN_SITE_URL", os.environ.get("SITE_URL", "")).rstrip("/")
UA = "PriceTableBot/1.0 (+https://github.com/palla003/rate-comparison)"
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


def allowed(url: str) -> bool:
    """robots.txt を守る。robots.txt が取れない(404)ときは許可、拒否・エラーは不許可。"""
    p = urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + "/robots.txt", headers={"User-Agent": UA}, timeout=20)
            if r.status_code == 404:
                rp.parse([])
            elif r.ok:
                rp.parse(r.text.splitlines())
            else:
                rp = None
        except requests.RequestException:
            rp = None
        _robots[base] = rp
    rp = _robots[base]
    return bool(rp and rp.can_fetch(UA, url))


def get_json(url: str, check_robots: bool = True, **kw):
    if check_robots and not allowed(url):
        raise PermissionError(f"robots.txt disallows {url}")
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json", **kw.pop("headers", {})}, timeout=30, **kw)
    r.raise_for_status()
    time.sleep(1)
    return r.json()


def load(name: str, default):
    f = DATA / name
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else default


def save(name: str, obj):
    DATA.mkdir(exist_ok=True)
    tmp = DATA / (name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(DATA / name)


def update_history(name: str, prices: dict[str, float], keep_days: int = 120) -> dict:
    """{key: [[date, price], ...]} を更新し、古い記録を捨てて返す。"""
    hist = load(name, {})
    today = dt.date.today().isoformat()
    cutoff = (dt.date.today() - dt.timedelta(days=keep_days)).isoformat()
    for k, p in prices.items():
        rows = [r for r in hist.get(k, []) if r[0] != today and r[0] >= cutoff]
        rows.append([today, p])
        hist[k] = rows
    for k in list(hist):
        hist[k] = [r for r in hist[k] if r[0] >= cutoff]
        if not hist[k]:
            del hist[k]
    save(name, hist)
    return hist


def affiliate(url: str, brand: str, links: dict) -> tuple[str, bool]:
    """affiliates.yaml の型があればアフィリンクに、なければ元のURL。"""
    tpl = (links.get(brand) or {}).get("template")
    if not tpl:
        return url, False
    from urllib.parse import quote
    return tpl.replace("{url}", quote(url, safe="")), True


e = html.escape

CSS = """
:root{--paper:oklch(97% 0.008 90);--paper-2:oklch(93% 0.012 88);--ink:oklch(18% 0.012 60);--ink-2:oklch(32% 0.012 60);
--muted:oklch(48% 0.014 60);--rule:oklch(80% 0.014 75);--rule-2:oklch(35% 0.012 60);--accent:oklch(46% 0.13 150);--deal:oklch(50% 0.15 30);
--display:"Zilla Slab",ui-serif,Georgia,serif;--body:"Source Serif 4",ui-serif,Georgia,serif;--agate:"Libre Franklin",ui-sans-serif,system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root{--paper:oklch(19% 0.01 70);--paper-2:oklch(24% 0.012 70);--ink:oklch(93% 0.01 85);--ink-2:oklch(82% 0.01 85);
--muted:oklch(68% 0.012 80);--rule:oklch(36% 0.012 70);--rule-2:oklch(70% 0.012 80);--accent:oklch(74% 0.13 150);--deal:oklch(72% 0.14 35)}}
html,body{overflow-x:clip}
body{margin:0;background:var(--paper);color:var(--ink);font:400 1.0625rem/1.6 var(--body)}
.wrap{max-width:76rem;margin-inline:auto;padding-inline:clamp(16px,4vw,40px)}
a{color:var(--accent);text-underline-offset:.18em}
h1,h2,h3{font-family:var(--display);margin:0}
.mast{display:flex;justify-content:space-between;align-items:baseline;gap:1rem;flex-wrap:wrap;padding-block:1.25rem .5rem;border-bottom:3px double var(--rule-2)}
.mast .name{font:700 1.375rem/1.2 var(--display);color:var(--ink);text-decoration:none}
.mast nav{display:flex;gap:1rem;font:500 .875rem var(--agate)}
.meta{font:500 .8125rem/1.5 var(--agate);color:var(--muted)}
.lead{display:grid;grid-template-columns:minmax(0,7fr) minmax(0,5fr);gap:2.5rem;padding-block:2rem 1.5rem}
.lead h1{font-size:clamp(2rem,4.5vw,3.25rem);line-height:1.1}
.lead p{margin:.75rem 0 0;max-width:36em;color:var(--ink-2)}
.score{display:grid;gap:1rem;align-content:start;border-left:1px solid var(--rule);padding-left:2rem}
.score>div{border-bottom:1px solid var(--rule);padding-bottom:.75rem}
.fig{font:500 clamp(2rem,5vw,3.25rem)/1 var(--agate);font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.fig small{font-size:.45em}
.tools{display:flex;flex-wrap:wrap;gap:.5rem 1.25rem;align-items:center;padding-block:.75rem;border-block:1px solid var(--rule);font:500 .875rem var(--agate)}
.tools select,.tools input[type=number]{font:inherit;background:var(--paper);color:var(--ink);border:1px solid var(--rule-2);padding:.2rem .4rem;max-width:8rem}
.tbl{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}
.tbl th{font:500 .75rem/1.3 var(--agate);text-transform:uppercase;letter-spacing:.04em;color:var(--muted);text-align:right;padding:.6rem .5rem;border-bottom:1px solid var(--rule-2);white-space:nowrap}
.tbl th:first-child,.tbl td:first-child{text-align:left}
.tbl td{padding:.6rem .5rem;border-bottom:1px solid var(--rule);text-align:right;vertical-align:baseline;font:500 .9375rem/1.4 var(--agate)}
.tbl td:first-child{font:600 1rem/1.4 var(--body)}
.tbl td:first-child a{color:var(--ink);text-decoration:none}
.tbl td:first-child a:hover{text-decoration:underline}
.tbl tr[hidden]{display:none!important}
.tbl .sub{display:block;font:500 .8125rem/1.4 var(--agate);color:var(--muted)}
.tbl .key{font-size:1.125rem;font-weight:600}
.deal{color:var(--deal);font-weight:600}
.tag{display:inline-block;font:600 .6875rem/1 var(--agate);border:1px solid currentColor;padding:.15em .35em;margin-left:.35em;color:var(--muted);vertical-align:.1em}
.tag.low{color:var(--deal)}
.foot{margin-top:3rem;padding-block:1.5rem 3rem;border-top:3px double var(--rule-2);display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:2rem;font-size:.875rem;color:var(--ink-2)}
.foot h3{font-size:1rem;margin-bottom:.4rem}.foot p{margin:0 0 .5rem}
.cards{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:2rem;padding-block:2rem}
.cards a{display:block;border-top:3px solid var(--ink);padding-top:1rem;color:var(--ink);text-decoration:none}
.cards h2{font-size:1.5rem}.cards p{color:var(--ink-2);margin:.5rem 0 0}
@media (max-width:760px){
 .lead,.cards,.foot{grid-template-columns:minmax(0,1fr);gap:1.25rem}
 .score{border-left:0;padding-left:0;grid-template-columns:repeat(2,minmax(0,1fr))}
 .tbl thead{display:none}
 .tbl,.tbl tbody,.tbl tr,.tbl td{display:block}
 .tbl tr{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:.15rem 1rem;padding-block:.75rem;border-bottom:1px solid var(--rule)}
 .tbl td{border:0;padding:0;text-align:left}
 .tbl td:first-child{grid-column:1/-1}
 .tbl td[data-l]::before{content:attr(data-l) " ";color:var(--muted);font-size:.75rem}
}
"""

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link href="https://fonts.googleapis.com/css2?family=Zilla+Slab:wght@700&family=Source+Serif+4:wght@400;600&family=Libre+Franklin:wght@500;600&display=swap" rel="stylesheet">')

SORT_JS = """<script>
(()=>{const t=document.querySelector('.tbl tbody');if(!t)return;const rows=[...t.rows];
const f=document.querySelector('.tools');const v=n=>f.querySelector('[name='+n+']');
function apply(){const s=v('sort').value,[k,dir]=s.split(':');
 const fs=[...f.querySelectorAll('[data-f]')];
 rows.sort((a,b)=>(parseFloat(a.dataset[k])-parseFloat(b.dataset[k]))*(dir==='d'?-1:1));
 for(const r of rows){let ok=true;for(const x of fs){const val=x.type==='checkbox'?(x.checked?x.value:''):x.value;if(!val)continue;
  const d=r.dataset[x.dataset.f];if(x.dataset.op==='min'){if(parseFloat(d)<parseFloat(val))ok=false}else if(x.dataset.op==='flag'){if(d!=='1')ok=false}else if(x.dataset.op==='noflag'){if(d==='1')ok=false}else if(d!==val)ok=false}
  r.hidden=!ok;t.appendChild(r)}}
f.addEventListener('input',apply);apply()})();
</script>"""


def page(title: str, desc: str, path: str, body: str, updated: str, jsonld: str = "") -> str:
    canon = f'<link rel="canonical" href="{SITE_URL}/en/{path}">' if SITE_URL else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title><meta name="description" content="{e(desc)}">{canon}
{FONTS}<style>{CSS}</style>{jsonld}</head><body><div class="wrap">
<header class="mast"><a class="name" href="{'../' if path else './'}">Price Per Unit</a>
<nav><a href="{'../' if path else ''}power/">Power stations</a><a href="{'../' if path else ''}vps/">VPS</a></nav>
<span class="meta">Updated {e(updated)} UTC</span></header>
{body}
<footer class="foot"><div><h3>How this works</h3><p>Prices are read once a day from each store's public product data or public pricing API. Prices change often; always confirm on the store's page before buying.</p></div>
<div><h3>Affiliate disclosure</h3><p>Some links are affiliate links. If you buy through them we may earn a commission at no extra cost to you. It never changes the order of this table, which is sorted by numbers only.</p></div></footer>
</div>{SORT_JS}</body></html>"""
