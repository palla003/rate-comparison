# 定期預金キャンペーン比較サイト

毎朝、銀行の公式ページを読み取り、円定期預金のキャンペーン金利を期間別の高い順に並べたサイトを作って公開する。

- `sources.yaml` 監視する銀行ページ。アフィリエイトに登録したら `apply_url` と `ad: true` を足す
- `monitor.py` 取得 → Claudeで読み取り → `data/offers.json` に保存 → Discordに通知
- `build_site.py` `site/index.html` を作る
- `.github/workflows/update.yml` GitHub Actionsで毎朝6:30に上の2つを実行し、GitHub Pagesに公開

## 手元で試す(Windows)
```
pip install -r requirements.txt
set ANTHROPIC_API_KEY=...        (設定済みなら不要)
python monitor.py
python build_site.py
start site\index.html
```

## GitHubでの設定
1. このフォルダをGitHubの公開リポジトリにpushする
2. Settings → Secrets and variables → Actions に `ANTHROPIC_API_KEY`(必須)と `DISCORD_WEBHOOK_URL`(任意)を登録
3. Settings → Pages の Source を「GitHub Actions」にする
4. Actions タブで update を手動実行(Run workflow)

## 費用の目安
金利(%)を含む行が変わったページだけClaudeに読ませる。既定のモデル(claude-opus-5-5)では1ページ約5〜20円、
初回は25ページで数百円、以後は変化した分だけ。安くしたい場合は環境変数 `CAMPAIGN_MODEL=claude-haiku-5-5` で約40分の1になる(読み取り精度は要確認)。
