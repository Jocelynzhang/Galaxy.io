"""End-to-end tests of the WebSocket server and its public-hosting safeguards."""
import time

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server import main
from server.game import config as C


@pytest.fixture
def client():
    with TestClient(main.app) as c:
        yield c


def recv_until(ws, kind, limit=200):
    for _ in range(limit):
        msg = ws.receive_json()
        if msg["t"] == kind:
            return msg
    raise AssertionError(f"no {kind!r} message")


def test_healthz(client):
    body = client.get("/healthz").json()
    assert body["ok"] and body["objects"] >= C.TARGET_PLAYERS


def test_connect_join_and_receive_snapshots(client):
    with client.websocket_connect("/ws") as ws:
        hello = ws.receive_json()
        assert hello["t"] == "hello" and hello["world"] == [C.WORLD_W, C.WORLD_H]
        ws.send_json({"t": "join", "name": "Tester", "vw": 1280, "vh": 720})
        welcome = recv_until(ws, "welcome")
        snap = recv_until(ws, "s")
        assert snap["me"]["id"] == welcome["id"] and "spec" not in snap


def test_spectators_get_leader_snapshots(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"t": "spectate"})
        snap = recv_until(ws, "s")
        assert snap["spec"] == 1


def test_foreign_origin_is_rejected(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws", headers={"origin": "https://evil.example"}) as ws:
            ws.receive_json()


def test_same_host_origin_is_allowed(client):
    with client.websocket_connect("/ws", headers={"origin": "http://testserver"}) as ws:
        assert ws.receive_json()["t"] == "hello"


def test_per_ip_connection_cap(client, monkeypatch):
    monkeypatch.setattr(C, "MAX_CONNECTIONS_PER_IP", 2)
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        a.receive_json(), b.receive_json()
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/ws") as c:
                c.receive_json()


def test_full_universe_lets_you_watch(client, monkeypatch):
    monkeypatch.setattr(C, "MAX_HUMANS", 1)
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        a.send_json({"t": "join", "name": "first"})
        recv_until(a, "welcome")
        b.send_json({"t": "join", "name": "second"})
        assert recv_until(b, "full")["t"] == "full"
        assert recv_until(b, "s")["spec"] == 1


def test_join_cooldown_blocks_spam(client):
    with client.websocket_connect("/ws") as ws:
        ws.receive_json()
        before = main.game.humans()
        for _ in range(5):
            ws.send_json({"t": "join", "name": "spam"})
        recv_until(ws, "welcome")
        time.sleep(0.2)
        assert main.game.humans() == before + 1


def test_flooding_connection_is_closed(client, monkeypatch):
    monkeypatch.setattr(C, "MSG_BURST", 5.0)
    monkeypatch.setattr(C, "MSG_RATE", 1.0)
    monkeypatch.setattr(C, "MSG_ABUSE_DROPS", 20)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as ws:
            for _ in range(200):
                ws.send_text('{"t":"view","vw":800,"vh":600}')
            for _ in range(500):
                ws.receive_json()


def test_game_loop_survives_a_crashing_tick(client, monkeypatch):
    real_step = main.game.world.step
    calls = {"n": 0}

    def flaky(dt):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real_step(dt)

    monkeypatch.setattr(main.game.world, "step", flaky)
    errors, tick = main.game.errors, main.game.world.tick
    time.sleep(0.3)
    assert main.game.errors == errors + 1
    assert main.game.world.tick > tick, "the universe keeps ticking after an error"
