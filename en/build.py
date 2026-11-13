"""data/en_power.json と data/en_vps.json から site/en/ を作る。"""
import json
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import SITE, SITE_URL, e, load, page, affiliate  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
LINKS = yaml.safe_load((HERE / "affiliates.yaml").read_text()) or {}


def money(x, d=0):
    return f"${x:,.{d}f}"


def build_power():
    d = load("en_power.json", None)
    if not d or not d["items"]:
        return None
    items = [r for r in d["items"]]
    std = [r for r in items if not r["kit"]]
    best = min(std or items, key=lambda r: r["price"] / r["wh"])
    def is_low(r):  # 7日以上記録があり、30日の最安で、かつ30日内の最高値より下がっている
        return r["days"] >= 7 and r["price"] <= r["low30"] and r["price"] < r.get("high30", r["price"])
    deals = [r for r in items if is_low(r)]
    brands = sorted({r["brand"] for r in items})
    trs = []
    for r in items:
        href, aff = affiliate(r["url"], r["brand"], LINKS)
        per = r["price"] / r["wh"]
        off = round((1 - r["price"] / r["was"]) * 100) if r.get("was") else 0
        tags = ("<span class='tag'>LiFePO4</span>" if r["lfp"] else "") + ("<span class='tag'>kit</span>" if r["kit"] else "") + \
               ("<span class='tag low'>30-day low</span>" if is_low(r) else "")
        name = r["name"] + (f" – {r['variant']}" if r["variant"] else "")
        rel = "sponsored nofollow noopener" if aff else "nofollow noopener"
        w_txt = f"{r['w']:,.0f} W" if r["w"] else "–"
        was_txt = f"<span class='sub'><s>{money(r['was'])}</s> <span class='deal'>−{off}%</span></span>" if off else ""
        trs.append(
            f"<tr data-per='{per:.4f}' data-price='{r['price']}' data-wh='{r['wh']}' data-off='{off}' data-brand='{e(r['brand'])}' "
            f"data-lfp='{int(r['lfp'])}' data-kit='{int(r['kit'])}'>"
            f"<td><a href='{e(href)}' rel='{rel}' target='_blank'>{e(name)}</a>{tags}<span class='sub'>{e(r['brand'])}"
            f"{' · capacity from description' if r['wh_src'] == 'description' else ''}</span></td>"
            f"<td data-l='$/Wh' class='key'>{per:.3f}</td><td data-l='Capacity'>{r['wh']:,.0f} Wh</td>"
            f"<td data-l='Output'>{w_txt}</td>"
            f"<td data-l='Price'>{money(r['price'])}{was_txt}</td></tr>")
    opts = "".join(f"<option>{e(b)}</option>" for b in brands)
    body = f"""<section class="lead"><div><h1>Portable power stations, ranked by price per watt-hour</h1>
<p>Every power station sold on the official US stores of {len(brands)} brands, sorted by how much battery you get per dollar. Checked daily, so sale prices show up the morning they start.</p></div>
<div class="score"><div><div class="fig">${best['price']/best['wh']:.3f}<small>/Wh</small></div><div class="meta">Cheapest today: {e(best['name'])}</div></div>
<div><div class="fig">{len(items)}</div><div class="meta">models tracked</div></div>
<div><div class="fig">{len(deals)}</div><div class="meta">at their 30-day low</div></div></div></section>
<form class="tools" onsubmit="return false"><label>Sort <select name="sort"><option value="per:a">$/Wh, low first</option><option value="price:a">Price, low first</option>
<option value="wh:d">Capacity, high first</option><option value="off:d">Discount, high first</option></select></label>
<label>Brand <select data-f="brand"><option value="">All</option>{opts}</select></label>
<label>Min Wh <input type="number" data-f="wh" data-op="min" step="100" min="0" placeholder="any"></label>
<label><input type="checkbox" data-f="lfp" data-op="flag" value="1"> LiFePO4 only</label>
<label><input type="checkbox" data-f="kit" data-op="noflag" value="1" checked> Hide solar kits</label></form>
<table class="tbl"><thead><tr><th>Model</th><th>$/Wh</th><th>Capacity</th><th>AC output</th><th>Price</th></tr></thead><tbody>{''.join(trs)}</tbody></table>"""
    out = SITE / "power"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page(
        "Portable Power Station Prices per Wh (Updated Daily)",
        "Compare EcoFlow, Jackery, Anker SOLIX, BLUETTI and more by price per watt-hour. Official US store prices, checked daily.",
        "power/", body, d["checked"]), encoding="utf-8")
    return len(items)


