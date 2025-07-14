# Contributing to FoodFlow

感谢你对 FoodFlow 的关注！以下是参与项目开发的指南。

## 环境准备

- Python 3.12+
- Node.js 18+
- PostgreSQL 16（本机运行，端口 5432）
- Redis 7（本机运行，端口 6379）

```bash
# 克隆仓库
git clone https://github.com/yourusername/FoodFlow.git
cd FoodFlow

# 创建数据库
createdb foodflow_db
```

## 本地启动

```bash
# 后端
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r ../requirements.txt
cp .env.example .env    # 使用 Mock 模式即可运行
alembic upgrade head

# 前端
cd ../frontend
npm install
```

启动服务（需要 3 个终端）：

```bash
# 终端 1：Redis
redis-server

# 终端 2：FastAPI
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 终端 3：Celery Worker
cd backend
celery -A app.worker worker --loglevel=info -P solo

# 终端 4：前端
cd frontend
npm run dev
```

## 运行测试

```bash
cd backend
python scripts/smoke_test.py
```

## 构建检查

```bash
cd frontend
npm run build    # 必须 0 TypeScript 错误
```

## 分支命名建议

- `feat/<功能名>` — 新功能（如 `feat/nutrition-engine`）
- `fix/<问题描述>` — Bug 修复（如 `fix/ocr-encoding`）
- `refactor/<模块名>` — 重构（如 `refactor/assistant-llm`）
- `docs/<描述>` — 文档更新

## 提交信息建议

遵循项目规范：

```
feat: add nutrition database integration
fix: correct weekly statistics date range
refactor: extract assistant output validator
docs: update deployment guide
```

## 代码规范

- 单文件不超过 300 行，超过即拆分
- 函数职责单一，拒绝 God Function
- 禁止复制粘贴，公共逻辑抽取复用
- 命名清晰自解释，禁止拼音/缩写拼凑
- 删除无用代码，禁止注释掉的大段废弃逻辑

详见 `CLAUDE.md` 和 `docs/` 目录。

## 不要提交的内容

- `.env` 或包含真实 Key 的环境变量文件
- `backend/uploads/` 中的运行时上传图片（`.gitkeep` 除外）
- `dump.rdb`（Redis 运行时数据）
- `__pycache__/`、`.pyc` 文件
- `node_modules/`、`.next/`、`.cache/`
- `.pytest_cache/`、`.coverage`、`htmlcov/`
- IDE 配置文件（`.vscode/`、`.idea/`）

## 开发原则

- MVP 优先：能运行 > 完美架构
- 小步开发，小范围验证，单任务推进
- Mock-First：所有 AI 和外部服务均支持 Mock 模式

## License

MIT License — 详见 [LICENSE](LICENSE)
