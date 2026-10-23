# demo-gate

FastAPI ベースのデモアプリに**合言葉式の軽量アクセスゲート**を 1 行で追加するパッケージ。

```python
from fastapi import FastAPI
from demo_gate import attach_demo_gate

app = FastAPI()
attach_demo_gate(app)
```

---

## 対応範囲

- **Python**: 3.14 以上。動作確認と CI は 3.14 系の最新パッチ版だけを対象にします
- **対応**: FastAPI / Starlette (ASGI)
- **非対応**: Flask, Django, Streamlit, Gradio など (別手段で保護すること)

## ⚠️ 利用上の注意

**本パッケージはデモ・検証用途専用です。本番サービスでの使用を想定していません。**

- **個人情報・機密情報を含むアプリには使用しないこと**。合言葉 1 つだけで守る簡易ゲートです
- 認証強度は Entra ID 等の本格 IdP に劣ります。共有された合言葉の漏洩リスクを前提とした設計です
- 監査ログ、パスワードローテーション、MFA、アカウント個別管理などの本番要件は満たしません
- 本番相当のデータや業務システムへのアクセス保護には使用しないでください

## こんなデモに向いている

**一時的に立てたデモアプリを、短期間だけサクッと守りたい**場面を想定しています。

### 使い所の例

- 顧客との打ち合わせ期間中、デモ URL を限定共有したい (1〜2 週間で閉じる想定)
- 社内勉強会・ハンズオン用の一時的な共有環境
- POC として立てたアプリを関係者だけに見せたい
- 開発中のステージング URL を外部レビュワーに触ってもらいたい

### デモで使う時のメリット

- **導入が 1 行**: 既存 FastAPI アプリに `attach_demo_gate(app)` を足すだけ
- **キー配布だけで済む**: 顧客にアカウント発行・MFA 設定を依頼せず、URL + 合言葉を Slack/Teams で渡すだけ
- **ゲスト用と社内用を分けられる**: `DEMO_ACCESS_KEY_GUEST` で顧客向けキーを別枠で発行 → デモ後はこちらだけローテーション可
- **撤去も 1 行**: デモ期間が終わったら行を消すかキーを空にすれば即無効化
- **コードが汚れない**: アプリ本体のコードに認証ロジックが混ざらないので、GitHub でサンプルとして公開するときに認証部分を気にしなくていい
- **日本語カスタム画面**: 顧客の前で画面共有しても、英語ダイアログが出ず統一感がある

## なぜ Basic 認証や Entra ID ではなく demo-gate か

- **Entra ID 認証は MFA 必須ポリシーを踏むことが多く、デモ中に顧客へ負担**をかける(スマホでコード入力はテンポを壊す)
- **Basic 認証** でも機能要件は満たせるが、ブラウザ標準ダイアログの UX とログアウト不可が気になる
- → 日本語カスタム画面 + Cookie + ロール分離 (internal/guest) を揃えた軽量ゲートとして実装

## セキュリティ設計

- Cookie は HMAC-SHA256 署名付き (HttpOnly / Secure / SameSite=Lax)
- HTTPS / WSS で利用すること。HTTP と WebSocket の両方で Cookie を検証します
- HMAC 比較は `hmac.compare_digest` で timing attack 耐性
- 簡易ブルートフォース抑制 (同一 IP が 60 秒で 3 回試行 → 5 分ブロック。認証成功時にリセット)。並列試行も数えます
- 制限状態はプロセス内のみ。複数ワーカー・複数インスタンスでは共有されません
- ログイン後は常に `/` に移動します。`next` による遷移先の指定は受け付けません
- ゲート画面の外部スクリプトは SRI で改変を検知します
- `DEMO_ACCESS_KEY` と `DEMO_ACCESS_KEY_GUEST` が両方未設定の場合だけゲートは無効 (素通し)

---

## 使い方

### 1. インストール

```bash
python -m pip install --upgrade --upgrade-strategy eager demo-gate
```

利用先アプリに依存の固定やロックファイルがある場合は、そちらも更新してください。
更新後はアプリのテストを実行し、再デプロイします。

### 2. アプリに組み込む

```python
from fastapi import FastAPI
from demo_gate import attach_demo_gate

app = FastAPI()
attach_demo_gate(app)
```

### 3. 環境変数でキーを設定

```bash
az webapp config appsettings set ... --settings DEMO_ACCESS_KEY=your-secret
```

