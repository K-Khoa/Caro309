SIZE = 15
board = []

def init_board(size: int):
    global SIZE, board
    SIZE = size
    board = [[""] * SIZE for _ in range(SIZE)]

def reset_board():
    global board
    board = [[""] * SIZE for _ in range(SIZE)]

def check_winner(player: str, r: int, c: int) -> bool:
    """True nếu player có đúng 5 quân liên tiếp qua (r,c). Overline (6+) không tính."""
    for dr, dc in [(0,1),(1,0),(1,1),(1,-1)]:
        count = 1
        for i in range(1, 6):
            nr, nc = r + dr*i, c + dc*i
            if 0 <= nr < SIZE and 0 <= nc < SIZE and board[nr][nc] == player:
                count += 1
            else:
                break
        for i in range(1, 6):
            nr, nc = r - dr*i, c - dc*i
            if 0 <= nr < SIZE and 0 <= nc < SIZE and board[nr][nc] == player:
                count += 1
            else:
                break
        if count >= 5:
            return True
    return False
