"""demo-gate のテスト。

FastAPI の TestClient で実際にリクエストを投げて挙動を確認する。
レートリミットはモジュールローカル dict なので各テストで state をリセットする。
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from demo_gate import attach_demo_gate
from demo_gate import _ratelimit


@pytest.fixture(autouse=True)
def _reset_ratelimit():
    """各テスト前にレートリミットの内部 state をクリア。"""
    _ratelimit._fail_log.clear()
    _ratelimit._blocked_until.clear()


def _make_app(**kwargs) -> FastAPI:
    app = FastAPI()

    @app.get("/")
    def root():
        return {"page": "root"}

    @app.get("/api/foo")
    def api_foo():
        return {"api": "foo"}

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    attach_demo_gate(app, **kwargs)
    return app


def _make_client(**kwargs) -> TestClient:
    """Secure Cookie を送るため https:// ベースの TestClient を作る。"""
    return TestClient(_make_app(**kwargs), base_url="https://testserver")


# --- 1. ゲート無効時の素通し ---------------------------------------------------


def test_gate_disabled_passes_through(monkeypatch):
    monkeypatch.delenv("DEMO_ACCESS_KEY", raising=False)
    monkeypatch.delenv("DEMO_ACCESS_KEY_GUEST", raising=False)
    client = _make_client()

    assert client.get("/").status_code == 200
    assert client.get("/api/foo").status_code == 200


# --- 2. 未認証でトップにアクセス → ゲート画面へ 302 ---------------------------


def test_unauthenticated_html_redirects_to_gate(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_KEY", "secret")
    client = _make_client()

    res = client.get("/", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/demo-gate.html"


# --- 3. 未認証で API を叩くと 401 JSON ----------------------------------------


def test_unauthenticated_api_returns_401(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_KEY", "secret")
    client = _make_client()

    res = client.get("/api/foo")
    assert res.status_code == 401
    body = res.json()
    assert body["detail"] == "demo_access required"
    assert body["gate"] == "/demo-gate.html"


# --- 4. 正しいキーで認証 → Cookie 発行 → 以後アクセス可 ------------------------


def test_login_with_correct_key_issues_cookie(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_KEY", "secret")
    client = _make_client()

    res = client.post("/api/demo-auth", json={"key": "secret"})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "role": "internal"}
    assert "demo_access" in client.cookies

    # Cookie が付いた状態でアクセス → ゲートを通過して本来の 200 が返る
    assert client.get("/", follow_redirects=False).status_code == 200
    assert client.get("/api/foo").status_code == 200


# --- 5. 間違ったキーを連打 → ブロック発動 -------------------------------------


def test_wrong_key_triggers_block(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_KEY", "secret")
    client = _make_client()

    # 3 回失敗までは通常の 401 を返しつつ、3 回目でブロック発動
    for _ in range(3):
        res = client.post("/api/demo-auth", json={"key": "wrong"})
        assert res.status_code == 401

    # ブロック中は正しいキーを送っても 401
    res = client.post("/api/demo-auth", json={"key": "secret"})
    assert res.status_code == 401


# --- 6. guest キーで guest ロール Cookie 発行 ---------------------------------


def test_guest_key_issues_guest_role(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_KEY", "internal-key")
    monkeypatch.setenv("DEMO_ACCESS_KEY_GUEST", "guest-key")
    client = _make_client()

    res = client.post("/api/demo-auth", json={"key": "guest-key"})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "role": "guest"}


# --- 7. 改ざんした Cookie は弾かれる -----------------------------------------


def test_tampered_cookie_is_rejected(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_KEY", "secret")
    client = _make_client()

    # 正しく認証して Cookie を取得
    client.post("/api/demo-auth", json={"key": "secret"})
    assert client.get("/", follow_redirects=False).status_code == 200

    # Cookie を書き換える (ロール部分を guest に改ざん)
    original = client.cookies.get("demo_access")
    parts = original.split(".")
    tampered = f"{parts[0]}.guest.{parts[2]}"
    client.cookies.set("demo_access", tampered)

    res = client.get("/", follow_redirects=False)
    assert res.status_code == 302  # リダイレクトされる = 未認可扱い


# --- 8. extra_public_prefixes で /healthz を未認証公開 -----------------------


def test_extra_public_prefixes_opens_healthz(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_KEY", "secret")
    client = _make_client(extra_public_prefixes=("/healthz",))

    # /healthz だけ未認証で通る
    assert client.get("/healthz").status_code == 200
    # / は相変わらずゲート
    assert client.get("/", follow_redirects=False).status_code == 302


# --- 9. extra_verifier による動的キー検証 -------------------------------------


def test_extra_verifier_accepts_dynamic_key(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_KEY", "static-key")

    async def my_verifier(key: str) -> str | None:
        if key == "dynamic-guest":
            return "guest"
        return None

    client = TestClient(
        _make_app(extra_verifier=my_verifier), base_url="https://testserver"
    )

    # 静的キーにマッチしないが、verifier が guest を返す
    res = client.post("/api/demo-auth", json={"key": "dynamic-guest"})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "role": "guest"}

    # verifier が None を返すキーは 401
    res = client.post("/api/demo-auth", json={"key": "unknown"})
    assert res.status_code == 401


# --- 10. カンマ区切りで複数キー受け入れ (ローテーション用) ----------------------


def test_comma_separated_keys_accept_all(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_KEY", "new-primary,old-secondary")
    monkeypatch.setenv("DEMO_ACCESS_KEY_GUEST", "guest-a,guest-b")
    client = _make_client()

    # 新旧どちらの internal キーでも internal ロールで通る
    res = client.post("/api/demo-auth", json={"key": "new-primary"})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "role": "internal"}

    client2 = _make_client()
    res = client2.post("/api/demo-auth", json={"key": "old-secondary"})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "role": "internal"}

    # guest キーの片方も通る
    client3 = _make_client()
    res = client3.post("/api/demo-auth", json={"key": "guest-b"})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "role": "guest"}


# --- 11. 単一キー運用は v0.1.0 と同じ挙動 (後方互換) --------------------------


def test_single_key_still_works_unchanged(monkeypatch):
    monkeypatch.setenv("DEMO_ACCESS_KEY", "secret")
    monkeypatch.delenv("DEMO_ACCESS_KEY_GUEST", raising=False)
    client = _make_client()

    res = client.post("/api/demo-auth", json={"key": "secret"})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "role": "internal"}

    # 空白やカンマ無しで従来どおり
    res = client.post("/api/demo-auth", json={"key": "wrong"})
    assert res.status_code == 401