キーは 16 文字以上のランダム文字列を推奨:

```bash
openssl rand -base64 24
```

`DEMO_SESSION_SECRET` も、合言葉とは別のランダムな値で設定することを推奨します。

## 動的なキーの差し込み (DB 連携など)

アプリ側で独自の検証ロジック (例: Cosmos に保存した一時キー) を足したい場合、
`extra_verifier` フックを使います:

```python
async def my_dynamic_verifier(key: str) -> str | None:
    # "internal" | "guest" | None
    if await my_db_lookup(key):
        return "guest"
    return None

attach_demo_gate(app, extra_verifier=my_dynamic_verifier)
```

## ヘルスチェック / 可用性テストを使う場合

App Service の正常性チェックや Application Insights の可用性テスト等、
外部から未認証で特定 URL を叩く監視を併用する場合は、対象パスをゲート外に出します:

```python
@app.get("/healthz")
async def healthz():
    return {"ok": True}

attach_demo_gate(app, extra_public_exact=("/healthz",))
```

なお SDK 経由のログ・メトリクス収集 (requests / traces / exceptions 等) は
アプリ内部から送信されるためゲートの影響を受けません。

## 環境変数

| 名前 | 意味 | デフォルト |
|---|---|---|
| `DEMO_ACCESS_KEY` | 社内メンバー向け合言葉 (internal ロール)。カンマ区切りで複数指定可 (キーローテーション用) | (guest キーも未設定ならゲート無効) |
| `DEMO_ACCESS_KEY_GUEST` | 静的ゲスト用合言葉 (guest ロール)。カンマ区切りで複数指定可 | (未設定) |
| `DEMO_SESSION_SECRET` | Cookie 署名鍵。未設定ならキーから派生 | (派生) |
| `DEMO_INTERNAL_TTL_HOURS` | internal Cookie の有効時間 | `168` (7日) |
| `DEMO_GUEST_TTL_HOURS` | guest Cookie の有効時間 | `24` (1日) |
| `DEMO_GATE_CONTACT` | ゲート画面に表示する連絡先名 | `管理者` |

### キーローテーション

合言葉が漏れた・定期的に切り替えたい場合、カンマ区切りで新旧両方を受け入れる期間を作れます:

```bash
# 移行期間中: 新旧どちらでもログイン可
DEMO_ACCESS_KEY="new-primary-key,old-key-being-rotated-out"

# 切り替え完了後: 旧キーを削除
DEMO_ACCESS_KEY="new-primary-key"
```

`DEMO_SESSION_SECRET` を明示指定していれば、環境変数を書き換えても既存 Cookie は失効しません。
未指定の場合、Cookie 署名鍵は環境変数値から派生するため、値を変えると既存セッションは全てログアウトされます。

## 開発

```bash
python -m pip install --upgrade --upgrade-strategy eager -e ".[test]"
python -m pytest -q
```

CI と同じビルド・Python 依存監査も実行する場合:

```bash
python -m pip install --upgrade setuptools wheel build pip-audit
python -m build
python -m pip list --format=freeze --exclude-editable > audit-requirements.txt
python -m pip_audit --strict --no-deps --disable-pip -r audit-requirements.txt
```

監査用ファイルは、editable インストールを除いた環境全体 (間接依存・ビルド・テスト用を含む) のスナップショットです。

## 顧客にソースコードを配布する時

デモ期間が終わって顧客にコードを渡す場合は以下を検討してください:

- `attach_demo_gate(app)` の呼び出しと import を削除する
- 本番で認証が必要なら Entra ID / Azure Easy Auth 等の本格 IdP を使う
- demo-gate は本番運用を想定していません

## メンテナンスポリシー

- 作者個人のデモ運用に必要な、小さな実装を維持します。古い Python 向けの互換性や本格的な認証基盤の機能は増やしません
- Dependabot が Python 依存と GitHub Actions の更新 PR をそれぞれ週次でまとめます。CI の結果を確認して手動でマージします
- CI は push / PR / 週次 / 手動実行で最新の依存を解決し、テスト・ビルド・`pip-audit` を実行します。既知の脆弱性や監査エラーがあれば失敗させます
- PyPI 公開前にもテストと監査を実行します。脆弱性を無視する設定や自動マージは追加しません
- 重要な用途に使う場合は、自身で fork するか別手段を検討してください
