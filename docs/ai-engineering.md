# AI Engineering Specification

## Prompt Pipeline
禁止：`llm.invoke(user_input)`
必须：OCR结果 → 数据结构化 → Prompt模板 → AI分析 → AI日志 → 缓存

## AI Cache
AI结果必须缓存。
Redis Key 示例：`ai_summary:{hash}`
禁止重复请求相同 Prompt。

## AI Logs
所有 AI 请求必须记录：
- prompt
- response
- token
- latency
- retry
- model

## AI Fallback
必须支持：
DeepSeek失败 → fallback GPT
或者：
AI失败 → fallback Rule Engine
