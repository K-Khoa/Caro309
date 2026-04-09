SIZE = 20
board = []

def init_board(size: int):
    global SIZE, board
    SIZE = size
    board = [[""] * SIZE for _ in range(SIZE)]

def reset_board():
    global board
    board = [[""] * SIZE for _ in range(SIZE)]

def check_winner(player: str, r: int, c: int) -> bool:
    """True nếu player có đúng 5 quân liên tiếp qua (r,c).
    Luật chặn trong: 5 quân bị chặn CẢ 2 ĐẦU → KHÔNG thắng.
    Overline (6+) cũng không tính thắng.
    """
    for dr, dc in [(0,1),(1,0),(1,1),(1,-1)]:
        cnt_pos = 0
        for i in range(1, 30):
            nr, nc = r + dr*i, c + dc*i
            if 0 <= nr < SIZE and 0 <= nc < SIZE and board[nr][nc] == player:
                cnt_pos += 1
            else:
                break

        cnt_neg = 0
        for i in range(1, 30):
            nr, nc = r - dr*i, c - dc*i
            if 0 <= nr < SIZE and 0 <= nc < SIZE and board[nr][nc] == player:
                cnt_neg += 1
            else:
                break

        total = 1 + cnt_pos + cnt_neg
        if total != 5:
            continue

        blocked = 0
        er, ec = r + dr*(cnt_pos+1), c + dc*(cnt_pos+1)
        if not (0 <= er < SIZE and 0 <= ec < SIZE) or board[er][ec] != "":
            blocked += 1

        er, ec = r - dr*(cnt_neg+1), c - dc*(cnt_neg+1)
        if not (0 <= er < SIZE and 0 <= ec < SIZE) or board[er][ec] != "":
            blocked += 1

        if blocked < 2:
            return True

    return False
