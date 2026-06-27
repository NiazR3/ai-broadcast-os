"""WebSocket broadcast — pushes cache snapshots at ~2 Hz."""

import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from backend.market_data import cache_snapshot, TICKER_CLASS, cache_get

logger = logging.getLogger("prod_dash")

active_ws: list[WebSocket] = []


async def broadcast_loop():
    """Push full cache snapshot to all WS clients at ~2 Hz."""
    while True:
        snap = {"type": "update", "data": cache_snapshot()}
        msg = json.dumps(snap, default=str)
        dead = []
        for ws in active_ws:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            if ws in active_ws:
                active_ws.remove(ws)
        await asyncio.sleep(0.5)


async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    active_ws.append(ws)
    try:
        await ws.send_json({"type": "init", "data": cache_snapshot()})
        while True:
            msg = await ws.receive_text()
            try:
                payload = json.loads(msg)
            except json.JSONDecodeError:
                continue
            ticker = payload.get("ticker", "").upper().strip()
            if ticker in TICKER_CLASS:
                entry = cache_get(ticker)
                if entry:
                    await ws.send_json({"type": "focus", "ticker": ticker, **entry})
    except WebSocketDisconnect:
        pass
    finally:
        if ws in active_ws:
            active_ws.remove(ws)
