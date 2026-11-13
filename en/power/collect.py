"""US公式ストアのポータブル電源の価格を集めて data/en_power.json に保存する。"""
import datetime as dt
import pathlib
import re
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from common import get_json, save, update_history  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
IS_STATION = re.compile(r"power station|portable power|solar generator|home backup|power bank station", re.I)
NOT_STATION = re.compile(r"\b(cable|adapter|bag|case|cover|charger only|panel only|extra battery|expansion battery|smart extra|"
                         r"warranty|protection plan|gift card|accessor|mount|tripod|refrigerator|fridge|cooler|air conditioner|"
                         r"lawn|mower|e-?bike|scooter|battery pack|subscriber exclusive|refurbished|renewed|open box|members-only)\b|\bPV\d"
                         r"|\b(canada|mexico|mex|uk|eu|australia|au)\s*only\b|\bonly\s*(canada|mex|mexico|uk|eu|au)\b", re.I)
WH = re.compile(r"(\d{1,2}(?:[.,]\d{1,3})?)\s*kwh|(\d{3,5}|\d{1,2},\d{3})\s*wh\b", re.I)
WATT = re.compile(r"(\d{3,5}|\d{1,2},\d{3})\s*w\b(?!h)", re.I)
TAG = re.compile(r"<[^>]+>")


def wh_values(text: str) -> list[float]:
    out = []
    for m in WH.finditer(text or ""):
        if m.group(1):
            out.append(float(m.group(1).replace(",", ".")) * 1000)
        else:
            out.append(float(m.group(2).replace(",", "")))
    return [v for v in out if 100 <= v <= 60000]


MULTI = re.compile(r"\d\s*[x×*]|[x×*]\s*\d|\b(EP|FP|PV)\d|\d{2,4}\s*W\b|panel|\+|bundle|\bkit\b|wheels|members|red cross", re.I)
MODEL_NUM = re.compile(r"\b(\d{3,4})(?:x|\s*plus|\s*pro|\s*max|\s*ultra)?\b", re.I)


def capacity(title: str, vtitle: str, body: str) -> tuple[float | None, str]:
    for src, text in (("variant", vtitle), ("title", title)):
        v = wh_values(text)
        if v:
            return v[0], src
    v = wh_values(TAG.sub(" ", body or ""))
    if not v:
        return None, ""
    # 型番の数字(例: Yeti 6000X → 6000)に近い値が説明文にあればそれを使う
    m = MODEL_NUM.search(title)
    if m:
        n = float(m.group(1))
        near = [x for x in v if 0.75 * n <= x <= 1.25 * n]
        if near:
            return min(near, key=lambda x: abs(x - n)), "description"
    # 説明文には「最大○kWhまで拡張」なども出るので、本体容量として一番小さい値を使う
    return min(v), "description"


def model_key(brand: str, title: str) -> str:
    t = title.lower().replace(brand.lower(), "")
    t = re.sub(r"\(.*?\)|\bexplorer\b|portable power station|solar generator|power station|series|home backup|\|.*$|[^a-z0-9 ]", " ", t)
    return " ".join(t.split())


def output_w(title: str, body: str) -> float | None:
    text = TAG.sub(" ", body or "")
    m = re.search(r"(\d{3,5}|\d{1,2},\d{3})\s*W\s*(?:rated\s*)?(?:AC\s*)?output", text, re.I) or WATT.search(title)
    return float(m.group(1).replace(",", "")) if m else None


def products(base: str):
    page = 1
    while page <= 10:
        data = get_json(f"{base}/products.json?limit=250&page={page}")
        items = data.get("products", [])
        if not items:
            break
        yield from items
        page += 1


def main():
    stores = yaml.safe_load((HERE / "stores.yaml").read_text())
    rows, status = [], {}
    for s in stores:
        n = 0
        try:
            for p in products(s["base"]):
                title = p.get("title", "")
                text = f"{title} {p.get('product_type', '')} {' '.join(p.get('tags', []) if isinstance(p.get('tags'), list) else [str(p.get('tags', ''))])}"
                if not IS_STATION.search(text) or NOT_STATION.search(title):
                    continue
                body = p.get("body_html") or ""
                lfp = bool(re.search(r"lifepo4|\blfp\b", body + title, re.I))
                if re.search(r"solar panel|\bpanels?\b|\+|bundle|\bkit\b", title, re.I):
                    continue  # 太陽光パネル付きセットは本体の価格比較にならないので載せない
                pre = bool(re.search(r"pre-?order", title, re.I))
                for v in p.get("variants", []):
                    if not v.get("available", True):
                        continue
                    vt = "" if v.get("title") in (None, "Default Title") else v["title"]
                    if MULTI.search(vt):
                        continue  # 2台セット・増設バッテリー付き・パネル付きなどの型は除く
                    price = float(v.get("price") or 0)
                    if price < 50:
                        continue
                    wh, src = capacity(title, vt, body)
                    if not wh:
                        continue
                    was = float(v.get("compare_at_price") or 0) or None
                    rows.append({
                        "key": f"{s['brand']}|{p.get('handle')}|{v.get('id')}",
                        "brand": s["brand"], "name": title, "variant": vt,
                        "url": f"{s['base']}/products/{p.get('handle')}" + (f"?variant={v['id']}" if vt else ""),
                        "price": price, "was": was if was and was > price else None,
                        "wh": wh, "wh_src": src, "w": output_w(title, body), "lfp": lfp, "pre": pre,
                    })
                    n += 1
            status[s["brand"]] = f"ok {n}"
        except Exception as ex:  # 店ごとに失敗を記録して続ける
            status[s["brand"]] = f"error {type(ex).__name__}: {str(ex)[:120]}"
        print(s["brand"], status[s["brand"]], flush=True)
    # 同じ商品の同じ容量は一番安い型だけ残す
    best = {}
    for r in rows:
        k = (r["brand"], model_key(r["brand"], r["name"]), r["wh"])  # 同じ品が別ページで重複掲載されていることが多い
        if k not in best or r["price"] < best[k]["price"]:
            best[k] = r
    rows = sorted(best.values(), key=lambda r: r["price"] / r["wh"])
    hist = update_history("en_power_history.json", {r["key"]: r["price"] for r in rows})
    for r in rows:
        past = [p for d, p in hist.get(r["key"], [])]
        r["low30"] = min(past[-30:]) if past else r["price"]
        r["high30"] = max(past[-30:]) if past else r["price"]
        r["days"] = len(past)
    ok = sum(1 for v in status.values() if v.startswith("ok") and v != "ok 0")
    save("en_power.json", {"checked": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M"), "status": status, "items": rows})
    print(f"{len(rows)} items from {ok}/{len(stores)} stores")
    if ok == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
