"""AgentOrchestrator — 多智能体协调器核心循环

流程：
  用户输入 → IntentClassifier → PlannerAgent(生成计划) → Agent Loop {
    取下一个待执行 Step
    → 选择对应 Agent → Agent.execute()
    → ReflectorAgent 反思该 Step 的输出
    → 如果发现问题 → replan
  } → 输出组装
"""

from __future__ import annotations
import logging
import time
import uuid

from app.services.agent.agents import (
    PlannerAgent, AnalyzerAgent, ValidatorAgent, ReflectorAgent,
)
from app.services.agent.agents.memory_agent import MemoryAgent
from app.services.agent.intent_classifier import HybridIntentClassifier
from app.services.agent.observability import Tracer, TraceCollector
from app.services.agent.models import (
    AgentKind, AgentStep, ExecutionPlan, IntentResult, StepStatus,
)

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """多智能体协调器"""

    def __init__(self, db, user_id: str, mode: str = "v2"):
        self.db = db
        self.user_id = user_id
        self.classifier = HybridIntentClassifier(mode="hybrid")
        self._init_agents()
        self.trace_id = ""

    def _init_agents(self):
        self.planner = PlannerAgent(db=self.db, user_id=self.user_id)
        self.analyzer = AnalyzerAgent(db=self.db, user_id=self.user_id)
        self.validator = ValidatorAgent(db=self.db, user_id=self.user_id)
        self.reflector = ReflectorAgent(db=self.db, user_id=self.user_id)
        self.memory = MemoryAgent(db=self.db, user_id=self.user_id)

    def _get_agent(self, kind: AgentKind):
        return {
            AgentKind.PLANNER: self.planner,
            AgentKind.ANALYZER: self.analyzer,
            AgentKind.VALIDATOR: self.validator,
            AgentKind.REFLECTOR: self.reflector,
            AgentKind.MEMORY: self.memory,
        }[kind]

    async def run(
        self,
        message: str,
        page: str = "",
        page_context: dict | None = None,
    ) -> dict:
        """主入口：执行完整的 Agent 循环"""
        self.trace_id = uuid.uuid4().hex[:12]
        Tracer.start_trace(trace_id=self.trace_id, session_id=ctx.get("session_id", ""), user_id=self.user_id)
        ctx = page_context or {}
        t_start = time.time()

        logger.warning("TRACE_AGENT_START trace=%s msg=%s page=%s",
                       self.trace_id, message[:60], page)

        # Step 1: 意图分类
        intent = await self.classifier.classify(message, page, ctx)
        logger.warning("TRACE_AGENT_INTENT trace=%s intent=%s conf=%s",
                       self.trace_id, intent.intent, intent.confidence)

        # 需要澄清 → 提前返回
        if intent.needs_clarification:
            logger.warning("TRACE_AGENT_CLARIFICATION trace=%s q=%s",
                           self.trace_id, intent.clarification_question)
            return self._build_response(
                answer=intent.clarification_question,
                intent=intent.intent,
                sources=[{"type": "assistant_info", "title": "需要更多信息"}],
            )

        # Step 2: Planner 生成执行计划
        async with Tracer.span("agent.planner", "agent", input={"intent": intent.intent}):
                plan = await self.planner.create_plan(intent, ctx)
        plan.context["user_message"] = message
        plan.context["page"] = page

        logger.warning("TRACE_AGENT_PLAN trace=%s intent=%s steps=%d",
                       self.trace_id, plan.intent, len(plan.steps))

        # Step 3: Agent Loop
        while not plan.is_done:
            step = plan.next_pending_step
            if step is None:
                break

            step.status = StepStatus.RUNNING
            agent = self._get_agent(step.agent)

            # 注入共享上下文
            step.input = {
                **plan.context,
                **({} if not step.input else step.input),
            }

            # 执行
            async with Tracer.span("agent." + step.agent.value, "agent", input={"description": step.description}):
                            completed_step = await agent.execute(step)

            if completed_step.status == StepStatus.FAILED:
                logger.warning("TRACE_AGENT_STEP_FAILED trace=%s step=%s error=%s",
                               self.trace_id, step.id, completed_step.error_message)
                # 写回失败信息
                for i, s in enumerate(plan.steps):
                    if s.id == step.id:
                        plan.steps[i] = completed_step
                        break

                # 将上一步输出注入到 plan context
                if completed_step.output:
                    plan.context["previous_step_output"] = completed_step.output

                # replan
                plan = await self.planner.replan(plan, str(completed_step.error_message))
                continue

            # 写回完成后的 step
            for i, s in enumerate(plan.steps):
                if s.id == step.id:
                    plan.steps[i] = completed_step
                    break

            # 将上一步输出注入到 plan context
            if completed_step.output:
                plan.context["previous_step_output"] = completed_step.output

            # Step 4: 反思（非最后一个 step 才反思）
            is_last = step.id == (plan.steps[-1].id if plan.steps else "")
            if not is_last and completed_step.output:
                reflect_step = AgentStep(
                    id=f"reflect-{step.id}",
                    agent=AgentKind.REFLECTOR,
                    description=f"反思 {step.agent.value} 的输出",
                    input={
                        "previous_step_output": completed_step.output,
                        "history_records": plan.context.get("history_records", []),
                    },
                )
                reflect_result = await self.reflector.execute(reflect_step)
                reflection = (reflect_result.output or {}).get("reflection", {})
                action = reflection.get("action", "accept")

                # 收集质量评分和修正记录
                rsl = reflect_result.output or {}
                qs = rsl.get("quality_score")
                if qs:
                    plan.context.setdefault("quality_scores", []).append(qs)
                corr = rsl.get("corrections", [])
                if corr:
                    plan.context.setdefault("corrections", []).extend(corr)

                if action == "retry":
                    logger.warning("TRACE_AGENT_REFLECT_RETRY trace=%s step=%s",
                                   self.trace_id, step.id)
                    plan = await self.planner.replan(plan, "反思触发重试")
                    continue

                elif action == "ask_user":
                    # 标记问题但不阻塞
                    if isinstance(reflection, dict):
                        issues = reflection.get("issues", [])
                        plan.context["warnings"] = plan.context.get("warnings", []) + issues

        # Step 5: 输出组装
        duration = (time.time() - t_start) * 1000
        logger.warning("TRACE_AGENT_DONE trace=%s duration=%.0fms steps=%d",
                       self.trace_id, duration, sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED))

        trace = Tracer.current_trace()
        if trace:
            trace.intent = intent.intent
            trace.close()
            TraceCollector.store(trace)
            Tracer.clear()
        return self._assemble_response(plan, duration)

    def _assemble_response(self, plan: ExecutionPlan, duration_ms: float) -> dict:
        """将 ExecutionPlan 组装为回复"""
        answer = plan.context.get("answer", "")
        sources = plan.context.get("sources", [])

        # 从每个 step 的 output 中收集 source 信息
        for step in plan.steps:
            if step.output and step.status == StepStatus.COMPLETED:
                if "dashboard_summary" in step.output:
                    sources.append({"type": "dashboard_summary", "title": "今日摄入"})
                if "weekly_summary" in step.output:
                    sources.append({"type": "weekly_statistics", "title": "本周统计"})
                if "record_detail" in step.output:
                    sources.append({"type": "food_record", "title": "记录详情"})
                if "food_estimate" in step.output:
                    sources.append({"type": "food_estimate", "title": "食物估算"})

        # 去重
        seen = set()
        unique_sources = []
        for s in sources:
            key = f"{s.get('type')}-{s.get('title')}"
            if key not in seen:
                seen.add(key)
                unique_sources.append(s)

        warnings = plan.context.get("warnings", [])
        if warnings:
            answer += "\n\n⚠️ " + "; ".join(
                w["detail"] if isinstance(w, dict) else str(w)
                for w in warnings[:3]
            )

        return {
            "answer": answer,
            "intent": plan.intent,
            "sources": unique_sources,
            "plan_summary": {
                "steps": len(plan.steps),
                "completed": sum(1 for s in plan.steps if s.status == StepStatus.COMPLETED),
                "duration_ms": round(duration_ms, 1),
                "trace_id": self.trace_id,
            },
        }

    def _build_response(
        self,
        answer: str,
        intent: str = "",
        sources: list | None = None,
    ) -> dict:
        return {
            "answer": answer,
            "intent": intent,
            "sources": sources or [],
            "plan_summary": {
                "steps": 0,
                "completed": 0,
                "duration_ms": 0,
                "trace_id": self.trace_id,
            },
        }

