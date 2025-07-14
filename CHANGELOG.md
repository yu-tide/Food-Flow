# Changelog

All notable changes to this project will be documented in this file.

## [v0.1.0] - 2026-05-18

### Initial Public Release

First public release of FoodFlow, an AI Workflow-driven food recording and nutrition analysis system.

#### Core Features

- **Food Image Analysis Pipeline** — 7-stage async pipeline: upload → OCR → AI vision recognition → normalization → nutrition retrieval → estimation → AI summary. Powered by Celery + Redis.
- **Agentic AI Assistant** — Multi-phase agent loop with intent classification (Reasoning Gate), structured planning, tool registry, RAG knowledge base, SSE streaming, and post-action audit logging. Supports food decision analysis, meal planning, nutrition Q&A, and record queries.
- **Nutrition Dashboard** — Daily calorie ring chart, macronutrient progress bars, recent meals list, and weekly calorie trend chart (Recharts).
- **User Settings** — Body metrics, personalized nutrition targets (Mifflin-St Jeor BMR/TDEE calculator), diet preferences, AI analysis preferences, notification and privacy settings.
- **Draft/Confirm Workflow** — AI analysis results enter draft state first; user review and confirmation required before inclusion in statistics.
- **Mock AI Mode** — OCR, AI text, Vision, and SMS all support mock mode for zero-dependency local development and testing.
- **Dual Analysis Modes** — `dish_with_components` (decomposing mixed dishes like hotpot) and `component_sum` (aggregating separate food items).
- **Weekly Statistics** — Aggregated weekly nutrition data with daily breakdown, protein target days, and macro compliance analysis.

#### Technical Foundation

- **Backend**: FastAPI + SQLAlchemy(async) + Pydantic v2
- **Frontend**: Next.js 15 + React 19 + TypeScript + TailwindCSS + Recharts
- **Database**: PostgreSQL 16 with Alembic migrations
- **Async Tasks**: Celery 5.x + Redis 7
- **AI**: Alibaba Cloud Bailian (qwen-plus for text, qwen-vl-max for vision)
- **Auth**: JWT (python-jose) + bcrypt password hashing
- **RAG**: PostgreSQL-backed keyword search knowledge base
- **Observability**: AI call logs, assistant action audit logs with before/after snapshots

#### Project Structure

- 11 database models (User, FoodRecord, FoodItem, AnalyzeTask, TaskEvent, UserSettings, WeeklyStatistics, AILog, AssistantActionLog, AssistantMemory, KnowledgeDocument/Chunk)
- 31 backend service modules
- 12 frontend pages
- 20+ API endpoints
- End-to-end smoke test suite
- 7 architecture/development docs
