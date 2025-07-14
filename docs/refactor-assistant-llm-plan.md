# Refactor Plan: assistant_llm.py

## 当前文件职责

`backend/app/services/assistant_llm.py` — 1152 行，承担了 LLM 对话的全部职责：

| 职责块 | 行数 | 说明 |
|---|---|---|
| 禁止字段定义 | 39 行 | `FORBIDDEN_LLM_INPUT_KEYS`、`FORBIDDEN_OUTPUT_TERMS` |
| System Prompt | 74 行 | `SYSTEM_PROMPT` 常量 |
| 上下文清洗器 | 126 行 | `sanitize_llm_context()` — 将 tool_context 转为中文安全数据 |
| 禁止字段剥离 | 11 行 | `_strip_forbidden_keys()` |
| 餐食计划 Facts 构建 | 44 行 | `_build_meal_plan_facts()` + `MEAL_PLAN_OPTIONS` |
| 用户记忆摘要 | 56 行 | `_build_memory_facts_summary()` |
| 食物决策 Facts 构建 | 62 行 | `build_food_decision_facts_for_llm()` |
| 用户消息构建 | 30 行 | `_build_user_content()` |
| 输出校验（通用） | 20 行 | `validate_no_internal_fields()` |
| 输出校验（食物决策） | 74 行 | `validate_food_decision_answer()` |
| 输出校验（统一） | 129 行 | `validate_assistant_answer()` |
| LLM 调用（Mock/Bailian） | 54 行 | `_run_mock()`、`_call_bailian()` |
| 输出清洗 | 53 行 | `clean_assistant_answer()` |
| 生成 + 校验主循环 | 49 行 | `_generate_and_validate()` |
| 非流式入口 | 66 行 | `generate_assistant_answer()` |
| 流式文本分割 | 28 行 | `split_text_for_stream()` |
| 流式调用（Bailian/Mock） | 88 行 | `_stream_bailian()`、`_stream_mock()`、`_tool_context_has_data()` |
| 流式入口 | 108 行 | `generate_assistant_answer_stream()` |

## 为什么过大

1. **超过项目规范 3.8 倍**：规范要求单文件 ≤300 行，当前 1152 行
2. **职责过多**：定义（Prompt + 禁止字段）+ 构建（Facts + 消息）+ 调用（LLM）+ 校验（多层）+ 清洗（后处理）+ 流式，6 种职责混在一个文件
3. **测试困难**：校验逻辑和构建逻辑无法独立测试
4. **修改风险高**：改 Prompt 可能影响校验，修改校验可能影响流式逻辑

## 建议拆成哪些文件

```
backend/app/services/
├── assistant_llm/
│   ├── __init__.py              # 公开接口 re-export
│   ├── constants.py             # Prompt + 禁止字段定义
│   ├── context_builder.py       # sanitize + facts 构建 + user content
│   ├── output_validator.py      # 所有校验函数
│   ├── output_cleaner.py        # clean_assistant_answer
│   ├── llm_client.py            # _run_mock + _call_bailian (非流式)
│   ├── llm_stream_client.py     # 流式调用 + split_text_for_stream
│   ├── generator.py             # generate_assistant_answer (非流式入口)
│   └── stream_generator.py      # generate_assistant_answer_stream (流式入口)
```

### 各文件职责

| 文件 | 行数估算 | 职责 |
|---|---|---|
| `constants.py` | ~140 | `SYSTEM_PROMPT`、`FORBIDDEN_LLM_INPUT_KEYS`、`FORBIDDEN_OUTPUT_TERMS`、`MEAL_PLAN_OPTIONS` |
| `context_builder.py` | ~280 | `sanitize_llm_context`、`_strip_forbidden_keys`、`_build_meal_plan_facts`、`_build_memory_facts_summary`、`build_food_decision_facts_for_llm`、`_build_user_content` |
| `output_validator.py` | ~240 | `validate_no_internal_fields`、`validate_food_decision_answer`、`validate_assistant_answer` |
| `output_cleaner.py` | ~60 | `clean_assistant_answer` |
| `llm_client.py` | ~70 | `_run_mock`、`_call_bailian` |
| `llm_stream_client.py` | ~110 | `split_text_for_stream`、`_stream_bailian`、`_stream_mock`、`_tool_context_has_data` |
| `generator.py` | ~120 | `_generate_and_validate`、`generate_assistant_answer` |
| `stream_generator.py` | ~120 | `generate_assistant_answer_stream` |
| `__init__.py` | ~20 | 公开接口 re-export |

