# FoodFlow

AI Workflow 驱动的饮食记录与营养分析系统。上传食物图片，AI 自动识别食物、估算营养成分并生成饮食建议。

## 项目简介

FoodFlow 是一个以 AI Workflow 为核心的个人饮食记录工具。区别于简单的聊天机器人，它通过「图片上传 → OCR 文字识别 → AI 视觉识别 → 营养估算 → AI 总结」的固定流水线，将非结构化的食物图片转化为结构化的营养数据，帮助用户追踪每日饮食摄入。

项目采用 **Mock-First** 开发模式：所有 AI 和外部服务均支持 Mock 模式，可在不依赖任何外部 API 的情况下完成完整的本地开发和测试。

## 核心功能

- **手机号注册/登录** — JWT 认证，支持 Mock 短信验证码
- **食物图片上传与分析** — 7 阶段异步分析流水线（OCR → AI 识别 → 标准化 → 营养检索 → 估算 → AI 总结）
- **两种分析模式** — `dish_with_components`（混合菜品拆解，如麻辣烫）和 `component_sum`（独立食物汇总，如减脂餐盒）
- **草稿/确认机制** — AI 分析结果先进入草稿状态，用户审核确认后才计入统计，确保数据准确
- **仪表盘** — 当日热量环形图、三大宏量营养素进度条、近期餐食列表、周热量趋势图
- **每周统计** — 日均热量、宏量营养素达标天数、餐食频率
- **食物记录管理** — 记录列表（今日/昨天/本周筛选）、记录详情、手动调整食物名称和分量
- **AI 饮食助手** — 浮窗式对话助手，支持「能不能吃」食物决策、餐食推荐、营养知识问答、记录查询等
- **RAG 知识库** — 内置营养知识文档，支持关键词检索
- **用户设置** — 身体信息、营养目标（支持 BMR/TDEE 计算器）、饮食偏好、AI 分析偏好、通知与隐私设置
- **任务重试** — AI 分析失败可一键重试

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Next.js 15 + React 19 + TypeScript + TailwindCSS + Recharts |
| 后端 | FastAPI + SQLAlchemy(async) + Pydantic v2 |
| 数据库 | PostgreSQL 16 |
| 缓存/队列 | Redis 7 + Celery 5.x |
| OCR | PaddleOCR 3.x（可选，默认 Mock） |
| AI | 阿里云百炼（通义千问 qwen-plus / qwen-vl-max） |
| 验证 | python-jose JWT + passlib bcrypt |

## 系统架构

```
用户 → Next.js 前端 → FastAPI 后端 → Celery Worker（异步分析）
                       ↓                ↓
                   PostgreSQL         Redis
                                       ↓
                              OCR / AI Vision / AI Chat
                                       ↓
                              RAG 知识库（PostgreSQL）
```

**分析流水线（7 阶段）：**

```
UPLOADED → OCR_PROCESSING → AI_RECOGNITION（视觉识别）
  → NORMALIZING → RETRIEVING → ESTIMATING → AI_SUMMARIZING
```

**AI 助手架构（多阶段 Agent Loop）：**

```
用户消息 → 意图分类（Reasoning Gate）→ 工具调用（数据快照/RAG搜索）
  → Planner 规划 → LLM 推理 → 响应（支持 SSE 流式输出）
  → 可选操作建议 → 操作审计 → 后置观察
```

## 项目结构

```
FoodFlow/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST API 路由
│   │   │   ├── auth.py      # 注册/登录/短信验证码
│   │   │   ├── foods.py     # 图片上传/记录管理/确认
│   │   │   ├── dashboard.py # 仪表盘聚合
│   │   │   ├── statistics.py# 每周统计
│   │   │   ├── assistant.py # AI 助手（chat/stream/actions）
│   │   │   ├── assistant_rag.py # RAG 知识库搜索
│   │   │   ├── tasks.py     # 任务状态/重试
│   │   │   ├── settings.py  # 用户设置
│   │   │   └── health.py    # 健康检查
│   │   ├── core/            # 配置、安全、依赖注入、Redis
│   │   ├── db/              # SQLAlchemy session、base
│   │   ├── models/          # ORM 模型（11 个）
│   │   ├── schemas/         # Pydantic 请求/响应模型
│   │   ├── services/        # 业务逻辑（31 个服务模块）
│   │   └── tasks/           # Celery 异步任务
│   ├── alembic/             # 数据库迁移
│   ├── scripts/             # 冒烟测试、知识库种子、调试脚本
│   │   └── fixtures/        # 测试图片
│   └── uploads/             # 上传图片存储
├── frontend/
│   └── src/
│       ├── app/             # Next.js App Router 页面（12 个页面）
│       ├── components/      # UI 组件（助手、用户）
│       ├── services/        # API 客户端（auth/foods/assistant/settings）
│       ├── hooks/           # 自定义 Hooks
│       ├── stores/          # 状态管理
│       ├── lib/             # 工具函数
│       └── types/           # TypeScript 类型定义
├── docs/                    # 架构、开发流程、部署文档
├── requirements.txt         # Python 依赖
├── .gitignore
├── .gitattributes
└── LICENSE
```

## 快速开始

### 前置条件

- Python 3.12+
- Node.js 18+
- PostgreSQL 16（本机运行，端口 5432）
- Redis 7（本机运行，端口 6379）

### 数据库准备

