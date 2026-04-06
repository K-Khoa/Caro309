# 🎮 caro309.com — Cờ Năm Mạch Online

Web app đầy đủ: vs AI · 2 người local · Online multiplayer · Bảng xếp hạng · Quan sát trận đấu

---

## Cấu trúc thư mục

```
caro309/
├── backend/
│   ├── main.py          ← FastAPI server chính
│   ├── AI.py            
│   ├── Board.py        
│   └── requirements.txt
└── frontend/
    └── index.html      
```

---

## Bước 1 — Chuẩn bị

Copy `AI.py` và `Board.py` từ project Python vào thư mục `backend/`.

---

## Bước 2 — Chạy Backend local

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Kiểm tra tại: http://localhost:8000/health

---

## Bước 3 — Mở Frontend

Mở `frontend/index.html` trong trình duyệt (hoặc dùng VS Code Live Server).

Mặc định frontend gọi `http://localhost:8000` — không cần đổi gì khi chạy local.

---

## Bước 4 — Deploy lên internet

### Backend → Render.com (miễn phí)

1. Tạo repo GitHub, push toàn bộ code lên
2. Vào https://render.com → New → Web Service
3. Chọn repo, cấu hình:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Thêm Environment Variable:
   - `SECRET_KEY` = một chuỗi bí mật bất kỳ (VD: `caro309-my-secret-2024`)
5. Deploy → copy URL dạng `https://caro309-backend.onrender.com`

### Frontend → Vercel (miễn phí)

1. Mở `frontend/index.html`
2. Tìm 2 dòng đầu trong `<script>` và thay:
   ```js
   const API = "https://caro309-backend.onrender.com";
   const WS  = "wss://caro309-backend.onrender.com";
   ```
3. Vào https://vercel.com → New Project → Import repo
4. Framework: **Other** (HTML thuần)
5. Root Directory: `frontend`
6. Deploy → trỏ domain `caro309.com` vào Vercel

### Trỏ domain caro309.com

Sau khi mua domain (Namecheap/GoDaddy/Inet.vn):
- Vào DNS settings → thêm CNAME record:
  - Name: `@` hoặc `www`
  - Value: `cname.vercel-dns.com`
- Trong Vercel → Settings → Domains → Add `caro309.com`

---

## Tính năng đã có

| Tính năng | Trạng thái |
|---|---|
| Chơi vs AI (3 cấp độ) | ✅ |
| Chơi 2 người local | ✅ |
| Tạo/vào phòng online | ✅ |
| WebSocket real-time | ✅ |
| Quan sát trận đấu | ✅ |
| Chat trong phòng | ✅ |
| Đăng ký / Đăng nhập | ✅ |
| Hệ thống ELO | ✅ |
| Bảng xếp hạng top 20 | ✅ |
| Dark mode UI | ✅ |
| Responsive mobile | ✅ |

---

## Nâng cấp tiếp theo (tuỳ chọn)

- Thêm PostgreSQL thay SQLite khi deploy production
- Thêm tính năng "Rematch" đồng ý 2 chiều
- Lịch sử các ván đấu
- Avatar người chơi
- Notification khi có người vào phòng