总计：~1160 行（与原来基本一致），但每个文件 <300 行，职责单一。

## 拆分顺序

1. **Phase 1：抽常量** — 将 `SYSTEM_PROMPT`、`FORBIDDEN_*`、`MEAL_PLAN_OPTIONS` 移到 `constants.py`。无逻辑变更，最安全。
2. **Phase 2：抽校验器** — 将 3 个 `validate_*()` 函数移到 `output_validator.py`。依赖 `constants.py`。
3. **Phase 3：抽清洗器** — 将 `clean_assistant_answer()` 移到 `output_cleaner.py`。依赖 `constants.py`。
4. **Phase 4：抽上下文构建器** — 将 `sanitize_*`、`_build_*`、`build_food_decision_facts_for_llm`、`_build_user_content` 移到 `context_builder.py`。依赖 `constants.py`。
5. **Phase 5：抽 LLM 客户端** — 将非流式调用和流式调用分别移到 `llm_client.py` 和 `llm_stream_client.py`。
6. **Phase 6：抽生成器** — 将 `generate_assistant_answer` 和 `generate_assistant_answer_stream` 分别移到 `generator.py` 和 `stream_generator.py`。
7. **Phase 7：创建 `__init__.py`** — Re-export 所有公开接口，保持调用方 import 路径兼容。
8. **Phase 8：保持向后兼容** — 在旧的 `assistant_llm.py` 中添加 deprecation warning，`from app.services.assistant_llm import ...` 自动转发到新模块。

## 风险点

| 风险 | 等级 | 缓解措施 |
|---|---|---|
| 循环 import | 中 | `constants.py` 不 import 任何项目内模块；`context_builder.py` 依赖 `constants.py` 和 `assistant_memory`/`assistant_facts_builder`（已存在）；校验器依赖 `constants.py` 和 `assistant_reasoning_gate`（已存在） |
| import 路径变更导致调用方报错 | 中 | Phase 8 保留旧文件作为兼容转发层，现有调用方 (`assistant.py` router) 无需修改 |
| 函数签名不一致 | 低 | 只移动代码不改变签名，每个 Phase 后运行 smoke_test.py 验证 |
| mock/bailian client 共用逻辑分裂 | 低 | 非流式和流式分开后，bailian client 初始化逻辑会重复 2 次，抽取共享的 `_get_bailian_client()` 到 `llm_client.py` |

## 如何验证没有破坏功能

每个 Phase 完成后：

1. **类型检查**：确认 Python 无 import 错误
   ```bash
   cd backend
   python -c "from app.services.assistant_llm import generate_assistant_answer, generate_assistant_answer_stream"
   ```

2. **冒烟测试**：运行端到端测试验证完整链路
   ```bash
   python scripts/smoke_test.py
   ```

3. **前端构建**：确认前端 TypeScript 编译通过
   ```bash
   cd frontend && npm run build
   ```

4. **手动验证**：启动完整服务，在前端测试 AI 助手对话（非流式 + 流式），确认响应正常

## 建议

- **暂缓拆分**：当前功能已稳定，拆分纯属代码组织优化，不影响功能。如果近期有面试展示或上线计划，建议先完成 Plan 1 和 Plan 2 的文档工作，拆分放在后续。
- **如果决定拆**：建议一次完成所有 8 个 Phase（预计 1-2 小时），避免半拆分状态导致困惑。
- **替代方案**：如果不想新增 `assistant_llm/` 子包，可以将 constants 和 validator 先拆出为独立文件（`assistant_llm_constants.py`、`assistant_llm_validator.py`），其他留在原文件，将文件减到 ~800 行。但治标不治本，不如一步到位。
