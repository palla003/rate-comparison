"""自治体ごとに、個人の住まいに関する補助金のページを探す(月1回)。

Claude のウェブ検索を自治体の公式ドメインに絞って使い、補助金ごとの説明ページのURLを集める。
見つけたURLは data/hojokin_pages.json に保存し、毎日の読み取り(collect.py)はそれだけを読む。
前回の結果が30日以内なら探し直さない(FORCE_DISCOVER=1 で強制)。
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import yaml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUT = REPO / "data" / "hojokin_pages.json"
JST = dt.timezone(dt.timedelta(hours=9))
MODEL = os.environ.get("DISCOVER_MODEL", "claude-opus-5-5")
MAX_AGE_DAYS = 30

TOPICS = ("住宅リフォーム、省エネ改修(断熱窓・高効率給湯器など)、太陽光発電・蓄電池、耐震診断・耐震改修、"
          "ブロック塀撤去、生垣・緑化、雨水タンク、浄化槽、空き家の改修、移住・住宅取得、三世代同居、"
          "電気自動車・V2H、家庭用燃料電池、感震ブレーカー")

PROMPT = """{name}({domain})の公式サイトで、個人や家庭が住まいについて使える補助金・助成金のページを探してください。
対象の例: {topics}。
事業者向け、農業向け、子どもの医療費などの給付、イベント告知は対象外です。

ウェブ検索は site:{domain} を付けて、いくつかの言い回しで行ってください。
最後に、見つかった補助金ごとの説明ページ(一覧ページではなく、制度ごとのページ。無ければ一覧ページ)を
次の形のJSONだけで答えてください。最大15件。見つからなければ空の配列。
{{"pages": [{{"title": "制度名", "url": "https://..."}}]}}"""


def now() -> dt.datetime:
    return dt.datetime.now(JST)


def ask(client, name: str, domain: str, restrict: bool = True) -> list[dict]:
    tool = {"type": "web_search_20260209", "name": "web_search", "max_uses": 5}
    if restrict:          # 検索を公式ドメインに絞る。0件のときは絞らずに探し、結果をドメインで選り分ける
        tool["allowed_domains"] = [domain]
    tools = [tool]
    messages = [{"role": "user", "content": PROMPT.format(name=name, domain=domain, topics=TOPICS)}]
    for _ in range(4):                                 # pause_turn が来たら続きを頼む
        with client.messages.stream(model=MODEL, max_tokens=16000, output_config={"effort": "low"},
                                    tools=tools, messages=messages) as s:
            resp = s.get_final_message()
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break
    if resp.stop_reason == "refusal":
        raise RuntimeError("refusal")
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\{.*\"pages\".*\}", text, re.S)
    if not m:
        raise RuntimeError(f"JSONが返らなかった: {text[-200:]}")
    pages = json.loads(m.group(0))["pages"]
    ok = []
    for p in pages:
        host = urlsplit(p.get("url", "")).netloc
        if host == domain or host.endswith("." + domain):     # 公式ドメインのページだけ使う
            ok.append({"title": p.get("title", ""), "url": p["url"]})
    return ok


def main() -> int:
    import anthropic

    conf = yaml.safe_load((ROOT / "municipalities.yaml").read_text(encoding="utf-8"))
    state = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {"municipalities": {}}
    force = os.environ.get("FORCE_DISCOVER") == "1"
    client = anthropic.Anthropic()
    done = failed = 0
    for m in conf["municipalities"]:
        rec = state["municipalities"].get(m["name"], {})
        if rec.get("searched_at") and not force and not rec.get("error") and rec.get("pages"):
            age = (now() - dt.datetime.fromisoformat(rec["searched_at"])).days
            if age < MAX_AGE_DAYS:
                continue
        try:
            pages = ask(client, m["name"], m["domain"])
            if not pages:
                pages = ask(client, m["name"], m["domain"], restrict=False)
            state["municipalities"][m["name"]] = {"domain": m["domain"], "pages": pages,
                                                  "searched_at": now().isoformat(timespec="minutes"), "error": None}
            print(f"OK  {m['name']}: {len(pages)}ページ")
            if not pages:
                print(f"    {m['name']}: 見つからず。ドメイン {m['domain']} を確認", file=sys.stderr)
            done += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
            state["municipalities"][m["name"]] = rec | {"domain": m["domain"]}
            print(f"NG  {m['name']}: {rec['error']}", file=sys.stderr)
        OUT.parent.mkdir(exist_ok=True)
        OUT.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")   # 途中で落ちても残す
    print(f"探索: {done}件更新、{failed}件失敗")
    return 1 if failed and not done else 0


if __name__ == "__main__":
    sys.exit(main())
