# Architecture & Core Principles

## 1. 项目定位

FoodFlow 是一个：AI Workflow 驱动的饮食记录与营养分析系统。

### 项目核心
- OCR Workflow
- AI Pipeline
- 异步任务系统
- 数据结构化分析
- AI Engineering Workflow

### 不是
- AI 聊天套壳
- 通用 CRUD 系统
- 复杂平台型产品

### 项目目标
- 后端 / 全栈实习简历项目
- AI Engineering 能力展示
- 真实可运行 MVP
- Vibe Coding 协作开发

---

## 2. 核心开发原则

### 原则1：MVP优先
永远优先：能运行 > 完美架构
优先跑通核心工作流：上传图片 → OCR → 数据结构化 → AI总结 → 数据展示

### 原则2：AI只是增强
FoodFlow 的核心：不是聊天机器人。
AI只负责：饮食总结、分类增强、周报总结、轻量建议
核心业务：OCR、数据结构化、规则引擎、数据分析、异步任务

### 原则3：Workflow 优先
系统核心是：Input → OCR → Parse → Rule Engine → AI Pipeline → Statistics
不是：Input → LLM → Output

### 原则4：单任务开发
每次只开发：一个完整链路。
✅ 正确：图片上传 → 文件保存 → 返回 task_id
❌ 错误：同时开发 OCR、AI、Redis、Celery、前端页面
