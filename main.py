import os, sys, json, uuid, time, hashlib, hmac, base64, sqlite3, asyncio
from typing import Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(__file__))
import Board
import AI

app = FastAPI(title="caro309")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
bearer = HTTPBearer(auto_error=False)

SECRET = os.environ.get("SECRET_KEY", "caro309-dev-key-change-in-prod")
DB     = os.path.join(os.path.dirname(__file__), "caro309.db")

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id       TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            elo      INTEGER DEFAULT 1000,
            wins     INTEGER DEFAULT 0,
            losses   INTEGER DEFAULT 0,
            draws    INTEGER DEFAULT 0,
            created  INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS games (
            id       TEXT PRIMARY KEY,
            px       TEXT,
            po       TEXT,
            winner   TEXT,
            moves    INTEGER DEFAULT 0,
            size     INTEGER DEFAULT 15,
            ended    INTEGER DEFAULT 0
        );
    """)
    try:
        db.execute("ALTER TABLE users ADD COLUMN draws INTEGER DEFAULT 0")
        db.commit()
    except Exception:
        pass
    db.commit()
    db.close()

init_db()

def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()

def make_token(uid: str, name: str) -> str:
    h = _b64(json.dumps({"alg":"HS256"}).encode())
    b = _b64(json.dumps({"sub":uid,"name":name,"exp":int(time.time())+86400*14}).encode())
    s = _b64(hmac.new(SECRET.encode(), f"{h}.{b}".encode(), hashlib.sha256).digest())
    return f"{h}.{b}.{s}"

def check_token(token: str) -> Optional[dict]:
    try:
        h, b, s = token.split(".")
        exp_s = _b64(hmac.new(SECRET.encode(), f"{h}.{b}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(s, exp_s):
            return None
        payload = json.loads(base64.urlsafe_b64decode(b + "=="))
        return payload if payload.get("exp", 0) > time.time() else None
    except Exception:
        return None

def get_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    if not creds:
        raise HTTPException(401, "Chưa đăng nhập")
    p = check_token(creds.credentials)
    if not p:
        raise HTTPException(401, "Token không hợp lệ")
    return p

def hash_pw(pw: str) -> str:
    """Hash mật khẩu bằng PBKDF2 + salt cố định."""
    salt = b"caro309_fixed_salt_v1"
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 100_000).hex()

def verify_pw(pw: str, stored_hash: str) -> bool:
    """So sánh mật khẩu với hash đã lưu — thử TẤT CẢ phương thức hash có thể."""
    # 1. PBKDF2 mới (current)
    salt = b"caro309_fixed_salt_v1"
    if stored_hash == hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 100_000).hex():
        return True
    # 2. HMAC(SECRET, pw)
    if stored_hash == hmac.new(SECRET.encode(), pw.encode(), hashlib.sha256).hexdigest():
        return True
    # 3. SHA256(SECRET + pw)
    if stored_hash == hashlib.sha256((SECRET + pw).encode()).hexdigest():
        return True
    # 4. SHA256(pw) thuần
    if stored_hash == hashlib.sha256(pw.encode()).hexdigest():
        return True
    # 5. HMAC(pw, SECRET) — reversed
    if stored_hash == hmac.new(pw.encode(), SECRET.encode(), hashlib.sha256).hexdigest():
        return True
    # 6. SHA256(pw + SECRET)
    if stored_hash == hashlib.sha256((pw + SECRET).encode()).hexdigest():
        return True
    # 7. PBKDF2 with SECRET as salt
    if stored_hash == hashlib.pbkdf2_hmac("sha256", pw.encode(), SECRET.encode(), 100_000).hex():
        return True
    # 8. MD5 (unlikely but just in case)
    if stored_hash == hashlib.md5(pw.encode()).hexdigest():
        return True
    # 9. Mật khẩu lưu plaintext (dev mode)
    if stored_hash == pw:
        return True
    return False

# Endpoint debug: kiểm tra hash format trong DB (chỉ dùng khi debug, xóa sau)
@app.get("/debug/check_hash/{username}")
def debug_check_hash(username: str):
    db = get_db()
    row = db.execute("SELECT password FROM users WHERE username=?", (username,)).fetchone()
    db.close()
    if not row:
        return {"error": "User not found"}
    h = row["password"]
    return {"hash_length": len(h), "hash_prefix": h[:16], "hash_suffix": h[-8:]}

class AuthIn(BaseModel):
    username: str
    password: str

@app.post("/auth/register")
def register(body: AuthIn):
    if len(body.username) < 3:
        raise HTTPException(400, "Tên phải ít nhất 3 ký tự")
    if len(body.password) < 6:
        raise HTTPException(400, "Mật khẩu phải ít nhất 6 ký tự")
    if not all(c.isalnum() or c == '_' for c in body.username):
        raise HTTPException(400, "Tên chỉ dùng chữ, số, gạch dưới")
    db = get_db()
    if db.execute("SELECT 1 FROM users WHERE username=?", (body.username,)).fetchone():
        db.close()
        raise HTTPException(400, "Tên đã tồn tại")
    uid = str(uuid.uuid4())
    db.execute("INSERT INTO users VALUES (?,?,?,1000,0,0,0,?)",
               (uid, body.username, hash_pw(body.password), int(time.time())))
    db.commit(); db.close()
    return {"token": make_token(uid, body.username),
            "username": body.username, "elo": 1000, "wins": 0, "losses": 0, "draws": 0}

@app.post("/auth/login")
def login(body: AuthIn):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE username=?", (body.username,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(401, "Sai tên hoặc mật khẩu")
    
    if not verify_pw(body.password, row["password"]):
        db.close()
        raise HTTPException(401, "Sai tên hoặc mật khẩu")
    
    # Auto-migrate: nếu hash cũ, cập nhật sang PBKDF2 mới
    new_hash = hash_pw(body.password)
    if row["password"] != new_hash:
        try:
            db.execute("UPDATE users SET password=? WHERE id=?", (new_hash, row["id"]))
            db.commit()
        except Exception:
            pass
    
    db.close()
    return {"token": make_token(row["id"], row["username"]),
            "username": row["username"], "elo": row["elo"],
            "wins": row["wins"], "losses": row["losses"], "draws": row["draws"] or 0}

@app.get("/auth/me")
def me(user=Depends(get_user)):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (user["sub"],)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404)
    return {"username": row["username"], "elo": row["elo"],
            "wins": row["wins"], "losses": row["losses"], "draws": row["draws"]}

class ResetPW(BaseModel):
    username: str
    new_password: str
    admin_key: str = ""

@app.post("/auth/reset_password")
def reset_password(body: ResetPW):
    """Reset mật khẩu — cần admin_key = SECRET hoặc 'caro309reset'."""
    if body.admin_key not in (SECRET, "caro309reset"):
        raise HTTPException(403, "Sai admin key")
    if len(body.new_password) < 6:
        raise HTTPException(400, "Mật khẩu phải ít nhất 6 ký tự")
    db = get_db()
    row = db.execute("SELECT id FROM users WHERE username=?", (body.username,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(404, "Không tìm thấy user")
    db.execute("UPDATE users SET password=? WHERE id=?", (hash_pw(body.new_password), row["id"]))
    db.commit(); db.close()
    return {"ok": True, "message": f"Đã reset mật khẩu cho {body.username}"}

@app.get("/leaderboard")
def leaderboard():
    db = get_db()
    rows = db.execute(
        "SELECT username,elo,wins,losses,draws,created FROM users ORDER BY elo DESC LIMIT 20"
    ).fetchall()
    db.close()
    result = []
    for r in rows:
        d = dict(r)
        # Đảm bảo không có giá trị None
        d["elo"] = d.get("elo") or 1000
        d["wins"] = d.get("wins") or 0
        d["losses"] = d.get("losses") or 0
        d["draws"] = d.get("draws") or 0
        ts = d.get("created", 0)
        if ts:
            import datetime
            dt = datetime.datetime.fromtimestamp(ts)
            d["joined"] = dt.strftime("%d/%m/%Y")
        else:
            d["joined"] = "—"
        result.append(d)
    return result

class NewGame(BaseModel):
    size: int = 15

class MoveIn(BaseModel):
    row:   int
    col:   int
    board: list
    level: str = "Hard"
    token: str = "" 

import threading
_ai_lock = threading.Lock()

def _update_ai_stats(token: str, won: bool):
    """Cập nhật wins/losses khi chơi vs AI (không tính ELO)."""
    if not token:
        return
    payload = check_token(token)
    if not payload:
        return
    uid = payload.get("sub", "")
    if not uid:
        return
    try:
        db = get_db()
        if won:
            db.execute("UPDATE users SET wins=wins+1 WHERE id=?", (uid,))
        else:
            db.execute("UPDATE users SET losses=losses+1 WHERE id=?", (uid,))
        db.commit(); db.close()
    except Exception as e:
        print("Stats update error:", e)

@app.post("/new_game")
def new_game(body: NewGame):
    size = max(10, min(20, body.size))
    with _ai_lock:
        Board.init_board(size)
        return {"board": [row[:] for row in Board.board], "size": Board.SIZE}

@app.post("/move")
def do_move(body: MoveIn):
    r, c = body.row, body.col

    # --- Validate và normalize board từ frontend ---
    if not body.board or not isinstance(body.board, list):
        raise HTTPException(400, "Board không hợp lệ")

    size = len(body.board)
    if not (10 <= size <= 20):
        raise HTTPException(400, f"Kích thước board không hợp lệ: {size}")

    # Normalize: chỉ giữ "" / "X" / "O"
    clean = []
    for row in body.board:
        if not isinstance(row, list) or len(row) != size:
            raise HTTPException(400, "Board không vuông")
        clean.append([v if v in ("X", "O") else "" for v in row])

    if not (0 <= r < size and 0 <= c < size):
        raise HTTPException(400, f"Tọa độ ({r},{c}) ngoài bàn {size}×{size}")

    # Frontend gửi board đã có X ở (r,c) — nếu chưa thì đặt
    if clean[r][c] == "":
        clean[r][c] = "X"
    elif clean[r][c] != "X":
        raise HTTPException(400, f"Ô ({r},{c}) đã có quân '{clean[r][c]}'")

    # Lock global Board state để tránh race condition giữa các request
    with _ai_lock:
        Board.board = [row[:] for row in clean]
        Board.SIZE  = size

        if Board.check_winner("X", r, c):
            _update_ai_stats(body.token, won=True)
            return {"board": Board.board, "winner": "X", "ai_move": None, "candidates": []}

        # Kiểm tra board không trống (phải có ít nhất 1 quân)
        has_pieces = any(Board.board[i][j] != "" for i in range(size) for j in range(size))
        if not has_pieces:
            raise HTTPException(400, "Board trống — không thể tính AI")

        cands     = AI.candidate_moves()
        ar, ac    = AI.ai_move(body.level)

        # Đảm bảo AI trả về ô hợp lệ
        if ar is None or ac is None:
            # Fallback: chọn ô trống đầu tiên gần quân
            if cands:
                ar, ac = cands[0]
            else:
                # Tìm ô trống bất kỳ
                for i in range(size):
                    for j in range(size):
                        if Board.board[i][j] == "":
                            ar, ac = i, j
                            break
                    if ar is not None:
                        break

        Board.board[ar][ac] = "O"
        winner = "O" if Board.check_winner("O", ar, ac) else None

        if winner == "O":
            _update_ai_stats(body.token, won=False)

        # Đảm bảo ai_move nằm trong candidates để hiển thị đúng
        ai_move_in_cands = any(cr == ar and cc == ac for cr, cc in cands)
        if not ai_move_in_cands:
            cands.insert(0, (ar, ac))

        result_board = [row[:] for row in Board.board]

    return {
        "board":      result_board,
        "winner":     winner,
        "ai_move":    [ar, ac],
        "candidates": [[r2, c2] for r2, c2 in cands],
    }

class Rooms:
    def __init__(self):
        self.rooms: dict = {}

    def create(self, size=15, creator="") -> str:
        rid = str(uuid.uuid4())[:8].upper()
        self.rooms[rid] = {
            "players":    {},
            "spectators": [],
            "board":      [[""] * size for _ in range(size)],
            "size":       size,
            "turn":       "X",
            "status":     "waiting",
            "winner":     None,
            "moves":      0,
            "created":    time.time(),
            "creator":    creator,
            "chat":       [],
            "rematch":    set(),
            "timer_x":    60,   # giây còn lại của X
            "timer_o":    60,   # giây còn lại của O
            "turn_start": None, # thời điểm bắt đầu lượt hiện tại
        }
        return rid

    def info(self, rid: str) -> dict:
        r = self.rooms.get(rid, {})
        return {
            "room_id":    rid,
            "status":     r.get("status", "?"),
            "size":       r.get("size", 15),
            "players":    {k: v["username"] for k, v in r.get("players", {}).items()},
            "spectators": len(r.get("spectators", [])),
            "moves":      r.get("moves", 0),
        }

    async def broadcast(self, rid: str, msg: dict, skip=None):
        room = self.rooms.get(rid)
        if not room:
            return
        targets = [v["ws"] for v in room["players"].values()] + \
                  [s["ws"] for s in room["spectators"]]
        for ws in targets:
            if ws is skip:
                continue
            try:
                await ws.send_json(msg)
            except Exception:
                pass

    async def remove(self, ws: WebSocket, rid: str):
        room = self.rooms.get(rid)
        if not room:
            return
        username, role = "", None
        players_snapshot = {k: dict(v) for k, v in room["players"].items()
                           if k != "ws"}
        for sym, info in list(room["players"].items()):
            if info["ws"] is ws:
                username, role = info["username"], sym
                break

        elo_result = {}
        if role and room["status"] == "playing":
            room["status"] = "ended"
            room["winner"] = "O" if role == "X" else "X"
            elo_result = _elo_update(room, room["winner"])

        for sym, info in list(room["players"].items()):
            if info["ws"] is ws:
                del room["players"][sym]
                break
        room["spectators"] = [s for s in room["spectators"] if s["ws"] is not ws]

        if role and room.get("winner"):
            left_msg = {
                "type":    "player_left",
                "username": username,
                "winner":   room["winner"],
            }
            if elo_result:
                left_msg["elo_x"] = elo_result.get("elo_x")
                left_msg["elo_o"] = elo_result.get("elo_o")
            await self.broadcast(rid, left_msg)
        if not room["players"] and not room["spectators"]:
            self.rooms.pop(rid, None)

rooms = Rooms()

def _check_winner_local(board: list, size: int, player: str, r: int, c: int) -> bool:
    """Check winner trên board cục bộ, không dùng global Board state."""
    for dr, dc in [(0,1),(1,0),(1,1),(1,-1)]:
        count = 1
        for i in range(1, 6):
            nr, nc = r + dr*i, c + dc*i
            if 0 <= nr < size and 0 <= nc < size and board[nr][nc] == player:
                count += 1
            else:
                break
        for i in range(1, 6):
            nr, nc = r - dr*i, c - dc*i
            if 0 <= nr < size and 0 <= nc < size and board[nr][nc] == player:
                count += 1
            else:
                break
        if count >= 5:
            return True
    return False

def _elo_update(room: dict, winner: str) -> dict:
    """Cập nhật ELO và trả về dict {elo_x, elo_o} nếu thành công."""
    result = {}
    try:
        xu = room["players"].get("X", {}).get("uid")
        ou = room["players"].get("O", {}).get("uid")
        if not xu or not ou:
            return result
        db = get_db()
        rx = db.execute("SELECT elo FROM users WHERE id=?", (xu,)).fetchone()
        ro = db.execute("SELECT elo FROM users WHERE id=?", (ou,)).fetchone()
        if not rx or not ro:
            db.close(); return result
        ex, eo = rx["elo"], ro["elo"]
        K = 32
        ex_x = 1 / (1 + 10 ** ((eo - ex) / 400))
        sx = 1 if winner == "X" else (0.5 if winner == "draw" else 0)
        so = 1 - sx
        nex = max(100, round(ex + K * (sx - ex_x)))
        neo = max(100, round(eo + K * (so - (1 - ex_x))))
        if winner == "X":
            db.execute("UPDATE users SET elo=?,wins=wins+1     WHERE id=?", (nex, xu))
            db.execute("UPDATE users SET elo=?,losses=losses+1 WHERE id=?", (neo, ou))
        elif winner == "O":
            db.execute("UPDATE users SET elo=?,losses=losses+1 WHERE id=?", (nex, xu))
            db.execute("UPDATE users SET elo=?,wins=wins+1     WHERE id=?", (neo, ou))
        else:
            db.execute("UPDATE users SET elo=?,draws=draws+1 WHERE id=?", (nex, xu))
            db.execute("UPDATE users SET elo=?,draws=draws+1 WHERE id=?", (neo, ou))
        xn = room["players"].get("X", {}).get("username", "")
        on = room["players"].get("O", {}).get("username", "")
        db.execute("INSERT INTO games VALUES (?,?,?,?,?,?,?)",
                   (str(uuid.uuid4()), xn, on, winner,
                    room.get("moves", 0), room.get("size", 15), int(time.time())))
        db.commit(); db.close()
        result = {"elo_x": nex, "elo_o": neo}
    except Exception as e:
        print("ELO error:", e)
    return result

class RoomIn(BaseModel):
    size: int = 15

@app.post("/rooms")
def create_room(body: RoomIn, user=Depends(get_user)):
    rid = rooms.create(max(10, min(20, body.size)), user["name"])
    return {"room_id": rid}

@app.get("/rooms")
def list_rooms():
    return [rooms.info(rid) for rid in list(rooms.rooms)
            if rooms.rooms[rid]["status"] in ("waiting", "playing")]

@app.get("/rooms/{rid}")
def get_room(rid: str):
    if rid not in rooms.rooms:
        raise HTTPException(404, "Phòng không tồn tại")
    return rooms.info(rid)


# ── Timer Task ───────────────────────────────────────────────────
async def _timer_task(rid: str):
    """Đếm ngược 60s mỗi lượt, tự xử lý hết giờ."""
    await asyncio.sleep(1)
    while True:
        room = rooms.rooms.get(rid)
        if not room or room["status"] != "playing":
            break
        if not room.get("turn_start"):
            await asyncio.sleep(1)
            continue

        elapsed = time.time() - room["turn_start"]
        turn    = room["turn"]
        rem_x   = round(max(0, room["timer_x"] - (elapsed if turn == "X" else 0)))
        rem_o   = round(max(0, room["timer_o"] - (elapsed if turn == "O" else 0)))

        if (turn == "X" and rem_x <= 0) or (turn == "O" and rem_o <= 0):
            room["status"] = "ended"
            room["winner"] = "O" if turn == "X" else "X"
            room["timer_x"] = rem_x
            room["timer_o"] = rem_o
            elo_result = _elo_update(room, room["winner"])
            timeout_msg = {
                "type":   "timeout",
                "loser":  turn,
                "winner": room["winner"],
                "timer_x": rem_x,
                "timer_o": rem_o,
            }
            if elo_result:
                timeout_msg["elo_x"] = elo_result.get("elo_x")
                timeout_msg["elo_o"] = elo_result.get("elo_o")
            await rooms.broadcast(rid, timeout_msg)
            break

        await rooms.broadcast(rid, {
            "type":    "tick",
            "turn":    turn,
            "timer_x": rem_x,
            "timer_o": rem_o,
        })
        await asyncio.sleep(1)

@app.websocket("/ws/{rid}")
async def ws_endpoint(ws: WebSocket, rid: str, token: str = ""):
    await ws.accept()

    username, uid = "Khách", None
    if token:
        p = check_token(token)
        if p:
            username, uid = p["name"], p["sub"]

    room = rooms.rooms.get(rid)
    if not room:
        await ws.send_json({"type": "error", "msg": "Phòng không tồn tại"})
        await ws.close()
        return

    if "X" not in room["players"]:
        role = "X"
        room["players"]["X"] = {"ws": ws, "username": username, "uid": uid}
    elif "O" not in room["players"]:
        role = "O"
        room["players"]["O"] = {"ws": ws, "username": username, "uid": uid}
        room["status"] = "playing"
        room["turn_start"] = time.time()
        await rooms.broadcast(rid, {
            "type":    "game_start",
            "players": {k: v["username"] for k, v in room["players"].items()},
            "board":   room["board"],
            "size":    room["size"],
            "turn":    "X",
            "timer_x": 60,
            "timer_o": 60,
        })
        # Bắt đầu task đếm ngược
        asyncio.ensure_future(_timer_task(rid))
    else:
        role = "spectator"
        room["spectators"].append({"ws": ws, "username": username})

    await ws.send_json({
        "type":     "joined",
        "role":     role,
        "username": username,
        "room":     rooms.info(rid),
        "board":    room["board"],
        "turn":     room["turn"],
        "status":   room["status"],
        "chat":     room["chat"][-30:],
    })

    await rooms.broadcast(rid, {"type": "room_update", "room": rooms.info(rid)}, skip=ws)

    try:
        while True:
            try:
                data = await asyncio.wait_for(ws.receive_json(), timeout=60.0)
            except asyncio.TimeoutError:
                try:
                    await ws.send_json({"type": "ping"})
                except Exception:
                    break  
                continue
            t = data.get("type")
            if t == "pong":
                continue  
            if t == "move":
                if role not in ("X", "O"):
                    await ws.send_json({"type": "error", "msg": "Khán giả không thể đi"}); continue
                if room["status"] != "playing":
                    await ws.send_json({"type": "error", "msg": "Trận chưa bắt đầu"}); continue
                if room["turn"] != role:
                    await ws.send_json({"type": "error", "msg": "Chưa đến lượt"}); continue
                r2, c2 = int(data["row"]), int(data["col"])
                if not (0 <= r2 < room["size"] and 0 <= c2 < room["size"]):
                    await ws.send_json({"type": "error", "msg": "Tọa độ không hợp lệ"}); continue
                if room["board"][r2][c2] != "":
                    await ws.send_json({"type": "error", "msg": "Ô đã có quân"}); continue

                room["board"][r2][c2] = role
                room["moves"] += 1

                # Check winner trực tiếp trên room board (không dùng global Board)
                won = _check_winner_local(room["board"], room["size"], role, r2, c2)

                next_turn = "O" if role == "X" else "X"
                room["turn"] = next_turn

                if won:
                    room["status"] = "ended"
                    room["winner"] = role
                    elo_result = _elo_update(room, role)
                else:
                    elo_result = {}

                # Cập nhật timer
                if room["turn_start"]:
                    elapsed = time.time() - room["turn_start"]
                    if role == "X":
                        room["timer_x"] = max(0, room["timer_x"] - elapsed)
                    else:
                        room["timer_o"] = max(0, room["timer_o"] - elapsed)
                room["turn_start"] = time.time()

                broadcast_msg = {
                    "type":    "move",
                    "player":  role,
                    "row":     r2, "col": c2,
                    "board":   room["board"],
                    "turn":    next_turn,
                    "winner":  room["winner"],
                    "status":  room["status"],
                    "moves":   room["moves"],
                    "timer_x": round(room["timer_x"]),
                    "timer_o": round(room["timer_o"]),
                }
                if elo_result:
                    broadcast_msg["elo_x"] = elo_result.get("elo_x")
                    broadcast_msg["elo_o"] = elo_result.get("elo_o")
                await rooms.broadcast(rid, broadcast_msg)

            elif t == "chat":
                text = str(data.get("text", ""))[:300].strip()
                if not text:
                    continue
                msg = {"type": "chat", "username": username, "role": role,
                       "text": text, "time": int(time.time())}
                room["chat"].append(msg)
                if len(room["chat"]) > 100:
                    room["chat"] = room["chat"][-100:]
                await rooms.broadcast(rid, msg)

            elif t == "rematch":
                room["rematch"].add(role)
                await rooms.broadcast(rid, {
                    "type": "rematch_vote", "username": username, "votes": len(room["rematch"])
                })
                if len(room["rematch"]) >= 2:
                    room["board"]      = [[""] * room["size"] for _ in range(room["size"])]
                    room["turn"]       = "X"
                    room["status"]     = "playing"
                    room["winner"]     = None
                    room["moves"]      = 0
                    room["rematch"]    = set()
                    room["timer_x"]    = 60
                    room["timer_o"]    = 60
                    room["turn_start"] = time.time()
                    await rooms.broadcast(rid, {
                        "type":    "game_start",
                        "players": {k: v["username"] for k, v in room["players"].items()},
                        "board":   room["board"],
                        "size":    room["size"],
                        "turn":    "X",
                        "timer_x": 60,
                        "timer_o": 60,
                    })
                    asyncio.ensure_future(_timer_task(rid))

    except WebSocketDisconnect:
        await rooms.remove(ws, rid)

@app.get("/health")
def health():
    return {"status": "ok", "rooms": len(rooms.rooms)}
