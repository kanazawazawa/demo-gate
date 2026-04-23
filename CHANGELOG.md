# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-04-23

### Changed
- ゲート画面の注釈を変更: 「本機能はデモ公開用の簡易認証です。本番環境には対応しておりません」の注意書きを追加
- 注釈の文字色を濃く調整

## [0.2.0] - 2026-04-22

### Added
- `DEMO_ACCESS_KEY` / `DEMO_ACCESS_KEY_GUEST` でカンマ区切りによる複数キー指定に対応 (キーローテーション用途)
- README に「キーローテーション」節を追加

### Changed
- 内部 API: `access_key_internal()` / `access_key_guest()` を `access_keys_internal()` / `access_keys_guest()` (list を返す) に置き換え。これらは private helper のため公開 API への影響はなし
- `_session_secret()` の種を「環境変数の生値」ベースに変更。単一キー運用時の署名鍵は v0.1.0 と同じになり既存 Cookie は引き続き有効

### Notes
- 単一キー運用 (`DEMO_ACCESS_KEY="secret"` 等、カンマを含まない値) は v0.1.0 と完全に同じ挙動。変更不要

## [0.1.0] - 2026-04-22

### Added
- 合言葉式アクセスゲート Middleware (`DemoAccessGateMiddleware`)
- HMAC-SHA256 署名 Cookie による認証 (`internal` / `guest` ロール)
- 認証エンドポイント (`/api/demo-auth`, `/api/demo-auth/status`, `/api/demo-auth/logout`)
- ゲート画面 (`/demo-gate.html`)
- 動的キー検証フック (`extra_verifier`)
- 公開パス拡張オプション (`extra_public_prefixes`, `extra_public_exact`)
- 連絡先カスタマイズ環境変数 `DEMO_GATE_CONTACT`
- 簡易ブルートフォース抑制 (60秒で3回失敗 → 5分ブロック)