```sql
CREATE DATABASE foodflow_db;
```

### 环境配置

```bash
cp backend/.env.example backend/.env
# 按需编辑 backend/.env，Mock 模式下无需修改即可运行
```

### 启动服务

```bash
# 1. 安装 Python 依赖
cd backend
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
.venv\Scripts\activate      # Windows
pip install -r ../requirements.txt

# 2. 数据库迁移
alembic upgrade head

# 3. （可选）初始化知识库
python scripts/seed_knowledge_base.py

# 4. 安装前端依赖
cd ../frontend
npm install

# 5. 启动 Redis（如未运行）
redis-server

# 6. 启动 FastAPI（终端 1）
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 7. 启动 Celery Worker（终端 2）
cd backend
celery -A app.worker worker --loglevel=info -P solo

# 8. 启动前端（终端 3）
cd frontend
npm run dev
```

启动后访问：
- 前端：http://localhost:3000
- 后端 API 文档（Swagger）：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health

### 冒烟测试

```bash
cd backend
python scripts/smoke_test.py
```

自动完成：注册/登录 → 上传测试图片 → 轮询任务状态 → 校验分析结果 → 查询记录列表 → 查询仪表盘 → 查询每周统计。

## 环境变量说明

复制 `backend/.env.example` 为 `backend/.env`，关键配置：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://postgres:123456@127.0.0.1:5432/foodflow_db` |
| `SECRET_KEY` | JWT 签名密钥 | `change-me-to-a-random-secret-key`（生产环境务必更换） |
| `REDIS_HOST` | Redis 地址 | `localhost` |
| `REDIS_PORT` | Redis 端口 | `6379` |
| `OCR_MODE` | OCR 模式 | `mock`（可选 `paddle`） |
| `AI_MODE` | AI 文本模式 | `mock`（可选 `bailian`） |
| `VISION_MODE` | AI 视觉模式 | `mock`（可选 `bailian`） |
| `BAILIAN_API_KEY` | 百炼 API Key | 空（使用 bailian 模式时必填） |
| `BAILIAN_MODEL` | 文本模型 | `qwen-plus` |
| `BAILIAN_VISION_MODEL` | 视觉模型 | `qwen-vl-max` |
| `ALLOWED_ORIGINS` | CORS 允许来源 | `http://localhost:3000` |

## Mock 模式说明

项目默认使用 Mock 模式，无需任何外部 API Key 即可完整运行：

- **OCR Mock** — 返回预设的中文食物描述文本
- **AI Mock** — 返回预设的营养总结和建议
- **Vision Mock** — 返回预设的食物识别结果
- **SMS Mock** — 验证码打印到终端日志，使用 `123456` 即可通过

切换到真实服务：在 `backend/.env` 中将对应 `*_MODE` 设为 `bailian`/`paddle` 并填入 API Key。

## 核心实现思路

### AI Workflow 而非 Chatbot

区别于「用户自由对话」的 AI 助手，FoodFlow 的核心是固定的分析流水线。每张食物图片经过 OCR 文字提取、AI 视觉识别、结果融合、营养数据库匹配、AI 生成总结等固定阶段，确保输出结构化、可追溯、可验证。

### 两阶段 AI 分析

1. **视觉识别**（qwen-vl-max）：分析图片中的食物构成，输出菜品名称、类型、食材成分
2. **文本理解**（qwen-plus）：综合 OCR 文本和视觉结果，生成营养总结和个性化建议

### 融合策略

OCR 文字识别和 AI 视觉识别各有优势（OCR 适合营养标签，视觉适合无文字食物），系统通过 `fusion_service` 融合两者结果，标注每项数据的来源和置信度。

### Assumption 标注

对于 AI 无法精确判断的数据（如某道菜中鸡肉的具体克数），系统统一标注 `estimated: true`，与营养数据库中确认数据区分，帮助用户识别可信度。

### 可信 AI 操作

AI 助手采用 Reasoning Gate（意图分类）+ Tool Registry（工具注册表）+ Action Audit（操作审计）+ Observer（后置观察）的多层架构，确保所有 AI 触发的操作可追溯、可回滚。

## 项目亮点

- **完整的 7 阶段分析流水线** — 从图片上传到营养总结，每阶段状态可追踪
- **Mock-First 开发** — 零外部依赖即可完整运行和测试
- **草稿/确认双状态** — AI 分析结果需用户审核，兼顾效率和准确性
- **食物决策引擎** — 基于剩余热量预算、脂肪风险评估、相似食物频率的个性化判断
- **多层级可观测性** — AI 调用日志、操作审计日志、前后状态快照
- **BMR/TDEE 计算器** — 基于 Mifflin-St Jeor 公式的个性化营养目标推荐
- **SSE 流式对话** — AI 助手支持实时流式输出
- **前端 0 TypeScript 错误** — 生产构建通过

## 待改进方向

- [ ] Food Parser 接入真实营养数据库（nutrition engine），替代硬编码查找表
- [ ] RAG 升级为向量检索（pgvector），替代关键词匹配
- [ ] 移动端适配优化
- [ ] 单元测试覆盖
- [ ] CI/CD 流水线
- [ ] 历史记录搜索与分页
- [ ] 多语言支持

## 许可证

MIT License — 详见 [LICENSE](LICENSE)

---

GitHub: [https://github.com/yu-tide/](https://github.com/yu-tide/FoodFlow)
