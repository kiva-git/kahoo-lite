from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Kahoo Lite")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    # Same name is treated as reconnect (keep score/state)
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
    await broadcast_state(pin)
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

    q = room.questions[room.current_q]
    correct = body.choice_index == q["answer"]
    player.last_answer_correct = correct
    if correct:
        player.score += 100

    await broadcast_state(body.pin)
    return {"ok": True, "correct": correct, "score": player.score}


@app.post("/rooms/{pin}/next")
async def next_question(pin: str):
    room = ROOMS.get(pin)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.current_q < len(room.questions) - 1:
        room.current_q += 1
        for p in room.players.values():
            p.last_answer_correct = None
    await broadcast_state(pin)
    return {"ok": True, "current_q": room.current_q}


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


async def send_state_to_socket(pin: str, ws: WebSocket):
    room = ROOMS.get(pin)
    if not room:
        await ws.send_json({"error": "room_not_found"})
        return

    q = room.questions[room.current_q]
    await ws.send_json(
        {
            "pin": pin,
            "started": room.started,
            "current_q": room.current_q,
            "question": q["question"],
            "choices": q["choices"],
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
