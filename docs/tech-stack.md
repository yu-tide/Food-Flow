# Tech Stack Specification

## 后端技术栈（固定）
- FastAPI
- PostgreSQL
- Redis
- Celery
- SQLAlchemy
- Pydantic

禁止随意切换技术栈。

## 前端技术栈（固定）
- Next.js
- TypeScript
- TailwindCSS
- shadcn/ui

前端必须轻量。
禁止：复杂状态管理、Redux、过度动画、UI过度设计

## 数据库原则
PostgreSQL 为唯一主数据库。
Redis 仅用于：Cache、Queue、RateLimit、AI Cache

禁止：多数据库混用、MongoDB、Elasticsearch（MVP阶段）
