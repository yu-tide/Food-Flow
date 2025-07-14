#!/usr/bin/env python3
"""Food Parser debug - reads real OCR text from DB"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.db.session import async_session
from app.models.food_record import FoodRecord
from app.services.food_parser import parse_ocr_text, _normalize_text, _SEP, _extract_food_name


async def main():
    async with async_session() as db:
        r = await db.execute(
            select(FoodRecord.ocr_text, FoodRecord.prompt_version)
            .order_by(FoodRecord.created_at.desc())
            .limit(1)
        )
        row = r.first()
        if not row:
            print("No food_record found")
            return

        ocr_text, prompt_ver = row
        print(f"Current prompt_version: {prompt_ver}")
        print(f"ocr_text len: {len(ocr_text)}")
        print(f"ocr_text repr: {repr(ocr_text)}")
        print()

        # Show each char's Unicode codepoint for first 40 chars
        print("First 20 chars (codepoints):")
        for i, ch in enumerate(ocr_text[:20]):
            print(f"  [{i}] U+{ord(ch):04X} {repr(ch)}")
        print()

        # Normalize
        norm = _normalize_text(ocr_text)
        print(f"normalized repr: {repr(norm)}")
        print()

        # Parts
        parts = [p.strip() for p in _SEP.split(norm) if p.strip()]
        print(f"parts ({len(parts)}):")
        for i, p in enumerate(parts):
            print(f"  [{i}] {repr(p)}")
        print()

        # Food name
        name = _extract_food_name(norm)
        print(f"food_name: {repr(name)}")
        print()

        # Parse
        result = parse_ocr_text(ocr_text)
        print(f"success: {result.success}")
        print(f"engine:  {result.engine}")
        print(f"items:   {len(result.items)}")
        if result.items:
            item = result.items[0]
            print(f"  food_name: {repr(item.food_name)}")
            print(f"  weight:    {item.weight}")
            print(f"  calories:  {item.calories}")
            print(f"  protein:   {item.protein}")
            print(f"  fat:       {item.fat}")
            print(f"  carbs:     {item.carbs}")
        print(f"totals: cal={result.total_calories} pro={result.total_protein} fat={result.total_fat} carb={result.total_carbs}")


if __name__ == "__main__":
    asyncio.run(main())
