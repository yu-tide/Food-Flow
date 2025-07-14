# FoodFlow

AI Workflow 驱动的饮食记录与营养分析系统。

## 技术栈
- 后端：FastAPI + PostgreSQL + Redis + Celery + SQLAlchemy + Pydantic
- 前端：Next.js + TypeScript + TailwindCSS + shadcn/ui

## 开发原则
- MVP优先：能运行 > 完美架构
- 小步开发，小范围验证，单任务推进
- 禁止一次生成整个系统

## 代码规范
- 单文件不超过 300 行，超过即拆分
- 函数职责单一，拒绝 God Function
- 禁止复制粘贴，公共逻辑抽取复用
- 命名清晰自解释，禁止拼音/缩写拼凑
- 删除无用代码，禁止注释掉的大段废弃逻辑

## 详细规范
按模块按需读取 [docs/](docs/) 目录下的对应文档。
