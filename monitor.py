"""預金キャンペーン監視。

1. sources.yaml の各ページを取得し、本文テキストにする
2. 前回と本文が同じなら、前回の読み取り結果をそのまま使う(APIを呼ばない)
3. 変わっていれば Claude に金利・期間・条件・期限を JSON で読み取らせる
4. 値の妥当性を確かめ、data/offers.json に保存。新着・終了・異常を data/events.json に記録
5. DISCORD_WEBHOOK_URL があれば、新着・高金利・異常を通知

人手を減らすための約束:
  * ページが取れない・読めない日は前回の値を残し、7日続いたら「要確認」にして通知する
  * 前回あった案件が急にゼロになったら、ページの作りが変わった可能性として通知する(値は前回を残す)
  * 期限が過ぎた案件はサイトから自動で外す
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
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OFFERS = DATA / "offers.json"
EVENTS = DATA / "events.json"
JST = dt.timezone(dt.timedelta(hours=9))

MODEL = os.environ.get("CAMPAIGN_MODEL", "claude-haiku-5-5")
MAX_CHARS = 150_000          # 本文がこれを超えたら読み取らずに異常として通知する(黙って切り詰めない)
STALE_DAYS = 7
ALERT_RATE = float(os.environ.get("ALERT_RATE_PCT", "1.8"))   # これ以上の新着は強調して通知
UA = "Mozilla/5.0 (compatible; deposit-campaign-monitor/1.0)"


class Offer(BaseModel):
    product: str = Field(description="商品名・キャンペーン名")
    kind: str = Field(description="'定期預金' か '普通預金'")
    term_months: Optional[int] = Field(description="預入期間(月)。普通預金や不明は null。1年=12")
    rate_pct: float = Field(description="年利(税引前, %)。'最大'表記なら最大値")
    rate_is_max: bool = Field(description="条件次第の『最大』金利なら true")
    new_customer_only: bool = Field(description="新規口座開設者・初回限定なら true")
    min_amount_yen: Optional[int] = Field(description="最低預入額(円)。不明は null")
    conditions: str = Field(description="主な条件(新規資金限定、上限、申込方法など)を60字以内で")
    start_date: Optional[str] = Field(description="開始日 YYYY-MM-DD。不明は null")
    end_date: Optional[str] = Field(description="募集期限 YYYY-MM-DD。期限なし・不明は null")
    quota: Optional[str] = Field(description="募集総額・口数の上限。なければ null")


class PageResult(BaseModel):
    offers: List[Offer]
    note: str = Field(description="読み取りで注意すべき点。なければ空文字")


SYSTEM = """あなたは銀行の公式ページから円預金の金利情報を正確に抜き出す担当です。
ページ本文に書かれている、個人が申し込める円定期預金と円普通預金の金利を列挙します。

