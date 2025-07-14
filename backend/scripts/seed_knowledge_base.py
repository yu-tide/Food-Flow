"""Seed knowledge base with initial nutrition/app-help documents."""
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session
from app.models.knowledge import KnowledgeChunk, KnowledgeDocument


SEED_DOCUMENTS = [
    {
        "title": "为什么未保存记录不进入统计",
        "source_type": "app_help",
        "content": (
            "FoodFlow 的饮食记录分为两个阶段：分析草稿（draft）和已保存记录（confirmed）。"
            "只有点击「保存记录」后，记录状态才会变为 confirmed，才会进入首页热量统计、每周趋势、营养分析和最近饮食记录。"
            "这样设计是为了让你有机会在确认页校准菜名、调整成分重量、删除误识别成分，确保最终保存的数据准确。"
            "如果你发现首页热量为 0，很可能是因为分析完成后还没有点击保存。"
        ),
    },
    {
        "title": "如何保存饮食记录",
        "source_type": "app_help",
        "content": (
            "保存饮食记录的完整流程：1. 上传餐食图片 → 2. 等待 AI 分析完成 → 3. 进入分析结果页查看识别结果 → "
            "4. 如需修改，点击编辑按钮进入确认页校准菜名和重量 → 5. 确认无误后返回分析结果页 → 6. 点击「保存记录」按钮。"
            "保存后记录状态变为 confirmed，才会进入所有统计。"
        ),
    },
    {
        "title": "如何校准菜名",
        "source_type": "app_help",
        "content": (
            "对于混合菜品（如冒菜、麻辣烫、火锅、麻辣香锅等），AI 可能无法 100% 准确判断具体菜名。"
            "在确认页面中，主餐卡片会显示菜名候选列表，你可以点选更准确的名称。"
            "点击候选后菜名立即更新，后续保存时会记录你的校正选择。"
            "菜名校准不会重新估算营养，也不会清空已有成分。"
        ),
    },
    {
        "title": "如何调整成分重量",
        "source_type": "app_help",
        "content": (
            "在确认页面的成分明细中，每项成分的重量是可编辑的。"
            "修改重量后，该成分的热量和蛋白质等宏量营养素会按营养密度自动重算。"
            "你不需要手动输入热量——系统会根据重量和营养参考数据自动计算。"
            "修改后的成分合计会实时更新顶部的主餐总量。"
        ),
    },
    {
        "title": "每周统计如何计算",
        "source_type": "app_help",
        "content": (
            "每周统计基于最近 7 天的已保存记录计算。平均每日热量 = 本周所有 confirmed 记录的总热量 / 7。"
            "蛋白质达标天数统计每天蛋白质摄入是否达到你在设置中设定的目标。"
            "餐别分布按早餐、午餐、晚餐、加餐四个类别展示本周热量占比。"
            "只有 confirmed 记录参与统计，draft 和分析中的记录不会计入。"
        ),
    },
    {
        "title": "营养目标如何生成",
        "source_type": "app_help",
        "content": (
            "营养目标可以在设置页的「营养目标」模块中生成。"
            "填写性别、年龄、身高、体重、活动水平和目标类型后，点击「生成推荐目标」，"
            "系统会使用 Mifflin-St Jeor 公式计算基础代谢率（BMR），再根据活动水平和目标类型调整，"
            "给出每日热量、蛋白质、碳水和脂肪的推荐值。"
            "你也可以手动输入自定义目标。"
        ),
    },
    {
        "title": "蛋白质摄入建议",
        "source_type": "nutrition_knowledge",
        "content": (
            "蛋白质是肌肉修复和维持代谢的重要营养素。一般成人建议每日摄入 1.2-1.6g/kg 体重。"
            "减脂期建议提高到 1.6-2.0g/kg，以保护肌肉不流失。增肌期建议 1.8-2.2g/kg。"
            "优质蛋白来源包括鸡蛋、鸡胸肉、鱼虾、瘦牛肉、豆腐、豆浆、牛奶和酸奶。"
            "一顿正餐建议蛋白质占比 25-35%。如果全天蛋白质摄入不足，可以增加蛋、鱼或豆制品的比例。"
        ),
    },
    {
        "title": "减脂热量缺口",
        "source_type": "nutrition_knowledge",
        "content": (
            "减脂的核心是保持适当的热量缺口。一般建议每日热量缺口在 300-500 kcal 之间，"
            "即摄入比消耗少 300-500 kcal。每周约减少 0.3-0.5 kg 体重是安全且可持续的速度。"
            "不建议追求过大缺口（>800 kcal），容易导致肌肉流失和代谢下降。"
            "减脂期间尤其要保证蛋白质摄入（建议 1.6-2.0g/kg），同时适当控制碳水和脂肪。"
        ),
    },
    {
        "title": "脂肪摄入过高如何处理",
        "source_type": "nutrition_knowledge",
        "content": (
            "如果某顿饭或某天脂肪摄入明显偏高，可以从以下方面调整："
            "1. 减少油炸、红烧、油焖类菜品。2. 选择清蒸、水煮、凉拌的烹饪方式。"
            "3. 注意汤底和酱料——麻辣烫、火锅的汤底和蘸料含大量油脂。"
            "4. 控制肥肉、加工肉制品（午餐肉、香肠等）的摄入。"
            "5. 增加蔬菜比例，蔬菜热量低且增加饱腹感。"
            "成人每日脂肪摄入建议占总热量的 20-30%，约 40-70g。"
        ),
    },
    {
        "title": "碳水摄入和运动关系",
        "source_type": "nutrition_knowledge",
        "content": (
            "碳水化合物是身体的主要能量来源，尤其对运动表现至关重要。"
            "一般成人每日碳水建议摄入 3-5g/kg 体重。运动量较大时（如跑步、健身、球类运动），"
            "可以适当提高到 5-7g/kg。运动前 1-2 小时补充碳水可提升耐力表现。"
            "运动后 30-60 分钟内补充碳水+蛋白质有助于糖原恢复和肌肉修复。"
            "优质碳水来源包括米饭、全麦面包、燕麦、红薯、土豆、水果。"
        ),
    },
    {
        "title": "冒菜、麻辣烫、火锅热量差异",
        "source_type": "nutrition_knowledge",
        "content": (
            "冒菜、麻辣烫和火锅虽然都是川式红汤类菜品，但热量差异明显。"
            "冒菜通常汤少、油量中等，一般 600-900 kcal/份。"
            "麻辣烫汤多、油量因店铺差异大，一般 500-1000 kcal/份。"
            "火锅热量受锅底（清汤 vs 牛油）、蘸料（香油碟 vs 干碟）和食材（肥牛 vs 蔬菜）影响极大，"
            "一餐火锅可高达 1200-2000 kcal。"
            "控制热量的关键在于：选择清汤锅底、多用蔬菜和瘦肉、控制油脂蘸料用量。"
        ),
    },
]


async def seed():
    async with async_session() as db:  # type: AsyncSession
        for doc in SEED_DOCUMENTS:
            # Check if already seeded
            existing = await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.title == doc["title"])
            )
            if existing.scalar_one_or_none():
                print(f"  SKIP (exists): {doc['title']}")
                continue

            d = KnowledgeDocument(
                title=doc["title"],
                source_type=doc["source_type"],
                content=doc["content"],
            )
            db.add(d)
            await db.flush()

            c = KnowledgeChunk(
                document_id=d.id,
                chunk_index=0,
                content=doc["content"],
            )
            db.add(c)
            print(f"  OK: {doc['title']}")

        await db.commit()
        print(f"\nSeed complete: {len(SEED_DOCUMENTS)} documents")


if __name__ == "__main__":
    asyncio.run(seed())
