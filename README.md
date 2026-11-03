# 定期預金キャンペーン比較サイト

毎朝、銀行の公式ページを読み取り、円定期預金のキャンペーン金利を期間別の高い順に並べたサイトを作って公開する。

- `sources.yaml` 監視する銀行ページ。アフィリエイトに登録したら `apply_url` と `ad: true` を足す
- `monitor.py` 取得 → Claudeで読み取り → `data/offers.json` に保存 → Discordに通知
- `build_site.py` `site/index.html` を作る
- `post_x.py` 新着・金利上げがあった日と毎週月曜に、Xへ投稿する(キーが無ければ文面の表示だけ)
- `.github/workflows/update.yml` GitHub Actionsで毎朝6:30に上の3つを実行し、GitHub Pagesに公開して data/ を保存

## 放っておいて大丈夫な範囲と、人がやること
自動で処理するもの: 毎日の取得・読み取り・公開・投稿、期限切れの削除、一時的な取得失敗(前回の値を表示し続ける)。

人に知らせるもの(Discord。全体障害と投稿失敗はGitHubの失敗メールでも届く):
- 🚨 APIのクレジット切れ・キー無効・ネットワーク障害 → 書いてある対処をする。読み取りはその時点で止まり、サイトは前回の値のまま
- ⚠ 個別の銀行の失敗(初日と7日目だけ) → 404なら `sources.yaml` のURLを直す、403なら外す、など対処の目安が添えてある
- ⚠ Xへの投稿失敗 → キー・権限・投稿回数の上限を確認

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
5. (任意)Settings → Secrets and variables → Actions の Variables に `SITE_URL`(公開URL)を登録すると、canonical・sitemap・X投稿のリンクに使われる
6. (任意)X投稿: developer.x.com でアプリを作り、権限を Read and Write にしてから、Secrets に `X_API_KEY` `X_API_SECRET` `X_ACCESS_TOKEN` `X_ACCESS_TOKEN_SECRET` を登録する。
   登録前でも `python post_x.py --dry-run --force-ranking` で文面を確認できる

## 費用の目安
金利(%)を含む行が変わったページだけClaudeに読ませる。既定のモデルは claude-haiku-5-5 で、月に数十円程度。
読み取りの誤りが多ければ環境変数 `CAMPAIGN_MODEL=claude-opus-5-5` に切り替える(費用は約40倍)。
