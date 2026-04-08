import math
import random
import Board

BEAM_WIDTH = 15
DEPTH      = 3

DIRECTIONS = [(1,0),(0,1),(1,1),(1,-1)]

PATTERNS = {
    (5,0): 10_000_000, (5,1): 10_000_000, (5,2): 10_000_000,
    (4,2): 500_000,    (4,1): 50_000,
    (3,2): 10_000,     (3,1): 1_000,
    (2,2): 500,        (2,1): 100,
}

# ── Helpers ──────────────────────────────────────────────────────

def _line_score(r: int, c: int, dr: int, dc: int, player: str) -> int:
    count, open_ends = 1, 0
    for sign in (1, -1):
        i = 1
        while True:
            nr, nc = r + sign*dr*i, c + sign*dc*i
            if not (0 <= nr < Board.SIZE and 0 <= nc < Board.SIZE):
                break
            if Board.board[nr][nc] == player:
                count += 1; i += 1
            elif Board.board[nr][nc] == "":
                open_ends += 1; break
            else:
                break
    if count >= 5:
        return 10_000_000
    return PATTERNS.get((count, open_ends), 0)


def _score_cell(r: int, c: int, player: str) -> int:
    return sum(_line_score(r, c, dr, dc, player) for dr, dc in DIRECTIONS)


def candidate_moves() -> list[tuple[int,int]]:
    """Trả về tối đa BEAM_WIDTH ô trống gần quân hiện có, xếp theo điểm."""
    seen: set[tuple[int,int]] = set()
    for i in range(Board.SIZE):
        for j in range(Board.SIZE):
            if Board.board[i][j] != "":
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        ni, nj = i+dx, j+dy
                        if (0 <= ni < Board.SIZE and 0 <= nj < Board.SIZE
                                and Board.board[ni][nj] == ""):
                            seen.add((ni, nj))

    if not seen:
        return [(Board.SIZE // 2, Board.SIZE // 2)]

    ranked = sorted(seen, key=lambda m: _score_cell(m[0], m[1], "O") + _score_cell(m[0], m[1], "X"), reverse=True)
    return ranked[:BEAM_WIDTH]


def _all_neighbor_moves() -> list[tuple[int,int]]:
    """Trả về TẤT CẢ ô trống gần quân hiện có (không giới hạn BEAM_WIDTH)."""
    seen: set[tuple[int,int]] = set()
    for i in range(Board.SIZE):
        for j in range(Board.SIZE):
            if Board.board[i][j] != "":
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        ni, nj = i+dx, j+dy
                        if (0 <= ni < Board.SIZE and 0 <= nj < Board.SIZE
                                and Board.board[ni][nj] == ""):
                            seen.add((ni, nj))
    if not seen:
        return [(Board.SIZE // 2, Board.SIZE // 2)]
    return list(seen)


def _immediate_win(player: str) -> tuple[int,int] | None:
    for r, c in _all_neighbor_moves():
        Board.board[r][c] = player
        won = Board.check_winner(player, r, c)
        Board.board[r][c] = ""
        if won:
            return (r, c)
    return None


def _minimax(depth: int, maximizing: bool, alpha: float, beta: float) -> tuple[float, tuple[int,int] | None]:
    if depth == 0:
        score = sum(
            (_score_cell(i, j, "O") if Board.board[i][j] == "O" else -_score_cell(i, j, "X"))
            for i in range(Board.SIZE) for j in range(Board.SIZE) if Board.board[i][j] != ""
        )
        return score, None

    moves = candidate_moves()
    if not moves:
        return 0, None

    best_move = None
    if maximizing:
        best = -math.inf
        for r, c in moves:
            Board.board[r][c] = "O"
            if Board.check_winner("O", r, c):
                Board.board[r][c] = ""
                return 10_000_000, (r, c)
            val, _ = _minimax(depth-1, False, alpha, beta)
            Board.board[r][c] = ""
            if val > best:
                best, best_move = val, (r, c)
            alpha = max(alpha, val)
            if beta <= alpha:
                break
        return best, best_move
    else:
        best = math.inf
        for r, c in moves:
            Board.board[r][c] = "X"
            if Board.check_winner("X", r, c):
                Board.board[r][c] = ""
                return -10_000_000, (r, c)
            val, _ = _minimax(depth-1, True, alpha, beta)
            Board.board[r][c] = ""
            if val < best:
                best, best_move = val, (r, c)
            beta = min(beta, val)
            if beta <= alpha:
                break
        return best, best_move


# ── Public API ───────────────────────────────────────────────────

def ai_move(level: str) -> tuple[int,int]:
    """Trả về (row, col) tốt nhất cho máy (O) theo level.
    Easy:   3 bước nhìn trước
    Medium: 4 bước nhìn trước
    Hard:   5 bước nhìn trước
    """
    # Thắng ngay nếu có thể
    win = _immediate_win("O")
    if win:
        return win

    # Chặn người chơi thắng
    block = _immediate_win("X")
    if block:
        return block

    cands = candidate_moves()

    if level == "Easy":
        _, move = _minimax(3, True, -math.inf, math.inf)
        return move or cands[0]
    elif level == "Medium":
        _, move = _minimax(4, True, -math.inf, math.inf)
        return move or cands[0]
    else:  # Hard
        _, move = _minimax(5, True, -math.inf, math.inf)
        return move or cands[0]
