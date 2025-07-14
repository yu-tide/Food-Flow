# FoodFlow 生产部署指南（非 Docker）

## 1. 服务器环境要求

| 组件 | 最低版本 | 建议 |
|---|---|---|
| OS | Windows 10+ / Ubuntu 20.04+ / macOS 12+ | Ubuntu 22.04 LTS |
| Python | 3.12+ | 3.12 |
| Node.js | 18+ | 20 LTS |
| PostgreSQL | 14+ | 16 |
| Redis | 6+ | 7 |
| Nginx | 1.24+ | 可选（反向代理） |

## 2. 依赖安装

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows
pip install -r ../requirements.txt

# Windows 需额外安装 PaddleOCR
# pip install paddlepaddle paddleocr opencv-python-headless
```

### 前端

```bash
cd frontend
npm install
npm run build   # 生产构建到 .next/
```

## 3. 数据库和 Redis

```bash
# PostgreSQL — 创建数据库
sudo -u postgres psql -c "CREATE DATABASE foodflow_db;"

# Redis — 启动服务
redis-server --daemonize yes   # Linux 后台启动
# Windows: redis-server
```

## 4. 环境变量配置

### backend/.env

```env
DEBUG=false
ENVIRONMENT=production
DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@127.0.0.1:5432/foodflow_db
SECRET_KEY=<生成随机密钥>
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=0
OCR_MODE=paddle
AI_MODE=bailian
BAILIAN_API_KEY=<你的百炼 key>
BAILIAN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
BAILIAN_MODEL=qwen-plus
VISION_MODE=mock
SMS_MODE=mock
UPLOAD_DIR=./uploads
```

### frontend/.env.local

```env
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

## 5. 数据库迁移

```bash
cd backend
source .venv/bin/activate
alembic upgrade head
```

## 6. 启动服务

### 后端 (FastAPI)

```bash
cd backend
source .venv/bin/activate

# 开发（单 worker, 热重载）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产（多 worker）
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
# 或
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### Celery Worker

```bash
cd backend
source .venv/bin/activate
celery -A app.worker worker --loglevel=info -P solo
# Windows 必须 -P solo
# Linux 可 -P prefork (默认)
```

### 前端

```bash
cd frontend

# 生产启动
npm run build
npm run start -- -p 3000
# 或
npx next start -p 3000
```

## 7. Nginx 反向代理（可选）

```nginx
server {
    listen 80;
    server_name foodflow.example.com;

    # 前端
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 上传文件
    location /uploads/ {
        proxy_pass http://127.0.0.1:8000;
    }

    client_max_body_size 20M;
}
```

## 8. systemd 服务（Linux）

### /etc/systemd/system/foodflow-backend.service

```ini
[Unit]
Description=FoodFlow Backend
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/foodflow/backend
Environment=PATH=/opt/foodflow/backend/.venv/bin:/usr/bin
ExecStart=/opt/foodflow/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### /etc/systemd/system/foodflow-worker.service

```ini
[Unit]
Description=FoodFlow Celery Worker
After=network.target redis.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/foodflow/backend
Environment=PATH=/opt/foodflow/backend/.venv/bin:/usr/bin
ExecStart=/opt/foodflow/backend/.venv/bin/celery -A app.worker worker --loglevel=info
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### /etc/systemd/system/foodflow-frontend.service

```ini
[Unit]
Description=FoodFlow Frontend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/foodflow/frontend
ExecStart=/usr/bin/node /opt/foodflow/frontend/node_modules/.bin/next start -p 3000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable foodflow-backend foodflow-worker foodflow-frontend
sudo systemctl start foodflow-backend foodflow-worker foodflow-frontend
```

## 9. 日志目录

```bash
# 应用日志建议存储位置
/var/log/foodflow/backend.log
/var/log/foodflow/worker.log
/var/log/foodflow/frontend.log

# systemd 日志查看
journalctl -u foodflow-backend -f
journalctl -u foodflow-worker -f
```

## 10. 上传文件目录

```bash
mkdir -p /opt/foodflow/backend/uploads
chmod 755 /opt/foodflow/backend/uploads
```

确保 `.gitignore` 包含 `uploads/`，不提交用户文件。

## 11. PaddleOCR 首次加载

PaddleOCR 首次运行会自动下载模型到 `~/.paddlex/official_models/`，耗时约 30-60 秒。首次上传图片时 Celery worker 日志会显示模型下载进度。后续调用使用缓存，加载速度 < 5 秒。

## 12. API Key 安全

- `.env` 已加入 `.gitignore`，**禁止提交到版本控制**。
- 生产环境 `.env` 中的 `BAILIAN_API_KEY` 仅服务端使用。
- 部署后验证：`grep -r "sk-" backend/app/` 应无输出。
- 定期轮换 API Key（百炼控制台 → API Key 管理）。

## 13. Smoke Test 验证

```bash
cd backend
source .venv/bin/activate
python scripts/smoke_test.py
# 预期: 8 steps all PASS

python scripts/vision_flow_smoke_test.py
# 预期: login → upload → poll → check → confirm → PASS
```

## 14. 常见故障排查

| 现象 | 检查 |
|---|---|
| 后端 500 | `journalctl -u foodflow-backend -n 50` |
| worker 不消费任务 | `redis-cli PING`; 确认 worker 启动 |
| 上传后任务停在 PENDING | Redis 是否运行; worker [tasks] 列表 |
| OCR 报错 | `python -c "from paddleocr import PaddleOCR"` |
| AI 总结为空 | `curl http://127.0.0.1:8000/api/health/redis` |
| 前端 404 | `npx next build` 是否有错误 |
| PostgreSQL 拒绝连接 | `pg_isready -h 127.0.0.1` |
| CORS 报错 | 检查 .env CORS 配置 + Nginx proxy_pass |
| 磁盘满 | `du -sh uploads/`; 定期清理过期上传文件 |

## 15. 启动顺序总结

```
1. PostgreSQL + Redis
2. alembic upgrade head
3. uvicorn / gunicorn (backend)
4. celery worker
5. next build + next start (frontend)
6. Nginx (可选)
```
