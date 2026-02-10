from __future__ import annotations

import asyncio
import os
import random
import string
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Kahoo Lite")

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


QUESTION_DURATION_SEC = 20


def gen_pin(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


@dataclass
class Player:
    name: str
    score: int = 0
    last_answer_correct: Optional[bool] = None


@dataclass
class Room:
    pin: str
    host_name: str
    players: Dict[str, Player] = field(default_factory=dict)
    current_q: int = 0
    questions: List[dict] = field(default_factory=list)
    started: bool = False

    question_locked: bool = False
    question_ends_at: Optional[float] = None
    answered_players: Set[str] = field(default_factory=set)
    round_id: int = 0


ROOMS: Dict[str, Room] = {}
SOCKETS: Dict[str, List[WebSocket]] = {}

DEFAULT_QUESTIONS = [
    {
        "question": "Python 的套件管理常用工具是？",
        "choices": ["pip", "docker", "brew", "make"],
        "answer": 0,
    },
    {
        "question": "HTTP 狀態碼 200 代表？",
        "choices": ["錯誤", "成功", "重導向", "未授權"],
        "answer": 1,
    },
]


class CreateRoomBody(BaseModel):
    host_name: str


class JoinRoomBody(BaseModel):
    pin: str
    name: str


class SubmitBody(BaseModel):
    pin: str
    name: str
    choice_index: int


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/rooms")
def create_room(body: CreateRoomBody):
    pin = gen_pin()
    while pin in ROOMS:
        pin = gen_pin()

    room = Room(pin=pin, host_name=body.host_name, questions=DEFAULT_QUESTIONS.copy())
    ROOMS[pin] = room
    SOCKETS[pin] = []
    return {"pin": pin, "host": body.host_name, "questions": len(room.questions)}


@app.post("/rooms/join")
def join_room(body: JoinRoomBody):
    room = ROOMS.get(body.pin)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    reconnected = body.name in room.players
    if not reconnected:
        room.players[body.name] = Player(name=body.name)

    return {
        "ok": True,
        "pin": body.pin,
        "player_count": len(room.players),
        "reconnected": reconnected,
    }


@app.post("/rooms/{pin}/start")
async def start_game(pin: str):
    room = ROOMS.get(pin)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    room.started = True
    room.current_q = 0
    for p in room.players.values():
        p.last_answer_correct = None

    await start_round(pin)
    return {"ok": True}


@app.post("/rooms/submit")
async def submit_answer(body: SubmitBody):
    room = ROOMS.get(body.pin)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    if not room.started:
        raise HTTPException(status_code=400, detail="Game not started")

    player = room.players.get(body.name)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    if room.question_locked:
        raise HTTPException(status_code=400, detail="Question locked")

    if body.name in room.answered_players:
        raise HTTPException(status_code=400, detail="Already answered")

    now = time.time()
    if room.question_ends_at is not None and now >= room.question_ends_at:
        room.question_locked = True
        await broadcast_state(body.pin)
        raise HTTPException(status_code=400, detail="Time is up")

    q = room.questions[room.current_q]
    correct = body.choice_index == q["answer"]
    player.last_answer_correct = correct
    room.answered_players.add(body.name)

    bonus = 0
    if correct:
        seconds_left = max(0, int((room.question_ends_at or now) - now))
        bonus = max(20, min(100, 20 + seconds_left * 4))
        player.score += bonus

    await broadcast_state(body.pin)
    return {
        "ok": True,
        "correct": correct,
        "score": player.score,
        "bonus": bonus,
    }


@app.post("/rooms/{pin}/next")
async def next_question(pin: str):
    room = ROOMS.get(pin)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.current_q < len(room.questions) - 1:
        room.current_q += 1
        for p in room.players.values():
            p.last_answer_correct = None
        await start_round(pin)
        return {"ok": True, "current_q": room.current_q}

    room.question_locked = True
    await broadcast_state(pin)
    return {"ok": True, "current_q": room.current_q, "finished": True}


@app.get("/rooms/{pin}/leaderboard")
def leaderboard(pin: str):
    room = ROOMS.get(pin)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    ranking = sorted(room.players.values(), key=lambda x: x.score, reverse=True)
    return {
        "pin": pin,
        "ranking": [{"name": p.name, "score": p.score} for p in ranking],
    }


@app.websocket("/ws/{pin}")
async def ws_room(websocket: WebSocket, pin: str):
    await websocket.accept()
    if pin not in SOCKETS:
        SOCKETS[pin] = []
    SOCKETS[pin].append(websocket)
    await send_state_to_socket(pin, websocket)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if pin in SOCKETS and websocket in SOCKETS[pin]:
            SOCKETS[pin].remove(websocket)


async def start_round(pin: str):
    room = ROOMS.get(pin)
    if not room:
        return

    room.question_locked = False
    room.question_ends_at = time.time() + QUESTION_DURATION_SEC
    room.answered_players.clear()
    room.round_id += 1

    this_round = room.round_id
    await broadcast_state(pin)
    asyncio.create_task(auto_lock_round(pin, this_round))


async def auto_lock_round(pin: str, round_id: int):
    room = ROOMS.get(pin)
    if not room or room.question_ends_at is None:
        return

    sleep_for = max(0.0, room.question_ends_at - time.time())
    await asyncio.sleep(sleep_for)

    room = ROOMS.get(pin)
    if not room:
        return

    if room.round_id != round_id:
        return

    if not room.question_locked:
        room.question_locked = True
        await broadcast_state(pin)


async def send_state_to_socket(pin: str, ws: WebSocket):
    room = ROOMS.get(pin)
    if not room:
        await ws.send_json({"error": "room_not_found"})
        return

    q = room.questions[room.current_q]
    now = time.time()
    seconds_left = 0
    if room.question_ends_at is not None:
        seconds_left = max(0, int(room.question_ends_at - now))

    await ws.send_json(
        {
            "pin": pin,
            "started": room.started,
            "current_q": room.current_q,
            "question": q["question"],
            "choices": q["choices"],
            "question_locked": room.question_locked,
            "seconds_left": seconds_left,
            "question_duration": QUESTION_DURATION_SEC,
            "answered_count": len(room.answered_players),
            "players": [
                {
                    "name": p.name,
                    "score": p.score,
                    "last_answer_correct": p.last_answer_correct,
                }
                for p in room.players.values()
            ],
        }
    )


async def broadcast_state(pin: str):
    dead = []
    for ws in SOCKETS.get(pin, []):
        try:
            await send_state_to_socket(pin, ws)
        except Exception:
            dead.append(ws)

    for ws in dead:
        if ws in SOCKETS.get(pin, []):
            SOCKETS[pin].remove(ws)


# Serve frontend directly from FastAPI (Render-friendly single service deploy)
FRONTEND_DIR = (Path(__file__).resolve().parent.parent.parent / "frontend")
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
