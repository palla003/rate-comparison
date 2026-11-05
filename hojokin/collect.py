"""discover.py が見つけた補助金ページを毎日読み、制度の中身(金額・期限・受付状況など)を取り出す。

ページの本文が前回と同じなら読み直さない。結果は data/hojokin.json。
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(REPO))
import monitor  # noqa: E402  取得(robots.txt確認・再試行・PDF対応)を共用する

PAGES = REPO / "data" / "hojokin_pages.json"
OUT = REPO / "data" / "hojokin.json"
JST = dt.timezone(dt.timedelta(hours=9))
MODEL = os.environ.get("CAMPAIGN_MODEL", "claude-haiku-5-5")
MAX_CHARS = 80_000

Category = Literal["リフォーム", "省エネ・断熱", "太陽光・蓄電池", "耐震", "ブロック塀", "緑化・雨水",
                   "浄化槽・下水", "空き家", "移住・住宅取得", "車・充電", "防災", "その他"]
Status = Literal["受付中", "受付前", "受付終了", "予算到達", "不明"]


class Subsidy(BaseModel):
    name: str = Field(description="制度名")
    category: Category
    who: str = Field(description="対象者の要点(例: 市内に住宅を所有し居住する個人)を50字以内")
    what: str = Field(description="対象になる工事・設備・購入の要点を60字以内")
    amount: str = Field(description="補助額の書き方そのまま(例: 費用の1/3、上限20万円)を50字以内")
    max_yen: Optional[int] = Field(description="上限額(円)。書かれていなければ null")
    status: Status = Field(description="今日時点の受付状況")
    deadline: Optional[str] = Field(description="申請期限 YYYY-MM-DD。無い・不明なら null")
    fiscal_year: Optional[int] = Field(description="何年度の制度か(西暦)。不明なら null")
    before_work: bool = Field(description="工事・購入の前に申請が必要なら true")


class PageResult(BaseModel):
    subsidies: List[Subsidy]


SYSTEM = """自治体の公式ページから、個人が住まいについて使える補助金・助成金の内容を取り出します。
- 書かれていることだけを使う。推測で補わない。
- 1ページに複数の制度があれば制度ごとに出す。事業者向け・給付金・イベントなどは出さない。
- 受付状況は今日の日付 {today} と、ページの受付期間・予算到達の記載から判断する。判断できなければ「不明」。
- 和暦は西暦に直す(令和8年度=2026年度)。"""


def main() -> int:
    import anthropic

    if not PAGES.exists():
        print("補助金ページの一覧がまだ無い(discover.py を先に実行)")
        return 0
    found = json.loads(PAGES.read_text(encoding="utf-8"))["municipalities"]
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"pages": {}}
    out = {"generated_at": dt.datetime.now(JST).isoformat(timespec="minutes"), "pages": {}}
    client = anthropic.Anthropic()
    today = dt.datetime.now(JST).date().isoformat()
    system = SYSTEM.format(today=today)
    ok = ng = 0
    for muni, rec in found.items():
        for p in rec.get("pages", []):
            url = p["url"]
            old = prev["pages"].get(url, {})
            try:
                text = monitor.page_text(url)
                if len(text) > MAX_CHARS:
                    raise RuntimeError(f"本文が長すぎる({len(text)}字)")
                h = hashlib.sha256((MODEL + system[:200] + text).encode()).hexdigest()
                # 受付状況は日付で変わるので、本文が同じでも7日に1回は読み直す
                fresh = old.get("read_on") and (dt.date.fromisoformat(today) - dt.date.fromisoformat(old["read_on"])).days < 7
                if h == old.get("hash") and fresh:
                    out["pages"][url] = old
                else:
                    resp = client.messages.parse(
                        model=MODEL, max_tokens=16000, output_config={"effort": "low"}, system=system,
                        messages=[{"role": "user", "content": f"自治体: {muni}\nURL: {url}\n\n{text}"}],
                        output_format=PageResult)
                    if resp.stop_reason in ("refusal", "max_tokens"):
                        raise RuntimeError(resp.stop_reason)
                    out["pages"][url] = {"municipality": muni, "url": url, "hash": h, "read_on": today,
                                         "subsidies": [s.model_dump() for s in resp.parsed_output.subsidies],
                                         "error": None}
                ok += 1
            except Exception as e:  # noqa: BLE001
                ng += 1
                out["pages"][url] = (old or {"municipality": muni, "url": url, "subsidies": []}) | {
                    "error": f"{type(e).__name__}: {e}"[:200]}
                print(f"NG  {muni} {url}: {out['pages'][url]['error']}", file=sys.stderr)
            time.sleep(1)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    n = sum(len(v["subsidies"]) for v in out["pages"].values())
    print(f"完了: {ok}ページ成功、{ng}ページ失敗、制度{n}件")
    return 2 if ng and not ok else 0


if __name__ == "__main__":
    sys.exit(main())