- 書かれている数字だけを使う。推測で補わない。期間ごとに金利が違えば期間ごとに1件ずつ出す。
- 店頭金利が0.1%未満の通常金利のような目立たないものは省いてよいが、キャンペーン・特別金利・優遇金利は必ず含める。
- 外貨預金、仕組預金、投資信託、ローン、法人向けは含めない。
- 既に終了したと書かれているキャンペーンは含めない。
- 今日の日付は {today}。年の書かれていない日付はこれを基準に解釈する。
- 金利が見つからなければ offers は空にし、note に理由を書く。"""


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST)


def load_json(p: Path, default):
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def save_json(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)


def robots_ok(url: str) -> bool:
    """サイトの robots.txt に従う。読めないときは許可とみなす。"""
    from urllib.parse import urlsplit
    from urllib.robotparser import RobotFileParser
    u = urlsplit(url)
    try:
        r = requests.get(f"{u.scheme}://{u.netloc}/robots.txt", headers={"User-Agent": UA}, timeout=15)
    except requests.RequestException:
        return True
    if r.status_code != 200:
        return True
    rp = RobotFileParser()
    rp.parse(r.text.splitlines())
    return rp.can_fetch(UA, url)


def fetch_text(url: str) -> str:
    if not robots_ok(url):
        raise PermissionError("robots.txt で取得が禁止されているため読まない")
    last = None
    for attempt in range(3):          # 一時的な切断・タイムアウトは間をあけて再試行
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
            r.raise_for_status()
            break
        except (requests.ConnectionError, requests.Timeout) as e:
            last = e
            time.sleep(5 * (attempt + 1))
    else:
        raise last
    r.encoding = r.apparent_encoding if r.encoding in (None, "ISO-8859-1") else r.encoding
    soup = BeautifulSoup(r.text, "html.parser")
    for t in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        t.decompose()
    text = soup.get_text("\n")
    text = re.sub(r"[ \t　]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def extract(client, name: str, url: str, text: str) -> PageResult:
    today = now_jst().date().isoformat()
    resp = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        output_config={"effort": "low"},
        system=SYSTEM.format(today=today),
        messages=[{"role": "user", "content": f"銀行: {name}\nURL: {url}\n\n--- ページ本文 ---\n{text}"}],
        output_format=PageResult,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("読み取りを断られた(refusal)")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("出力が上限で切れた")
    return resp.parsed_output


def sane(o: dict) -> bool:
    if not (0 < o["rate_pct"] < 5):
        return False
    if o["term_months"] is not None and not (1 <= o["term_months"] <= 120):
        return False
    return True


def offer_key(o: dict) -> str:
    return f'{o["bank"]}|{o["product"]}|{o["term_months"]}'


def expired(o: dict, today: str) -> bool:
    return bool(o.get("end_date")) and o["end_date"] < today


def notify(lines: list[str]) -> None:
    hook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not hook or not lines:
        return
    msg = "\n".join(lines)
    for i in range(0, len(msg), 1900):          # Discordの1投稿2000字制限
        try:
            requests.post(hook, json={"content": msg[i:i + 1900]}, timeout=15)
        except requests.RequestException as e:
            print("通知に失敗:", e, file=sys.stderr)


def fmt(o: dict) -> str:
    term = f'{o["term_months"]}か月' if o["term_months"] else o["kind"]
    mx = "最大" if o["rate_is_max"] else ""
    end = f' 〜{o["end_date"]}' if o.get("end_date") else ""
    new = " 新規限定" if o["new_customer_only"] else ""
    return f'{o["bank"]} {term} {mx}{o["rate_pct"]:.2f}%{new}{end}({o["product"]})'


def main() -> int:
    import anthropic

    client = anthropic.Anthropic()
    sources = yaml.safe_load((ROOT / "sources.yaml").read_text(encoding="utf-8"))["sources"]
    state = load_json(OFFERS, {"sources": {}})
    events = load_json(EVENTS, [])
    today = now_jst().date().isoformat()
    stamp = now_jst().isoformat(timespec="minutes")

    new_lines, warn_lines = [], []
    old_rates = {offer_key(o): o["rate_pct"] for s in state["sources"].values() for o in s.get("offers", [])
                 if not expired(o, today)}
    old_keys = set(old_rates)

    for src in sources:
        name, url = src["name"], src["url"]
        prev = state["sources"].get(name, {})
        rec = dict(prev)
        rec.update(name=name, url=url, apply_url=src.get("apply_url") or url, ad=bool(src.get("ad")))
        try:
            text = fetch_text(url)
            if len(text) > MAX_CHARS:
                raise RuntimeError(f"本文が長すぎる({len(text)}字)。URLを金利ページに絞ってください")
            # お知らせ欄や日付の変化で毎日読み直さないよう、金利(%)を含む行だけで変化を判定する
            rate_lines = "\n".join(l for l in text.splitlines() if "%" in l or "％" in l)
            h = hashlib.sha256(rate_lines.encode()).hexdigest()
            if h == prev.get("hash") and "offers" in prev:
                rec["checked_at"] = stamp
                rec["error"] = None
                rec["fail_since"] = None
            else:
                res = extract(client, name, url, text)
                offers = []
                for o in res.offers:
                    d = o.model_dump()
                    d["bank"] = name
                    if sane(d):
                        offers.append(d)
                    else:
                        warn_lines.append(f"⚠ {name}: 不自然な値を除外 {d['product']} {d['rate_pct']}%")
                if not offers and prev.get("offers"):
                    # 急にゼロ件。ページ構成の変更かもしれないので前回の値を残す
                    raise RuntimeError(f"案件が0件になった(前回{len(prev['offers'])}件)。{res.note}")
                rec.update(offers=offers, hash=h, note=res.note, checked_at=stamp,
                           updated_at=stamp, error=None, fail_since=None)
            print(f"OK  {name}: {len(rec.get('offers', []))}件")
        except Exception as e:  # noqa: BLE001  1行の失敗で全体を止めない
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
            rec["fail_since"] = prev.get("fail_since") or today
            print(f"NG  {name}: {rec['error']}", file=sys.stderr)
            days = (dt.date.fromisoformat(today) - dt.date.fromisoformat(rec["fail_since"])).days
            if days in (0, STALE_DAYS):   # 初日と7日目だけ知らせる(毎日鳴らさない)
                warn_lines.append(f"⚠ {name}: 取得/読み取り失敗({days}日目) {rec['error'][:120]}\n{url}")
        state["sources"][name] = rec
        time.sleep(2)   # 相手のサーバーに優しく

    # 消えたsourceの掃除
    names = {s["name"] for s in sources}
    state["sources"] = {k: v for k, v in state["sources"].items() if k in names}

    cur = [o for s in state["sources"].values() for o in s.get("offers", []) if not expired(o, today)]
    cur_keys = {offer_key(o) for o in cur}
    for o in cur:
        if offer_key(o) not in old_keys and old_keys:   # 初回は全件が新着になるので通知しない
            star = "🔥" if o["rate_pct"] >= ALERT_RATE else "🆕"
            new_lines.append(f"{star} {fmt(o)}")
            events.append({"date": today, "type": "new", "offer": o})
        elif offer_key(o) in old_rates and o["rate_pct"] > old_rates[offer_key(o)] + 1e-9:
            new_lines.append(f"⬆ {fmt(o)}(前回{old_rates[offer_key(o)]:.2f}%)")
            events.append({"date": today, "type": "up", "offer": o, "prev": old_rates[offer_key(o)]})
    for k in old_keys - cur_keys:
        events.append({"date": today, "type": "gone", "key": k})
    events = events[-2000:]

    state["generated_at"] = stamp
    save_json(OFFERS, state)
    save_json(EVENTS, events)

    lines = []
    if new_lines:
        lines += ["**新しい預金キャンペーン**"] + sorted(new_lines, reverse=True)
    if warn_lines:
        lines += ["**要確認**"] + warn_lines
    notify(lines)
    ok = sum(1 for s in state["sources"].values() if not s.get("error"))
    print(f"完了: {ok}/{len(sources)}行が正常、現在の案件{len(cur)}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
