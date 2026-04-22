# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
