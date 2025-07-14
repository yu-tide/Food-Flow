import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.analyze_task import AnalyzeTask
from app.models.food_item import FoodItem
from app.models.food_record import FoodRecord
from app.models.task_event import TaskEvent
from app.services.ai_food_recognizer import recognize_food
from app.services.food_item_normalizer import normalize_food_items
from app.services.food_component_fallback import generate_fallback_components
from app.services.ai_service import generate_summary
from app.services.food_normalizer import normalize_food_name
from app.services.nutrition_estimator import estimate_nutrition, NutritionEstimate
from app.services.nutrition_retriever import retrieve_nutrition_references
from app.services.ocr_service import _image_url_to_path, recognize_image_text

logger = logging.getLogger(__name__)

STAGES = [
    ("UPLOADED", 10, 9, "图片上传完成"),
    ("OCR_PROCESSING", 25, 8, "正在识别图片内容"),
    ("AI_RECOGNITION", 45, 6, "图像识别中"),
    ("NORMALIZING", 58, 5, "正在标准化食物名称"),
    ("RETRIEVING", 68, 4, "营养参考检索中"),
    ("ESTIMATING", 78, 3, "营养估算中"),
    ("AI_SUMMARIZING", 90, 2, "正在生成饮食建议"),
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M")


async def _get_task(db: AsyncSession, task_id: str) -> AnalyzeTask:
    result = await db.execute(select(AnalyzeTask).where(AnalyzeTask.id == task_id))
    return result.scalar_one()


async def _update_task_status(
    db: AsyncSession, task_id: str, status: str, progress_percent: int, eta_seconds: int
) -> None:
    task = await _get_task(db, task_id)
    task.status = status
    task.progress_percent = progress_percent
    task.eta_seconds = eta_seconds
    await db.commit()


async def _add_task_event(db: AsyncSession, task_id: str, title: str) -> None:
    event = TaskEvent(task_id=task_id, time=_now(), title=title)
    db.add(event)
    await db.commit()


async def _create_food_record(
    db: AsyncSession, task_id: str, user_id: str, meal_type: str, remark: str, image_url: str,
    ocr_text: str | None = None,
    ocr_engine: str = "mock",
    ai_summary: str | None = None,
    ai_latency: str = "",
    ai_engine: str = "",
    analysis_mode: str = "dish_with_components",
    status_label: str = "分析完成",
) -> FoodRecord:
    summary = ai_summary or ""
    prompt_ver = f"{ocr_engine}-ocr-v1"
    if ai_engine:
        prompt_ver += f"+{ai_engine}"
    record = FoodRecord(
        user_id=user_id,
        task_id=task_id,
        meal_type=meal_type,
        image_url=image_url,
        remark=remark,
        ocr_text=ocr_text,
        total_calories=0,
        protein=0,
        carbohydrate=0,
        fat=0,
        target_calories=2000,
        status="draft",
        status_label=status_label,
        summary=summary,
        prompt_version=prompt_ver[:50],
        ai_latency=ai_latency,
        cache_hit=False,
        analysis_mode=analysis_mode,
    )
    db.add(record)
    await db.flush()
    return record


async def _complete_task(db: AsyncSession, task_id: str, record_id: str) -> None:
    logger.info("_complete_task: task_id=%s record_id=%s", task_id, record_id)
    task = await _get_task(db, task_id)
    task.status = "SUCCESS"
    task.progress_percent = 100
    task.eta_seconds = 0
    task.record_id = record_id
    await _add_task_event(db, task_id, "分析完成")
    await db.commit()
    logger.info("_complete_task: commited, task.record_id=%s", task.record_id)


async def _fail_task(db: AsyncSession, task_id: str, error_message: str) -> None:
    task = await _get_task(db, task_id)
    task.status = "FAILED"
    task.error_message = error_message
    await db.commit()
    await _add_task_event(db, task_id, "分析失败")


async def run_analysis(task_id: str, meal_type: str, remark: str | None = None) -> None:
    """执行开放式 AI 识别 + RAG 营养检索分析 pipeline。

    新流程:
    1. OCR → 2. AI Vision 识别 → 3. 食物名标准化
    4. 营养参考检索 → 5. 营养估算 → 6. AI 总结 → 7. 保存
    """
    async with async_session() as db:
        remark = remark or ""
        task = await _get_task(db, task_id)
        user_id = str(task.user_id)
        image_url = task.image_url or ""
        image_path = _image_url_to_path(image_url)

        ocr_text: str | None = None
        ocr_engine = "mock"
        recognition_result = None
        ai_engine = ""
        ai_summary_text: str | None = None
        ai_latency_val = ""

        for status, progress, eta, event_title in STAGES:
            await _update_task_status(db, task_id, status, progress, eta)
            await _add_task_event(db, task_id, event_title)
            logger.info("task=%s stage=%s progress=%s%%", task_id, status, progress)

            # Stage 1: OCR
            if status == "OCR_PROCESSING":
                ocr_result = recognize_image_text(image_url)
                ocr_text = ocr_result.text if ocr_result.success else ""
                ocr_engine = ocr_result.engine
                logger.info("task=%s OCR engine=%s text_len=%d", task_id, ocr_engine, len(ocr_text or ""))

            # Stage 2: AI Vision Recognition
            if status == "AI_RECOGNITION":
                if image_path:
                    recognition_result = recognize_food(image_path)
                else:
                    recognition_result = None

                if recognition_result is None or not recognition_result.is_food_detected:
                    reason = recognition_result.non_food_reason if recognition_result else "无法识别图片内容"
                    await _add_task_event(db, task_id, "未识别到可分析的食物")
                    await _update_task_status(db, task_id, "SUCCESS", 100, 0)

                    # 创建非食物记录
                    record = await _create_food_record(
                        db, task_id, user_id, meal_type, remark, image_url,
                        ocr_text=ocr_text, ocr_engine=ocr_engine,
                        status_label="未识别到食物",
                    )
                    record.summary = f"未识别到可分析的食物。{reason}"
                    record.prompt_version = f"{ocr_engine}-ocr+vision-nonfood"[:50]
                    await db.commit()
                    await _complete_task(db, task_id, str(record.id))
                    logger.warning("task=%s non-food: %s", task_id, reason)
                    return

                logger.info("task=%s recognition items=%d confidence=%.2f",
                            task_id, len(recognition_result.food_items), recognition_result.confidence)

                # Normalize mode name: accept legacy "whole_dish" as "dish_with_components"
                if recognition_result.analysis_mode == "whole_dish":
                    recognition_result.analysis_mode = "dish_with_components"

                # Fallback: generate components if AI didn't return any for dish_with_components/mixed
                for item in recognition_result.food_items:
                    if item.role == "main_dish" and not item.components and recognition_result.analysis_mode in ("dish_with_components", "mixed"):
                        item.components = generate_fallback_components(
                            food_name=item.food_name,
                            main_weight_g=item.estimated_weight_g or 0,
                            main_calories=item.calories or 0,
                        )
                        logger.info("task=%s fallback: generated %d components for %s",
                                    task_id, len(item.components), item.food_name)

                # Normalize: derive dish totals from components, remove component-only items
                original_count = len(recognition_result.food_items)
                recognition_result.food_items = normalize_food_items(recognition_result.food_items, recognition_result.analysis_mode)
                if len(recognition_result.food_items) < original_count:
                    logger.info("task=%s normalized: %d → %d items (removed %d components)",
                                task_id, original_count, len(recognition_result.food_items),
                                original_count - len(recognition_result.food_items))

            # Stage 3: Food Name Normalization
            if status == "NORMALIZING":
                norm_results = []
                for item in recognition_result.food_items:
                    norm = normalize_food_name(
                        item.food_name,
                        item.category,
                        recognition_result.scene_description,
                    )
                    norm_results.append(norm)
                logger.info("task=%s normalized %d food items", task_id, len(norm_results))

            # Stage 4: Nutrition Reference Retrieval
            if status == "RETRIEVING":
                refs_map = {}
                for item in recognition_result.food_items:
                    norm = normalize_food_name(
                        item.food_name, item.category,
                        recognition_result.scene_description,
                    )
                    refs = retrieve_nutrition_references(
                        food_name=norm["normalized_name"],
                        category=norm["category"],
                        search_queries=norm["search_queries"],
                    )
                    refs_map[item.food_name] = refs
                logger.info("task=%s retrieved refs for %d items", task_id, len(refs_map))

            # Stage 5: Nutrition Estimation
            if status == "ESTIMATING":
                estimated_items = []
                for item in recognition_result.food_items:
                    est = estimate_nutrition(item)
                    estimated_items.append(est)
                logger.info("task=%s estimated %d items", task_id, len(estimated_items))

            # Stage 6: AI Summary
            if status == "AI_SUMMARIZING":
                if estimated_items:
                    total_cal = sum(e.calories for e in estimated_items)
                    total_pro = sum(e.protein for e in estimated_items)
                    total_carb = sum(e.carbs for e in estimated_items)
                    total_fat = sum(e.fat for e in estimated_items)
                    food_names = "、".join(item.food_name for item in recognition_result.food_items)
                    any_estimated = any(e.estimated for e in estimated_items)
                else:
                    total_cal = total_pro = total_carb = total_fat = 0
                    food_names = ""
                    any_estimated = True

                ai_result = generate_summary(
                    food_name=food_names,
                    total_calories=int(total_cal), protein=int(total_pro),
                    carbs=int(total_carb), fat=int(total_fat),
                    meal_type=meal_type, remark=remark, ocr_text=ocr_text or "",
                    estimated=any_estimated,
                )
                ai_summary_text = ai_result.text
                ai_latency_val = ai_result.latency
                ai_engine = ai_result.engine
                logger.info("task=%s AI engine=%s latency=%s", task_id, ai_engine, ai_latency_val)

            time.sleep(0.5)

        # Stage 7: Save FoodRecord + FoodItems
        source_tag = recognition_result.food_items[0].source if recognition_result and recognition_result.food_items else "unknown"
        prompt_ver = f"{ocr_engine}-ocr+{source_tag}+{ai_engine}" if ai_engine else f"{ocr_engine}-ocr+{source_tag}"
        prompt_ver = prompt_ver[:50]

        record = await _create_food_record(
            db, task_id, user_id, meal_type, remark, image_url,
            ocr_text=ocr_text, ocr_engine=ocr_engine,
            ai_summary=ai_summary_text, ai_latency=ai_latency_val, ai_engine=ai_engine,
            analysis_mode=recognition_result.analysis_mode if recognition_result else "dish_with_components",
        )

        # Write food items with estimated nutrition
        total_cal = sum(e.calories for e in estimated_items)
        total_pro = sum(e.protein for e in estimated_items)
        total_carb = sum(e.carbs for e in estimated_items)
        total_fat = sum(e.fat for e in estimated_items)

        record.total_calories = int(total_cal)
        record.protein = int(total_pro)
        record.carbohydrate = int(total_carb)
        record.fat = int(total_fat)
        record.prompt_version = prompt_ver
        await db.commit()

        for i, (rec_item, est) in enumerate(zip(recognition_result.food_items, estimated_items), start=1):
            # Serialize components (already generated + normalized in AI_RECOGNITION stage)
            components_json = [c.model_dump() for c in rec_item.components] if rec_item.components else []
            db.add(FoodItem(
                record_id=record.id,
                food_name=rec_item.food_name,
                category=rec_item.category or "unknown",
                weight=f"{est.estimated_weight_g:.0f}g",
                calories=int(est.calories),
                protein=int(est.protein),
                carbs=int(est.carbs),
                fat=int(est.fat),
                confidence=est.confidence,
                source=est.source,
                estimated=est.estimated,
                sort_order=i,
                components=components_json,
                dish_family=rec_item.dish_family,
                alternatives=rec_item.alternatives if rec_item.alternatives else None,
                user_correction=rec_item.user_correction,
            ))
        await db.commit()
        logger.info("task=%s saved %d items cal=%d pro=%d carb=%d fat=%d",
                    task_id, len(estimated_items), int(total_cal), int(total_pro), int(total_carb), int(total_fat))

        await _complete_task(db, task_id, str(record.id))
        logger.info("task=%s SUCCESS record=%s prompt=%s", task_id, record.id, record.prompt_version)


# 向后兼容别名
run_mock_analysis = run_analysis


MOCK_MACRO_TARGETS = {"protein": 120, "carbs": 250, "fat": 70}


async def get_food_detail(db: AsyncSession, record_id: str) -> dict:
    """查询 FoodRecord 详情，包含 items、AI 日志、宏量营养素对比。"""
    from sqlalchemy import select

    record_result = await db.execute(
        select(FoodRecord).where(FoodRecord.id == record_id)
    )
    record = record_result.scalar_one()

    items_result = await db.execute(
        select(FoodItem)
        .where(FoodItem.record_id == record_id)
        .order_by(FoodItem.sort_order.asc())
    )
    food_items = items_result.scalars().all()

    macro_targets = dict(MOCK_MACRO_TARGETS)
    macro_percentages = {
        "protein": round(record.protein / macro_targets["protein"] * 100),
        "carbs": round(record.carbohydrate / macro_targets["carbs"] * 100),
        "fat": round(record.fat / macro_targets["fat"] * 100),
    }

    has_food = len(food_items) > 0 and record.total_calories > 0
    non_food_reason = None if has_food else (record.summary or "未识别到可分析的食物")

    return {
        "record": {
            "id": str(record.id),
            "status": record.status,
            "status_label": record.status_label,
            "confirmed_at": record.confirmed_at.isoformat() if record.confirmed_at else None,
            "is_food_detected": has_food,
            "non_food_reason": non_food_reason,
            "total_calories": record.total_calories,
            "protein": record.protein,
            "carbohydrate": record.carbohydrate,
            "fat": record.fat,
            "target_calories": record.target_calories,
            "image_url": record.image_url,
            "created_at": record.created_at,
            "analysis_mode": record.analysis_mode or "dish_with_components",
            "summary": record.summary,
            "ocr_text": record.ocr_text,
        },
        "food_items": [
            {
                "id": str(item.id),
                "food_name": item.food_name,
                "weight": item.weight,
                "calories": item.calories,
                "protein": item.protein,
                "carbohydrate": item.carbs,
                "fat": item.fat,
                "category": item.category,
                "confidence": item.confidence,
                "source": item.source,
                "estimated": item.estimated,
                "image_url": item.image_url,
                "dish_family": item.dish_family,
                "alternatives": item.alternatives if item.alternatives else [],
                "user_correction": item.user_correction,
                "components": [
                    {
                        "name": c.get("name", ""),
                        "confidence": c.get("confidence", 0.5),
                        "estimated_weight_g": c.get("estimated_weight_g"),
                        "calories": c.get("calories"),
                        "protein": c.get("protein"),
                        "carbs": c.get("carbs"),
                        "fat": c.get("fat"),
                        "role": c.get("role", "ingredient"),
                        "include_in_total": c.get("include_in_total", False),
                    }
                    for c in (item.components or [])
                ],
            }
            for item in food_items
        ],
        "ai_log": {
            "prompt_version": record.prompt_version,
            "latency": record.ai_latency,
            "cache_hit": record.cache_hit,
        },
        "macro_targets": macro_targets,
        "macro_percentages": macro_percentages,
    }


async def confirm_food_record(
    db: AsyncSession,
    record_id: str,
    user_id: str,
) -> FoodRecord:
    """确认保存草稿为正式记录。已确认的记录幂等返回。"""
    result = await db.execute(select(FoodRecord).where(FoodRecord.id == record_id))
    record = result.scalar_one_or_none()
    if record is None or str(record.user_id) != user_id:
        raise ValueError("记录不存在或无权访问")

    if record.status == "confirmed":
        return record

    record.status = "confirmed"
    record.confirmed_at = datetime.now(timezone.utc)
    record.status_label = "用户已确认"

    await db.commit()
    await db.refresh(record)
    return record


async def update_draft_record(
    db: AsyncSession,
    record_id: str,
    user_id: str,
    meal_type: str | None = None,
    remark: str | None = None,
    items: list[dict] | None = None,
    analysis_mode: str | None = None,
    dish: dict | None = None,
    components: list[dict] | None = None,
    user_correction: str | None = None,
) -> FoodRecord:
    """更新草稿记录。只允许 status=draft 的记录。

    dish_with_components 模式：从 components 汇总计算 dish totals。
    component_sum 模式：按旧逻辑逐 item 处理。
    """
    result = await db.execute(select(FoodRecord).where(FoodRecord.id == record_id))
    record = result.scalar_one_or_none()
    if record is None or str(record.user_id) != user_id:
        raise ValueError("记录不存在或无权访问")
    if record.status == "confirmed":
        raise ValueError("已保存的正式记录不可编辑")

    if meal_type is not None:
        record.meal_type = meal_type
    if remark is not None:
        record.remark = remark

    # --- dish_with_components: save components + recalculate dish from components ---
    if analysis_mode in ("dish_with_components", "whole_dish") and components is not None:
        await _update_dish_with_components(db, record, components, user_correction)
        await db.commit()
        await db.refresh(record)
        return record

    # --- component_sum / mixed: existing item-based logic ---
    if items is not None and len(items) > 0:
        # Phase 1: Load old items + validate + compute new item data (NO DB writes)
        old_result = await db.execute(
            select(FoodItem).where(FoodItem.record_id == record_id).order_by(FoodItem.sort_order.asc())
        )
        old_items_map: dict[str, FoodItem] = {str(it.id): it for it in old_result.scalars().all()}

        # Collect context for presence check
        context_names = [it.food_name for it in old_items_map.values() if it.food_name]
        image_path = _image_url_to_path(record.image_url) if record.image_url else ""

        new_items_data: list[dict] = []
        total_cal = total_pro = total_carb = total_fat = 0

        for i, item_data in enumerate(items, start=1):
            food_name = item_data.get("food_name") or item_data.get("name") or item_data.get("display_name") or ""
            new_weight_str = item_data.get("weight") or item_data.get("quantity_description") or ""
            category = item_data.get("category", "unknown")

            # Find matching old item by id
            item_id = item_data.get("id", "")
            is_new = item_data.get("is_new", False) or (not item_id or str(item_id).startswith("temp-") or str(item_id).startswith("new-"))
            name_changed = item_data.get("name_changed", False) or is_new
            old_item = old_items_map.get(str(item_id)) if item_id and not is_new else None

            # Validate user-provided food name
            if food_name:
                from app.services.food_name_validator import validate_manual_food_name
                validation = validate_manual_food_name(food_name)
                if not validation["valid"]:
                    raise ValueError(validation["reason"])
                food_name = validation["normalized_name"]

            # Determine nutrition
            calories = item_data.get("calories", 0) or 0
            protein = item_data.get("protein", 0) or 0
            carbs = item_data.get("carbs", 0) or 0
            fat = item_data.get("fat", 0) or 0
            estimated_source = "manual"
            estimated_conf = 1.0

            if name_changed or is_new:
                # Image presence check for new/renamed items
                if food_name and food_name not in context_names:
                    try:
                        from app.services.food_presence_checker import check_food_presence
                        presence = check_food_presence(image_path or "", food_name, context_names)
                        if presence.get("present") == "false":
                            raise ValueError(f"图片中未识别到「{food_name}」。请确认添加的是图片中存在的食物。")
                        if presence.get("present") == "uncertain":
                            estimated_source = "manual_unverified"
                            estimated_conf = 0.5
                    except ValueError:
                        raise
                    except Exception as exc:
                        logger.exception("presence check failed for %s: %s", food_name, exc)
                        raise ValueError("图片食物校验暂时失败，请稍后重试")

                # Name changed or new item: re-estimate via RAG / fallback
                est = _estimate_new_item(food_name, _parse_weight_grams(new_weight_str or ""), category)
                calories = int(est.calories)
                protein = int(est.protein)
                carbs = int(est.carbs)
                fat = int(est.fat)
                estimated_source = est.source
                estimated_conf = est.confidence
            elif old_item and new_weight_str:
                # Existing item, name unchanged: scale by weight ratio
                old_weight = _parse_weight_grams(old_item.weight)
                new_weight = _parse_weight_grams(new_weight_str)
                if old_weight > 0 and new_weight > 0 and old_item.calories > 0:
                    ratio = new_weight / old_weight
                    calories = int(old_item.calories * ratio)
                    protein = int(old_item.protein * ratio)
                    carbs = int(old_item.carbs * ratio)
                    fat = int(old_item.fat * ratio)

            total_cal += calories
            total_pro += protein
            total_carb += carbs
            total_fat += fat
            new_items_data.append({
                "food_name": food_name or (old_item.food_name if old_item else ""),
                "weight": new_weight_str,
                "category": category or (old_item.category if old_item else "unknown"),
                "calories": calories, "protein": protein, "carbs": carbs, "fat": fat,
                "confidence": estimated_conf, "source": estimated_source, "estimated": True,
                "sort_order": i,
            })

        # Phase 2: All validation passed — delete old items + insert new
        for old in old_items_map.values():
            await db.delete(old)
        await db.flush()

        for item in new_items_data:
            db.add(FoodItem(
                record_id=record.id,
                food_name=item["food_name"],
                weight=item["weight"],
                category=item["category"],
                calories=item["calories"],
                protein=item["protein"],
                carbs=item["carbs"],
                fat=item["fat"],
                confidence=item["confidence"],
                source=item["source"],
                estimated=item["estimated"],
                sort_order=item["sort_order"],
            ))

        record.total_calories = total_cal
        record.protein = total_pro
        record.carbohydrate = total_carb
        record.fat = total_fat

    await db.commit()
    await db.refresh(record)
    return record


async def _update_dish_with_components(db: AsyncSession, record: FoodRecord, components: list[dict], user_correction: str | None = None) -> None:
    """dish_with_components 模式：用 components 汇总重算 dish 总量并保存。"""
    from sqlalchemy import select as sa_select
    items_result = await db.execute(
        sa_select(FoodItem)
        .where(FoodItem.record_id == record.id)
        .order_by(FoodItem.sort_order.asc())
    )
    food_items = items_result.scalars().all()
    if not food_items:
        logger.warning("_update_dish_with_components: no food items for record %s", record.id)
        return

    dish_item = food_items[0]
    # dish name is read-only — keep existing name
    dish_name = dish_item.food_name

    # Recalculate nutrition for each component from name + weight
    from app.schemas.ai_food import RecognizedFoodItem
    from app.services.nutrition_estimator import estimate_nutrition

    recalculated: list[dict] = []
    total_weight = 0.0
    total_cal = total_pro = total_carb = total_fat = 0.0

    for c in components:
        name = str(c.get("name", ""))
        weight = c.get("estimated_weight_g") or 0
        existing_cal = c.get("calories")

        # Re-estimate if weight was provided but calories weren't, or if weight changed significantly
        if name and weight > 0:
            item = RecognizedFoodItem(food_name=name, estimated_weight_g=weight, source="manual")
            est = estimate_nutrition(item)
            cal = est.calories
            pro = est.protein
            carb = est.carbs
            fat = est.fat
            conf = est.confidence
        else:
            cal = existing_cal or 0
            pro = c.get("protein") or 0
            carb = c.get("carbs") or 0
            fat = c.get("fat") or 0
            conf = c.get("confidence", 0.5)

        recalculated.append({
            "name": name,
            "estimated_weight_g": weight,
            "calories": cal,
            "protein": pro,
            "carbs": carb,
            "fat": fat,
            "confidence": c.get("confidence", conf),
            "include_in_total": c.get("include_in_total", True),
        })
        total_weight += weight
        total_cal += cal
        total_pro += pro
        total_carb += carb
        total_fat += fat

    # Update FoodItem
    dish_item.food_name = dish_name  # preserve
    dish_item.weight = f"{total_weight:.0f}g"
    dish_item.calories = int(total_cal)
    dish_item.protein = int(total_pro)
    dish_item.carbs = int(total_carb)
    dish_item.fat = int(total_fat)
    dish_item.confidence = 1.0
    dish_item.source = "manual"
    dish_item.estimated = True
    if components:
        dish_item.components = recalculated
    if user_correction:
        dish_item.user_correction = user_correction
        dish_item.food_name = user_correction
        dish_item.confidence = 1.0

    # Update FoodRecord totals from components if present
    if components:
        record.total_calories = int(total_cal)
        record.protein = int(total_pro)
        record.carbohydrate = int(total_carb)
        record.fat = int(total_fat)

    logger.info("_update_dish_with_components: record=%s dish=%s weight=%.0fg cal=%d components=%d",
                record.id, dish_name, total_weight, int(total_cal), len(components))


def _parse_weight_grams(weight_str: str) -> float:
    """从重量字符串提取克数，如 '150g', '约200g', '1碗'"""
    import re
    if not weight_str:
        return 0.0
    m = re.search(r"(\d+(?:\.\d+)?)", str(weight_str))
    return float(m.group(1)) if m else 0.0


def _estimate_new_item(food_name: str, weight_g: float, category: str = "unknown") -> "NutritionEstimate":
    """为新添加的食物估算营养。使用 RAG 检索 + 类别兜底，保证不全为0。"""
    from app.schemas.ai_food import RecognizedFoodItem, NutritionEstimateResult
    from app.services.nutrition_estimator import estimate_nutrition

    item = RecognizedFoodItem(
        food_name=food_name,
        category=category,
        estimated_weight_g=weight_g if weight_g > 0 else 200.0,
        quantity_description=f"{weight_g:.0f}g" if weight_g > 0 else None,
        source="manual",
        estimated=True,
    )
    result = estimate_nutrition(item)
    return NutritionEstimate(
        calories=int(result.calories),
        protein=int(result.protein),
        carbs=int(result.carbs),
        fat=int(result.fat),
        estimated=True,
        confidence=result.confidence,
        source=result.source,
    )