def build_vps():
    d = load("en_vps.json", None)
    if not d or not d["items"]:
        return None
    items = d["items"]
    cheapest = min(items, key=lambda r: r["monthly"])
    per_gb = min(items, key=lambda r: r["per_gb"] or 1e9)
    provs = sorted({r["provider"] for r in items})
    trs = []
    for r in items:
        href, aff = affiliate(r["url"], r["provider"], LINKS)
        rel = "sponsored nofollow noopener" if aff else "nofollow noopener"
        tb_txt = f"{r['transfer_tb']:g} TB" if r.get("transfer_tb") else "–"
        trs.append(
            f"<tr data-monthly='{r['monthly']}' data-pergb='{r['per_gb'] or 0}' data-pervcpu='{r['per_vcpu'] or 0}' data-vcpu='{r['vcpu']}' "
            f"data-ram='{r['ram_gb']}' data-provider='{e(r['provider'])}' data-cpu='{r['cpu']}'>"
            f"<td><a href='{e(href)}' rel='{rel}' target='_blank'>{e(r['provider'])} {e(r['family'])}</a>"
            f"<span class='sub'>{e(r['plan'])} · {r['cpu']} CPU{(' · ' + e(r['note'])) if r.get('note') else ''}</span></td>"
            f"<td data-l='Monthly' class='key'>{money(r['monthly'], 2)}</td><td data-l='vCPU'>{r['vcpu']}</td>"
            f"<td data-l='RAM'>{r['ram_gb']:g} GB</td><td data-l='Disk'>{r['disk_gb']:,.0f} GB</td>"
            f"<td data-l='Transfer'>{tb_txt}</td>"
            f"<td data-l='$/GB RAM'>{money(r['per_gb'], 2) if r['per_gb'] else '–'}</td></tr>")
    opts = "".join(f"<option>{e(p)}</option>" for p in provs)
    body = f"""<section class="lead"><div><h1>VPS prices compared by the gigabyte</h1>
<p>Every current cloud server plan from {', '.join(provs)}, read daily from each provider's public pricing API. Filter by what you need and sort by what you pay.</p></div>
<div class="score"><div><div class="fig">{money(cheapest['monthly'], 2)}<small>/mo</small></div><div class="meta">Cheapest plan: {e(cheapest['provider'])} {e(cheapest['plan'])}</div></div>
<div><div class="fig">{money(per_gb['per_gb'], 2)}<small>/GB</small></div><div class="meta">Lowest per GB of RAM: {e(per_gb['provider'])}</div></div>
<div><div class="fig">{len(items)}</div><div class="meta">plans tracked</div></div></div></section>
<form class="tools" onsubmit="return false"><label>Sort <select name="sort"><option value="monthly:a">Monthly, low first</option><option value="pergb:a">$/GB RAM, low first</option>
<option value="pervcpu:a">$/vCPU, low first</option></select></label>
<label>Provider <select data-f="provider"><option value="">All</option>{opts}</select></label>
<label>CPU <select data-f="cpu"><option value="">Any</option><option value="shared">Shared</option><option value="dedicated">Dedicated</option></select></label>
<label>Min vCPU <input type="number" data-f="vcpu" data-op="min" min="1" placeholder="any"></label>
<label>Min RAM GB <input type="number" data-f="ram" data-op="min" min="0" placeholder="any"></label></form>
<table class="tbl"><thead><tr><th>Plan</th><th>Monthly</th><th>vCPU</th><th>RAM</th><th>Disk</th><th>Transfer</th><th>$/GB RAM</th></tr></thead><tbody>{''.join(trs)}</tbody></table>"""
    out = SITE / "vps"
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(page(
        "VPS Price Comparison per GB RAM (Updated Daily)",
        "Compare Vultr, Linode, DigitalOcean and Hetzner VPS plans by monthly price, price per vCPU and per GB of RAM. Updated daily from public APIs.",
        "vps/", body, d["checked"]), encoding="utf-8")
    return len(items)


def main():
    n_power, n_vps = build_power(), build_vps()
    checked = max((load(f, {}).get("checked", "") for f in ("en_power.json", "en_vps.json")), default="")
    cards = ""
    if n_power:
        cards += f"<a href='power/'><h2>Power stations by $/Wh</h2><p>{n_power} models from official US stores, ranked by price per watt-hour.</p></a>"
    if n_vps:
        cards += f"<a href='vps/'><h2>VPS by $/GB</h2><p>{n_vps} cloud server plans, ranked by monthly price, per vCPU and per GB of RAM.</p></a>"
    body = f"<section class='lead'><div><h1>Price per unit, checked every morning</h1><p>Plain tables that answer one question: how much do you pay for what you get.</p></div></section><div class='cards'>{cards}</div>"
    SITE.mkdir(parents=True, exist_ok=True)
    (SITE / "index.html").write_text(page("Price Per Unit – daily price tables", "Daily price-per-unit tables for portable power stations and VPS plans.", "", body, checked), encoding="utf-8")
    print(f"site/en: power={n_power} vps={n_vps}")


if __name__ == "__main__":
    main()
