"""ふるさと納税の返礼品を楽天ウェブサービスのAPIで集め、量を読み取って「寄付1万円あたりの量」を計算する。

1. カテゴリごとに楽天市場商品検索API(楽天ふるさと納税の自治体ショップに限る)で返礼品を集める
2. 商品名と説明から、Claude がカテゴリの単位に換算した合計量を読む(前回と同じ商品は読み直さない)
3. data/furusato.json に保存

必要な環境変数: RAKUTEN_APP_ID, RAKUTEN_ACCESS_KEY, ANTHROPIC_API_KEY
任意: RAKUTEN_AFFILIATE_ID(付けると商品リンクが楽天アフィリエイトのリンクになる), SITE_URL(Refererに使う)
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional

import requests
import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUT = REPO / "data" / "furusato.json"
JST = dt.timezone(dt.timedelta(hours=9))
API = "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701"
MODEL = os.environ.get("CAMPAIGN_MODEL", "claude-haiku-5-5")
PAGES = int(os.environ.get("FURUSATO_PAGES", "3"))      # 1ページ30件
REFERER = (os.environ.get("SITE_URL") or "https://palla003.github.io/rate-comparison").rstrip("/") + "/"
FURUSATO_SHOP = re.compile(r"^f\d{6}")                    # 楽天ふるさと納税の自治体ショップのコード


class Qty(BaseModel):
    idx: int = Field(description="入力の番号")
    qty: Optional[float] = Field(description="指定単位に換算した合計量。読み取れない・対象外・量を選ぶ形式なら null")
    deliveries: int = Field(description="届く回数。定期便でなければ1")
    note: str = Field(description="量について注意すべき点(例: タレ込み、グレーズ込み)。なければ空文字")


class QtyBatch(BaseModel):
    items: List[Qty]


SYSTEM = """ふるさと納税の返礼品の商品名と説明から、届く量を読み取ります。
- 指定された単位に換算した合計量を qty に入れる(g→kg、本数×容量→L など)。
- 定期便は全回の合計量。届く回数は deliveries。
- 量を後から選ぶ形式、複数の商品から選ぶ形式、量が書かれていない、カテゴリの対象外の商品は qty を null にする。
- 書かれていない数字を推測しない。"""


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST)


def search(keyword: str, page: int) -> list[dict]:
    params = {"applicationId": os.environ["RAKUTEN_APP_ID"], "keyword": f"ふるさと納税 {keyword}",
              "format": "json", "formatVersion": 2, "hits": 30, "page": page, "sort": "standard",
              "availability": 1}
    if os.environ.get("RAKUTEN_AFFILIATE_ID"):
        params["affiliateId"] = os.environ["RAKUTEN_AFFILIATE_ID"]
    headers = {"accessKey": os.environ["RAKUTEN_ACCESS_KEY"], "Referer": REFERER}
    for attempt in range(4):
        r = requests.get(API, params=params, headers=headers, timeout=30)
        if r.status_code == 429:                       # 呼び出し回数の上限。間をあけて再試行
            time.sleep(3 * (attempt + 1))
            continue
        body = r.json() if r.headers.get("Content-Type", "").startswith("application/json") else {}
        if r.status_code != 200 or "error" in body or "errors" in body:
            raise RuntimeError(f"楽天API {r.status_code}: {json.dumps(body, ensure_ascii=False)[:300]}")
        return body.get("Items", [])
    raise RuntimeError("楽天API: 429が続いた")


def read_qty(client, cat: dict, items: list[dict]) -> dict[int, Qty]:
    lines = [f"[{i}] 寄付額{it['itemPrice']}円 / {it['itemName']}\n説明: {(it.get('itemCaption') or '')[:600]}"
             for i, it in enumerate(items)]
    resp = client.messages.parse(
        model=MODEL, max_tokens=16000, output_config={"effort": "low"}, system=SYSTEM,
        messages=[{"role": "user", "content":
                   f"カテゴリ: {cat['name']} / 単位: {cat['unit']}\n注意: {cat['hint']}\n\n" + "\n\n".join(lines)}],
        output_format=QtyBatch)
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"読み取りが止まった: {resp.stop_reason}")
    return {q.idx: q for q in resp.parsed_output.items}


def fingerprint(it: dict) -> str:
    return hashlib.sha256(f"{MODEL}|{it['itemName']}|{it['itemPrice']}|{SYSTEM}".encode()).hexdigest()[:16]


def main() -> int:
    import anthropic

    for k in ("RAKUTEN_APP_ID", "RAKUTEN_ACCESS_KEY"):
        if not os.environ.get(k):
            print(f"{k} が未設定のため、ふるさと納税の更新を飛ばす")
            return 0
    client = anthropic.Anthropic()
    cats = yaml.safe_load((ROOT / "categories.yaml").read_text(encoding="utf-8"))["categories"]
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"categories": {}}
    out = {"generated_at": now_jst().isoformat(timespec="minutes"), "categories": {}}
    failures = 0

    for cat in cats:
        cache = {it["code"]: it for it in prev["categories"].get(cat["slug"], {}).get("items", [])}
        try:
            raw, seen = [], set()
            for p in range(1, PAGES + 1):
                for it in search(cat["keyword"], p):
                    if FURUSATO_SHOP.match(it.get("shopCode", "")) and it["itemCode"] not in seen and it.get("itemPrice"):
                        seen.add(it["itemCode"])
                        raw.append(it)
                time.sleep(1.1)                          # 1秒1回程度に抑える
            todo = [it for it in raw if cache.get(it["itemCode"], {}).get("fp") != fingerprint(it)]
            qtys = {}
            for i in range(0, len(todo), 25):
                chunk = todo[i:i + 25]
                for j, q in read_qty(client, cat, chunk).items():
                    if 0 <= j < len(chunk):
                        qtys[chunk[j]["itemCode"]] = q
            items = []
            for it in raw:
                c = cache.get(it["itemCode"])
                if it["itemCode"] in qtys:
                    q = qtys[it["itemCode"]]
                    qty, dl, note = q.qty, q.deliveries, q.note
                elif c:
                    qty, dl, note = c["qty"], c["deliveries"], c["note"]
                else:
                    continue
                imgs = it.get("mediumImageUrls") or []
                items.append({
                    "code": it["itemCode"], "fp": fingerprint(it), "name": it["itemName"],
                    "price": it["itemPrice"], "shop": it.get("shopName", ""),
                    "url": it.get("affiliateUrl") or it["itemUrl"], "ad": bool(it.get("affiliateUrl")),
                    "image": (imgs[0] if imgs and isinstance(imgs[0], str) else (imgs[0].get("imageUrl") if imgs else "")),
                    "review_avg": it.get("reviewAverage"), "review_count": it.get("reviewCount"),
                    "qty": qty, "deliveries": dl, "note": note,
                    "per10k": round(qty * 10000 / it["itemPrice"], 3) if qty else None,
                })
            out["categories"][cat["slug"]] = {"name": cat["name"], "unit": cat["unit"], "items": items, "error": None}
            print(f"OK  {cat['name']}: {len(raw)}件取得、{len(qtys)}件を新たに読み取り")
        except Exception as e:  # noqa: BLE001  1カテゴリの失敗で全体を止めない。前回の値を残す
            failures += 1
            old = prev["categories"].get(cat["slug"], {"name": cat["name"], "unit": cat["unit"], "items": []})
            old["error"] = f"{type(e).__name__}: {e}"[:300]
            out["categories"][cat["slug"]] = old
            print(f"NG  {cat['name']}: {old['error']}", file=sys.stderr)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"完了: {len(cats) - failures}/{len(cats)}カテゴリ")
    return 2 if failures == len(cats) else 0


if __name__ == "__main__":
    sys.exit(main())
